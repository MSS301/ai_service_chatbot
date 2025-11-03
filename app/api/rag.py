from fastapi import APIRouter
from app.models.rag_model import RAGRequest, RAGResponse
from app.services.rag_engine import rag_query

router = APIRouter()

@router.post("/query", response_model=RAGResponse)
def rag_query_endpoint(req: RAGRequest):
    outline, distances, indices = rag_query(req.lesson_id, req.teacher_notes, k=req.k)
    return {
        "outline": outline,
        "sources": outline.get("sources", []),
        "indices": indices,
        "distances": distances
    }
