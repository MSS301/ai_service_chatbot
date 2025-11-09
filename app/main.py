from fastapi import FastAPI
from contextlib import asynccontextmanager
from .api import ingest, rag, books, chapters, lessons, grades
from .core.logger import get_logger
from .core.database import get_database, close_database
from .repositories.book_repository import BookRepository
from .repositories.chunk_repository import ChunkRepository
from .repositories.chapter_repository import ChapterRepository
from .repositories.lesson_repository import LessonRepository
from .repositories.grade_repository import GradeRepository
from .services.utils import ensure_data_dirs

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger = get_logger(__name__)
    ensure_data_dirs()
    try:
        # Initialize MongoDB connection and create indexes
        db = get_database()
        book_repo = BookRepository()
        chunk_repo = ChunkRepository()
        chapter_repo = ChapterRepository()
        lesson_repo = LessonRepository()
        grade_repo = GradeRepository()
        book_repo.create_indexes()
        chunk_repo.create_indexes()
        chapter_repo.create_indexes()
        lesson_repo.create_indexes()
        grade_repo.create_indexes()
        logger.info("MongoDB initialized and indexes created")
    except Exception as e:
        logger.error(f"Failed to initialize MongoDB: {e}")
    yield
    # Shutdown
    close_database()
    logger.info("Application shutdown")

app = FastAPI(
    title="AI Service Chatbot",
    version="1.0.0",
    description="AI-powered RAG service for textbooks.",
    lifespan=lifespan
)

app.include_router(ingest.router, prefix="/api/ai_service/admin", tags=["Ingestion"])
app.include_router(rag.router, prefix="/api/ai_service/rag", tags=["RAG Query"])
app.include_router(grades.router, prefix="/api/ai_service/grades", tags=["Grades"])
app.include_router(books.router, prefix="/api/ai_service/books", tags=["Books"])
app.include_router(chapters.router, prefix="/api/ai_service/chapters", tags=["Chapters"])
app.include_router(lessons.router, prefix="/api/ai_service/lessons", tags=["Lessons"])

logger = get_logger(__name__)

@app.get("/api/ai_service/", tags=["Health"])
def health_check():
    return {"status": "ok", "message": "AI Service Chatbot is running 🚀"}
