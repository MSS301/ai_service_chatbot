from typing import List, Dict
from langchain.text_splitter import RecursiveCharacterTextSplitter

def chunk_pages(pages: List[Dict], book_name: str, grade: int,
                size: int = 800, overlap: int = 100) -> List[Dict]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=size,
        chunk_overlap=overlap,
        length_function=lambda x: len(x.split())
    )
    chunks = []
    for p in pages:
        text = p.get("text") or ""
        for chunk_text in splitter.split_text(text):
            chunks.append({
                "chunk_id": f"chunk_{len(chunks)+1:06d}",
                "book": book_name,
                "grade": grade,
                "page": p["page_num"],
                "text": chunk_text
            })
    return chunks
