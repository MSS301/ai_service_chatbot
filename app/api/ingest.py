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
                "id": metadata.get("books", {}).get(book, {}).get("id"),  # có thể None nếu sách cũ
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

@router.get("/ingest/id/{book_id}")
def get_book_by_id(book_id: str):
    """
    🔎 Tìm sách theo book_id
    """
    if not os.path.exists(METADATA_PATH):
        raise HTTPException(status_code=404, detail="No books ingested yet")

    with open(METADATA_PATH, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    books_meta = metadata.get("books", {})
    match = None
    for name, info in books_meta.items():
        if info.get("id") == book_id:
            match = {"book_name": name, "grade": info.get("grade"), "structure": info.get("structure", {})}
            break

    if not match:
        raise HTTPException(status_code=404, detail=f"Book id '{book_id}' not found")

    return match

@router.get("/ingest/id/{book_id}/structure")
def get_book_structure_by_id(book_id: str):
    """
    📖 Lấy cấu trúc chương/bài chi tiết bằng book_id
    """
    if not os.path.exists(METADATA_PATH):
        raise HTTPException(status_code=404, detail="No books ingested yet")

    with open(METADATA_PATH, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    books_meta = metadata.get("books", {})
    for name, info in books_meta.items():
        if info.get("id") == book_id:
            return {
                "book_id": book_id,
                "book_name": name,
                "grade": info.get("grade"),
                "structure": info.get("structure", {})
            }

    raise HTTPException(status_code=404, detail=f"Book id '{book_id}' not found")

@router.get("/ingest/{book_name}/structure")
def get_book_structure(book_name: str):
    """
    📖 Lấy cấu trúc chương/bài chi tiết của một sách cụ thể
    """
    if not os.path.exists(METADATA_PATH):
        raise HTTPException(status_code=404, detail="No books ingested yet")
    
    with open(METADATA_PATH, "r", encoding="utf-8") as f:
        metadata = json.load(f)
    
    # Nếu đã có structure được lưu khi ingest, dùng trực tiếp
    if metadata.get("books", {}).get(book_name):
        saved = metadata["books"][book_name]
        return {
            "book_name": book_name,
            "grade": saved.get("grade"),
            "structure": saved.get("structure", {})
        }

    # Lọc chunks của sách cụ thể (fallback)
    book_chunks = [c for c in metadata.get("chunks", []) if c.get("book") == book_name]
    
    if not book_chunks:
        raise HTTPException(status_code=404, detail=f"Book '{book_name}' not found")
    
    # Gom nhóm theo chương và bài
    structure = {}
    for chunk in book_chunks:
        chapter = chunk.get("chapter", "")
        lesson = chunk.get("lesson", "")
        
        if chapter:
            if chapter not in structure:
                structure[chapter] = {
                    "lessons": {},
                    "total_chunks": 0,
                    "pages": set()
                }
            
            if lesson and lesson not in structure[chapter]["lessons"]:
                structure[chapter]["lessons"][lesson] = {
                    "pages": set(),
                    "chunks": 0
                }
            
            if lesson:
                structure[chapter]["lessons"][lesson]["pages"].add(chunk["page"])
                structure[chapter]["lessons"][lesson]["chunks"] += 1
            
            structure[chapter]["total_chunks"] += 1
            structure[chapter]["pages"].add(chunk["page"])
    
    # Convert sets to sorted lists
    for chapter_data in structure.values():
        chapter_data["pages"] = sorted(chapter_data["pages"])
        for lesson_data in chapter_data["lessons"].values():
            lesson_data["pages"] = sorted(lesson_data["pages"])
    
    return {
        "book_name": book_name,
        "structure": structure
    }

@router.post("/ingest", response_model=IngestResponse)
def ingest_book(req: IngestRequest):
    result = ingest_pdf(
        pdf_url=req.pdf_url,
        book_name=req.book_name,
        grade=req.grade,
        force_reparse=req.force_reparse,
        force_clear_cache=req.force_clear_cache,
    )
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

    # Xóa cache cấu trúc đã lưu trong metadata["books"]
    if "books" in metadata and book_name in metadata["books"]:
        del metadata["books"][book_name]
    
    # Ghi lại metadata.json
    with open(METADATA_PATH, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    
    # Xóa cache (nếu có)
    # Yêu cầu: xóa hết cache để lần ingest sau luôn mới
    if os.path.exists(CACHE_DIR):
        for f in os.listdir(CACHE_DIR):
            try:
                os.remove(os.path.join(CACHE_DIR, f))
            except Exception:
                pass
    
    return {
        "status": "deleted",
        "book_name": book_name,
        "removed_chunks": old_count - new_count
    }
