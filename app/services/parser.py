import fitz  # PyMuPDF
from pdf2image import convert_from_bytes
import pytesseract
from typing import List, Dict, Tuple
import re
from PIL import ImageFile
from app.core.logger import get_logger
from app.core.config import FORCE_OCR, OPENAI_API_KEY
from openai import OpenAI

# Enable loading truncated images
ImageFile.LOAD_TRUNCATED_IMAGES = True

logger = get_logger(__name__)

def _heuristic_shorten_heading(text: str) -> str:
    """
    Heuristic rút gọn tiêu đề dài do OCR: bỏ đuôi dấu chấm dẫn/số trang, lấy đoạn ý chính đầu.
    """
    t = text.strip()
    # Bỏ đường chấm và số trang ở cuối: ....... 12
    t = re.sub(r'(\.{3,}\s*)?\d{1,3}\s*$', '', t).strip()
    # Rút ngắn theo câu/dấu phân cách nếu quá dài
    if len(t) > 200:
        m = re.search(r'([^.:\n]{10,200})(?:[.:\\n]|$)', t)
        if m:
            t = m.group(1).strip()
    t = re.sub(r'\s+', ' ', t)
    return t[:200].strip()

def _refine_heading_with_llm(kind: str, raw: str) -> str:
    """
    Dùng OpenAI để rút gọn/chuẩn hoá tiêu đề chương/bài khi phát hiện quá dài (nhiễu OCR).
    Nếu không có API key hoặc lỗi, fallback về heuristic.
    """
    cleaned = _heuristic_shorten_heading(raw)
    if not OPENAI_API_KEY:
        return cleaned
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        prompt = (
            f"Hãy rút gọn và chuẩn hoá tiêu đề {kind} dưới đây thành một dòng ngắn gọn, "
            f"loại bỏ phần dư như mô tả/câu ví dụ/số trang... Chỉ trả về CHUỖI TIÊU ĐỀ, không giải thích.\n\n"
            f"Tiêu đề gốc:\n{raw}"
        )
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Bạn là bộ lọc tiêu đề. Chỉ trả về một dòng tiêu đề sạch."},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        content = (resp.choices[0].message.content or "").strip()
        content = re.sub(r'\s+', ' ', content)[:200].strip()
        return content or cleaned
    except Exception as e:
        logger.warning(f"LLM refine heading failed: {e}")
        return cleaned

