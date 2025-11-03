from fastapi import APIRouter
from app.models.ingest_model import IngestRequest, IngestResponse
from app.services.indexer import ingest_pdf

router = APIRouter()

@router.post("/ingest", response_model=IngestResponse)
def ingest_book(req: IngestRequest):
    result = ingest_pdf(req.pdf_url, req.book_name, req.grade)
    return result
