import json
import os
from typing import Tuple, List
import numpy as np, faiss
from openai import OpenAI
from dotenv import load_dotenv
from app.core.config import INDEX_PATH, CHAT_MODEL
from app.core.logger import get_logger
from app.services.embedder import embed_query
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.book_repository import BookRepository
from app.repositories.chapter_repository import ChapterRepository
from app.repositories.lesson_repository import LessonRepository

logger = get_logger(__name__)

# Load environment variables from .env if present
load_dotenv()

# MVP lesson DB (sẽ được thay bằng PostgreSQL sau)
LESSONS = {
    "L8-ALG-CH2-BT3": {
        "name": "Phương trình bậc hai",
        "grade": 8,
        "chapter": "Chương 2",
        "chapter_full": "Chương 2: Phương trình và hệ phương trình"
    },
    "L9-GEO-CH1-BT1": {
        "name": "Định lý Pytago",
        "grade": 9,
        "chapter": "Chương 1",
        "chapter_full": "Chương 1: Hệ thức lượng trong tam giác vuông"
    }
}

def _get_lesson(lesson_id: str):
    return LESSONS.get(lesson_id, {
        "name": "",
        "grade": 0,
        "chapter": "",
        "chapter_full": ""
    })

def _load_index_chunks():
    """Load FAISS index and get all chunks from MongoDB, sorted by embedding_index"""
    if not os.path.exists(INDEX_PATH):
        logger.error(f"FAISS index file not found: {INDEX_PATH}")
        raise FileNotFoundError(f"FAISS index file not found: {INDEX_PATH}")
    
    index = faiss.read_index(INDEX_PATH)
    num_vectors = index.ntotal
    logger.info(f"Loaded FAISS index with {num_vectors} vectors from {INDEX_PATH}")
    
    chunk_repo = ChunkRepository()
    # Get all chunks sorted by embedding_index to match FAISS index order
    all_chunks = chunk_repo.collection.find({}).sort("embedding_index", 1)
    chunks_list = list(all_chunks)
    
    logger.info(f"Loaded {len(chunks_list)} chunks from MongoDB")
    
    # Check if counts match
    if num_vectors != len(chunks_list):
        logger.warning(f"Mismatch: FAISS has {num_vectors} vectors but MongoDB has {len(chunks_list)} chunks")
    
    return index, chunks_list

def _build_prompt(chunks, lesson, teacher_notes):
    """
    Build prompt với context từ chunks + lesson info
    
    NOTE: Prompt được thiết kế để:
    - Chỉ dùng nội dung từ chunks (không bịa)
    - Ưu tiên chunks có chapter/lesson info khớp
    - Trả về JSON format cố định
    """
    # Sort chunks by relevance (chunks có chapter/lesson info lên trước)
    def score_chunk(c):
        score = 0
        if c.get("chapter"): score += 10
        if c.get("lesson"): score += 5
        return score
    
    chunks_sorted = sorted(chunks[:8], key=score_chunk, reverse=True)
    
    # Build context với annotations rõ ràng
    # Lấy tên từ MongoDB collections
    from app.repositories.book_repository import BookRepository
    from app.repositories.chapter_repository import ChapterRepository
    from app.repositories.lesson_repository import LessonRepository
    
    book_repo_ctx = BookRepository()
    chapter_repo_ctx = ChapterRepository()
    lesson_repo_ctx = LessonRepository()
    
    context_parts = []
    for i, c in enumerate(chunks_sorted[:5]):  # Top 5 chunks
        # Lấy book_name
        chunk_book_id = c.get("book_id")
        book_name = "N/A"
        if chunk_book_id:
            chunk_book = book_repo_ctx.get_book_by_id(chunk_book_id)
            if chunk_book:
                book_name = chunk_book.get("book_name", "N/A")
        
        # Lấy chapter title
        chunk_chapter_id = c.get("chapter_id")
        chapter = "N/A"
        if chunk_chapter_id:
            chunk_chapter = chapter_repo_ctx.get_chapter_by_id(chunk_chapter_id)
            if chunk_chapter:
                chapter = chunk_chapter.get("title", "N/A")
        
        # Lấy lesson title
        chunk_lesson_id = c.get("lesson_id")
        lesson_info = "N/A"
        if chunk_lesson_id:
            chunk_lesson = lesson_repo_ctx.get_lesson_by_id(chunk_lesson_id)
            if chunk_lesson:
                lesson_info = chunk_lesson.get("title", "N/A")
        
        page = c.get("page", 0)
        text = c.get("text", "")[:1200]  # Limit 1200 chars/chunk
        
        context_parts.append(
            f"--- Nguồn {i+1} ---\n"
            f"Sách: {book_name}\n"
            f"Chương: {chapter}\n"
            f"Bài: {lesson_info}\n"
            f"Trang: {page}\n"
            f"Nội dung:\n{text}\n"
        )
    
    context = "\n".join(context_parts)
    
    # Build prompt
    prompt = f"""Bạn là giáo viên Toán giỏi. Nhiệm vụ: Tạo outline bài giảng CHỈ DỰA VÀO nội dung SGK bên dưới.

**QUAN TRỌNG:**

- CHỈ sử dụng thông tin từ "Nội dung SGK"
- KHÔNG thêm kiến thức ngoài SGK
- Nếu không đủ thông tin → Trả về {{"sections": [], "note": "Không đủ nội dung trong SGK"}}

===== NỘI DUNG SGK =====

{context}

===========================

**YÊU CẦU:**

Tạo outline cho bài "{lesson['name']}" (Lớp {lesson['grade']}, {lesson.get('chapter_full', lesson.get('chapter', ''))})

Cấu trúc:

- 5-10 mục chính
- Mỗi mục: Tiêu đề + 3-5 bullet points
- Thêm ví dụ thực tế (gợi ý từ giáo viên: "{teacher_notes}")

**OUTPUT (JSON duy nhất):**

{{
  "sections": [
    {{
      "title": "Tiêu đề mục 1",
      "bullets": ["Điểm 1", "Điểm 2", "Điểm 3"],
      "examples": ["Ví dụ 1: x² - 4 = 0"]
    }}
  ]
}}

"""
    return prompt

