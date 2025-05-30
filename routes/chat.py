import os
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from db.getdb import get_db
from db.models import Conversation, User
from brain.model_active import ModelInit
from datetime import datetime
from typing import Dict, List, Optional
import json
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

class ChatRequest(BaseModel):
    user_id: str
    query: str
    is_voice: Optional[bool] = False
    is_websearch: Optional[bool] = False
    is_image_analysis: Optional[bool] = False
    conversation_id: str 
    files: Optional[List[UploadFile]] = None

model = ModelInit()

async def response_generator(history: List[Dict], db: Session, user_id: str, query: str, is_voice: bool, is_websearch: bool, is_image_analysis: bool, conversation_id: str, files: Optional[List[UploadFile]] = None,  image_path: Optional[str] = None):
    logger.info(f"Starting response for query: {query}")
    full_response = ""
    
    try:
        # Save user message first
        save_history(
            user_id=user_id,
            role="user",
            content=query,
            conversation_id=conversation_id,  # Fixed typo here
            db=db
        )
        # send metadata converstation to client

        # Generate response based on mode
        if is_voice:
            logger.info("Using voice response mode")
            generator = model.text_offline_response(
                query=query,
                history=history,
                is_voice=True
            )
        elif image_path:
            logger.info(f"Using image analysis mode with image: {image_path}")
            generator = model.image_offline_response(
                query=query,
                history=history,
                image_path=image_path
            )
        else:
            logger.info("Using standard text response mode")
            generator = model.text_offline_response(
                query=query,
                history=history,
                is_voice=False
            )

        # Stream the response
        async for chunk in generator:
            if chunk.startswith('[Error]') or chunk.startswith('[Exception]'):
                logger.error(f"Error from model: {chunk}")
                yield f"data: {chunk}\n\n"
                break  # Changed from return to break to ensure we save what we have
            
            logger.debug(f"Received chunk: {chunk}")
            try:
                chunk_data = json.loads(chunk.replace('data: ', ''))
                if 'content' in chunk_data:
                    full_response += chunk_data['content']
            except json.JSONDecodeError:
                logger.warning(f"Failed to decode chunk JSON: {chunk}")
            
            yield chunk

    except Exception as e:
        logger.error(f"Error in response generator: {str(e)}")
        yield f"data: Error: {str(e)}\n\n"
    finally:
        # Save assistant response in finally block to ensure it runs
    
        yield "data: [DONE]\n\n"

        # send metadata converstation to client
        if conversation_id:
            yield f'data: {{"metadata": {{"conversation_id": "{conversation_id}", "user_id": "{user_id}"}}}}'
        else:
            conversation = db.query(Conversation).filter(Conversation.user_id == user_id).order_by(Conversation.created_at.desc()).first()
            conversation_id = conversation.conversation_id if conversation else None
            yield f'data: {{"metadata": {{"conversation_id": "{conversation_id}", "user_id": "{user_id}"}}}}'


        if full_response:
            try:
                save_history(
                    user_id=user_id,
                    role="assistant",
                    content=full_response,
                    conversation_id=conversation_id,
                    db=db
                )
        
            except Exception as e:
                logger.error(f"Failed to save conversation history: {str(e)}")
                yield f"data: {json.dumps({'warning': 'Failed to save conversation history'})}\n\n"


@router.post("/chat")
async def chat(
    user_id: str = Form(...),
    query: str = Form(...)  ,
    is_voice: bool = Form(False),
    is_websearch: bool = Form(False),
    is_image_analysis: bool = Form(False),
    conversation_id: str = Form(None),
    files: List[UploadFile] = Form(None),
    db: Session = Depends(get_db)
):
    # Verify user exists
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=400, detail="User not found")
    
    # Get conversation history
    if  conversation_id:
        history = get_history(
        user_id=user_id,
        conversation_id=conversation_id,
        db=db
        )
    else:
        history = []
    
    # Handle file upload if present
    image_path = None
    if files:
        try:
            os.makedirs(f"images/{user_id}", exist_ok=True)
            for file in files:
                image_path = f"images/{user_id}/{file.filename}"
                contents = await file.read()
                with open(image_path, "wb") as f:
                    f.write(contents)
                await file.seek(0)
        except Exception as e:
            logger.error(f"Error handling file upload: {str(e)}")
            raise HTTPException(status_code=400, detail=f"File upload failed: {str(e)}")

    return StreamingResponse(
        response_generator(
            user_id=user_id,
            query=query,
            is_voice=is_voice,
            is_websearch=is_websearch,
            is_image_analysis=is_image_analysis,
            conversation_id=conversation_id,
            files=files,
            history=history,
            db=db,
            image_path=image_path
        ),
        media_type="text/event-stream"
    )

def get_history(user_id: str, conversation_id: str, db: Session) -> List[Dict]:
    chat_entry = db.query(Conversation).filter(
        Conversation.user_id == user_id,
        Conversation.conversation_id == conversation_id
    ).first()
    return chat_entry.history if chat_entry else []

def save_history(
    user_id: str,
    role: str,
    content: str,
    conversation_id: str,
    db: Session
):
    data = {
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat()
    }

    chat_entry = db.query(Conversation).filter(
        Conversation.user_id == user_id,
        Conversation.conversation_id == conversation_id
    ).first()

    if chat_entry:
        
        history = chat_entry.history
        db.query(Conversation).filter(Conversation.user_id == user_id, Conversation.conversation_id == conversation_id).update({
            "history": history + [data]
        })
    else:
        chat_entry = Conversation(
            user_id=user_id,
            conversation_id=conversation_id,
            history=[data],
            created_at=datetime.now()
        )
        db.add(chat_entry)

    db.commit()
    return chat_entry

@router.get("/chat/history/user/{user_id}")
async def get_chat_history(user_id: str, db: Session = Depends(get_db)):
    chat_entry = db.query(Conversation).filter(Conversation.user_id == user_id).order_by(Conversation.created_at.desc()).all()
    history = []
    for entry in chat_entry:
        history.append({
            'conversation_id': entry.conversation_id,
            'created_at': entry.created_at,
            'title': entry.history[0]['content']
        })
    return history

@router.get("/chat/history/conversation/{conversation_id}")
async def get_chat_history_by_conversation_id(conversation_id: str, db: Session = Depends(get_db)):
    chat_entry = db.query(Conversation).filter(Conversation.conversation_id == conversation_id).first()
    return chat_entry.history

