from fastapi import FastAPI, HTTPException, Request, Depends, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from .stock_service import StockService
from .config import init_mongodb, close_mongodb, settings
from .db_service import DatabaseService, User as DBUser
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional, List
import os
import logging
from .models import User, WatchlistAdd, WatchlistRemove  # Add this at the top with other imports
from pydantic import BaseModel
import plotly.graph_objects as go
from time import time
import asyncio
import pandas as pd
from .services.stock_service import stock_service, StockData
from .database import get_mongo_db, get_sql_db  # Updated import
from databases import Database
from .auth import (
    authenticate_user,
    create_access_token,
    get_current_user,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    SECRET_KEY,
    validate_token,
    get_password_hash,
    router as auth_router
)
from fastapi import status
from dotenv import load_dotenv
from fastapi.templating import Jinja2Templates
from . import settings as app_settings  # Import as module
from motor.motor_asyncio import AsyncIOMotorClient

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Stock Terminal API")

# Get the absolute path to the static directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
static_dir = os.path.join(BASE_DIR, "static")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add middleware to log requests
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.debug(f"Incoming request: {request.method} {request.url}")
    logger.debug(f"Headers: {request.headers}")
    try:
        response = await call_next(request)
        logger.debug(f"Response status: {response.status_code}")
        return response
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        raise

# Create service instances at module level, but don't initialize DB connection yet
stock_service = StockService()
db_service = None

@app.on_event("startup")
async def startup_db_client():
    """Initialize database connection on startup"""
    try:
        logger.info("Starting application...")
        logger.info("Initializing MongoDB connection...")
        
        # Initialize MongoDB
        await init_mongodb()
        logger.info("MongoDB initialized successfully")
        
        # Create and initialize database service
        logger.info("Creating database service...")
        global db_service
        db_service = DatabaseService()
        await db_service.initialize()
        
        # Initialize stock service
        logger.info("Initializing stock service...")
        global stock_service
        stock_service = StockService()
        stock_service.set_db_service(db_service)
        logger.info("Stock service initialized successfully")
        
    except Exception as e:
        logger.error(f"Startup failed: {str(e)}")
        raise

@app.on_event("shutdown")
async def shutdown_db_client():
    await close_mongodb()
    await get_mongo_db().disconnect()

# Verify SECRET_KEY at startup
logger.info(f"main.py: Using SECRET_KEY from auth module: {SECRET_KEY[:10]}...")
if not SECRET_KEY or SECRET_KEY == "your-256-bit-secret":
    raise RuntimeError("Invalid SECRET_KEY, please check your .env file")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Mount static directories first
app.mount("/js", StaticFiles(directory="static/js"), name="js")
app.mount("/css", StaticFiles(directory="static/css"), name="css")

# Route handlers for HTML pages
@app.get("/")
async def read_root():
    return RedirectResponse(url="/login")

@app.get("/login")
async def read_login():
    return FileResponse("static/login.html")

@app.get("/register")
async def read_register():
    return FileResponse("static/register.html")

@app.get("/quote")
async def read_quote():
    return FileResponse("static/quote.html")

@app.get("/watchlist")
async def read_watchlist():
    return FileResponse("static/watchlist.html")

@app.get("/api/watchlist/data")
async def get_watchlist_data(current_user: User = Depends(get_current_user)):
    try:
        logger.info(f"Getting watchlist for user: {current_user.username}")
        # Get user's watchlist
        watchlist = await db_service.get_user_watchlist(current_user.username)
        
        # Get stock data for each symbol
        stocks = []
        for symbol in watchlist:
            try:
                stock_data = await stock_service.get_stock_data(symbol)
                if stock_data:
                    stocks.append(stock_data)
            except Exception as e:
                logger.error(f"Error fetching stock data for {symbol}: {str(e)}")
                continue
        
        logger.info(f"Returning watchlist with {len(stocks)} stocks")
        return {"stocks": stocks, "symbols": watchlist}
        
    except Exception as e:
        logger.error(f"Error getting watchlist: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stock/{symbol}")
