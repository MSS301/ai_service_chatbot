from fastapi import FastAPI
from .api import ingest, rag
from .core.logger import get_logger
from .services.utils import ensure_data_dirs

app = FastAPI(
    title="AI Service Chatbot",
    version="1.0.0",
    description="AI-powered RAG service for textbooks."
)

app.include_router(ingest.router, prefix="/admin", tags=["Ingestion"])
app.include_router(rag.router, prefix="/rag", tags=["RAG Query"])

logger = get_logger(__name__)
ensure_data_dirs()

@app.get("/", tags=["Health"])
def health_check():
    return {"status": "ok", "message": "AI Service Chatbot is running 🚀"}
