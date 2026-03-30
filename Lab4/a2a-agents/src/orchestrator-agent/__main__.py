"""A2A Orchestrator Agent server.

Single client entry point: forwards requests to the Personal Assistant Agent over A2A.
The assistant (Lab3) invokes tools and external APIs — the orchestrator does not.

Usage:
    python -m orchestrator-agent
    # or
    python src/orchestrator-agent/__main__.py

Environment:
    A2A_ASSISTANT_URL — base URL of the A2A Personal Assistant Agent
                        (default: http://localhost:14000)
    A2A_AGENT_URLS   — legacy: if A2A_ASSISTANT_URL is empty, first URL
                        from comma-separated list is used
"""

import os

import uvicorn

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
)

from agent_executor import OrchestratorAgentExecutor

HOST = "0.0.0.0"
PORT = int(os.getenv("A2A_ORCHESTRATOR_PORT", "14001"))


def _resolve_assistant_url() -> str:
    explicit = os.getenv("A2A_ASSISTANT_URL", "").strip()
    if explicit:
        return explicit.rstrip("/")
    legacy = os.getenv("A2A_AGENT_URLS", "http://localhost:14000").strip()
    first = legacy.split(",")[0].strip()
    return first.rstrip("/") if first else "http://localhost:14000"


ASSISTANT_URL = _resolve_assistant_url()


def _agent_card_url() -> str:
    """Public orchestrator URL in Agent Card. Set A2A_PUBLIC_BASE_URL in K8s."""
    base = os.getenv("A2A_PUBLIC_BASE_URL", "").strip().rstrip("/")
    if base:
        return f"{base}/"
    return f"http://localhost:{PORT}/"


_ORCH_ENDPOINT = _agent_card_url()

# ---------------------------------------------------------------------------
# Agent Skills
# ---------------------------------------------------------------------------

skill_orchestration = AgentSkill(
    id="orchestration",
    name="Agent Orchestration",
    description=(
        "Accepts client requests and forwards them to the Personal Assistant Agent over A2A; "
        "the assistant invokes tools (KB, lessons, tasks) for external systems."
    ),
    tags=["orchestration", "delegation", "assistant", "a2a"],
    examples=[
        "discover — show the assistant Agent Card",
        "Show the list of documents (via assistant)",
        "help",
    ],
)

# ---------------------------------------------------------------------------
# Agent Card
# ---------------------------------------------------------------------------

public_agent_card = AgentCard(
    name="Orchestrator Agent",
    description=(
        "A2A orchestrator: client entry point. All tasks are sent to the "
        "Personal Assistant Agent over A2A; the assistant uses tools and "
        "external systems (Knowledge Base, Lesson Credits, Task Manager)."
    ),
    url=_ORCH_ENDPOINT,
    preferred_transport="JSONRPC",
    additional_interfaces=[
        AgentInterface(transport="JSONRPC", url=_ORCH_ENDPOINT),
    ],
    version="1.0.0",
    default_input_modes=["text"],
    default_output_modes=["text"],
    capabilities=AgentCapabilities(
        streaming=False,
        push_notifications=False,
    ),
    skills=[skill_orchestration],
)

# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------


def main():
    request_handler = DefaultRequestHandler(
        agent_executor=OrchestratorAgentExecutor(assistant_url=ASSISTANT_URL),
        task_store=InMemoryTaskStore(),
    )

    app = A2AStarletteApplication(
        agent_card=public_agent_card,
        http_handler=request_handler,
    )

    print(f"Starting Orchestrator A2A Agent on {HOST}:{PORT}")
    print(f"Agent Card: http://{HOST}:{PORT}/.well-known/agent-card.json")
    print(f"Assistant (delegation target): {ASSISTANT_URL}")

    uvicorn.run(app.build(), host=HOST, port=PORT)


if __name__ == "__main__":
    main()