def _call_llm(prompt: str) -> dict:
    """
    Call LLM với safeguards:
    - Temperature=0 (minimize hallucination)
    - JSON format enforcement
    - Retry logic (TODO: add retry)
    """
    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.error("OPENAI_API_KEY is not set. Skipping LLM call.")
            return {
                "sections": [],
                "note": "Thiếu cấu hình OPENAI_API_KEY. Vui lòng thêm vào file .env trong thư mục app/."
            }

        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "Bạn là trợ lý giáo viên. CHỈ trích dẫn nội dung đã cho, KHÔNG bịa thêm."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0,  # Zero creativity = stick to facts
            response_format={"type": "json_object"}
        )
        content = resp.choices[0].message.content
        return json.loads(content)
    
    except json.JSONDecodeError as e:
        logger.error(f"LLM returned invalid JSON: {e}")
        return {
            "sections": [],
            "note": "Lỗi parse JSON từ AI. Vui lòng thử lại."
        }
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        return {
            "sections": [],
            "note": f"Lỗi gọi AI: {str(e)}"
        }

def _filter_chunks_by_metadata(chunks: List, lesson: dict) -> List:
    """
    Filter chunks theo grade + chapter để tránh nhầm lẫn giữa các lớp/chương
    
    Priority:
    1. Exact match: grade=8 AND chapter="Chương 2"
    2. Grade match only: grade=8 (nếu không có chapter info)
    3. No filter (fallback)
    """
    target_grade = lesson.get("grade")
    target_chapter = lesson.get("chapter", "")  # "Chương 2"
    
    if not target_grade:
        return chunks  # No lesson info, return all
    
    # Level 1: Filter by grade + chapter
    if target_chapter:
        exact_match = [
            c for c in chunks
            if c.get("grade") == target_grade and target_chapter in c.get("chapter", "")
        ]
        if exact_match:
            logger.info(f"Filtered to {len(exact_match)}/{len(chunks)} chunks (grade={target_grade}, chapter={target_chapter})")
            return exact_match
    
    # Level 2: Filter by grade only
    grade_match = [c for c in chunks if c.get("grade") == target_grade]
    if grade_match:
        logger.info(f"Filtered to {len(grade_match)}/{len(chunks)} chunks (grade={target_grade} only)")
        return grade_match
    
    # Level 3: No filter (fallback)
    logger.warning(f"No chunks match grade={target_grade}, using all {len(chunks)} chunks")
    return chunks

