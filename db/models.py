from sqlalchemy import JSON, Boolean, Column, ForeignKey, Integer, String, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base
from sqlalchemy.orm import Session

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    contact = Column(String, nullable=False)
    name = Column(String, nullable=False)
    last_location = Column(String, nullable=True)
    required_needs = Column(String, nullable=True)
    speciality = Column(String, nullable=True)
    address = Column(String, nullable=True)
    fcm_token = Column(String, nullable=True)
    is_track_me = Column(Boolean, nullable=False, default=False)
    need_help = Column(Boolean, nullable=False, default=False)
    # [{"name" : "", "contact" :""}]
    emergency_contacts = Column(JSON, nullable=True)  # List of emergency contacts
    created_at = Column(DateTime, default=datetime.utcnow)
    last_location_updated_at = Column(DateTime, default=datetime.utcnow)

class UserQuestions(Base):
    __tablename__ = "user_questions"

    user_id = Column(Integer, primary_key=True)
    question_answer = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class QuestionRecordTrack(Base):
    __tablename__ = "question_record_track"
    periodic_time = Column(Integer, nullable=False)
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    question_answer = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Conversation(Base):
    __tablename__ = "conversations"

    conversation_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    history = Column(JSON, nullable=False, default=list)  # List of interactions, each interaction is a list of messages
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User")
    
class AdminUser(Base):
    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)  
    username = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    official_id = Column(String, unique=True, nullable=False)
    role = Column(String, nullable=False)
    city = Column(String, nullable=False)
    contact = Column(String, nullable=False)
    fcm_token = Column(String, nullable=True)
    email = Column(String, unique=True, nullable=True)
    location_cordinate = Column(String, nullable=False)
    is_organization = Column(String, nullable=False) 
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AdminNotification(Base):
    __tablename__ = "admin_notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer,  nullable=False)
    role = Column(String, nullable=False)
    name = Column(String, nullable=False)  # Name of the user
    contact = Column(String, nullable=False)  # Contact of the user
    action_taken_by = Column(String, nullable=True)  # Username of the admin who took action
    action_taken_at = Column(DateTime, default=datetime.utcnow, nullable=True)
    action_details = Column(String, nullable=True)  # Details of the action taken
    coordinate = Column(String, nullable=True)  # Coordinates related to the notification
    notification = Column(String, nullable=True)
    last_admin_coordinate = Column(String, nullable=True)  # Last known coordinates of the admin
    completed_time = Column(DateTime, nullable=True)  # Time when the notification was completed
    status = Column(String, nullable=False)  # 'read', 'unread'
    admin_image_path = Column(String, nullable=True)  # Image related to the notification
    user_image_path = Column(String, nullable=True)  # Image related to the user
    user_voice_path = Column(String, nullable=True)  # Voice recording related to the user
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
