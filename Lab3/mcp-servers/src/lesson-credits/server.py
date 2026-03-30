#!/usr/bin/env python3
"""MCP server for Lesson Credits — top-ups and deductions (English. Mary).

Requires storage: local (.env) or lakeFS (STORAGE_BACKEND=lakefs, LAKEFS_*).
Run from project root:
  python mcp-servers-lesson-credits/server.py
  uv run mcp-servers-lesson-credits/server.py

ENV:
  TASKS_ENV_FILE=.env.mcp — load alternate config (e.g. remote dev).
  ENABLE_DELETE_TOOLS=1   — enable delete tools (lessons_delete_transaction).
"""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(_PROJECT_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(_PROJECT_ROOT / ".env", override=False)
    _mcp_env = os.environ.get("TASKS_ENV_FILE")
    if _mcp_env:
        _mcp_path = _PROJECT_ROOT / _mcp_env
        if _mcp_path.exists():
            load_dotenv(_mcp_path, override=True)
except ImportError:
    pass

ENABLE_DELETE_TOOLS = os.environ.get("ENABLE_DELETE_TOOLS", "").lower() in ("1", "true", "yes")

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "lesson-credits",
    instructions="MCP server for lesson credit top-ups and deductions. Calendar English. Mary. Tools: balance, top-up, deduct, delete transaction.",
)


def _get_calendar_store():
    from agents.calendar_agent import calendar_store
    return calendar_store


def _get_lesson_repo():
    from core.repository.lesson_credits import lesson_credits_repository
    return lesson_credits_repository


def _has_lesson_tracking(cal: dict) -> bool:
    if cal.get("lesson_tracking_enabled"):
        return True
    return "English. Mary" in (cal.get("name") or "")


def _create_calendar_event(calendar_id: str, title: str, created_at: str, description: str = "") -> dict | None:
    try:
        store = _get_calendar_store()
        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        start = dt.isoformat().replace("+00:00", "Z")
        end_dt = dt + timedelta(hours=1)
        end = end_dt.isoformat().replace("+00:00", "Z")
        return store.create_event(calendar_id=calendar_id, title=title, start=start, end=end, description=description)
    except Exception:
        return None


@mcp.tool()
def lessons_list_calendars() -> str:
    """List calendars with lesson tracking (English. Mary). Returns id and name for calendar_id."""
    store = _get_calendar_store()
    calendars = store.list_calendars()
    lesson_cals = [c for c in calendars if _has_lesson_tracking(c)]
    if not lesson_cals:
        return "No calendars with lesson tracking. Add lesson_tracking_enabled or an 'English. Mary' calendar."
    lines = [f"- {c.get('name', '?')} (id: {c.get('id', '?')})" for c in lesson_cals]
    return "\n".join(lines)


@mcp.tool()
def lessons_get_balance(calendar_id: str) -> str:
    """Get balance and recent transactions for a lesson-tracking calendar."""
    store = _get_calendar_store()
    cal = store.get_calendar(calendar_id)
    if not cal:
        return f"Calendar {calendar_id} not found."
    if not _has_lesson_tracking(cal):
        return "Calendar has no lesson tracking (needs English. Mary or lesson_tracking_enabled)."
    repo = _get_lesson_repo()
    balance, transactions = repo.get_balance(calendar_id)
    recent = transactions[-20:] if transactions else []
    lines = [f"Balance: {balance} lessons", "Recent transactions:"]
    for tx in reversed(recent):
        t = tx.get("type", "?")
        amt = tx.get("amount", 0)
        note = tx.get("note", "") or ""
        lines.append(f"  - {t}: {amt:+d} | {tx.get('created_at', '')[:10]} {note}")
    return "\n".join(lines)


@mcp.tool()
def lessons_top_up(calendar_id: str, amount: int, note: str = "") -> str:
    """Top up lesson balance (e.g. after package payment). amount — number of lessons."""
    if amount <= 0:
        return "amount must be > 0"
    store = _get_calendar_store()
    cal = store.get_calendar(calendar_id)
    if not cal:
        return f"Calendar {calendar_id} not found."
    if not _has_lesson_tracking(cal):
        return "Calendar has no lesson tracking."
    created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    evt = _create_calendar_event(
        calendar_id,
        title="Top up",
        created_at=created_at,
        description=f"Top up: +{amount} lessons" + (f" — {note}" if note else ""),
    )
    repo = _get_lesson_repo()
    try:
        tx = repo.add_top_up(
            calendar_id, amount, note=note, created_at=created_at,
            calendar_event_id=evt["id"] if evt else None,
        )
        balance, _ = repo.get_balance(calendar_id)
        return f"Topped up +{amount}. Balance: {balance}. Transaction id: {tx.get('id', '')}"
    except ValueError as e:
        return f"Error: {e}"


@mcp.tool()
def lessons_deduct(calendar_id: str, amount: int = 1, note: str = "") -> str:
    """Deduct lessons (e.g. after a session). amount defaults to 1."""
    if amount <= 0:
        return "amount must be > 0"
    store = _get_calendar_store()
    cal = store.get_calendar(calendar_id)
    if not cal:
        return f"Calendar {calendar_id} not found."
    if not _has_lesson_tracking(cal):
        return "Calendar has no lesson tracking."
    created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    evt = _create_calendar_event(
        calendar_id,
        title="Funds write-off",
        created_at=created_at,
        description=f"Funds write-off: -{amount} lessons" + (f" — {note}" if note else ""),
    )
    repo = _get_lesson_repo()
    try:
        tx = repo.add_deduction(
            calendar_id, amount=amount, note=note, created_at=created_at,
            calendar_event_id=evt["id"] if evt else None,
        )
        balance, _ = repo.get_balance(calendar_id)
        return f"Deducted -{amount}. Balance: {balance}. Transaction id: {tx.get('id', '')}"
    except ValueError as e:
        return f"Error: {e}"


@mcp.tool()
def lessons_delete_transaction(calendar_id: str, transaction_id: str) -> str:
    """Delete a transaction (reversal for mistakes). Requires ENABLE_DELETE_TOOLS=1."""
    if not ENABLE_DELETE_TOOLS:
        return "Deletes disabled. Set ENABLE_DELETE_TOOLS=1 in .env."
    store = _get_calendar_store()
    cal = store.get_calendar(calendar_id)
    if not cal:
        return f"Calendar {calendar_id} not found."
    if not _has_lesson_tracking(cal):
        return "Calendar has no lesson tracking."
    repo = _get_lesson_repo()
    deleted = repo.delete_transaction(calendar_id, transaction_id)
    if not deleted:
        return f"Transaction {transaction_id} not found."
    ev_id = deleted.get("calendar_event_id")
    if ev_id:
        try:
            store.delete_event(ev_id)
        except Exception:
            pass
    balance, _ = repo.get_balance(calendar_id)
    return f"Transaction deleted. Balance: {balance}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
