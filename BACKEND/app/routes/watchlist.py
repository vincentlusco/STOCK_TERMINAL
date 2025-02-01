from fastapi import APIRouter, Depends, HTTPException, Body
from typing import List
from ..models import User, UserInDB, WatchlistResponse
from ..auth import get_current_user
from ..db_service import DatabaseService

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])

@router.get("/", response_model=WatchlistResponse)
async def get_watchlist(current_user: UserInDB = Depends(get_current_user)):
    db_service = DatabaseService()
    watchlist = await db_service.get_watchlist(str(current_user.id))
    if not watchlist:
        return WatchlistResponse(stocks=[], message="No watchlist found")
    return WatchlistResponse(stocks=watchlist.get("symbols", []))

@router.post("/add")
async def add_to_watchlist(
    symbol: str = Body(..., embed=True),
    current_user: User = Depends(get_current_user)
):
    db_service = DatabaseService()
    success = await db_service.add_to_watchlist(str(current_user.id), symbol)
    if success:
        return {"message": f"Added {symbol} to watchlist"}
    raise HTTPException(status_code=500, detail="Failed to add to watchlist")

@router.delete("/remove")
async def remove_from_watchlist(
    symbol: str = Body(..., embed=True),
    current_user: User = Depends(get_current_user)
):
    db_service = DatabaseService()
    success = await db_service.remove_from_watchlist(str(current_user.id), symbol)
    if success:
        return {"message": f"Removed {symbol} from watchlist"}
    raise HTTPException(status_code=500, detail="Failed to remove from watchlist") 