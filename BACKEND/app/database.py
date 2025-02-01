from databases import Database
from sqlalchemy import create_engine, MetaData
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from typing import Optional
from . import settings as app_settings  # Import as module
import logging

# Set up logging
logger = logging.getLogger(__name__)

# PostgreSQL Configuration
DATABASE_URL = app_settings.DATABASE_URL
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL must be set in .env file")

# Create SQL database connection
sql_database = Database(DATABASE_URL)
engine = create_engine(DATABASE_URL)
metadata = MetaData()

# Global database instances
_mongo_client: Optional[AsyncIOMotorClient] = None
_mongo_db: Optional[AsyncIOMotorDatabase] = None

async def get_sql_db() -> Database:
    """Get SQL database connection"""
    try:
        if not sql_database.is_connected:
            await sql_database.connect()
            logger.info("Connected to PostgreSQL database")
        return sql_database
    except Exception as e:
        logger.error(f"Error connecting to PostgreSQL database: {str(e)}")
        raise

async def get_database_client() -> AsyncIOMotorClient:
    """Get MongoDB client instance"""
    global _mongo_client
    
    if _mongo_client is None:
        try:
            _mongo_client = AsyncIOMotorClient(app_settings.MONGODB_URI)
            logger.info("MongoDB client initialized")
        except Exception as e:
            logger.error(f"Error initializing MongoDB client: {str(e)}")
            raise
    
    return _mongo_client

async def get_mongo_db() -> AsyncIOMotorDatabase:
    """Get MongoDB database instance"""
    global _mongo_db
    
    if _mongo_db is None:
        client = await get_database_client()
        _mongo_db = client[app_settings.DATABASE_NAME]
        logger.info("MongoDB instance set")
    
    return _mongo_db

def set_mongo_db(db: AsyncIOMotorDatabase):
    """Set the global MongoDB instance"""
    global _mongo_db
    _mongo_db = db
    logger.info("MongoDB instance set")

async def close_mongo_connection():
    """Close MongoDB connection"""
    global _mongo_client, _mongo_db
    
    if _mongo_client:
        _mongo_client.close()
        _mongo_client = None
        _mongo_db = None
        logger.info("MongoDB connection closed")

# Initialize database connection
async def init_db():
    """Initialize database connection"""
    try:
        db = await get_mongo_db()
        set_mongo_db(db)  # Set the global instance
        logger.info("Database initialized successfully")
        return db
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        raise

async def close_connections() -> None:
    """Close all database connections"""
    try:
        if sql_database.is_connected:
            await sql_database.disconnect()
            logger.info("Disconnected from PostgreSQL database")
    except Exception as e:
        logger.error(f"Error disconnecting from PostgreSQL database: {str(e)}") 