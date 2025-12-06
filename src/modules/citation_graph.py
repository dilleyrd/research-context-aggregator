import os
import re
import arxiv
from semanticscholar import SemanticScholar
from rich.console import Console

# Rich is a library for beautiful terminal output.
console = Console()

# CitationGraph is a class that manages interactions with local citation databases and APIs (Semantic Scholar, ArXiv).
# It is responsible for resolving paper identifiers and fetching reference lists.
# It is initialized with an optional API key for Semantic Scholar.
# It has a method to get paper metadata for a given paper identifier.
# It has a method to search for a paper by title.
# It has a method to get influential references for a given paper identifier.

class CitationGraph:
    """
    Manages interactions with local citation databases and APIs (Semantic Scholar, ArXiv).
    This class is responsible for resolving paper identifiers and fetching reference lists.
    """
    def __init__(self, api_key=None):
        # Initialize the Semantic Scholar client.
        # An API key allows for higher rate limits (more requests per second).
        self.sch = SemanticScholar(api_key=api_key)

    def get_paper_metadata(self, seed_id):
        """
        Fetches metadata (Title, Year, ID, References) for a paper.
        Handles various input formats: IDs, DOIs, ArXiv IDs, or Search Queries.
        """
        
        # Heuristics: Guess what kind of ID the user provided.
        ids_to_try = [seed_id]
        
        # Case 1: Input looks like a DOI (e.g., "10.1145/1234.5678") but lacks the prefix.
        if "10." in seed_id and not seed_id.lower().startswith("doi:"):
            ids_to_try.append(f"DOI:{seed_id}")
            
        # Case 2: Input looks like an ArXiv ID (e.g., "1706.03762").
        if "arXiv" in seed_id and not seed_id.startswith("arXiv:"):
             clean_arxiv = seed_id.split("arXiv.")[-1] if "arXiv." in seed_id else seed_id
             ids_to_try.append(f"arXiv:{clean_arxiv}")

        # Case 3: Input looks like a Title (contains spaces, no slashes).
        if " " in seed_id and not "/" in seed_id:
             console.print(f"[cyan]Input looks like a title. Searching for '{seed_id}'...[/cyan]")
             found_paper = self.search_paper_by_title(seed_id)
             if found_paper:
                 return found_paper

        # Iterate through our guesses and try to fetch the paper.
        for pid in ids_to_try:
            try:
                # API Call to Semantic Scholar
                paper = self.sch.get_paper(pid)
                if paper:
                    # Data Normalization: Ensure 'openAccessPdf' field is accessible in a consistent way.
                    if not hasattr(paper, 'openAccessPdf') or not paper.openAccessPdf:
                         if isinstance(paper, dict) and 'openAccessPdf' in paper:
                             paper.openAccessPdf = paper['openAccessPdf']
                    return paper
            except Exception as e:
                # If a guess fails (e.g. invalid ID), silent ignore and try the next one.
                pass

        console.print(f"[bold red]Error: Could not resolve paper with IDs: {ids_to_try}[/bold red]")
        return None

    def search_paper_by_title(self, query):
        """
        Searches for a paper by its title.
        Uses a two-step strategy with fuzzy validation:
        1. ArXiv Search (Best for recent CS/AI papers).
        2. Semantic Scholar Search (General fallback).
        """
        from difflib import SequenceMatcher

        def is_similar(a, b):
            return SequenceMatcher(None, a.lower(), b.lower()).ratio() > 0.6

        # Strategy 1: ArXiv Search
        try:
            search = arxiv.Search(
                query=query,
                max_results=1,
                sort_by=arxiv.SortCriterion.Relevance
            )
            
            # Execute search
            results = list(search.results())
            if results:
                result = results[0]
                
                # Check Similarity
                if is_similar(query, result.title):
                    console.print(f"[green]Found via ArXiv: {result.title} ({result.published.year})[/green]")
                    
                    raw_id = result.entry_id.split('/')[-1]
                    paper_id = re.sub(r'v\d+$', '', raw_id) # Remove version (v1, v2)
                    
                    return self.get_paper_metadata(f"arXiv:{paper_id}")
                else:
                    console.print(f"[yellow]ArXiv match low confidence: '{result.title}' vs '{query}'. Skipping.[/yellow]")
                
        except Exception as e:
            console.print(f"[yellow]ArXiv search failed: {e}. Falling back to SS.[/yellow]")

        # Strategy 2: Semantic Scholar Search
        try:
            results = self.sch.search_paper(query, limit=1)
            if results and len(results) > 0:
                top_paper = results[0]
                # Check Similarity for SS as well to be safe
                if is_similar(query, top_paper.title):
                    console.print(f"[green]Found: {top_paper.title} ({top_paper.year})[/green]")
                    return top_paper
                else:
                    console.print(f"[red]Semantic Scholar match low confidence: '{top_paper.title}' vs '{query}'.[/red]")
        except Exception as e:
            console.print(f"[bold red]Search failed: {e}[/bold red]")
        return None

    def get_influential_references(self, seed_doi, limit=10):
        """
        The core of the "Research Context" logic.
        Fetches references for a paper and filters them to keep only the important ones.
        """
        console.print(f"[cyan]Fetching citation graph for {seed_doi}...[/cyan]")
        paper = self.get_paper_metadata(seed_doi)
        
        if not paper:
            return []

        influential_refs = []
        if paper.references:
            for ref in paper.references:
                # Semantic Scholar classifies some citations as "Influential"
                # (meaning the paper significantly builds upon or critiques the reference).
                if getattr(ref, 'isInfluential', False):
                    influential_refs.append(ref)
        
        # Sort candidates by Citation Count (proxy for impact)
        influential_refs.sort(key=lambda x: getattr(x, 'citationCount', 0) or 0, reverse=True)
        
        # Fail-safe:
        # If no "Influential" papers are marked (common for older or less parsed papers),
        # simply return the top N most cited references.
        if not influential_refs and paper.references:
            console.print("[yellow]No 'influential' citations marked. Falling back to top cited references.[/yellow]")
            all_refs = list(paper.references)
            all_refs.sort(key=lambda x: getattr(x, 'citationCount', 0) or 0, reverse=True)
            top_refs = all_refs[:limit]
        else:
            top_refs = influential_refs[:limit]
            
        console.print(f"[green]Found {len(top_refs)} references (limit {limit}).[/green]")
        return top_refs

    def get_citing_papers(self, seed_doi, limit=10):
        """
        Fetches papers that *cite* the seed paper (looking forward in time).
        Useful for finding newer work that builds upon the seed.
        """
        console.print(f"[cyan]Fetching incoming citations for {seed_doi}...[/cyan]")
        paper = self.get_paper_metadata(seed_doi)
        
        if not paper:
            return []

        citing_papers = []
        if paper.citations:
            for cit in paper.citations:
                # Similar logic: Prefer influential, but gather all candidates
                if getattr(cit, 'isInfluential', False):
                    citing_papers.append(cit)
        
        # Sort by Citation Count (find the most impactful newer papers)
        citing_papers.sort(key=lambda x: getattr(x, 'citationCount', 0) or 0, reverse=True)
        
        # Fallback to general citations if no influential ones found
        if not citing_papers and paper.citations:
            console.print("[yellow]No 'influential' incoming citations. Falling back to top citing papers.[/yellow]")
            all_cites = list(paper.citations)
            all_cites.sort(key=lambda x: getattr(x, 'citationCount', 0) or 0, reverse=True)
            top_cites = all_cites[:limit]
        else:
            top_cites = citing_papers[:limit]
            
        console.print(f"[green]Found {len(top_cites)} citing papers (limit {limit}).[/green]")
        return top_cites
