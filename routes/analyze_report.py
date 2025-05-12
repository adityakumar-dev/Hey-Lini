from fastapi import APIRouter, File, Form, UploadFile, Depends, HTTPException
from fastapi.responses import StreamingResponse
from typing import List
import os
from brain.model_init import ChatModel
from configs.response_rules import report_analyzer_rules
from db.getdb import get_db
from sqlalchemy.orm import Session

router = APIRouter()
chat_model = ChatModel()

@router.post("/analyze/report")
async def analyze_report(
    description: str = Form(...),
    images: List[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """
    Analyze a report with optional images and provide a streaming response
    """
    image_paths = []
    upload_dir = "uploads/reports"

    try:
        # Ensure the upload directory exists
        os.makedirs(upload_dir, exist_ok=True)

        # Save uploaded images
        if images:
            for image in images:
                if not image.content_type.startswith("image/"):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid file type for {image.filename}. Only images are allowed."
                    )

                file_path = os.path.join(upload_dir, image.filename)
                with open(file_path, "wb") as f:
                    content = await image.read()
                    f.write(content)

                if not os.path.exists(file_path):
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to save image: {file_path}"
                    )

                image_paths.append(file_path)

        # Build the base prompt
        prompt = f"""
        Report Analysis Request:
        Description: {description}
        
        Please analyze this report following these guidelines:
        {report_analyzer_rules}
        
        Provide a detailed analysis including:
        1. Emergency Level Assessment
        2. Recommended Response
        3. Required Resources
        4. Special Considerations
        5. Follow-up Actions
        """

        if image_paths:
            # Stream with image analysis
            resposne_stream = chat_model.analyzeImageStream(
                        prompt=prompt,
                        image_path=image_paths,
                        history=[]
                    )

            return StreamingResponse(
                resposne_stream,
                media_type="text/event-stream"
            )

        else:
            # Text-only analysis
            return StreamingResponse(
                chat_model.quick_streamed_health(prompt, "health"),
                media_type="text/event-stream"
            )

    except Exception as e:
        # Cleanup in case of an exception
        for path in image_paths:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except:
                pass
        raise HTTPException(status_code=500, detail=f"Report analysis failed: {str(e)}")
