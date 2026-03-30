#!/usr/bin/env python3
"""MCP server for Knowledge Base — Obsidian vault document graph.

Requires a running backend (viz/backend) on port 8000.
Tools: kb_graph_get, kb_get_document, kb_list_documents, kb_graph_rebuild.

Run from project root:
  python mcp-servers-knowledge-base/server.py
  uv run mcp-servers-knowledge-base/server.py

ENV:
  KB_API_BASE_URL — API base URL (default http://localhost:8000)
  API_KEY — API key for X-API-Key header (if backend requires it)
  TASKS_ENV_FILE — load an alternate .env (e.g. .env.mcp)
"""

import os
from pathlib import Path
from urllib.parse import quote

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(_PROJECT_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(_PROJECT_ROOT / ".env", override=False)
    _mcp_env = os.environ.get("TASKS_ENV_FILE")
    if _mcp_env:
        _mcp_path = _PROJECT_ROOT / _mcp_env
        if _mcp_path.exists():
            load_dotenv(_mcp_path, override=True)
except ImportError:
    pass

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "knowledge-base",
    instructions="MCP server for the knowledge base (Obsidian vault graph). Tools: kb_graph_get, kb_get_document, kb_list_documents, kb_graph_rebuild. Backend must be running (uvicorn main:app --port 8000).",
)

API_BASE = os.getenv("KB_API_BASE_URL", "http://localhost:8000").rstrip("/")
API_KEY = os.getenv("API_KEY", "")


def _headers() -> dict:
    h = {"Accept": "application/json"}
    if API_KEY:
        h["X-API-Key"] = API_KEY
    return h


def _get(url: str) -> dict | str:
    """GET request to backend API. Returns parsed JSON or error string."""
    try:
        import urllib.request
        req = urllib.request.Request(url, headers=_headers())
        with urllib.request.urlopen(req, timeout=60) as resp:
            import json
            return json.loads(resp.read().decode())
    except Exception as e:
        return f"Request error: {e}"


@mcp.tool()
def kb_graph_get(limit: int = 500, force: bool = False) -> str:
    """Get document graph (nodes, edges) from the knowledge base. limit — max documents; force — rebuild index."""
    url = f"{API_BASE}/api/kb-graph?limit={limit}&force={'true' if force else 'false'}"
    result = _get(url)
    if isinstance(result, str):
        return result
    nodes = result.get("nodes", [])
    edges = result.get("edges", [])
    return f"Nodes: {len(nodes)}, Edges: {len(edges)}. Sample nodes: {nodes[:5] if nodes else []}"


@mcp.tool()
def kb_get_document(path: str) -> str:
    """Get document content by vault-relative path. E.g. '46 AWS/AWS Skill Builder.md'."""
    encoded = quote(path, safe="/")
    url = f"{API_BASE}/api/kb-graph/doc/{encoded}"
    result = _get(url)
    if isinstance(result, str):
        return result
    content = result.get("content", "")
    return content or "(empty document)"


@mcp.tool()
def kb_list_documents() -> str:
    """List documents with modification times (mtimes) for sorting and search."""
    url = f"{API_BASE}/api/kb-graph/mtimes"
    result = _get(url)
    if isinstance(result, str):
        return result
    mtimes = result.get("mtimes", {})
    lines = [f"- {p} | {v}" for p, v in sorted(mtimes.items(), key=lambda x: -x[1])[:50]]
    return "\n".join(lines) if lines else "No documents"


@mcp.tool()
def kb_graph_rebuild() -> str:
    """Rebuild the knowledge base index from scratch. Can take time on large vaults."""
    url = f"{API_BASE}/api/kb-graph?force=true"
    result = _get(url)
    if isinstance(result, str):
        return result
    nodes = result.get("nodes", [])
    edges = result.get("edges", [])
    return f"Index rebuilt. Nodes: {len(nodes)}, Edges: {len(edges)}"


def _put(url: str, body: dict) -> dict | str:
    """PUT request to backend API. Returns parsed JSON or error string."""
    try:
        import json
        import urllib.request
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="PUT", headers={**_headers(), "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return f"Request error: {e}"


@mcp.tool()
def kb_edit_document(path: str, content: str) -> str:
    """Save document content by vault-relative path. Edits existing or creates new .md files."""
    encoded = quote(path, safe="/")
    url = f"{API_BASE}/api/kb-graph/doc/{encoded}"
    result = _put(url, {"content": content})
    if isinstance(result, str):
        return result
    if result.get("ok"):
        return "Saved"
    return str(result)


if __name__ == "__main__":
    mcp.run(transport="stdio")
