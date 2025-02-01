import yfinance as yf
from datetime import datetime, timedelta
from .models import StockData, StockHistory
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

logger = logging.getLogger(__name__)

class StockService:
    def __init__(self):
        """Initialize StockService"""
        self.db_service = None
        self.db = None
        self._cache_lock = asyncio.Lock()
        self._batch_size = 10  # For bulk operations
        logger.info("StockService initialized")

    def set_db_service(self, db_service):
        """Set the database service instance"""
        if db_service is not None:  # Proper None check
            self.db_service = db_service
            self.db = db_service.db
            logger.info("Database service set for StockService")

    async def init_db(self) -> None:
        """Initialize database connection"""
        try:
            if self.db is None:  # Proper None check
                self.db = await get_mongo_db()
                logger.info("StockService initialized with MongoDB connection")
        except Exception as e:
            logger.error(f"Failed to initialize StockService: {str(e)}")
            raise

    async def get_stock_data(self, symbol: str):
        try:
            if self.db is None:
                await self.init_db()

            collection = self.db[app_settings.STOCKS_COLLECTION]
            stock_data = await collection.find_one({"symbol": symbol})
            
            if stock_data is None or (datetime.now() - stock_data.get('timestamp', datetime.min)).seconds > 300:
                logger.info(f"Fetching {symbol} data from yfinance")
                ticker = yf.Ticker(symbol)
                
                try:
                    info = ticker.info
                    if not info:
                        raise HTTPException(status_code=404, detail=f"Stock data not found for {symbol}")
                    
                    # Get current price and calculate changes
                    current_price = info.get("regularMarketPrice", 0)
                    previous_close = info.get("previousClose", 0)
                    price_change = current_price - previous_close if current_price and previous_close else 0
                    price_change_percent = (price_change / previous_close * 100) if previous_close else 0
                    
                    stock_data = {
                        "symbol": symbol,
                        "company_name": info.get("longName", ""),
                        "current_price": float(current_price),
                        "price_change": float(price_change),
                        "price_change_percent": float(price_change_percent),
                        "previous_close": float(previous_close),
                        "volume": int(info.get("regularMarketVolume", 0)),
                        "market_cap": float(info.get("marketCap", 0)),
                        "timestamp": datetime.utcnow()
                    }
                    
                    await collection.update_one(
                        {"symbol": symbol},
                        {"$set": stock_data},
                        upsert=True
                    )
                    
                    return StockData(**stock_data)
                    
                except Exception as e:
                    logger.error(f"Error processing data for {symbol}: {str(e)}")
                    raise HTTPException(
                        status_code=500,
                        detail=f"Error processing stock data: {str(e)}"
                    )
            
            # Convert database data to StockData object
            stock_dict = {
                "symbol": stock_data.get("symbol"),
                "company_name": stock_data.get("company_name", ""),
                "current_price": float(stock_data.get("current_price", 0)),
                "price_change": float(stock_data.get("price_change", 0)),
                "price_change_percent": float(stock_data.get("price_change_percent", 0)),
                "previous_close": float(stock_data.get("previous_close", 0)),
                "volume": int(stock_data.get("volume", 0)),
                "market_cap": float(stock_data.get("market_cap", 0)),
                "timestamp": stock_data.get("timestamp", datetime.utcnow())
            }
            return StockData(**stock_dict)
        
        except Exception as e:
            logger.error(f"Unexpected error fetching stock data for {symbol}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Unexpected error fetching stock data: {str(e)}"
            )

    async def get_batch_stock_data(self, tickers: List[str]) -> Dict[str, StockData]:
        """Efficiently fetch multiple stocks"""
        results = {}
        tasks = []
        
        for chunk in [tickers[i:i + self._batch_size] for i in range(0, len(tickers), self._batch_size)]:
            for ticker in chunk:
                tasks.append(asyncio.create_task(self.get_stock_data(ticker)))
            
            completed = await asyncio.gather(*tasks, return_exceptions=True)
            
            for ticker, result in zip(chunk, completed):
                if isinstance(result, Exception):
                    logger.error(f"Failed to fetch {ticker}: {result}")
                elif result:
                    results[ticker] = result
        
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
                "opens": df['Open'].tolist(),
                "highs": df['High'].tolist(),
                "lows": df['Low'].tolist(),
                "closes": df['Close'].tolist(),
                "volumes": df['Volume'].tolist()
            }
            
            return history_data

        except Exception as e:
            logger.error(f"Error fetching stock history for {symbol}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error fetching stock history: {str(e)}"
            ) 