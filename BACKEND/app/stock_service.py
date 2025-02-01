import yfinance as yf
from datetime import datetime, timedelta
from .database import get_mongo_db
from .config import settings
import logging
import asyncio
import pandas as pd
from typing import Optional, Dict, List, Any
from motor.motor_asyncio import AsyncIOMotorDatabase
from .db_service import DatabaseService
from . import settings as app_settings
from fastapi import HTTPException
from pymongo import UpdateOne
from pymongo.errors import BulkWriteError
from .models import StockData
import os

# Configure logging
logging.basicConfig(level=logging.DEBUG)  # Changed to DEBUG for more details
logger = logging.getLogger(__name__)

# Use settings for MongoDB configuration
MONGODB_URI = app_settings.MONGO_URI
logger.info(f"Initializing DatabaseService with URI: {MONGODB_URI}")

# Initialize database service
db_service = None

async def init_db_service():
    global db_service
    if db_service is None:
        db_service = DatabaseService(MONGODB_URI)
        await db_service.ensure_initialized()
    return db_service

class StockService:
    def __init__(self, db_service=None):
        self.db_service = db_service
        self._cache_lock = asyncio.Lock()
        self._batch_size = 10  # For bulk operations
        self._cache_ttl = 300  # 5 minutes in seconds
        logger.info("StockService initialized")

    async def ensure_db_service(self):
        if self.db_service is None:
            self.db_service = await init_db_service()

    async def get_stock_data(self, symbol: str) -> Dict[str, Any]:
        await self.ensure_db_service()
        try:
            # Check cache first
            cached_data = await self.db_service.get_stock_data(symbol)
            if cached_data and (datetime.now() - cached_data.get('lastUpdated', datetime.min)).seconds < self._cache_ttl:
                return cached_data

            # Fetch from yfinance if not cached or expired
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            if not info:
                raise HTTPException(status_code=404, detail=f"No data found for {symbol}")

            stock_data = {
                "symbol": symbol.upper(),
                "company_name": info.get("longName", ""),
                "current_price": float(info.get("currentPrice", 0) or info.get("regularMarketPrice", 0)),
                "price_change": float(info.get("regularMarketChange", 0)),
                "price_change_percent": float(info.get("regularMarketChangePercent", 0)),
                "previous_close": float(info.get("previousClose", 0)),
                "open": float(info.get("regularMarketOpen", 0)),
                "day_high": float(info.get("regularMarketDayHigh", 0)),
                "day_low": float(info.get("regularMarketDayLow", 0)),
                "volume": int(info.get("regularMarketVolume", 0)),
                "market_cap": float(info.get("marketCap", 0)),
                "pe_ratio": float(info.get("trailingPE", 0) or 0),
                "fifty_two_week_high": float(info.get("fiftyTwoWeekHigh", 0)),
                "fifty_two_week_low": float(info.get("fiftyTwoWeekLow", 0)),
                "lastUpdated": datetime.now()
            }

            # Add error handling for NaN values
            for key, value in stock_data.items():
                if isinstance(value, float) and pd.isna(value):
                    stock_data[key] = 0.0

            # Cache the data
            try:
                await self.db_service.store_stock_data(stock_data)
            except Exception as cache_error:
                logger.warning(f"Cache error (non-critical): {str(cache_error)}")

            return stock_data

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error fetching stock data for {symbol}: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    async def get_stock_chart_data(self, symbol: str, period: str = "6mo") -> Dict[str, Any]:
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period)
            
            if hist.empty:
                raise HTTPException(status_code=404, detail=f"No chart data found for {symbol}")
            
            chart_data = {
                "dates": hist.index.strftime('%Y-%m-%d').tolist(),
                "opens": hist['Open'].round(2).tolist(),
                "highs": hist['High'].round(2).tolist(),
                "lows": hist['Low'].round(2).tolist(),
                "prices": hist['Close'].round(2).tolist(),
                "volumes": hist['Volume'].tolist()
            }
            
            return chart_data

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error fetching chart data for {symbol}: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    async def get_batch_stock_data(self, tickers: List[str]) -> Dict[str, StockData]:
        """Efficiently fetch multiple stocks"""
        results = {}
        tasks = []
        
        if not tickers:
            logger.debug("No tickers provided for batch stock data")
            return results
        
        # Filter out invalid symbols
        valid_tickers = [t.strip().upper() for t in tickers if t and isinstance(t, str)]
        if len(valid_tickers) != len(tickers):
            logger.warning(f"Filtered out {len(tickers) - len(valid_tickers)} invalid tickers")
        
        logger.debug(f"Fetching batch stock data for tickers: {tickers}")
        
        try:
            for chunk in [valid_tickers[i:i + self._batch_size] for i in range(0, len(valid_tickers), self._batch_size)]:
                logger.debug(f"Processing chunk: {chunk}")
                for ticker in chunk:
                    tasks.append(asyncio.create_task(self.get_stock_data(ticker)))
                
                completed = await asyncio.gather(*tasks, return_exceptions=True)
                
                for ticker, result in zip(chunk, completed):
                    if isinstance(result, Exception):
                        logger.error(f"Failed to fetch {ticker}: {result}")
                        results[ticker] = None
                    elif result:
                        results[ticker] = result
                
                tasks = []  # Clear tasks for next chunk
            
            logger.debug(f"Batch processing complete. Results for {len(results)} tickers")
            return results
        except Exception as e:
            logger.exception(f"Error in batch stock data processing: {str(e)}")
            return results

    async def get_stock_history(self, symbol: str, period: str = '6mo'):
        try:
            logger.info(f"Getting history for {symbol} with period {period}")
            
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period)
            
            if df.empty:
                logger.error(f"No historical data found for {symbol}")
                raise HTTPException(status_code=404, detail=f"No historical data found for {symbol}")
            
            # Format the data for the chart
            history_data = {
                "dates": df.index.strftime('%Y-%m-%d').tolist(),
                "opens": df['Open'].round(2).tolist(),
                "highs": df['High'].round(2).tolist(),
                "lows": df['Low'].round(2).tolist(),
                "prices": df['Close'].round(2).tolist(),
                "volumes": df['Volume'].tolist()
            }
            
            # Validate data before returning
            if not all(len(history_data[key]) == len(history_data['dates']) 
                      for key in ['opens', 'highs', 'lows', 'prices', 'volumes']):
                raise ValueError("Data arrays have mismatched lengths")
            
            return history_data

        except Exception as e:
            logger.error(f"Error fetching stock history for {symbol}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error fetching stock history: {str(e)}"
            )

