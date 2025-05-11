import requests
from typing import List, Dict, Optional
from datetime import datetime
import json
import logging
from urllib.parse import urlparse

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class SearXNGSearch:
    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url.rstrip('/')
        self.search_endpoint = f"{self.base_url}/search"
        self.headers = {
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'application/json'
        }
        self.data = {
            'q': '',
            'format': 'json',
            'categories': 'general',
            'language': 'auto',
            'time_range': '',
            'safesearch': '0',
            'theme': 'detailed'
        }

    def _clean_url(self, url: str) -> str:
        """Clean and format URL for display."""
        try:
            parsed = urlparse(url)
            return f"{parsed.netloc}{parsed.path}"
        except:
            return url

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            return urlparse(url).netloc
        except:
            return url

    def search(self, query: str, num_results: int = 10, categories: List[str] = None) -> List[Dict]:
        """
        Perform a search using SearXNG.
        
        Args:
            query (str): The search query
            num_results (int): Number of results to return (default: 10)
            categories (List[str]): List of categories to search in (e.g., ['general', 'science', 'news'])
        
        Returns:
            List[Dict]: List of search results with title, url, content, and source
        """
        try:
            logger.debug(f"Performing search for query: {query}")
            
            # Update search parameters
            self.data['q'] = query
            
            logger.debug(f"Search parameters: {self.data}")

            # Make the request
            response = requests.get(
                f"{self.search_endpoint}?q={query}&format=json",
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()
            
            logger.debug(f"Response status code: {response.status_code}")
            logger.debug(f"Response content type: {response.headers.get('content-type', 'unknown')}")
            
            # Parse JSON response
            data = response.json()
            logger.debug(f"Received JSON response: {json.dumps(data, indent=2)}")
            
            # Format the results
            formatted_results = []
            
            # Extract results from JSON
            if 'results' in data:
                # Track domains to avoid duplicate sources
                seen_domains = set()
                
                for result in data['results'][:num_results]:
                    try:
                        # Get the domain for source tracking
                        domain = self._extract_domain(result.get('url', ''))
                        
                        # Skip if we've seen this domain before (to get diverse sources)
                        if domain in seen_domains:
                            continue
                        seen_domains.add(domain)
                        
                        # Clean and format the content
                        content = result.get('content', 'No description')
                        content = ' '.join(content.split())  # Remove extra whitespace
                        
                        formatted_result = {
                            'title': result.get('title', 'No title'),
                            'url': result.get('url', ''),
                            'content': content,
                            'source': result.get('engine', 'Unknown'),
                            'domain': domain,
                            'timestamp': datetime.now().isoformat()
                        }
                        formatted_results.append(formatted_result)
                        logger.debug(f"Found result: {formatted_result['title']}")
                    except Exception as e:
                        logger.error(f"Error parsing result: {e}")
                        continue
            
            return formatted_results

        except requests.exceptions.RequestException as e:
            logger.error(f"Error performing SearXNG search: {e}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON response: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error during search: {e}")
            return []

    def format_results(self, results: List[Dict]) -> str:
        """Format search results into a readable string."""
        if not results:
            return "No search results found."
        
        formatted = "\nSearch Results:\n"
        formatted += "=" * 80 + "\n\n"
        
        # Group results by domain for better organization
        domain_groups = {}
        for result in results:
            domain = result['domain']
            if domain not in domain_groups:
                domain_groups[domain] = []
            domain_groups[domain].append(result)
        
        # Format results by domain
        for domain, domain_results in domain_groups.items():
            formatted += f"Source: {domain}\n"
            formatted += "-" * 40 + "\n\n"
            
            for i, result in enumerate(domain_results, 1):
                formatted += f"Result {i}:\n"
                formatted += f"Title: {result['title']}\n\n"
                formatted += f"Content: {result['content']}\n\n"
                formatted += f"URL: {self._clean_url(result['url'])}\n"
                formatted += f"Engine: {result['source']}\n"
                formatted += f"Retrieved: {result['timestamp']}\n"
                formatted += "-" * 40 + "\n\n"
            
            formatted += "=" * 80 + "\n\n"
        
        return formatted

def main():
    # Example usage
    searx = SearXNGSearch()
    
    # Test search
    query = "vmsbutu affiliated colleges"
    print(f"\nTesting search for: {query}")
    results = searx.search(query, num_results=10)
    
    # Print formatted results
    print(searx.format_results(results))

if __name__ == "__main__":
    main()
