from typing import Optional, Dict, List
from datetime import datetime, timezone
from app.core.database import get_database
from app.core.logger import get_logger
from bson import ObjectId
import uuid
import gridfs

logger = get_logger(__name__)


class SlideTemplateRepository:
    """
    Lưu template PPTX vào MongoDB bằng GridFS.
    Collection metadata: slide_templates
    File binary: GridFS (fs.files/fs.chunks)
    """

    def __init__(self):
        self.db = get_database()
        self.collection = self.db.slide_templates
        self.fs = gridfs.GridFS(self.db)

    def create_indexes(self):
        self.collection.create_index("template_id", unique=True)
        self.collection.create_index("name")
        self.collection.create_index("filename")
        self.collection.create_index("created_at")

    @staticmethod
    def new_template_id() -> str:
        return uuid.uuid4().hex

    def insert_template(
        self,
        name: str,
        filename: str,
        content_type: str,
        data: bytes,
        description: Optional[str] = None,
    ) -> str:
        now = datetime.now(timezone.utc)
        template_id = self.new_template_id()
        # Store file in GridFS
        file_id = self.fs.put(data, filename=filename, contentType=content_type)
        doc = {
            "template_id": template_id,
            "name": name,
            "filename": filename,
            "content_type": content_type,
            "file_id": file_id,
            "description": description,
            "size": len(data),
            "created_at": now,
            "updated_at": now,
        }
        self.collection.insert_one(doc)
        return template_id

    def get_template_by_id(self, template_id: str) -> Optional[Dict]:
        doc = self.collection.find_one({"template_id": template_id}, {"_id": 0})
        return doc

    def list_templates(self) -> List[Dict]:
        items = list(self.collection.find({}, {"_id": 0}).sort("created_at", -1))
        return items

    def download_template_file(self, template_id: str) -> Optional[bytes]:
        doc = self.collection.find_one({"template_id": template_id})
        if not doc:
            return None
        file_id = doc.get("file_id")
        if not file_id:
            return None
        grid_out = self.fs.get(ObjectId(str(file_id)))
        return grid_out.read()

    def delete_template(self, template_id: str) -> bool:
        doc = self.collection.find_one({"template_id": template_id})
        if not doc:
            return False
        file_id = doc.get("file_id")
        if file_id:
            try:
                self.fs.delete(ObjectId(str(file_id)))
            except Exception:
                pass
        res = self.collection.delete_one({"template_id": template_id})
        return res.deleted_count > 0


