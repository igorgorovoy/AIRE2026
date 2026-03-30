#!/usr/bin/env python3
"""Example: MCP server with Phoenix tracing.

Based on: https://arize.com/docs/phoenix/integrations/python/mcp-tracing

This wraps the knowledge-base MCP server with OpenTelemetry tracing
so every tool call appears as a span in Phoenix UI.

ENV:
  PHOENIX_COLLECTOR_ENDPOINT — Phoenix OTLP endpoint (default http://phoenix.aire2026.local:4317)
  KB_API_BASE_URL — Knowledge Base backend URL
"""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# 1. Configure OpenTelemetry BEFORE importing MCP
# ---------------------------------------------------------------------------
PHOENIX_ENDPOINT = os.getenv(
    "PHOENIX_COLLECTOR_ENDPOINT", "http://phoenix.aire2026.local:4317"
)

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

resource = Resource.create({"service.name": "mcp-knowledge-base"})
provider = TracerProvider(resource=resource)
exporter = OTLPSpanExporter(endpoint=PHOENIX_ENDPOINT, insecure=True)
provider.add_span_processor(BatchSpanProcessor(exporter))
trace.set_tracer_provider(provider)

tracer = trace.get_tracer("mcp-knowledge-base")

# ---------------------------------------------------------------------------
# 2. Instrument MCP with OpenInference
# ---------------------------------------------------------------------------
from openinference.instrumentation.mcp import MCPInstrumentor

MCPInstrumentor().instrument(tracer_provider=provider)

# ---------------------------------------------------------------------------
# 3. MCP server (same as Lab3 knowledge-base, now traced)
# ---------------------------------------------------------------------------
from urllib.parse import quote

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "knowledge-base-traced",
    instructions="Knowledge Base MCP server with Phoenix tracing enabled.",
)

API_BASE = os.getenv("KB_API_BASE_URL", "http://localhost:8000").rstrip("/")
API_KEY = os.getenv("API_KEY", "")


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
    """Get document graph (nodes, edges) from the knowledge base."""
    with tracer.start_as_current_span("kb_graph_get", attributes={"limit": limit, "force": force}):
        url = f"{API_BASE}/api/kb-graph?limit={limit}&force={'true' if force else 'false'}"
        result = _get(url)
        if isinstance(result, str):
            return result
        nodes = result.get("nodes", [])
        edges = result.get("edges", [])
        return f"Nodes: {len(nodes)}, Edges: {len(edges)}. Sample nodes: {nodes[:5] if nodes else []}"


@mcp.tool()
def kb_get_document(path: str) -> str:
    """Get document content by vault-relative path."""
    with tracer.start_as_current_span("kb_get_document", attributes={"path": path}):
        encoded = quote(path, safe="/")
        url = f"{API_BASE}/api/kb-graph/doc/{encoded}"
        result = _get(url)
        if isinstance(result, str):
            return result
        content = result.get("content", "")
        return content or "(empty document)"


@mcp.tool()
def kb_list_documents() -> str:
    """List documents with modification times."""
    with tracer.start_as_current_span("kb_list_documents"):
        url = f"{API_BASE}/api/kb-graph/mtimes"
        result = _get(url)
        if isinstance(result, str):
            return result
        mtimes = result.get("mtimes", {})
        lines = [f"- {p} | {v}" for p, v in sorted(mtimes.items(), key=lambda x: -x[1])[:50]]
        return "\n".join(lines) if lines else "No documents"


if __name__ == "__main__":
    mcp.run(transport="stdio")
