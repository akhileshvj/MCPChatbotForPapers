import os
import sys
import arxiv
import json
import warnings
import time
from typing import List
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP 

# Silence any mixed-content warnings
warnings.filterwarnings("ignore", message=".*non-text parts in the response.*")

# Initialize FastMCP
mcp = FastMCP("research")
PAPER_DIR = "papers"

load_dotenv() 

@mcp.tool()
def search_papers(topic: str, max_results: int = 5) -> str:
    """
    Search for papers on arXiv based on a topic and store their information.
    """
    # 2. Add an explicit client-side pace delay.
    # arXiv's Terms of Use strictly request a 3-second delay between access attempts.
    print(f"[Pacing] Pausing for 3 seconds to protect arXiv rate limits...", file=sys.stderr)
    time.sleep(3.0)

    arxiv_client = arxiv.Client()

    search = arxiv.Search(
        query=topic,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.Relevance
    )

    try:
        papers = arxiv_client.results(search)
        
        path = os.path.join(PAPER_DIR, topic.lower().replace(" ", "_"))
        os.makedirs(path, exist_ok=True)
        file_path = os.path.join(path, "papers_info.json")

        try:
            with open(file_path, "r") as json_file:
                papers_info = json.load(json_file)
        except (FileNotFoundError, json.JSONDecodeError):
            papers_info = {}

        current_search_results = {}
        for paper in papers:
            short_id = paper.get_short_id()
            paper_info = {
                'title': paper.title,
                'authors': [author.name for author in paper.authors],
                'summary': paper.summary,
                'pdf_url': paper.pdf_url,
                'published': str(paper.published.date())
            }
            papers_info[short_id] = paper_info
            current_search_results[short_id] = paper_info
        
        with open(file_path, "w") as json_file:
            json.dump(papers_info, json_file, indent=2)
        
        print(f"[Tool Activity] Results saved to {file_path}", file=sys.stderr)
        return json.dumps(current_search_results, indent=2)

    except Exception as e:
        # Catch the 429 natively and report it gracefully back to Gemini
        error_msg = f"arXiv Search failed due to rate limits or connectivity issues: {str(e)}"
        print(f"[Error] {error_msg}", file=sys.stderr)
        return json.dumps({"error": error_msg})

@mcp.tool()
def extract_info(paper_id: str) -> str:
    """
    Search for stored local information about a specific paper by its ID.
    
    Args:
        paper_id: The unique short ID of the paper.
    """
    if not os.path.exists(PAPER_DIR):
        return f"There's no saved information related to paper {paper_id}."

    for item in os.listdir(PAPER_DIR):
        item_path = os.path.join(PAPER_DIR, item)
        if os.path.isdir(item_path):
            file_path = os.path.join(item_path, "papers_info.json")
            if os.path.isfile(file_path):
                try:
                    with open(file_path, "r") as json_file:
                        papers_info = json.load(json_file)
                        if paper_id in papers_info:
                            return json.dumps(papers_info[paper_id], indent=2)
                except (FileNotFoundError, json.JSONDecodeError) as e:
                    print(f"Error reading {file_path}: {str(e)}", file=sys.stderr)
                    continue
    
    return f"There's no saved information related to paper {paper_id}."

if __name__ == "__main__":
    # FastMCP uses stdio transport by default on run()
    mcp.run()