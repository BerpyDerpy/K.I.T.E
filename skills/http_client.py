from mcp.server.fastmcp import FastMCP

mcp = FastMCP("HTTP Request Client")

@mcp.tool(name="http_client")
def http_client() -> str:
    """Stub tool for HTTP Request Client"""
    return "Stub: HTTP Request Client not yet implemented"

if __name__ == "__main__":
    mcp.run()
