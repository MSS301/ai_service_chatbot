from pydantic import BaseModel

class IngestRequest(BaseModel):
    pdf_url: str
    book_name: str
    grade_id: str
    force_reparse: bool = True
    force_clear_cache: bool = True

class IngestResponse(BaseModel):
    status: str
    chunks_created: int
    embeddings_indexed: int
    total_pages: int
    duration_seconds: int
