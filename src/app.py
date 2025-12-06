import streamlit as st
import os
import sys
import subprocess
from dotenv import load_dotenv

# Import custom modules responsible for specific tasks
from modules.citation_graph import CitationGraph        # Handles citation graph retrieval from Semantic Scholar    
from modules.asset_retriever import AssetRetriever      # Handles PDF retrieval from Semantic Scholar
from modules.web_retriever import GoogleWebRetriever    # Handles web retrieval from Google
from modules.file_manager import FileManager            # Handles file management

# Ensure we can import modules from the parent directory if running from a different context
# This adds the parent directory to the system path, allowing Python to find our 'modules' folder.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load environment variables from the .env file
# This is a safe way to handle sensitive keys (like API keys) without hardcoding them.
load_dotenv()

# --- Application Configuration ---
# Sets the browser tab title and favicon. Must be the first Streamlit command.
st.set_page_config(page_title="Research Context Aggregator", page_icon="📚")

# Display the main title and description on the web page.
st.title("Research Context Aggregator (RCA) 📚")
st.markdown("""
Accelerate your research by discovering and downloading influential context for a paper.
Enter a **DOI**, **URL**, or **Paper Title**.
""")

# --- Sidebar Configuration ---
# The sidebar contains settings that remain accessible while scrolling the main content.
st.sidebar.header("Configuration")

# Input for Semantic Scholar API Key
# We use 'type="password"' to mask the input.
api_key_input = st.sidebar.text_input("Semantic Scholar API Key", value=os.getenv("SEMANTIC_SCHOLAR_API_KEY", ""), type="password")

# Slider to determine how many influential references to fetch (Limit: 1-50)
limit = st.sidebar.slider("Influential References", min_value=1, max_value=50, value=10)

# ResearchRabbit Adaptation: Future Context
# Toggle to include papers that cite the seed paper (Forward lookup)
include_citations = st.sidebar.checkbox("Include Incoming Citations", value=False, help="Find newer papers that cite this work.")

st.sidebar.divider()
st.sidebar.subheader("Agentic Search (Optional)")
# Inputs for Google Custom Search to enable "Agentic Fallback" mode
google_api_key = st.sidebar.text_input("Google API Key", value=os.getenv("GOOGLE_API_KEY", ""), type="password")
google_cx = st.sidebar.text_input("Google Search CX", value=os.getenv("GOOGLE_SEARCH_CX", ""), help="Search Engine ID")

# --- Main Input Section ---
# Text box for the user to enter the seed paper identifier.
query = st.text_input("Seed Paper (DOI, URL, or Title)", placeholder="e.g. Attention Is All You Need")
# Button to trigger the process.
# Button to trigger the process.
find_btn = st.button("Find Paper")

# --- State Management ---
if 'results_data' not in st.session_state:
    st.session_state.results_data = None
if 'output_dir' not in st.session_state:
    st.session_state.output_dir = None
if 'candidate_paper' not in st.session_state:
    st.session_state.candidate_paper = None

# --- Step 1: Find Paper ---
if find_btn and query:
    safe_api_key = api_key_input if api_key_input and api_key_input.strip() else None
    
    with st.spinner("Resolving Paper..."):
        try:
            graph = CitationGraph(api_key=safe_api_key)
            candidate = graph.get_paper_metadata(query)
            
            if candidate:
                st.session_state.candidate_paper = candidate
                # Reset previous results to avoid confusion
                st.session_state.results_data = None
                st.session_state.output_dir = None
            else:
                st.error(f"Could not resolve paper for: {query}")
        except Exception as e:
            st.error(f"Error resolving paper: {e}")

