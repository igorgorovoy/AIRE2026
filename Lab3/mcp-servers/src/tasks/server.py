#!/usr/bin/env python3
"""MCP Server для Task Manager — workspaces, boards, lists, cards, comments.

Потребує доступ до storage: local (.env) або lakeFS (STORAGE_BACKEND=lakefs, LAKEFS_*).
Запуск з кореня проєкту:
  python mcp-servers-tasks/server.py
  # або
  uv run mcp-servers-tasks/server.py

ENV:
  TASKS_ENV_FILE=.env.mcp — завантажити окремий конфіг (напр. для remote dev).
  ENABLE_DELETE_TOOLS=1 — увімкнути інструменти видалення (delete_card, тощо).
"""

import os
import sys
from pathlib import Path

# Додати корінь проєкту в path для імпорту agents
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Завантажити .env — storage backend (STORAGE_BACKEND) збігається з viz
# TASKS_ENV_FILE — опційно інший файл (напр. .env.mcp для remote dev)
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
    instructions="MCP сервер для керування задачами (Task Manager). Потребує lakeFS (STORAGE_BACKEND=lakefs, LAKEFS_* в .env).",
)


def _get_store():
    from agents.task_manager import task_store
    return task_store


def _labels_str(labels) -> str:
    """Labels: list[str] або list[dict] з text/color → рядок для відображення."""
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
    """Показати всі workspaces (робочі простори)."""
    store = _get_store()
    workspaces = store.list_workspaces()
    if not workspaces:
        return "Немає workspaces. Створіть через tasks_create_workspace."
    lines = [f"- {w['name']} (id: {w['id']})" for w in workspaces]
    return "\n".join(lines)


@mcp.tool()
def tasks_create_workspace(name: str) -> str:
    """Створити новий workspace."""
    store = _get_store()
    ws = store.create_workspace(name=name)
    return f"Створено workspace '{ws['name']}' (id: {ws['id']})"


@mcp.tool()
def tasks_update_workspace(workspace_id: str, name: str | None = None, archived: bool | None = None) -> str:
    """Оновити workspace (назва, archived)."""
    store = _get_store()
    ws = store.update_workspace(workspace_id, name=name, archived=archived)
    if not ws:
        return f"Workspace {workspace_id} не знайдено."
    return f"Оновлено workspace '{ws['name']}'"


# ---------------------------------------------------------------------------
# Boards
# ---------------------------------------------------------------------------


@mcp.tool()
def tasks_list_boards(workspace_id: str) -> str:
    """Показати дошки в workspace."""
    store = _get_store()
    boards = store.list_boards(workspace_id)
    if not boards:
        return "Немає досок. Створіть через tasks_create_board."
    lines = [f"- {b['name']} (id: {b['id']})" for b in boards]
    return "\n".join(lines)


@mcp.tool()
def tasks_create_board(workspace_id: str, name: str) -> str:
    """Створити дошку в workspace."""
    store = _get_store()
    board = store.create_board(workspace_id=workspace_id, name=name)
    return f"Створено дошку '{board['name']}' (id: {board['id']})"


@mcp.tool()
def tasks_update_board(board_id: str, name: str | None = None, archived: bool | None = None) -> str:
    """Оновити дошку (назва, archived)."""
    store = _get_store()
    board = store.update_board(board_id, name=name, archived=archived)
    if not board:
        return f"Дошку {board_id} не знайдено."
    return f"Оновлено дошку '{board['name']}'"


@mcp.tool()
def tasks_move_board(board_id: str, workspace_id: str) -> str:
    """Перемістити дошку в інший workspace."""
    store = _get_store()
    board = store.move_board(board_id, workspace_id)
    if not board:
        return f"Дошку {board_id} не знайдено."
    return f"Переміщено дошку '{board['name']}' в workspace {workspace_id}"


# ---------------------------------------------------------------------------
# Lists
# ---------------------------------------------------------------------------


@mcp.tool()
def tasks_list_lists(board_id: str) -> str:
    """Показати списки (колонки) на дошці."""
    store = _get_store()
    lists = store.list_lists(board_id=board_id)
    if not lists:
        return "Немає списків. Створіть через tasks_create_list."
    lines = [f"- {l['title']} (id: {l['id']})" for l in lists]
    return "\n".join(lines)


@mcp.tool()
def tasks_create_list(board_id: str, title: str) -> str:
    """Створити список (колонку) на дошці."""
    store = _get_store()
    lst = store.create_list(board_id=board_id, title=title)
    return f"Створено список '{lst['title']}' (id: {lst['id']})"


@mcp.tool()
def tasks_update_list(list_id: str, title: str | None = None) -> str:
    """Оновити список (назва)."""
    store = _get_store()
    lst = store.update_list(list_id, title=title)
    if not lst:
        return f"Список {list_id} не знайдено."
    return f"Оновлено список '{lst['title']}'"


@mcp.tool()
def tasks_move_list(list_id: str, board_id: str) -> str:
    """Перемістити список на іншу дошку."""
    store = _get_store()
    lst = store.move_list(list_id, board_id)
    if not lst:
        return f"Список {list_id} не знайдено."
    return f"Переміщено список '{lst['title']}' на дошку {board_id}"


# ---------------------------------------------------------------------------
# Cards
# ---------------------------------------------------------------------------