def rag_query(grade: int, book_id: str, chapter_id: str, lesson_id: str, content: str, k: int = 8) -> Tuple[dict, List[float], List[int]]:
    """
    RAG Query với filtering theo book_id, chapter_id, lesson_id
    """
    # Get lesson info from MongoDB
    lesson_repo = LessonRepository()
    lesson = lesson_repo.get_lesson_by_id(lesson_id)
    
    if not lesson:
        return {
            "sections": [],
            "note": f"Lesson '{lesson_id}' not found",
            "sources": []
        }, [], []
    
    # Get chapter info
    chapter_repo = ChapterRepository()
    chapter = chapter_repo.get_chapter_by_id(chapter_id)
    
    # Get book info (for validation)
    book_repo = BookRepository()
    book = book_repo.get_book_by_id(book_id)
    if not book:
        return {
            "sections": [],
            "note": f"Book '{book_id}' not found",
            "sources": []
        }, [], []
    
    # Build query string
    query_parts = []
    if chapter:
        query_parts.append(chapter.get("title", ""))
    query_parts.append(lesson.get("title", ""))
    if content:
        query_parts.append(content)
    
    query_string = " ".join(query_parts).strip()
    logger.info(f"RAG Query: book_id={book_id}, chapter_id={chapter_id}, lesson_id={lesson_id}, query='{query_string}'")
    
    # Embed query
    qvec = np.array(embed_query(query_string), dtype="float32").reshape(1, -1)
    
    # Load index + chunks from MongoDB
    index, all_chunks = _load_index_chunks()
    num_vectors_in_index = index.ntotal  # Total vectors in FAISS index
    num_chunks_in_db = len(all_chunks)  # Chunks in MongoDB
    
    logger.info(f"FAISS index has {num_vectors_in_index} vectors, MongoDB has {num_chunks_in_db} chunks")
    
    if num_vectors_in_index == 0:
        logger.error("FAISS index is empty")
        return {
            "sections": [],
            "note": "Chưa có dữ liệu SGK. Vui lòng ingest sách trước.",
            "sources": []
        }, [], []
    
    # FAISS search - use num_vectors_in_index for k_search
    k_search = min(k * 3, num_vectors_in_index)  # Search more, filter later
    logger.info(f"Searching FAISS with k_search={k_search}, num_vectors={num_vectors_in_index}")
    
    try:
        distances, indices = index.search(qvec, k_search)
        idxs = indices[0].tolist()
        dists = distances[0].tolist()
        
        logger.info(f"FAISS returned {len(idxs)} indices: {idxs[:5]}... (showing first 5)")
        
        # Filter invalid indices (FAISS returns -1 for empty slots if k_search > actual vectors)
        # Use num_vectors_in_index, not num_chunks_in_db
        valid_pairs = [
            (idx, dist) for idx, dist in zip(idxs, dists)
            if idx >= 0 and idx < num_vectors_in_index
        ]
        
        logger.info(f"After filtering invalid indices: {len(valid_pairs)} valid pairs out of {len(idxs)}")
        
        if not valid_pairs:
            logger.error(f"FAISS returned no valid indices. Raw indices: {idxs[:10]}, num_vectors: {num_vectors_in_index}")
            return {
                "sections": [],
                "note": "Lỗi tìm kiếm. Vui lòng thử lại.",
                "sources": []
            }, [], []
    except Exception as e:
        logger.error(f"FAISS search failed: {e}")
        return {
            "sections": [],
            "note": f"Lỗi tìm kiếm: {str(e)}",
            "sources": []
        }, [], []
    
    # Sort by distance (lower = better for L2)
    valid_pairs.sort(key=lambda x: x[1])
    idxs = [idx for idx, _ in valid_pairs]
    dists = [dist for _, dist in valid_pairs]
    
    # Get chunks by embedding indices from MongoDB
    # Note: We query by embedding_index, not by position in array
    chunk_repo = ChunkRepository()
    retrieved_chunks = chunk_repo.get_chunks_by_indices(idxs)
    
    logger.info(f"Retrieved {len(retrieved_chunks)} chunks from MongoDB (requested {len(idxs)} indices), filtering by book_id={book_id}, chapter_id={chapter_id}, lesson_id={lesson_id}")
    
    # Debug: Check what book_id/chapter_id/lesson_id the chunks have
    if retrieved_chunks:
        sample_chunk = retrieved_chunks[0]
        logger.info(f"Sample chunk: embedding_index={sample_chunk.get('embedding_index')}, book_id={sample_chunk.get('book_id')}, chapter_id={sample_chunk.get('chapter_id')}, lesson_id={sample_chunk.get('lesson_id')}")
    else:
        logger.warning(f"No chunks found for indices: {idxs[:10]}... (showing first 10)")
    
    # Filter by book_id, chapter_id, lesson_id
    filtered_chunks = [
        c for c in retrieved_chunks
        if c.get("book_id") == book_id 
        and c.get("chapter_id") == chapter_id
        and c.get("lesson_id") == lesson_id
    ]
    
    logger.info(f"After exact filter: {len(filtered_chunks)} chunks match")
    
    # If no exact match, try chapter_id only
    if not filtered_chunks:
        filtered_chunks = [
            c for c in retrieved_chunks
            if c.get("book_id") == book_id 
            and c.get("chapter_id") == chapter_id
        ]
        logger.info(f"Filtered to {len(filtered_chunks)} chunks (by chapter_id only)")
    
    # If still no match, try book_id only
    if not filtered_chunks:
        filtered_chunks = [
            c for c in retrieved_chunks
            if c.get("book_id") == book_id
        ]
        logger.info(f"Filtered to {len(filtered_chunks)} chunks (by book_id only)")
    
    # Check relevance threshold (L2 distance for ada-002: <0.35 = good)
    RELEVANCE_THRESHOLD = 0.35
    if not filtered_chunks or (dists[0] > RELEVANCE_THRESHOLD):
        logger.warning(f"No relevant content (best distance: {dists[0]:.4f})")
        return {
            "sections": [],
            "note": f"Không tìm thấy nội dung phù hợp trong SGK (độ tương đồng thấp: {dists[0]:.2f}).",
            "sources": []
        }, dists[:len(filtered_chunks)], idxs[:len(filtered_chunks)]
    
    # Build prompt + Call LLM
    lesson_info = {
        "name": lesson.get("title", ""),
        "grade": grade,
        "chapter": chapter.get("title", "") if chapter else "",
        "chapter_full": chapter.get("title", "") if chapter else ""
    }
    prompt = _build_prompt(filtered_chunks, lesson_info, content)
    outline = _call_llm(prompt)
    
    # Add source citations - lấy tên từ MongoDB collections thay vì từ chunk metadata
    outline["sources"] = []
    for i, chunk in enumerate(filtered_chunks[:3]):  # Top 3 sources
        source_dist = dists[i] if i < len(dists) else 1.0
        
        # Lấy book_name từ BookRepository
        chunk_book_id = chunk.get("book_id")
        book_name = "N/A"
        if chunk_book_id:
            chunk_book = book_repo.get_book_by_id(chunk_book_id)
            if chunk_book:
                book_name = chunk_book.get("book_name", "N/A")
        
        # Lấy chapter title từ ChapterRepository
        chunk_chapter_id = chunk.get("chapter_id")
        chapter_title = "N/A"
        if chunk_chapter_id:
            chunk_chapter = chapter_repo.get_chapter_by_id(chunk_chapter_id)
            if chunk_chapter:
                chapter_title = chunk_chapter.get("title", "N/A")
        
        # Lấy lesson title từ LessonRepository
        chunk_lesson_id = chunk.get("lesson_id")
        lesson_title = "N/A"
        if chunk_lesson_id:
            chunk_lesson = lesson_repo.get_lesson_by_id(chunk_lesson_id)
            if chunk_lesson:
                lesson_title = chunk_lesson.get("title", "N/A")
        
        outline["sources"].append({
            "book": book_name,
            "chapter": chapter_title,
            "lesson": lesson_title,
            "pages": [chunk.get("page", 0)],
            "confidence": round(max(0, 1 - source_dist), 4)  # Convert L2 to 0-1 score
        })
    
    logger.info(f"Generated outline with {len(outline.get('sections', []))} sections from {len(filtered_chunks)} chunks")
    
    return outline, dists[:len(filtered_chunks)], idxs[:len(filtered_chunks)]
