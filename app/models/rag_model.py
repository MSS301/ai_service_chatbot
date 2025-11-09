from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class RAGRequest(BaseModel):
    grade_id: str
    book_id: str
    chapter_id: str
    lesson_id: str
    content: str  # teacher_notes/content
    k: int = 8

class RAGResponse(BaseModel):
    outline: Dict[str, Any]
    sources: List[Dict[str, Any]]
    indices: List[int]
    distances: List[float]
