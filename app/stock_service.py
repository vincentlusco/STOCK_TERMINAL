import yfinance as yf
from datetime import datetime, timedelta
from .models import StockData, StockHistory
from .config import get_db
import logging
import asyncio
import pandas as pd
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)

class StockService:
    def __init__(self):
        self.db = None
        self._cache_lock = asyncio.Lock()
        self._batch_size = 10  # For bulk operations

    def init_db_service(self, db_service):
        self.db = get_db()

    async def get_stock_data(self, ticker: str) -> Optional[StockData]:
        """Get stock data with optimized caching"""
        async with self._cache_lock:  # Prevent race conditions
            try:
                logger.info(f"Getting stock data for {ticker}")
                
                # Check cache first
                cached = await self.db.stocks.find_one({
                    "symbol": ticker.upper(),
                    "last_updated": {"$gt": datetime.utcnow() - timedelta(minutes=5)}
                })
                
                if cached:
                    logger.info(f"Cache hit for {ticker}")
                    # Access the nested data structure
                    if 'data' in cached:
                        return StockData(**cached['data'])
                    else:
                        logger.warning(f"Cached data for {ticker} is malformed, fetching fresh data")
                        # If cache is malformed, continue to fetch fresh data

                # Fetch fresh data
                logger.info(f"Cache miss for {ticker}, fetching from Yahoo")
                stock = yf.Ticker(ticker)
                info = await asyncio.to_thread(lambda: stock.info)  # Run in thread pool
                
                if not info:
                    logger.error(f"No data returned from Yahoo Finance for {ticker}")
                    return None

                try:
                    stock_data = StockData(
                        symbol=ticker.upper(),
                        company_name=info.get("longName", "N/A"),
                        current_price=float(info.get("currentPrice", 0.0)),
                        previous_close=float(info.get("previousClose", 0.0)),
                        open=float(info.get("open", 0.0)),
                        day_high=float(info.get("dayHigh", 0.0)),
                        day_low=float(info.get("dayLow", 0.0)),
                        volume=int(info.get("volume", 0)),
                        market_cap=float(info.get("marketCap", 0)),
                        pe_ratio=float(info.get("trailingPE", 0)) if info.get("trailingPE") else None,
                        fifty_two_week_high=float(info.get("fiftyTwoWeekHigh", 0)) if info.get("fiftyTwoWeekHigh") else None,
                        fifty_two_week_low=float(info.get("fiftyTwoWeekLow", 0)) if info.get("fiftyTwoWeekLow") else None,
                        last_updated=datetime.utcnow()
                    )

                    # Cache the data
                    await self.db.stocks.update_one(
                        {"symbol": ticker.upper()},
                        {
                            "$set": {
                                "data": stock_data.dict(),
                                "symbol": ticker.upper(),
                                "last_updated": datetime.utcnow()
                            }
                        },
                        upsert=True
                    )

                    return stock_data

                except (ValueError, TypeError) as e:
                    logger.error(f"Error parsing Yahoo Finance data for {ticker}: {str(e)}")
                    return None

            except Exception as e:
                logger.error(f"Error fetching stock data for {ticker}: {str(e)}")
                raise

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

    async def get_stock_history(self, ticker: str, period: str = "1y") -> Optional[StockHistory]:
        """Get historical stock data with MongoDB caching"""
        try:
            logger.info(f"Getting history for {ticker} with period {period}")
            
            # Check MongoDB cache first
            cached_history = await self.db.stock_history.find_one({
                "symbol": ticker.upper(),
                "last_updated": {"$gt": datetime.utcnow() - timedelta(hours=24)}
            })

            if cached_history:
                logger.info(f"Found cached history for {ticker}")
                return StockHistory(**cached_history)

            # Fetch fresh data from Yahoo Finance
            logger.info(f"Fetching fresh history for {ticker} from Yahoo Finance")
            stock = yf.Ticker(ticker)
            history = await asyncio.to_thread(lambda: stock.history(period=period))

            if history.empty:
                logger.error(f"No historical data found for ticker {ticker}")
                return None

            logger.info(f"Got {len(history)} data points for {ticker}")
            
            # Convert to list of dictionaries with proper date formatting
            history_data = []
            for index, row in history.iterrows():
                # Convert timezone-aware datetime to string
                date_str = index.strftime('%Y-%m-%d')
                history_data.append({
                    "date": date_str,
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": int(row["Volume"])
                })

            # Create StockHistory object
            stock_history = StockHistory(
                symbol=ticker.upper(),
                data=history_data,
                last_updated=datetime.utcnow()
            )

            # Store in MongoDB
            await self.db.stock_history.update_one(
                {"symbol": ticker.upper()},
                {"$set": stock_history.dict()},
                upsert=True
            )

            logger.info(f"Successfully stored history for {ticker}")
            return stock_history

        except Exception as e:
            logger.error(f"Error fetching stock history for {ticker}: {str(e)}")
            raise 