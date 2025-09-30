"""
MCP Server Implementation
A Python server for exposing tools, resources, and prompts via Model Context Protocol
"""

import asyncio
import logging
from typing import Any
import httpx
from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Resource,
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
)
from pydantic import AnyUrl

# Configure logging to stderr (stdout is reserved for MCP communication)
logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler()])
logger = logging.getLogger("mcp_server")

# Initialize MCP server
app = Server("example-server")

# Constants for external API example
NWS_API_BASE = "https://api.weather.gov"
USER_AGENT = "mcp-server/1.0"


@app.list_resources()
async def handle_list_resources() -> list[Resource]:
    """
    List available resources.
    Resources are data or content that can be read by the client.
    """
    return [
        Resource(
            uri=AnyUrl("example://static-resource"),
            name="Static Example Resource",
            description="A static example resource",
            mimeType="text/plain",
        )
    ]


@app.read_resource()
async def handle_read_resource(uri: AnyUrl) -> str:
    """
    Read a specific resource by URI.

    Args:
        uri: The URI of the resource to read

    Returns:
        The resource content as a string
    """
    if str(uri) == "example://static-resource":
        return "This is a static example resource content."
    else:
        raise ValueError(f"Unknown resource: {uri}")


@app.list_tools()
async def handle_list_tools() -> list[Tool]:
    """
    List available tools.
    Tools are functions that can be called by the LLM.
    """
    return [
        Tool(
            name="get_weather_forecast",
            description="Get weather forecast for a location using latitude and longitude",
            inputSchema={
                "type": "object",
                "properties": {
                    "latitude": {
                        "type": "number",
                        "description": "Latitude of the location"
                    },
                    "longitude": {
                        "type": "number",
                        "description": "Longitude of the location"
                    }
                },
                "required": ["latitude", "longitude"]
            }
        ),
        Tool(
            name="get_weather_alerts",
            description="Get active weather alerts for a US state",
            inputSchema={
                "type": "object",
                "properties": {
                    "state": {
                        "type": "string",
                        "description": "Two-letter US state code (e.g., CA, NY)"
                    }
                },
                "required": ["state"]
            }
        ),
        Tool(
            name="echo",
            description="Echo back the input message",
            inputSchema={
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Message to echo back"
                    }
                },
                "required": ["message"]
            }
        ),
        Tool(
            name="add_numbers",
            description="Add two numbers together",
            inputSchema={
                "type": "object",
                "properties": {
                    "a": {
                        "type": "number",
                        "description": "First number"
                    },
                    "b": {
                        "type": "number",
                        "description": "Second number"
                    }
                },
                "required": ["a", "b"]
            }
        )
    ]


