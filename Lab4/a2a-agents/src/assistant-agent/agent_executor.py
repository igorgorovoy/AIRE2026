"""A2A AgentExecutor for the Personal Assistant agent.

Wraps the Lab3 MCP tools (Knowledge Base, Lesson Credits, Task Manager)
and exposes them via A2A protocol. The agent receives user messages,
routes them to the appropriate MCP tool, and returns results as A2A artifacts.
"""

import json
import os
from urllib.parse import quote

import httpx

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import (
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
)
from a2a.utils.artifact import new_text_artifact
from a2a.utils.message import new_agent_text_message
from a2a.utils.task import new_task


# ---------------------------------------------------------------------------
# MCP Tool implementations (ported from Lab3 MCP servers)
# ---------------------------------------------------------------------------

KB_API_BASE = os.getenv("KB_API_BASE_URL", "http://localhost:8000").rstrip("/")
KB_API_KEY = os.getenv("KB_API_KEY", "")


def _kb_headers() -> dict:
    h = {"Accept": "application/json"}
    if KB_API_KEY:
        h["X-API-Key"] = KB_API_KEY
    return h


async def kb_list_documents() -> str:
    """List documents from the knowledge base with modification times."""
    url = f"{KB_API_BASE}/api/kb-graph/mtimes"
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(url, headers=_kb_headers())
        resp.raise_for_status()
        mtimes = resp.json().get("mtimes", {})
        lines = [f"- {p} | {v}" for p, v in sorted(mtimes.items(), key=lambda x: -x[1])[:50]]
        return "\n".join(lines) if lines else "Немає документів"


async def kb_get_document(path: str) -> str:
    """Get document content by path."""
    encoded = quote(path, safe="/")
    url = f"{KB_API_BASE}/api/kb-graph/doc/{encoded}"
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(url, headers=_kb_headers())
        resp.raise_for_status()
        content = resp.json().get("content", "")
        return content or "(порожній документ)"


async def kb_graph_get(limit: int = 500) -> str:
    """Get the document graph (nodes, edges)."""
    url = f"{KB_API_BASE}/api/kb-graph?limit={limit}&force=false"
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(url, headers=_kb_headers())
        resp.raise_for_status()
        data = resp.json()
        nodes = data.get("nodes", [])
        edges = data.get("edges", [])
        return f"Nodes: {len(nodes)}, Edges: {len(edges)}. Sample nodes: {nodes[:5]}"


# ---------------------------------------------------------------------------
# Simple intent routing (keyword-based for demo purposes)
# ---------------------------------------------------------------------------

TOOL_REGISTRY = {
    "kb_list_documents": kb_list_documents,
    "kb_get_document": kb_get_document,
    "kb_graph_get": kb_graph_get,
}


async def route_message(text: str) -> str:
    """Route a user message to the appropriate tool based on keywords."""
    lower = text.lower()

    # Knowledge Base routing
    if any(kw in lower for kw in ["документ", "document", "список", "list", "knowledge", "vault", "obsidian"]):
        if any(kw in lower for kw in ["граф", "graph", "nodes", "edges"]):
            return await kb_graph_get()
        return await kb_list_documents()

    if any(kw in lower for kw in ["отримай", "get", "покажи документ", "зміст"]):
        # Try to extract a document path from the message
        for prefix in ["отримай документ ", "get document ", "покажи документ "]:
            if prefix in lower:
                path = text[lower.index(prefix) + len(prefix):].strip().strip("'\"")
                if path:
                    return await kb_get_document(path)
        return await kb_list_documents()

    # Default: describe capabilities
    return (
        "Я персональний AI-асистент з доступом до:\n"
        "1. **Knowledge Base** — документи Obsidian vault\n"
        "   - Попросіть 'список документів' або 'граф knowledge base'\n"
        "2. **Lesson Credits** — облік уроків (потребує MCP backend)\n"
        "3. **Task Manager** — управління задачами (потребує MCP backend)\n\n"
        "Що вас цікавить?"
    )


# ---------------------------------------------------------------------------
# A2A AgentExecutor
# ---------------------------------------------------------------------------

class AssistantAgentExecutor(AgentExecutor):
    """A2A executor that routes user messages to MCP tools."""

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        task = context.current_task or new_task(context.message)
        await event_queue.enqueue_event(task)

        # Signal working
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=context.task_id,
                context_id=context.context_id,
                status=TaskStatus(
                    state=TaskState.TASK_STATE_WORKING,
                    message=new_agent_text_message("Обробляю запит..."),
                ),
            )
        )

        # Extract text from the incoming message
        user_text = ""
        if context.message and context.message.parts:
            for part in context.message.parts:
                if hasattr(part, "text"):
                    user_text += part.text

        if not user_text:
            user_text = "help"

        # Route to appropriate tool
        try:
            result = await route_message(user_text)
        except Exception as e:
            result = f"Помилка: {e}"

        # Send artifact
        await event_queue.enqueue_event(
            TaskArtifactUpdateEvent(
                task_id=context.task_id,
                context_id=context.context_id,
                artifact=new_text_artifact(name="response", text=result),
            )
        )

        # Signal completed
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=context.task_id,
                context_id=context.context_id,
                status=TaskStatus(state=TaskState.TASK_STATE_COMPLETED),
            )
        )

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        raise Exception("cancel not supported")
