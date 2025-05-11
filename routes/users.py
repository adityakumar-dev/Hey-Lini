from fastapi import APIRouter, Depends, HTTPException, Form, File, UploadFile
from sqlalchemy.orm import Session
from typing import List, Dict
router = APIRouter()
from db.getdb import get_db
from db.models import User
from pydantic import BaseModel
class EmergencyContactInput(BaseModel):
    user_id: int
    emergency_contacts: List[Dict[str, str]]

@router.post("/user/add/emergency")
def add_emergency_contacts(data: EmergencyContactInput, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == data.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Save JSON list
    user.emergency_contacts = data.emergency_contacts
    db.commit()

    return {"status": "success", "message": "Contacts saved"}
@router.get("/user/get/emergency/{user_id}")
def get_emergency_contacts(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"emergency_contacts": user.emergency_contacts}