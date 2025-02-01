import asyncio
import uvicorn
from app.config import init_mongodb, close_mongodb
from app import settings as app_settings
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def startup():
    """Initialize services on startup"""
    try:
        logger.info("Starting up services...")
        logger.info(f"Using MongoDB URI: {app_settings.MONGO_URI}")
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
    config = uvicorn.Config(
        "app.main:app",
        host=app_settings.HOST,
        port=app_settings.PORT,
        reload=True
    )
    server = uvicorn.Server(config)
    
    # Run startup
    asyncio.run(startup())
    
    try:
        # Start server
        server.run()
    finally:
        # Run shutdown
        asyncio.run(shutdown()) 