import asyncio
import uvicorn
from app.config import init_mongodb, close_mongodb
from app.settings import settings
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def startup():
    """Initialize services on startup"""
    logger.info("Starting up services...")
    logger.info(f"Using MongoDB URI: {settings.MONGO_URI}")
    
    try:
        # Initialize MongoDB
        await init_mongodb()
        logger.info("Services started successfully")
    except Exception as e:
        logger.error(f"Error during startup: {str(e)}")
        raise

async def shutdown():
    """Cleanup on shutdown"""
    try:
        await close_mongodb()
        logger.info("Services shut down successfully")
    except Exception as e:
        logger.error(f"Error during shutdown: {str(e)}")
        raise

if __name__ == "__main__":
    try:
        # Run startup tasks
        asyncio.run(startup())
        
        # Start the server
        uvicorn.run(
            "app.main:app",
            host=settings.HOST,
            port=settings.PORT,
            reload=True,
            log_level="info"
        )
    finally:
        # Run shutdown
        asyncio.run(shutdown()) 