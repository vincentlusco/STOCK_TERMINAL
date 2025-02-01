from datetime import datetime, timedelta
from typing import Optional, List, Dict
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from bson import ObjectId
from pydantic import validator

class UserBase(BaseModel):
    username: str
    email: EmailStr

class UserCreate(UserBase):
    password: str

class UserInDB(UserBase):
    id: str
    hashed_password: str
    watchlists: List[str] = []
    created_at: datetime = datetime.utcnow()

    class Config:
        from_attributes = True

class User(UserBase):
    id: str
    watchlists: List[str] = []
    created_at: datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class StockBase(BaseModel):
    symbol: str

class StockData(BaseModel):
    symbol: str
    company_name: Optional[str] = None
    current_price: float
    price_change: float
    price_change_percent: float
    previous_close: float
    volume: int
    market_cap: float
    timestamp: datetime = datetime.utcnow()

    class Config:
        from_attributes = True

class StockHistory(BaseModel):
    symbol: str
    dates: List[str]
    prices: List[float]
    volumes: List[int]
    period: str
    last_updated: datetime

    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None,
            ObjectId: str
        }
    )

class WatchlistItem(BaseModel):
    symbol: str
    added_at: datetime

class WatchlistAdd(BaseModel):
    """Model for adding a stock to watchlist"""
    symbol: str

class WatchlistRemove(BaseModel):
    """Model for removing a stock from watchlist"""
    symbol: str

class WatchlistResponse(BaseModel):
    """Model for watchlist response"""
    stocks: List[StockData]
    message: Optional[str] = None

    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None,
            ObjectId: str
        }
    )

class WatchList(BaseModel):
    user_id: str
    name: str = "Default"
    symbols: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None,
            ObjectId: str
        },
        arbitrary_types_allowed=True,
        validate_assignment=True
    )

    def dict(self, *args, **kwargs):
        d = super().dict(*args, **kwargs)
        # Ensure all fields are properly serialized
        d['user_id'] = str(d['user_id'])
        d['name'] = str(d['name'])
        d['symbols'] = list(d.get('symbols', []))
        if d.get('created_at'):
            d['created_at'] = self.created_at.isoformat()
        if d.get('last_updated'):
            d['last_updated'] = self.last_updated.isoformat()
        return d

class StockCache(BaseModel):
    """Model for cached stock data"""
    symbol: str
    data: StockData
    history: Optional[StockHistory]
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    ttl: datetime = Field(default_factory=lambda: datetime.utcnow() + timedelta(minutes=5))

    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None,
            ObjectId: str
        },
        arbitrary_types_allowed=True
    )

class StockResponse(BaseModel):
    data: StockData
    message: Optional[str] = None

class ErrorResponse(BaseModel):
    detail: str

    def dict(self, *args, **kwargs):
        d = super().dict(*args, **kwargs)
        return {
            "username": d["username"],
            "email": d["email"],
            "watchlists": d.get("watchlists", [])
        } 