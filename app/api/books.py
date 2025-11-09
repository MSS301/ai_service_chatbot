from fastapi import APIRouter, HTTPException, Path
from typing import List
from app.repositories.book_repository import BookRepository
from app.repositories.chapter_repository import ChapterRepository
from app.repositories.lesson_repository import LessonRepository
from app.repositories.chunk_repository import ChunkRepository
from app.models.crud_model import (
    BookCreateRequest, BookUpdateRequest, BookResponse, DeleteResponse
)
from app.services.indexer import _compute_book_id

router = APIRouter()

@router.post("", response_model=BookResponse, status_code=201)
def create_book(req: BookCreateRequest):
    """Create a new book"""
    from app.repositories.grade_repository import GradeRepository
    
    # Validate grade_id exists
    grade_repo = GradeRepository()
    grade = grade_repo.get_grade_by_id(req.grade_id)
    if not grade:
        raise HTTPException(status_code=404, detail=f"Grade '{req.grade_id}' not found")
    
    grade_number = grade.get("grade_number")
    book_repo = BookRepository()
    book_id = _compute_book_id(req.book_name, grade_number)
    
    # Check if book already exists
    existing = book_repo.get_book_by_id(book_id)
    if existing:
        raise HTTPException(status_code=400, detail=f"Book with ID '{book_id}' already exists")
    
    book_repo.upsert_book(book_id, req.book_name, req.grade_id, req.structure or {})
    book = book_repo.get_book_by_id(book_id)
    
    if not book:
        raise HTTPException(status_code=500, detail="Failed to create book")
    
    # Convert datetime to string for JSON response
    book["created_at"] = str(book.get("created_at")) if book.get("created_at") else None
    book["updated_at"] = str(book.get("updated_at")) if book.get("updated_at") else None
    
    return book

@router.get("", response_model=List[BookResponse])
def get_all_books():
    """Get all books"""
    book_repo = BookRepository()
    books = book_repo.get_all_books()
    
    # Convert datetime to string
    for book in books:
        book["created_at"] = str(book.get("created_at")) if book.get("created_at") else None
        book["updated_at"] = str(book.get("updated_at")) if book.get("updated_at") else None
    
    return books

@router.get("/{book_id}", response_model=BookResponse)
def get_book(book_id: str = Path(..., description="Book ID")):
    """Get book by ID"""
    book_repo = BookRepository()
    book = book_repo.get_book_by_id(book_id)
    
    if not book:
        raise HTTPException(status_code=404, detail=f"Book '{book_id}' not found")
    
    # Convert datetime to string
    book["created_at"] = str(book.get("created_at")) if book.get("created_at") else None
    book["updated_at"] = str(book.get("updated_at")) if book.get("updated_at") else None
    
    return book

@router.put("/{book_id}", response_model=BookResponse)
def update_book(
    book_id: str = Path(..., description="Book ID"),
    req: BookUpdateRequest = None
):
    """Update book by ID"""
    book_repo = BookRepository()
    
    # Check if book exists
    existing = book_repo.get_book_by_id(book_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Book '{book_id}' not found")
    
    # Validate grade_id if provided
    if req and req.grade_id:
        from app.repositories.grade_repository import GradeRepository
        grade_repo = GradeRepository()
        grade = grade_repo.get_grade_by_id(req.grade_id)
        if not grade:
            raise HTTPException(status_code=404, detail=f"Grade '{req.grade_id}' not found")
    
    # Update book
    updated = book_repo.update_book(
        book_id=book_id,
        book_name=req.book_name if req else None,
        grade_id=req.grade_id if req else None,
        structure=req.structure if req else None
    )
    
    if not updated:
        raise HTTPException(status_code=400, detail="No fields to update or update failed")
    
    # Get updated book
    book = book_repo.get_book_by_id(book_id)
    book["created_at"] = str(book.get("created_at")) if book.get("created_at") else None
    book["updated_at"] = str(book.get("updated_at")) if book.get("updated_at") else None
    
    return book

@router.delete("/{book_id}", response_model=DeleteResponse)
def delete_book(book_id: str = Path(..., description="Book ID")):
    """Delete book by ID (also deletes related chapters, lessons, and chunks)"""
    book_repo = BookRepository()
    chapter_repo = ChapterRepository()
    lesson_repo = LessonRepository()
    chunk_repo = ChunkRepository()
    
    # Check if book exists
    existing = book_repo.get_book_by_id(book_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Book '{book_id}' not found")
    
    # Delete related data
    chapters_deleted = chapter_repo.delete_chapters_by_book(book_id)
    lessons_deleted = lesson_repo.delete_lessons_by_book(book_id)
    chunks_deleted = chunk_repo.delete_chunks_by_book(book_id)
    
    # Delete book
    deleted = book_repo.delete_book(book_id)
    
    if not deleted:
        raise HTTPException(status_code=500, detail="Failed to delete book")
    
    return DeleteResponse(
        success=True,
        message=f"Book '{book_id}' and related data deleted successfully",
        deleted_count=1
    )

