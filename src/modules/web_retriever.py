import requests
import os
from typing import Optional
from rich.console import Console

class GoogleWebRetriever:
    """
    Implements an "Agentic Fallback" strategy.
    When standard academic APIs (like Semantic Scholar) fail to return a direct link,
    this class searches the open web (via Google) to find the PDF manually, similar to 
    how a human researcher would type 'filetype:pdf "Paper Title"' into a search bar.
    """
    def __init__(self, api_key: Optional[str] = None, cx: Optional[str] = None):
        """
        Initializes the retriever with Google credentials.
        Args:
            api_key: Your Google Cloud API Key (authentication).
            cx: Your Custom Search Engine ID (configuration for *what* to search).
        """
        # Try to use passed arguments, otherwise fall back to environment variables.
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        self.cx = cx or os.getenv("GOOGLE_SEARCH_CX")
        self.console = Console()
        self.base_url = "https://www.googleapis.com/customsearch/v1"

    def search_pdf(self, title: str) -> Optional[str]:
        """
        Executes a Google Search for the paper title, specifically looking for PDF files.
        Returns: The URL of the first PDF found, or None.
        """
        if not self.api_key or not self.cx:
            # If keys are missing, we just skip this strategy without erroring.
            return None

        # --- The Magic Query ---
        # `filetype:pdf` tells Google to only return results that are actual PDF documents.
        # `"{title}"` (with quotes) tells Google to look for that exact phrase.
        query = f'filetype:pdf "{title}"'
        
        # Parameters for the JSON API
        params = {
            'q': query,
            'key': self.api_key,
            'cx': self.cx,
            'num': 3  # We only fetch the top 3 results to save quota and speed up processing.
        }

        try:
            response = requests.get(self.base_url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                items = data.get('items', [])
                
                # Iterate through the search results
                for item in items:
                    link = item.get('link')
                    
                    # --- Validation ---
                    # Just because Google returned it doesn't mean it's the right file.
                    # We check if the link actually looks like a PDF url.
                    if link and (link.lower().endswith('.pdf') or 'pdf' in link.lower()):
                         self.console.print(f"[green]Google Search Found PDF candidate:[/green] {link}")
                         return link
            else:
                # 400 = Bad Request (often invalid keys), 403 = Forbidden (quota or service unavailable)
                self.console.print(f"[red]Google Search API Error: {response.status_code}[/red]")
                
        except Exception as e:
            self.console.print(f"[red]Google Search failed: {e}[/red]")

        return None
