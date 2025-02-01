from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from .config import get_db
from .models import StockData, User, WatchList, UserInDB, UserCreate
from motor.motor_asyncio import AsyncIOMotorDatabase, AsyncIOMotorClient
import bcrypt
import logging
from bson import ObjectId
from databases import Database
from pydantic import BaseModel
from .settings import settings as app_settings
from .database import get_mongo_db  # Change this line
from pymongo.errors import OperationFailure

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

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
    def __init__(self):
        """Initialize DatabaseService"""
        self.db: Optional[AsyncIOMotorDatabase] = None
        self.users = None
        self.stocks = None
        self.watchlists = None
        self.client: Optional[AsyncIOMotorClient] = None

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

    async def store_stock_data(self, data: StockData) -> bool:
        """Store stock data with TTL index"""
        try:
            # Add expiration time (e.g., 5 minutes)
            expiration = datetime.utcnow() + timedelta(minutes=5)
            data_dict = data.dict()
            data_dict['expiration'] = expiration
            
            result = await self.db.stocks.update_one(
                {"symbol": data.symbol},
                {"$set": data_dict},
                upsert=True
            )
            return result.modified_count > 0 or result.upserted_id is not None
        except Exception as e:
            logger.error(f"Error storing stock data: {str(e)}")
            return False

    async def get_stock_data(self, symbol: str) -> Optional[StockData]:
        """Get stock data if it exists and is not stale"""
        try:
            data = await self.db.stocks.find_one({
                "symbol": symbol.upper(),
                "expiration": {"$gt": datetime.utcnow()}
            })
            if data:
                return StockData(**data)
            return None
        except Exception as e:
            logger.error(f"Error retrieving stock data: {str(e)}")
            return None

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

    async def verify_password(self, username: str, password: str) -> bool:
        """Verify user password"""
        try:
            from passlib.context import CryptContext
            pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
            
            user = await self.get_user(username)
            if not user:
                return False
                
            return pwd_context.verify(password, user.hashed_password)
            
        except Exception as e:
            logger.error(f"Error verifying password: {str(e)}")
            return False

    async def create_user(self, user: UserCreate) -> UserInDB:
        """Create new user"""
        try:
            if not self.db:
                await self.connect()

            # Check if username exists
            existing_user = await self.db[app_settings.USERS_COLLECTION].find_one(
                {"username": user.username}
            )
            if existing_user:
                raise ValueError("Username already exists")

            # Hash password
            from passlib.context import CryptContext
            pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
            hashed_password = pwd_context.hash(user.password)

            # Create user document
            user_dict = {
                "username": user.username,
                "email": user.email,
                "hashed_password": hashed_password,
                "created_at": datetime.utcnow(),
                "watchlists": [],
                "id": str(ObjectId())
            }
            del user_dict["password"]

            # Insert into database
            result = await self.db[app_settings.USERS_COLLECTION].insert_one(user_dict)
            
            if result.inserted_id:
                user_dict["id"] = str(result.inserted_id)
                return UserInDB(**user_dict)
            return None

        except Exception as e:
            logger.error(f"Error creating user: {str(e)}")
            raise

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

    async def get_watchlist(self, user_id: str, list_name: str = "Default") -> Optional[WatchList]:
        """Get user's watchlist"""
        try:
            watchlist_data = await self.db.watchlists.find_one({
                "user_id": str(user_id),
                "name": list_name
            })
            if watchlist_data:
                return WatchList(**watchlist_data)
            return None
        except Exception as e:
            logger.error(f"Error getting watchlist: {str(e)}")
            return None

    async def get_user_watchlist(self, username: str) -> List[str]:
        """Get user's watchlist"""
        try:
            # First get the user
            user = await self.get_user(username)
            if not user:
                logger.error(f"User {username} not found")
                return []

            # Get watchlist document
            watchlist_doc = await self.watchlists.find_one({"user_id": str(user.id)})
            
            if watchlist_doc:
                # Check if it's using the old format with 'symbols' array
                if "symbols" in watchlist_doc:
                    return watchlist_doc["symbols"]
                # Check if it's using the new format with 'symbol' field
                elif "symbol" in watchlist_doc:
                    return [watchlist_doc["symbol"]]
                else:
                    logger.warning(f"Invalid watchlist format: {watchlist_doc}")
                    return []
            
            logger.info(f"No watchlist found for user {username}")
            return []

        except Exception as e:
            logger.error(f"Error getting watchlist for user {username}: {str(e)}")
            return []

    async def add_to_watchlist(self, username: str, symbol: str) -> bool:
        """Add a symbol to user's watchlist"""
        try:
            user = await self.get_user(username)
            if not user:
                logger.error(f"User {username} not found")
                return False

            # Add symbol to the symbols array
            result = await self.watchlists.update_one(
                {"user_id": str(user.id)},
                {
                    "$addToSet": {
                        "symbols": symbol.upper()
                    },
                    "$set": {
                        "last_updated": datetime.utcnow().isoformat()
                    },
                    "$setOnInsert": {
                        "user_id": str(user.id),
                        "name": "Default",
                        "created_at": datetime.utcnow().isoformat()
                    }
                },
                upsert=True
            )
            
            logger.info(f"Added {symbol} to watchlist for user {username}")
            return True

        except Exception as e:
            logger.error(f"Error adding {symbol} to watchlist: {str(e)}")
            return False

    async def remove_from_watchlist(self, username: str, symbol: str) -> bool:
        """Remove a symbol from user's watchlist"""
        try:
            user = await self.get_user(username)
            if not user:
                logger.error(f"User {username} not found")
                return False

            # Remove symbol from the symbols array
            result = await self.watchlists.update_one(
                {"user_id": str(user.id)},
                {
                    "$pull": {
                        "symbols": symbol.upper()
                    },
                    "$set": {
                        "last_updated": datetime.utcnow().isoformat()
                    }
                }
            )
            
            success = result.modified_count > 0
            if success:
                logger.info(f"Removed {symbol} from watchlist for user {username}")
            else:
                logger.warning(f"Symbol {symbol} not found in watchlist for user {username}")
            return success

        except Exception as e:
            logger.error(f"Error removing {symbol} from watchlist: {str(e)}")
            return False

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

