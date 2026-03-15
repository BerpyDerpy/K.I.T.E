from mcp.server.fastmcp import FastMCP

mcp = FastMCP("JSON Parser")

@mcp.tool(name="json_parser")
def json_parser() -> str:
    """Stub tool for JSON Parser"""
    return "Stub: JSON Parser not yet implemented"

if __name__ == "__main__":
    mcp.run()
