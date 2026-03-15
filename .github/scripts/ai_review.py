#!/usr/bin/env python3
"""
AI Code Review via GitHub Models API.
Reads PR diff, sends to GitHub Models, posts review comment on the PR.

Environment variables required:
  GITHUB_TOKEN  — automatically provided by GitHub Actions
  PR_NUMBER     — pull request number
  REPO          — owner/repo (e.g. "octocat/Hello-World")
  BASE_REF      — base branch name (e.g. "main")
  HEAD_SHA      — HEAD commit SHA of the PR
"""

import json
import os
import sys
import urllib.request
import urllib.error
import subprocess
from pathlib import Path

GITHUB_MODELS_URL = "https://models.inference.ai.azure.com/chat/completions"
GITHUB_API_URL = "https://api.github.com"
MODEL = "gpt-4o-mini"
MAX_DIFF_CHARS = 12_000
MAX_TOKENS = 2_000


def gh_request(method: str, path: str, body: dict | None = None) -> dict:
    token = os.environ["GITHUB_TOKEN"]
    url = f"{GITHUB_API_URL}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "AIRE2026-AI-Review/1.0",
        },
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def get_pr_diff(base_ref: str) -> str:
    result = subprocess.run(
        ["git", "diff", f"origin/{base_ref}...HEAD"],
        capture_output=True, text=True, check=True,
    )
    diff = result.stdout
    if len(diff) > MAX_DIFF_CHARS:
        diff = diff[:MAX_DIFF_CHARS] + "\n\n[... diff truncated to first 12,000 chars ...]"
    return diff


def load_prompt_files() -> tuple[str, str]:
    root = Path(__file__).parent.parent.parent
    review_md = (root / "REVIEW.md").read_text()
    codebase_md = (root / "CODEBASE.md").read_text()

    # Extract system prompt block from REVIEW.md (between ``` fences after "## System Prompt")
    lines = review_md.split("\n")
    in_block = False
    prompt_lines = []
    for line in lines:
        if line.strip().startswith("```") and not in_block and "System Prompt" in "\n".join(lines[max(0, lines.index(line)-3):lines.index(line)]):
            in_block = True
            continue
        if line.strip() == "```" and in_block:
            break
        if in_block:
            prompt_lines.append(line)

    system_prompt = "\n".join(prompt_lines).strip() if prompt_lines else review_md
    return system_prompt, codebase_md


def call_github_models(system_prompt: str, user_content: str) -> str:
    token = os.environ["GITHUB_TOKEN"]
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.3,
        "max_tokens": MAX_TOKENS,
    }
    req = urllib.request.Request(
        GITHUB_MODELS_URL,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "AIRE2026-AI-Review/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
            return result["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"GitHub Models API error {e.code}: {body}", file=sys.stderr)
        raise


def post_pr_comment(repo: str, pr_number: str, body: str) -> None:
    gh_request("POST", f"/repos/{repo}/issues/{pr_number}/comments", {"body": body})


def build_comment(review_text: str, model: str, diff_size: int) -> str:
    truncated = "⚠️ diff truncated" if diff_size >= MAX_DIFF_CHARS else f"{diff_size:,} chars"
    return (
        f"## 🤖 AI Code Review\n\n"
        f"{review_text}\n\n"
        f"---\n"
        f"<sub>Model: `{model}` · Diff: {truncated} · "
        f"[REVIEW.md](./REVIEW.md) · [CODEBASE.md](./CODEBASE.md)</sub>"
    )


def main() -> None:
    required = ["GITHUB_TOKEN", "PR_NUMBER", "REPO", "BASE_REF"]
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        print(f"Missing env vars: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    pr_number = os.environ["PR_NUMBER"]
    repo = os.environ["REPO"]
    base_ref = os.environ["BASE_REF"]

    print(f"Reviewing PR #{pr_number} in {repo} (base: {base_ref})")

    diff = get_pr_diff(base_ref)
    diff_size = len(diff)
    print(f"Diff size: {diff_size:,} chars")

    if diff_size < 10:
        print("Diff is empty — skipping review")
        return

    system_prompt, codebase_md = load_prompt_files()

    user_content = (
        f"## Codebase Context\n\n{codebase_md}\n\n"
        f"## PR Diff\n\n```diff\n{diff}\n```"
    )

    print(f"Calling GitHub Models ({MODEL})...")
    review_text = call_github_models(system_prompt, user_content)
    print("Review generated.")

    comment_body = build_comment(review_text, MODEL, diff_size)
    post_pr_comment(repo, pr_number, comment_body)
    print(f"Review posted to PR #{pr_number}")

    # Save review for potential use by evals workflow
    output_file = Path("/tmp/ai_review_output.json")
    output_file.write_text(json.dumps({
        "pr_number": pr_number,
        "repo": repo,
        "model": MODEL,
        "review": review_text,
        "diff_size": diff_size,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
