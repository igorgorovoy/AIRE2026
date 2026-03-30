"""Shared helpers for A2A JSON-RPC over HTTP (a2a-sdk 0.3.x).

The send method is ``message/send`` (not the legacy ``a2a.SendMessage``).
The ``message`` object must include ``kind``, ``messageId``, and in ``parts`` use ``kind: \"text\"``.
"""

from __future__ import annotations

import json
import uuid
from typing import Any


def build_message_send_payload(
    text: str,
    *,
    request_id: str | None = None,
    blocking: bool = True,
) -> dict[str, Any]:
    """Build JSON-RPC body for ``message/send``."""
    return {
        "jsonrpc": "2.0",
        "id": request_id or str(uuid.uuid4()),
        "method": "message/send",
        "params": {
            "message": {
                "kind": "message",
                "role": "user",
                "messageId": str(uuid.uuid4()),
                "parts": [{"kind": "text", "text": text}],
            },
            "configuration": {"blocking": blocking},
        },
    }


def _parts_to_text(parts: list[Any]) -> str:
    chunks: list[str] = []
    for p in parts:
        if not isinstance(p, dict):
            continue
        if p.get("kind") == "text" or p.get("type") == "text":
            t = p.get("text")
            if isinstance(t, str) and t:
                chunks.append(t)
    return "\n".join(chunks)


def extract_task_or_message_text(result: Any) -> str:
    """Extract plain text from ``result`` of a successful ``message/send`` (Task or Message)."""
    if not isinstance(result, dict):
        return ""
    if result.get("kind") == "message":
        return _parts_to_text(result.get("parts") or [])

    chunks: list[str] = []
    for art in result.get("artifacts") or []:
        if isinstance(art, dict):
            chunks.append(_parts_to_text(art.get("parts") or []))
    status = result.get("status") or {}
    msg = status.get("message")
    if isinstance(msg, dict):
        chunks.append(_parts_to_text(msg.get("parts") or []))
    history = result.get("history") or []
    for hm in history:
        if isinstance(hm, dict) and hm.get("role") == "agent":
            chunks.append(_parts_to_text(hm.get("parts") or []))
    return "\n".join(c for c in chunks if c)


def format_jsonrpc_result(data: dict[str, Any]) -> str:
    """Return reply text or serialize error / raw result."""
    if err := data.get("error"):
        return json.dumps(err, ensure_ascii=False, indent=2)
    result = data.get("result")
    text = extract_task_or_message_text(result)
    if text:
        return text
    if result is not None:
        return json.dumps(result, ensure_ascii=False, indent=2)
    return json.dumps(data, ensure_ascii=False, indent=2)
