import os, json, time, hashlib, requests
from typing import Dict, List, Optional
import numpy as np, faiss
from app.core.config import INDEX_PATH, DATA_DIR, CACHE_DIR
from app.core.logger import get_logger
from app.services.parser import parse_pdf_bytes, extract_toc_candidates
from openai import OpenAI
from app.core.config import OPENAI_API_KEY, CHAT_MODEL
from app.services.chunker import chunk_pages
from app.services.embedder import embed_texts
from app.repositories.book_repository import BookRepository
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.chapter_repository import ChapterRepository
from app.repositories.lesson_repository import LessonRepository

logger = get_logger(__name__)

def _ensure_index(dim: int) -> faiss.IndexFlatL2:
    if os.path.exists(INDEX_PATH):
        return faiss.read_index(INDEX_PATH)
    os.makedirs(DATA_DIR, exist_ok=True)
    index = faiss.IndexFlatL2(dim)
    faiss.write_index(index, INDEX_PATH)
    return index

# Removed _ensure_meta() - now using MongoDB repositories

def _cache_key(book_name: str, grade: int, pdf_bytes: bytes) -> str:
    return hashlib.md5((book_name+str(grade)+str(len(pdf_bytes))).encode()).hexdigest()

def _compute_book_id(book_name: str, grade: int) -> str:
    """
    Tạo book_id ổn định từ tên sách + grade (không phụ thuộc đường dẫn PDF).
    """
    base = f"{book_name.strip().lower()}::{grade}"
    return hashlib.md5(base.encode("utf-8")).hexdigest()

def _compute_chapter_id(book_id: str, chapter_title: str) -> str:
    """Tạo chapter_id từ book_id + chapter_title"""
    base = f"{book_id}::{chapter_title.strip().lower()}"
    return hashlib.md5(base.encode("utf-8")).hexdigest()

def _compute_lesson_id(chapter_id: str, lesson_title: str) -> str:
    """Tạo lesson_id từ chapter_id + lesson_title"""
    base = f"{chapter_id}::{lesson_title.strip().lower()}"
    return hashlib.md5(base.encode("utf-8")).hexdigest()

def _build_page_assignments(structured: Dict) -> Dict[int, Dict[str, str]]:
    """
    Tạo mapping page -> {chapter, lesson} dựa vào TOC đã chuẩn hoá.
    - Mỗi bài có 'page' (nếu có). Ta sắp xếp bài theo trang trong từng chương.
    - Range bài: từ trang của bài đến trang trước bài kế tiếp trong cùng chương.
    - Range chương: từ bài đầu tiên của chương đến trước bài đầu tiên của chương kế tiếp.
    Trả về: dict {page_number: {"chapter": ch, "lesson": le_or_None}}
    """
    page_map: Dict[int, Dict[str, str]] = {}
    # Chuẩn bị danh sách chapter theo thứ tự xuất hiện (bằng trang bài đầu)
    chapter_order: List[tuple] = []
    chapter_lessons_pages: Dict[str, List[tuple]] = {}
    for ch, info in structured.items():
        lesson_pages = info.get("lesson_pages", {})
        pairs = [(lp, lt) for lt, lp in lesson_pages.items() if isinstance(lp, int)]
        pairs.sort(key=lambda x: x[0])
        chapter_lessons_pages[ch] = pairs
        first_page = pairs[0][0] if pairs else None
        if first_page is not None:
            chapter_order.append((first_page, ch))
    chapter_order.sort(key=lambda x: x[0])

    # Gán range chương
    chapter_ranges: List[tuple] = []  # (start, end, chapter)
    for idx, (start_page, ch) in enumerate(chapter_order):
        end_page = None
        if idx + 1 < len(chapter_order):
            end_page = chapter_order[idx + 1][0] - 1
        chapter_ranges.append((start_page, end_page, ch))

    # Gán range bài trong mỗi chương
    lesson_ranges: List[tuple] = []  # (start, end, chapter, lesson)
    for ch, pairs in chapter_lessons_pages.items():
        for i, (start, title) in enumerate(pairs):
            end = None
            if i + 1 < len(pairs):
                end = pairs[i + 1][0] - 1
            else:
                # Nếu là bài cuối, kết thúc tại end của chương (nếu có)
                ch_range = next(((s, e, c) for (s, e, c) in chapter_ranges if c == ch), None)
                if ch_range:
                    end = ch_range[1]
            lesson_ranges.append((start, end, ch, title))

    # Duyệt tạo page_map
    def _in_range(p: int, rng: tuple) -> bool:
        s, e = rng
        if s is None:
            return False
        if e is None:
            return p >= s
        return s <= p <= e

    # Phủ bài trước, rồi fallback chương
    for (start, end, ch, le) in lesson_ranges:
        if start is None:
            continue
        last = start if end is None else end
        for p in range(start, last + 1):
            page_map[p] = {"chapter": ch, "lesson": le}

    for (start, end, ch) in chapter_ranges:
        if start is None:
            continue
        last = start if end is None else end
        for p in range(start, last + 1):
            if p not in page_map:
                page_map[p] = {"chapter": ch, "lesson": None}

    return page_map

