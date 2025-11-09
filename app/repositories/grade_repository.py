from typing import Dict, List, Optional
from app.core.database import get_database
from app.core.logger import get_logger

logger = get_logger(__name__)

class GradeRepository:
    """Repository for grades"""
    
    def __init__(self):
        self.db = get_database()
        self.collection = self.db.grades
    
    def create_indexes(self):
        """Create indexes for better query performance"""
        self.collection.create_index("grade_id", unique=True)
        self.collection.create_index("grade_number", unique=True)
        self.collection.create_index("grade_name")
    
    def upsert_grade(self, grade_id: str, grade_number: int, grade_name: str) -> str:
        """
        Insert or update grade
        Returns: grade_id
        """
        from datetime import datetime
        
        doc = {
            "grade_id": grade_id,
            "grade_number": grade_number,
            "grade_name": grade_name,
            "created_at": None,
            "updated_at": None
        }
        
        existing = self.collection.find_one({"grade_id": grade_id})
        if existing:
            doc["created_at"] = existing.get("created_at")
            doc["updated_at"] = datetime.utcnow()
            self.collection.update_one(
                {"grade_id": grade_id},
                {"$set": doc}
            )
            logger.info(f"Updated grade: {grade_id}")
        else:
            doc["created_at"] = datetime.utcnow()
            doc["updated_at"] = datetime.utcnow()
            self.collection.insert_one(doc)
            logger.info(f"Created grade: {grade_id}")
        
        return grade_id
    
    def get_grade_by_id(self, grade_id: str) -> Optional[Dict]:
        """Get grade by grade_id"""
        return self.collection.find_one({"grade_id": grade_id})
    
    def get_grade_by_number(self, grade_number: int) -> Optional[Dict]:
        """Get grade by grade_number"""
        return self.collection.find_one({"grade_number": grade_number})
    
    def get_all_grades(self) -> List[Dict]:
        """Get all grades, ordered by grade_number"""
        return list(self.collection.find({}, {"_id": 0}).sort("grade_number", 1))
    
    def update_grade(self, grade_id: str, grade_number: int = None, grade_name: str = None) -> bool:
        """Update grade by grade_id"""
        from datetime import datetime
        update_data = {"updated_at": datetime.utcnow()}
        if grade_number is not None:
            update_data["grade_number"] = grade_number
        if grade_name is not None:
            update_data["grade_name"] = grade_name
        
        result = self.collection.update_one(
            {"grade_id": grade_id},
            {"$set": update_data}
        )
        return result.modified_count > 0
    
    def delete_grade(self, grade_id: str) -> bool:
        """Delete grade by grade_id"""
        result = self.collection.delete_one({"grade_id": grade_id})
        deleted = result.deleted_count > 0
        if deleted:
            logger.info(f"Deleted grade: {grade_id}")
        return deleted

