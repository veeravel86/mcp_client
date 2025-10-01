# MCP Client & Server

A complete implementation of the Model Context Protocol (MCP) with OpenAI integration, featuring both CLI and web-based interfaces.

## 🌟 Features

- **MCP Client with OpenAI Integration** - Connect to MCP servers and use tools via GPT-4
- **Web-Based GUI** - Modern, responsive interface for easy interaction
- **CLI Interface** - Command-line version for terminal enthusiasts
- **Real-Time Logging** - View complete request/response logs with pretty JSON formatting
- **Built-in MCP Server** - Example server with weather tools and math operations
- **Tool & Prompt Support** - Full MCP implementation with tools, resources, and prompts

## 📋 Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Usage](#usage)
- [MCP Server Tools](#mcp-server-tools)
- [Architecture](#architecture)
- [Configuration](#configuration)
- [Development](#development)
- [Troubleshooting](#troubleshooting)

## 🔧 Prerequisites

Before you begin, ensure you have:

- **Python 3.8+** installed on your system
- **OpenAI API Key** - Get one from [OpenAI Platform](https://platform.openai.com/api-keys)
- **Git** (for cloning the repository)

## 📥 Installation

### 1. Clone the Repository

```bash
git clone https://github.com/veeravel86/mcp_client.git
cd mcp_client
```

### 2. Create Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Set Up Environment Variables

```bash
# Set your OpenAI API key
export OPENAI_API_KEY="your-api-key-here"

# Optional: Set custom MCP server path
export MCP_SERVER_SCRIPT="/path/to/mcp_server.py"
```

**For persistent setup**, add to your shell profile (`~/.bashrc`, `~/.zshrc`):

```bash
echo 'export OPENAI_API_KEY="your-api-key-here"' >> ~/.zshrc
source ~/.zshrc
```

## 🚀 Quick Start

### Option 1: Web Interface (Recommended)

```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Start the web server
python mcp_client_web.py
```

Then open your browser to: **http://localhost:5001**

### Option 2: Command Line Interface

```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Run the CLI client
python mcp_client.py
```

Type your queries and press Enter. Type `quit`, `exit`, or `q` to exit.

## 📖 Usage

### Using the Web Interface

1. **Start the Server**
   ```bash
   python mcp_client_web.py
   ```

2. **Open Browser**
   - Navigate to `http://localhost:5001`

3. **Connect to MCP Server**
   - Click the "Connect to Server" button
   - Wait for connection confirmation

4. **View Logs** (Optional)
   - Click "📋 View Logs" to see detailed request/response data
   - Click "🗑️ Clear Logs" to clear the log history

5. **Start Chatting**
   - Type your query in the input field
   - Press Enter or click "Send"
   - Watch tool executions in real-time

### Example Queries

```
# Math operations
"Add 25 and 17"
"What's 100 plus 250?"

# Weather information
"What's the weather forecast for New York?"
"Get weather alerts for California"

# Simple tests
"Echo hello world"
```

## 🛠️ MCP Server Tools

The included MCP server provides these tools:

### 1. **echo**
- **Purpose**: Echo back a message
- **Parameters**: `message` (string)
- **Example**: "Echo hello world"

### 2. **add_numbers**
- **Purpose**: Add two numbers
- **Parameters**: `a` (number), `b` (number)
- **Example**: "Add 25 and 17"

### 3. **get_weather_forecast**
- **Purpose**: Get weather forecast for coordinates
- **Parameters**: `latitude` (number), `longitude` (number)
- **Example**: "What's the weather in New York?" (OpenAI knows NYC coordinates)
- **API**: Uses National Weather Service API

### 4. **get_weather_alerts**
- **Purpose**: Get active weather alerts for a US state
- **Parameters**: `state` (2-letter state code)
- **Example**: "Get weather alerts for California"
- **API**: Uses National Weather Service API

### Prompts

The server also provides pre-written prompt templates:

- **math_problem_solver** - Solve math problems step-by-step
- **calculate_total** - Calculate totals with breakdown
- **analyze_weather** - Analyze weather conditions

## 🏗️ Architecture

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│   Web GUI   │ ───▶ │ MCP Client  │ ───▶ │   OpenAI    │
│ (Browser)   │ ◀─── │  (Python)   │ ◀─── │   GPT-4     │
└─────────────┘      └─────────────┘      └─────────────┘
                            │                      │
                            │                      │
                            ▼                      ▼
                     ┌─────────────┐      ┌─────────────┐
                     │ MCP Server  │      │  Tool Call  │
                     │  (Python)   │      │  Decision   │
                     └─────────────┘      └─────────────┘
                            │
                            ▼
                     ┌─────────────┐
                     │ External    │
                     │ APIs (NWS)  │
                     └─────────────┘
```

### Flow:
1. User enters query in web interface
2. Client sends query + tool schemas to OpenAI
3. OpenAI decides which tools to call
4. Client executes tools on MCP server
5. Server returns results to client
6. Client sends results back to OpenAI
7. OpenAI generates natural language response
8. Response displayed to user

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `OPENAI_API_KEY` | Your OpenAI API key | Yes | None |
| `MCP_SERVER_SCRIPT` | Path to MCP server script | No | `./mcp_server.py` |

### Port Configuration

By default, the web server runs on port `5001`. To change:

Edit `mcp_client_web.py` line 240:
```python
app.run(debug=True, host='0.0.0.0', port=5001, use_reloader=False)
```

## 💻 Development

### Project Structure

```
mcp_client/
├── mcp_client.py          # CLI client
├── mcp_client_web.py      # Web server (Flask)
├── mcp_client_gui.py      # Tkinter GUI (legacy)
├── mcp_server.py          # MCP server with tools
├── requirements.txt       # Python dependencies
├── .env.example          # Example environment config
├── .gitignore           # Git ignore rules
├── templates/
│   └── index.html       # Web interface HTML
└── README.md           # This file
```

### Adding New Tools

To add a tool to the MCP server:

1. **Define the tool** in `mcp_server.py`:

```python
@app.list_tools()
async def handle_list_tools() -> list[Tool]:
    return [
        # ... existing tools ...
        Tool(
            name="your_tool_name",
            description="What your tool does",
            inputSchema={
                "type": "object",
                "properties": {
                    "param1": {
                        "type": "string",
                        "description": "Parameter description"
                    }
                },
                "required": ["param1"]
            }
        )
    ]
```

2. **Implement the handler**:

```python
@app.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "your_tool_name":
        param1 = arguments.get("param1")
        # Your logic here
        return [TextContent(type="text", text=f"Result: {result}")]
```

3. **Restart the server** and it's ready to use!

## 🐛 Troubleshooting

### Common Issues

#### 1. Port Already in Use

**Error**: `Address already in use` or `Port 5001 is in use`

**Solution**:
- Change the port in `mcp_client_web.py`
- Or kill the process using the port:
  ```bash
  lsof -ti:5001 | xargs kill
  ```

#### 2. OpenAI API Key Not Found

**Error**: `OPENAI_API_KEY environment variable is required`

**Solution**:
```bash
export OPENAI_API_KEY="your-key-here"
# Or add to .env file
```

#### 3. Module Not Found

**Error**: `ModuleNotFoundError: No module named 'mcp'`

**Solution**:
```bash
# Ensure virtual environment is activated
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

#### 4. Connection Failed

**Error**: Client can't connect to MCP server

**Solution**:
- Check that `MCP_SERVER_SCRIPT` path is correct
- Ensure `python3` is available in PATH
- Check server logs for errors

#### 5. Tkinter Not Available (GUI)

**Error**: `ImportError: No module named '_tkinter'`

**Solution**: Use the web interface instead (`mcp_client_web.py`), which doesn't require Tkinter.

## 📦 Dependencies

- **mcp** - Model Context Protocol SDK
- **openai** - OpenAI Python client
- **flask** - Web framework
- **flask-cors** - CORS support
- **httpx** - HTTP client for async requests
- **pydantic** - Data validation
- **python-dotenv** - Environment variable management

## 🤝 Contributing

Contributions are welcome! To contribute:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes
4. Commit: `git commit -m "Add feature"`
5. Push: `git push origin feature-name`
6. Create a Pull Request

## 📄 License

This project is open source and available under the MIT License.

## 🙏 Acknowledgments

- Built with [Model Context Protocol](https://modelcontextprotocol.io/)
- Powered by [OpenAI GPT-4](https://openai.com/)
- Weather data from [National Weather Service API](https://www.weather.gov/documentation/services-web-api)

## 📞 Support

For issues, questions, or contributions:
- Open an issue on [GitHub](https://github.com/veeravel86/mcp_client/issues)
- Check the [MCP Documentation](https://modelcontextprotocol.io/docs)

---

**Made with ❤️ using Claude Code and MCP**
