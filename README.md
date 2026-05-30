# MCPChatbotForPapers

An MCP-based paper search chatbot that connects a Gemini client to local MCP tools for arXiv search and paper metadata lookup.

## What's Included

- `mcp_chatbot.py`: interactive chatbot that connects to configured MCP servers and routes tool calls through Gemini
- `research_server.py`: MCP server that searches arXiv and stores paper metadata locally
- `papers/`: generated cache of paper search results, grouped by topic
- `server_config.json`: MCP server launch configuration used by the chatbot

## Requirements

- Python 3.14 or newer
- `uv` installed locally
- A Google Gemini API key

## Quick Start

1. Clone the repo and enter the project directory.
2. Create a local `.env` file in the project root and add your Google API key.
3. Install dependencies with `uv sync`.
4. Start the research server.
5. Start the chatbot in a second terminal and ask a question.

```bash
git clone git@github.com:akhileshvj/MCPChatbotForPapers.git
cd MCPChatbotForPapers
uv sync
uv run python research_server.py
uv run python mcp_chatbot.py
```

## Initialize the Project

Clone the repository and move into it:

```bash
git clone git@github.com:akhileshvj/MCPChatbotForPapers.git
cd MCPChatbotForPapers
```

Create and use the virtual environment managed by `uv`:

```bash
uv sync
```

If you prefer to install from the pinned requirements file instead of `pyproject.toml`, use:

```bash
uv pip install -r requirements.txt
```

## Configure Environment Variables

Create a `.env` file in the project root and add your Gemini API key:

```env
GOOGLE_API_KEY=your_google_genai_api_key
```

Keep this file local. It is not meant to be pushed to GitHub.

The chatbot loads environment variables with `python-dotenv`.

## Install Dependencies

If you are starting from a clean environment, install the project dependencies with:

```bash
uv sync
```

That will install the packages listed in `pyproject.toml`, including:

- `google-genai`
- `mcp[cli]`
- `python-dotenv`
- `arxiv`
- `fastapi`
- `uvicorn`

## Run the MCP Research Server

The research server exposes the paper search tools over MCP stdio:

```bash
uv run python research_server.py
```

## Run the Chatbot

Start the interactive chatbot in a second terminal:

```bash
uv run python mcp_chatbot.py
```

The chatbot reads `server_config.json`, launches the configured MCP servers, and then waits for queries at the prompt.

## Example Usage

Inside the chatbot, try prompts like:

```text
Search papers about diffusion models
Find recent papers on quantum computing
Look up paper details for a saved paper ID
```

## How It Works

1. `mcp_chatbot.py` connects to the MCP servers listed in `server_config.json`.
2. Gemini receives the available tool schemas.
3. When Gemini requests a tool call, the chatbot routes it to the correct MCP server.
4. `research_server.py` searches arXiv and stores results under `papers/<topic>/papers_info.json`.

## Notes

- `papers/` is populated automatically when you run searches.
- If you change server commands in `server_config.json`, restart the chatbot so it reloads the config.
- The project currently uses local stdio-based MCP servers, so each server process must be runnable from the repository root.

## Troubleshooting

- If the chatbot cannot connect to Gemini, check that `GOOGLE_API_KEY` is set in `.env`.
- If `research_server.py` fails to start, make sure `arxiv` and `mcp` are installed in the active environment.
- If you see stale results, delete the relevant folder under `papers/` and run the search again.
