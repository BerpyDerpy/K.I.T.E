from mcp.server.fastmcp import FastMCP

mcp = FastMCP("API Request Builder")

@mcp.tool(name="api_builder")
def api_builder() -> str:
    """Stub tool for API Request Builder"""
    return "Stub: API Request Builder not yet implemented"

if __name__ == "__main__":
    mcp.run()
