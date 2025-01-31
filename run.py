import uvicorn
from app.config import init_mongodb, close_mongodb, settings
import asyncio
from pyngrok import ngrok

async def startup():
    await init_mongodb()

async def shutdown():
    await close_mongodb()

if __name__ == "__main__":
    config = uvicorn.Config(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["app"],
        log_level="info"
    )
    
    # Set up ngrok tunnel if in dev mode
    if settings.DEV_MODE:
        # Set up ngrok tunnel
        ngrok.set_auth_token(settings.NGROK_AUTH_TOKEN)
        tunnel = ngrok.connect(8000)
        print(f"\n* ngrok tunnel \"{tunnel.public_url}\" -> \"http://localhost:8000\"\n")

    server = uvicorn.Server(config)
    
    # Add startup and shutdown events
    server.install_signal_handlers = lambda: None
    
    asyncio.run(startup())
    try:
        server.run()
    finally:
        asyncio.run(shutdown())
        if settings.DEV_MODE:
            ngrok.kill()  # Kill ngrok process on exit 