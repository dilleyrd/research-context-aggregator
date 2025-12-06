# Research Context Aggregator (RCA) 📚

**Accelerate your research by discovering and downloading influential context for a paper.**

RCA is a tool designed to take a "Seed Paper" (DOI, URL, or Title) and automatically discovery, filter, and retrieve the full text (PDFs) of its most influential references. It populates a local folder with these assets, ready for analysis in tools like **Google NotebookLM**.

## Features

*   **Smart Resolution**: Resolves papers by DOI, ArXiv ID, or Title Search.
*   **Influential Filtering**: Uses Semantic Scholar's graph to identify references that heavily influenced the seed paper, filtering out noise.
*   **Multi-Strategy Retrieval**:
    1.  **Semantic Scholar Direct**: Checks for direct Open Access PDF links.
    2.  **ArXiv Direct**: Automatically resolves and downloads from ArXiv if available.
    3.  **Agentic Fallback (Google Search)**: (Optional) Uses a custom search engine to find PDFs on the open web if standard APIs fail.
*   **Deep Research Prompt**: Generates a custom prompt to help you find high-quality missing sources using LLMs.
*   **Local Management**: Saves files to organized local folders for easy access.

## Installation

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/yourusername/research-context-aggregator.git
    cd research-context-aggregator
    ```

2.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Environment Setup**:
    Create a `.env` file in the root directory (see `.env.example` if available, or use the format below):
    ```env
    # Optional: For higher rate limits
    SEMANTIC_SCHOLAR_API_KEY=your_key_here
    
    # Optional: For Agentic Web Fallback
    GOOGLE_API_KEY=your_google_api_key
    GOOGLE_SEARCH_CX=your_search_engine_id
    ```

## Usage

Run the Streamlit application:

```bash
streamlit run src/app.py
```

1.  Enter your **Seed Paper** identifier.
2.  Adjust the number of references to fetch.
3.  Click **Generate Context**.
4.  Review the results table (sorted by missing items) and use the "Gemini Deep Research Prompt" for further analysis.
