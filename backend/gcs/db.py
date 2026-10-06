"""MongoDB connection helper."""
import os
from motor.motor_asyncio import AsyncIOMotorClient

_client: AsyncIOMotorClient | None = None
_db = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        _client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=5000)
    return _client



def get_db():
    global _db
    if _db is None:
        db_name = os.environ.get("DB_NAME", "aether_gcs")
        _db = get_client()[db_name]
    return _db


async def close_db():
    global _client
    if _client is not None:
        _client.close()
        _client = None
