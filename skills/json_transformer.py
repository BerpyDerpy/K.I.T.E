from mcp.server.fastmcp import FastMCP

mcp = FastMCP("JSON Transformer")

@mcp.tool(name="json_transformer")
def json_transformer() -> str:
    """Stub tool for JSON Transformer"""
    return "Stub: JSON Transformer not yet implemented"

if __name__ == "__main__":
    mcp.run()
