#!/usr/bin/env python3
"""Test script for A2A agents.

Demonstrates:
1. Fetching Agent Card from Well-Known URI
2. Sending a task via A2A JSON-RPC (``message/send``)
3. Agent-to-agent delegation via orchestrator

Usage:
    # Test assistant agent directly
    python test_a2a.py assistant

    # Test orchestrator (delegates to assistant)
    python test_a2a.py orchestrator

    # Discover agents
    python test_a2a.py discover

    # Quick check with minimal output (exit code 0 / 1)
    python test_a2a.py smoke
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx

# Shared helpers (same module as in the orchestrator Docker image)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from a2a_http_client import (  # noqa: E402
    build_message_send_payload,
    format_jsonrpc_result,
)

# Default 14000/14001 — agent ports (compose / local run).
# K8s: kubectl port-forward svc/a2a-assistant-agent -n a2a 14000:14000 → same defaults
ASSISTANT_URL = os.getenv("A2A_TEST_ASSISTANT_URL", "http://127.0.0.1:14000").rstrip("/")
ORCHESTRATOR_URL = os.getenv("A2A_TEST_ORCHESTRATOR_URL", "http://127.0.0.1:14001").rstrip(
    "/"
)

# Local requests must not use HTTP(S)_PROXY — otherwise 400 or empty responses
_CLIENT_KWARGS = {
    "timeout": 10,
    "trust_env": False,
    "headers": {"Accept": "application/json"},
}


def fetch_agent_card(base_url: str) -> dict:
    """Fetch Agent Card from /.well-known/agent-card.json"""
    base = base_url.rstrip("/")
    url = f"{base}/.well-known/agent-card.json"
    print(f"\n{'='*60}")
    print(f"GET {url}")
    print(f"{'='*60}")
    resp = httpx.get(url, **_CLIENT_KWARGS)
    if resp.status_code >= 400:
        print(
            f"Error: HTTP {resp.status_code}, "
            f"Content-Type={resp.headers.get('content-type')!r}, "
            f"body (first 400 chars): {resp.text[:400]!r}"
        )
        if "InvalidBucketName" in resp.text or "MinIO" in resp.text:
            print(
                "This looks like MinIO (or another S3 API) on this port. "
                "Lab4 agents listen on 14000/14001; check A2A_TEST_*_URL and that A2A is bound to the port."
            )
        else:
            print(
                "Hint: are agents running? docker compose up; for K8s use port-forward and A2A_TEST_*_URL. "
                "Check: lsof -i :14000 ; HTTP_PROXY disabled in this script (trust_env=False)."
            )
        resp.raise_for_status()
    if not (resp.content or b"").strip():
        print(
            "Empty response (expected JSON Agent Card). "
            "Verify an A2A agent is listening, not another service / broken port-forward."
        )
        raise RuntimeError("Empty response from GET agent-card")
    try:
        card = resp.json()
    except json.JSONDecodeError as e:
        print(f"Invalid JSON: {e}; body: {resp.text[:400]!r}")
        raise
    print(json.dumps(card, indent=2, ensure_ascii=False))
    return card


def send_message(base_url: str, text: str) -> dict:
    """Send a message via JSON-RPC ``message/send``."""
    payload = build_message_send_payload(text)

    print(f"\n{'='*60}")
    base = base_url.rstrip("/")
    print(f"POST {base}/ — message/send: {text!r}")
    print(f"{'='*60}")
    resp = httpx.post(
        f"{base}/",
        json=payload,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        timeout=120,
        trust_env=False,
    )
    resp.raise_for_status()
    data = resp.json()
    print(json.dumps(data, indent=2, ensure_ascii=False))
    print("\n--- Extracted reply text ---")
    print(format_jsonrpc_result(data))
    return data


def _rpc_ok(data: dict) -> bool:
    return "error" not in data


def run_smoke() -> int:
    """Minimal check: agent card + one message/send to assistant."""
    try:
        fetch_agent_card(ASSISTANT_URL)
    except Exception as e:
        print(f"[smoke] FAIL agent-card: {e}", file=sys.stderr)
        return 1
    payload = build_message_send_payload("help", request_id="smoke")
    try:
        r = httpx.post(
            f"{ASSISTANT_URL.rstrip('/')}/",
            json=payload,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=120,
            trust_env=False,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"[smoke] FAIL message/send: {e}", file=sys.stderr)
        return 1
    if not _rpc_ok(data):
        print(f"[smoke] FAIL JSON-RPC error: {data.get('error')}", file=sys.stderr)
        return 1
    print("[smoke] OK assistant:", format_jsonrpc_result(data)[:500])
    return 0


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "assistant"

    if cmd == "discover":
        print("\n--- Discovering Assistant Agent ---")
        fetch_agent_card(ASSISTANT_URL)
        print("\n--- Discovering Orchestrator Agent ---")
        fetch_agent_card(ORCHESTRATOR_URL)

    elif cmd == "assistant":
        print("\n--- Assistant Agent Card ---")
        fetch_agent_card(ASSISTANT_URL)

        print("\n--- Sending task: document list ---")
        send_message(ASSISTANT_URL, "Show the list of documents")

        print("\n--- Sending task: help ---")
        send_message(ASSISTANT_URL, "help")

    elif cmd == "orchestrator":
        print("\n--- Orchestrator Agent Card ---")
        fetch_agent_card(ORCHESTRATOR_URL)

        print("\n--- Orchestrator discovers agents ---")
        send_message(ORCHESTRATOR_URL, "discover")

        print("\n--- Orchestrator delegates: document list ---")
        send_message(ORCHESTRATOR_URL, "Show the list of documents")

    elif cmd == "smoke":
        sys.exit(run_smoke())

    else:
        print(f"Unknown command: {cmd}")
        print(
            "Usage: python test_a2a.py [assistant|orchestrator|discover|smoke]"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
