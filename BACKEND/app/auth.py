import os
from dotenv import load_dotenv
import logging
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
from typing import Optional
from fastapi import FastAPI
from fastapi.routing import APIRouter
from pydantic import BaseModel
from .database import get_mongo_db
from .models import User, UserInDB, Token, TokenData
from . import settings as app_settings  # Import settings directly
from .db_service import DatabaseService

# Load environment variables
load_dotenv(override=True)

# Use settings directly
SECRET_KEY = app_settings.SECRET_KEY
ALGORITHM = app_settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = app_settings.ACCESS_TOKEN_EXPIRE_MINUTES

logger = logging.getLogger(__name__)
logger.info(f"auth.py: Loaded SECRET_KEY from environment: {SECRET_KEY[:10]}...")

# Set up router
router = APIRouter()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Token model
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

# Auth functions
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Generate password hash"""
    return pwd_context.hash(password)

async def get_user(username: str) -> Optional[UserInDB]:
    """Get user from database"""
    try:
        db = get_mongo_db()
        user_dict = await db[app_settings.USERS_COLLECTION].find_one({"username": username})
        if user_dict:
            return UserInDB(**user_dict)
        return None
    except Exception as e:
        logger.error(f"Error getting user: {str(e)}")
        return None

async def authenticate_user(username: str, password: str) -> Optional[UserInDB]:
    """Authenticate user"""
    try:
        user = await get_user(username)
        if not user:
            return None
        if not pwd_context.verify(password, user.hashed_password):
            return None
        return user
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        return None

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, app_settings.SECRET_KEY, algorithm=app_settings.ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserInDB:
    """Get current user from token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, app_settings.SECRET_KEY, algorithms=[app_settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    mongo_db = get_mongo_db()
    user = await mongo_db.users.find_one({"username": username})
    if user is None:
        raise credentials_exception
    return UserInDB(**user)

# Routes
@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """Login endpoint"""
    user = await authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=app_settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/register", response_model=User)
async def register_user(user: User):
    """Register new user"""
    try:
        db = get_mongo_db()
        
        # Check if username exists
        if await db[app_settings.USERS_COLLECTION].find_one({"username": user.username}):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already registered"
            )
            
        # Check if email exists
        if await db[app_settings.USERS_COLLECTION].find_one({"email": user.email}):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
            
        # Create user
        user_in_db = UserInDB(
            username=user.username,
            email=user.email,
            hashed_password=pwd_context.hash(user.password),
            created_at=datetime.utcnow(),
            watchlists=[]
        )
        
        await db[app_settings.USERS_COLLECTION].insert_one(user_in_db.dict())
        
        return User(
            username=user.username,
            email=user.email,
            password="",
            created_at=user_in_db.created_at
        )
        
    except Exception as e:
        logger.error(f"Error registering user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error registering user"
        )

@router.get("/api/validate-token")
async def validate_token(current_user: UserInDB = Depends(get_current_user)):
    """Validate token"""
    return {"valid": True, "username": current_user.username} 