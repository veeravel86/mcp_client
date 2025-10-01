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
        self.servers = {}  # server_name -> {session, exit_stack, tools}
        self.client = None
        self.available_tools = []  # Combined tools from all servers
        self.connected_servers = []
        self.loop = None
        self.chat_history = []
        self.logs = []
        self.server_configs = []  # List of configured servers

    def add_log(self, log_type: str, message: str, data: any = None):
        """Add a log entry"""
        import datetime
        log_entry = {
            'timestamp': datetime.datetime.now().isoformat(),
            'type': log_type,
            'message': message,
            'data': data
        }
        self.logs.append(log_entry)

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


@app.route('/servers', methods=['GET'])
def get_servers():
    """Get list of configured servers"""
    return jsonify({'servers': state.server_configs})


@app.route('/servers/add', methods=['POST'])
def add_server():
    """Add a new MCP server configuration"""
    data = request.json
    server_name = data.get('name')
    server_command = data.get('command')
    server_args = data.get('args', [])

    if not server_name or not server_command:
        return jsonify({'status': 'error', 'message': 'Name and command are required'})

    # Check if server already exists
    if any(s['name'] == server_name for s in state.server_configs):
        return jsonify({'status': 'error', 'message': 'Server with this name already exists'})

    server_config = {
        'name': server_name,
        'command': server_command,
        'args': server_args,
        'connected': False
    }

    state.server_configs.append(server_config)
    state.add_log('system', f'Added server configuration: {server_name}', server_config)

    return jsonify({'status': 'success', 'message': f'Server {server_name} added'})


@app.route('/servers/remove', methods=['POST'])
def remove_server():
    """Remove a server configuration"""
    data = request.json
    server_name = data.get('name')

    state.server_configs = [s for s in state.server_configs if s['name'] != server_name]

    # Disconnect if connected
    if server_name in state.servers:
        future = asyncio.run_coroutine_threadsafe(
            disconnect_server_async(server_name), state.loop
        )
        future.result(timeout=5)

    state.add_log('system', f'Removed server configuration: {server_name}')
    return jsonify({'status': 'success', 'message': f'Server {server_name} removed'})


@app.route('/servers/connect', methods=['POST'])
def connect_server():
    """Connect to a specific MCP server"""
    data = request.json
    server_name = data.get('name')

    if not server_name:
        return jsonify({'status': 'error', 'message': 'Server name is required'})

    server_config = next((s for s in state.server_configs if s['name'] == server_name), None)
    if not server_config:
        return jsonify({'status': 'error', 'message': 'Server not found'})

    future = asyncio.run_coroutine_threadsafe(
        connect_server_async(server_config), state.loop
    )
    try:
        result = future.result(timeout=10)
        return jsonify(result)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})


@app.route('/servers/disconnect', methods=['POST'])
def disconnect_server():
    """Disconnect from a specific server"""
    data = request.json
    server_name = data.get('name')

    future = asyncio.run_coroutine_threadsafe(
        disconnect_server_async(server_name), state.loop
    )
    try:
        result = future.result(timeout=5)
        return jsonify(result)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})


@app.route('/connect', methods=['POST'])
def connect():
    """Connect to all configured MCP servers"""
    future = asyncio.run_coroutine_threadsafe(connect_all_async(), state.loop)
    try:
        result = future.result(timeout=30)
        return jsonify(result)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})


