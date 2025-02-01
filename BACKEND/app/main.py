from fastapi import FastAPI, HTTPException, Depends, status, Body
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
import os
from typing import Dict, Any, Optional, List
import yfinance as yf
from app.db_service import DatabaseService
from app.models import User, WatchList, UserInDB
from app.auth import get_current_user, router as auth_router
from app.settings import settings
from datetime import datetime, timedelta
import pandas as pd
from .stock_service import get_stock_data, get_stock_chart_data
from .stock_service import StockService
import logging

logger = logging.getLogger(__name__)

app = FastAPI()

# Add CORS middleware with settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=settings.CORS_METHODS,
    allow_headers=settings.CORS_HEADERS,
)

# Mount static files
app.mount("/static", StaticFiles(directory="../FRONTEND/static"), name="static")

# Get MongoDB connection string from environment variable or use default
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")

# Initialize database service
db_service = DatabaseService(connection_string=MONGODB_URI)

# Initialize stock service
stock_service = StockService(db_service)

# Include the auth router
app.include_router(auth_router)

# JWT settings
SECRET_KEY = "your-secret-key"  # Change this in production!
ALGORITHM = "HS256"

# Route handlers for HTML pages
@app.get("/")
async def read_root():
    return FileResponse("../FRONTEND/static/html/index.html")

@app.get("/login")
async def read_login():
    return FileResponse("../FRONTEND/static/html/login.html")

@app.get("/register")
async def read_register():
    return FileResponse("../FRONTEND/static/html/register.html")

@app.get("/quote")
async def read_quote():
    return FileResponse("../FRONTEND/static/html/quote.html")

@app.get("/watchlist")
async def read_watchlist_page():
    return FileResponse("../FRONTEND/static/html/watchlist.html")

# Authentication endpoints
@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    if not await db_service.verify_password(form_data.username, form_data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    
    # Create access token
    access_token = create_access_token(data={"sub": form_data.username})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/register")
async def register(username: str, email: str, password: str):
    try:
        user = await db_service.create_user(username, email, password)
        return {"message": "User created successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# API Endpoints
@app.get("/api/user/profile")
async def get_user_profile(current_user: UserInDB = Depends(get_current_user)):
    return {
        "username": current_user.username,
        "email": current_user.email,
        "watchlists": current_user.watchlists
    }

@app.get("/api/stock/{ticker}")
async def get_stock_data(ticker: str, current_user: UserInDB = Depends(get_current_user)):
    try:
        return await stock_service.get_stock_data(ticker)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stock/{ticker}/chart")
async def get_stock_chart(ticker: str, period: str = "6mo", current_user: UserInDB = Depends(get_current_user)):
    try:
        return await stock_service.get_stock_chart_data(ticker, period)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/watchlist/data")
async def get_watchlist_data(current_user: User = Depends(get_current_user)):
    try:
        watchlist = await db_service.get_watchlist(str(current_user.id))
        if watchlist is None:
            return []
            
        stock_data = []
        for symbol in watchlist.get('symbols', []):
            data = await get_stock_data(symbol)
            if data:
                stock_data.append(data)
        return stock_data
    except Exception as e:
        logger.exception(f"Error in get_watchlist_data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Watchlist endpoints
@app.get("/watchlist")
async def get_watchlist(current_user: UserInDB = Depends(get_current_user)):
    watchlist = await db_service.get_watchlist(str(current_user.id))
    if not watchlist:
        return {"symbols": []}
    return {"symbols": watchlist.symbols}

@app.post("/api/watchlist/add")
async def add_to_watchlist(
    symbol: str = Body(..., embed=True),
    current_user: User = Depends(get_current_user)
):
    try:
        if not symbol:
            raise HTTPException(status_code=400, detail="Symbol is required")
            
        success = db_service.add_to_watchlist(str(current_user.id), symbol)
        if success:
            return {"message": f"Added {symbol} to watchlist"}
        else:
            raise HTTPException(status_code=500, detail="Failed to add to watchlist")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/watchlist/remove")
async def remove_from_watchlist(
    symbol: str = Body(..., embed=True),
    current_user: User = Depends(get_current_user)
):
    try:
        if not symbol:
            raise HTTPException(status_code=400, detail="Symbol is required")
            
        success = db_service.remove_from_watchlist(str(current_user.id), symbol)
        if success:
            return {"message": f"Removed {symbol} from watchlist"}
        else:
            raise HTTPException(status_code=500, detail="Failed to remove from watchlist")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Helper functions
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=7)  # Token expires in 7 days
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

@app.get("/api/stock/{symbol}")
async def get_stock(symbol: str):
    try:
        data = await get_stock_data(symbol)
        if data:
            return data
        raise HTTPException(status_code=404, detail="Stock not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stock/{symbol}/chart")
async def get_stock_chart(symbol: str, period: str = "6mo"):
    try:
        data = await get_stock_chart_data(symbol, period)
        if data:
            return data
        raise HTTPException(status_code=404, detail="Chart data not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))