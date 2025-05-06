from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
import jwt
from db.getdb import get_db
from db.models import User
from sqlalchemy.orm import Session

router = APIRouter()

# Basic user model for request/response
class UserCreate(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    user_id: str
    username: str

# JWT settings (you should move these to a config file later)
SECRET_KEY = "my_secret_key"  # Change this in production!
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

@router.post("/auth/register")
def register(user: UserCreate, db: Session = Depends(get_db)):
    try:
        # Check if user already exists
        existing_user = db.query(User).filter(User.username == user.username).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="Username already registered")

        # Create new user (in production, hash the password!)
        new_user = User(
            username=user.username,
            password=user.password  # In production, use proper password hashing!
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        return {
            "status": "success",
            "message": "User registered successfully",
            "user_id": new_user.id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/auth/login")
def login(user: UserCreate, db: Session = Depends(get_db)):
    try:
        # Find user
        user = db.query(User).filter(User.username == user.username).first()
        if not user or user.password != user.password:  # In production, use proper password verification!
            raise HTTPException(status_code=401, detail="Invalid credentials")

        # Create access token
        access_token = create_access_token(
            data={"sub": user.username, "user_id": user.id}
        )

        return {
            "status": "success",
            "access_token": access_token,
            "token_type": "bearer",
            "user_id": user.id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/auth/me")
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user = db.query(User).filter(User.username == username).first()
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        
        return {
            "status": "success",
            "user_id": user.id,
            "username": user.username
        }
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))