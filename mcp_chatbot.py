import os
import json
import asyncio
import warnings
from typing import List, Dict
from contextlib import AsyncExitStack
from dotenv import load_dotenv

# Import Google GenAI SDK
from google import genai
from google.genai import types

# Import MCP client capabilities
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Silence mixed-content accessor logs since we handle parts manually
warnings.filterwarnings("ignore", message=".*non-text parts in the response.*")

load_dotenv()

class MCP_ChatBot:

    def __init__(self):
        # Multi-server session tracking hooks
        self.sessions: List[ClientSession] = []
        self.exit_stack = AsyncExitStack()
        
        # Initialize Google GenAI client
        self.client = genai.Client()
        self.available_tools: List[dict] = []
        self.tool_to_session: Dict[str, ClientSession] = {}
        
        # Maintain conversation context dynamically across user turns
        self.chat_history: List[types.Content] = []

    async def connect_to_server(self, server_name: str, server_config: dict) -> None:
        """Connect to a single MCP server process and ingest its capabilities."""
        try:
            server_params = StdioServerParameters(**server_config)
            stdio_transport = await self.exit_stack.enter_async_context(
                stdio_client(server_params)
            )
            read, write = stdio_transport
            session = await self.exit_stack.enter_async_context(
                ClientSession(read, write)
            )
            await session.initialize()
            self.sessions.append(session)
            
            # Request tools from this specific background process
            response = await session.list_tools()
            tools = response.tools
            print(f"\nConnected to {server_name} with tools:", [t.name for t in tools])
            
            # Translate and index tool execution nodes
            for tool in tools:
                self.tool_to_session[tool.name] = session
                
                # --- CLEAN SCHEMA CLEANUP FOR GEMINI ---
                # Deep copy the input schema so we don't mutate the original reference
                clean_parameters = json.loads(json.dumps(tool.inputSchema))
                
                # 1. Strip top-level schema validation identifiers that break Pydantic
                if "$schema" in clean_parameters:
                    del clean_parameters["$schema"]
                    
                # 2. Strip draft-specific property limits from nested objects if present
                if "properties" in clean_parameters:
                    for prop_name, prop_data in clean_parameters["properties"].items():
                        if isinstance(prop_data, dict):
                            prop_data.pop("exclusiveMaximum", None)
                            prop_data.pop("exclusiveMinimum", None)
                
                # Format into a clean declaration object that Gemini expects
                gemini_tool_format = {
                    "function_declarations": [
                        {
                            "name": tool.name,
                            "description": tool.description,
                            "parameters": clean_parameters
                        }
                    ]
                }
                self.available_tools.append(gemini_tool_format)
                
        except Exception as e:
            print(f"Failed to connect to {server_name}: {e}")

    async def connect_to_servers(self):
        """Load composition maps and boot all registered MCP micro-servers."""
        try:
            with open("server_config.json", "r") as file:
                data = json.load(file)
            
            servers = data.get("mcpServers", {})
            for server_name, server_config in servers.items():
                await self.connect_to_server(server_name, server_config)
        except Exception as e:
            print(f"Error loading server configuration: {e}")
            raise

    async def process_query(self, query: str):
        """
        Processes inquiries against active tool-declarations, handling multi-turn 
        context memory and catching background server pipe crashes gracefully.
        """
        # 1. Append the incoming user inquiry to the global context array
        self.chat_history.append(
            types.Content(role="user", parts=[types.Part.from_text(text=query)])
        )
        
        process_query = True
        while process_query:
            # Send the complete history stack to Gemini (Synchronous SDK Call)
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=self.chat_history,
                config=types.GenerateContentConfig(
                    tools=self.available_tools, # Dynamic schemas with stripped metadata
                    temperature=0.3
                )
            )
            
            # Save Gemini's structural response block into the session history
            if response.candidates and response.candidates[0].content:
                model_content = response.candidates[0].content
                self.chat_history.append(model_content)
            
            # 2. Check if Gemini wants to invoke one or more MCP tools
            if response.function_calls:
                tool_results_parts = []
                
                for call in response.function_calls:
                    print(f"Calling tool {call.name} with args {call.args}")
                    
                    # Look up which server instance handles this tool
                    session = self.tool_to_session.get(call.name)
                    if not session:
                        text_content = f"Error: No active MCP server found handling tool '{call.name}'."
                    else:
                        try:
                            # Execute across the active async stdio connection pipe
                            mcp_result = await session.call_tool(call.name, arguments=call.args)
                            
                            # Consolidate multiline content blocks returned from the server
                            text_content = ""
                            for content_item in mcp_result.content:
                                if hasattr(content_item, 'text'):
                                    text_content += content_item.text
                        except Exception as tool_error:
                            # Catch crashes, timeouts, or JSON-RPC pipe EOF errors cleanly
                            text_content = f"Tool execution failed on the server side: {str(tool_error)}"
                    
                    # Package the result text into the specific schema format Gemini expects
                    tool_results_parts.append(
                        types.Part.from_function_response(
                            name=call.name,
                            response={"result": text_content}
                        )
                    )
                
                # Append the tool execution results back to history under 'user' role
                self.chat_history.append(
                    types.Content(role="user", parts=tool_results_parts)
                )
                # Keep the while loop active to send the tool output back into Gemini's context window
                continue
            else:
                # No tool execution requested; output the final synthesized text answer
                if response.text:
                    print(response.text)
                process_query = False

    async def get_user_input(self) -> str:
        """Safely isolate blocking standard console input from asynchronous loops."""
        return await asyncio.to_thread(input, "\nQuery: ")

    async def chat_loop(self):
        """Run standard interactive loop on primary async task runner paths."""
        print("\nMCP Gemini Multi-Server Chatbot Started!")
        print("Type your queries or 'quit' to exit.")
        
        while True:
            try:
                query = await self.get_user_input()
                query = query.strip()
                
                if not query:
                    continue
                if query.lower() == 'quit':
                    break
                    
                await self.process_query(query)
                print("\n")
                    
            except Exception as e:
                print(f"\nError: {str(e)}")

    async def cleanup(self):
        """Cleanly close all tracked subprocess configurations via AsyncExitStack."""
        await self.exit_stack.aclose()


async def main():
    chatbot = MCP_ChatBot()
    try:
        await chatbot.connect_to_servers()
        await chatbot.chat_loop()
    finally:
        print("\nShutting down backend servers...")
        await chatbot.cleanup()


if __name__ == "__main__":
    asyncio.run(main())