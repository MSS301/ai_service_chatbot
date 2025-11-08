from fastapi import APIRouter, HTTPException, Path, Query
from typing import List, Optional
from app.repositories.chapter_repository import ChapterRepository
from app.repositories.lesson_repository import LessonRepository
from app.repositories.book_repository import BookRepository
from app.models.crud_model import (
    ChapterCreateRequest, ChapterUpdateRequest, ChapterResponse, DeleteResponse
)
from app.services.indexer import _compute_chapter_id

router = APIRouter()

@router.post("", response_model=ChapterResponse, status_code=201)
def create_chapter(req: ChapterCreateRequest):
    """Create a new chapter"""
    chapter_repo = ChapterRepository()
    book_repo = BookRepository()
    
    # Verify book exists
    book = book_repo.get_book_by_id(req.book_id)
    if not book:
        raise HTTPException(status_code=404, detail=f"Book '{req.book_id}' not found")
    
    chapter_id = _compute_chapter_id(req.book_id, req.title)
    
    # Check if chapter already exists
    existing = chapter_repo.get_chapter_by_id(chapter_id)
    if existing:
        raise HTTPException(status_code=400, detail=f"Chapter with ID '{chapter_id}' already exists")
    
    chapter_repo.upsert_chapter(chapter_id, req.book_id, req.title, req.order)
    chapter = chapter_repo.get_chapter_by_id(chapter_id)
    
    if not chapter:
        raise HTTPException(status_code=500, detail="Failed to create chapter")
    
    # Convert datetime to string
    chapter["created_at"] = str(chapter.get("created_at")) if chapter.get("created_at") else None
    chapter["updated_at"] = str(chapter.get("updated_at")) if chapter.get("updated_at") else None
    
    return chapter

@router.get("", response_model=List[ChapterResponse])
def get_all_chapters(book_id: Optional[str] = Query(None, description="Filter by book_id")):
    """Get all chapters, optionally filtered by book_id"""
    chapter_repo = ChapterRepository()
    
    if book_id:
        chapters = chapter_repo.get_chapters_by_book(book_id)
    else:
        # Get all chapters
        chapters = list(chapter_repo.collection.find({}, {"_id": 0}).sort("order", 1))
    
    # Convert datetime to string
    for chapter in chapters:
        chapter["created_at"] = str(chapter.get("created_at")) if chapter.get("created_at") else None
        chapter["updated_at"] = str(chapter.get("updated_at")) if chapter.get("updated_at") else None
    
    return chapters

@router.get("/{chapter_id}", response_model=ChapterResponse)
def get_chapter(chapter_id: str = Path(..., description="Chapter ID")):
    """Get chapter by ID"""
    chapter_repo = ChapterRepository()
    chapter = chapter_repo.get_chapter_by_id(chapter_id)
    
    if not chapter:
        raise HTTPException(status_code=404, detail=f"Chapter '{chapter_id}' not found")
    
    # Convert datetime to string
    chapter["created_at"] = str(chapter.get("created_at")) if chapter.get("created_at") else None
    chapter["updated_at"] = str(chapter.get("updated_at")) if chapter.get("updated_at") else None
    
    return chapter

@router.put("/{chapter_id}", response_model=ChapterResponse)
def update_chapter(
    chapter_id: str = Path(..., description="Chapter ID"),
    req: ChapterUpdateRequest = None
):
    """Update chapter by ID"""
    chapter_repo = ChapterRepository()
    
    # Check if chapter exists
    existing = chapter_repo.get_chapter_by_id(chapter_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Chapter '{chapter_id}' not found")
    
    # Update chapter
    updated = chapter_repo.update_chapter(
        chapter_id=chapter_id,
        title=req.title if req else None,
        order=req.order if req else None
    )
    
    if not updated:
        raise HTTPException(status_code=400, detail="No fields to update or update failed")
    
    # Get updated chapter
    chapter = chapter_repo.get_chapter_by_id(chapter_id)
    chapter["created_at"] = str(chapter.get("created_at")) if chapter.get("created_at") else None
    chapter["updated_at"] = str(chapter.get("updated_at")) if chapter.get("updated_at") else None
    
    return chapter

@router.delete("/{chapter_id}", response_model=DeleteResponse)
def delete_chapter(chapter_id: str = Path(..., description="Chapter ID")):
    """Delete chapter by ID (also deletes related lessons)"""
    chapter_repo = ChapterRepository()
    lesson_repo = LessonRepository()
    
    # Check if chapter exists
    existing = chapter_repo.get_chapter_by_id(chapter_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Chapter '{chapter_id}' not found")
    
    # Delete related lessons
    lessons_deleted = lesson_repo.delete_lessons_by_chapter(chapter_id)
    
    # Delete chapter
    deleted = chapter_repo.delete_chapter(chapter_id)
    
    if not deleted:
        raise HTTPException(status_code=500, detail="Failed to delete chapter")
    
    return DeleteResponse(
        success=True,
        message=f"Chapter '{chapter_id}' and {lessons_deleted} related lesson(s) deleted successfully",
        deleted_count=1
    )

