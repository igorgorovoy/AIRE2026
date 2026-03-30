"""A2A Orchestrator Agent — single entry point for the client.

The orchestrator does not call MCP directly: it forwards requests to the Personal Assistant Agent
(Lab3 / A2A on port 14000), which routes to tools and external systems
(Knowledge Base, Lesson Credits, Task Manager).

Demonstrates: client → A2A orchestrator → A2A assistant → tools / HTTP API.
"""

import json
import sys
from pathlib import Path

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

# Local: a2a_http_client at a2a-agents root; Docker: copied next to agent_executor in /app
_orchestrator_dir = Path(__file__).resolve().parent
for _p in (_orchestrator_dir, _orchestrator_dir.parent.parent):
    if (_p / "a2a_http_client.py").is_file():
        if str(_p) not in sys.path:
            sys.path.insert(0, str(_p))
        break

from a2a_http_client import build_message_send_payload, extract_task_or_message_text


# ---------------------------------------------------------------------------
# A2A Client: discover assistant and send tasks
# ---------------------------------------------------------------------------


async def discover_agent(base_url: str) -> dict | None:
    """Fetch Agent Card from a remote A2A agent via Well-Known URI."""
    url = f"{base_url.rstrip('/')}/.well-known/agent-card.json"
    try:
        async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        print(f"[orchestrator] Failed to discover agent at {url}: {e}")
        return None


async def send_task_to_agent(base_url: str, user_text: str) -> str:
    """Send a message to a remote A2A agent (JSON-RPC ``message/send``)."""
    payload = build_message_send_payload(user_text)

    try:
        async with httpx.AsyncClient(timeout=120, trust_env=False) as client:
            resp = await client.post(
                base_url.rstrip("/") + "/",
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("error"):
                return json.dumps(data["error"], indent=2, ensure_ascii=False)

            result = data.get("result")
            text = extract_task_or_message_text(result)
            if text:
                return text
            if result is not None:
                return json.dumps(result, indent=2, ensure_ascii=False)
            return json.dumps(data, indent=2, ensure_ascii=False)

    except Exception as e:
        return f"Error contacting agent: {e}"


# ---------------------------------------------------------------------------
# A2A AgentExecutor
# ---------------------------------------------------------------------------


class OrchestratorAgentExecutor(AgentExecutor):
    """Orchestrator: forwards all user tasks to one A2A Assistant Agent."""

    def __init__(self, assistant_url: str = "http://localhost:14000"):
        self.assistant_url = assistant_url.rstrip("/")

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
                final=False,
                status=TaskStatus(
                    state=TaskState.working,
                    message=new_agent_text_message(
                        "Forwarding request to assistant (tools and external systems)..."
                    ),
                ),
            )
        )

        # Extract user text
        user_text = ""
        if context.message and context.message.parts:
            for part in context.message.parts:
                if hasattr(part, "text"):
                    user_text += part.text

        if not user_text:
            user_text = "help"

        # Special command: discover
        if user_text.strip().lower() in ("discover", "agents", "list agents"):
            result = await self._discover_all()
        else:
            result = await self._delegate_task(user_text)

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
                final=True,
                status=TaskStatus(state=TaskState.completed),
            )
        )

    async def _discover_all(self) -> str:
        """Show Assistant Agent Card — single downstream A2A agent with tools."""
        lines = [
            "# Orchestrator → Assistant Agent\n",
            "The orchestrator accepts client requests and via A2A delegates them to the **Personal Assistant Agent**, "
            "which invokes tools (KB, lessons, tasks).\n",
        ]
        url = self.assistant_url
        card = await discover_agent(url)
        if card:
            lines.append(f"## {card.get('name', 'Assistant')}")
            lines.append(f"- **URL**: {url}")
            lines.append(f"- **Description**: {card.get('description', 'N/A')}")
            lines.append(f"- **Version**: {card.get('version', 'N/A')}")
            skills = card.get("skills", [])
            if skills:
                lines.append("- **Skills** (access to external systems):")
                for s in skills:
                    lines.append(f"  - `{s.get('id')}`: {s.get('description', '')}")
            lines.append("")
        else:
            lines.append(f"## Assistant at {url}")
            lines.append("- **Status**: UNREACHABLE\n")
        return "\n".join(lines)

    async def _delegate_task(self, user_text: str) -> str:
        """Always delegate to the Personal Assistant Agent."""
        url = self.assistant_url
        card = await discover_agent(url)
        if not card:
            return (
                f"Assistant unreachable at `{url}`. "
                "Check the assistant-agent service and A2A_ASSISTANT_URL."
            )
        agent_name = card.get("name", url)
        result = await send_task_to_agent(url, user_text)
        return (
            f"**Orchestrator called**: {agent_name}\n"
            f"**Reply** (assistant handled the request via tools / API):\n\n{result}"
        )

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        raise Exception("cancel not supported")