def ingest_pdf(
    pdf_url: str,
    book_name: str,
    grade: int,
    force_reparse: bool = False,
    force_clear_cache: bool = False,
) -> Dict:
    t0 = time.time()
    os.makedirs(CACHE_DIR, exist_ok=True)
    # Optionally clear entire cache per request
    if force_clear_cache and os.path.exists(CACHE_DIR):
        for f in os.listdir(CACHE_DIR):
            try:
                os.remove(os.path.join(CACHE_DIR, f))
            except Exception:
                pass
    logger.info(f"Downloading PDF: {pdf_url}")
    pdf_bytes = requests.get(pdf_url).content

    key = _cache_key(book_name, grade, pdf_bytes)
    cache_file = os.path.join(CACHE_DIR, f"{key}_pages.json")

    if os.path.exists(cache_file) and not force_reparse:
        pages = json.load(open(cache_file, "r", encoding="utf-8"))
        logger.info(f"Loaded cached pages: {cache_file}")
        # Kiểm tra chất lượng cache: có chapter/lesson hợp lệ không
        # Invalid patterns: contains <<<, >>, or doesn't follow expected format
        has_invalid = False
        for p in pages[:10]:
            ch = p.get("chapter", "").strip()
            le = p.get("lesson", "").strip()
            # Check for invalid patterns
            if ch and (ch.startswith("<<") or ch.startswith(">>") or 
                      (not ch.startswith("Chương") and not ch.startswith("Phần"))):
                has_invalid = True
                break
            if le and (le.startswith("<<") or le.startswith(">>") or 
                      not le.startswith("Bài")):
                has_invalid = True
                break
        needs_reparse = not any(p.get("chapter") or p.get("lesson") for p in pages[:10]) or has_invalid
        if needs_reparse:
            logger.info("Cache lacks valid chapter/lesson info, re-parsing...")
            pages = parse_pdf_bytes(pdf_bytes, lang="vie", prefer_text=True)
            json.dump(pages, open(cache_file, "w", encoding="utf-8"), ensure_ascii=False)
            logger.info(f"Re-cached pages with structure: {cache_file}")
    else:
        pages = parse_pdf_bytes(pdf_bytes, lang="vie", prefer_text=True)
        json.dump(pages, open(cache_file, "w", encoding="utf-8"), ensure_ascii=False)
        logger.info(f"Cached pages: {cache_file}")

    # Xây dựng cấu trúc chương/bài ưu tiên từ MỤC LỤC (nếu có)
    toc_result = extract_toc_candidates(pages)
    if isinstance(toc_result, tuple):
        toc, raw_toc_text = toc_result
    else:
        toc, raw_toc_text = toc_result, ""

    # Nếu có OpenAI key, nhờ LLM chuẩn hoá cấu trúc (kèm số trang)
    structured = {}
    if toc and OPENAI_API_KEY:
        try:
            client = OpenAI(api_key=OPENAI_API_KEY)
            prompt = {
                "instruction": (
                    "Bạn là trợ lý biên tập SGK. Dựa trên MỤC LỤC thô (có thể bị xuống dòng giữa chừng), "
                    "hãy tái cấu trúc đầy đủ tiêu đề CHƯƠNG và danh sách BÀI thuộc chương đó. "
                    "- Gộp các dòng bị ngắt dòng (ví dụ tiêu đề chương/bài trải trên 2-3 dòng) thành một tiêu đề chuẩn, đầy đủ ý.\n"
                    "- Đặt đúng bài vào đúng chương (ví dụ: \"Bài 9. Khoảng biến thiên và khoảng tứ phân vị\" thuộc Chương III).\n"
                    "- Giữ lại số trang của từng bài nếu có, và lấy trang đầu của chương là trang của bài đầu tiên trong chương (nếu biết).\n"
                    "- Giữ nguyên tiếng Việt, không dịch, không thêm/suy diễn tiêu đề mới.\n"
                    "- Chỉ trả về JSON theo đúng format:\n"
                    "{\n"
                    "  \"chapters\": [\n"
                    "    { \"title\": \"Chương I. ...\", \"lessons\": [{\"title\": \"Bài 1. ...\", \"page\": 5}, {\"title\": \"Bài 2. ...\", \"page\": 15}] },\n"
                    "    { \"title\": \"Chương II. ...\", \"lessons\": [...] }\n"
                    "  ]\n"
                    "}\n"
                ),
                "raw_toc_text": raw_toc_text or json.dumps(toc, ensure_ascii=False)
            }
            resp = client.chat.completions.create(
                model=CHAT_MODEL,
                messages=[
                    {"role": "system", "content": "Trả về JSON hợp lệ, không kèm giải thích."},
                    {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)}
                ],
                temperature=0,
                response_format={"type": "json_object"},
            )
            content = resp.choices[0].message.content
            data = json.loads(content)
            # Chuẩn hoá sang dict chapter -> {lessons:[]}
            structured = {}
            for ch in data.get("chapters", []):
                lessons = ch.get("lessons", [])
                structured[ch.get("title", "")] = {
                    "lessons": [l.get("title") for l in lessons if isinstance(l, dict)],
                    "lesson_pages": {l.get("title"): l.get("page") for l in lessons if isinstance(l, dict) and l.get("page")}
                }
        except Exception as e:
            logger.warning(f"TOC LLM normalize failed: {e}. Using heuristic TOC.")
            structured = {}
            for ch, info in toc.items():
                structured[ch] = {
                    "lessons": [l["title"] for l in info.get("lessons", [])],
                    "lesson_pages": {l["title"]: l["page"] for l in info.get("lessons", []) if l.get("page")}
                }
    else:
        structured = {}
        for ch, info in toc.items():
            structured[ch] = {
                "lessons": [l["title"] for l in info.get("lessons", [])],
                "lesson_pages": {l["title"]: l["page"] for l in info.get("lessons", []) if l.get("page")}
            }

    # Compute book_id
    book_id = _compute_book_id(book_name, grade)
    
    # Initialize repositories
    book_repo = BookRepository()
    chunk_repo = ChunkRepository()
    chapter_repo = ChapterRepository()
    lesson_repo = LessonRepository()
    
    # Create indexes if not exist
    book_repo.create_indexes()
    chunk_repo.create_indexes()
    chapter_repo.create_indexes()
    lesson_repo.create_indexes()
    
    # Delete existing data for this book if re-ingesting
    chunk_repo.delete_chunks_by_book(book_id)
    chapter_repo.delete_chapters_by_book(book_id)
    lesson_repo.delete_lessons_by_book(book_id)
    
    chunks = chunk_pages(pages, book_name, grade, size=800, overlap=100)
    texts = [c["text"] for c in chunks]
    vectors = embed_texts(texts)
    dim = len(vectors[0])

    # Get max embedding_index from existing chunks (if any)
    # For now, we'll use a simple approach: get max from all chunks
    max_index = 0
    try:
        # Get all chunks to find max index (could be optimized with aggregation)
        all_chunks = chunk_repo.collection.find({}, {"embedding_index": 1}).sort("embedding_index", -1).limit(1)
        if all_chunks:
            max_index = all_chunks[0].get("embedding_index", 0) + 1
    except Exception:
        pass
    
    index = _ensure_index(dim)
    index.add(np.array(vectors, dtype="float32"))
    faiss.write_index(index, INDEX_PATH)

    # Trang theo chương từ pages
    chapter_pages: Dict[str, List[int]] = {}
    for p in pages:
        ch = p.get("chapter")
        if ch:
            chapter_pages.setdefault(ch, set()).add(p.get("page_num"))
    
    # Hợp nhất structured với pages (thêm pages, chunk counts sẽ điền sau)
    book_structure: Dict[str, Dict] = {}
    for ch, info in structured.items():
        book_structure[ch] = {
            "lessons": {l: {"pages": ([] if not info.get("lesson_pages", {}).get(l) else [info["lesson_pages"][l]]), "chunks": 0} for l in info.get("lessons", [])},
            "total_chunks": 0,
            "pages": sorted(list(chapter_pages.get(ch, set())))
        }
    
    # Dùng mapping page->(chapter/lesson) từ TOC để override detect từ nội dung
    page_assignments = _build_page_assignments(structured) if structured else {}

    # Create mapping chapter_title -> chapter_id, lesson_title -> lesson_id
    chapter_id_map = {}
    lesson_id_map = {}
    for ch_title, ch_info in structured.items():
        chapter_id = _compute_chapter_id(book_id, ch_title)
        chapter_id_map[ch_title] = chapter_id
        for le_title in ch_info.get("lessons", {}).keys():
            lesson_id = _compute_lesson_id(chapter_id, le_title)
            lesson_id_map[le_title] = lesson_id
    
    # Prepare chunks for insertion
    chunks_to_insert = []
    for i, c in enumerate(chunks):
        # Override chapter/lesson theo TOC nếu có
        pnum = c.get("page")
        if isinstance(pnum, int) and pnum in page_assignments:
            assign = page_assignments[pnum]
            c["chapter"] = assign.get("chapter") or c.get("chapter")
            c["lesson"] = assign.get("lesson") or c.get("lesson")
        
        # Add chapter_id and lesson_id
        ch_title = c.get("chapter")
        le_title = c.get("lesson")
        if ch_title and ch_title in chapter_id_map:
            c["chapter_id"] = chapter_id_map[ch_title]
        if le_title and le_title in lesson_id_map:
            c["lesson_id"] = lesson_id_map[le_title]
        
        c["embedding_index"] = max_index + i
        chunks_to_insert.append(c)
        
        # Cập nhật đếm chunks vào structure
        ch = c.get("chapter")
        le = c.get("lesson")
        if ch and ch in book_structure:
            meta_count = book_structure[ch]
            meta_count["total_chunks"] += 1
            if le and le in meta_count["lessons"]:
                meta_count["lessons"][le]["chunks"] += 1
                # thêm page
                pages_dict = meta_count["lessons"][le]
                if "pages" in pages_dict:
                    pages_dict["pages"] = sorted(list(set(pages_dict["pages"] + [c.get("page")])))
    
    # Insert chunks into MongoDB
    chunk_repo.insert_chunks(chunks_to_insert, book_id)
    
    # Create chapters and lessons collections
    chapter_order = 0
    for ch_title, ch_info in structured.items():
        chapter_id = _compute_chapter_id(book_id, ch_title)
        chapter_repo.upsert_chapter(chapter_id, book_id, ch_title, chapter_order)
        chapter_order += 1
        
        # Create lessons for this chapter
        lesson_order = 0
        for le_title in ch_info.get("lessons", {}).keys():
            lesson_id = _compute_lesson_id(chapter_id, le_title)
            lesson_page = ch_info.get("lesson_pages", {}).get(le_title)
            lesson_repo.upsert_lesson(lesson_id, chapter_id, book_id, le_title, lesson_page, lesson_order)
            lesson_order += 1
    
    # Save book structure to MongoDB
    book_repo.upsert_book(book_id, book_name, grade, book_structure)

    duration = int(time.time() - t0)
    logger.info(f"Ingestion completed in {duration}s, chunks: {len(chunks)}")
    return {
        "status": "completed",
        "chunks_created": len(chunks),
        "embeddings_indexed": len(chunks),
        "total_pages": len(pages),
        "duration_seconds": duration
    }
