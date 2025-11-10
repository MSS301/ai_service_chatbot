from fastapi import APIRouter, HTTPException
from app.models.rag_model import (
    RAGRequest, RAGResponse,
    SlideContentRequest, SlideContentResponse,
    SlidesGPTRequest, SlidesGPTResponse,
    TemplateSlidesRequest, TemplateSlidesResponse
)
from app.services.rag_engine import rag_query
from app.repositories.book_repository import BookRepository
from app.repositories.chapter_repository import ChapterRepository
from app.repositories.lesson_repository import LessonRepository
from app.core.config import SLIDES_BASE_URL, OPENAI_API_KEY, SLIDESGPT_API_KEY
from openai import OpenAI
import requests, uuid, os

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

    # Validate subject if provided: book.subject_id must match req.subject_id
    if req.subject_id:
        book_repo = BookRepository()
        book = book_repo.get_book_by_id(req.book_id)
        if not book:
            raise HTTPException(status_code=404, detail=f"Book '{req.book_id}' not found")
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
    return {
        "outline": outline,
        "sources": outline.get("sources", []),
        "indices": indices,
        "distances": distances
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