# --- Step 2: Confirm & Process ---
if st.session_state.candidate_paper:
    candidate = st.session_state.candidate_paper
    
    # Display Candidate Details for Confirmation
    st.divider()
    st.subheader("Did you mean this paper?")
    
    c1, c2 = st.columns([3, 1])
    with c1:
        st.markdown(f"**Title**: {candidate.title}")
        st.markdown(f"**Year**: {candidate.year}")
        if hasattr(candidate, 'abstract') and candidate.abstract:
             st.caption(f"{candidate.abstract[:300]}...")
    with c2:
        confirm_btn = st.button("Confirm & Generate Context", type="primary")

    if confirm_btn:
        primary_paper = candidate
        safe_api_key = api_key_input if api_key_input and api_key_input.strip() else None
        
        try:
            # Initialize our helper classes with the provided keys
            graph = CitationGraph(api_key=safe_api_key)
            retriever = AssetRetriever()
            file_manager = FileManager()
            
            # Initialize Web Retriever only if both Google keys are provided
            web_retriever = None
            if google_api_key and google_cx:
                 web_retriever = GoogleWebRetriever(api_key=google_api_key, cx=google_cx)
            
            # Create UI placeholders for status updates and logs
            status_container = st.empty()
            progress_bar = st.progress(0)
            log_area = st.empty()
            logs = []
            
            # Helper function to print logs to the UI in real-time
            def log(msg):
                logs.append(msg)
                # Keeping only last 10 logs for a cleaner UI
                log_area.code("\n".join(logs[-10:]))

            st.success(f"Confirmed: {primary_paper.title}")
            log(f"Confirmed: {primary_paper.title}")

            # 2. Fetch Citation Graph
            # We ask Semantic Scholar for papers that this paper cites heavily ("Influential Citations").
            status_container.info("Fetching Citation Graph...")
            # We need the 'paperId' to request references.
            references = graph.get_influential_references(getattr(primary_paper, 'paperId', None), limit=limit)
            
            # The list of target papers includes the seed paper itself + its references.
            targets = [primary_paper] + references
            
            # --- Future Context (Forward Citations) ---
            if include_citations:
                status_container.info("Fetching Incoming Citations (Future Context)...")
                # We limit forward citations to 50% of the reference limit to keep things balanced, 
                # or just use the same limit. Let's use the same limit for simplicity.
                citations = graph.get_citing_papers(getattr(primary_paper, 'paperId', None), limit=limit)
                targets += citations
                
            log(f"Found {len(targets)} targets total.")

            # Prepare Output Directory
            # We create a local folder named after the paper to store PDFs.
            folder_title = f"[{primary_paper.year}] {primary_paper.title}"
            output_dir = file_manager.create_project_folder(folder_title)
            
            # Save the directory path to session state so we can open it later
            st.session_state.output_dir = output_dir

            # 3. Main Download Loop
            results_data = []
            total = len(targets)
            
            # Iterate through each target paper to attempt download
            for i, paper in enumerate(targets):
                status_container.info(f"Processing {i+1}/{total}...")
                progress_bar.progress((i + 1) / total)

                # Safely get title and year, defaulting if missing
                title = getattr(paper, 'title', 'Unknown')
                year = getattr(paper, 'year', '0000')
                
                # --- Identifier Extraction ---
                # We try to find DOI and ArXiv IDs to help us locate the PDF.
                doi = None
                arxiv_id = None
                direct_pdf_url = None

                # Check 1: Does Semantic Scholar provide a direct Open Access PDF link?
                if hasattr(paper, 'openAccessPdf') and paper.openAccessPdf:
                    direct_pdf_url = paper.openAccessPdf.get('url')
                elif isinstance(paper, dict) and 'openAccessPdf' in paper:
                        # Handle case where 'paper' is a raw dictionary instead of an object
                        direct_pdf_url = paper['openAccessPdf'].get('url')

                # Check 2: Extract External IDs (DOI, ArXiv) from object properties
                if hasattr(paper, 'externalIds') and paper.externalIds:
                    doi = paper.externalIds.get('DOI')
                    arxiv_id = paper.externalIds.get('ArXiv')
                
                # Fallback: Check top-level 'doi' attribute
                if not doi and hasattr(paper, 'doi'):
                    doi = paper.doi
                
                # Fallback: Case-insensitive search for ArXiv ID in externalIds
                if not arxiv_id and hasattr(paper, 'externalIds') and paper.externalIds:
                        for k, v in paper.externalIds.items():
                            if k.lower() == 'arxiv':
                                arxiv_id = v
                                break

                # Fallback: Dictionary access if the object is just a dict
                if not doi and isinstance(paper, dict):
                        doi = paper.get('externalIds', {}).get('DOI') or paper.get('doi')
                        arxiv_id = paper.get('externalIds', {}).get('ArXiv')
                
                # Create a safe filename (removing illegal characters)
                safe_title = file_manager.sanitize_filename(title)
                filename = f"[{year}] {safe_title}.pdf"
                pdf_path = os.path.join(output_dir, filename)
                
                status = "Skipped"

                # --- Download Strategy ---
                if os.path.exists(pdf_path):
                        status = "Exists"
                        log(f"Exists: {title}")
                
                else:
                    success = False
                    
                    # Strategy 1: Direct Link from Semantic Scholar (Fastest/Best)
                    if direct_pdf_url:
                            if retriever.download_pdf(direct_pdf_url, pdf_path):
                                status = "Downloaded (SS)"
                                log(f"Downloaded (SS): {title}")
                                success = True

                    # Strategy 2: Direct ArXiv Download (Reliable for CS/Math papers)
                    if not success and arxiv_id:
                        if retriever.download_from_arxiv(arxiv_id, pdf_path):
                            status = "Downloaded (ArXiv)"
                            log(f"Downloaded (ArXiv): {title}")
                            success = True
                            
                    # Strategy 3: Agentic Web Search (Last Resort)
                    # If enabled, uses Google to search the web for the PDF file.
                    if not success and web_retriever:
                         # Only search if title is valid
                         if title and title != "Unknown":
                              pdf_url = web_retriever.search_pdf(title)
                              if pdf_url:
                                   if retriever.download_pdf(pdf_url, pdf_path):
                                        status = "Downloaded (Web)"
                                        log(f"Downloaded (Web): {title}")
                                        success = True
                    
                    # Failure Case: Check if we can just save the abstract
                    if not success:
                        log_msg = f"No Access: {title}"
                        log(log_msg)
                        
                        abstract = getattr(paper, 'abstract', None)
                        if abstract:
                            abs_filename = f"[{year}] {safe_title} (Abstract).txt"
                            file_manager.save_text(abstract, output_dir, abs_filename)
                            status = "Abstract Only"
                        else:
                            status = "Missing"

                # --- Link Generation for Manual Fallback ---
                # If we couldn't download it, provide a link so the user can find it manually.
                display_url = None
                if "Downloaded" not in status and "Exists" not in status:
                    display_url = getattr(paper, 'url', None)
                    if not display_url and doi:
                        display_url = f"https://doi.org/{doi}"
                    if not display_url and arxiv_id:
                            display_url = f"https://arxiv.org/abs/{arxiv_id}"

                results_data.append({
                    "Title": title,
                    "Year": year,
                    "Status": status,
                    "Link": display_url
                })

            # --- 4. Metadata Generation (New Phase) ---
            # We crate a 'metadata.md' file that summarizes all the papers.
            # This is critical for NotebookLM, as it gives the AI access to Abstracts
            # and Citation Counts even if the PDF failed to download.
            status_container.info("Generating Metadata Summary...")
            
            md_content = f"# Research Context: {primary_paper.title}\n\n"
            md_content += f"**Seed Paper**: {primary_paper.title} ({primary_paper.year})\n"
            md_content += f"**Generated**: {len(targets)} papers processed.\n\n"
            md_content += "---\n\n"
            
            # Initialize BibTeX content
            bib_content = ""
            
            for paper in targets:
                # Extract details
                p_title = getattr(paper, 'title', 'Unknown Title')
                p_year = getattr(paper, 'year', '????')
                p_venue = getattr(paper, 'venue', 'Unknown Venue')
                p_citations = getattr(paper, 'citationCount', 0)
                p_abstract = getattr(paper, 'abstract', None)
                p_authors = getattr(paper, 'authors', [])
                
                # Check if we downloaded it (by checking the list we just built)
                # We simply check if the status in our results_data says "Downloaded" or "Exists"
                # (A bit inefficient to loop again, but safe and clear)
                p_status = "Missing"
                for res in results_data:
                    if res['Title'] == p_title:
                        p_status = res['Status']
                        break
                
                md_content += f"## {p_title} ({p_year})\n"
                md_content += f"- **Citations**: {p_citations}\n"
                md_content += f"- **Venue**: {p_venue}\n"
                md_content += f"- **Status**: {p_status}\n"
                
                if p_abstract:
                    md_content += f"- **Abstract**:\n> {p_abstract}\n"
                else:
                    md_content += f"- **Abstract**: (Not available)\n"
                
                md_content += "\n---\n\n"
                
                # --- BibTeX Entry Construction ---
                # A heuristic approach to generating BibTeX
                clean_title = p_title.replace("{", "").replace("}", "")
                slug = safe_title.split(' ')[0] + str(p_year) # e.g. Attention2017
                
                # Format authors list
                author_list = []
                for a in p_authors:
                    if isinstance(a, dict):
                        author_list.append(a.get('name', ''))
                    else:
                        author_list.append(getattr(a, 'name', ''))
                author_str = " and ".join(filter(None, author_list)) if author_list else "Unknown"
                
                bib_entry = f"@article{{{slug},\n"
                bib_entry += f"  title = {{{clean_title}}},\n"
                bib_entry += f"  author = {{{author_str}}},\n"
                bib_entry += f"  year = {{{p_year}}},\n"
                bib_entry += f"  journal = {{{p_venue}}},\n"
                bib_entry += f"  note = {{Citations: {p_citations}}}\n"
                bib_entry += "}\n\n"
                
                bib_content += bib_entry
                
            file_manager.save_text(md_content, output_dir, "metadata.md")
            file_manager.save_text(bib_content, output_dir, "references.bib")
            log(f"Generated: metadata.md & references.bib")

            # --- Sorting Results ---
            # We sort the table to show actionable items first:
            # 1. Items with a "Link" (Manual download needed)
            # 2. Items with "Missing" status
            results_data.sort(key=lambda x: (x.get('Link') is not None, x.get('Status') == 'Missing'), reverse=True)

            status_container.success("Complete!")
            st.session_state.results_data = results_data
            
            # Save the primary title for generating the AI prompt later
            st.session_state.primary_title = primary_paper.title

        except Exception as e:
            st.error(f"An error occurred: {e}")


