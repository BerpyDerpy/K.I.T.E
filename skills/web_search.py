from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Web Search Engine")

@mcp.tool(name="web_search")
def web_search() -> str:
    """Stub tool for Web Search Engine"""
    return "Stub: Web Search Engine not yet implemented"

if __name__ == "__main__":
    mcp.run()
