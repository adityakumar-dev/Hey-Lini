from fastapi import APIRouter, Depends, Form, HTTPException, File, UploadFile
from fastapi.responses import StreamingResponse
from typing import List, Dict, Any, Optional, Union
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime
import json
import traceback

from db.getdb import get_db
from brain.model_init import ChatModel
from db.models import Conversation

router = APIRouter()
chat_model = ChatModel()

def add_history(user_id: int, role: str, content: str, db: Session, conversation_id: int = None) -> Conversation:
    """Append a message to the correct conversation, always as a flat list. Create conversation if needed."""
    try:
        # Clean the content if it's a JSON string
        if isinstance(content, str):
            try:
                # Try to parse as JSON
                parsed_content = json.loads(content)
                # If it's a dict with response field, use that
                if isinstance(parsed_content, dict) and "response" in parsed_content:
                    content = parsed_content["response"]
                # If it's a dict with message field, use that
                elif isinstance(parsed_content, dict) and "message" in parsed_content:
                    content = parsed_content["message"].get("content", content)
            except json.JSONDecodeError:
                # If not JSON, use as is
                pass

        if not conversation_id:
            new_message = {
                "role": role,
                "content": content
            }
            conversation = Conversation(
                user_id=user_id, 
                history=[new_message], 
                created_at=datetime.utcnow()
            )
            db.add(conversation)
            db.commit()
            db.refresh(conversation)
            print("1st if conversation : ",conversation)   
            return conversation
        conversation = None
        # First, try to find the conversation by provided ID
        if conversation_id:
            conversation = db.query(Conversation).filter(
                Conversation.conversation_id == conversation_id,
                Conversation.user_id == user_id
            ).first()
        print("1st if conversation : ",conversation)   
        # If no conversation found but ID was provided, this is an error
        if conversation_id and not conversation:
            raise HTTPException(status_code=404, detail=f"Conversation with ID {conversation_id} not found")
        print("2nd if conversation : ",conversation)   
        # If no conversation_id was provided or it wasn't found, check if we should use the latest
        if not conversation and not conversation_id:
            # Get the latest conversation for the user if it exists
            conversation = db.query(Conversation).filter(
                Conversation.user_id == user_id
            ).order_by(Conversation.created_at.desc()).first()
            print("3rd if conversation : ",conversation)   
        # If still no conversation, create a new one
        if not conversation:
            # Create new conversation with default empty history
            conversation = Conversation(
                user_id=user_id, 
                history=[], 
                created_at=datetime.utcnow()
            )
            db.add(conversation)
            db.commit()
            db.refresh(conversation)
        print("4th if conversation : ",conversation)   
        
        # Get current history or initialize an empty list
        current_history = []
        if conversation.history:
            # Try to handle both list and JSON string formats
            if isinstance(conversation.history, list):
                current_history = conversation.history
            elif isinstance(conversation.history, str):
                try:
                    current_history = json.loads(conversation.history)
                except json.JSONDecodeError:
                    current_history = []
        print("5th if conversation : ",conversation)   
            
        # Ensure we have a flat list (not nested)
        flat_history = []
        for item in current_history:
            if isinstance(item, list):
                flat_history.extend(item)
            else:
                flat_history.append(item)
        print("6th if conversation : ",conversation)   
                
        # Create the new message
        new_message = {
            "role": role,
            "content": content
        }
        
        # Append the new message to the flat history
        flat_history.append(new_message)
        
        # Explicitly update the history field
        conversation.history = flat_history
        
        # Commit changes and refresh
        db.commit()
        db.refresh(conversation)
        
        return conversation
    except HTTPException as he:
        # Re-raise HTTP exceptions
        raise he
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update history: {str(e)}")

