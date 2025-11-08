from fastapi import APIRouter, HTTPException, Path, Query
from typing import List, Optional
from app.repositories.lesson_repository import LessonRepository
from app.repositories.chapter_repository import ChapterRepository
from app.repositories.book_repository import BookRepository
from app.models.crud_model import (
    LessonCreateRequest, LessonUpdateRequest, LessonResponse, DeleteResponse
)
from app.services.indexer import _compute_lesson_id

router = APIRouter()

@router.post("", response_model=LessonResponse, status_code=201)
def create_lesson(req: LessonCreateRequest):
    """Create a new lesson"""
    lesson_repo = LessonRepository()
    chapter_repo = ChapterRepository()
    book_repo = BookRepository()
    
    # Verify chapter exists
    chapter = chapter_repo.get_chapter_by_id(req.chapter_id)
    if not chapter:
        raise HTTPException(status_code=404, detail=f"Chapter '{req.chapter_id}' not found")
    
    # Verify book exists
    book = book_repo.get_book_by_id(req.book_id)
    if not book:
        raise HTTPException(status_code=404, detail=f"Book '{req.book_id}' not found")
    
    lesson_id = _compute_lesson_id(req.chapter_id, req.title)
    
    # Check if lesson already exists
    existing = lesson_repo.get_lesson_by_id(lesson_id)
    if existing:
        raise HTTPException(status_code=400, detail=f"Lesson with ID '{lesson_id}' already exists")
    
    lesson_repo.upsert_lesson(lesson_id, req.chapter_id, req.book_id, req.title, req.page, req.order)
    lesson = lesson_repo.get_lesson_by_id(lesson_id)
    
    if not lesson:
        raise HTTPException(status_code=500, detail="Failed to create lesson")
    
    # Convert datetime to string
    lesson["created_at"] = str(lesson.get("created_at")) if lesson.get("created_at") else None
    lesson["updated_at"] = str(lesson.get("updated_at")) if lesson.get("updated_at") else None
    
    return lesson

@router.get("", response_model=List[LessonResponse])
def get_all_lessons(
    chapter_id: Optional[str] = Query(None, description="Filter by chapter_id"),
    book_id: Optional[str] = Query(None, description="Filter by book_id")
):
    """Get all lessons, optionally filtered by chapter_id or book_id"""
    lesson_repo = LessonRepository()
    
    if chapter_id:
        lessons = lesson_repo.get_lessons_by_chapter(chapter_id)
    elif book_id:
        lessons = lesson_repo.get_lessons_by_book(book_id)
    else:
        # Get all lessons
        lessons = list(lesson_repo.collection.find({}, {"_id": 0}).sort("order", 1))
    
    # Convert datetime to string
    for lesson in lessons:
        lesson["created_at"] = str(lesson.get("created_at")) if lesson.get("created_at") else None
        lesson["updated_at"] = str(lesson.get("updated_at")) if lesson.get("updated_at") else None
    
    return lessons

@router.get("/{lesson_id}", response_model=LessonResponse)
def get_lesson(lesson_id: str = Path(..., description="Lesson ID")):
    """Get lesson by ID"""
    lesson_repo = LessonRepository()
    lesson = lesson_repo.get_lesson_by_id(lesson_id)
    
    if not lesson:
        raise HTTPException(status_code=404, detail=f"Lesson '{lesson_id}' not found")
    
    # Convert datetime to string
    lesson["created_at"] = str(lesson.get("created_at")) if lesson.get("created_at") else None
    lesson["updated_at"] = str(lesson.get("updated_at")) if lesson.get("updated_at") else None
    
    return lesson

@router.put("/{lesson_id}", response_model=LessonResponse)
def update_lesson(
    lesson_id: str = Path(..., description="Lesson ID"),
    req: LessonUpdateRequest = None
):
    """Update lesson by ID"""
    lesson_repo = LessonRepository()
    
    # Check if lesson exists
    existing = lesson_repo.get_lesson_by_id(lesson_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Lesson '{lesson_id}' not found")
    
    # Update lesson
    updated = lesson_repo.update_lesson(
        lesson_id=lesson_id,
        title=req.title if req else None,
        page=req.page if req else None,
        order=req.order if req else None
    )
    
    if not updated:
        raise HTTPException(status_code=400, detail="No fields to update or update failed")
    
    # Get updated lesson
    lesson = lesson_repo.get_lesson_by_id(lesson_id)
    lesson["created_at"] = str(lesson.get("created_at")) if lesson.get("created_at") else None
    lesson["updated_at"] = str(lesson.get("updated_at")) if lesson.get("updated_at") else None
    
    return lesson

@router.delete("/{lesson_id}", response_model=DeleteResponse)
def delete_lesson(lesson_id: str = Path(..., description="Lesson ID")):
    """Delete lesson by ID"""
    lesson_repo = LessonRepository()
    
    # Check if lesson exists
    existing = lesson_repo.get_lesson_by_id(lesson_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Lesson '{lesson_id}' not found")
    
    # Delete lesson
    deleted = lesson_repo.delete_lesson(lesson_id)
    
    if not deleted:
        raise HTTPException(status_code=500, detail="Failed to delete lesson")
    
    return DeleteResponse(
        success=True,
        message=f"Lesson '{lesson_id}' deleted successfully",
        deleted_count=1
    )

