from functools import lru_cache
import os
from dotenv import load_dotenv
import logging
from pathlib import Path
from typing import List

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

class Settings:
    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEV_MODE: bool = os.getenv("DEV_MODE", "true").lower() == "true"
    NGROK_AUTH_TOKEN: str = os.getenv("NGROK_AUTH_TOKEN", "")
    MONGO_URI: str = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    DB_NAME: str = os.getenv("DB_NAME", "bloomberg_lite")
    STOCKS_COLLECTION: str = "stocks"
    STOCK_HISTORY_COLLECTION: str = "stock_history"
    USERS_COLLECTION: str = "users"
    WATCHLIST_COLLECTION: str = "watchlists"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    CORS_ORIGINS: list = ["*"]
    CORS_METHODS: list = ["*"]
    CORS_HEADERS: list = ["*"]

    def log_settings(self) -> None:
        """Log all settings values"""
        settings_dict = {attr: getattr(self, attr) 
                        for attr in dir(self) 
                        if not attr.startswith('_') and 
                        not callable(getattr(self, attr))}
        
        # Mask sensitive values
        for key in ['SECRET_KEY', 'NGROK_AUTH_TOKEN']:
            if key in settings_dict and settings_dict[key]:
                settings_dict[key] = f"{str(settings_dict[key])[:8]}..."
        
        logger.info("Settings loaded with values:")
        for key, value in sorted(settings_dict.items()):
            logger.info(f"{key}: {value}")

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()

# Create and export settings instance
settings = get_settings()
settings.log_settings()

# Export all settings as module-level variables
HOST = settings.HOST
PORT = settings.PORT
DEV_MODE = settings.DEV_MODE
NGROK_AUTH_TOKEN = settings.NGROK_AUTH_TOKEN
MONGO_URI = settings.MONGO_URI
DB_NAME = settings.DB_NAME
STOCKS_COLLECTION = settings.STOCKS_COLLECTION
STOCK_HISTORY_COLLECTION = settings.STOCK_HISTORY_COLLECTION
USERS_COLLECTION = settings.USERS_COLLECTION
WATCHLIST_COLLECTION = settings.WATCHLIST_COLLECTION
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
CORS_ORIGINS = settings.CORS_ORIGINS
CORS_METHODS = settings.CORS_METHODS
CORS_HEADERS = settings.CORS_HEADERS 