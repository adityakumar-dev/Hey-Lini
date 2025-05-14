from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Form, File, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Dict
router = APIRouter()
from db.getdb import get_db
from db.models import User, UserQuestions
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

class LocationUpdateInput(BaseModel):
    user_id: int
    location: str
@router.post("/user/update/location")
def update_location(data: LocationUpdateInput, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == data.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.last_location = data.location
    user.last_location_updated_at = datetime.utcnow()
    db.commit()
    return {"status": "success", "message": "Location updated"}



@router.get("/user/emergency/details/{user_id}")
def get_emergency_details(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.password = None
    return user

class QuestionAnswerInput(BaseModel):
    user_id: int
    question_answer: List[Dict[str, str]]

@router.post("/user/question")
def add_question_answer(data: QuestionAnswerInput, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == data.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Try to get existing question record
    user_question = db.query(UserQuestions).filter(UserQuestions.user_id == data.user_id).first()
    
    if user_question:
        # Update existing record
        user_question.question_answer = data.question_answer
    else:
        # Create new record
        user_question = UserQuestions(user_id=data.user_id, question_answer=data.question_answer)
        db.add(user_question)
    
    db.commit()
    return {"status": "success", "message": "Question answer updated"}

@router.get("/user/question/{user_id}")
def get_question_answer(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user_question = db.query(UserQuestions).filter(UserQuestions.user_id == user_id).first()
    if not user_question:
        raise HTTPException(status_code=404, detail="Question answer not found")
    
    return user_question.question_answer

