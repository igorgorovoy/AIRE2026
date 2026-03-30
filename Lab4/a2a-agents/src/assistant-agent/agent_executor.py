"""A2A AgentExecutor for the Personal Assistant agent.

Invokes the same MCP tools as Lab3 (stdio MCP servers): Knowledge Base is always
started from ``mcp/knowledge_base_server.py``. Lesson Credits and Task Manager
start only when ``MCP_LESSON_CREDITS_SCRIPT`` / ``MCP_TASKS_SCRIPT`` point to
Lab3 ``server.py`` files and CWD env vars match a project tree with ``agents/`` + ``core/``.
"""

from __future__ import annotations

import re

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

from mcp_stdio_hub import AssistantMcpHub, get_mcp_hub

_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)


async def route_message(text: str, hub: AssistantMcpHub) -> str:
    """Keyword routing to MCP ``call_tool`` (same tool names as Lab3)."""
    lower = text.lower().strip()

    # --- Lesson Credits (optional MCP) ---
    if hub.lessons and hub.lessons.configured:
        if any(
            k in lower
            for k in [
                "lesson",
                "calendar",
                "credit",
                "balance",
                "top up",
                "deduct",
                "transaction",
            ]
        ):
            if "balance" in lower:
                ids = _UUID_RE.findall(text)
                if ids:
                    return await hub.lessons.call_tool(
                        "lessons_get_balance",
                        {"calendar_id": ids[0]},
                    )
            return await hub.lessons.call_tool("lessons_list_calendars", {})

    # --- Task Manager (optional MCP) ---
    if hub.tasks and hub.tasks.configured:
        if any(
            k in lower
            for k in [
                "workspace",
                "kanban",
                "task manager",
                "list boards",
                "list cards",
            ]
        ):
            return await hub.tasks.call_tool("tasks_list_workspaces", {})

    # --- Knowledge Base (bundled MCP) ---
    if not hub.kb.configured:
        return (
            "Knowledge Base MCP is not available (missing server script). "
            "Check MCP_KB_SCRIPT and image layout."
        )

    if any(k in lower for k in ["graph", "nodes", "edges"]) and any(
        k in lower for k in ["knowledge", "vault", "obsidian", "graph", "kb", "document"]
    ):
        return await hub.kb.call_tool("kb_graph_get", {"limit": 500, "force": False})

    if any(k in lower for k in ["rebuild", "re-index", "reindex"]) and any(
        k in lower for k in ["knowledge", "vault", "index", "kb"]
    ):
        return await hub.kb.call_tool("kb_graph_rebuild", {})

    if any(k in lower for k in ["get document", "show document", "read document", "open document"]):
        for prefix in ("get document ", "show document ", "read document ", "open document "):
            if prefix in lower:
                idx = lower.index(prefix)
                path = text[idx + len(prefix) :].strip().strip("'\"")
                if path:
                    return await hub.kb.call_tool("kb_get_document", {"path": path})
                break

    if any(
        k in lower
        for k in [
            "document",
            "list",
            "knowledge",
            "vault",
            "obsidian",
            "files",
        ]
    ):
        if "workspace" in lower or "calendar" in lower or "lesson" in lower:
            pass
        else:
            if any(k in lower for k in ["graph", "nodes", "edges"]):
                return await hub.kb.call_tool("kb_graph_get", {})
            return await hub.kb.call_tool("kb_list_documents", {})

    lines = [
        "I am a personal AI assistant using **MCP tools** (same protocol as Lab3).",
        "",
        "1. **Knowledge Base** — list/read/graph Obsidian documents via MCP.",
    ]
    if hub.lessons and hub.lessons.configured:
        lines.append(
            "2. **Lesson Credits** — MCP connected. Try: lesson calendars, balance <calendar_id>."
        )
    else:
        lines.append(
            "2. **Lesson Credits** — not connected. Set MCP_LESSON_CREDITS_SCRIPT and "
            "MCP_LESSON_CREDITS_CWD (project root with agents/ + core/)."
        )
    if hub.tasks and hub.tasks.configured:
        lines.append("3. **Task Manager** — MCP connected. Try: list workspaces.")
    else:
        lines.append(
            "3. **Task Manager** — not connected. Set MCP_TASKS_SCRIPT and MCP_TASKS_CWD."
        )
    lines.extend(
        [
            "",
            "Try: `list documents`, `knowledge graph`, `get document path/to/file.md`.",
        ]
    )
    return "\n".join(lines)


class AssistantAgentExecutor(AgentExecutor):
    """Routes user messages to MCP tool calls (stdio), Lab3-compatible tool names."""

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        task = context.current_task or new_task(context.message)
        await event_queue.enqueue_event(task)

        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=context.task_id,
                context_id=context.context_id,
                final=False,
                status=TaskStatus(
                    state=TaskState.working,
                    message=new_agent_text_message(
                        "Calling MCP tools (Knowledge Base / optional Lab3 servers)..."
                    ),
                ),
            )
        )

        user_text = ""
        if context.message and context.message.parts:
            for part in context.message.parts:
                if hasattr(part, "text"):
                    user_text += part.text

        if not user_text:
            user_text = "help"

        try:
            hub = await get_mcp_hub()
            result = await route_message(user_text, hub)
        except Exception as e:
            result = f"Error: {e}"

        await event_queue.enqueue_event(
            TaskArtifactUpdateEvent(
                task_id=context.task_id,
                context_id=context.context_id,
                artifact=new_text_artifact(name="response", text=result),
            )
        )

        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=context.task_id,
                context_id=context.context_id,
                final=True,
                status=TaskStatus(state=TaskState.completed),
            )
        )

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        raise Exception("cancel not supported")
