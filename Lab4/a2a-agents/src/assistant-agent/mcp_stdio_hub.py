"""MCP stdio clients for the A2A assistant (same protocol as Lab3 MCPServer processes).

- Knowledge Base MCP is always started from the bundled ``mcp/knowledge_base_server.py``.
- Lesson Credits / Task Manager are optional: set env paths to Lab3 ``server.py`` files
  and **MCP_LESSON_CREDITS_CWD** / **MCP_TASKS_CWD** to the project root that contains
  ``agents/`` and ``core/`` (same layout as Lab3 Docker images).
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult, TextContent

logger = logging.getLogger(__name__)


def _subprocess_env() -> dict[str, str]:
    env = {**os.environ}
    if env.get("KB_API_KEY") and not env.get("API_KEY"):
        env["API_KEY"] = env["KB_API_KEY"]
    return env


def format_tool_result(result: CallToolResult) -> str:
    chunks: list[str] = []
    for block in result.content or []:
        if isinstance(block, TextContent):
            chunks.append(block.text)
        elif getattr(block, "text", None):
            chunks.append(str(block.text))
    text = "\n".join(chunks)
    if result.isError:
        return f"MCP error: {text}" if text else "MCP tool error"
    return text if text else "(empty tool result)"


class McpStdioSession:
    """One MCP server subprocess + persistent ``ClientSession``."""

    def __init__(
        self,
        name: str,
        script_path: Path,
        *,
        cwd: Path | None = None,
    ) -> None:
        self.name = name
        self.script_path = Path(script_path)
        self.cwd = Path(cwd) if cwd else self.script_path.parent
        self._stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None
        self._lock = asyncio.Lock()

    @property
    def configured(self) -> bool:
        return bool(str(self.script_path)) and self.script_path.is_file()

    async def _ensure_session(self) -> ClientSession:
        if self._session is not None:
            return self._session
        if not self.configured:
            raise FileNotFoundError(f"MCP script not found: {self.script_path}")

        stack = AsyncExitStack()
        params = StdioServerParameters(
            command=sys.executable,
            args=[str(self.script_path.resolve())],
            env=_subprocess_env(),
            cwd=str(self.cwd.resolve()),
        )
        try:
            read_write = await stack.enter_async_context(stdio_client(params))
            read, write = read_write
            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
        except Exception:
            await stack.aclose()
            raise

        self._stack = stack
        self._session = session
        logger.info("MCP session started: %s (%s)", self.name, self.script_path)
        return self._session

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> str:
        async with self._lock:
            session = await self._ensure_session()
            result = await session.call_tool(name, arguments or {})
        return format_tool_result(result)


def _a2a_agents_root() -> Path:
    """``Lab4/a2a-agents`` — or ``/app`` in Docker (flat copy + ``mcp/``)."""
    p = Path(__file__).resolve().parent
    if (p / "mcp" / "knowledge_base_server.py").is_file():
        return p
    return p.parent.parent


def _kb_script_default() -> Path:
    return _a2a_agents_root() / "mcp" / "knowledge_base_server.py"


def build_mcp_hub() -> AssistantMcpHub:
    return AssistantMcpHub()


class AssistantMcpHub:
    """KB (required script in image) + optional Lab3 lesson/tasks MCP servers."""

    def __init__(self) -> None:
        root = _a2a_agents_root()
        kb_path = Path(os.getenv("MCP_KB_SCRIPT", str(_kb_script_default()))).expanduser()
        self.kb = McpStdioSession("knowledge-base", kb_path, cwd=root)

        self.lessons: McpStdioSession | None = None
        ls = os.getenv("MCP_LESSON_CREDITS_SCRIPT", "").strip()
        if ls:
            p = Path(ls).expanduser()
            lcwd = os.getenv("MCP_LESSON_CREDITS_CWD", "").strip()
            cwd = Path(lcwd).expanduser() if lcwd else p.parent
            if p.is_file():
                self.lessons = McpStdioSession("lesson-credits", p, cwd=cwd)
            else:
                logger.warning("MCP_LESSON_CREDITS_SCRIPT set but missing: %s", p)

        self.tasks: McpStdioSession | None = None
        ts = os.getenv("MCP_TASKS_SCRIPT", "").strip()
        if ts:
            p = Path(ts).expanduser()
            tcwd = os.getenv("MCP_TASKS_CWD", "").strip()
            cwd = Path(tcwd).expanduser() if tcwd else p.parent
            if p.is_file():
                self.tasks = McpStdioSession("tasks", p, cwd=cwd)
            else:
                logger.warning("MCP_TASKS_SCRIPT set but missing: %s", p)


_hub: AssistantMcpHub | None = None
_hub_lock = asyncio.Lock()


async def get_mcp_hub() -> AssistantMcpHub:
    global _hub
    async with _hub_lock:
        if _hub is None:
            _hub = build_mcp_hub()
        return _hub