# --- Results Display (Persistent) ---
# This block runs on every re-run if we have data in the session state.
if st.session_state.results_data:
    st.divider()
    st.subheader("Results")
    
    # Display an interactive dataframe
    # LinkColumn turns the URL into a clickable "Open" button.
    st.dataframe(
        st.session_state.results_data,
        column_config={
            "Link": st.column_config.LinkColumn("Manual Link", display_text="Open"),
            "Title": st.column_config.TextColumn("Title", width="large"),
            "Status": st.column_config.TextColumn("Status", width="small")
        },
        hide_index=True,
        use_container_width=True
    )

    # Show the local folder path and a button to open it (Windows friendly)
    if st.session_state.output_dir:
        st.success(f"Files saved to: `{st.session_state.output_dir}`")
        if sys.platform == 'win32':
            if st.button("Open Output Folder"):
                os.startfile(st.session_state.output_dir)

        # --- Zotero Adaptation: BibTeX Export ---
        # Create a simple .bib file for direct import into reference managers
        bib_path = os.path.join(st.session_state.output_dir, "references.bib")
        # We generate this file during the main loop, but we can also just confirm it here
        if os.path.exists(bib_path):
             st.info("`references.bib` created. Drag this file into Zotero to import all metadata.")

    # --- Gemini Deep Research Prompt ---
    # Generates a text block that users can copy to continue their research with AI tools.
    st.divider()
    st.subheader("Gemini Deep Research Prompt")
    st.markdown("Copy this to **NotebookLM** or **Gemini** to find missing sources.")
    
    seed_title = st.session_state.get('primary_title', 'this paper')
    prompt_text = f"""I am analyzing the paper '{seed_title}'. 

Please use your deep research capabilities to fill in possible gaps in context and identify high-quality sources that may not have been included in the references. 

The goal is to get a comprehensive and robust representation of the topic documented in the paper for complete understanding of the associated research."""

    st.code(prompt_text, language="text")
