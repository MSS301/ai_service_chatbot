from fastapi import APIRouter, HTTPException
from app.models.rag_model import (
    RAGRequest, RAGResponse,
    SlideContentRequest, SlideContentResponse,
    SlidesGPTRequest, SlidesGPTResponse,
    TemplateSlidesRequest, TemplateSlidesResponse,
    ContentReviseRequest, ContentReviseResponse
)
from app.services.rag_engine import rag_query
from app.repositories.book_repository import BookRepository
from app.repositories.chapter_repository import ChapterRepository
from app.repositories.lesson_repository import LessonRepository
from app.core.config import SLIDES_BASE_URL, OPENAI_API_KEY, SLIDESGPT_API_KEY
from openai import OpenAI
import requests, uuid, os
from app.repositories.content_repository import ContentRepository
import re

router = APIRouter()

@router.post("/query", response_model=RAGResponse)
def rag_query_endpoint(req: RAGRequest):
    """
    RAG Query với 5 params: grade_id, book_id, chapter_id, lesson_id, content
    """
    # Get grade_number from grade_id
    from app.repositories.grade_repository import GradeRepository
    grade_repo = GradeRepository()
    grade = grade_repo.get_grade_by_id(req.grade_id)
    if not grade:
        raise HTTPException(status_code=404, detail=f"Grade '{req.grade_id}' not found")
    grade_number = grade.get("grade_number")

    # Fetch book/chapter/lesson for names
    book_repo = BookRepository()
    book = book_repo.get_book_by_id(req.book_id)
    if not book:
        raise HTTPException(status_code=404, detail=f"Book '{req.book_id}' not found")

    chapter_repo = ChapterRepository()
    chapter = chapter_repo.get_chapter_by_id(req.chapter_id)
    lesson_repo = LessonRepository()
    lesson = lesson_repo.get_lesson_by_id(req.lesson_id)

    # Validate subject if provided: book.subject_id must match req.subject_id
    if req.subject_id:
        book_subject_id = book.get("subject_id")
        if book_subject_id != req.subject_id:
            raise HTTPException(status_code=400, detail="subject_id does not match the book's subject")
    
    outline, distances, indices = rag_query(
        grade=grade_number,
        book_id=req.book_id,
        chapter_id=req.chapter_id,
        lesson_id=req.lesson_id,
        content=req.content,
        k=req.k
    )

    # Generate teaching content with OpenAI and persist
    content_text = ""
    if OPENAI_API_KEY:
        try:
            client = OpenAI(api_key=OPENAI_API_KEY)
            book_name = book.get("book_name", "")
            chapter_name = (chapter or {}).get("title", "")
            lesson_name = (lesson or {}).get("title", "")
            grade_name = grade.get("grade_name", f"Lớp {grade_number}")

            prompt = (
                "Prompt Chuẩn Soạn Slide (Giới hạn 5–7 slide)\n\n"
                f"Hãy soạn bộ Slide bài giảng gồm khoảng 5–7 slide dựa trên nội dung chính của bài học trong sách giáo khoa {book_name}.\n\n"
                f"Bài học thuộc {lesson_name}, nằm trong {chapter_name} của chương trình {grade_name}.\n\n"
                "Yêu cầu cụ thể:\n"
                "1. Slide 1 – Tiêu đề và Giới thiệu: Ghi rõ tên bài, chương, lớp học và mục đích tổng quát của bài học.\n"
                "2. Slide 2 – Mục tiêu bài học: Liệt kê 3–5 mục tiêu chính học sinh cần đạt được sau bài học.\n"
                "3. Slide 3–5 – Nội dung trọng tâm:\n"
                "   - Chia thành các phần logic (I, II, III, …), trình bày dưới dạng bullet points.\n"
                "   - Giải thích ngắn gọn, dễ hiểu.\n"
                "   - Mỗi phần có thể có ví dụ minh họa hoặc ứng dụng thực tế ngắn.\n"
                "4. Slide 6 – Câu hỏi củng cố: Gồm 3–5 câu hỏi ngắn (trắc nghiệm hoặc tự luận) giúp học sinh ôn tập.\n"
                "5. Slide 7 – Tổng kết: Nêu lại các ý chính, liên hệ thực tiễn hoặc gợi mở cho bài tiếp theo.\n\n"
                "Yêu cầu trình bày:\n"
                "- Ngôn ngữ: tiếng Việt, rõ ràng, thân thiện, dễ hiểu.\n"
                "- Giọng văn: sư phạm, hiện đại, có tính tương tác.\n"
                "- Không dùng mã Markdown hoặc HTML.\n"
                "- Nội dung đủ để giáo viên có thể dùng trình chiếu trực tiếp.\n\n"
                "Nếu nội dung sách giáo khoa không đầy đủ, hãy bổ sung kiến thức chuẩn theo chương trình phổ thông.\n\n"
                "Dữ liệu tham chiếu:\n"
                f"- Outline RAG:\n{outline}\n\n"
                f"- Ghi chú giáo viên:\n{req.content}\n"
            )
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Bạn là trợ lý giáo viên, biên soạn giáo án đúng phạm vi SGK và chuẩn CTPT."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
            )
            content_text = resp.choices[0].message.content or ""
        except Exception:
            content_text = ""

    content_id = None
    try:
        crepo = ContentRepository()
        crepo.create_indexes()
        content_id = crepo.new_content_id()
        crepo.insert_content({
            "content_id": content_id,
            "grade_id": req.grade_id,
            "book_id": req.book_id,
            "chapter_id": req.chapter_id,
            "lesson_id": req.lesson_id,
            "subject_id": req.subject_id,
            "outline": outline,
            "content_text": content_text,
            "version": 1
        })
    except Exception:
        pass

    return {
        "outline": outline,
        "sources": outline.get("sources", []),
        "indices": indices,
        "distances": distances,
        "content_id": content_id,
        "content_text": content_text
    }

