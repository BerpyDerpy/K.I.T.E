from mcp.server.fastmcp import FastMCP

mcp = FastMCP("System Info Reporter")

@mcp.tool(name="system_info")
def system_info() -> str:
    """Stub tool for System Info Reporter"""
    return "Stub: System Info Reporter not yet implemented"

if __name__ == "__main__":
    mcp.run()
