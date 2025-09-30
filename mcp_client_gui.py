"""
MCP Client GUI Implementation
A graphical user interface for the MCP client using Tkinter
"""

import asyncio
import os
import tkinter as tk
from tkinter import scrolledtext, messagebox
from typing import Optional
from contextlib import AsyncExitStack
import threading

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import OpenAI


class MCPClientGUI:
    def __init__(self, root):
        """Initialize the MCP Client GUI"""
        self.root = root
        self.root.title("MCP Client")
        self.root.geometry("800x600")

        # MCP Client components
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.client = None
        self.available_tools = []
        self.loop = None
        self.connected = False

        # Setup GUI
        self.setup_gui()

        # Start async loop in background thread
        self.start_async_loop()

    def setup_gui(self):
        """Setup the GUI components"""
        # Header
        header_frame = tk.Frame(self.root, bg="#2c3e50", height=60)
        header_frame.pack(fill=tk.X)

        title_label = tk.Label(
            header_frame,
            text="MCP Client",
            font=("Arial", 18, "bold"),
            bg="#2c3e50",
            fg="white"
        )
        title_label.pack(pady=15)

        # Connection status
        self.status_label = tk.Label(
            self.root,
            text="Status: Not Connected",
            font=("Arial", 10),
            fg="red"
        )
        self.status_label.pack(pady=5)

        # Chat display area
        chat_frame = tk.Frame(self.root)
        chat_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.chat_display = scrolledtext.ScrolledText(
            chat_frame,
            wrap=tk.WORD,
            font=("Arial", 11),
            state=tk.DISABLED,
            bg="#ecf0f1",
            fg="#2c3e50"
        )
        self.chat_display.pack(fill=tk.BOTH, expand=True)

        # Configure text tags for styling
        self.chat_display.tag_config("user", foreground="#2980b9", font=("Arial", 11, "bold"))
        self.chat_display.tag_config("assistant", foreground="#27ae60", font=("Arial", 11, "bold"))
        self.chat_display.tag_config("system", foreground="#7f8c8d", font=("Arial", 10, "italic"))
        self.chat_display.tag_config("error", foreground="#e74c3c", font=("Arial", 10))

        # Input area
        input_frame = tk.Frame(self.root)
        input_frame.pack(fill=tk.X, padx=10, pady=10)

        self.input_field = tk.Text(
            input_frame,
            height=3,
            font=("Arial", 11),
            wrap=tk.WORD
        )
        self.input_field.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.input_field.bind("<Return>", self.handle_enter)
        self.input_field.bind("<Shift-Return>", lambda e: None)  # Allow Shift+Enter for newline

        # Send button
        self.send_button = tk.Button(
            input_frame,
            text="Send",
            command=self.send_message,
            bg="#3498db",
            fg="white",
            font=("Arial", 11, "bold"),
            width=10,
            state=tk.DISABLED
        )
        self.send_button.pack(side=tk.RIGHT, padx=(5, 0))

        # Connect button
        button_frame = tk.Frame(self.root)
        button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        self.connect_button = tk.Button(
            button_frame,
            text="Connect to Server",
            command=self.connect_to_server,
            bg="#27ae60",
            fg="white",
            font=("Arial", 10, "bold")
        )
        self.connect_button.pack()

    def start_async_loop(self):
        """Start the asyncio event loop in a background thread"""
        def run_loop():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop.run_forever()

        thread = threading.Thread(target=run_loop, daemon=True)
        thread.start()

    def add_message(self, sender: str, message: str, tag: str = ""):
        """Add a message to the chat display"""
        self.chat_display.config(state=tk.NORMAL)

        if sender:
            self.chat_display.insert(tk.END, f"{sender}: ", tag)
        self.chat_display.insert(tk.END, f"{message}\n\n", tag if not sender else "")

        self.chat_display.config(state=tk.DISABLED)
        self.chat_display.see(tk.END)

    def handle_enter(self, event):
        """Handle Enter key press"""
        if event.state & 0x1:  # Shift is pressed
            return None
        else:
            self.send_message()
            return "break"  # Prevent newline insertion

    def send_message(self):
        """Send a message to the MCP client"""
        query = self.input_field.get("1.0", tk.END).strip()

        if not query:
            return

        if not self.connected:
            messagebox.showwarning("Not Connected", "Please connect to the server first.")
            return

        # Clear input field
        self.input_field.delete("1.0", tk.END)

        # Add user message to chat
        self.add_message("You", query, "user")

        # Disable send button while processing
        self.send_button.config(state=tk.DISABLED)
        self.input_field.config(state=tk.DISABLED)

        # Process query asynchronously
        asyncio.run_coroutine_threadsafe(
            self.process_query_async(query),
            self.loop
        )

    def connect_to_server(self):
        """Connect to the MCP server"""
        if self.connected:
            messagebox.showinfo("Already Connected", "Already connected to server.")
            return

        self.connect_button.config(state=tk.DISABLED)
        self.add_message("", "Connecting to server...", "system")

        # Connect asynchronously
        asyncio.run_coroutine_threadsafe(
            self.connect_async(),
            self.loop
        )

    async def connect_async(self):
        """Async connection to MCP server"""
        try:
            # Check for API key
            if not os.environ.get("OPENAI_API_KEY"):
                self.root.after(0, lambda: self.add_message(
                    "", "Error: OPENAI_API_KEY not found in environment", "error"
                ))
                self.root.after(0, lambda: self.connect_button.config(state=tk.NORMAL))
                return

            # Initialize OpenAI client
            self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

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

            self.connected = True

            # Update GUI
            tools_list = "\n".join([f"  • {tool.name}: {tool.description}" for tool in self.available_tools])
            self.root.after(0, lambda: self.add_message(
                "", f"✓ Connected to server!\n\nAvailable tools:\n{tools_list}", "system"
            ))
            self.root.after(0, lambda: self.status_label.config(
                text=f"Status: Connected ({len(self.available_tools)} tools)",
                fg="green"
            ))
            self.root.after(0, lambda: self.send_button.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.input_field.focus())

        except Exception as e:
            self.root.after(0, lambda: self.add_message(
                "", f"Connection failed: {str(e)}", "error"
            ))
            self.root.after(0, lambda: self.connect_button.config(state=tk.NORMAL))

    async def process_query_async(self, query: str):
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
                    self.root.after(0, lambda: self.add_message(
                        "Assistant", response_message.content, "assistant"
                    ))
                    break

                # Process tool calls
                for tool_call in response_message.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = eval(tool_call.function.arguments)

                    self.root.after(0, lambda n=tool_name, a=tool_args: self.add_message(
                        "", f"🔧 Executing tool: {n}\nArguments: {a}", "system"
                    ))

                    # Call the MCP tool
                    result = await self.session.call_tool(tool_name, tool_args)

                    # Add tool result to messages
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_name,
                        "content": str(result.content)
                    })

        except Exception as e:
            self.root.after(0, lambda: self.add_message(
                "", f"Error: {str(e)}", "error"
            ))

        finally:
            # Re-enable input
            self.root.after(0, lambda: self.send_button.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.input_field.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.input_field.focus())

    def on_closing(self):
        """Handle window closing"""
        if self.connected:
            asyncio.run_coroutine_threadsafe(
                self.exit_stack.aclose(),
                self.loop
            )
        if self.loop:
            self.loop.call_soon_threadsafe(self.loop.stop)
        self.root.destroy()


def main():
    """Main entry point"""
    root = tk.Tk()
    app = MCPClientGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()
