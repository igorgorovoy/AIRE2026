#!/usr/bin/env python3
"""MCP Server для Knowledge Base — граф документів Obsidian vault.

Потребує запущений backend (viz/backend) на порту 8000.
Tools: kb_graph_get, kb_get_document, kb_list_documents, kb_graph_rebuild.

Запуск з кореня проєкту:
  python mcp-servers-knowledge-base/server.py
  uv run mcp-servers-knowledge-base/server.py

ENV:
  KB_API_BASE_URL — базовий URL API (default http://localhost:8000)
  API_KEY — API key для X-API-Key header (якщо backend вимагає)
  TASKS_ENV_FILE — завантажити окремий .env (напр. .env.mcp)
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
    instructions="MCP сервер для роботи з knowledge base (Obsidian vault graph). Tools: kb_graph_get, kb_get_document, kb_list_documents, kb_graph_rebuild. Backend має бути запущений (uvicorn main:app --port 8000).",
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
        return f"Помилка запиту: {e}"


@mcp.tool()
def kb_graph_get(limit: int = 500, force: bool = False) -> str:
    """Отримати граф документів (nodes, edges) з knowledge base. limit — макс. документів, force — перебудувати індекс."""
    url = f"{API_BASE}/api/kb-graph?limit={limit}&force={'true' if force else 'false'}"
    result = _get(url)
    if isinstance(result, str):
        return result
    nodes = result.get("nodes", [])
    edges = result.get("edges", [])
    return f"Nodes: {len(nodes)}, Edges: {len(edges)}. Sample nodes: {nodes[:5] if nodes else []}"


@mcp.tool()
def kb_get_document(path: str) -> str:
    """Отримати вміст документа за шляхом (відносно vault). Напр. '46 AWS/AWS Skill Builder.md'."""
    encoded = quote(path, safe="/")
    url = f"{API_BASE}/api/kb-graph/doc/{encoded}"
    result = _get(url)
    if isinstance(result, str):
        return result
    content = result.get("content", "")
    return content or "(порожній документ)"


@mcp.tool()
def kb_list_documents() -> str:
    """Список документів з датами зміни (mtimes) — для сортування та пошуку."""
    url = f"{API_BASE}/api/kb-graph/mtimes"
    result = _get(url)
    if isinstance(result, str):
        return result
    mtimes = result.get("mtimes", {})
    lines = [f"- {p} | {v}" for p, v in sorted(mtimes.items(), key=lambda x: -x[1])[:50]]
    return "\n".join(lines) if lines else "Немає документів"


@mcp.tool()
def kb_graph_rebuild() -> str:
    """Перебудувати індекс knowledge base з нуля. Може зайняти час на великих vault."""
    url = f"{API_BASE}/api/kb-graph?force=true"
    result = _get(url)
    if isinstance(result, str):
        return result
    nodes = result.get("nodes", [])
    edges = result.get("edges", [])
    return f"Індекс перебудовано. Nodes: {len(nodes)}, Edges: {len(edges)}"


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
        return f"Помилка запиту: {e}"


@mcp.tool()
def kb_edit_document(path: str, content: str) -> str:
    """Зберегти вміст документа за шляхом (відносно vault). Дозволяє редагувати існуючі та створювати нові .md файли."""
    encoded = quote(path, safe="/")
    url = f"{API_BASE}/api/kb-graph/doc/{encoded}"
    result = _put(url, {"content": content})
    if isinstance(result, str):
        return result
    if result.get("ok"):
        return "Збережено"
    return str(result)


if __name__ == "__main__":
    mcp.run(transport="stdio")
