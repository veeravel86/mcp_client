"""
MCP Client Implementation
A Python client for connecting to Model Context Protocol servers
"""

import asyncio
import os
from typing import Optional
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import OpenAI

class MCPClient:
    def __init__(self):
        """Initialize the MCP client"""
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.available_tools = []

    async def connect_to_server(self, server_script_path: str):
        """Connect to an MCP server

        Args:
            server_script_path: Path to the server script
        """
        server_params = StdioServerParameters(
            command="python3",
            args=[server_script_path],
            env=None
        )

        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(self.stdio, self.write)
        )

        await self.session.initialize()

        # List available tools
        response = await self.session.list_tools()
        self.available_tools = response.tools
        print(f"\nConnected to server with {len(self.available_tools)} tools:")
        for tool in self.available_tools:
            print(f"  - {tool.name}: {tool.description}")

    async def process_query(self, query: str) -> str:
        """Process a query using OpenAI and available MCP tools

        Args:
            query: The user's query

        Returns:
            The response from OpenAI
        """
        messages = [
            {
                "role": "user",
                "content": query
            }
        ]

        # Convert MCP tools to OpenAI tool format
        tools = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.inputSchema
                }
            }
            for tool in self.available_tools
        ]

        # Agentic loop
        while True:
            response = self.client.chat.completions.create(
                model="gpt-4-turbo-preview",
                max_tokens=4096,
                messages=messages,
                tools=tools if tools else None
            )

            response_message = response.choices[0].message

            # Add assistant response to messages
            messages.append(response_message)

            # Check if we're done (no tool calls)
            if not response_message.tool_calls:
                return response_message.content

            # Process tool calls
            for tool_call in response_message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = eval(tool_call.function.arguments)

                print(f"\nExecuting tool: {tool_name}")
                print(f"Arguments: {tool_args}")

                # Call the MCP tool
                result = await self.session.call_tool(tool_name, tool_args)

                # Add tool result to messages
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_name,
                    "content": str(result.content)
                })

    async def chat_loop(self):
        """Run an interactive chat loop"""
        print("\nMCP Client Started!")
        print("Type your queries or 'quit' to exit.\n")

        while True:
            try:
                query = input("You: ").strip()

                if query.lower() in ['quit', 'exit', 'q']:
                    break

                if not query:
                    continue

                response = await self.process_query(query)
                print(f"\nAssistant: {response}\n")

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"\nError: {e}\n")

    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()


async def main():
    """Main entry point"""
    if not os.environ.get("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY environment variable is required")

    # You can modify this to point to your MCP server
    server_script = os.environ.get("MCP_SERVER_SCRIPT", "server.py")

    client = MCPClient()

    try:
        await client.connect_to_server(server_script)
        await client.chat_loop()
    finally:
        await client.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
