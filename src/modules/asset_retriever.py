import requests
import httpx
import os
from rich.console import Console

console = Console()

# AssetRetriever is a class that handles the actual process of downloading files from the internet.
# It is initialized with an optional email address for Unpaywall API queries.
# It has a method to get the best open access link for a paper.
# It has a method to download a file from a URL to a local path.
# It has a method to download a file from ArXiv.

class AssetRetriever:
    """
    Handles the actual process of downloading files from the internet.
    Supports fetching from direct URLs, Unpaywall (legacy), and ArXiv.
    """
    def __init__(self, email="unpaywall_placeholder@example.com"):
        self.email = email

    def get_best_oa_link(self, doi):
        """
        Queries the Unpaywall API to find a free (Open Access) version of a paper.
        Note: We removed this from the main loop in Phase 2.5 because it was returning
        too many false negatives for our test cases, but the method remains as a utility.
        """
        url = f"https://api.unpaywall.org/v2/{doi}?email={self.email}"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                # 'is_oa' means 'Is Open Access'
                if data.get('is_oa'):
                    best_oa_location = data.get('best_oa_location', {})
                    # Prefer PDF url, fall back to general URL
                    return best_oa_location.get('url_for_pdf') or best_oa_location.get('url')
        except Exception as e:
            console.print(f"[red]Error querying Unpaywall for {doi}: {e}[/red]")
        return None

    def download_pdf(self, url, output_path):
        """
        Downloads a file from a URL to a local path.
        """
        # Headers are important!
        # Many websites (like ArXiv or University repos) block scripts.
        # By setting a 'User-Agent', we pretend to be a standard Chrome browser.
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        try:
            # We use 'httpx' instead of 'requests' here because it handles streaming better.
            # 'stream=True' means we download the file in chunks, so we don't load 
            # a massive PDF entirely into RAM before saving it.
            with httpx.stream('GET', url, headers=headers, follow_redirects=True, timeout=30.0) as response:
                 if response.status_code == 200:
                    with open(output_path, 'wb') as f:
                        for chunk in response.iter_bytes():
                            f.write(chunk)
                    return True
                 else:
                    console.print(f"[red]Failed download {url}: Status {response.status_code}[/red]")
        except Exception as e:
            console.print(f"[red]Failed to download {url}: {e}[/red]")
        return False

    def download_from_arxiv(self, arxiv_id, output_path):
        """
        Constructs a direct download link for ArXiv papers.
        ArXiv URLs follow a predictable format: https://arxiv.org/pdf/{ID}.pdf
        """
        url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        console.print(f"[cyan]Attempting ArXiv Direct Download: {url}[/cyan]")
        return self.download_pdf(url, output_path)
