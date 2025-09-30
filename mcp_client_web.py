"""
MCP Client Web GUI Implementation
A web-based interface for the MCP client using Flask
"""

import asyncio
import os
from typing import Optional
from contextlib import AsyncExitStack
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import threading

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import OpenAI

app = Flask(__name__)
CORS(app)

# Global MCP client state
class MCPClientState:
    def __init__(self):
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.client = None
        self.available_tools = []
        self.connected = False
        self.loop = None
        self.chat_history = []

state = MCPClientState()


def start_async_loop():
    """Start asyncio event loop in background thread"""
    state.loop = asyncio.new_event_loop()
    asyncio.set_event_loop(state.loop)
    state.loop.run_forever()


# Start async loop
thread = threading.Thread(target=start_async_loop, daemon=True)
thread.start()


@app.route('/')
def index():
    """Render main page"""
    return render_template('index.html')


@app.route('/connect', methods=['POST'])
def connect():
    """Connect to MCP server"""
    if state.connected:
        return jsonify({'status': 'already_connected', 'message': 'Already connected to server'})

    future = asyncio.run_coroutine_threadsafe(connect_async(), state.loop)
    try:
        result = future.result(timeout=10)
        return jsonify(result)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})


async def connect_async():
    """Async connection to MCP server"""
    try:
        # Check for API key
        if not os.environ.get("OPENAI_API_KEY"):
            return {'status': 'error', 'message': 'OPENAI_API_KEY not found in environment'}

        # Initialize OpenAI client
        state.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

        # Get server script path
        server_script = os.environ.get(
            "MCP_SERVER_SCRIPT",
            "/Users/veeravelmanivannan/AI_projects/mcp_client/mcp_server.py"
        )

        # Connect to MCP server
        server_params = StdioServerParameters(
            command="python3",
            args=[server_script],
            env=None
        )

        stdio_transport = await state.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        stdio, write = stdio_transport
        state.session = await state.exit_stack.enter_async_context(
            ClientSession(stdio, write)
        )

        await state.session.initialize()

        # List available tools
        response = await state.session.list_tools()
        state.available_tools = response.tools

        state.connected = True

        tools_list = [{'name': tool.name, 'description': tool.description} for tool in state.available_tools]

        return {
            'status': 'success',
            'message': 'Connected to server',
            'tools': tools_list
        }

    except Exception as e:
        return {'status': 'error', 'message': str(e)}


@app.route('/send', methods=['POST'])
def send_message():
    """Send a message and get response"""
    if not state.connected:
        return jsonify({'status': 'error', 'message': 'Not connected to server'})

    data = request.json
    query = data.get('message', '')

    if not query:
        return jsonify({'status': 'error', 'message': 'Empty message'})

    # Add user message to history
    state.chat_history.append({'role': 'user', 'content': query})

    future = asyncio.run_coroutine_threadsafe(process_query_async(query), state.loop)
    try:
        result = future.result(timeout=60)
        return jsonify(result)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})


async def process_query_async(query: str):
    """Process a query using OpenAI and available MCP tools"""
    try:
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
            for tool in state.available_tools
        ]

        tool_executions = []

        # Agentic loop
        while True:
            response = state.client.chat.completions.create(
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
                # Add to chat history
                state.chat_history.append({'role': 'assistant', 'content': response_message.content})

                return {
                    'status': 'success',
                    'response': response_message.content,
                    'tool_executions': tool_executions
                }

            # Process tool calls
            for tool_call in response_message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = eval(tool_call.function.arguments)

                tool_executions.append({
                    'name': tool_name,
                    'arguments': tool_args
                })

                # Call the MCP tool
                result = await state.session.call_tool(tool_name, tool_args)

                # Add tool result to messages
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_name,
                    "content": str(result.content)
                })

    except Exception as e:
        return {'status': 'error', 'message': str(e)}


@app.route('/history', methods=['GET'])
def get_history():
    """Get chat history"""
    return jsonify({'history': state.chat_history})


@app.route('/status', methods=['GET'])
def get_status():
    """Get connection status"""
    return jsonify({
        'connected': state.connected,
        'tools_count': len(state.available_tools) if state.connected else 0
    })


if __name__ == '__main__':
    print("\n" + "="*60)
    print("MCP Client Web Interface")
    print("="*60)
    print("\nStarting server on http://localhost:5001")
    print("Open this URL in your web browser to use the client\n")
    print("Press Ctrl+C to stop the server")
    print("="*60 + "\n")

    app.run(debug=True, host='0.0.0.0', port=5001, use_reloader=False)
