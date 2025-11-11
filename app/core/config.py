import os
from pathlib import Path
from dotenv import load_dotenv

# Always load the app/.env regardless of current working directory
APP_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = APP_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-ada-002")
CHAT_MODEL = os.getenv("CHAT_MODEL", "gpt-4-turbo")

DATA_DIR = os.getenv("DATA_DIR", "app/data/faiss")
CACHE_DIR = os.getenv("CACHE_DIR", "app/data/cache")
FORCE_OCR = os.getenv("FORCE_OCR", "0") == "1"

# MongoDB Configuration
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "ai_chatbot_mss301")

# Paths (still used for FAISS index files)
INDEX_PATH = os.path.join(DATA_DIR, "index.faiss")
# META_PATH deprecated - using MongoDB instead
# META_PATH = os.path.join(DATA_DIR, "metadata.json")  # Only for migration script

# Slides generation (external) - used to build embed/download links in RAG response
SLIDES_BASE_URL = os.getenv("SLIDES_BASE_URL", "https://api.slidesgpt.com")
SLIDESGPT_API_KEY = os.getenv("SLIDESGPT_API_KEY", "")

# Slides template (local PPTX)
SLIDES_TEMPLATE_DIR = os.getenv("SLIDES_TEMPLATE_DIR", "app/assets/slides/templates")
SLIDES_DEFAULT_THEME = os.getenv("SLIDES_DEFAULT_THEME", "default")
