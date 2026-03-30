"""A2A Personal Assistant Agent server.

Serves the assistant agent with:
- Agent Card at /.well-known/agent-card.json
- A2A JSON-RPC endpoint for task communication
- Skills: knowledge_base, lesson_credits, task_manager

Usage:
    python -m assistant-agent
    # or
    python src/assistant-agent/__main__.py

Environment:
    A2A_ASSISTANT_PORT — uvicorn port (default 14000)
    A2A_PUBLIC_BASE_URL — URL in Agent Card for clients (K8s / compose)
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

from agent_executor import AssistantAgentExecutor

HOST = "0.0.0.0"
PORT = int(os.getenv("A2A_ASSISTANT_PORT", "14000"))


def _agent_card_url() -> str:
    """Base URL in Agent Card (for clients and A2A). Set A2A_PUBLIC_BASE_URL in K8s."""
    base = os.getenv("A2A_PUBLIC_BASE_URL", "").strip().rstrip("/")
    if base:
        return f"{base}/"
    return f"http://localhost:{PORT}/"


# ---------------------------------------------------------------------------
# Agent Skills
# ---------------------------------------------------------------------------

skill_knowledge_base = AgentSkill(
    id="knowledge_base",
    name="Knowledge Base",
    description=(
        "Access Obsidian vault documents: list, search, read, and edit "
        "markdown documents. Get the document graph (nodes, edges)."
    ),
    tags=["knowledge-base", "obsidian", "documents", "search"],
    examples=[
        "Show the list of documents",
        "Get document '46 AWS/AWS Skill Builder.md'",
        "Show the knowledge base graph",
    ],
)

skill_lesson_credits = AgentSkill(
    id="lesson_credits",
    name="Lesson Credits",
    description=(
        "Track lesson balances: view calendars, check balance, "
        "top up or deduct lessons, manage transactions."
    ),
    tags=["lessons", "credits", "balance", "calendar"],
    examples=[
        "How many lessons are left?",
        "Top up 5 lessons",
        "Show transaction history",
    ],
)

skill_task_manager = AgentSkill(
    id="task_manager",
    name="Task Manager",
    description=(
        "Full task management: workspaces, boards, lists, cards, "
        "comments, and attachments. Kanban-style project tracking."
    ),
    tags=["tasks", "boards", "kanban", "project-management"],
    examples=[
        "List all workspaces",
        "Create a new card in list 'To Do'",
        "Show card details",
    ],
)

# ---------------------------------------------------------------------------
# Agent Card (public, served at /.well-known/agent-card.json)
# ---------------------------------------------------------------------------

_AGENT_ENDPOINT = _agent_card_url()

public_agent_card = AgentCard(
    name="Personal Assistant Agent",
    description=(
        "Personal AI assistant with access to Knowledge Base (Obsidian vault), "
        "Lesson Credits, and Task Manager."
    ),
    url=_AGENT_ENDPOINT,
    preferred_transport="JSONRPC",
    additional_interfaces=[
        AgentInterface(transport="JSONRPC", url=_AGENT_ENDPOINT),
    ],
    version="1.0.0",
    default_input_modes=["text"],
    default_output_modes=["text"],
    capabilities=AgentCapabilities(
        streaming=False,
        push_notifications=False,
    ),
    skills=[skill_knowledge_base, skill_lesson_credits, skill_task_manager],
)

# ---------------------------------------------------------------------------
# Server setup
# ---------------------------------------------------------------------------


def main():
    request_handler = DefaultRequestHandler(
        agent_executor=AssistantAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )

    app = A2AStarletteApplication(
        agent_card=public_agent_card,
        http_handler=request_handler,
    )

    print(f"Starting Personal Assistant A2A Agent on {HOST}:{PORT}")
    print(f"Agent Card: http://{HOST}:{PORT}/.well-known/agent-card.json")
    print(f"A2A Endpoint: http://{HOST}:{PORT}/")

    uvicorn.run(app.build(), host=HOST, port=PORT)


if __name__ == "__main__":
    main()
