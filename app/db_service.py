from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from .config import get_db
from .models import StockData, User, WatchList
from motor.motor_asyncio import AsyncIOMotorDatabase
import bcrypt
import logging
from bson import ObjectId

logger = logging.getLogger(__name__)

class DatabaseService:
    def __init__(self):
        try:
            self.db: AsyncIOMotorDatabase = get_db()
            logger.info("DatabaseService initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize DatabaseService: {str(e)}")
            raise

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

    async def create_user(self, username: str, email: str, password: str) -> User:
        """Create a new user with hashed password"""
        try:
            # Check if username or email already exists
            existing_user = await self.db.users.find_one({
                "$or": [
                    {"username": username},
                    {"email": email}
                ]
            })
            if existing_user:
                raise ValueError("Username or email already exists")
                
            # Hash password
            salt = bcrypt.gensalt()
            hashed = bcrypt.hashpw(password.encode(), salt)
            
            user = User(
                username=username,
                email=email,
                hashed_password=hashed.decode(),
                created_at=datetime.utcnow()
            )
            
            # Insert user into database
            result = await self.db.users.insert_one(user.dict())
            user.id = str(result.inserted_id)
            
            # Create default watchlist
            await self.create_watchlist(str(user.id))
            
            return user
        except Exception as e:
            logger.error(f"Error creating user: {str(e)}")
            raise

    async def get_user(self, username: str) -> Optional[User]:
        """Get user by username"""
        try:
            user_data = await self.db.users.find_one({"username": username})
            if user_data:
                return User(**user_data)
            return None
        except Exception as e:
            logger.error(f"Error getting user: {str(e)}")
            return None

    async def verify_password(self, username: str, password: str) -> bool:
        """Verify user password"""
        try:
            user = await self.get_user(username)
            if not user:
                return False
            return bcrypt.checkpw(
                password.encode(),
                user.hashed_password.encode()
            )
        except Exception as e:
            logger.error(f"Error verifying password: {str(e)}")
            return False

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

    async def add_to_watchlist(self, user_id: str, symbol: str, list_name: str = "Default") -> bool:
        """Add symbol to user's watchlist"""
        try:
            # First check if watchlist exists
            watchlist = await self.get_watchlist(user_id, list_name)
            if not watchlist:
                logger.info(f"Creating new watchlist for user {user_id}")
                watchlist = await self.create_watchlist(user_id, list_name)

            # Add symbol to watchlist
            result = await self.db.watchlists.update_one(
                {"user_id": str(user_id), "name": list_name},
                {
                    "$addToSet": {"symbols": symbol.upper()},
                    "$currentDate": {"last_updated": True}
                }
            )
            
            success = result.modified_count > 0 or result.matched_count > 0
            if success:
                logger.info(f"Added {symbol} to watchlist for user {user_id}")
            else:
                logger.error(f"Failed to add {symbol} to watchlist for user {user_id}")
            return success
        except Exception as e:
            logger.error(f"Error adding to watchlist: {str(e)}")
            return False

    async def remove_from_watchlist(self, user_id: str, symbol: str, list_name: str = "Default") -> bool:
        """Remove symbol from user's watchlist"""
        try:
            result = await self.db.watchlists.update_one(
                {"user_id": str(user_id), "name": list_name},
                {
                    "$pull": {"symbols": symbol.upper()},
                    "$currentDate": {"last_updated": True}
                }
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error removing from watchlist: {str(e)}")
            return False 