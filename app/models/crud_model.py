from pydantic import BaseModel
from typing import Optional, Dict, Any

# ========== Subject Models ==========
class SubjectCreateRequest(BaseModel):
    subject_code: str
    subject_name: str

class SubjectUpdateRequest(BaseModel):
    subject_code: Optional[str] = None
    subject_name: Optional[str] = None

class SubjectResponse(BaseModel):
    subject_id: str
    subject_code: str
    subject_name: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

# ========== Grade-Subject Link Models ==========
class GradeSubjectLinkRequest(BaseModel):
    grade_id: str
    subject_id: str

# ========== Grade Models ==========
class GradeCreateRequest(BaseModel):
    grade_number: int
    grade_name: str

class GradeUpdateRequest(BaseModel):
    grade_number: Optional[int] = None
    grade_name: Optional[str] = None

class GradeResponse(BaseModel):
    grade_id: str
    grade_number: int
    grade_name: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

# ========== Book Models ==========
class BookCreateRequest(BaseModel):
    book_name: str
    grade_id: str
    subject_id: Optional[str] = None
    structure: Optional[Dict[str, Any]] = None

class BookUpdateRequest(BaseModel):
    book_name: Optional[str] = None
    grade_id: Optional[str] = None
    subject_id: Optional[str] = None
    structure: Optional[Dict[str, Any]] = None

class BookResponse(BaseModel):
    book_id: str
    book_name: str
    grade_id: str
    subject_id: Optional[str] = None
    structure: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

# ========== Chapter Models ==========
class ChapterCreateRequest(BaseModel):
    book_id: str
    title: str
    order: int = 0

class ChapterUpdateRequest(BaseModel):
    title: Optional[str] = None
    order: Optional[int] = None

class ChapterResponse(BaseModel):
    chapter_id: str
    book_id: str
    title: str
    order: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

# ========== Lesson Models ==========
class LessonCreateRequest(BaseModel):
    chapter_id: str
    book_id: str
    title: str
    page: Optional[int] = None
    order: int = 0

class LessonUpdateRequest(BaseModel):
    title: Optional[str] = None
    page: Optional[int] = None
    order: Optional[int] = None

class LessonResponse(BaseModel):
    lesson_id: str
    chapter_id: str
    book_id: str
    title: str
    page: Optional[int] = None
    order: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

# ========== Generic Response Models ==========
class DeleteResponse(BaseModel):
    success: bool
    message: str
    deleted_count: Optional[int] = None

