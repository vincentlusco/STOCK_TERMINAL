from motor.motor_asyncio import AsyncIOMotorClient
from .settings import Settings

settings = Settings()
mongo_client = None
mongo_db = None

async def init_db():
    global mongo_client, mongo_db
    mongo_client = AsyncIOMotorClient(settings.MONGO_URI)
    mongo_db = mongo_client[settings.DB_NAME]
    return mongo_db

async def close_mongo_connection():
    if mongo_client:
        mongo_client.close()

def get_mongo_db():
    return mongo_db

def set_mongo_db(db):
    global mongo_db
    mongo_db = db 