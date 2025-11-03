import os, json, time, hashlib, requests
from typing import Dict, List
import numpy as np, faiss
from app.core.config import INDEX_PATH, META_PATH, DATA_DIR, CACHE_DIR
from app.core.logger import get_logger
from app.services.parser import parse_pdf_bytes
from app.services.chunker import chunk_pages
from app.services.embedder import embed_texts

logger = get_logger(__name__)

def _ensure_index(dim: int) -> faiss.IndexFlatL2:
    if os.path.exists(INDEX_PATH):
        return faiss.read_index(INDEX_PATH)
    os.makedirs(DATA_DIR, exist_ok=True)
    index = faiss.IndexFlatL2(dim)
    faiss.write_index(index, INDEX_PATH)
    return index

def _ensure_meta() -> Dict:
    if os.path.exists(META_PATH):
        with open(META_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    os.makedirs(DATA_DIR, exist_ok=True)
    meta = {"chunks": []}
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    return meta

def _cache_key(book_name: str, grade: int, pdf_bytes: bytes) -> str:
    return hashlib.md5((book_name+str(grade)+str(len(pdf_bytes))).encode()).hexdigest()

def ingest_pdf(pdf_url: str, book_name: str, grade: int) -> Dict:
    t0 = time.time()
    os.makedirs(CACHE_DIR, exist_ok=True)
    logger.info(f"Downloading PDF: {pdf_url}")
    pdf_bytes = requests.get(pdf_url).content

    key = _cache_key(book_name, grade, pdf_bytes)
    cache_file = os.path.join(CACHE_DIR, f"{key}_pages.json")

    if os.path.exists(cache_file):
        pages = json.load(open(cache_file, "r", encoding="utf-8"))
        logger.info(f"Loaded cached pages: {cache_file}")
    else:
        pages = parse_pdf_bytes(pdf_bytes, lang="vie", prefer_text=True)
        json.dump(pages, open(cache_file, "w", encoding="utf-8"), ensure_ascii=False)
        logger.info(f"Cached pages: {cache_file}")

    chunks = chunk_pages(pages, book_name, grade, size=800, overlap=100)
    texts = [c["text"] for c in chunks]
    vectors = embed_texts(texts)
    dim = len(vectors[0])

    index = _ensure_index(dim)
    index.add(np.array(vectors, dtype="float32"))
    faiss.write_index(index, INDEX_PATH)

    meta = _ensure_meta()
    start = len(meta["chunks"])
    for i, c in enumerate(chunks):
        c["embedding_index"] = start + i
        meta["chunks"].append(c)
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    duration = int(time.time() - t0)
    logger.info(f"Ingestion completed in {duration}s, chunks: {len(chunks)}")
    return {
        "status": "completed",
        "chunks_created": len(chunks),
        "embeddings_indexed": len(chunks),
        "total_pages": len(pages),
        "duration_seconds": duration
    }