@app.call_tool()
async def handle_call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """
    Handle tool execution.

    Args:
        name: Name of the tool to execute
        arguments: Tool arguments

    Returns:
        List of text content results
    """
    try:
        if name == "echo":
            message = arguments.get("message", "")
            return [TextContent(type="text", text=f"Echo: {message}")]

        elif name == "add_numbers":
            a = arguments.get("a", 0)
            b = arguments.get("b", 0)
            result = a + b
            return [TextContent(type="text", text=f"Result: {result}")]

        elif name == "get_weather_forecast":
            latitude = arguments.get("latitude")
            longitude = arguments.get("longitude")

            async with httpx.AsyncClient() as client:
                # Get grid point data
                headers = {"User-Agent": USER_AGENT}
                points_url = f"{NWS_API_BASE}/points/{latitude},{longitude}"

                response = await client.get(points_url, headers=headers, timeout=30.0)
                response.raise_for_status()

                points_data = response.json()
                forecast_url = points_data["properties"]["forecast"]

                # Get forecast
                forecast_response = await client.get(forecast_url, headers=headers, timeout=30.0)
                forecast_response.raise_for_status()

                forecast_data = forecast_response.json()
                periods = forecast_data["properties"]["periods"]

                # Format forecast
                forecast_text = f"Weather forecast for {latitude}, {longitude}:\n\n"
                for period in periods[:5]:  # First 5 periods
                    forecast_text += f"{period['name']}:\n"
                    forecast_text += f"Temperature: {period['temperature']}°{period['temperatureUnit']}\n"
                    forecast_text += f"{period['detailedForecast']}\n\n"

                return [TextContent(type="text", text=forecast_text)]

        elif name == "get_weather_alerts":
            state = arguments.get("state", "").upper()

            async with httpx.AsyncClient() as client:
                headers = {"User-Agent": USER_AGENT}
                alerts_url = f"{NWS_API_BASE}/alerts/active?area={state}"

                response = await client.get(alerts_url, headers=headers, timeout=30.0)
                response.raise_for_status()

                alerts_data = response.json()
                features = alerts_data.get("features", [])

                if not features:
                    return [TextContent(type="text", text=f"No active alerts for {state}")]

                # Format alerts
                alerts_text = f"Active weather alerts for {state}:\n\n"
                for alert in features[:5]:  # First 5 alerts
                    props = alert["properties"]
                    alerts_text += f"Event: {props.get('event', 'Unknown')}\n"
                    alerts_text += f"Severity: {props.get('severity', 'Unknown')}\n"
                    alerts_text += f"Description: {props.get('headline', 'No description')}\n\n"

                return [TextContent(type="text", text=alerts_text)]

        else:
            raise ValueError(f"Unknown tool: {name}")

    except Exception as e:
        logger.error(f"Error executing tool {name}: {str(e)}")
        return [TextContent(type="text", text=f"Error: {str(e)}")]


@app.list_prompts()
async def handle_list_prompts() -> list[Any]:
    """
    List available prompts.
    Prompts are pre-written templates for common tasks.
    """
    return [
        {
            "name": "analyze_weather",
            "description": "Analyze weather data and provide insights",
            "arguments": [
                {
                    "name": "location",
                    "description": "Location to analyze",
                    "required": True
                }
            ]
        },
        {
            "name": "math_problem_solver",
            "description": "Help solve math problems step by step using available tools",
            "arguments": [
                {
                    "name": "problem",
                    "description": "The math problem to solve",
                    "required": True
                }
            ]
        },
        {
            "name": "calculate_total",
            "description": "Calculate totals and provide breakdown using add_numbers tool",
            "arguments": [
                {
                    "name": "items",
                    "description": "List of numbers to sum (comma-separated)",
                    "required": True
                }
            ]
        }
    ]


@app.get_prompt()
async def handle_get_prompt(name: str, arguments: dict[str, str] | None) -> Any:
    """
    Get a specific prompt by name.

    Args:
        name: Name of the prompt
        arguments: Prompt arguments

    Returns:
        The prompt content
    """
    if name == "analyze_weather":
        location = arguments.get("location", "unknown location") if arguments else "unknown location"
        return {
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": f"Please analyze the weather conditions for {location} and provide insights about what to expect and any precautions to take."
                    }
                }
            ]
        }

    elif name == "math_problem_solver":
        problem = arguments.get("problem", "a math problem") if arguments else "a math problem"
        return {
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": f"Please solve this math problem step by step: {problem}\n\nUse the add_numbers tool when you need to add numbers together. Show your work and explain each step clearly."
                    }
                }
            ]
        }

    elif name == "calculate_total":
        items = arguments.get("items", "0") if arguments else "0"
        return {
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": f"Please calculate the total of these numbers: {items}\n\nUse the add_numbers tool to add pairs of numbers, and show the breakdown of your calculation."
                    }
                }
            ]
        }

    else:
        raise ValueError(f"Unknown prompt: {name}")


async def main():
    """Main entry point for the MCP server"""
    logger.info("Starting MCP server...")

    # Run the server using stdio transport
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="example-server",
                server_version="1.0.0",
                capabilities=app.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={}
                )
            )
        )


if __name__ == "__main__":
    asyncio.run(main())
