import yfinance as yf
from pydantic import BaseModel
from typing import Optional, Dict
import logging
import asyncio
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class StockData(BaseModel):
    symbol: str
    company_name: str
    current_price: float
    previous_close: float
    open: float
    day_high: float
    day_low: float
    volume: int
    market_cap: float
    pe_ratio: Optional[float] = None
    fifty_two_week_high: float
    fifty_two_week_low: float

class StockService:
    def __init__(self):
        self.cache: Dict[str, tuple[StockData, datetime]] = {}
        self.cache_duration = timedelta(minutes=15)

    async def get_stock_data(self, symbol: str) -> Optional[StockData]:
        try:
            # Check cache first
            logger.info(f"Getting stock data for {symbol}")
            if symbol in self.cache:
                data, timestamp = self.cache[symbol]
                if datetime.now() - timestamp < self.cache_duration:
                    logger.info(f"Cache hit for {symbol}")
                    return data
                
            logger.info(f"Cache miss for {symbol}, fetching from Yahoo")
            
            # Use yfinance to get stock data
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            if not info:
                logger.error(f"No data found for {symbol}")
                return None

            # Create StockData object
            stock_data = StockData(
                symbol=symbol,
                company_name=info.get('longName', 'N/A'),
                current_price=info.get('currentPrice', info.get('regularMarketPrice', 0.0)),
                previous_close=info.get('previousClose', 0.0),
                open=info.get('open', info.get('regularMarketOpen', 0.0)),
                day_high=info.get('dayHigh', info.get('regularMarketDayHigh', 0.0)),
                day_low=info.get('dayLow', info.get('regularMarketDayLow', 0.0)),
                volume=info.get('volume', info.get('regularMarketVolume', 0)),
                market_cap=info.get('marketCap', 0),
                pe_ratio=info.get('trailingPE'),
                fifty_two_week_high=info.get('fiftyTwoWeekHigh', 0.0),
                fifty_two_week_low=info.get('fiftyTwoWeekLow', 0.0)
            )

            # Cache the result
            self.cache[symbol] = (stock_data, datetime.now())
            return stock_data

        except Exception as e:
            logger.error(f"Error fetching stock data for {symbol}: {str(e)}")
            return None

    async def get_stock_history(self, symbol: str, period: str = "1y"):
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period)
            
            if df.empty:
                return None
                
            return df.reset_index().to_dict('records')
            
        except Exception as e:
            logger.error(f"Error fetching stock history for {symbol}: {str(e)}")
            return None

# Create a single instance of the service
stock_service = StockService() 