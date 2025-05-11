from fastapi import Request , APIRouter
from fastapi.responses import JSONResponse
from brain.model_init import ChatModel
from fastapi.responses import StreamingResponse

# Initialize the ChatModel
chat_model = ChatModel()
router = APIRouter()
@router.post("/voice")
async def voice_chat(prompt :str  ):
    """
    Route to handle voice-like streaming responses.
    The client sends a prompt, and the server streams the model's response.
    """
    try:
        if not prompt:
            return {"error": "Prompt is required"}

        # Generate a streaming response from the model
        response_stream = chat_model.quick_streamed_response(prompt)

        # Return the response as a streaming response
        return StreamingResponse(response_stream, media_type="text/event-stream")

    except Exception as e:
        return {"error": str(e)}