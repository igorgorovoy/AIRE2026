#!/usr/bin/env python3
"""Test script for A2A agents.

Demonstrates:
1. Fetching Agent Card from Well-Known URI
2. Sending a task via A2A JSON-RPC
3. Agent-to-agent delegation via orchestrator

Usage:
    # Test assistant agent directly
    python test_a2a.py assistant

    # Test orchestrator (delegates to assistant)
    python test_a2a.py orchestrator

    # Discover agents
    python test_a2a.py discover
"""

import json
import sys

import httpx

ASSISTANT_URL = "http://localhost:9000"
ORCHESTRATOR_URL = "http://localhost:9001"


def fetch_agent_card(base_url: str) -> dict:
    """Fetch Agent Card from /.well-known/agent-card.json"""
    url = f"{base_url}/.well-known/agent-card.json"
    print(f"\n{'='*60}")
    print(f"GET {url}")
    print(f"{'='*60}")
    resp = httpx.get(url, timeout=10)
    resp.raise_for_status()
    card = resp.json()
    print(json.dumps(card, indent=2, ensure_ascii=False))
    return card


def send_message(base_url: str, text: str) -> dict:
    """Send a message via A2A JSON-RPC SendMessage."""
    payload = {
        "jsonrpc": "2.0",
        "id": "test-1",
        "method": "a2a.SendMessage",
        "params": {
            "message": {
                "role": "user",
                "parts": [{"type": "text", "text": text}],
            },
            "configuration": {
                "returnImmediately": False,
            },
        },
    }

    print(f"\n{'='*60}")
    print(f"POST {base_url}/ — SendMessage: '{text}'")
    print(f"{'='*60}")
    resp = httpx.post(
        f"{base_url}/",
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    print(json.dumps(data, indent=2, ensure_ascii=False))
    return data


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

        print("\n--- Sending task: 'список документів' ---")
        send_message(ASSISTANT_URL, "Покажи список документів")

        print("\n--- Sending task: 'help' ---")
        send_message(ASSISTANT_URL, "help")

    elif cmd == "orchestrator":
        print("\n--- Orchestrator Agent Card ---")
        fetch_agent_card(ORCHESTRATOR_URL)

        print("\n--- Orchestrator discovers agents ---")
        send_message(ORCHESTRATOR_URL, "discover")

        print("\n--- Orchestrator delegates: 'список документів' ---")
        send_message(ORCHESTRATOR_URL, "Покажи список документів")

    else:
        print(f"Unknown command: {cmd}")
        print("Usage: python test_a2a.py [assistant|orchestrator|discover]")
        sys.exit(1)


if __name__ == "__main__":
    main()
