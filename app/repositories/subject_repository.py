from typing import Dict, List, Optional
from app.core.database import get_database
from app.core.logger import get_logger
from datetime import datetime, timezone
import hashlib

logger = get_logger(__name__)


class SubjectRepository:
    """Repository for subjects"""

    def __init__(self):
        self.db = get_database()
        self.collection = self.db.subjects

    def create_indexes(self):
        self.collection.create_index("subject_id", unique=True)
        self.collection.create_index("subject_code", unique=True)
        self.collection.create_index("subject_name")

    @staticmethod
    def compute_subject_id(subject_code: str) -> str:
        base = f"subject::{subject_code.strip().lower()}"
        return hashlib.md5(base.encode("utf-8")).hexdigest()

    def upsert_subject(self, subject_id: str, subject_code: str, subject_name: str) -> str:
        doc = {
            "subject_id": subject_id,
            "subject_code": subject_code,
            "subject_name": subject_name,
            "updated_at": datetime.now(timezone.utc),
        }
        existing = self.collection.find_one({"subject_id": subject_id})
        if existing:
            doc["created_at"] = existing.get("created_at")
            self.collection.update_one({"subject_id": subject_id}, {"$set": doc})
            logger.info(f"Updated subject: {subject_code}")
        else:
            doc["created_at"] = datetime.now(timezone.utc)
            self.collection.insert_one(doc)
            logger.info(f"Created subject: {subject_code}")
        return subject_id

    def get_subject_by_id(self, subject_id: str) -> Optional[Dict]:
        return self.collection.find_one({"subject_id": subject_id}, {"_id": 0})

    def get_subject_by_code(self, subject_code: str) -> Optional[Dict]:
        return self.collection.find_one({"subject_code": subject_code}, {"_id": 0})

    def get_all_subjects(self) -> List[Dict]:
        return list(self.collection.find({}, {"_id": 0}).sort("subject_code", 1))

    def update_subject(self, subject_id: str, subject_code: Optional[str] = None, subject_name: Optional[str] = None) -> bool:
        update_data: Dict = {"updated_at": datetime.now(timezone.utc)}
        if subject_code is not None:
            update_data["subject_code"] = subject_code
        if subject_name is not None:
            update_data["subject_name"] = subject_name
        res = self.collection.update_one({"subject_id": subject_id}, {"$set": update_data})
        return res.modified_count > 0

    def delete_subject(self, subject_id: str) -> bool:
        res = self.collection.delete_one({"subject_id": subject_id})
        return res.deleted_count > 0


class GradeSubjectRepository:
    """Join collection for many-to-many: Grade <-> Subject"""

    def __init__(self):
        self.db = get_database()
        self.collection = self.db.grade_subjects

    def create_indexes(self):
        # unique pair
        self.collection.create_index([("grade_id", 1), ("subject_id", 1)], unique=True)
        self.collection.create_index("grade_id")
        self.collection.create_index("subject_id")

    def link(self, grade_id: str, subject_id: str) -> bool:
        try:
            self.collection.update_one(
                {"grade_id": grade_id, "subject_id": subject_id},
                {"$set": {"grade_id": grade_id, "subject_id": subject_id}},
                upsert=True,
            )
            return True
        except Exception as e:
            logger.error(f"Failed to link grade-subject: {e}")
            return False

    def unlink(self, grade_id: str, subject_id: str) -> bool:
        res = self.collection.delete_one({"grade_id": grade_id, "subject_id": subject_id})
        return res.deleted_count > 0

    def get_subjects_by_grade(self, grade_id: str) -> List[str]:
        return [d["subject_id"] for d in self.collection.find({"grade_id": grade_id}, {"_id": 0, "subject_id": 1})]

    def get_grades_by_subject(self, subject_id: str) -> List[str]:
        return [d["grade_id"] for d in self.collection.find({"subject_id": subject_id}, {"_id": 0, "grade_id": 1})]