async def get_user_by_id(db: Database, user_id: int) -> Optional[User]:
    try:
        query = """
        SELECT id, username, email
        FROM users
        WHERE id = :user_id
        """
        user = await db.fetch_one(query=query, values={"user_id": user_id})
        if user:
            return User(
                id=user['id'],
                username=user['username'],
                email=user['email']
            )
        return None
    except Exception as e:
        logger.error(f"Error getting user: {str(e)}")
        return None

async def get_user_watchlist(db: Database, user_id: int) -> List[str]:
    try:
        query = """
        SELECT symbol
        FROM watchlist
        WHERE user_id = :user_id
        """
        results = await db.fetch_all(query=query, values={"user_id": user_id})
        return [row['symbol'] for row in results]
    except Exception as e:
        logger.error(f"Error getting watchlist: {str(e)}")
        return []

async def add_to_watchlist(db: Database, user_id: int, symbol: str) -> bool:
    try:
        query = """
        INSERT INTO watchlist (user_id, symbol)
        VALUES (:user_id, :symbol)
        ON CONFLICT (user_id, symbol) DO NOTHING
        """
        await db.execute(query=query, values={"user_id": user_id, "symbol": symbol})
        return True
    except Exception as e:
        logger.error(f"Error adding to watchlist: {str(e)}")
        return False

async def remove_from_watchlist(db: Database, user_id: int, symbol: str) -> bool:
    try:
        query = """
        DELETE FROM watchlist
        WHERE user_id = :user_id AND symbol = :symbol
        """
        await db.execute(query=query, values={"user_id": user_id, "symbol": symbol})
        return True
    except Exception as e:
        logger.error(f"Error removing from watchlist: {str(e)}")
        return False 