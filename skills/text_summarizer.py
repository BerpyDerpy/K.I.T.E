from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Text Summarizer")

@mcp.tool(name="text_summarizer")
def text_summarizer() -> str:
    """Stub tool for Text Summarizer"""
    return "Stub: Text Summarizer not yet implemented"

if __name__ == "__main__":
    mcp.run()
