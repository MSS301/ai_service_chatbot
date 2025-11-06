from fastapi import APIRouter, HTTPException
from app.models.rag_model import RAGRequest, RAGResponse
from app.services.rag_engine import rag_query
from app.repositories.book_repository import BookRepository
from app.repositories.chapter_repository import ChapterRepository
from app.repositories.lesson_repository import LessonRepository

router = APIRouter()

@router.post("/query", response_model=RAGResponse)
def rag_query_endpoint(req: RAGRequest):
    """
    RAG Query với 5 params: grade, book_id, chapter_id, lesson_id, content
    """
    outline, distances, indices = rag_query(
        grade=req.grade,
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

@router.get("/books/{grade}")
def get_books_by_grade(grade: int):
    """
    📚 Lấy danh sách sách đã ingest theo lớp
    """
    book_repo = BookRepository()
    books = book_repo.collection.find({"grade": grade}, {"_id": 0})
    return {
        "grade": grade,
        "books": [
            {
                "book_id": b.get("book_id"),
                "book_name": b.get("book_name"),
                "grade": b.get("grade")
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
