from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
import asyncio
from typing import Optional
import logging
from pymongo.errors import ServerSelectionTimeoutError, ConnectionFailure
from .database import set_mongo_db, init_db, close_mongo_connection, get_mongo_db
from . import settings as app_settings  # Import as module

# Set up logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Initialize MongoDB client and database
mongo_client: Optional[AsyncIOMotorClient] = None
mongo_db: Optional[AsyncIOMotorDatabase] = None

async def init_mongodb():
    """Initialize MongoDB connection"""
    try:
        logger.info("Connecting to MongoDB (attempt 1/3)...")
        logger.info(f"Using MongoDB URI: {app_settings.MONGODB_URI}")
        logger.info(f"Using Database: {app_settings.DATABASE_NAME}")
        
        # Initialize the database
        db = await init_db()
        logger.info("MongoDB connected successfully")
        return db
        
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {str(e)}")
        raise

async def init_indexes(db: AsyncIOMotorDatabase) -> None:
    """Initialize MongoDB indexes"""
    try:
        # Collections to index
        collections = [
            app_settings.STOCKS_COLLECTION,
            app_settings.STOCK_HISTORY_COLLECTION,
            app_settings.USERS_COLLECTION,
            app_settings.WATCHLIST_COLLECTION
        ]

        # Drop existing indexes
        for collection in collections:
            try:
                await db[collection].drop_indexes()
            except Exception as e:
                logger.warning(f"Error dropping indexes for {collection}: {str(e)}")

        # Create new indexes
        await db[app_settings.STOCKS_COLLECTION].create_index(
            [("symbol", 1)], unique=True, name="idx_stocks_symbol_unique"
        )
        await db[app_settings.STOCKS_COLLECTION].create_index(
            [("last_updated", 1)], expireAfterSeconds=300, name="idx_stocks_ttl"
        )
        
        await db[app_settings.STOCK_HISTORY_COLLECTION].create_index(
            [("symbol", 1)], unique=True, name="idx_history_symbol_unique"
        )
        await db[app_settings.STOCK_HISTORY_COLLECTION].create_index(
            [("last_updated", 1)], expireAfterSeconds=86400, name="idx_history_ttl"
        )
        
        await db[app_settings.USERS_COLLECTION].create_index(
            "username", unique=True, name="idx_users_username_unique"
        )
        await db[app_settings.USERS_COLLECTION].create_index(
            "email", unique=True, name="idx_users_email_unique"
        )
        
        await db[app_settings.WATCHLIST_COLLECTION].create_index(
            [("user_id", 1), ("name", 1)], unique=True, name="idx_watchlist_userid_name_unique"
        )
        
        logger.info("MongoDB indexes created successfully")
    except Exception as e:
        logger.error(f"Error creating indexes: {str(e)}")
        raise

async def close_mongodb():
    """Close MongoDB connection"""
    try:
        await close_mongo_connection()
        logger.info("MongoDB connection closed")
    except Exception as e:
        logger.error(f"Error closing MongoDB connection: {str(e)}")
        raise

def get_db() -> AsyncIOMotorDatabase:
    """Get MongoDB database instance"""
    if mongo_db is None:
        raise Exception("Database not initialized. Call init_mongodb() first")
    return mongo_db

class Settings:
    HOST = app_settings.HOST
    PORT = app_settings.PORT
    NGROK_AUTH_TOKEN = app_settings.NGROK_AUTH_TOKEN
    DEV_MODE = app_settings.DEV_MODE

class AppSettings:
    MONGODB_URI: str = "mongodb://localhost:27017"
    DATABASE_NAME: str = "bloomberg_lite"
    STOCKS_COLLECTION: str = "stocks"
    STOCK_HISTORY_COLLECTION: str = "stock_history"
    USERS_COLLECTION: str = "users"
    # ... rest of your settings ...

settings = Settings() 