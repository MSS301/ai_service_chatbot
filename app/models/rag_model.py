from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class RAGRequest(BaseModel):
    grade_id: str
    book_id: str
    chapter_id: str
    lesson_id: str
    content: str  # teacher_notes/content
    subject_id: Optional[str] = None
    k: int = 8

class RAGResponse(BaseModel):
    outline: Dict[str, Any]
    sources: List[Dict[str, Any]]
    indices: List[int]
    distances: List[float]
    content_id: Optional[str] = None
    content_text: Optional[str] = None

class ContentReviseRequest(BaseModel):
    instruction: str
    created_by: Optional[str] = None

class ContentReviseResponse(BaseModel):
    content_id: str
    content_text: str

class SlideContentRequest(BaseModel):
    content: str
    style: Optional[str] = None

class SlideContentResponse(BaseModel):
    markdown: str

class SlidesGPTRequest(BaseModel):
    prompt: str

class SlidesGPTResponse(BaseModel):
    id: str
    embed: str
    download: str

class TemplateSlidesRequest(BaseModel):
    title: str
    outline: Dict[str, Any]
    theme: Optional[str] = None

class TemplateSlidesResponse(BaseModel):
    slides: List[Dict[str, Any]]
