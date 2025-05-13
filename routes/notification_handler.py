import os
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from datetime import datetime
from db.getdb import get_db
from db.models import AdminNotification, User
from sqlalchemy.orm import Session
import mimetypes

router = APIRouter()

class AcknowledgeSchema(BaseModel):
    id: int
    username: str

def get_file_type(file: UploadFile) -> str:
    """Determine if the file is an image or voice file based on MIME type"""
    content_type = file.content_type.lower()
    if content_type.startswith('image/'):
        return 'image'
    elif content_type.startswith('audio/'):
        return 'voice'
    return 'unknown'

@router.post("/notify")
def send_notification(
    user_id: int = Form(...),
    role: str = Form(...),
    coordinate: str = Form(...),
    notification: str = Form(...),
    status: str = Form(...),
    name: str = Form(...),
    contact: str = Form(...),
    file: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    # Create separate directories for images and voice files
    os.makedirs("uploads/images", exist_ok=True)
    os.makedirs("uploads/voice", exist_ok=True)
    
    image_path = None
    voice_path = None
    
    if file:
        file_type = get_file_type(file)
        if file_type == 'image':
            image_path = f"uploads/images/{file.filename}"
            with open(image_path, "wb") as f:
                f.write(file.file.read())
        elif file_type == 'voice':
            voice_path = f"uploads/voice/{file.filename}"
            with open(voice_path, "wb") as f:
                f.write(file.file.read())
        else:
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Only image and voice files are allowed."
            )

    note = AdminNotification(
        user_id=user_id,
        role=role,
        coordinate=coordinate,
        notification=notification,
        status=status,
        user_image_path=image_path,
        user_voice_path=voice_path,
        name=name,
        contact=contact,
    )
    
    db.add(note)
    db.commit()
    db.refresh(note)
    user = db.query(User).filter(User.id == user_id).first()
    user.last_location = coordinate
    db.commit()
    return {"message": "Notification sent successfully"}

@router.get("/notify/all")
def get_all_notifications(db: Session = Depends(get_db)):
    notifications = db.query(AdminNotification).all()
    return notifications

@router.post("/notification/acknowledge")
def acknowledge_notification(data: AcknowledgeSchema, db: Session = Depends(get_db)):
    notif = db.query(AdminNotification).filter(AdminNotification.id == data.id).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    notif.action_taken_by = data.username
    notif.action_taken_at = datetime.utcnow()
    notif.status = "read"

    db.commit()
    return {"status": "success", "message": "Notification acknowledged"}

@router.post("/notification/complete")
def complete_notification(
    notification_id: int = Form(...),
    last_admin_coordinate: str = Form(...),
    action_details: str = Form(...),
    image_file: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    notif = db.query(AdminNotification).filter(AdminNotification.id == notification_id).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    notif.last_admin_coordinate = last_admin_coordinate
    notif.action_details = action_details
    notif.status = "completed"
    notif.completed_time = datetime.utcnow()
    if image_file:
        image_path = f"static/evidence/{notification_id}_{image_file.filename}"
        with open(image_path, "wb") as f:
            f.write(image_file.file.read())
        notif.admin_image_path = image_path

    db.commit()
    return {"status": "success", "message": "Notification completed"}

@router.get('/notify/file/{notification_id}')
async def get_notification_file(notification_id: int, file_type: str, db: Session = Depends(get_db)):
    """
    Get a file associated with a notification.
    file_type should be either 'image' or 'voice'
    """
    notification = db.query(AdminNotification).filter(AdminNotification.id == notification_id).first()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    file_path = None
    if file_type == 'image':
        file_path = notification.user_image_path
    elif file_type == 'voice':
        file_path = notification.user_voice_path
    else:
        raise HTTPException(status_code=400, detail="Invalid file type. Must be either 'image' or 'voice'")

    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=file_path,
        filename=os.path.basename(file_path),
        media_type=mimetypes.guess_type(file_path)[0] or 'application/octet-stream'
    ) 