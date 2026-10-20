from pymongo import MongoClient
from app.core.config import settings
from motor.motor_asyncio import AsyncIOMotorClient

client = MongoClient(settings.MONGO_URL)
mongo_db = client[settings.MONGO_DB]

itineraries_collection = mongo_db["itineraries"]

async def get_mongo_db():
    """Get async MongoDB connection"""
    client = AsyncIOMotorClient(settings.MONGO_URL)
    try:
        db = client[settings.MONGO_DB]
        yield db
    finally:
        client.close()

# Helper function to get specific collections
async def get_itineraries_collection():
    """Get itineraries collection"""
    db = await get_mongo_db().__anext__()
    return db["itineraries"]