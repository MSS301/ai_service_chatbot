from typing import Dict, List, Optional
from app.core.database import get_database
from app.core.logger import get_logger

logger = get_logger(__name__)

class BookRepository:
    """Repository for book metadata and structure"""
    
    def __init__(self):
        self.db = get_database()
        self._collection = self.db.books
    
    @property
    def collection(self):
        """Expose collection for direct access if needed"""
        return self._collection
    
    def create_indexes(self):
        """Create indexes for better query performance"""
        self.collection.create_index("book_id", unique=True)
        self.collection.create_index("book_name")
        self.collection.create_index("grade_id")
        self.collection.create_index("subject_id")
    
    def upsert_book(self, book_id: str, book_name: str, grade_id: str, structure: Dict, subject_id: Optional[str] = None) -> str:
        """
        Insert or update book metadata
        Returns: book_id
        """
        doc = {
            "book_id": book_id,
            "book_name": book_name,
            "grade_id": grade_id,
            "subject_id": subject_id,
            "structure": structure,
            "created_at": None,
            "updated_at": None
        }
        
        from datetime import datetime, timezone
        existing = self.collection.find_one({"book_id": book_id})
        if existing:
            doc["created_at"] = existing.get("created_at")
            doc["updated_at"] = datetime.now(timezone.utc)
            self.collection.update_one(
                {"book_id": book_id},
                {"$set": doc}
            )
            logger.info(f"Updated book: {book_id}")
        else:
            doc["created_at"] = datetime.now(timezone.utc)
            doc["updated_at"] = datetime.now(timezone.utc)
            self.collection.insert_one(doc)
            logger.info(f"Created book: {book_id}")
        
        return book_id
    
    def get_book_by_id(self, book_id: str) -> Optional[Dict]:
        """Get book by book_id"""
        return self.collection.find_one({"book_id": book_id})
    
    def get_book_by_name(self, book_name: str) -> Optional[Dict]:
        """Get book by book_name"""
        return self.collection.find_one({"book_name": book_name})
    
    def get_all_books(self) -> List[Dict]:
        """Get all books"""
        return list(self.collection.find({}, {"_id": 0}))
    
    def delete_book(self, book_id: str) -> bool:
        """Delete book by book_id"""
        result = self.collection.delete_one({"book_id": book_id})
        deleted = result.deleted_count > 0
        if deleted:
            logger.info(f"Deleted book: {book_id}")
        return deleted
    
    def update_book(self, book_id: str, book_name: str = None, grade_id: str = None, structure: Dict = None, subject_id: Optional[str] = None) -> bool:
        """Update book by book_id"""
        from datetime import datetime, timezone
        update_data = {"updated_at": datetime.now(timezone.utc)}
        if book_name is not None:
            update_data["book_name"] = book_name
        if grade_id is not None:
            update_data["grade_id"] = grade_id
        if structure is not None:
            update_data["structure"] = structure
        if subject_id is not None:
            update_data["subject_id"] = subject_id
        
        result = self.collection.update_one(
            {"book_id": book_id},
            {"$set": update_data}
        )
        return result.modified_count > 0


    
    def delete_book_by_name(self, book_name: str) -> bool:
        """Delete book by book_name"""
        result = self.collection.delete_one({"book_name": book_name})
        deleted = result.deleted_count > 0
        if deleted:
            logger.info(f"Deleted book by name: {book_name}")
        return deleted