async def connect_server_async(server_config: dict):
    """Connect to a specific MCP server"""
    try:
        server_name = server_config['name']
        state.add_log('system', f'Connecting to server: {server_name}')

        # Create exit stack for this server
        exit_stack = AsyncExitStack()

        # Connect to MCP server
        server_params = StdioServerParameters(
            command=server_config['command'],
            args=server_config['args'],
            env=None
        )

        stdio_transport = await exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        stdio, write = stdio_transport
        session = await exit_stack.enter_async_context(
            ClientSession(stdio, write)
        )

        await session.initialize()
        state.add_log('mcp_server', f'{server_name}: Session initialized')

        # List available tools
        response = await session.list_tools()
        tools = response.tools

        # Log complete tool schemas
        tools_with_schemas = [
            {
                'name': tool.name,
                'description': tool.description,
                'inputSchema': tool.inputSchema,
                'server': server_name
            } for tool in tools
        ]
        state.add_log('mcp_server', f'{server_name}: Received {len(tools)} tools',
                     {'tools': tools_with_schemas})

        # Store server info
        state.servers[server_name] = {
            'session': session,
            'exit_stack': exit_stack,
            'tools': tools,
            'config': server_config
        }

        # Update server config status
        for config in state.server_configs:
            if config['name'] == server_name:
                config['connected'] = True

        if server_name not in state.connected_servers:
            state.connected_servers.append(server_name)

        # Rebuild combined tools list
        rebuild_tools_list()

        return {
            'status': 'success',
            'message': f'Connected to {server_name}',
            'server': server_name,
            'tool_count': len(tools)
        }

    except Exception as e:
        state.add_log('error', f'Failed to connect to {server_name}: {str(e)}')
        return {'status': 'error', 'message': str(e)}


