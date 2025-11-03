from fastapi import FastAPI
from app.api import ingest, rag

app = FastAPI(
    title="AI Service Chatbot",
    version="1.0.0",
    description="AI-powered RAG service for textbooks."
)

# Đăng ký router
app.include_router(ingest.router, prefix="/admin", tags=["Ingestion"])
app.include_router(rag.router, prefix="/rag", tags=["RAG Query"])

@app.get("/", tags=["Health"])
def health_check():
    return {"status": "ok", "message": "AI Service Chatbot is running 🚀"}
