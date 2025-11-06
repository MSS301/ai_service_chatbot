from pymongo import MongoClient
from pymongo.database import Database
from app.core.config import MONGODB_URI, MONGODB_DB_NAME
from app.core.logger import get_logger

logger = get_logger(__name__)

_client: MongoClient = None
_db: Database = None

def get_database() -> Database:
    """Get MongoDB database instance (singleton)"""
    global _db, _client
    if _db is None:
        if not MONGODB_URI:
            raise ValueError("MONGODB_URI not set in environment variables")
        _client = MongoClient(MONGODB_URI)
        _db = _client[MONGODB_DB_NAME]
        logger.info(f"Connected to MongoDB: {MONGODB_DB_NAME}")
    return _db

def close_database():
    """Close MongoDB connection"""
    global _client, _db
    if _client:
        _client.close()
        _client = None
        _db = None
        logger.info("MongoDB connection closed")