def extract_toc_candidates(pages: List[Dict], max_scan_pages: int = 30) -> Dict[str, Dict] | tuple[Dict[str, Dict], str]:
    """
    Quét phần MỤC LỤC (hoặc các trang đầu) để lấy danh sách chương và bài.
    Trả về:
      - Nếu tìm thấy văn bản mục lục rõ ràng: (toc_dict, raw_toc_text)
      - Nếu không: toc_dict (fallback dựa vào headings đã detect)

    toc_dict format:
    {
      "Chương I. ...": {
        "lessons": [{"title": "Bài 1. ...", "page": 5}, ...],
        "chapter_first_page": 5
      },
      ...
    }
    """
    toc: Dict[str, Dict] = {}
    text_accum = []
    for p in pages[:max_scan_pages]:
        text_accum.append(p.get("text", ""))
    head_text = "\n".join(text_accum)

    # Cắt riêng khu vực có thể là MỤC LỤC
    # Tìm từ "MỤC LỤC" và lấy ~2000 ký tự sau đó, nếu có
    m = re.search(r'MỤC\s*LỤC', head_text, re.IGNORECASE)
    candidate_text = head_text
    if m:
        start = m.start()
        candidate_text = head_text[start:start+8000]

    # Chuẩn hoá xuống từng dòng để regex
    lines = [l.strip() for l in candidate_text.splitlines() if l.strip()]

    current_chapter = None
    i = 0
    while i < len(lines):
        line = lines[i]

        # Dòng chương (có thể đa dòng)
        ch = re.match(r'^(Chương|CHƯƠNG|Phần|PHẦN)\s+([IVXLCDM\d]+)[\.\s]+(.{2,})$', line)
        if ch:
            num = ch.group(2)
            title = ch.group(3).strip()
            # Gộp thêm 1-2 dòng tiếp theo nếu là phần tiếp của tiêu đề chương (thường toàn chữ hoa/khoảng trắng)
            j = i + 1
            join_parts = [title]
            while j < len(lines) and j <= i + 3:
                nxt = lines[j]
                if re.match(r'^(Bài|BÀI)\s+\d+', nxt) or re.match(r'^(Chương|CHƯƠNG|Phần|PHẦN)\s+', nxt) or "HOẠT ĐỘNG" in nxt.upper():
                    break
                # Dòng toàn chữ/space hoặc quá ngắn được xem là tiếp tiêu đề
                if re.match(r'^[A-Za-zÀ-Ỵà-ỹ0-9\\s\\.,]+$', nxt) or len(nxt) <= 40:
                    join_parts.append(nxt.strip())
                    j += 1
                else:
                    break
            title = " ".join(join_parts)
            title = re.sub(r'(\.{3,}\s*)?\d{1,3}$', '', title).strip()
            chapter_title = f"{ch.group(1).capitalize()} {num}. {title}".strip()
            if chapter_title not in toc:
                toc[chapter_title] = {"lessons": [], "chapter_first_page": None}
            current_chapter = chapter_title
            i = j
            continue

        # Dòng bài học (có thể đa dòng, số trang có thể ở dòng sau)
        le = re.match(r'^(Bài|BÀI)\s+(\d+)[\.\s]+(.+)$', line)
        if le and current_chapter:
            title_main = le.group(3).strip()
            parts = [title_main]
            page_no = None
            j = i + 1
            while j < len(lines) and j <= i + 3:
                nxt = lines[j].strip()
                # Nếu là số trang đứng riêng ở dòng tiếp theo
                if re.match(r'^\d{1,3}$', nxt):
                    page_no = int(nxt)
                    j += 1
                    break
                # Nếu gặp bắt đầu chương/bài mới thì dừng
                if re.match(r'^(Bài|BÀI)\s+\d+', nxt) or re.match(r'^(Chương|CHƯƠNG|Phần|PHẦN)\s+', nxt) or "HOẠT ĐỘNG" in nxt.upper():
                    break
                # Ngược lại, nối tiếp tiêu đề bài
                parts.append(nxt)
                j += 1
            lesson_title = " ".join(parts)
            lesson_title = re.sub(r'(\.{3,}\s*)?\d{1,3}$', '', lesson_title).strip()
            # Bỏ qua mục không phải bài học chính
            if lesson_title.lower().startswith("bài tập cuối") or "hoạt động" in lesson_title.lower() or "bảng tra" in lesson_title.lower() or "giải thích thuật ngữ" in lesson_title.lower():
                i = j
                continue
            toc[current_chapter]["lessons"].append({
                "title": f"Bài {le.group(2)}. {lesson_title}",
                "page": page_no
            })
            if toc[current_chapter]["chapter_first_page"] is None and page_no:
                toc[current_chapter]["chapter_first_page"] = page_no
            i = j
            continue

        i += 1

    # Fallback: nếu không thấy MỤC LỤC, dựa vào headings đã detect
    if not toc:
        tmp: Dict[str, Dict] = {}
        for p in pages[:max_scan_pages]:
            ch = p.get("chapter") or ""
            le = p.get("lesson") or ""
            if ch:
                tmp.setdefault(ch, {"lessons": [], "chapter_first_page": p.get("page_num")})
            if ch and le and all(l["title"] != le for l in tmp[ch]["lessons"]):
                tmp[ch]["lessons"].append({"title": le, "page": p.get("page_num")})
        toc = tmp
        return toc

    # Có mục lục: trả về cả raw_text để LLM tái cấu trúc dòng dài/ngắt dòng
    return toc, candidate_text
def _has_text_layer(doc: fitz.Document) -> bool:
    pages = min(3, len(doc))
    for i in range(pages):
        if doc[i].get_text().strip():
            return True
    return False

