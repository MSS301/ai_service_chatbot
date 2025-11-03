from pydantic import BaseModel

class IngestRequest(BaseModel):
    pdf_url: str
    book_name: str
    grade: int

class IngestResponse(BaseModel):
    status: str
    chunks_created: int
    embeddings_indexed: int
    total_pages: int
    duration_seconds: int
