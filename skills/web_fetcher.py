"""
skills/web_fetcher.py — Web Page Fetcher skill for K.I.T.E.

Uses Firecrawl to fetch clean, LLM-ready content from any URL.
Handles JavaScript rendering, anti-bot systems, and boilerplate removal.

Requires FIRECRAWL_API_KEY in .env (free tier: 500 credits/month at firecrawl.dev).
"""

import os
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

load_dotenv()

mcp = FastMCP("Web Page Fetcher")

FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY", "")
MAX_CONTENT_CHARS = 6000  # Generous limit for direct URL fetches


def _get_firecrawl():
    """Initialize and return a FirecrawlApp instance."""
    if not FIRECRAWL_API_KEY:
        raise RuntimeError(
            "FIRECRAWL_API_KEY is not set. "
            "Get a free key at https://firecrawl.dev and add it to your .env file."
        )
    from firecrawl import FirecrawlApp
    return FirecrawlApp(api_key=FIRECRAWL_API_KEY)


@mcp.tool()
def fetch_url(url: str) -> str:
    """Fetch the content of a web page as clean markdown given its URL.
    Handles JavaScript-rendered pages and removes ads/navigation clutter."""
    try:
        app = _get_firecrawl()
        result = app.scrape(url, formats=["markdown"])

        if not result or not result.markdown:
            return f"No content could be extracted from '{url}'."

        content = result.markdown
        # Extract metadata if available
        metadata = result.metadata if hasattr(result, 'metadata') and result.metadata else None
        title = "Unknown"
        source = url
        if metadata:
            if hasattr(metadata, 'title'):
                title = metadata.title or "Unknown"
            if hasattr(metadata, 'source_url'):
                source = metadata.source_url or url

        if len(content) > MAX_CONTENT_CHARS:
            content = content[:MAX_CONTENT_CHARS] + "\n\n... [truncated]"

        return (
            f"Title: {title}\n"
            f"Source: {source}\n"
            f"{'─' * 40}\n\n"
            f"{content}"
        )

    except Exception as e:
        return f"Failed to fetch '{url}': {e}"


@mcp.tool()
def fetch_text(url: str) -> str:
    """Fetch the content of a web page as plain text (no markdown formatting) given its URL."""
    try:
        app = _get_firecrawl()
        result = app.scrape(url, formats=["markdown"])

        if not result or not result.markdown:
            return f"No content could be extracted from '{url}'."

        # Strip markdown formatting for plain text output
        content = result.markdown
        import re
        content = re.sub(r'#{1,6}\s*', '', content)         # headers
        content = re.sub(r'\*\*(.+?)\*\*', r'\1', content)  # bold
        content = re.sub(r'\*(.+?)\*', r'\1', content)      # italic
        content = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', content)  # links
        content = re.sub(r'!\[.*?\]\(.+?\)', '', content)   # images
        content = re.sub(r'`{1,3}', '', content)             # code markers

        if len(content) > MAX_CONTENT_CHARS:
            content = content[:MAX_CONTENT_CHARS] + "\n\n... [truncated]"

        return content.strip()

    except Exception as e:
        return f"Failed to fetch '{url}': {e}"


if __name__ == "__main__":
    mcp.run()
