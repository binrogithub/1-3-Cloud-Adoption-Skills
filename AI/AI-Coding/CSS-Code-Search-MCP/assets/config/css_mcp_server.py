"""CSS/OpenSearch MCP HTTP server. Exposes indexed repo search as MCP tools.

Environment variables:
  CSS_URL   - CSS/OpenSearch endpoint (default: http://192.168.0.23:9200)
  CSS_INDEX - index name (default: cloud-adoption-skills)
  MCP_TOKEN - bearer token for auth (empty = no auth)
  MCP_PORT  - listen port (default: 8789)
"""
import os
import httpx
from fastmcp import FastMCP

CSS_URL = os.environ.get("CSS_URL", "http://192.168.0.23:9200")
INDEX = os.environ.get("CSS_INDEX", "cloud-adoption-skills")
TOKEN = os.environ.get("MCP_TOKEN", "")
PORT = int(os.environ.get("MCP_PORT", "8789"))

mcp = FastMCP(name="css-search")


@mcp.tool
async def search_code(query: str, size: int = 10, category: str = "", skill: str = "") -> list[dict]:
    """Search Cloud Adoption Skills code and docs indexed in CSS/OpenSearch.

    Use this tool to find code snippets, scripts, SKILL.md instructions, deployment
    references, and configuration examples from the indexed repository.

    Args:
        query: search query, e.g. "LiteLLM gateway install", "GaussDB migration SQL",
               "CSS monitor autoscaling", "CFW finance ACL rules"
        size: max results to return (1-20)
        category: filter by category - AI, Big-Data, Application-Modernization, Cloud-Foundation
        skill: filter by skill name, e.g. "LiteLLM-SearXNG-AICoding-Gateway-Single-ECS",
               "CSS-Autoscaling-Benchmark-Skill", "enterprise-rag-agent", "GaussDB-Adaptation-Skill"
    Returns: list of {repo_path, file_name, category, skill_name, ext, chunk_index,
             total_chunks, line_start, line_end, content, score, highlights}
    """
    size = max(1, min(20, size))
    must = [
        {
            "multi_match": {
                "query": query,
                "fields": ["content^2", "file_name^3", "skill_name^2", "category", "subcategory"],
            }
        }
    ]
    if category:
        must.append({"term": {"category": category}})
    if skill:
        must.append({"term": {"skill_name": skill}})

    body = {
        "query": {"bool": {"must": must}},
        "_source": [
            "repo_path", "file_name", "category", "subcategory", "skill_name",
            "ext", "chunk_index", "total_chunks", "line_start", "line_end", "content",
        ],
        "size": size,
        "highlight": {
            "fields": {"content": {"fragment_size": 200, "number_of_fragments": 2}},
            "pre_tags": [">>>"],
            "post_tags": ["<<<"],
        },
    }

    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.post(f"{CSS_URL}/{INDEX}/_search", json=body)
        r.raise_for_status()
        data = r.json()

    results = []
    for h in data.get("hits", {}).get("hits", []):
        s = h["_source"]
        s["score"] = round(h.get("_score", 0), 3)
        s["highlights"] = h.get("highlight", {}).get("content", [])
        results.append(s)
    return results


@mcp.tool
async def list_skills() -> dict:
    """List all Cloud Adoption Skills categories and skill names with document counts.

    Returns: {categories: [{key, doc_count}], skills: [{key, doc_count}]}
    """
    body = {
        "size": 0,
        "aggs": {
            "categories": {"terms": {"field": "category", "size": 50}},
            "skills": {"terms": {"field": "skill_name", "size": 100}},
        },
    }
    async with httpx.AsyncClient(timeout=10.0) as c:
        r = await c.post(f"{CSS_URL}/{INDEX}/_search", json=body)
        r.raise_for_status()
        return r.json().get("aggregations", {})


@mcp.tool
async def get_file(repo_path: str) -> str:
    """Get all chunks of a specific file from the CSS index.

    Use after search_code to retrieve the full content of a file that matched.

    Args:
        repo_path: file path in the repo, e.g. "AI/AI-Coding/LiteLLM-SearXNG-AICoding-Gateway-Single-ECS/SKILL.md"
    Returns: concatenated content of all chunks for the file
    """
    body = {
        "query": {"term": {"repo_path": repo_path}},
        "_source": ["content", "chunk_index", "total_chunks"],
        "size": 20,
        "sort": [{"chunk_index": {"order": "asc"}}],
    }
    async with httpx.AsyncClient(timeout=10.0) as c:
        r = await c.post(f"{CSS_URL}/{INDEX}/_search", json=body)
        r.raise_for_status()
        data = r.json()

    chunks = []
    for h in data.get("hits", {}).get("hits", []):
        chunks.append(h["_source"]["content"])
    return "\n".join(chunks)


if __name__ == "__main__":
    if TOKEN:
        from fastmcp.server.auth import StaticTokenVerifier
        mcp.auth = StaticTokenVerifier(tokens={TOKEN: {"client_id": "claude-glm"}})
    mcp.run(transport="http", host="0.0.0.0", port=PORT)
