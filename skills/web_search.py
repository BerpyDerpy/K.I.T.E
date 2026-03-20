"""
skills/web_search.py — Web Search skill for K.I.T.E.

Two-stage pipeline:
  1. Search  — Uses ddgs (DuckDuckGo) to discover relevant URLs
  2. Scrape  — Uses Firecrawl to fetch clean, LLM-ready markdown from the top result

This eliminates hallucination by giving the LLM actual page content
instead of just tiny search snippets.

Requires FIRECRAWL_API_KEY in .env (free tier: 500 credits/month at firecrawl.dev).
"""

import os
from mcp.server.fastmcp import FastMCP
from ddgs import DDGS
from dotenv import load_dotenv

load_dotenv()

mcp = FastMCP("Web Search Engine")

# ─── Firecrawl setup ──────────────────────────
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY", "")

MAX_CONTENT_CHARS = 4000  # Truncate scraped content to fit LLM context


def _scrape_url(url: str) -> str | None:
    """Scrape a URL using Firecrawl and return clean markdown content."""
    if not FIRECRAWL_API_KEY:
        return None
    try:
        from firecrawl import FirecrawlApp
        app = FirecrawlApp(api_key=FIRECRAWL_API_KEY)
        result = app.scrape(url, formats=["markdown"])

        if result and result.markdown:
            content = result.markdown
            if len(content) > MAX_CONTENT_CHARS:
                content = content[:MAX_CONTENT_CHARS] + "\n\n... [truncated]"
            return content
    except Exception as e:
        print(f"  [web_search] Firecrawl scrape failed for {url}: {e}")
    return None


@mcp.tool()
def search_web(query: str, max_results: int = 5) -> str:
    """Search the internet for current information and web results using a query string.
    Returns the full content of the most relevant page along with other search results."""
    try:
        results = DDGS().text(query, max_results=max_results)

        if not results:
            return f"No web results found for '{query}'."

        # Stage 1: Collect search results
        search_lines = []
        urls = []
        for i, r in enumerate(results, 1):
            title = r.get("title", "No title")
            url = r.get("href", "")
            snippet = r.get("body", "")
            search_lines.append(f"{i}. {title}\n   URL: {url}\n   {snippet}")
            if url:
                urls.append((url, title))

        search_summary = "\n\n".join(search_lines)

        # Stage 2: Scrape the top result for full content
        page_content = None
        scraped_url = None
        for url, title in urls[:2]:  # Try top 2 results
            page_content = _scrape_url(url)
            if page_content:
                scraped_url = url
                break

        if page_content:
            return (
                f"=== PAGE CONTENT (from: {scraped_url}) ===\n\n"
                f"{page_content}\n\n"
                f"=== OTHER SEARCH RESULTS ===\n\n"
                f"{search_summary}"
            )
        else:
            # Fallback: return just the search snippets (old behavior)
            return search_summary

    except Exception as e:
        return f"Web search failed: {e}"


@mcp.tool()
def search_news(query: str, max_results: int = 5) -> str:
    """Search for recent news articles using a query string. Returns titles, URLs, dates, and article bodies."""
    try:
        results = DDGS().news(query, max_results=max_results)

        if not results:
            return f"No news results found for '{query}'."

        output_lines = []
        for i, r in enumerate(results, 1):
            title = r.get("title", "No title")
            url = r.get("url", "")
            date = r.get("date", "Unknown date")
            body = r.get("body", "")
            source = r.get("source", "")
            output_lines.append(
                f"{i}. {title}\n   Source: {source} | {date}\n   URL: {url}\n   {body}"
            )

        return "\n\n".join(output_lines)

    except Exception as e:
        return f"News search failed: {e}"


if __name__ == "__main__":
    mcp.run()
