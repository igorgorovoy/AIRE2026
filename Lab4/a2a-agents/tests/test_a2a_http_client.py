"""Unit tests for JSON-RPC shape and reply text extraction."""

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from a2a_http_client import (  # noqa: E402
    build_message_send_payload,
    extract_task_or_message_text,
    format_jsonrpc_result,
)


def test_message_send_uses_sdk_method_name():
    p = build_message_send_payload("hello", request_id="r1")
    assert p["jsonrpc"] == "2.0"
    assert p["id"] == "r1"
    assert p["method"] == "message/send"
    msg = p["params"]["message"]
    assert msg["kind"] == "message"
    assert msg["role"] == "user"
    assert "messageId" in msg
    assert msg["parts"] == [{"kind": "text", "text": "hello"}]
    assert p["params"]["configuration"]["blocking"] is True


def test_extract_from_task_artifacts_camel_case():
    result = {
        "kind": "task",
        "id": "t1",
        "contextId": "c1",
        "status": {"state": "completed"},
        "artifacts": [
            {
                "artifactId": "a1",
                "parts": [{"kind": "text", "text": "Agent reply"}],
            }
        ],
    }
    assert extract_task_or_message_text(result) == "Agent reply"


def test_extract_supports_legacy_type_text_in_parts():
    result = {
        "artifacts": [{"parts": [{"type": "text", "text": "legacy"}]}],
    }
    assert extract_task_or_message_text(result) == "legacy"


def test_format_jsonrpc_error():
    data = {"error": {"code": -32601, "message": "Method not found"}}
    out = format_jsonrpc_result(data)
    assert "Method not found" in out
    assert "-32601" in out or "-32601" in json.dumps(data)


def test_format_jsonrpc_direct_message():
    data = {
        "result": {
            "kind": "message",
            "messageId": "m1",
            "role": "agent",
            "parts": [{"kind": "text", "text": "hi"}],
        }
    }
    assert format_jsonrpc_result(data) == "hi"
