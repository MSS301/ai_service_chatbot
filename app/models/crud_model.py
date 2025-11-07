from pydantic import BaseModel
from typing import Optional, Dict, Any

# ========== Book Models ==========
class BookCreateRequest(BaseModel):
    book_name: str
    grade: int
    structure: Optional[Dict[str, Any]] = None

class BookUpdateRequest(BaseModel):
    book_name: Optional[str] = None
    grade: Optional[int] = None
    structure: Optional[Dict[str, Any]] = None

class BookResponse(BaseModel):
    book_id: str
    book_name: str
    grade: int
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

