from typing import Dict, List, Optional
from app.core.database import get_database
from app.core.logger import get_logger

logger = get_logger(__name__)

class ChunkRepository:
    """Repository for document chunks and embeddings"""
    
    def __init__(self):
        self.db = get_database()
        self._collection = self.db.chunks
    
    @property
    def collection(self):
        """Expose collection for direct access if needed"""
        return self._collection
    
    def create_indexes(self):
        """Create indexes for better query performance"""
        self.collection.create_index("book_id")
        self.collection.create_index("chapter_id")
        self.collection.create_index("lesson_id")
        self.collection.create_index("embedding_index", unique=True)
        self.collection.create_index([("book_id", 1), ("page", 1)])
        self.collection.create_index([("book_id", 1), ("chapter_id", 1)])
        self.collection.create_index([("book_id", 1), ("chapter_id", 1), ("lesson_id", 1)])
    
    def insert_chunks(self, chunks: List[Dict], book_id: str):
        """
        Insert multiple chunks for a book
        chunks should have: text, page, chapter, lesson, embedding_index, book
        """
        if not chunks:
            return
        
        # Add book_id to each chunk
        for chunk in chunks:
            chunk["book_id"] = book_id
        
        self.collection.insert_many(chunks)
        logger.info(f"Inserted {len(chunks)} chunks for book: {book_id}")
    
    def get_chunks_by_book(self, book_id: str) -> List[Dict]:
        """Get all chunks for a book"""
        return list(self.collection.find({"book_id": book_id}, {"_id": 0}))
    
    def get_chunks_by_indices(self, indices: List[int]) -> List[Dict]:
        """Get chunks by embedding indices, preserving the order of indices"""
        if not indices:
            return []
        
        # Get chunks and create a map for O(1) lookup
        chunks_map = {
            chunk["embedding_index"]: chunk
            for chunk in self.collection.find(
                {"embedding_index": {"$in": indices}},
                {"_id": 0}
            )
        }
        
        # Return chunks in the same order as indices
        result = []
        for idx in indices:
            if idx in chunks_map:
                result.append(chunks_map[idx])
        
        return result
    
    def delete_chunks_by_book(self, book_id: str) -> int:
        """Delete all chunks for a book"""
        result = self.collection.delete_many({"book_id": book_id})
        deleted = result.deleted_count
        if deleted > 0:
            logger.info(f"Deleted {deleted} chunks for book: {book_id}")
        return deleted
    
    def count_chunks_by_book(self, book_id: str) -> int:
        """Count chunks for a book"""
        return self.collection.count_documents({"book_id": book_id})

