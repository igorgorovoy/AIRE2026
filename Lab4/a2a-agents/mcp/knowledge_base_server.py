#!/usr/bin/env python3
"""MCP server for Knowledge Base (Lab3-compatible, bundled for Lab4 A2A assistant).

Same tools as Lab3 mcp-servers/src/knowledge-base/server.py.
ENV: KB_API_BASE_URL, API_KEY or KB_API_KEY, optional TASKS_ENV_FILE for extra .env path.
"""

import os
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_APP = _ROOT.parent

if str(_APP) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(_APP))

try:
    from dotenv import load_dotenv

    load_dotenv(_APP / ".env", override=False)
    load_dotenv(_ROOT / ".env", override=False)
    _mcp_env = os.environ.get("TASKS_ENV_FILE")
    if _mcp_env:
        _p = Path(_mcp_env)
        if not _p.is_absolute():
            _p = _APP / _mcp_env
        if _p.exists():
            load_dotenv(_p, override=True)
except ImportError:
    pass

from mcp.server.fastmcp import FastMCP
from urllib.parse import quote

mcp = FastMCP(
    "knowledge-base",
    instructions="MCP server for the knowledge base (Obsidian vault graph). Tools: kb_graph_get, kb_get_document, kb_list_documents, kb_graph_rebuild, kb_edit_document.",
)

API_BASE = os.getenv("KB_API_BASE_URL", "http://localhost:8000").rstrip("/")
API_KEY = os.getenv("API_KEY") or os.getenv("KB_API_KEY", "")


def _headers() -> dict:
    h = {"Accept": "application/json"}
    if API_KEY:
        h["X-API-Key"] = API_KEY
    return h


def _get(url: str) -> dict | str:
    try:
        import json
        import urllib.request

        req = urllib.request.Request(url, headers=_headers())
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return f"Request error: {e}"


@mcp.tool()
def kb_graph_get(limit: int = 500, force: bool = False) -> str:
    url = f"{API_BASE}/api/kb-graph?limit={limit}&force={'true' if force else 'false'}"
    result = _get(url)
    if isinstance(result, str):
        return result
    nodes = result.get("nodes", [])
    edges = result.get("edges", [])
    return f"Nodes: {len(nodes)}, Edges: {len(edges)}. Sample nodes: {nodes[:5] if nodes else []}"


@mcp.tool()
def kb_get_document(path: str) -> str:
    encoded = quote(path, safe="/")
    url = f"{API_BASE}/api/kb-graph/doc/{encoded}"
    result = _get(url)
    if isinstance(result, str):
        return result
    content = result.get("content", "")
    return content or "(empty document)"


@mcp.tool()
def kb_list_documents() -> str:
    url = f"{API_BASE}/api/kb-graph/mtimes"
    result = _get(url)
    if isinstance(result, str):
        return result
    mtimes = result.get("mtimes", {})
    lines = [f"- {p} | {v}" for p, v in sorted(mtimes.items(), key=lambda x: -x[1])[:50]]
    return "\n".join(lines) if lines else "No documents"


@mcp.tool()
def kb_graph_rebuild() -> str:
    url = f"{API_BASE}/api/kb-graph?force=true"
    result = _get(url)
    if isinstance(result, str):
        return result
    nodes = result.get("nodes", [])
    edges = result.get("edges", [])
    return f"Index rebuilt. Nodes: {len(nodes)}, Edges: {len(edges)}"


def _put(url: str, body: dict) -> dict | str:
    try:
        import json
        import urllib.request

        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            method="PUT",
            headers={**_headers(), "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return f"Request error: {e}"


@mcp.tool()
def kb_edit_document(path: str, content: str) -> str:
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
