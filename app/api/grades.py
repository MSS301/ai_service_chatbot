from fastapi import APIRouter, HTTPException, Path
from typing import List
from app.repositories.grade_repository import GradeRepository
from app.repositories.book_repository import BookRepository
from app.models.crud_model import (
    GradeCreateRequest, GradeUpdateRequest, GradeResponse, DeleteResponse
)

router = APIRouter()

def _compute_grade_id(grade_number: int) -> str:
    """Compute grade_id from grade_number"""
    import hashlib
    key = f"grade_{grade_number}"
    return hashlib.md5(key.encode()).hexdigest()

@router.post("", response_model=GradeResponse, status_code=201)
def create_grade(req: GradeCreateRequest):
    """Create a new grade"""
    grade_repo = GradeRepository()
    grade_id = _compute_grade_id(req.grade_number)
    
    # Check if grade already exists
    existing = grade_repo.get_grade_by_id(grade_id)
    if existing:
        raise HTTPException(status_code=400, detail=f"Grade with ID '{grade_id}' already exists")
    
    # Check if grade_number already exists
    existing_by_number = grade_repo.get_grade_by_number(req.grade_number)
    if existing_by_number:
        raise HTTPException(status_code=400, detail=f"Grade number {req.grade_number} already exists")
    
    grade_repo.upsert_grade(grade_id, req.grade_number, req.grade_name)
    grade = grade_repo.get_grade_by_id(grade_id)
    
    if not grade:
        raise HTTPException(status_code=500, detail="Failed to create grade")
    
    # Convert datetime to string for JSON response
    grade["created_at"] = str(grade.get("created_at")) if grade.get("created_at") else None
    grade["updated_at"] = str(grade.get("updated_at")) if grade.get("updated_at") else None
    
    return grade

@router.get("", response_model=List[GradeResponse])
def get_all_grades():
    """Get all grades"""
    grade_repo = GradeRepository()
    grades = grade_repo.get_all_grades()
    
    # Convert datetime to string
    for grade in grades:
        grade["created_at"] = str(grade.get("created_at")) if grade.get("created_at") else None
        grade["updated_at"] = str(grade.get("updated_at")) if grade.get("updated_at") else None
    
    return grades

@router.get("/{grade_id}", response_model=GradeResponse)
def get_grade(grade_id: str = Path(..., description="Grade ID")):
    """Get grade by ID"""
    grade_repo = GradeRepository()
    grade = grade_repo.get_grade_by_id(grade_id)
    
    if not grade:
        raise HTTPException(status_code=404, detail=f"Grade '{grade_id}' not found")
    
    # Convert datetime to string
    grade["created_at"] = str(grade.get("created_at")) if grade.get("created_at") else None
    grade["updated_at"] = str(grade.get("updated_at")) if grade.get("updated_at") else None
    
    return grade

@router.get("/number/{grade_number}", response_model=GradeResponse)
def get_grade_by_number(grade_number: int = Path(..., description="Grade number (e.g., 12)")):
    """Get grade by grade number"""
    grade_repo = GradeRepository()
    grade = grade_repo.get_grade_by_number(grade_number)
    
    if not grade:
        raise HTTPException(status_code=404, detail=f"Grade number {grade_number} not found")
    
    # Convert datetime to string
    grade["created_at"] = str(grade.get("created_at")) if grade.get("created_at") else None
    grade["updated_at"] = str(grade.get("updated_at")) if grade.get("updated_at") else None
    
    return grade

@router.put("/{grade_id}", response_model=GradeResponse)
def update_grade(
    grade_id: str = Path(..., description="Grade ID"),
    req: GradeUpdateRequest = None
):
    """Update grade by ID"""
    grade_repo = GradeRepository()
    
    # Check if grade exists
    existing = grade_repo.get_grade_by_id(grade_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Grade '{grade_id}' not found")
    
    # Check if new grade_number conflicts with existing
    if req and req.grade_number is not None:
        existing_by_number = grade_repo.get_grade_by_number(req.grade_number)
        if existing_by_number and existing_by_number.get("grade_id") != grade_id:
            raise HTTPException(status_code=400, detail=f"Grade number {req.grade_number} already exists")
    
    # Update grade
    updated = grade_repo.update_grade(
        grade_id=grade_id,
        grade_number=req.grade_number if req else None,
        grade_name=req.grade_name if req else None
    )
    
    if not updated:
        raise HTTPException(status_code=400, detail="No fields to update or update failed")
    
    # Get updated grade
    grade = grade_repo.get_grade_by_id(grade_id)
    grade["created_at"] = str(grade.get("created_at")) if grade.get("created_at") else None
    grade["updated_at"] = str(grade.get("updated_at")) if grade.get("updated_at") else None
    
    return grade

@router.delete("/{grade_id}", response_model=DeleteResponse)
def delete_grade(grade_id: str = Path(..., description="Grade ID")):
    """Delete grade by ID (WARNING: This does not delete related books)"""
    grade_repo = GradeRepository()
    book_repo = BookRepository()
    
    # Check if grade exists
    existing = grade_repo.get_grade_by_id(grade_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Grade '{grade_id}' not found")
    
    # Check if there are books associated with this grade
    grade_number = existing.get("grade_number")
    all_books = book_repo.get_all_books()
    books_with_grade = [b for b in all_books if b.get("grade") == grade_number]
    
    if books_with_grade:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot delete grade '{grade_id}'. There are {len(books_with_grade)} book(s) associated with this grade. Please delete the books first."
        )
    
    # Delete grade
    deleted = grade_repo.delete_grade(grade_id)
    
    if not deleted:
        raise HTTPException(status_code=500, detail="Failed to delete grade")
    
    return DeleteResponse(
        success=True,
        message=f"Grade '{grade_id}' deleted successfully",
        deleted_count=1
    )