# Initialize global stock service
stock_service = StockService()

# These functions are for backward compatibility
async def get_stock_data(symbol: str) -> Dict[str, Any]:
    return await stock_service.get_stock_data(symbol)

async def get_stock_chart_data(symbol: str, period: str = "6mo") -> Dict[str, Any]:
    return await stock_service.get_stock_chart_data(symbol)

def format_market_cap(market_cap: float) -> str:
    """
    Format market cap value to human readable string (e.g., 1.5T, 234.5B)
    """
    try:
        if market_cap >= 1e12:
            return f"${market_cap/1e12:.2f}T"
        elif market_cap >= 1e9:
            return f"${market_cap/1e9:.2f}B"
        elif market_cap >= 1e6:
            return f"${market_cap/1e6:.2f}M"
        else:
            return f"${market_cap:.2f}"
    except Exception as e:
        logger.error(f"Error formatting market cap: {str(e)}")
        return "N/A"

def format_volume(volume: int) -> str:
    """
    Format volume value to human readable string
    """
    try:
        if volume >= 1e9:
            return f"{volume/1e9:.2f}B"
        elif volume >= 1e6:
            return f"{volume/1e6:.2f}M"
        elif volume >= 1e3:
            return f"{volume/1e3:.2f}K"
        else:
            return str(volume)
    except Exception as e:
        logger.error(f"Error formatting volume: {str(e)}")
        return "N/A"

# Log when module is loaded
logger.info("Stock service initialized") 