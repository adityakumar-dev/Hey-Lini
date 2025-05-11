import base64
import json
from typing import Dict, Generator, List

import requests
from brain.search_engine import SearXNGSearch
from configs.response_rules import (
    search_response_context,
    system_message,
    search_message,
    voice_message_rule,
    health_assistant_system_message,
    accident_assistant_system_message
)
from db.getdb import get_db
from db.models import Conversation


class ChatModel:
    def __init__(self):
        self.model = "gemma3:4b"  # or your preferred model name
        self.base_url = "http://localhost:11434/api"
        self.conversation_history = []
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
            # Open image in base64 format
            image_base64 = []
            for image in image_path:
                with open(image, "rb") as image_file:
                    image_base64.append(base64.b64encode(image_file.read()).decode("utf-8"))

            # Build the prompt in the correct format for Ollama vision models
            data = {
                "model": self.model,
                "messages": [
                    {"role": "user", "content": prompt, "images": image_base64}
                ],
                "stream": True,
            }

            print(f"Sending request to Ollama with data: {json.dumps(data, indent=2)}")

            # Send the request to Ollama
            response = requests.post(f"{self.base_url}/chat", json=data, stream=True)
            response.raise_for_status()

            # Process the response
            full_response = ""
            for line in response.iter_lines():
                if line:
                    try:
                        chunk = json.loads(line.decode("utf-8"))
                        if "message" in chunk:
                            content = chunk["message"].get("content", "")
                            print(content, end="", flush=True)
                            full_response += content
                        if chunk.get("done", False):
                            print()
                            break
                    except json.JSONDecodeError:
                        print(f"Error decoding JSON: {line}")

            return full_response

        except FileNotFoundError:
            print("Error: Image file not found")
            return "Error: Image file not found"
        except requests.exceptions.RequestException as e:
            print(f"Error making request to Ollama: {e}")
            return f"Error making request to Ollama: {str(e)}"
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            return f"An unexpected error occurred: {str(e)}"

    def format_search_results(self, results: List[Dict]) -> str:
        """Format search results into a readable string."""
        if not results:
            return "No search results found."
        
        formatted = "\nSearch Results:\n"
        formatted += "=" * 80 + "\n\n"
        
        for i, result in enumerate(results, 1):
            formatted += f"Result {i}:\n"
            formatted += "-" * 40 + "\n"
            formatted += f"Title: {result['title']}\n\n"
            formatted += f"Content: {result.get('body', result.get('content', 'No description'))}\n\n"
            if 'link' in result:
                formatted += f"Source: {result['link']}\n"
            elif 'url' in result:
                formatted += f"Source: {result['url']}\n"
            formatted += f"Retrieved: {result['timestamp']}\n"
            formatted += "-" * 40 + "\n\n"
        
        formatted += "=" * 80 + "\n"
        return formatted

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
                    parsed_response = json.loads(search_query)
                    search_query = parsed_response.get("search_query", search_query)
                    categories = parsed_response.get("categories", None)
                except json.JSONDecodeError:
                    categories = None

                print(f"\nGenerated search query: {search_query}")
                searx = SearXNGSearch()
                search_results = searx.search(search_query)
                if search_results:
                    context = self.format_search_results(search_results)
                    message = f"""Context from search:
{context}

Based on this information, please provide a detailed and accurate answer to: {prompt}

Please follow these guidelines:
1. Use [REFERENCE: "source_name" - "url"] format for citations.
2. Organize information with proper headings and bullet points.
3. Mark time-sensitive information with [UPDATED: date].
4. Use markdown formatting for better readability.
5. Include a "References" section at the end.
6. Verify information from multiple sources.
7. Present conflicting information with clear attribution.
8. Provide complete answers - do not cut off mid-sentence.
9. Include practical examples where relevant.
10. End with a clear conclusion or next steps."""
                else:
                    message = f"I couldn't find any relevant real-time information. Please answer based on your knowledge: {prompt}"

                # Add message to conversation history
                self.conversation_history.append({"role": "user", "content": message})

            # Prepare the chat request with system message
            data = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_message["content"]},
                    *self.conversation_history,
                    {"role": "user", "content": prompt},
                ],
                "stream": True,
                "options": {
                    "num_ctx": 8192,
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "stop": ["<|", "|>", "<", ">", "thus", "therefore", "hence", "pat", "pati", "etc", "..."],
                },
            }

            print(f"Sending request to Ollama with data: {json.dumps(data, indent=2)}")

            # Send the request to Ollama
            response = requests.post(f"{self.base_url}/chat", json=data, stream=True)
            response.raise_for_status()

            # Process the response
            full_response = ""
            for line in response.iter_lines():
                if line:
                    try:
                        chunk = json.loads(line.decode("utf-8"))
                        if "message" in chunk:
                            content = chunk["message"].get("content", "")
                            print(content, end="", flush=True)
                            full_response += content
                        if chunk.get("done", False):
                            print("\n")
                            break
                    except json.JSONDecodeError:
                        print(f"Error decoding JSON: {line}")
                        continue

            # Add response to conversation history
            if full_response.strip():
                self.conversation_history.append({"role": "assistant", "content": full_response})
            return full_response

        except Exception as e:
            error_msg = f"Error in analyzeText: {str(e)}"
            print(f"Error: {error_msg}")
            return error_msg

    def generate_query_prompt(self, prompt: str):
        response = requests.post(
            f"{self.base_url}/generate",
            headers={"Content-Type": "application/json"},
            json={"model": self.model, "prompt": search_message(prompt), "stream": False},
        )
        return response.json()

    def format_search_results(self, results: List[Dict]) -> str:
        if not results:
            return "No search results found."
        formatted = "\n".join(
            f"- {result.get('title', 'No title')} ({result.get('url', 'No URL')})"
            for result in results
        )
        return formatted
    def quick_streamed_response(self, prompt: str) -> Generator[str, None, None]:
   
        try:
            # Format the messages field as a list of dictionaries
            messages = [
                {"role": "system", "content": voice_message_rule},  # Add a system message if needed
                {"role": "user", "content": prompt}  # User's prompt
            ]

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
    
    def quick_streamed_health(self, prompt: str, type : str) -> Generator[str, None, None]:
   
        try:
            # Format the messages field as a list of dictionaries
            messages = [
                {"role": "system", "content": health_assistant_system_message if type == "health" else accident_assistant_system_message},  # Add a system message if needed
                {"role": "user", "content": prompt}  # User's prompt
            ]

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
            