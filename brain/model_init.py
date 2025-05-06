import base64
import json
from typing import Dict, Generator, List

from fastapi.responses import StreamingResponse
from pydantic_core import Url
import requests
from brain.search_engine import SearXNGSearch
from configs.response_rules import search_response_context, system_message, search_message
from db.getdb import get_db
from db.models import Conversation
from sqlalchemy.orm import Session
# from configs.response_rules import system_message, search_message

class ChatModel:
    def __init__(self):
        self.model = "gemma3:4b"  # or your preferred model name
        self.base_url = "http://localhost:11434/api"
        self.load_model()

    def load_model(self):
        try:
            # Verify model is available
            response = requests.get(f"{self.base_url}/tags")
            if response.status_code == 200:
                models = response.json().get("models", [])
                if not any(m["name"] == self.model for m in models):
                    raise Exception(f"Model {self.model} not found")
            return True
        except Exception as e:
            raise Exception(f"Failed to load model: {str(e)}")

    def analyzeImage(self, prompt: str, image_path: List[str], history: List[Dict]):
        try:
            #open image in base64 format
            image_base64 = []
            for image in image_path:
                with open(image, "rb") as image_file:
                    image_base64.append(base64.b64encode(image_file.read()).decode('utf-8'))

            # Build the prompt in the correct format for Ollama vision models
            data = {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt,
                        "images": image_base64
                    }
                ],
                "stream": True
            }

            print(f"Sending request to Ollama with data: {json.dumps(data, indent=2)}")

            # Send the request to Ollama
            response = requests.post(f'{self.base_url}/chat', json=data)
            response.raise_for_status()

            # Process the response
            full_response = ""
            for line in response.iter_lines():
                if line:
                    try:
                        chunk = json.loads(line.decode('utf-8'))
                        if 'message' in chunk:
                            content = chunk['message'].get('content', '')
                            print(content, end='', flush=True)
                            full_response += content
                        if chunk.get('done', False):
                            print()
                            break
                    except json.JSONDecodeError:
                        print(f"Error decoding JSON: {line}")

            return full_response

        except FileNotFoundError:
            print(f"Error: Image file not found")
            return "Error: Image file not found"
        except requests.exceptions.RequestException as e:
            print(f"Error making request to Ollama: {e}")
            return f"Error making request to Ollama: {str(e)}"
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            return f"An unexpected error occurred: {str(e)}"

    def analyzeText(self, prompt: str, user_id: int, history: List[Dict], is_search: bool = False):
        try:
            if is_search:
                # Generate search query using the model
                response = self.generate_query_prompt(prompt)
                if not response or "response" not in response:
                    raise Exception("Failed to generate search query")
                
                # Extract the search query and categories from the model's response
                search_query = response["response"]
                try:
                    # Try to parse the response as JSON to get categories
                    parsed_response = json.loads(search_query)
                    search_query = parsed_response.get("search_query", search_query)
                    categories = parsed_response.get("categories", None)
                except json.JSONDecodeError:
                    # If not JSON, use the raw response as search query
                    categories = None
                
                print(f"\nGenerated search query: {search_query}")
                if categories:
                    print(f"Categories: {categories}")
                
                # Perform the search
                search_engine = SearXNGSearch()
                results = search_engine.search(search_query, categories=categories)
                
                if not results:
                    return "No search results found."
                
                print(f"\nFound {len(results)} results for '{search_query}'")
                
                # Format search results for better context
                formatted_results = []
                for result in results:
                    if isinstance(result, dict):
                        # Clean and format the content
                        content = result.get('content', '').strip()
                        if content:
                            formatted_results.append({
                                "title": result.get("title", ""),
                                "url": result.get("url", ""),
                                "content": content,
                                "source": result.get("source", ""),
                                "domain": result.get("domain", ""),
                                "timestamp": result.get("timestamp", ""),
                                "score": result.get("score", 0),
                                "category": result.get("category", "general")
                            })
                
                # Sort results by score
                formatted_results.sort(key=lambda x: x.get('score', 0), reverse=True)
                
                # Generate a response based on search results
                try:
                    # Prepare the context with search results and history
                    context = search_response_context(formatted_results, history, prompt)
                    
                    # Generate response using the formatted results
                    response = requests.post(
                        f"{self.base_url}/chat",
                        json={
                            "model": self.model,
                            "messages": [
                                {"role": "system", "content": str(system_message["content"])},
                                {"role": "user", "content": context}
                            ],
                            "stream": False,
                            "options": {
                                "num_ctx": 8192,
                                "temperature": 0.7,
                                "top_p": 0.9,
                                "stop": ["<|", "|>", "<", ">", "thus", "therefore", "hence", "pat", "pati", "etc", "..."]
                            }
                        }
                    )
                    
                    if response.status_code != 200:
                        raise Exception(f"API request failed with status {response.status_code}")
                    
                    response_data = response.json()
                    if "message" in response_data:
                        content = response_data["message"].get("content", "")
                        # Format the response as JSON if it's not already
                        try:
                            json.loads(content)
                            return content
                        except json.JSONDecodeError:
                            return json.dumps({
                                "response": content,
                                "references": [
                                    {
                                        "title": result.get("title", ""),
                                        "url": result.get("url", ""),
                                        "relevance": "Provides information about the search query",
                                        "score": result.get("score", 0),
                                        "category": result.get("category", "general")
                                    }
                                    for result in formatted_results[:3]  # Include top 3 results as references
                                ]
                            })
                    return "No response generated."
                        
                except Exception as e:
                    return f"Error generating response: {str(e)}"
            
            # Get conversation history (use the latest conversation)
            db = next(get_db())
            try:
                conversation = db.query(Conversation).filter(Conversation.user_id == user_id).order_by(Conversation.created_at.desc()).first()
                history = conversation.history if conversation and conversation.history else []
            finally:
                db.close()

            # Clean and format history messages
            cleaned_history = []
            for msg in history:
                if isinstance(msg, dict) and "role" in msg and "content" in msg:
                    # If content is a string, use it directly
                    if isinstance(msg["content"], str):
                        cleaned_history.append({
                            "role": msg["role"],
                            "content": msg["content"]
                        })
                    # If content is a dict (API response), extract the message content
                    elif isinstance(msg["content"], dict) and "message" in msg["content"]:
                        content = msg["content"]["message"].get("content", "")
                        if content:
                            cleaned_history.append({
                                "role": msg["role"],
                                "content": content
                            })
                    # If content is a dict with response field
                    elif isinstance(msg["content"], dict) and "response" in msg["content"]:
                        content = msg["content"]["response"]
                        if content:
                            cleaned_history.append({
                                "role": msg["role"],
                                "content": content
                            })

            # Prepare the request data
            data = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": str(system_message["content"])},
                    *cleaned_history,
                    {"role": "user", "content": str(prompt)}
                ],
                "stream": False,
                "options": {
                    "num_ctx": 8192,
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "stop": ["<|", "|>", "<", ">", "thus", "therefore", "hence", "pat", "pati", "etc", "..."]
                }
            }

            print(f"Sending request to Ollama with data: {json.dumps(data, indent=2)}")

            # Make the request to Ollama
            response = requests.post(f"{self.base_url}/chat", json=data)
            
            if response.status_code != 200:
                error_msg = f"API request failed with status {response.status_code}: {response.text}"
                print(f"Error: {error_msg}")
                return error_msg

            response_data = response.json()
            if "message" in response_data:
                return response_data["message"].get("content", "")
            return "No response generated."

        except Exception as e:
            error_msg = f"Error in analyzeText: {str(e)}"
            print(f"Error: {error_msg}")
            return error_msg
        
    def generate_query_prompt(self, prompt: str):
        response = requests.post(
            self.base_url + "/generate",
            headers={"Content-Type": "application/json"},
            data=json.dumps({"model": self.model, "prompt": search_message(prompt), "stream": False}),
        )
        return response.json()

    def chat_response(self, prompt: str, history: List[Dict]) -> Generator[str, None, None]:
        try:
            # Prepare messages with system message and history
            messages = []
            
            # Add system message - ensure content is a string
            messages.append({
                "role": "system",
                "content": str(system_message["content"])
            })
            
            # Add all previous messages from history
            if history:
                for msg in history:
                    if isinstance(msg, dict) and "role" in msg and "content" in msg:
                        # Ensure content is a string
                        content = str(msg["content"])
                        messages.append({
                            "role": msg["role"],
                            "content": content
                        })
            
            # Add the current user message
            messages.append({
                "role": "user",
                "content": str(prompt)
            })

            # Prepare the request data
            data = {
                "model": self.model,
                "messages": messages,
                "stream": True,
                "options": {
                    "num_ctx": 8192,
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "stop": ["<|", "|>", "<", ">", "thus", "therefore", "hence", "pat", "pati", "etc", "..."]
                }
            }

            print(f"Sending request to Ollama with data: {json.dumps(data, indent=2)}")

            # Make the request to Ollama
            response = requests.post(
                f"{self.base_url}/chat",
                json=data,
                stream=True
            )

            if response.status_code != 200:
                error_msg = f"API request failed with status {response.status_code}: {response.text}"
                print(f"Error: {error_msg}")
                yield f"data: {json.dumps({'error': error_msg})}\n\n"
                return

            # Process the streaming response
            for line in response.iter_lines():
                if line:
                    try:
                        chunk = json.loads(line)
                        if "message" in chunk:
                            content = chunk["message"].get("content", "")
                            if content:
                                yield f"data: {json.dumps({'content': content})}\n\n"
                    except json.JSONDecodeError as e:
                        print(f"Error decoding JSON: {e}")
                        continue

        except Exception as e:
            error_msg = f"Error in chat response: {str(e)}"
            print(f"Error: {error_msg}")
            yield f"data: {json.dumps({'error': error_msg})}\n\n"
        
    def chat_response_search(self, prompt: str) -> Generator[str, None, None]:
        try:
            response = requests.post(
                f"{self.base_url}/chat",
                headers={"Content-Type": "application/json"},
                json={
                    "model": self.model,
                    "messages": [system_message, {"role": "user", "content": prompt}],
                    "stream": True,
                    "options": {
                        "num_ctx": 8192,
                        "temperature": 0.7,
                        "top_p": 0.9,
                        "stop": ["<|", "|>", "<", ">", "thus", "therefore", "hence", "pat", "pati", "etc", "..."]
                    }
                },
                stream=True
            )
            if response.status_code != 200:
                raise Exception(f"API request failed with status {response.status_code}")

            for line in response.iter_lines():
                if line:
                    try:
                        chunk = json.loads(line)
                        if "message" in chunk:
                            content = chunk["message"].get("content", "")
                            if content:
                                yield f"data: {json.dumps({'content': content})}\n\n"
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        
    def _handle_about_me_query(self, history: List[Dict]) -> str:
        """Handle queries about the conversation or user."""
        try:
            # Analyze the conversation history
            analysis = {
                "total_messages": len(history),
                "user_messages": sum(1 for msg in history if msg.get("role") == "user"),
                "assistant_messages": sum(1 for msg in history if msg.get("role") == "assistant"),
                "topics": self._extract_topics(history)
            }
            
            return json.dumps({
                "response": f"""Based on our conversation history, I can tell you:

**Conversation Overview:**
• Total messages: {analysis['total_messages']}
• Your messages: {analysis['user_messages']}
• My responses: {analysis['assistant_messages']}

**Main Topics Discussed:**
{self._format_topics(analysis['topics'])}

**Recent Context:**
{self._get_recent_context(history)}""",
                "references": []
            })
        except Exception as e:
            return str(e)

    def _extract_topics(self, history: List[Dict]) -> List[str]:
        """Extract main topics from conversation history."""
        topics = set()
        for msg in history:
            if msg.get("role") == "user":
                content = msg.get("content", "").lower()
                # Add basic topic extraction logic here
                if "search" in content or "find" in content:
                    topics.add("Search Queries")
                if "help" in content or "how to" in content:
                    topics.add("Help Requests")
                if "about" in content or "tell me" in content:
                    topics.add("Information Requests")
        return list(topics)

    def _format_topics(self, topics: List[str]) -> str:
        """Format topics for display."""
        if not topics:
            return "• No specific topics identified yet"
        return "\n".join(f"• {topic}" for topic in topics)

    def _get_recent_context(self, history: List[Dict], limit: int = 3) -> str:
        """Get recent conversation context."""
        if not history:
            return "No previous conversation history available."
        
        recent = history[-limit:]
        context = []
        for msg in recent:
            role = "You" if msg.get("role") == "user" else "I"
            content = msg.get("content", "")[:100] + "..." if len(msg.get("content", "")) > 100 else msg.get("content", "")
            context.append(f"{role}: {content}")
        
        return "\n".join(context)

    # def return_stream(self, response: Generator[str, None, None]):
    #     return StreamingResponse(response, media_type="text/event-stream")