@mcp.tool()
def tasks_list_cards(list_id: str | None = None) -> str:
    """Показати картки. Якщо list_id не вказано — всі картки."""
    store = _get_store()
    cards = store.list_cards(list_id=list_id)
    if not cards:
        return "Немає карток."
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
    """Створити картку (задачу) в списку. priority: urgent, high, medium, low. due_date: YYYY-MM-DD. story_points/original_estimate для velocity."""
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
    return f"Створено картку '{card['title']}' (id: {card['id']})"


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
    """Оновити картку. priority: urgent, high, medium, low. due_date: YYYY-MM-DD або null. story_points/original_estimate для velocity. assignee — виконавець (display name); порожній рядок — очистити."""
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
        return f"Картку {card_id} не знайдено."
    return f"Оновлено картку '{card['title']}'"


@mcp.tool()
def tasks_get_card(card_id: str) -> str:
    """Отримати деталі картки (title, description, labels, priority, due_date, finished, story_points, blocked_since)."""
    store = _get_store()
    card = store.get_card(card_id)
    if not card:
        return f"Картку {card_id} не знайдено."
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
    """Перемістити картку в інший список."""
    store = _get_store()
    card = store.move_card(card_id=card_id, list_id=list_id)
    if not card:
        return f"Картку {card_id} не знайдено."
    return f"Переміщено '{card['title']}' в список {list_id}"


@mcp.tool()
def tasks_delete_card(card_id: str) -> str:
    """Видалити картку. Потребує ENABLE_DELETE_TOOLS=1 в .env."""
    if not ENABLE_DELETE_TOOLS:
        return "Видалення вимкнено. Встановіть ENABLE_DELETE_TOOLS=1 в .env."
    store = _get_store()
    ok = store.delete_card(card_id)
    return "Картку видалено." if ok else f"Картку {card_id} не знайдено."


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------


@mcp.tool()
def tasks_list_comments(card_id: str) -> str:
    """Показати коментарі до картки."""
    store = _get_store()
    comments = store.list_comments(card_id)
    if not comments:
        return "Немає коментарів."
    lines = [f"- [{c.get('author', '?')}] {c.get('content', '')}" for c in comments]
    return "\n".join(lines)


@mcp.tool()
def tasks_add_comment(card_id: str, content: str, author: str = "User", trello_id: str | None = None) -> str:
    """Додати коментар до картки. Якщо trello_id вказано — ідемпотентно: пропускає, якщо коментар з [Trello:id] вже є."""
    store = _get_store()
    if trello_id:
        marker = f"[Trello:{trello_id}]"
        for c in store.list_comments(card_id):
            if marker in (c.get("content") or ""):
                return f"Коментар з {marker} вже є (пропущено)"
        content = f"{marker} {content}"
    comment = store.add_comment(card_id=card_id, content=content, author=author)
    return f"Додано коментар (id: {comment['id']})"


@mcp.tool()
def tasks_list_attachments(card_id: str) -> str:
    """Показати аттачменти картки (filename, id). Для ідемпотентності — перевірити перед додаванням."""
    store = _get_store()
    atts = store.list_attachments(card_id)
    if not atts:
        return "Немає аттачментів."
    lines = [f"- {a.get('filename', '?')} (id: {a['id']})" for a in atts]
    return "\n".join(lines)


@mcp.tool()
def tasks_add_attachment(card_id: str, file_path: str) -> str:
    """Додати аттачмент до картки з локального файлу. Ідемпотентно: пропускає, якщо filename вже є."""
    store = _get_store()
    path = Path(file_path)
    if not path.exists():
        return f"Файл не знайдено: {file_path}"
    existing = {a.get("filename", "") for a in store.list_attachments(card_id)}
    if path.name in existing:
        return f"Аттачмент '{path.name}' вже є (пропущено)"
    content = path.read_bytes()
    att = store.add_attachment(
        card_id=card_id,
        filename=path.name,
        content=content,
        mime_type=None,
    )
    return f"Додано аттачмент '{att['filename']}' (id: {att['id']})"


# ---------------------------------------------------------------------------
# Beads sync
# ---------------------------------------------------------------------------


@mcp.tool()
def tasks_sync_beads(
    workspace: str = "Beads",
    board: str = "Beads Sync",
    dry_run: bool = False,
) -> str:
    """Синхронізувати задачі з beads (bd) у Task Manager. workspace — назва workspace, board — назва дошки. Якщо не існують — створюються. Картки мають label bead:<id> для ідемпотентності. Приклад: workspace='Personal assistant', board='Expert Memory Machine'."""
    import subprocess
    root = Path(__file__).resolve().parents[1]
    script = root / "scripts" / "beads_to_tasks_sync.py"
    if not script.exists():
        return f"Скрипт не знайдено: {script}"
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
    """Отримати повну дошку зі списками та картками (для огляду)."""
    store = _get_store()
    board = store.get_full_board(board_id)
    lines = []
    for lst in board.get("lists", []):
        lines.append(f"\n## {lst['title']}")
        for card in lst.get("cards", []):
            labels = _labels_str(card.get("labels") or [])
            lines.append(f"  - {card['title']}{labels} (id: {card['id']})")
    return "\n".join(lines) if lines else "Дошка порожня."


if __name__ == "__main__":
    mcp.run(transport="stdio")