async def disconnect_server_async(server_name: str):
    """Disconnect from a specific server"""
    try:
        if server_name in state.servers:
            await state.servers[server_name]['exit_stack'].aclose()
            del state.servers[server_name]

            if server_name in state.connected_servers:
                state.connected_servers.remove(server_name)

            # Update server config status
            for config in state.server_configs:
                if config['name'] == server_name:
                    config['connected'] = False

            # Rebuild combined tools list
            rebuild_tools_list()

            state.add_log('system', f'Disconnected from {server_name}')
            return {'status': 'success', 'message': f'Disconnected from {server_name}'}
        else:
            return {'status': 'error', 'message': 'Server not connected'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


async def connect_all_async():
    """Connect to all configured servers"""
    try:
        # Check for API key
        if not os.environ.get("OPENAI_API_KEY"):
            state.add_log('error', 'OPENAI_API_KEY not found in environment')
            return {'status': 'error', 'message': 'OPENAI_API_KEY not found in environment'}

        # Initialize OpenAI client if not already done
        if not state.client:
            state.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
            state.add_log('system', 'OpenAI client initialized')

        # If no servers configured, add default
        if not state.server_configs:
            default_server = {
                'name': 'default',
                'command': 'python3',
                'args': [os.environ.get("MCP_SERVER_SCRIPT",
                        "/Users/veeravelmanivannan/AI_projects/mcp_client/mcp_server.py")],
                'connected': False
            }
            state.server_configs.append(default_server)

        # Connect to all servers
        results = []
        for server_config in state.server_configs:
            if not server_config['connected']:
                result = await connect_server_async(server_config)
                results.append(result)

        state.add_log('system', f'Connected to {len(state.connected_servers)} servers')

        return {
            'status': 'success',
            'message': f'Connected to {len(state.connected_servers)} servers',
            'servers': state.connected_servers,
            'total_tools': len(state.available_tools)
        }

    except Exception as e:
        state.add_log('error', f'Connection failed: {str(e)}')
        return {'status': 'error', 'message': str(e)}


def rebuild_tools_list():
    """Rebuild the combined tools list from all connected servers"""
    state.available_tools = []
    for server_name, server_info in state.servers.items():
        # Add server name to each tool for tracking
        for tool in server_info['tools']:
            tool.server_name = server_name  # Track which server provides this tool
            state.available_tools.append(tool)


@app.route('/send', methods=['POST'])
def send_message():
    """Send a message and get response"""
    if len(state.connected_servers) == 0:
        return jsonify({'status': 'error', 'message': 'Not connected to any server'})

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
        state.add_log('user', f'User query: {query}')

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

        # Log the tool schemas that will be sent to OpenAI
        state.add_log('system', 'Tool schemas available for OpenAI',
                     {'tools': tools})

        tool_executions = []

        # Agentic loop
        loop_count = 0
        while True:
            loop_count += 1

            # Log full request with complete tool schemas
            request_data = {
                'model': 'gpt-4-turbo-preview',
                'messages': [
                    {
                        'role': msg.get('role') if isinstance(msg, dict) else getattr(msg, 'role', 'unknown'),
                        'content': str(msg.get('content') if isinstance(msg, dict) else getattr(msg, 'content', ''))[:500]
                    } for msg in messages
                ],
                'tools': tools if tools else []  # Include complete tool schemas
            }
            state.add_log('openai', f'📤 Request to OpenAI (iteration {loop_count})', request_data)

            response = state.client.chat.completions.create(
                model="gpt-4-turbo-preview",
                max_tokens=4096,
                messages=messages,
                tools=tools if tools else None
            )

            response_message = response.choices[0].message

            # Log full response
            response_data = {
                'role': 'assistant',
                'content': response_message.content,
                'tool_calls': [
                    {
                        'id': tc.id,
                        'name': tc.function.name,
                        'arguments': tc.function.arguments
                    } for tc in response_message.tool_calls
                ] if response_message.tool_calls else None,
                'finish_reason': response.choices[0].finish_reason
            }
            state.add_log('openai', f'📥 Response from OpenAI', response_data)

            # Add assistant response to messages
            messages.append(response_message)

            # Check if we're done (no tool calls)
            if not response_message.tool_calls:
                # Add to chat history
                state.chat_history.append({'role': 'assistant', 'content': response_message.content})
                state.add_log('system', 'Query processing completed')

                return {
                    'status': 'success',
                    'response': response_message.content,
                    'tool_executions': tool_executions
                }

            # Process tool calls
            for tool_call in response_message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = eval(tool_call.function.arguments)

                state.add_log('openai', f'🔧 OpenAI requesting tool execution: {tool_name}',
                             {'tool_call_id': tool_call.id, 'arguments': tool_args})

                tool_executions.append({
                    'name': tool_name,
                    'arguments': tool_args
                })

                # Find which server provides this tool
                tool_obj = next((t for t in state.available_tools if t.name == tool_name), None)
                if not tool_obj:
                    error_msg = f"Tool {tool_name} not found in any connected server"
                    state.add_log('error', error_msg)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_name,
                        "content": error_msg
                    })
                    continue

                server_name = tool_obj.server_name
                server_session = state.servers[server_name]['session']

                # Call the MCP tool on the correct server
                mcp_request = {
                    'tool': tool_name,
                    'arguments': tool_args,
                    'server': server_name
                }
                state.add_log('mcp_client', f'📤 Sending tool request to {server_name}: {tool_name}', mcp_request)

                result = await server_session.call_tool(tool_name, tool_args)

                mcp_response = {
                    'tool': tool_name,
                    'server': server_name,
                    'result': str(result.content),
                    'content_type': type(result.content).__name__
                }
                state.add_log('mcp_server', f'📥 {server_name} tool execution complete: {tool_name}', mcp_response)

                # Add tool result to messages
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_name,
                    "content": str(result.content)
                })

    except Exception as e:
        state.add_log('error', f'Error in query processing: {str(e)}')
        return {'status': 'error', 'message': str(e)}


@app.route('/history', methods=['GET'])
def get_history():
    """Get chat history"""
    return jsonify({'history': state.chat_history})


@app.route('/status', methods=['GET'])
def get_status():
    """Get connection status"""
    return jsonify({
        'connected': len(state.connected_servers) > 0,
        'connected_servers': state.connected_servers,
        'total_servers': len(state.server_configs),
        'tools_count': len(state.available_tools)
    })


@app.route('/logs', methods=['GET'])
def get_logs():
    """Get all logs"""
    return jsonify({'logs': state.logs})


@app.route('/logs/clear', methods=['POST'])
def clear_logs():
    """Clear all logs"""
    state.logs = []
    return jsonify({'status': 'success', 'message': 'Logs cleared'})


if __name__ == '__main__':
    print("\n" + "="*60)
    print("MCP Client Web Interface")
    print("="*60)
    print("\nStarting server on http://localhost:5001")
    print("Open this URL in your web browser to use the client\n")
    print("Press Ctrl+C to stop the server")
    print("="*60 + "\n")

    app.run(debug=True, host='0.0.0.0', port=5001, use_reloader=False)
