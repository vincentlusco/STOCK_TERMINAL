from datetime import datetime, timedelta
from typing import Optional, List
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from bson import ObjectId
from pydantic import validator

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
    fifty_two_week_high: Optional[float] = None
    fifty_two_week_low: Optional[float] = None
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None,
            ObjectId: str
        },
        arbitrary_types_allowed=True
    )

    @validator('current_price', 'previous_close', 'open', 'day_high', 'day_low', 'market_cap', pre=True)
    def convert_to_float(cls, v):
        if isinstance(v, str):
            return float(v)
        return v

    @validator('volume', pre=True)
    def convert_to_int(cls, v):
        if isinstance(v, str):
            return int(v)
        return v

    def dict(self, *args, **kwargs):
        d = super().dict(*args, **kwargs)
        if d.get('last_updated'):
            d['last_updated'] = self.last_updated.isoformat()
        return d

class StockHistory(BaseModel):
    symbol: str
    data: List[dict]  # List of daily price data
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None,
            ObjectId: str
        }
    )

class User(BaseModel):
    id: Optional[str] = Field(default_factory=lambda: str(ObjectId()))
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    hashed_password: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    watchlists: List[str] = Field(default_factory=list)

    class Config:
        json_schema_extra = {
            "example": {
                "username": "johndoe",
                "email": "john@example.com",
                "password": "secretpassword"
            }
        }

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