async def get_stock_data(symbol: str):
    try:
        logger.info(f"Fetching stock data for {symbol}")
        if not stock_service:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Stock service not initialized"
            )
            
        stock_data = await stock_service.get_stock_data(symbol)
        if not stock_data:
            return {"message": f"No data found for symbol {symbol}"}
            
        return stock_data
    except Exception as e:
        logger.error(f"Error fetching stock data for {symbol}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@app.get("/stock/{ticker}/history")
async def get_stock_history(ticker: str):
    if not ticker or len(ticker) > 10:
        raise HTTPException(status_code=400, detail="Invalid ticker symbol")
    
    try:
        data = await stock_service.get_stock_history(ticker)
        return data
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

# Add OPTIONS handler for CORS preflight requests
@app.options("/stock/{ticker}")
async def options_stock(ticker: str):
    return JSONResponse(
        content={},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Headers": "*",
        }
    )

# Add this class for request validation
class UserCreate(BaseModel):
    username: str
    email: str
    password: str

# Update the register endpoint
@app.post("/register")
async def register_user(user: UserCreate):
    """Register a new user"""
    try:
        global db_service
        logger.info(f"Registration attempt for user: {user.username}")
        
        if db_service is None:
            error_msg = "Database service not initialized during registration"
            logger.error(error_msg)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_msg
            )

        # Check if user exists
        logger.info(f"Checking if user exists: {user.username}")
        try:
            existing_user = await db_service.get_user(user.username)
            if existing_user:
                error_msg = f"Username {user.username} already registered"
                logger.warning(error_msg)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error_msg
                )
        except Exception as e:
            error_msg = f"Error checking existing user: {str(e)}"
            logger.error(error_msg)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_msg
            )

        # Create new user
        try:
            logger.info("Creating password hash")
            hashed_password = get_password_hash(user.password)
            user_data = {
                "username": user.username,
                "email": user.email,
                "hashed_password": hashed_password
            }
            
            logger.info(f"Attempting to create user in database: {user.username}")
            success = await db_service.create_user(user_data)
            
            if not success:
                error_msg = "Failed to create user in database"
                logger.error(error_msg)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=error_msg
                )
                
            logger.info(f"Successfully created user: {user.username}")
            return {"message": "User created successfully", "username": user.username}
            
        except Exception as e:
            error_msg = f"Error creating user: {str(e)}"
            logger.error(error_msg)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_msg
            )
            
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Unexpected error during registration: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )

# Add Token model
class Token(BaseModel):
    access_token: str
    token_type: str

