"""
Script để migrate dữ liệu từ metadata.json sang MongoDB
Chạy: python -m app.scripts.migrate_to_mongodb
"""
import json
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

# Set working directory to project root
os.chdir(project_root)

from app.core.config import META_PATH, DATA_DIR
from app.core.database import get_database
from app.repositories.book_repository import BookRepository
from app.repositories.chunk_repository import ChunkRepository
from app.services.indexer import _compute_book_id
from app.core.logger import get_logger

logger = get_logger(__name__)

def migrate_metadata_to_mongodb():
    """Migrate books and chunks from metadata.json to MongoDB"""
    
    # Check if metadata.json exists
    if not os.path.exists(META_PATH):
        logger.info(f"No metadata.json found at {META_PATH}. Nothing to migrate.")
        return
    
    logger.info(f"Reading metadata from {META_PATH}")
    
    # Read metadata.json
    with open(META_PATH, "r", encoding="utf-8") as f:
        metadata = json.load(f)
    
    # Initialize repositories
    book_repo = BookRepository()
    chunk_repo = ChunkRepository()
    
    # Create indexes
    book_repo.create_indexes()
    chunk_repo.create_indexes()
    
    # Migrate books
    books_meta = metadata.get("books", {})
    migrated_books = 0
    
    for book_name, book_info in books_meta.items():
        grade = book_info.get("grade")
        structure = book_info.get("structure", {})
        book_id = book_info.get("id") or _compute_book_id(book_name, grade or 0)
        
        # Check if book already exists
        existing = book_repo.get_book_by_id(book_id)
        if existing:
            logger.info(f"Book '{book_name}' (id: {book_id}) already exists in MongoDB, skipping...")
            continue
        
        # Insert book
        book_repo.upsert_book(book_id, book_name, grade, structure)
        migrated_books += 1
        logger.info(f"Migrated book: {book_name} (id: {book_id})")
    
    # Migrate chunks
    chunks = metadata.get("chunks", [])
    if not chunks:
        logger.info("No chunks found in metadata.json")
        return
    
    logger.info(f"Found {len(chunks)} chunks to migrate")
    
    # Group chunks by book
    chunks_by_book = {}
    for chunk in chunks:
        book_name = chunk.get("book")
        if not book_name:
            continue
        
        # Find book_id for this book
        book_id = None
        if book_name in books_meta:
            book_id = books_meta[book_name].get("id") or _compute_book_id(book_name, books_meta[book_name].get("grade", 0))
        else:
            # Try to infer grade from chunk
            grade = chunk.get("grade", 0)
            book_id = _compute_book_id(book_name, grade)
        
        if book_id not in chunks_by_book:
            chunks_by_book[book_id] = []
        
        # Add book_id to chunk
        chunk["book_id"] = book_id
        chunks_by_book[book_id].append(chunk)
    
    # Insert chunks by book
    total_chunks = 0
    for book_id, book_chunks in chunks_by_book.items():
        # Check if chunks already exist
        existing_count = chunk_repo.count_chunks_by_book(book_id)
        if existing_count > 0:
            logger.info(f"Book {book_id} already has {existing_count} chunks, skipping...")
            continue
        
        # Insert chunks
        chunk_repo.insert_chunks(book_chunks, book_id)
        total_chunks += len(book_chunks)
        logger.info(f"Migrated {len(book_chunks)} chunks for book_id: {book_id}")
    
    logger.info(f"Migration completed:")
    logger.info(f"  - Books migrated: {migrated_books}")
    logger.info(f"  - Chunks migrated: {total_chunks}")

if __name__ == "__main__":
    try:
        migrate_metadata_to_mongodb()
    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        sys.exit(1)

