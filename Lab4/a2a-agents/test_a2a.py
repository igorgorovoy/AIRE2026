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
import os
import sys

import httpx

# За замовч. 14000/14001 — порти агентів (compose / локальний запуск).
# K8s: kubectl port-forward svc/a2a-assistant-agent -n a2a 14000:14000 → той самий дефолт
ASSISTANT_URL = os.getenv("A2A_TEST_ASSISTANT_URL", "http://127.0.0.1:14000").rstrip("/")
ORCHESTRATOR_URL = os.getenv("A2A_TEST_ORCHESTRATOR_URL", "http://127.0.0.1:14001").rstrip(
    "/"
)

# Локальні запити не повинні йти через HTTP(S)_PROXY — інакше 400 / порожня відповідь
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
            f"Помилка: HTTP {resp.status_code}, "
            f"Content-Type={resp.headers.get('content-type')!r}, "
            f"тіло (до 400 симв.): {resp.text[:400]!r}"
        )
        if "InvalidBucketName" in resp.text or "MinIO" in resp.text:
            print(
                "Схоже на MinIO (або інший S3 API) на цьому порту. "
                "Агенти Lab4 слухають 14000/14001; перевірте A2A_TEST_*_URL і що на порту саме A2A."
            )
        else:
            print(
                "Підказка: агенти запущені? docker compose up; для K8s — port-forward і A2A_TEST_*_URL. "
                "Перевірка: lsof -i :14000 ; HTTP_PROXY у скрипті вимкнено (trust_env=False)."
            )
        resp.raise_for_status()
    if not (resp.content or b"").strip():
        print(
            "Порожня відповідь (очікувався JSON Agent Card). "
            "Перевірте, що на порту саме A2A-агент, а не інший сервіс / зламаний port-forward."
        )
        raise RuntimeError("Порожня відповідь від GET agent-card")
    try:
        card = resp.json()
    except json.JSONDecodeError as e:
        print(f"Невалідний JSON: {e}; тіло: {resp.text[:400]!r}")
        raise
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
    base = base_url.rstrip("/")
    print(f"POST {base}/ — SendMessage: '{text}'")
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
