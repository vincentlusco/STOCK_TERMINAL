import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import asyncio
from typing import Optional
import logging
from pymongo.errors import ServerSelectionTimeoutError, ConnectionFailure

# Set up logging
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# MongoDB Configuration
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "bloomberg_lite")

# JWT Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# MongoDB Collections
STOCKS_COLLECTION = "stocks"
WATCHLIST_COLLECTION = "watchlists"

# Initialize MongoDB client
mongo_client = None
db = None

async def init_mongodb():
    global mongo_client, db
    retries = 3
    retry_delay = 2  # seconds
    
    for attempt in range(retries):
        try:
            logger.info(f"Connecting to MongoDB (attempt {attempt + 1}/{retries})...")
            mongo_client = AsyncIOMotorClient(
                MONGO_URI,
                serverSelectionTimeoutMS=5000,
                maxPoolSize=50
            )
            db = mongo_client[DB_NAME]
            
            # Test connection
            await mongo_client.admin.command('ping')
            
            # Drop existing indexes to avoid conflicts
            try:
                await db.stocks.drop_indexes()
                await db.stock_history.drop_indexes()
                await db.users.drop_indexes()
                await db.watchlists.drop_indexes()
            except Exception as e:
                logger.warning(f"Error dropping indexes: {str(e)}")
            
            # Create optimized indexes with explicit names
            await db.stocks.create_index(
                [("symbol", 1)], 
                unique=True, 
                name="idx_stocks_symbol_unique"
            )
            await db.stocks.create_index(
                [("last_updated", 1)], 
                expireAfterSeconds=300,
                name="idx_stocks_ttl"
            )
            
            await db.stock_history.create_index(
                [("symbol", 1)], 
                unique=True,
                name="idx_history_symbol_unique"
            )
            await db.stock_history.create_index(
                [("last_updated", 1)], 
                expireAfterSeconds=86400,
                name="idx_history_ttl"
            )
            
            await db.users.create_index(
                "username", 
                unique=True,
                name="idx_users_username_unique"
            )
            await db.users.create_index(
                "email", 
                unique=True,
                name="idx_users_email_unique"
            )
            
            await db.watchlists.create_index(
                [("user_id", 1), ("name", 1)], 
                unique=True,
                name="idx_watchlist_userid_name_unique"
            )
            
            # Add this to the init_mongodb function after creating indexes
            try:
                # Clear existing collections to ensure clean data
                await db.stocks.delete_many({})
                await db.stock_history.delete_many({})
                logger.info("Cleared existing stock data cache")
            except Exception as e:
                logger.warning(f"Error clearing cache: {str(e)}")
            
            logger.info("MongoDB connected and indexes created successfully")
            return
            
        except Exception as e:
            logger.error(f"MongoDB connection attempt {attempt + 1} failed: {str(e)}")
            if attempt < retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
            else:
                raise

async def close_mongodb():
    if mongo_client:
        logger.info("Closing MongoDB connection...")
        mongo_client.close()
        logger.info("MongoDB connection closed")

def get_db():
    global db
    if db is None:
        raise Exception("Database not initialized. Call init_mongodb() first")
    return db

class Settings:
    HOST = os.getenv("HOST", "127.0.0.1")
    PORT = int(os.getenv("PORT", 8000))
    NGROK_AUTH_TOKEN = os.getenv("NGROK_AUTH_TOKEN", "")
    DEV_MODE = os.getenv("DEV_MODE", "true").lower() == "true"

settings = Settings() 