@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Login endpoint"""
    try:
        user = await authenticate_user(form_data.username, form_data.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
        access_token = create_access_token(
            data={"sub": user.username},
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        
        return {
            "access_token": access_token, 
            "token_type": "bearer",
            "redirect_url": "/quote"  # Add redirect URL to response
        }
        
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

# Add watchlist endpoints
@app.post("/watchlist/add/{symbol}")
async def add_to_watchlist(symbol: str, current_user: User = Depends(get_current_user)):
    try:
        success = await db_service.add_to_watchlist(str(current_user.id), symbol)
        if success:
            return {"message": f"Added {symbol} to watchlist"}
        raise HTTPException(status_code=400, detail="Failed to add to watchlist")
    except Exception as e:
        logger.error(f"Error adding to watchlist: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/watchlist/remove/{symbol}")
async def remove_from_watchlist(symbol: str, current_user: User = Depends(get_current_user)):
    success = await db_service.remove_from_watchlist(str(current_user.id), symbol)
    if success:
        return {"message": f"Removed {symbol} from watchlist"}
    raise HTTPException(status_code=400, detail="Failed to remove from watchlist")

class UserProfile(BaseModel):
    username: str
    email: Optional[str] = None
    watchlist: List[str] = []

@app.get("/api/user/profile", response_model=UserProfile)
async def get_user_profile(current_user: dict = Depends(get_current_user)):
    try:
        if isinstance(current_user, dict):
            username = current_user.get("username")
        else:
            username = current_user.username
            current_user = {"username": username, "email": getattr(current_user, "email", None)}
            
        watchlist = await db_service.get_user_watchlist(username)
        
        return UserProfile(
            username=username,
            email=current_user.get("email"),
            watchlist=watchlist
        )
    except Exception as e:
        logger.error(f"Error getting user profile: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@app.post("/watchlist/create")
async def create_watchlist(name: str, current_user: User = Depends(get_current_user)):
    try:
        watchlist = await db_service.create_watchlist(str(current_user.id), name)
        return watchlist
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/watchlist/{name}")
async def get_specific_watchlist(name: str, current_user: User = Depends(get_current_user)):
    watchlist = await db_service.get_watchlist(str(current_user.id), name)
    if watchlist:
        return watchlist
    raise HTTPException(status_code=404, detail="Watchlist not found")

# Add a new endpoint for stock charts
@app.get("/stock/{ticker}/chart", response_class=HTMLResponse)
async def get_stock_chart(
    ticker: str, 
    request: Request, 
    chart_type: str = "candlestick", 
    period: str = "1y",
    volume: bool = False,
    moving_average: bool = False,
    bollinger: bool = False,
    rsi: bool = False
):
    try:
        logger.info(f"Getting chart for {ticker} with type={chart_type}, period={period}")
        history = await stock_service.get_stock_history(ticker, period)
        
        if not history or not history.data:
            logger.error(f"No historical data found for {ticker}")
            raise HTTPException(status_code=404, detail=f"No historical data found for {ticker}")
        
        logger.info(f"Creating chart with {len(history.data)} data points")
        logger.debug(f"First data point: {history.data[0]}")  # Add this debug log
        
        # Create base figure
        fig = go.Figure()
        
        try:
            # Add main price data
            if chart_type == "line":
                dates = [d['date'] for d in history.data]
                closes = [d['close'] for d in history.data]
                
                fig.add_trace(go.Scatter(
                    x=dates,
                    y=closes,
                    mode='lines',
                    name='Close Price',
                    line=dict(color='#00ff00')
                ))
            elif chart_type == "candlestick":
                fig.add_trace(go.Candlestick(
                    x=[d['date'] for d in history.data],
                    open=[d['open'] for d in history.data],
                    high=[d['high'] for d in history.data],
                    low=[d['low'] for d in history.data],
                    close=[d['close'] for d in history.data],
                    increasing=dict(line=dict(color='#00ff00')),
                    decreasing=dict(line=dict(color='#ff4444'))
                ))
            
            # Add volume if requested
            if volume:
                fig.add_trace(go.Bar(
                    x=[d['date'] for d in history.data],
                    y=[d['volume'] for d in history.data],
                    name='Volume',
                    yaxis='y2',
                    marker_color='#454545'
                ))
            
            # Update layout
            layout_updates = {
                'title': f'{ticker} Stock Price',
                'yaxis_title': 'Price ($)',
                'template': 'plotly_dark',
                'plot_bgcolor': '#1a1a1a',
                'paper_bgcolor': '#1a1a1a',
                'font': dict(color='#00ff00'),
                'xaxis': dict(
                    rangeslider=dict(visible=True),
                    type='date',
                    gridcolor='#333333',
                    showgrid=True,
                    title_font=dict(color='#00ff00'),
                    tickfont=dict(color='#00ff00')
                ),
                'yaxis': dict(
                    gridcolor='#333333',
                    zerolinecolor='#333333',
                    showgrid=True,
                    title_font=dict(color='#00ff00'),
                    tickfont=dict(color='#00ff00'),
                    side='left'
                ),
                'margin': dict(l=50, r=50, t=50, b=50),
                'showlegend': True,
                'legend': dict(
                    bgcolor='#1a1a1a',
                    bordercolor='#333333',
                    borderwidth=1,
                    font=dict(color='#00ff00')
                ),
                'width': None,
                'height': 600,
                'autosize': True
            }
            
            if volume:
                layout_updates.update({
                    'yaxis2': dict(
                        title='Volume',
                        overlaying='y',
                        side='right',
                        showgrid=False,
                        title_font=dict(color='#454545'),
                        tickfont=dict(color='#454545')
                    )
                })
            
            fig.update_layout(**layout_updates)
            
            logger.info("Successfully created chart")
            html = fig.to_html(
                full_html=False,
                include_plotlyjs='cdn',
                config={
                    'displayModeBar': True,
                    'scrollZoom': True,
                    'modeBarButtonsToAdd': ['drawline', 'drawopenpath', 'eraseshape'],
                    'responsive': True,
                    'displaylogo': False,
                    'showLink': False
                }
            )
            
            logger.debug(f"Generated HTML length: {len(html)}")
            return HTMLResponse(content=html)
            
        except Exception as e:
            logger.error(f"Error creating chart: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error creating chart: {str(e)}")
            
    except Exception as e:
        logger.error(f"Error in chart endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stock/{symbol}/chart")
async def get_stock_chart_data(
    symbol: str,
    period: str = '6mo',
    current_user: User = Depends(get_current_user)
):
    """Get raw chart data for a stock"""
    try:
        logger.info(f"Getting chart data for {symbol} with period {period}")
        history = await stock_service.get_stock_history(symbol, period)
        
        if not history:
            raise HTTPException(status_code=404, detail=f"No historical data found for {symbol}")
            
        return history  # This already returns the correct JSON structure
        
    except Exception as e:
        logger.error(f"Error getting chart data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    protected_paths = ["/watchlist", "/quote", "/api"]
    current_path = request.url.path
    
    if any(current_path.startswith(path) for path in protected_paths):
        # Get the accept header and check if it's an API request
        accept_header = request.headers.get("accept", "")
        is_api_request = "application/json" in accept_header or current_path.startswith("/api")
        
        # Skip auth check for HTML requests to /quote and /watchlist
        if not is_api_request and current_path in ["/watchlist", "/quote"]:
            return await call_next(request)
            
        # Get auth header
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            logger.error(f"Missing auth header for API request to {current_path}")
            raise HTTPException(
                status_code=401,
                detail="Not authenticated",
                headers={"WWW-Authenticate": "Bearer"}
            )
            
        try:
            # Validate token
            scheme, token = auth_header.split()
            if scheme.lower() != "bearer":
                raise HTTPException(status_code=401, detail="Invalid authentication scheme")
                
            # Get user from token
            user = await get_current_user(token)
            # Add user to request state for later use
            request.state.user = user
            
            logger.debug(f"Successfully authenticated user {user.username} for {current_path}")
            
        except Exception as e:
            logger.error(f"Auth error for {current_path}: {str(e)}")
            raise HTTPException(
                status_code=401,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"}
            )
    
    response = await call_next(request)
    return response

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check MongoDB connection
        db = await get_mongo_db()
        await db.command("ping")
        
        # Check PostgreSQL connection
        sql_db = await get_sql_db()
        if not sql_db.is_connected:
            await sql_db.connect()
        
        return {
            "status": "healthy",
            "mongo": "connected",
            "postgres": "connected"
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "detail": str(e)
            }
        )

@app.middleware("http")
async def add_performance_headers(request: Request, call_next):
    start_time = time()
    response = await call_next(request)
    process_time = time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response 

# Add these models at the top with your other imports
class WatchlistItem(BaseModel):
    symbol: str

class WatchlistResponse(BaseModel):
    stocks: List[dict]

@app.post("/api/watchlist/add")
async def add_to_watchlist(
    data: WatchlistAdd,
    current_user: User = Depends(get_current_user)
):
    try:
        # Verify the stock exists
        stock_data = await stock_service.get_stock_data(data.symbol)
        if not stock_data:
            raise HTTPException(status_code=404, detail="Stock not found")
        
        # Add to watchlist
        success = await db_service.add_to_watchlist(current_user.username, data.symbol)
        if success:
            return {"message": f"Added {data.symbol} to watchlist"}
        else:
            raise HTTPException(status_code=400, detail="Failed to add to watchlist")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding to watchlist: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/watchlist/remove")
async def remove_from_watchlist(
    data: WatchlistRemove,
    current_user: User = Depends(get_current_user)
):
    try:
        success = await db_service.remove_from_watchlist(current_user.username, data.symbol)
        if success:
            return {"message": f"Removed {data.symbol} from watchlist"}
        else:
            raise HTTPException(status_code=400, detail="Failed to remove from watchlist")
            
    except Exception as e:
        logger.error(f"Error removing from watchlist: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/validate-token")
async def validate_token_endpoint(current_user: User = Depends(get_current_user)):
    """Endpoint to validate JWT token"""
    try:
        return {"valid": True, "username": current_user.username}
    except Exception as e:
        logger.error(f"Error validating token: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid token")

# Include routers
app.include_router(auth_router)

# Add NGROK tunnel in development mode
if app_settings.DEV_MODE and app_settings.NGROK_AUTH_TOKEN:
    from pyngrok import ngrok
    
    # Set up ngrok
    ngrok.set_auth_token(app_settings.NGROK_AUTH_TOKEN)
    
    # Open a tunnel
    public_url = ngrok.connect(app_settings.PORT)
    logger.info(f"\n* ngrok tunnel \"{public_url}\" -> \"http://localhost:{app_settings.PORT}\"") 