@router.post("/generate/slide-content", response_model=SlideContentResponse)
def generate_slide_content(req: SlideContentRequest):
    """
    Tạo nội dung slide (markdown) bằng OpenAI từ content/outline người dùng truyền vào.
    """
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")
    client = OpenAI(api_key=OPENAI_API_KEY)

    style_hint = req.style or "presentable, structured, Vietnamese"
    system_msg = "Bạn là chuyên gia tạo slide. Xuất ra Markdown, có tiêu đề và bullet rõ ràng, không bịa."
    user_msg = f"Hãy chuyển nội dung sau thành outline slide Markdown, phong cách: {style_hint}\n\n{req.content}"
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.2,
    )
    md = resp.choices[0].message.content or ""
    return {"markdown": md}

@router.post("/generate/slidesgpt", response_model=SlidesGPTResponse)
def generate_slides_slidesgpt(req: SlidesGPTRequest):
    """
    Gọi SlidesGPT API để tạo slide từ prompt.
    """
    base = SLIDES_BASE_URL.rstrip("/")
    api_key = SLIDESGPT_API_KEY or os.getenv("SLIDESGPT_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="SLIDESGPT_API_KEY not configured")

    url = f"{base}/v1/presentations/generate"
    try:
        r = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={"prompt": req.prompt},
            timeout=120,
        )
        if r.status_code >= 400:
            raise HTTPException(status_code=r.status_code, detail=f"SlidesGPT error: {r.text}")
        data = r.json()
        return {
            "id": data.get("id", uuid.uuid4().hex),
            "embed": data.get("embed"),
            "download": data.get("download"),
        }
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"SlidesGPT request failed: {e}")

@router.post("/generate/template-slides", response_model=TemplateSlidesResponse)
def generate_template_slides(req: TemplateSlidesRequest):
    """
    Sinh slide theo khung template có sẵn (trả về JSON cấu trúc slide).
    Client có thể render ra PPT/HTML tùy ý ở phía trước.
    """
    outline = req.outline or {}
    sections = outline.get("sections", [])
    slides = []
    # Slide tiêu đề
    slides.append({"type": "title", "title": req.title, "subtitle": req.theme or ""})
    # Slide nội dung
    for sec in sections:
        slides.append({
            "type": "content",
            "title": sec.get("title", ""),
            "bullets": sec.get("bullets", []),
            "examples": sec.get("examples", []),
        })
    # Slide kết thúc
    slides.append({"type": "closing", "title": "Tổng kết", "bullets": ["Câu hỏi?", "Bài tập/vận dụng"]})
    return {"slides": slides}

