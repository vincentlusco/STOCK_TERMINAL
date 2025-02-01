from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, List
from ..models import StockData, User, UserInDB
from ..stock_service import StockService
from ..auth import get_current_user

router = APIRouter(prefix="/api/stock", tags=["stocks"])

@router.get("/{symbol}")
async def get_stock(symbol: str, current_user: UserInDB = Depends(get_current_user)):
    try:
        stock_service = StockService()
        return await stock_service.get_stock_data(symbol)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{symbol}/chart")
async def get_stock_chart(
    symbol: str, 
    period: str = "6mo", 
    current_user: UserInDB = Depends(get_current_user)
):
    try:
        stock_service = StockService()
        return await stock_service.get_stock_history(symbol, period)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 