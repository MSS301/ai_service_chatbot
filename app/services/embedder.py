from typing import List
from openai import OpenAI
from app.core.config import OPENAI_API_KEY, EMBED_MODEL
from app.core.logger import get_logger

logger = get_logger(__name__)

def _get_client() -> OpenAI:
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is not set. Add it to app/.env")
    return OpenAI(api_key=OPENAI_API_KEY)

def embed_texts(texts: List[str], batch_size: int = 100) -> List[List[float]]:
    client = _get_client()
    vectors: List[List[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        resp = client.embeddings.create(model=EMBED_MODEL, input=batch)
        vectors.extend([d.embedding for d in resp.data])
        logger.info(f"Embedded {i+len(batch)}/{len(texts)}")
    return vectors

def embed_query(text: str) -> List[float]:
    client = _get_client()
    return client.embeddings.create(model=EMBED_MODEL, input=text).data[0].embedding
