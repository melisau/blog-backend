from beanie import init_beanie
from pymongo import AsyncMongoClient

from core.config import MONGODB_DB_NAME, MONGODB_URL
from models import Category, Comment, Blog, User

# Beanie 2.x uses PyMongo's AsyncMongoClient, not Motor's AsyncIOMotorClient.
mongo_client: AsyncMongoClient | None = None


async def init_db() -> AsyncMongoClient:
    global mongo_client

    if not MONGODB_URL:
        raise ValueError("MONGODB_URL is not set. Please configure it in your .env file.")

    mongo_client = AsyncMongoClient(MONGODB_URL)

    # Category must appear before Blog because Blog holds a Link[Category].
    # Beanie resolves forward references in declaration order.
    await init_beanie(
        database=mongo_client[MONGODB_DB_NAME],
        document_models=[Category, Blog, Comment, User],
    )

    return mongo_client


async def close_db() -> None:
    global mongo_client

    if mongo_client is not None:
        await mongo_client.close()
        mongo_client = None
