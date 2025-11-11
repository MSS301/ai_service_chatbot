from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
from app.models.ingest_model import IngestRequest, IngestResponse
from app.services.indexer import ingest_pdf, _compute_book_id, rebuild_faiss_index
from app.repositories.book_repository import BookRepository
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.chapter_repository import ChapterRepository
from app.repositories.lesson_repository import LessonRepository
from app.core.logger import get_logger
from app.core.auth import get_current_user, UserInfo
import os

# Optional import for migration (only if needed)
try:
    from app.scripts.migrate_to_mongodb import migrate_metadata_to_mongodb
    MIGRATION_AVAILABLE = True
except ImportError:
    MIGRATION_AVAILABLE = False
    migrate_metadata_to_mongodb = None

router = APIRouter()

CACHE_DIR = "app/data/cache"
logger = get_logger(__name__)


def _delete_book_resources(book_id: str, book_name: Optional[str] = None):
    """Xóa toàn bộ dữ liệu liên quan tới book_id (chunks, chapters, lessons, metadata, cache, FAISS)."""
    chunk_repo = ChunkRepository()
    chapter_repo = ChapterRepository()
    lesson_repo = LessonRepository()
    book_repo = BookRepository()

    deleted_chunks = chunk_repo.delete_chunks_by_book(book_id)
    deleted_lessons = lesson_repo.delete_lessons_by_book(book_id)
    deleted_chapters = chapter_repo.delete_chapters_by_book(book_id)

    # Delete book metadata (failsafe: ignore if already removed)
    book_deleted = book_repo.delete_book(book_id)
    if not book_deleted:
        logger.warning(f"Book metadata for '{book_id}' was not found during deletion")

    # Xóa cache (nếu có)
    if os.path.exists(CACHE_DIR):
        for f in os.listdir(CACHE_DIR):
            try:
                os.remove(os.path.join(CACHE_DIR, f))
            except Exception:
                pass

    # Rebuild FAISS index để đồng bộ
    logger.info("Rebuilding FAISS index after deleting book...")
    rebuild_faiss_index()

    return {
        "status": "deleted",
        "book_id": book_id,
        "book_name": book_name,
        "removed_chunks": deleted_chunks,
        "removed_chapters": deleted_chapters,
        "removed_lessons": deleted_lessons,
    }

@router.get("/")
def get_all_ingested_books(user: UserInfo = Depends(get_current_user)):
    """
    📘 Lấy danh sách tất cả sách đã ingest (từ MongoDB)
    """
    logger.info(f"User {user.user_id} requested all ingested books")
    book_repo = BookRepository()
    chunk_repo = ChunkRepository()
    
    all_books = book_repo.get_all_books()
    books = {}
    
    for book in all_books:
        book_id = book.get("book_id")
        book_name = book.get("book_name")
        grade_id = book.get("grade_id")
        
        # Count chunks and pages
        chunks = chunk_repo.get_chunks_by_book(book_id)
        pages = sorted({c.get("page") for c in chunks if c.get("page")})
        
        books[book_name] = {
            "id": book_id,
            "grade_id": grade_id,
            "chunks": len(chunks),
            "pages": pages
        }
    
    return {"books": books}

@router.get("/id/{book_id}")
def get_book_by_id(book_id: str, user: UserInfo = Depends(get_current_user)):
    """
    🔎 Tìm sách theo book_id
    """
    logger.info(f"User {user.user_id} requested book {book_id}")
    book_repo = BookRepository()
    book = book_repo.get_book_by_id(book_id)
    
    if not book:
        raise HTTPException(status_code=404, detail=f"Book id '{book_id}' not found")
    
    return {
        "book_id": book.get("book_id"),
        "book_name": book.get("book_name"),
        "grade_id": book.get("grade_id"),
        "structure": book.get("structure", {})
    }

@router.get("/id/{book_id}/structure")
def get_book_structure_by_id(book_id: str, user: UserInfo = Depends(get_current_user)):
    """
    📖 Lấy cấu trúc chương/bài chi tiết bằng book_id
    """
    logger.info(f"User {user.user_id} requested structure for book {book_id}")
    book_repo = BookRepository()
    book = book_repo.get_book_by_id(book_id)
    
    if not book:
        raise HTTPException(status_code=404, detail=f"Book id '{book_id}' not found")
    
    return {
        "book_id": book.get("book_id"),
        "book_name": book.get("book_name"),
        "grade_id": book.get("grade_id"),
        "structure": book.get("structure", {})
    }

