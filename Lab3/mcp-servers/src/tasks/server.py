#!/usr/bin/env python3
"""MCP server for Task Manager — workspaces, boards, lists, cards, comments.

Requires storage: local (.env) or lakeFS (STORAGE_BACKEND=lakefs, LAKEFS_*).
Run from project root:
  python mcp-servers-tasks/server.py
  # or
  uv run mcp-servers-tasks/server.py

ENV:
  TASKS_ENV_FILE=.env.mcp — load alternate config (e.g. remote dev).
  ENABLE_DELETE_TOOLS=1 — enable delete tools (delete_card, etc.).
"""

import os
import sys
from pathlib import Path

# Add project root to path for agents imports
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Load .env — STORAGE_BACKEND matches viz
# TASKS_ENV_FILE — optional alternate file (e.g. .env.mcp for remote dev)
try:
    from dotenv import load_dotenv

    load_dotenv(_PROJECT_ROOT / ".env", override=False)
    _mcp_env = os.environ.get("TASKS_ENV_FILE")
    if _mcp_env:
        _mcp_path = _PROJECT_ROOT / _mcp_env
        if _mcp_path.exists():
            load_dotenv(_mcp_path, override=True)
except ImportError:
    _env_file = _PROJECT_ROOT / ".env"
    if _env_file.exists():
        with open(_env_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    os.environ[k.strip()] = v.strip().strip("'\"")
    _mcp_env = os.environ.get("TASKS_ENV_FILE")
    if _mcp_env:
        _mcp_path = _PROJECT_ROOT / _mcp_env
        if _mcp_path.exists():
            with open(_mcp_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, _, v = line.partition("=")
                        os.environ[k.strip()] = v.strip().strip("'\"")

ENABLE_DELETE_TOOLS = os.environ.get("ENABLE_DELETE_TOOLS", "").lower() in ("1", "true", "yes")

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "tasks",
    instructions="MCP server for task management (Task Manager). Requires lakeFS (STORAGE_BACKEND=lakefs, LAKEFS_* in .env).",
)


def _get_store():
    from agents.task_manager import task_store
    return task_store


def _labels_str(labels) -> str:
    """Labels: list[str] or list[dict] with text/color → display string."""
    if not labels:
        return ""
    texts = []
    for L in labels:
        if isinstance(L, dict) and L.get("text"):
            texts.append(str(L["text"]))
        elif isinstance(L, str):
            texts.append(L)
    return f" [{', '.join(texts)}]" if texts else ""


# ---------------------------------------------------------------------------
# Workspaces
# ---------------------------------------------------------------------------


@mcp.tool()
def tasks_list_workspaces() -> str:
    """List all workspaces."""
    store = _get_store()
    workspaces = store.list_workspaces()
    if not workspaces:
        return "No workspaces. Create one with tasks_create_workspace."
    lines = [f"- {w['name']} (id: {w['id']})" for w in workspaces]
    return "\n".join(lines)


@mcp.tool()
def tasks_create_workspace(name: str) -> str:
    """Create a new workspace."""
    store = _get_store()
    ws = store.create_workspace(name=name)
    return f"Created workspace '{ws['name']}' (id: {ws['id']})"


@mcp.tool()
def tasks_update_workspace(workspace_id: str, name: str | None = None, archived: bool | None = None) -> str:
    """Update workspace (name, archived)."""
    store = _get_store()
    ws = store.update_workspace(workspace_id, name=name, archived=archived)
    if not ws:
        return f"Workspace {workspace_id} not found."
    return f"Updated workspace '{ws['name']}'"


# ---------------------------------------------------------------------------
# Boards
# ---------------------------------------------------------------------------


@mcp.tool()
def tasks_list_boards(workspace_id: str) -> str:
    """List boards in a workspace."""
    store = _get_store()
    boards = store.list_boards(workspace_id)
    if not boards:
        return "No boards. Create one with tasks_create_board."
    lines = [f"- {b['name']} (id: {b['id']})" for b in boards]
    return "\n".join(lines)


@mcp.tool()
def tasks_create_board(workspace_id: str, name: str) -> str:
    """Create a board in a workspace."""
    store = _get_store()
    board = store.create_board(workspace_id=workspace_id, name=name)
    return f"Created board '{board['name']}' (id: {board['id']})"


@mcp.tool()
def tasks_update_board(board_id: str, name: str | None = None, archived: bool | None = None) -> str:
    """Update board (name, archived)."""
    store = _get_store()
    board = store.update_board(board_id, name=name, archived=archived)
    if not board:
        return f"Board {board_id} not found."
    return f"Updated board '{board['name']}'"


@mcp.tool()
def tasks_move_board(board_id: str, workspace_id: str) -> str:
    """Move a board to another workspace."""
    store = _get_store()
    board = store.move_board(board_id, workspace_id)
    if not board:
        return f"Board {board_id} not found."
    return f"Moved board '{board['name']}' to workspace {workspace_id}"


# ---------------------------------------------------------------------------
# Lists
# ---------------------------------------------------------------------------


@mcp.tool()
def tasks_list_lists(board_id: str) -> str:
    """List columns (lists) on a board."""
    store = _get_store()
    lists = store.list_lists(board_id=board_id)
    if not lists:
        return "No lists. Create one with tasks_create_list."
    lines = [f"- {l['title']} (id: {l['id']})" for l in lists]
    return "\n".join(lines)


@mcp.tool()
def tasks_create_list(board_id: str, title: str) -> str:
    """Create a list (column) on a board."""
    store = _get_store()
    lst = store.create_list(board_id=board_id, title=title)
    return f"Created list '{lst['title']}' (id: {lst['id']})"


@mcp.tool()
def tasks_update_list(list_id: str, title: str | None = None) -> str:
    """Update list (title)."""
    store = _get_store()
    lst = store.update_list(list_id, title=title)
    if not lst:
        return f"List {list_id} not found."
    return f"Updated list '{lst['title']}'"


@mcp.tool()
def tasks_move_list(list_id: str, board_id: str) -> str:
    """Move a list to another board."""
    store = _get_store()
    lst = store.move_list(list_id, board_id)
    if not lst:
        return f"List {list_id} not found."
    return f"Moved list '{lst['title']}' to board {board_id}"


# ---------------------------------------------------------------------------
# Cards
# ---------------------------------------------------------------------------


@mcp.tool()
def tasks_list_cards(list_id: str | None = None) -> str:
    """List cards. If list_id is omitted, all cards."""
    store = _get_store()
    cards = store.list_cards(list_id=list_id)
    if not cards:
        return "No cards."
    lines = []
    for c in cards:
        labels = _labels_str(c.get("labels") or [])
        lines.append(f"- {c['title']}{labels} (id: {c['id']}, list: {c.get('list_id', '?')})")
    return "\n".join(lines)


@mcp.tool()
def tasks_create_card(
    list_id: str,
    title: str,
    description: str = "",
    labels: list[str] | None = None,
    priority: str | None = None,
    due_date: str | None = None,
    story_points: int | None = None,
    original_estimate: int | None = None,
) -> str:
    """Create a card in a list. priority: urgent, high, medium, low. due_date: YYYY-MM-DD. story_points/original_estimate for velocity."""
    store = _get_store()
    card = store.create_card(
        list_id=list_id,
        title=title,
        description=description,
        labels=labels or [],
        priority=priority,
        due_date=due_date,
        story_points=story_points,
        original_estimate=original_estimate,
    )
    return f"Created card '{card['title']}' (id: {card['id']})"


@mcp.tool()
def tasks_update_card(
    card_id: str,
    title: str | None = None,
    description: str | None = None,
    list_id: str | None = None,
    labels: list[str] | None = None,
    priority: str | None = None,
    due_date: str | None = None,
    finished: bool | None = None,
    story_points: int | None = None,
    original_estimate: int | None = None,
    assignee: str | None = None,
) -> str:
    """Update card. priority: urgent, high, medium, low. due_date: YYYY-MM-DD or null. story_points/original_estimate for velocity. assignee — display name; empty string clears."""
    store = _get_store()
    assignee_arg = assignee if assignee is not None else ...
    card = store.update_card(
        card_id=card_id,
        title=title,
        description=description,
        list_id=list_id,
        labels=labels,
        priority=priority,
        due_date=due_date,
        finished=finished,
        story_points=story_points,
        original_estimate=original_estimate,
        assignee=assignee_arg,
    )
    if not card:
        return f"Card {card_id} not found."
    return f"Updated card '{card['title']}'"


@mcp.tool()
def tasks_get_card(card_id: str) -> str:
    """Get card details (title, description, labels, priority, due_date, finished, story_points, blocked_since)."""
    store = _get_store()
    card = store.get_card(card_id)
    if not card:
        return f"Card {card_id} not found."
    labels = _labels_str(card.get("labels") or [])
    parts = [
        f"# {card['title']}",
        f"id: {card['id']}",
        f"list_id: {card.get('list_id', '?')}",
        f"priority: {card.get('priority', 'medium')}",
        f"finished: {card.get('finished', False)}",
    ]
    if card.get("description"):
        parts.append(f"description: {card['description']}")
    if labels:
        parts.append(f"labels:{labels}")
    if card.get("due_date"):
        parts.append(f"due_date: {card['due_date']}")
    if card.get("story_points") is not None:
        parts.append(f"story_points: {card['story_points']}")
    if card.get("original_estimate") is not None:
        parts.append(f"original_estimate: {card['original_estimate']}")
    if card.get("blocked_since"):
        parts.append(f"blocked_since: {card['blocked_since']}")
    return "\n".join(parts)


@mcp.tool()
def tasks_move_card(card_id: str, list_id: str) -> str:
    """Move a card to another list."""
    store = _get_store()
    card = store.move_card(card_id=card_id, list_id=list_id)
    if not card:
        return f"Card {card_id} not found."
    return f"Moved '{card['title']}' to list {list_id}"


@mcp.tool()
def tasks_delete_card(card_id: str) -> str:
    """Delete a card. Requires ENABLE_DELETE_TOOLS=1 in .env."""
    if not ENABLE_DELETE_TOOLS:
        return "Deletes disabled. Set ENABLE_DELETE_TOOLS=1 in .env."
    store = _get_store()
    ok = store.delete_card(card_id)
    return "Card deleted." if ok else f"Card {card_id} not found."


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------


@mcp.tool()
def tasks_list_comments(card_id: str) -> str:
    """List comments on a card."""
    store = _get_store()
    comments = store.list_comments(card_id)
    if not comments:
        return "No comments."
    lines = [f"- [{c.get('author', '?')}] {c.get('content', '')}" for c in comments]
    return "\n".join(lines)


@mcp.tool()
def tasks_add_comment(card_id: str, content: str, author: str = "User", trello_id: str | None = None) -> str:
    """Add a comment. If trello_id is set, idempotent: skips if a comment with [Trello:id] already exists."""
    store = _get_store()
    if trello_id:
        marker = f"[Trello:{trello_id}]"
        for c in store.list_comments(card_id):
            if marker in (c.get("content") or ""):
                return f"Comment with {marker} already exists (skipped)"
        content = f"{marker} {content}"
    comment = store.add_comment(card_id=card_id, content=content, author=author)
    return f"Added comment (id: {comment['id']})"


@mcp.tool()
def tasks_list_attachments(card_id: str) -> str:
    """List card attachments (filename, id). Check before add for idempotency."""
    store = _get_store()
    atts = store.list_attachments(card_id)
    if not atts:
        return "No attachments."
    lines = [f"- {a.get('filename', '?')} (id: {a['id']})" for a in atts]
    return "\n".join(lines)


@mcp.tool()
def tasks_add_attachment(card_id: str, file_path: str) -> str:
    """Add attachment from a local file. Idempotent: skips if filename already exists."""
    store = _get_store()
    path = Path(file_path)
    if not path.exists():
        return f"File not found: {file_path}"
    existing = {a.get("filename", "") for a in store.list_attachments(card_id)}
    if path.name in existing:
        return f"Attachment '{path.name}' already exists (skipped)"
    content = path.read_bytes()
    att = store.add_attachment(
        card_id=card_id,
        filename=path.name,
        content=content,
        mime_type=None,
    )
    return f"Added attachment '{att['filename']}' (id: {att['id']})"


# ---------------------------------------------------------------------------
# Beads sync
# ---------------------------------------------------------------------------


@mcp.tool()
def tasks_sync_beads(
    workspace: str = "Beads",
    board: str = "Beads Sync",
    dry_run: bool = False,
) -> str:
    """Sync tasks from beads (bd) into Task Manager. workspace/board names; created if missing. Cards use label bead:<id> for idempotency. Example: workspace='Personal assistant', board='Expert Memory Machine'."""
    import subprocess
    root = Path(__file__).resolve().parents[1]
    script = root / "scripts" / "beads_to_tasks_sync.py"
    if not script.exists():
        return f"Script not found: {script}"
    cmd = [sys.executable, str(script), "--workspace", workspace, "--board", board]
    if dry_run:
        cmd.append("--dry-run")
    result = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True, timeout=60)
    out = result.stdout or ""
    err = result.stderr or ""
    if result.returncode != 0:
        return f"Sync failed:\n{err}\n{out}"
    return out


# ---------------------------------------------------------------------------
# Full board
# ---------------------------------------------------------------------------


@mcp.tool()
def tasks_get_board(board_id: str) -> str:
    """Get full board with lists and cards (overview)."""
    store = _get_store()
    board = store.get_full_board(board_id)
    lines = []
    for lst in board.get("lists", []):
        lines.append(f"\n## {lst['title']}")
        for card in lst.get("cards", []):
            labels = _labels_str(card.get("labels") or [])
            lines.append(f"  - {card['title']}{labels} (id: {card['id']})")
    return "\n".join(lines) if lines else "Board is empty."


if __name__ == "__main__":
    mcp.run(transport="stdio")
