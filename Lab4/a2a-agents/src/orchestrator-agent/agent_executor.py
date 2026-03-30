"""A2A Orchestrator Agent — єдина точка входу для клієнта.

Оркестратор не викликає MCP напряму: він передає запити Personal Assistant Agent
(Lab3 / A2A на порту 9000), а той уже маршрутизує до інструментів і зовнішніх систем
(Knowledge Base, Lesson Credits, Task Manager).

Демонструє ланцюг: клієнт → A2A оркестратор → A2A асистент → tools / HTTP API.
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
# A2A Client: discover assistant and send tasks
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# A2A AgentExecutor
# ---------------------------------------------------------------------------

class OrchestratorAgentExecutor(AgentExecutor):
    """Оркестратор: усі користувацькі завдання передає одному A2A Assistant Agent."""

    def __init__(self, assistant_url: str = "http://localhost:9000"):
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
                status=TaskStatus(
                    state=TaskState.TASK_STATE_WORKING,
                    message=new_agent_text_message(
                        "Передаю запит асистенту (інструменти та зовнішні системи)..."
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
        """Показує Agent Card асистента — єдиного downstream A2A-агента з інструментами."""
        lines = [
            "# Оркестратор → Assistant Agent\n",
            "Оркестратор приймає запити клієнта і через A2A делегує їх **Personal Assistant Agent**, "
            "який викликає інструменти (KB, уроки, задачі).\n",
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
                lines.append("- **Skills** (тут — доступ до зовнішніх систем):")
                for s in skills:
                    lines.append(f"  - `{s.get('id')}`: {s.get('description', '')}")
            lines.append("")
        else:
            lines.append(f"## Assistant at {url}")
            lines.append("- **Status**: UNREACHABLE\n")
        return "\n".join(lines)

    async def _delegate_task(self, user_text: str) -> str:
        """Завжди делегує запит одному Personal Assistant Agent."""
        url = self.assistant_url
        card = await discover_agent(url)
        if not card:
            return (
                f"Асистент недоступний за `{url}`. "
                "Перевірте сервіс assistant-agent і змінну A2A_ASSISTANT_URL."
            )
        agent_name = card.get("name", url)
        result = await send_task_to_agent(url, user_text)
        return (
            f"**Оркестратор звернувся до**: {agent_name}\n"
            f"**Відповідь** (асистент обробив запит через інструменти / API):\n\n{result}"
        )

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        raise Exception("cancel not supported")
