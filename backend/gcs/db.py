"""MongoDB connection helper."""
import os
from motor.motor_asyncio import AsyncIOMotorClient

_client: AsyncIOMotorClient | None = None
_db = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=2000)
    return _client



def get_db():
    global _db
    if _db is None:
        _db = get_client()[os.environ["DB_NAME"]]
    return _db


async def close_db():
    global _client
    if _client is not None:
        _client.close()
        _client = None
