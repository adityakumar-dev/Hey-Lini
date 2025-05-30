import base64
import aiohttp
import json
from typing import AsyncGenerator
from configs.response_rules import (
    search_response_context,
    system_message,
    search_message,
    voice_message_rule,
    health_assistant_system_message,
    accident_assistant_system_message
)
import logging

logger = logging.getLogger(__name__)

class ModelInit:
    def __init__(self):
        self.model = "gemma3:4b"
        self.base_url = "http://localhost:11434/api/"
    
    async def text_offline_response(
        self, 
        query: str, 
        history: list, 
        is_voice: bool = False
    ) -> AsyncGenerator[str, None]:
        """Generate text response from the local model"""
        url = f"{self.base_url}chat"
        headers = {"Content-Type": "application/json"}

        rules = voice_message_rule if is_voice else system_message
        messages = [
            {"role": "system", "content": "\n".join(rules)},
            *history,
            {"role": "user", "content": query}
        ]

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True
        }

        logger.info(f"Sending text request to model: {query}")
        async for chunk in self._stream_response(payload, url, headers):
            yield chunk

    async def image_offline_response(
        self, 
        query: str, 
        history: list, 
        image_path: str
    ) -> AsyncGenerator[str, None]:
        """Generate response for image analysis"""
        url = f"{self.base_url}chat"
        headers = {"Content-Type": "application/json"}

        # Read and encode image
        with open(image_path, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode("utf-8")
        
        messages = [
            {"role": "system", "content": "\n".join(accident_assistant_system_message)},
            *history,
            {
                "role": "user", 
                "content": query,
                "images": [base64_image]
            }
        ]

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True
        }

        logger.info(f"Sending image request to model: {query}")
        async for chunk in self._stream_response(payload, url, headers):
            yield chunk
    
    async def _stream_response(
        self, 
        payload: dict, 
        url: str, 
        headers: dict
    ) -> AsyncGenerator[str, None]:
        """Handle the streaming response from the model"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        async for line in response.content:
                            if line:
                                try:
                                    data = json.loads(line)
                                    if "message" in data:
                                        content = data["message"].get("content", "")
                                        if content:
                                            # Format each character as a separate JSON response
                                            for char in content:
                                                yield f"data: {json.dumps({'content': char})}\n\n"
                                except json.JSONDecodeError:
                                    logger.warning(f"Failed to decode JSON: {line}")
                                    continue
                    else:
                        error = await response.text()
                        logger.error(f"Model API error: {error}")
                        yield f"data: {json.dumps({'error': f'Model API returned status {response.status}'})}\n\n"
        except Exception as e:
            logger.error(f"Streaming error: {str(e)}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"