def _clean_content_text(text: str) -> str:
    """
    Remove common leading prefaces and separators like 'Dưới đây là...', 'Sau đây là...', and top '---' lines.
    Keep the main content intact.
    """
    if not text:
        return text
    lines = [ln.strip() for ln in text.splitlines()]
    # Drop leading empty lines
    while lines and lines[0] == "":
        lines.pop(0)
    # Drop one or two leading separators '---'
    while lines and re.fullmatch(r"-{3,}", lines[0]):
        lines.pop(0)
    # Drop common Vietnamese preface phrases at the very beginning
    preface_patterns = [
        r"^Dưới\s+đây\s+là\s+",
        r"^Sau\s+đây\s+là\s+",
        r"^Nội\s+dung\s+đã\s+được\s+chỉnh\s+sửa",
        r"^Đây\s+là\s+nội\s+dung",
    ]
    if lines:
        for pat in preface_patterns:
            if re.search(pat, lines[0], flags=re.IGNORECASE):
                lines.pop(0)
                break
    # Drop a separator again if it appears after removing preface
    while lines and re.fullmatch(r"-{3,}", lines[0]):
        lines.pop(0)
    # Rejoin
    cleaned = "\n".join(lines).strip()
    return cleaned


@router.post("/content/{content_id}/revise", response_model=ContentReviseResponse)
def revise_content(content_id: str, req: ContentReviseRequest):
    crepo = ContentRepository()
    doc = crepo.get_by_id(content_id)
    if not doc:
        raise HTTPException(status_code=404, detail="content_id not found")
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")

    current = doc.get("content_text", "")
    outline = doc.get("outline", {})

    client = OpenAI(api_key=OPENAI_API_KEY)
    prompt = (
        "Bạn là trợ lý giáo viên. Hãy CHỈ chỉnh sửa nội dung bài giảng theo yêu cầu dưới đây, giữ đúng phạm vi SGK.\n"
        "- Chỉ trả về NỘI DUNG CHÍNH THỨC sau khi chỉnh sửa.\n"
        "- KHÔNG thêm lời dẫn, không mở đầu bằng các cụm như: 'Dưới đây là...', 'Sau đây là...'.\n"
        "- KHÔNG chèn các đường kẻ '---' hay tiêu đề phụ không cần thiết.\n"
        "- KHÔNG dùng code block Markdown.\n\n"
        f"Yêu cầu chỉnh sửa của người dùng:\n{req.instruction}\n\n"
        "Nội dung hiện tại:\n"
        f"{current}\n\n"
        "Outline SGK tham chiếu:\n"
        f"{outline}\n"
    )
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Biên tập nội dung giáo án theo chỉ dẫn, không bịa ngoài SGK. Chỉ trả về nội dung cuối cùng, không tiền tố/hậu tố."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    raw_text = resp.choices[0].message.content or current
    new_text = _clean_content_text(raw_text)

    crepo.revise_content(
        content_id=content_id,
        new_text=new_text,
        instruction=req.instruction,
        previous_text=current,
        created_by=getattr(req, "created_by", None),
    )
    return {"content_id": content_id, "content_text": new_text}

@router.get("/books/{grade_id}")
def get_books_by_grade(grade_id: str):
    """
    📚 Lấy danh sách sách đã ingest theo grade_id
    """
    book_repo = BookRepository()
    books = book_repo.collection.find({"grade_id": grade_id}, {"_id": 0})
    return {
        "grade_id": grade_id,
        "books": [
            {
                "book_id": b.get("book_id"),
                "book_name": b.get("book_name"),
                "grade_id": b.get("grade_id")
            }
            for b in books
        ]
    }

@router.get("/chapters/{book_id}")
def get_chapters_by_book(book_id: str):
    """
    📖 Lấy danh sách chương của một sách
    """
    chapter_repo = ChapterRepository()
    chapters = chapter_repo.get_chapters_by_book(book_id)
    return {
        "book_id": book_id,
        "chapters": [
            {
                "chapter_id": ch.get("chapter_id"),
                "title": ch.get("title"),
                "order": ch.get("order")
            }
            for ch in chapters
        ]
    }

@router.get("/lessons/{chapter_id}")
def get_lessons_by_chapter(chapter_id: str):
    """
    📝 Lấy danh sách bài học của một chương
    """
    lesson_repo = LessonRepository()
    lessons = lesson_repo.get_lessons_by_chapter(chapter_id)
    return {
        "chapter_id": chapter_id,
        "lessons": [
            {
                "lesson_id": le.get("lesson_id"),
                "title": le.get("title"),
                "page": le.get("page"),
                "order": le.get("order")
            }
            for le in lessons
        ]
    }