def _clean_text(text: str) -> str:
    """Clean và normalize text"""
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)
    # Remove weird characters
    text = re.sub(r'[<>]+', '', text)
    return text.strip()

def _detect_chapter_info(text: str, page_num: int) -> Tuple[str, str]:
    """
    Phát hiện chương và bài từ text
    
    SGK Việt Nam patterns:
    - CHƯƠNG I. TÊN CHƯƠNG
    - CHƯƠNG 1. TÊN CHƯƠNG  
    - Bài 1. Tên bài
    - BÀI 2. TÊN BÀI
    
    Returns: (chapter_name, lesson_name)
    """
    chapter_name = ""
    lesson_name = ""
    
    # Clean text trước
    text = _clean_text(text)
    
    # ============ DETECT CHAPTER ============
    # Pattern 1: "CHƯƠNG I. TÊN" (chữ hoa, số La Mã)
    # Stop at Bài, CHƯƠNG, etc.
    match = re.search(
        r'CHƯƠNG\s+([IVXLCDM]+)[\.\s]+(.+?)(?=\s+(?:Bài|BÀI|Chương|CHƯƠNG|Bài tập|HOẠT|\d+\s*$)|$)',
        text,
        re.IGNORECASE | re.DOTALL | re.MULTILINE
    )
    if match:
        num = match.group(1).upper()
        title = match.group(2).strip()
        # Validate: must have meaningful title (not just "Bài tập cuối")
        if title and len(title) > 3 and not title.startswith("tập"):
            title = re.sub(r'\s*\d+\s*$', '', title)  # Remove page numbers at end
            chapter_name = f"Chương {num}. {title}"
            logger.debug(f"Page {page_num}: Detected chapter (Roman): '{chapter_name}'")
    
    # Pattern 2: "Chương 1. Tên" (chữ thường, số Ả-rập)
    if not chapter_name:
        match = re.search(
            r'Chương\s+(\d+)[\.\s]+(.+?)(?=\s+(?:Bài|BÀI|Chương|CHƯƠNG|Bài tập|HOẠT|\d+\s*$)|$)',
            text,
            re.IGNORECASE | re.DOTALL | re.MULTILINE
        )
        if match:
            num = match.group(1)
            title = match.group(2).strip()
            if title and len(title) > 3 and not title.startswith("tập"):
                title = re.sub(r'\s*\d+\s*$', '', title)
                chapter_name = f"Chương {num}. {title}"
                logger.debug(f"Page {page_num}: Detected chapter (Arabic): '{chapter_name}'")
    
    # Pattern 3: "PHẦN I. TÊN" (một số SGK dùng "phần" thay vì "chương")
    if not chapter_name:
        match = re.search(
            r'PHẦN\s+([IVXLCDM\d]+)[\.\s]+(.+?)(?=\s+(?:Bài|BÀI|Chương|CHƯƠNG|Bài tập|HOẠT|\d+\s*$)|$)',
            text,
            re.IGNORECASE | re.DOTALL | re.MULTILINE
        )
        if match:
            num = match.group(1)
            title = match.group(2).strip()
            if title and len(title) > 3 and not title.startswith("tập"):
                title = re.sub(r'\s*\d+\s*$', '', title)
                chapter_name = f"Phần {num}. {title}"
                logger.debug(f"Page {page_num}: Detected chapter (Phần): '{chapter_name}'")
    
    # ============ DETECT LESSON ============
    # Pattern 1: "BÀI 1. TÊN BÀI" (chữ hoa)
    # Stop at page numbers or new lines with digits
    match = re.search(
        r'BÀI\s+(\d+)[\.\s]+([^\n]*?)(?=\s+\d+\s*$|\n\s*\d+\s*$|$)',
        text,
        re.IGNORECASE
    )
    if match:
        num = match.group(1)
        title = match.group(2).strip()
        # Clean up title
        title = re.sub(r'\s*\d+\s*$', '', title)  # Remove trailing page number
        title = re.sub(r'^\W+|\W+$', '', title)  # Remove leading/trailing punctuation
        lesson_name = f"Bài {num}. {title}"
        logger.debug(f"Page {page_num}: Detected lesson: '{lesson_name}'")
    
    # Pattern 2: "Bài học 1. Tên" (một số SGK)
    if not lesson_name:
        match = re.search(
            r'Bài\s+học\s+(\d+)[\.\s]+([^\n]*?)(?=\s+\d+\s*$|\n\s*\d+\s*$|$)',
            text,
            re.IGNORECASE
        )
        if match:
            num = match.group(1)
            title = match.group(2).strip()
            title = re.sub(r'\s*\d+\s*$', '', title)
            lesson_name = f"Bài {num}. {title}"
            logger.debug(f"Page {page_num}: Detected lesson (alt): '{lesson_name}'")
    
    # Pattern 3: "§1. Tên" (ký hiệu đoạn)
    if not lesson_name:
        match = re.search(
            r'§\s*(\d+)[\.\s]+([^\n]*?)(?=\s+\d+\s*$|\n\s*\d+\s*$|$)',
            text
        )
        if match:
            num = match.group(1)
            title = match.group(2).strip()
            title = re.sub(r'\s*\d+\s*$', '', title)
            lesson_name = f"Bài {num}. {title}"
            logger.debug(f"Page {page_num}: Detected lesson (§): '{lesson_name}'")
    
    # Normalize/Refine lengths: dùng LLM khi quá dài (nghi nhiễu), fallback heuristic
    MAX_LEN = 200
    if len(chapter_name) > MAX_LEN:
        chapter_name = _refine_heading_with_llm("chương", chapter_name)
        logger.info(f"Page {page_num}: Chapter refined")
    
    if len(lesson_name) > MAX_LEN:
        lesson_name = _refine_heading_with_llm("bài", lesson_name)
        logger.info(f"Page {page_num}: Lesson refined")
    
    return chapter_name, lesson_name

