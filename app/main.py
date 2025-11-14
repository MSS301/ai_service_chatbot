from fastapi import FastAPI
# from fastapi.middleware.cors import CORSMiddleware  # CORS handled by API Gateway
from fastapi.openapi.utils import get_openapi
from contextlib import asynccontextmanager
from .api import ingest, rag, books, chapters, lessons, grades, subjects, slides
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
        get_database()
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
    lifespan=lifespan,
    servers=[
        {
            "url": "http://localhost:8080/ai-chatbot-service",
            "description": "API Gateway"
        },
        {
            "url": "http://localhost:8000",
            "description": "Direct Service (Development)"
        }
    ]
)

# CORS Configuration
# Note: CORS is handled by API Gateway (CorsWebFilter)
# AI Chatbot Service should only be accessed through API Gateway, not directly from browser
# Therefore, CORS middleware is removed to avoid duplicate CORS headers
# If you need to access this service directly (e.g., for testing), uncomment below:
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
#     expose_headers=["*"],
# )

app.include_router(ingest.router, prefix="/ai_service/ingestion", tags=["Ingestion"])
app.include_router(rag.router, prefix="/ai_service/rag", tags=["RAG Query"])
app.include_router(grades.router, prefix="/ai_service/grades", tags=["Grades"])
app.include_router(books.router, prefix="/ai_service/books", tags=["Books"])
app.include_router(chapters.router, prefix="/ai_service/chapters", tags=["Chapters"])
app.include_router(lessons.router, prefix="/ai_service/lessons", tags=["Lessons"])
app.include_router(subjects.router, prefix="/ai_service/subjects", tags=["Subjects"])
app.include_router(slides.router, prefix="/ai_service/slides", tags=["Slides"])

logger = get_logger(__name__)


def custom_openapi():
    """
    Custom OpenAPI schema with JWT Bearer authentication
    """
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        servers=app.servers,
    )
    
    # Add security scheme for JWT Bearer token
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Enter JWT token from API Gateway. Token should be obtained from auth service."
        }
    }
    
    # Apply security to all endpoints (except health check)
    # Individual endpoints can override this if needed
    for path, path_item in openapi_schema.get("paths", {}).items():
        # Skip health check endpoint
        if path == "/ai_service/" or path == "/":
            continue
        
        for method in ["get", "post", "put", "delete", "patch"]:
            if method in path_item:
                operation = path_item[method]
                # Add security requirement
                if "security" not in operation:
                    operation["security"] = [{"BearerAuth": []}]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema


# Override OpenAPI schema
app.openapi = custom_openapi


@app.get("/ai_service/", tags=["Health"])
def health_check():
    return {"status": "ok", "message": "AI Service Chatbot is running 🚀"}
