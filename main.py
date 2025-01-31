from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, Optional
import yfinance as yf
from app.db_service import DatabaseService
from app.models import User, WatchList
import jwt
from datetime import datetime, timedelta

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database service
db_service = DatabaseService()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# JWT settings
SECRET_KEY = "your-secret-key"  # Change this in production!
ALGORITHM = "HS256"

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

# Stock data endpoints
@app.get("/stock/{ticker}")
async def get_stock_data(ticker: str, current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    try:
        # First check cache
        cached_data = await db_service.get_stock_data(ticker)
        if cached_data:
            return cached_data

        # If not in cache, fetch from yfinance
        stock = yf.Ticker(ticker)
        info = stock.info
        
        if not info:
            raise HTTPException(status_code=404, detail=f"No data found for ticker {ticker}")
            
        # Format the response
        stock_data = {
            "symbol": ticker.upper(),
            "company_name": info.get("longName", "N/A"),
            "current_price": info.get("currentPrice") or info.get("regularMarketPrice", 0),
            "previous_close": info.get("previousClose", 0),
            "open": info.get("open", 0),
            "day_high": info.get("dayHigh", 0),
            "day_low": info.get("dayLow", 0),
            "volume": info.get("volume", 0),
            "market_cap": info.get("marketCap", 0),
            "pe_ratio": info.get("trailingPE", None),
            "fifty_two_week_high": info.get("fiftyTwoWeekHigh", 0),
            "fifty_two_week_low": info.get("fiftyTwoWeekLow", 0)
        }
        
        # Cache the data
        await db_service.store_stock_data(stock_data)
        
        return stock_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Watchlist endpoints
@app.get("/watchlist")
async def get_watchlist(current_user: User = Depends(get_current_user)):
    watchlist = await db_service.get_watchlist(str(current_user.id))
    if not watchlist:
        return {"symbols": []}
    return {"symbols": watchlist.symbols}

@app.post("/watchlist/add/{ticker}")
async def add_to_watchlist(ticker: str, current_user: User = Depends(get_current_user)):
    success = await db_service.add_to_watchlist(str(current_user.id), ticker)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to add to watchlist")
    return {"message": f"Added {ticker} to watchlist"}

@app.delete("/watchlist/remove/{ticker}")
async def remove_from_watchlist(ticker: str, current_user: User = Depends(get_current_user)):
    success = await db_service.remove_from_watchlist(str(current_user.id), ticker)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to remove from watchlist")
    return {"message": f"Removed {ticker} from watchlist"}

# Helper functions
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=7)  # Token expires in 7 days
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
        
    user = await db_service.get_user(username)
    if user is None:
        raise credentials_exception
    return user