@router.post("/chat")
async def chat(
    user_id: int = Form(...),
    conversation_id: int = Form(None),
    prompt: str = Form(...),
    is_search: bool = Form(False),
    image: List[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID is required")
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt is required")
    
    print(f"Processing chat request: user_id={user_id}, conversation_id={conversation_id}, prompt={prompt[:30]}...")
    
    try:
        history = []
        try:
            conversation = db.query(Conversation).filter(Conversation.conversation_id == conversation_id).first()
            if conversation:
                history = conversation.history
        except Exception as e:
            print(f"Error getting conversation history: {str(e)}")
            history = []
        
        # Handle image processing
        if image and len(image) > 0:
            try:
                import os
                os.makedirs("images", exist_ok=True)
                image_paths = []
                for img in image:
                    # Generate a unique filename
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"{timestamp}_{img.filename}"
                    image_path = f"images/{filename}"
                    
                    # Save the image
                    with open(image_path, "wb") as f:
                        f.write(await img.read())
                    image_paths.append(image_path)
                
                print(f"Processing images: {image_paths}")
                
                # Get conversation history
                history = []
                if conversation_id:
                    conversation = db.query(Conversation).filter(Conversation.conversation_id == conversation_id).first()
                    if conversation:
                        history = conversation.history
                
                # Generate image analysis response
                response = chat_model.analyzeImage(prompt, image_paths, history)
                
                # Record the conversation for image analysis
                print(f"Adding user message to history for image analysis")
                conversation = add_history(user_id, "user", prompt, db, conversation_id)
                
                if response:
                    print(f"Adding assistant response to history for image analysis")
                    add_history(user_id, "assistant", response, db, conversation.conversation_id)
                    
                    # Clean up image files after processing
                    for path in image_paths:
                        try:
                            os.remove(path)
                        except Exception as e:
                            print(f"Error removing image file {path}: {str(e)}")
                
                return {
                    "status": "success",
                    "conversation_id": conversation.conversation_id,
                    "history": conversation.history,
                    "assistant_response": response
                }
            except Exception as img_err:
                print(f"Image processing error: {str(img_err)}")
                print(f"Traceback: {traceback.format_exc()}")
                raise HTTPException(status_code=500, detail=f"Image processing error: {str(img_err)}")
        
        # Handle search mode
        elif is_search:
            try:
                print(f"Processing search request")
                # Get conversation history first
                history = []
                if conversation_id:
                    conversation = db.query(Conversation).filter(Conversation.conversation_id == conversation_id).first()
                    if conversation:
                        history = conversation.history
                
                # Generate search response
                response = chat_model.analyzeText(prompt, user_id, history, is_search=True)
                
                # Record search queries in conversation history
                print(f"Adding user message to history for search")
                conversation = add_history(user_id, "user", prompt, db, conversation_id)
                
                if response:
                    print(f"Adding assistant response to history for search")
                    add_history(user_id, "assistant", response, db, conversation.conversation_id)
                
                return {
                    "status": "success",
                    "conversation_id": conversation.conversation_id,
                    "history": conversation.history,
                    "assistant_response": response
                }
            except Exception as search_err:
                print(f"Search processing error: {str(search_err)}")
                raise HTTPException(status_code=500, detail=f"Search processing error: {str(search_err)}")
        
        # Normal chat flow
        else:
            print(f"Processing normal chat request")
            
            # Append user message to history
            print(f"Adding user message to history"+" user : ",user_id , " convid  : " , conversation_id)
            conversation = add_history(user_id, "user", prompt, db, conversation_id)
            print(f"Created/updated conversation: {conversation.conversation_id}")
            
            # Check if conversation history is available
            if not conversation.history:
                print("WARNING: No history available for this conversation")
            
            # Get response from model
            response = chat_model.analyzeText(prompt, user_id, conversation.history, is_search=False)
            
            # Add response to history
            if response:
                print(f"Adding assistant response to history")
                add_history(user_id, "assistant", response, db, conversation.conversation_id)
            
            return {
                "status": "success",
                "conversation_id": conversation.conversation_id,
                "history": conversation.history,
                "assistant_response": response
            }
            
    except Exception as e:
        print(f"Error in chat route: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

class ChatAdd(BaseModel):
    user_id: int
    role: str
    content: str
    created_at: str

@router.get("/chat/history/{conversation_id}")
def chat_history(conversation_id: int, db: Session = Depends(get_db)):
    try:
        conversation = db.query(Conversation).filter(
            Conversation.conversation_id == conversation_id,
        ).first()
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return {
            "status": "success",
            "data": {
                "id": conversation.conversation_id,
                "user_id": conversation.user_id,
                "history": conversation.history,
                "created_at": conversation.created_at.isoformat()
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/chat/history/user/{user_id}")
def user_chat_history(user_id: int, db: Session = Depends(get_db)):
    try:
        conversations = db.query(Conversation).filter(
            Conversation.user_id == user_id
        ).order_by(Conversation.created_at.desc()).all()
        return {
            "status": "success",
            "data": [
                {
                    "id": conv.conversation_id,
                    "user_id": conv.user_id,
                    "history": conv.history,
                    "created_at": conv.created_at.isoformat()
                } for conv in conversations
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/chat/history/{conversation_id}")
def delete_conversation(conversation_id: int, user_id: int, db: Session = Depends(get_db)):
    try:
        conversation = db.query(Conversation).filter(
            Conversation.conversation_id == conversation_id,
            Conversation.user_id == user_id  # Ensure user owns the conversation
        ).first()
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        db.delete(conversation)
        db.commit()
        return {"status": "success", "message": "Conversation deleted successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/chat/history/user/{user_id}")
def clear_user_history(user_id: int, db: Session = Depends(get_db)):
    try:
        db.query(Conversation).filter(Conversation.user_id == user_id).delete()
        db.commit()
        return {"status": "success", "message": "All conversations cleared successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))