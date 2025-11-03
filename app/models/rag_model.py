from pydantic import BaseModel
from typing import List, Dict, Any

class RAGRequest(BaseModel):
    lesson_id: str
    teacher_notes: str
    k: int = 8

class RAGResponse(BaseModel):
    outline: Dict[str, Any]
    sources: List[Dict[str, Any]]
    indices: List[int]
    distances: List[float]
