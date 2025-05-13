from fastapi import APIRouter, File, Form, Request, HTTPException, Depends, UploadFile
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
import jwt
from db.getdb import get_db
from db.models import User
from sqlalchemy.orm import Session
from db.models import AdminUser
router = APIRouter()

# Basic user model for request/response
class UserCreate(BaseModel):
    username: str
    password: str
    name : str
    contact : str
    address : str | None = None
    speciality : str | None = None
    required_needs : str | None = None
    last_location : str | None = None
    fcm_token : str | None = None

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
            password=user.password,
            name = user.name,
            contact = user.contact,
            address = user.address,
            speciality = user.speciality,
            required_needs = user.required_needs,
            last_location = user.last_location,
            fcm_token = user.fcm_token
                # In production, use proper password hashing!
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        return {
            "status": "success",
            "message": "User registered successfully",
            "user_id": new_user.id,
            "user" : new_user
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from pydantic import BaseModel

class LoginRequest(BaseModel):
    username: str
    password: str
    last_location : str | None = None
    fcm_token : str | None = None
@router.post("/auth/login")
def login(data : LoginRequest, db: Session = Depends(get_db)):
    try:
        # Find user
        user = db.query(User).filter(User.username == data.username).first()
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        if not user or user.password != data.password:  # In production, use proper password verification!
            raise HTTPException(status_code=401, detail="Invalid credentials")

        # Create access token
        access_token = create_access_token(
            data={"sub": user.username, "user_id": user.id}
        )
        db.query(User).filter(User.id == user.id).update({"last_location": data.last_location, "last_location_updated_at": datetime.utcnow(), "fcm_token": data.fcm_token})
        db.commit()
        print(data)
        return {
            "status": "success",
            "access_token": access_token,
            "token_type": "bearer",
            "user_id": user.id,
            "user" : user,
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


class AdminRegisterSchema(BaseModel):
    name : str
    username: str
    password: str
    official_id: str
    role: str
    city: str
    email : str
    contact: str
    is_organization: str
    location_cordinate: str
    fcm_token : str | None = None
class AdminLoginSchema(BaseModel):
    username: str
    password: str
    fcm_token : str | None = None
@router.post("/admin/register")
def register_admin(data: AdminRegisterSchema, db: Session = Depends(get_db)):
    existing_user = db.query(AdminUser).filter(AdminUser.username == data.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")

    user = AdminUser(
        name = data.name,
        username=data.username,
        password=data.password,  # In production, hash the password!
        official_id=data.official_id,
        role=data.role,
        city=data.city,
        email=data.email,
        contact=data.contact,
        is_organization=str(data.is_organization).lower(),
        location_cordinate=data.location_cordinate,
        fcm_token = data.fcm_token
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"message": "Admin registered successfully", "user_id": user.id}


@router.post("/admin/login")
def login_admin(data: AdminLoginSchema, db: Session = Depends(get_db)):
    user = db.query(AdminUser).filter(AdminUser.username == data.username).first()
    if not user or not data.password == user.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    db.query(AdminUser).filter(AdminUser.id == user.id).update({"fcm_token": data.fcm_token})
    db.commit()
    return {"message": "Login successful","user" : user}

@router.get("/admin/all") 
def get_all_admins(db: Session = Depends(get_db)):
    admins = db.query(AdminUser).all()
    return admins
