# Multi-Server MCP Client Setup

The MCP client now supports connecting to multiple MCP servers simultaneously, just like Claude Desktop!

## Quick Start

Click the **❓ Add Servers** button in the web interface for detailed instructions, or use the API directly:

### Add Local Servers

#### Python Server
```bash
curl -X POST http://localhost:5001/servers/add \
  -H "Content-Type: application/json" \
  -d '{
    "name": "weather",
    "command": "python3",
    "args": ["/path/to/weather_server.py"]
  }'
```

#### Node.js Server
```bash
curl -X POST http://localhost:5001/servers/add \
  -H "Content-Type: application/json" \
  -d '{
    "name": "nodejs-server",
    "command": "node",
    "args": ["/path/to/server.js"]
  }'
```

#### NPX Package Server
```bash
curl -X POST http://localhost:5001/servers/add \
  -H "Content-Type: application/json" \
  -d '{
    "name": "filesystem",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/directory"]
  }'
```

### Add Remote Servers

#### Via SSH
```bash
curl -X POST http://localhost:5001/servers/add \
  -H "Content-Type: application/json" \
  -d '{
    "name": "remote-db",
    "command": "ssh",
    "args": ["user@remote-server.com", "python3", "/remote/path/server.py"]
  }'
```

#### Docker Container
```bash
curl -X POST http://localhost:5001/servers/add \
  -H "Content-Type: application/json" \
  -d '{
    "name": "docker-server",
    "command": "docker",
    "args": ["run", "-i", "my-mcp-server-image"]
  }'
```

### Connect to Servers

```bash
# Connect to all configured servers
curl -X POST http://localhost:5001/connect

# Connect to specific server
curl -X POST http://localhost:5001/servers/connect \
  -H "Content-Type: application/json" \
  -d '{"name": "weather"}'

# List all servers
curl http://localhost:5001/servers
```

## Features Implemented

✅ **Backend Support for Multiple Servers**
- Add/remove server configurations
- Connect/disconnect individual servers
- Tool routing to correct server
- Combined tool list from all servers

✅ **Smart Tool Routing**
- Automatically routes tool calls to the correct server
- Tracks which server provides which tool
- Shows server name in logs

✅ **Enhanced Logging**
- Shows which server executes each tool
- Separate logs per server
- Tool schemas tagged with server names

## Coming Soon

🔄 **Web UI for Server Management** (In Progress)
- Visual server list
- Add/remove servers via GUI
- Connect/disconnect buttons
- Server status indicators

## Current Workflow

1. Start the client: `python mcp_client_web.py`
2. Add servers using the API endpoints above
3. Click "Connect to Server" - connects to all configured servers
4. Use the chat - tools are automatically routed to the right server

## Example: Multiple Servers

```bash
# Add weather server
curl -X POST http://localhost:5001/servers/add \
  -H "Content-Type: application/json" \
  -d '{
    "name": "weather",
    "command": "python3",
    "args": ["/path/to/weather_server.py"]
  }'

# Add database server
curl -X POST http://localhost:5001/servers/add \
  -H "Content-Type: application/json" \
  -d '{
    "name": "database",
    "command": "python3",
    "args": ["/path/to/db_server.py"]
  }'

# Connect to all
curl -X POST http://localhost:5001/connect
```

Now you can use tools from both servers in the same conversation!

## Architecture

```
User Query
    ↓
OpenAI GPT-4
    ↓
Tool Decision (e.g., get_weather)
    ↓
MCP Client Routes to Correct Server
    ↓
┌─────────┬─────────┬─────────┐
│ Weather │Database │  Other  │
│ Server  │ Server  │ Server  │
└─────────┴─────────┴─────────┘
```

Each server provides different tools, and the client automatically knows which server to call for each tool!
