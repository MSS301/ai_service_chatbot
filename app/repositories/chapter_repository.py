from typing import Dict, List, Optional
from app.core.database import get_database
from app.core.logger import get_logger

logger = get_logger(__name__)

class ChapterRepository:
    """Repository for chapters"""
    
    def __init__(self):
        self.db = get_database()
        self.collection = self.db.chapters
    
    def create_indexes(self):
        """Create indexes for better query performance"""
        self.collection.create_index("chapter_id", unique=True)
        self.collection.create_index("book_id")
        self.collection.create_index([("book_id", 1), ("chapter_id", 1)])
    
    def upsert_chapter(self, chapter_id: str, book_id: str, chapter_title: str, order: int = 0) -> str:
        """
        Insert or update chapter
        Returns: chapter_id
        """
        from datetime import datetime
        
        doc = {
            "chapter_id": chapter_id,
            "book_id": book_id,
            "title": chapter_title,
            "order": order,
            "created_at": None,
            "updated_at": None
        }
        
        existing = self.collection.find_one({"chapter_id": chapter_id})
        if existing:
            doc["created_at"] = existing.get("created_at")
            doc["updated_at"] = datetime.utcnow()
            self.collection.update_one(
                {"chapter_id": chapter_id},
                {"$set": doc}
            )
        else:
            doc["created_at"] = datetime.utcnow()
            doc["updated_at"] = datetime.utcnow()
            self.collection.insert_one(doc)
        
        return chapter_id
    
    def get_chapter_by_id(self, chapter_id: str) -> Optional[Dict]:
        """Get chapter by chapter_id"""
        return self.collection.find_one({"chapter_id": chapter_id})
    
    def get_chapters_by_book(self, book_id: str) -> List[Dict]:
        """Get all chapters for a book, ordered by order field"""
        return list(self.collection.find(
            {"book_id": book_id},
            {"_id": 0}
        ).sort("order", 1))
    
    def update_chapter(self, chapter_id: str, title: str = None, order: int = None) -> bool:
        """Update chapter by chapter_id"""
        from datetime import datetime
        update_data = {"updated_at": datetime.utcnow()}
        if title is not None:
            update_data["title"] = title
        if order is not None:
            update_data["order"] = order
        
        result = self.collection.update_one(
            {"chapter_id": chapter_id},
            {"$set": update_data}
        )
        return result.modified_count > 0
    
    def delete_chapter(self, chapter_id: str) -> bool:
        """Delete chapter by chapter_id"""
        result = self.collection.delete_one({"chapter_id": chapter_id})
        return result.deleted_count > 0
    
    def delete_chapters_by_book(self, book_id: str) -> int:
        """Delete all chapters for a book"""
        result = self.collection.delete_many({"book_id": book_id})
        return result.deleted_count

