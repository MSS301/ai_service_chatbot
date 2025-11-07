from typing import Dict, List, Optional
from app.core.database import get_database
from app.core.logger import get_logger

logger = get_logger(__name__)

class LessonRepository:
    """Repository for lessons"""
    
    def __init__(self):
        self.db = get_database()
        self.collection = self.db.lessons
    
    def create_indexes(self):
        """Create indexes for better query performance"""
        self.collection.create_index("lesson_id", unique=True)
        self.collection.create_index("chapter_id")
        self.collection.create_index("book_id")
        self.collection.create_index([("chapter_id", 1), ("lesson_id", 1)])
        self.collection.create_index([("book_id", 1), ("chapter_id", 1)])
    
    def upsert_lesson(self, lesson_id: str, chapter_id: str, book_id: str, lesson_title: str, page: int = None, order: int = 0) -> str:
        """
        Insert or update lesson
        Returns: lesson_id
        """
        from datetime import datetime
        
        doc = {
            "lesson_id": lesson_id,
            "chapter_id": chapter_id,
            "book_id": book_id,
            "title": lesson_title,
            "page": page,
            "order": order,
            "created_at": None,
            "updated_at": None
        }
        
        existing = self.collection.find_one({"lesson_id": lesson_id})
        if existing:
            doc["created_at"] = existing.get("created_at")
            doc["updated_at"] = datetime.utcnow()
            self.collection.update_one(
                {"lesson_id": lesson_id},
                {"$set": doc}
            )
        else:
            doc["created_at"] = datetime.utcnow()
            doc["updated_at"] = datetime.utcnow()
            self.collection.insert_one(doc)
        
        return lesson_id
    
    def get_lesson_by_id(self, lesson_id: str) -> Optional[Dict]:
        """Get lesson by lesson_id"""
        return self.collection.find_one({"lesson_id": lesson_id})
    
    def get_lessons_by_chapter(self, chapter_id: str) -> List[Dict]:
        """Get all lessons for a chapter, ordered by order field"""
        return list(self.collection.find(
            {"chapter_id": chapter_id},
            {"_id": 0}
        ).sort("order", 1))
    
    def get_lessons_by_book(self, book_id: str) -> List[Dict]:
        """Get all lessons for a book"""
        return list(self.collection.find(
            {"book_id": book_id},
            {"_id": 0}
        ).sort("order", 1))
    
    def delete_lessons_by_chapter(self, chapter_id: str) -> int:
        """Delete all lessons for a chapter"""
        result = self.collection.delete_many({"chapter_id": chapter_id})
        return result.deleted_count
    
    def update_lesson(self, lesson_id: str, title: str = None, page: int = None, order: int = None) -> bool:
        """Update lesson by lesson_id"""
        from datetime import datetime
        update_data = {"updated_at": datetime.utcnow()}
        if title is not None:
            update_data["title"] = title
        if page is not None:
            update_data["page"] = page
        if order is not None:
            update_data["order"] = order
        
        result = self.collection.update_one(
            {"lesson_id": lesson_id},
            {"$set": update_data}
        )
        return result.modified_count > 0
    
    def delete_lesson(self, lesson_id: str) -> bool:
        """Delete lesson by lesson_id"""
        result = self.collection.delete_one({"lesson_id": lesson_id})
        return result.deleted_count > 0
    
    def delete_lessons_by_chapter(self, chapter_id: str) -> int:
        """Delete all lessons for a chapter"""
        result = self.collection.delete_many({"chapter_id": chapter_id})
        return result.deleted_count
    
    def delete_lessons_by_book(self, book_id: str) -> int:
        """Delete all lessons for a book"""
        result = self.collection.delete_many({"book_id": book_id})
        return result.deleted_count

