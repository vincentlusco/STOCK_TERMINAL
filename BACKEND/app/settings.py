from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field
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

# Define all settings at module level
HOST: str = os.getenv("HOST", "127.0.0.1")
PORT: int = int(os.getenv("PORT", "8000"))
DEV_MODE: bool = os.getenv("DEV_MODE", "true").lower() == "true"
NGROK_AUTH_TOKEN: str = os.getenv("NGROK_AUTH_TOKEN", "")

# Database Configuration
MONGO_HOST: str = os.getenv("MONGO_HOST", "localhost")
MONGO_PORT: int = int(os.getenv("MONGO_PORT", "27017"))
MONGO_URI: str = os.getenv("MONGO_URI", f"mongodb://{MONGO_HOST}:{MONGO_PORT}")
DB_NAME: str = os.getenv("DB_NAME", "bloomberg_lite")
DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://bloomberg_user:bloomberg123@localhost/bloomberg")

# Security Configuration
SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here")
ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

# MongoDB Collections
STOCKS_COLLECTION = "stocks"
USERS_COLLECTION = "users"
WATCHLIST_COLLECTION = "watchlists"
STOCK_HISTORY_COLLECTION = "stock_history"

# CORS Settings
CORS_ORIGINS: List[str] = os.getenv("CORS_ORIGINS", "*").split(",")
CORS_METHODS: List[str] = ["*"]
CORS_HEADERS: List[str] = ["*"]

def log_settings() -> None:
    """Log all settings values"""
    settings_dict = {k: v for k, v in globals().items() 
                    if not k.startswith('_') and k.isupper()}
    
    # Mask sensitive values
    for key in ['SECRET_KEY', 'NGROK_AUTH_TOKEN']:
        if key in settings_dict and settings_dict[key]:
            settings_dict[key] = f"{str(settings_dict[key])[:8]}..."
    
    logger.info("Settings loaded with values:")
    for key, value in sorted(settings_dict.items()):
        logger.info(f"{key}: {value}")

# Log settings on module import
log_settings()

class Settings(BaseSettings):
    """Application settings with Pydantic validation"""
    # Server Configuration
    HOST: str = Field(default="127.0.0.1")
    PORT: int = Field(default=8000)
    DEV_MODE: bool = Field(default=True)
    NGROK_AUTH_TOKEN: str = Field(default="")

    # Database Configuration
    MONGODB_URI: str = Field(default="mongodb://localhost:27017")
    DATABASE_NAME: str = Field(default="bloomberg_lite")
    STOCKS_COLLECTION: str = Field(default="stocks")
    STOCK_HISTORY_COLLECTION: str = Field(default="stock_history")
    USERS_COLLECTION: str = Field(default="users")
    WATCHLIST_COLLECTION: str = Field(default="watchlists")

    # Security Configuration
    SECRET_KEY: str = Field(default="your-secret-key-here")
    ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30)

    # CORS Settings
    CORS_ORIGINS: List[str] = Field(default=["*"])
    CORS_METHODS: List[str] = Field(default=["*"])
    CORS_HEADERS: List[str] = Field(default=["*"])

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # This will ignore extra fields in .env

    def log_settings(self) -> None:
        """Log all settings values"""
        settings_dict = self.model_dump()
        # Mask sensitive values
        for key in ['SECRET_KEY', 'NGROK_AUTH_TOKEN']:
            if key in settings_dict and settings_dict[key]:
                settings_dict[key] = f"{str(settings_dict[key])[:8]}..."
        
        logger.info("Settings loaded with values:")
        for key, value in settings_dict.items():
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
MONGODB_URI = settings.MONGODB_URI
DATABASE_NAME = settings.DATABASE_NAME
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

# Add these constants if they don't exist
USERS_COLLECTION = "users"
STOCKS_COLLECTION = "stocks"
WATCHLISTS_COLLECTION = "watchlists"
STOCK_HISTORY_COLLECTION = "stock_history" 