@router.get("/{book_name}/structure")
def get_book_structure(book_name: str, user: UserInfo = Depends(get_current_user)):
    """
    📖 Lấy cấu trúc chương/bài chi tiết của một sách cụ thể
    """
    logger.info(f"User {user.user_id} requested structure for book {book_name}")
    book_repo = BookRepository()
    book = book_repo.get_book_by_name(book_name)
    
    if not book:
        raise HTTPException(status_code=404, detail=f"Book '{book_name}' not found")
    
    return {
        "book_id": book.get("book_id"),
        "book_name": book.get("book_name"),
        "grade_id": book.get("grade_id"),
        "structure": book.get("structure", {})
    }

@router.post("/", response_model=IngestResponse)
def ingest_book(req: IngestRequest, user: UserInfo = Depends(get_current_user)):
    """
    📥 Ingest sách mới (yêu cầu ADMIN role từ API Gateway)
    """
    logger.info(f"User {user.user_id} requested to ingest book: {req.book_name}")
    result = ingest_pdf(
        pdf_url=req.pdf_url,
        book_name=req.book_name,
        grade_id=req.grade_id,
        force_reparse=req.force_reparse,
        force_clear_cache=req.force_clear_cache,
    )
    return result

@router.post("/migrate")
def migrate_books_to_mongodb(user: UserInfo = Depends(get_current_user)):
    """
    🔄 Migrate dữ liệu từ metadata.json sang MongoDB (nếu có)
    Chỉ migrate những sách/chunks chưa có trong MongoDB
    Yêu cầu ADMIN role từ API Gateway
    """
    logger.info(f"User {user.user_id} requested migration")
    if not MIGRATION_AVAILABLE:
        raise HTTPException(
            status_code=501, 
            detail="Migration script not available. All data is now stored in MongoDB directly."
        )
    
    try:
        migrate_metadata_to_mongodb()
        return {
            "status": "success",
            "message": "Migration completed. Check logs for details."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Migration failed: {str(e)}")

@router.get("/collections/status")
def get_collections_status(user: UserInfo = Depends(get_current_user)):
    """
    📊 Kiểm tra trạng thái collections trong MongoDB
    Yêu cầu ADMIN role từ API Gateway
    """
    logger.info(f"User {user.user_id} requested collections status")
    from app.core.database import get_database
    
    db = get_database()
    collections = db.list_collection_names()
    
    status = {
        "database": db.name,
        "collections": {}
    }
    
    for coll_name in ["books", "chunks", "chapters", "lessons"]:
        if coll_name in collections:
            coll = db[coll_name]
            count = coll.count_documents({})
            indexes = list(coll.list_indexes())
            status["collections"][coll_name] = {
                "exists": True,
                "document_count": count,
                "indexes": [idx.get("name") for idx in indexes]
            }
        else:
            status["collections"][coll_name] = {
                "exists": False,
                "document_count": 0,
                "indexes": []
            }
    
    return status

@router.delete("/by-id/{book_id}")
def delete_ingested_book_by_id(book_id: str, user: UserInfo = Depends(get_current_user)):
    """
    ❌ Xóa toàn bộ dữ liệu của một sách theo book_id.
    Yêu cầu ADMIN role từ API Gateway
    """
    logger.info(f"User {user.user_id} requested to delete book {book_id}")
    book_repo = BookRepository()
    book = book_repo.get_book_by_id(book_id)

    if not book:
        raise HTTPException(status_code=404, detail=f"Book '{book_id}' not found")

    book_name = book.get("book_name")
    return _delete_book_resources(book_id=book_id, book_name=book_name)


@router.delete("/{book_name}")
def delete_ingested_book(book_name: str, user: UserInfo = Depends(get_current_user)):
    """
    ❌ Xóa toàn bộ dữ liệu (MongoDB + cache + FAISS) của một sách theo tên.
    Yêu cầu ADMIN role từ API Gateway
    """
    logger.info(f"User {user.user_id} requested to delete book {book_name}")
    book_repo = BookRepository()
    book = book_repo.get_book_by_name(book_name)

    if not book:
        raise HTTPException(status_code=404, detail=f"Book '{book_name}' not found")

    book_id = book.get("book_id")
    return _delete_book_resources(book_id=book_id, book_name=book_name)
