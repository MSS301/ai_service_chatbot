from fastapi import APIRouter, HTTPException
from app.models.ingest_model import IngestRequest, IngestResponse
from app.services.indexer import ingest_pdf
import json
import os
import shutil

router = APIRouter()

FAISS_DIR = "app/data/faiss"
CACHE_DIR = "app/data/cache"
METADATA_PATH = os.path.join(FAISS_DIR, "metadata.json")

@router.get("/ingest")
def get_all_ingested_books():
    """
    📘 Lấy danh sách tất cả sách đã ingest (từ metadata.json)
    """
    if not os.path.exists(METADATA_PATH):
        return {"books": []}
    
    with open(METADATA_PATH, "r", encoding="utf-8") as f:
        metadata = json.load(f)
    
    # Gom nhóm theo tên sách
    books = {}
    for chunk in metadata.get("chunks", []):
        book = chunk["book"]
        if book not in books:
            books[book] = {
                "grade": chunk.get("grade"),
                "chunks": 0,
                "pages": set()
            }
        books[book]["chunks"] += 1
        books[book]["pages"].add(chunk["page"])
    
    # Chuyển set → list
    for b in books.values():
        b["pages"] = sorted(b["pages"])
    
    return {"books": books}

@router.post("/ingest", response_model=IngestResponse)
def ingest_book(req: IngestRequest):
    result = ingest_pdf(req.pdf_url, req.book_name, req.grade)
    return result

@router.delete("/ingest/{book_name}")
def delete_ingested_book(book_name: str):
    """
    ❌ Xóa toàn bộ dữ liệu (metadata + cache) của 1 sách cụ thể
    """
    if not os.path.exists(METADATA_PATH):
        raise HTTPException(status_code=404, detail="metadata.json not found")
    
    with open(METADATA_PATH, "r", encoding="utf-8") as f:
        metadata = json.load(f)
    
    # Lọc ra các chunk KHÔNG thuộc book_name
    old_count = len(metadata.get("chunks", []))
    metadata["chunks"] = [
        c for c in metadata.get("chunks", []) if c["book"] != book_name
    ]
    new_count = len(metadata["chunks"])
    
    # Ghi lại metadata.json
    with open(METADATA_PATH, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    
    # Xóa cache (nếu có)
    if os.path.exists(CACHE_DIR):
        for f in os.listdir(CACHE_DIR):
            if book_name.lower().replace(" ", "_") in f.lower():
                os.remove(os.path.join(CACHE_DIR, f))
    
    return {
        "status": "deleted",
        "book_name": book_name,
        "removed_chunks": old_count - new_count
    }
