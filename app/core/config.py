import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-ada-002")
CHAT_MODEL = os.getenv("CHAT_MODEL", "gpt-4-turbo")

DATA_DIR = os.getenv("DATA_DIR", "app/data/faiss")
CACHE_DIR = os.getenv("CACHE_DIR", "app/data/cache")
FORCE_OCR = os.getenv("FORCE_OCR", "0") == "1"

# Paths
INDEX_PATH = os.path.join(DATA_DIR, "index.faiss")
META_PATH = os.path.join(DATA_DIR, "metadata.json")
