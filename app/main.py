from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from .stock_service import StockService
from .config import init_mongodb, close_mongodb
from .db_service import DatabaseService
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional
import os
import logging
from .models import User  # Add this at the top with other imports
from pydantic import BaseModel
import plotly.graph_objects as go
from time import time
import asyncio
import pandas as pd

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
    global db_service
    logger.info("Starting application...")
    try:
        logger.info("Initializing MongoDB connection...")
        await init_mongodb()
        logger.info("MongoDB initialized successfully")
        
        logger.info("Creating database service...")
        db_service = DatabaseService()
        logger.info("Database service created")
        
        logger.info("Initializing stock service...")
        stock_service.init_db_service(db_service)
        logger.info("Stock service initialized")
        
        logger.info("Application startup complete")
    except Exception as e:
        logger.error(f"Startup failed: {str(e)}")
        raise

@app.on_event("shutdown")
async def shutdown_db_client():
    await close_mongodb()

# Add these constants at the top
SECRET_KEY = "your-secret-key-here"  # Change this!
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Add these new functions
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = await db_service.get_user(username)
    if user is None:
        raise credentials_exception
    return user

@app.get("/")
async def root():
    return FileResponse(os.path.join(static_dir, "index.html"))

@app.get("/quote")
async def quote_page(request: Request):
    # For HTML requests, let the client-side handle auth
    if request.headers.get("accept", "").startswith("text/html"):
        return FileResponse(os.path.join(static_dir, "quote.html"))
    
    # For API requests, check auth header
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        scheme, token = auth_header.split()
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid authentication scheme")
        await get_current_user(token)
    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return FileResponse(os.path.join(static_dir, "quote.html"))

@app.get("/watchlist")
async def get_watchlist(request: Request):
    # Check if this is an HTML request or API request
    accept_header = request.headers.get("accept", "")
    is_api_request = "application/json" in accept_header
    
    if not is_api_request:
        return FileResponse(os.path.join(static_dir, "watchlist.html"))
    
    # For API requests, get user from request state (set by auth middleware)
    current_user = getattr(request.state, "user", None)
    if not current_user:
        logger.error("No user found in request state")
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    try:
        logger.info(f"Getting watchlist for user: {current_user.username}")
        logger.debug(f"Request headers: {request.headers}")
        
        watchlist = await db_service.get_watchlist(str(current_user.id))
        if watchlist:
            watchlist_dict = watchlist.dict()
            logger.info(f"Found watchlist data: {watchlist_dict}")
            return JSONResponse(
                content=watchlist_dict,
                headers={
                    "Content-Type": "application/json",
                    "Cache-Control": "no-cache"
                }
            )
        
        # Create default watchlist if none exists
        logger.info(f"Creating default watchlist for user: {current_user.username}")
        watchlist = await db_service.create_watchlist(str(current_user.id))
        return JSONResponse(
            content=watchlist.dict(),
            headers={
                "Content-Type": "application/json",
                "Cache-Control": "no-cache"
            }
        )
    except Exception as e:
        logger.error(f"Error getting watchlist: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stock/{ticker}")
async def get_stock_data(ticker: str, request: Request):
    try:
        logger.info(f"Fetching stock data for {ticker}")
        data = await stock_service.get_stock_data(ticker)
        if not data:
            logger.error(f"No data found for ticker {ticker}")
            raise HTTPException(status_code=404, detail=f"No data found for {ticker}")
            
        logger.info(f"Successfully fetched data for {ticker}")
        return data
    except Exception as e:
        logger.error(f"Error fetching stock data for {ticker}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

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
    try:
        # Create the user
        user_obj = await db_service.create_user(
            username=user.username,
            email=user.email,
            password=user.password
        )
        # Create default watchlist
        await db_service.create_watchlist(str(user_obj.id))
        return {"message": "User created successfully"}
    except Exception as e:
        logger.error(f"Registration failed: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    try:
        if not await db_service.verify_password(form_data.username, form_data.password):
            raise HTTPException(
                status_code=401,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": form_data.username}, expires_delta=access_token_expires
        )
        
        # Get user info
        user = await db_service.get_user(form_data.username)
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "username": user.username,
            "redirect_url": "/quote"
        }
    except Exception as e:
        logger.error(f"Login failed: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
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

# Add these routes after your existing routes
@app.get("/login")
async def login_page():
    return FileResponse(os.path.join(static_dir, "login.html"))

@app.get("/register")
async def register_page():
    return FileResponse(os.path.join(static_dir, "register.html"))

@app.get("/api/user/profile")
async def get_user_profile(current_user: User = Depends(get_current_user)):
    return {
        "username": current_user.username,
        "email": current_user.email,
        "watchlists": current_user.watchlists
    }

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

# Serve static files last
app.mount("/static", StaticFiles(directory=static_dir), name="static")

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
    try:
        # Test MongoDB connection
        await mongo_client.admin.command('ping')
        collections = await db.list_collection_names()
        return {
            "status": "healthy",
            "mongodb": "connected",
            "collections": collections
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }

@app.middleware("http")
async def add_performance_headers(request: Request, call_next):
    start_time = time()
    response = await call_next(request)
    process_time = time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response 