"""SearXNG MCP HTTP server. Wraps a local SearXNG as an MCP web_search tool."""
import os
import httpx
from fastmcp import FastMCP

SEARXNG = os.environ.get("SEARXNG_URL", "http://127.0.0.1:8080")
TOKEN = os.environ.get("MCP_TOKEN", "")
PORT = int(os.environ.get("MCP_PORT", "8788"))

mcp = FastMCP(name="searxng")


@mcp.tool
async def web_search(query: str, num_results: int = 8, language: str = "auto") -> list[dict]:
    """Search the web via SearXNG.

    Args:
        query: search query
        num_results: max results to return (1-20)
        language: language code, e.g. en, zh, auto
    Returns: list of {title, url, snippet}
    """
    num_results = max(1, min(20, num_results))
    params = {
        "q": query,
        "format": "json",
        "language": language,
        "safesearch": "1",
    }
    async with httpx.AsyncClient(timeout=20.0) as c:
        r = await c.get(
            f"{SEARXNG}/search",
            params=params,
            headers={"Accept": "application/json"},
        )
        r.raise_for_status()
        data = r.json()
    out = []
    for it in (data.get("results") or [])[:num_results]:
        out.append({
            "title": it.get("title", ""),
            "url": it.get("url", ""),
            "snippet": (it.get("content") or "")[:500],
        })
    return out


@mcp.tool
async def fetch_url(url: str, max_chars: int = 6000) -> str:
    """Fetch a URL and return its text content (truncated)."""
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as c:
        r = await c.get(url, headers={"User-Agent": "ecs-searxng-mcp/1.0"})
        r.raise_for_status()
    return r.text[:max_chars]


if __name__ == "__main__":
    if TOKEN:
        from fastmcp.server.auth import StaticTokenVerifier
        mcp.auth = StaticTokenVerifier(tokens={TOKEN: {"client_id": "claude-glm"}})
    mcp.run(transport="http", host="0.0.0.0", port=PORT)
