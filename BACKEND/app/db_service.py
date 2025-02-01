from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase, AsyncIOMotorClient
import bcrypt
import logging
from bson import ObjectId
from pydantic import BaseModel
from .settings import settings as app_settings
from .database import get_mongo_db
from pymongo.errors import OperationFailure
from pymongo import MongoClient, ASCENDING
from pymongo.collection import Collection

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class UserInDB(BaseModel):
    id: Optional[str] = None
    username: str
    email: str
    created_at: datetime

class WatchList(BaseModel):
    id: Optional[str] = None
    user_id: str
    name: str
    symbols: List[str]
    created_at: datetime
    last_updated: datetime

class User(BaseModel):
    id: int
    username: str
    email: str

    @classmethod
    def from_auth_user(cls, auth_user):
        return cls(
            id=auth_user.id,
            username=auth_user.username,
            email=auth_user.email
        )

class DatabaseService:
    def __init__(self, connection_string: str):
        self.client = AsyncIOMotorClient(connection_string)
        self.db = self.client.bloomberg_lite
        self.stocks = self.db.stocks
        self.users = self.db.users
        self.watchlists = self.db.watchlists
        self._initialized = False

    async def ensure_initialized(self):
        """Ensure database is initialized"""
        if not self._initialized:
            try:
                # Test connection
                await self.client.admin.command('ping')
                logger.info("MongoDB connection test successful")
                # Initialize indexes
                await self._init_indexes()
                self._initialized = True
                logger.info("Database initialized successfully")
            except Exception as e:
                logger.error(f"Database initialization failed: {e}")
                # Try to reconnect
                try:
                    self.client = AsyncIOMotorClient(app_settings.MONGO_URI)
                    await self.client.admin.command('ping')
                    logger.info("MongoDB reconnection successful")
                except Exception as reconnect_error:
                    logger.error(f"MongoDB reconnection failed: {reconnect_error}")
                raise

    async def _init_indexes(self) -> None:
        try:
            # Drop existing indexes to avoid conflicts
            await self.stocks.drop_indexes()
            await self.users.drop_indexes()
            await self.watchlists.drop_indexes()

            await self.stocks.create_index([("symbol", 1)], unique=True)
            await self.users.create_index([("username", 1)], unique=True)
            await self.users.create_index([("email", 1)], unique=True)
            await self.watchlists.create_index([("user_id", 1)])
            # Add TTL index for stock data cache
            await self.stocks.create_index(
                "lastUpdated", 
                expireAfterSeconds=300,  # 5 minutes
                name="idx_stocks_ttl"
            )
            logger.info("Database collections and indexes initialized")
        except Exception as e:
            logger.error(f"Error initializing indexes: {e}")
            raise

    async def get_user_watchlist(self, user_id: str) -> Optional[List[str]]:
        try:
            watchlist = await self.watchlists.find_one({"user_id": user_id})
            return watchlist.get("symbols", []) if watchlist else []
        except Exception as e:
            logger.error(f"Error getting watchlist: {e}")
            return []

    async def add_to_watchlist(self, user_id: str, symbol: str) -> bool:
        try:
            result = await self.watchlists.update_one(
                {"user_id": user_id},
                {"$addToSet": {"symbols": symbol}},
                upsert=True
            )
            return result.modified_count > 0 or result.upserted_id is not None
        except Exception as e:
            logger.error(f"Error adding to watchlist: {e}")
            return False

    async def remove_from_watchlist(self, user_id: str, symbol: str) -> bool:
        try:
            result = await self.watchlists.update_one(
                {"user_id": user_id},
                {"$pull": {"symbols": symbol}}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error removing from watchlist: {e}")
            return False

    async def store_stock_data(self, stock_data: Dict[str, Any]) -> bool:
        try:
            if not stock_data or "symbol" not in stock_data:
                return False
                
            result = await self.stocks.update_one(
                {"symbol": stock_data["symbol"]},
                {"$set": stock_data},
                upsert=True
            )
            return result.modified_count > 0 or result.upserted_id is not None
        except Exception as e:
            logger.error(f"Error storing stock data: {e}")
            return False

    async def get_stock_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        try:
            result = await self.stocks.find_one({"symbol": symbol}, {"_id": 0})
            return result
        except Exception as e:
            logger.error(f"Error retrieving stock data: {e}")
            return None

    async def verify_password(self, username: str, password: str) -> bool:
        try:
            user = await self.users.find_one({"username": username})
            if not user:
                return False
            return bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8'))
        except Exception as e:
            logger.error(f"Error verifying password: {e}")
            return False

    async def create_user(self, username: str, email: str, password: str) -> Optional[Dict]:
        try:
            # Hash the password
            hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            
            # Create user document
            user = {
                "username": username,
                "email": email,
                "hashed_password": hashed.decode('utf-8'),
                "created_at": datetime.utcnow(),
                "watchlists": []
            }
            
            # Insert the user
            result = await self.users.insert_one(user)
            user['_id'] = str(result.inserted_id)
            return user
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            return None

    async def get_user_by_username(self, username: str) -> Optional[Dict]:
        try:
            user = await self.users.find_one({"username": username})
            if user:
                user['_id'] = str(user['_id'])
            return user
        except Exception as e:
            logger.error(f"Error getting user: {e}")
            return None

    async def create_index_if_not_exists(self, collection, index_spec, **kwargs):
        """Create an index if it doesn't exist"""
        try:
            await collection.create_index(index_spec, **kwargs)
        except OperationFailure as e:
            if "Index already exists" in str(e):
                logger.info(f"Index already exists for {collection.name}: {index_spec}")
            else:
                raise

    async def initialize(self):
        """Initialize database and collections"""
        try:
            # Get MongoDB client
            self.client = AsyncIOMotorClient(app_settings.MONGODB_URI)
            self.db = self.client[app_settings.DATABASE_NAME]
            
            # Initialize collections
            self.users = self.db[app_settings.USERS_COLLECTION]
            self.stocks = self.db[app_settings.STOCKS_COLLECTION]
            self.watchlists = self.db[app_settings.WATCHLIST_COLLECTION]
            
            # Create TTL index for stocks collection
            await self.db.stocks.create_index(
                "expiration", 
                expireAfterSeconds=0
            )
            
            # Create indexes safely
            await self.create_index_if_not_exists(
                self.stocks, 
                [("symbol", 1)], 
                unique=True
            )
            await self.create_index_if_not_exists(
                self.users, 
                [("username", 1)], 
                unique=True
            )
            await self.create_index_if_not_exists(
                self.users, 
                [("email", 1)], 
                unique=True
            )
            await self.create_index_if_not_exists(
                self.watchlists, 
                [("user_id", 1), ("symbol", 1)], 
                unique=True
            )
            
            logger.info("Database collections and indexes initialized")
            
        except Exception as e:
            logger.error(f"Error initializing database: {str(e)}")
            raise

    async def connect(self):
        """Initialize database connection"""
        try:
            self.client = AsyncIOMotorClient(app_settings.MONGODB_URI)
            self.db = self.client[app_settings.DATABASE_NAME]
            # Test connection
            await self.client.admin.command('ping')
            logger.info("Connected to MongoDB successfully")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {str(e)}")
            raise

    async def close(self):
        """Close database connection"""
        if self.client:
            self.client.close()
            logger.info("Database connection closed")

    async def get_user(self, username: str) -> Optional[UserInDB]:
        """Get user by username"""
        try:
            user_doc = await self.users.find_one({"username": username})
            if user_doc:
                # Convert _id to string id
                user_doc["id"] = str(user_doc["_id"])
                return UserInDB(**user_doc)
            return None
        except Exception as e:
            logger.error(f"Error getting user {username}: {str(e)}")
            return None

    async def create_watchlist(self, user_id: str, name: str = "Default") -> WatchList:
        """Create a new watchlist for user"""
        try:
            # Check if watchlist already exists
            existing_watchlist = await self.get_watchlist(user_id, name)
            if existing_watchlist:
                return existing_watchlist

            # Create new watchlist
            now = datetime.utcnow()
            watchlist = WatchList(
                user_id=str(user_id),
                name=name,
                symbols=[],
                created_at=now,
                last_updated=now
            )

            try:
                result = await self.db.watchlists.insert_one(watchlist.dict())
                watchlist.id = str(result.inserted_id)
                return watchlist
            except Exception as e:
                if "duplicate key error" in str(e):
                    existing = await self.get_watchlist(user_id, name)
                    if existing:
                        return existing
                raise

        except Exception as e:
            logger.error(f"Error creating watchlist: {str(e)}")
            raise

    async def get_watchlist(self, user_id: str, list_name: str = "Default") -> Optional[Dict[str, Any]]:
        """Get user's watchlist"""
        try:
            logger.debug(f"Getting watchlist for user_id: {user_id}, list_name: {list_name}")
            
            watchlist = await self.watchlists.find_one({
                "user_id": str(user_id),
                "name": list_name
            })
            
            if not watchlist:
                logger.debug(f"Creating new watchlist for user_id: {user_id}")
                watchlist = {
                    "user_id": str(user_id),
                    "name": list_name,
                    "symbols": [],
                    "created_at": datetime.utcnow().isoformat(),
                    "last_updated": datetime.utcnow().isoformat()
                }
                try:
                    await self.watchlists.insert_one(watchlist)
                    logger.debug("New watchlist created successfully")
                except Exception as insert_error:
                    logger.error(f"Error creating watchlist: {str(insert_error)}")
                    return {"symbols": []}
            
            # Ensure the watchlist has a symbols field
            if "symbols" not in watchlist:
                watchlist["symbols"] = []
            
            return watchlist
        except Exception as e:
            logger.exception(f"Error getting watchlist for user_id {user_id}: {str(e)}")
            return {"symbols": []}

    async def init_collections(self):
        try:
            # Drop the entire collection to remove all indexes
            await self.db.drop_collection(app_settings.STOCK_HISTORY_COLLECTION)
            
            # Create the collection
            collection = await self.db.create_collection(app_settings.STOCK_HISTORY_COLLECTION)
            
            # Create a compound index on symbol and date
            await collection.create_index(
                [("symbol", 1), ("date", 1)],
                unique=True,
                name="idx_history_symbol_date_unique"
            )
            
            # Create a simple index on symbol for faster lookups
            await collection.create_index(
                [("symbol", 1)],
                name="idx_history_symbol"
            )
            
            logger.info("Stock history collection and indexes initialized")
            
        except Exception as e:
            logger.error(f"Error initializing collections: {str(e)}")
            raise 