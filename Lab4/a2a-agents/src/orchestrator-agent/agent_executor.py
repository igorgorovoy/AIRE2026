"""A2A Orchestrator Agent — discovers and delegates tasks to other A2A agents.

This agent:
1. Discovers available agents via Well-Known URI
2. Routes user requests to the appropriate agent based on skills
3. Returns aggregated results

Demonstrates A2A inter-agent communication (agent-to-agent task delegation).
"""

import json

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
# A2A Client: discover agents and send tasks
# ---------------------------------------------------------------------------

AGENT_REGISTRY: list[str] = []
"""List of base URLs for known A2A agents."""


async def discover_agent(base_url: str) -> dict | None:
    """Fetch Agent Card from a remote A2A agent via Well-Known URI."""
    url = f"{base_url.rstrip('/')}/.well-known/agent-card.json"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        print(f"[orchestrator] Failed to discover agent at {url}: {e}")
        return None


async def send_task_to_agent(base_url: str, user_text: str) -> str:
    """Send a message to a remote A2A agent using JSON-RPC SendMessage."""
    payload = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "a2a.SendMessage",
        "params": {
            "message": {
                "role": "user",
                "parts": [{"type": "text", "text": user_text}],
            },
            "configuration": {
                "returnImmediately": False,
            },
        },
    }

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                base_url.rstrip("/") + "/",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()

            # Extract result from JSON-RPC response
            result = data.get("result", {})

            # Try to get artifact text
            artifacts = result.get("artifacts", [])
            if artifacts:
                texts = []
                for artifact in artifacts:
                    for part in artifact.get("parts", []):
                        if part.get("type") == "text":
                            texts.append(part["text"])
                if texts:
                    return "\n".join(texts)

            # Fallback: look for status message
            status = result.get("status", {})
            msg = status.get("message", {})
            if msg:
                parts = msg.get("parts", [])
                for part in parts:
                    if part.get("type") == "text":
                        return part["text"]

            return json.dumps(result, indent=2, ensure_ascii=False)

    except Exception as e:
        return f"Помилка зв'язку з агентом: {e}"


def match_skill(agent_card: dict, user_text: str) -> bool:
    """Check if any of the agent's skills match the user request."""
    lower = user_text.lower()
    for skill in agent_card.get("skills", []):
        tags = skill.get("tags", [])
        name = skill.get("name", "").lower()
        description = skill.get("description", "").lower()
        # Match by tags or keywords in skill description
        for tag in tags:
            if tag.lower() in lower:
                return True
        if any(word in lower for word in name.split()):
            return True
    return True  # Default: route to first available agent


# ---------------------------------------------------------------------------
# A2A AgentExecutor
# ---------------------------------------------------------------------------

class OrchestratorAgentExecutor(AgentExecutor):
    """Orchestrator that discovers agents and delegates tasks via A2A."""

    def __init__(self, agent_urls: list[str] | None = None):
        self.agent_urls = agent_urls or ["http://localhost:9000"]

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
                    message=new_agent_text_message(
                        "Discovering agents and routing request..."
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
                status=TaskStatus(state=TaskState.TASK_STATE_COMPLETED),
            )
        )

    async def _discover_all(self) -> str:
        """Discover all registered agents and return their cards."""
        lines = ["# Discovered A2A Agents\n"]
        for url in self.agent_urls:
            card = await discover_agent(url)
            if card:
                lines.append(f"## {card.get('name', 'Unknown')}")
                lines.append(f"- **URL**: {url}")
                lines.append(f"- **Description**: {card.get('description', 'N/A')}")
                lines.append(f"- **Version**: {card.get('version', 'N/A')}")
                skills = card.get("skills", [])
                if skills:
                    lines.append("- **Skills**:")
                    for s in skills:
                        lines.append(f"  - `{s.get('id')}`: {s.get('description', '')}")
                lines.append("")
            else:
                lines.append(f"## Agent at {url}")
                lines.append("- **Status**: UNREACHABLE\n")
        return "\n".join(lines)

    async def _delegate_task(self, user_text: str) -> str:
        """Find the best matching agent and delegate the task."""
        for url in self.agent_urls:
            card = await discover_agent(url)
            if card and match_skill(card, user_text):
                agent_name = card.get("name", url)
                result = await send_task_to_agent(url, user_text)
                return (
                    f"**Delegated to**: {agent_name}\n"
                    f"**Result**:\n\n{result}"
                )
        return "Не знайдено жодного доступного агента для обробки запиту."

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        raise Exception("cancel not supported")
