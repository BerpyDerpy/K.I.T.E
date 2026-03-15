from mcp.server.fastmcp import FastMCP
import os

mcp = FastMCP("filesystem")

@mcp.tool()
def read_file(path: str) -> str:
    """Read the contents of a file."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {e}"

@mcp.tool()
def write_file(path: str, content: str) -> str:
    """Write content to a file."""
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote to {path}"
    except Exception as e:
        return f"Error writing file: {e}"

@mcp.tool()
def list_directory(path: str) -> list[str]:
    """List directory contents."""
    try:
        return os.listdir(path)
    except Exception as e:
        return [f"Error listing directory: {e}"]

if __name__ == "__main__":
    mcp.run()