def _extract_text_with_structure(page: fitz.Page, page_num: int) -> Tuple[str, str, str]:
    """
    Trích xuất text + detect structure từ 1 page
    
    Strategy:
    1. Get full text
    2. Get blocks để tìm headings (font size lớn)
    3. Combine headings + text → detect chapter/lesson
    """
    # Get full text
    text = page.get_text("text")
    
    # Get blocks để phân tích font
    blocks = page.get_text("dict").get("blocks", [])
    
    # Extract text từ blocks có font size lớn (likely headings)
    heading_texts = []
    for block in blocks:
        if block.get("type") == 0:  # Text block
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    font_size = span.get("size", 0)
                    span_text = span.get("text", "").strip()
                    
                    # Headings thường có font >12pt và ít nhất 5 ký tự
                    if font_size >= 12 and len(span_text) >= 5:
                        heading_texts.append(span_text)
    
    # Combine headings với đầu text (2000 chars đầu thường chứa chapter/lesson)
    search_text = "\n".join(heading_texts) + "\n" + text[:2000]
    
    # Detect chapter/lesson
    chapter, lesson = _detect_chapter_info(search_text, page_num)
    
    return text, chapter, lesson

def parse_pdf_bytes(pdf_bytes: bytes, lang: str = "vie", prefer_text: bool = True) -> List[Dict]:
    """
    Parse PDF với improved structure detection
    
    Key improvements:
    1. Better regex patterns cho SGK Việt Nam
    2. Validate chapter/lesson lengths
    3. Clean text (remove <>, excessive spaces)
    4. Debug logging
    
    Returns: List[Dict] với keys:
        - page_num: int
        - text: str
        - blocks: List (raw block data)
        - chapter: str (e.g., "Chương I. ỨNG DỤNG ĐẠO HÀM...")
        - lesson: str (e.g., "Bài 1. Tính đơn điệu và cực trị của hàm số")
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = []
    
    # State để "carry forward"
    current_chapter = ""
    current_lesson = ""
    
    try:
        should_text = prefer_text and _has_text_layer(doc) and not FORCE_OCR
        
        if should_text:
            logger.info(f"Parsing {len(doc)} pages with TEXT layer")
            
            for i in range(len(doc)):
                page = doc[i]
                text, detected_chapter, detected_lesson = _extract_text_with_structure(page, i+1)
                
                # Update state khi detect được
                if detected_chapter:
                    current_chapter = detected_chapter
                    logger.info(f"📘 Page {i+1}: Chapter = '{current_chapter}'")
                
                if detected_lesson:
                    current_lesson = detected_lesson
                    logger.info(f"📗 Page {i+1}: Lesson = '{current_lesson}'")
                
                pages.append({
                    "page_num": i + 1,
                    "text": text,
                    "blocks": page.get_text("dict").get("blocks", []),
                    "chapter": current_chapter,
                    "lesson": current_lesson
                })
        
        else:
            logger.info(f"Parsing {len(doc)} pages with OCR")
            images = convert_from_bytes(pdf_bytes, dpi=300)
            
            for i, img in enumerate(images):
                try:
                    txt = pytesseract.image_to_string(img, lang=lang)
                    detected_chapter, detected_lesson = _detect_chapter_info(txt[:2000], i+1)
                    
                    if detected_chapter:
                        current_chapter = detected_chapter
                        logger.info(f"📘 Page {i+1}: Chapter = '{current_chapter}'")
                    
                    if detected_lesson:
                        current_lesson = detected_lesson
                        logger.info(f"📗 Page {i+1}: Lesson = '{current_lesson}'")
                    
                    pages.append({
                        "page_num": i + 1,
                        "text": txt,
                        "blocks": [],
                        "chapter": current_chapter,
                        "lesson": current_lesson
                    })
                except OSError as e:
                    logger.warning(f"⚠️ Page {i+1}: Image truncated or corrupted, skipping OCR. Error: {e}")
                    # Fallback: try to extract text directly from PDF if possible
                    try:
                        page = doc[i]
                        txt = page.get_text()
                        detected_chapter, detected_lesson = _detect_chapter_info(txt[:2000], i+1)
                        
                        if detected_chapter:
                            current_chapter = detected_chapter
                        if detected_lesson:
                            current_lesson = detected_lesson
                        
                        pages.append({
                            "page_num": i + 1,
                            "text": txt,
                            "blocks": page.get_text("dict").get("blocks", []),
                            "chapter": current_chapter,
                            "lesson": current_lesson
                        })
                    except Exception as e2:
                        logger.error(f"❌ Page {i+1}: Failed to extract text (OCR and PDF both failed). Error: {e2}")
                        # Add empty page to maintain page numbering
                        pages.append({
                            "page_num": i + 1,
                            "text": "",
                            "blocks": [],
                            "chapter": current_chapter,
                            "lesson": current_lesson
                        })
                except Exception as e:
                    logger.error(f"❌ Page {i+1}: Unexpected error during OCR. Error: {e}")
                    # Add empty page to maintain page numbering
                    pages.append({
                        "page_num": i + 1,
                        "text": "",
                        "blocks": [],
                        "chapter": current_chapter,
                        "lesson": current_lesson
                    })
        
        # Summary logging
        unique_chapters = {p["chapter"] for p in pages if p["chapter"]}
        unique_lessons = {p["lesson"] for p in pages if p["lesson"]}
        
        logger.info("✅ Parse complete:")
        logger.info(f"   - {len(pages)} pages")
        logger.info(f"   - {len(unique_chapters)} chapters: {list(unique_chapters)[:3]}")
        logger.info(f"   - {len(unique_lessons)} lessons: {list(unique_lessons)[:3]}")
        
        # Warning nếu detection rate quá thấp
        with_chapter_pct = len([p for p in pages if p["chapter"]]) / len(pages) * 100
        with_lesson_pct = len([p for p in pages if p["lesson"]]) / len(pages) * 100
        
        if with_chapter_pct < 30:
            logger.warning(f"⚠️  Low chapter detection: {with_chapter_pct:.1f}% pages")
        if with_lesson_pct < 20:
            logger.warning(f"⚠️  Low lesson detection: {with_lesson_pct:.1f}% pages")
        
        return pages
    
    finally:
        doc.close()
