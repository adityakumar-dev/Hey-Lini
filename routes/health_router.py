from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from brain.model_init import ChatModel
router = APIRouter()
chat_model = ChatModel()

@router.get("/health")
async def health_check(prompt: str = None):

    try:
        if not prompt:
            return {"error": "Prompt is required"}

        # Generate a streaming response from the model
        response_stream = chat_model.quick_streamed_health(prompt, "health")

        # Return the response as a streaming response
        return StreamingResponse(response_stream, media_type="text/event-stream")

    except Exception as e:
        return {"error": str(e)}