from typing import Dict, Optional, List
from datetime import datetime, timezone
from app.core.database import get_database
from app.core.logger import get_logger
import uuid

logger = get_logger(__name__)


class ContentRepository:
    """Repository for generated teaching contents"""

    def __init__(self):
        self.db = get_database()
        self.collection = self.db.contents

    def create_indexes(self):
        self.collection.create_index("content_id", unique=True)
        self.collection.create_index([("grade_id", 1), ("book_id", 1), ("chapter_id", 1), ("lesson_id", 1)])
        self.collection.create_index("subject_id")

    @staticmethod
    def new_content_id() -> str:
        return uuid.uuid4().hex

    def insert_content(self, doc: Dict) -> str:
        now = datetime.now(timezone.utc)
        doc.setdefault("created_at", now)
        doc.setdefault("updated_at", now)
        self.collection.insert_one(doc)
        return doc["content_id"]

    def get_by_id(self, content_id: str) -> Optional[Dict]:
        return self.collection.find_one({"content_id": content_id}, {"_id": 0})

    def update_content(self, content_id: str, new_text: str, outline: Optional[Dict] = None, meta: Optional[Dict] = None) -> bool:
        update = {
            "$set": {
                "content_text": new_text,
                "updated_at": datetime.now(timezone.utc),
            },
            "$inc": {"version": 1}
        }
        if outline is not None:
            update["$set"]["outline"] = outline
        if meta:
            update["$set"].update(meta)
        res = self.collection.update_one({"content_id": content_id}, update)
        return res.modified_count > 0

    def list_by_scope(self, grade_id: str, book_id: str, chapter_id: str, lesson_id: str) -> List[Dict]:
        return list(self.collection.find(
            {"grade_id": grade_id, "book_id": book_id, "chapter_id": chapter_id, "lesson_id": lesson_id},
            {"_id": 0}
        ).sort("updated_at", -1))


