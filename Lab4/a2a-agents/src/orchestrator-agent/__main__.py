"""A2A Orchestrator Agent server.

Discovers other A2A agents via Well-Known URI and delegates tasks.
Demonstrates agent-to-agent communication via A2A protocol.

Usage:
    python -m orchestrator-agent
    # or
    python src/orchestrator-agent/__main__.py

Environment:
    A2A_AGENT_URLS — comma-separated list of A2A agent base URLs
                     (default: http://localhost:9000)
"""

import os

import uvicorn

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)

from agent_executor import OrchestratorAgentExecutor

HOST = "0.0.0.0"
PORT = 9001

# Parse agent URLs from environment
AGENT_URLS = [
    u.strip()
    for u in os.getenv("A2A_AGENT_URLS", "http://localhost:9000").split(",")
    if u.strip()
]

# ---------------------------------------------------------------------------
# Agent Skills
# ---------------------------------------------------------------------------

skill_orchestration = AgentSkill(
    id="orchestration",
    name="Agent Orchestration",
    description=(
        "Discover available A2A agents, inspect their capabilities, "
        "and delegate tasks to the best matching agent."
    ),
    tags=["orchestration", "delegation", "routing", "multi-agent"],
    examples=[
        "Discover available agents",
        "List agents",
        "Покажи список документів (delegates to assistant)",
    ],
)

# ---------------------------------------------------------------------------
# Agent Card
# ---------------------------------------------------------------------------

public_agent_card = AgentCard(
    name="Orchestrator Agent",
    description=(
        "A2A Orchestrator — discovers other agents via Well-Known URI "
        "and delegates tasks based on skill matching. "
        "Demonstrates agent-to-agent communication."
    ),
    url=f"http://localhost:{PORT}/",
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
        agent_executor=OrchestratorAgentExecutor(agent_urls=AGENT_URLS),
        task_store=InMemoryTaskStore(),
    )

    app = A2AStarletteApplication(
        agent_card=public_agent_card,
        http_handler=request_handler,
    )

    print(f"Starting Orchestrator A2A Agent on {HOST}:{PORT}")
    print(f"Agent Card: http://{HOST}:{PORT}/.well-known/agent-card.json")
    print(f"Target agents: {AGENT_URLS}")

    uvicorn.run(app.build(), host=HOST, port=PORT)


if __name__ == "__main__":
    main()
