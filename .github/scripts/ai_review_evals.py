#!/usr/bin/env python3
"""
AI Review Evals — weekly evaluation of AI review quality.
Analyzes merged PRs, measures metrics from EVALS.md, publishes GitHub Issue report.

Environment variables required:
  GITHUB_TOKEN  — automatically provided by GitHub Actions
  REPO          — owner/repo (e.g. "octocat/Hello-World")
  LOOKBACK_DAYS — how many days to look back (default: 7)
"""

import json
import os
import re
import sys
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

GITHUB_MODELS_URL = "https://models.inference.ai.azure.com/chat/completions"
GITHUB_API_URL = "https://api.github.com"
MODEL = "gpt-4o-mini"
AI_REVIEW_MARKER = "🤖 AI Code Review"
EVALS_ISSUE_LABEL = "ai-evals"

REQUIRED_SECTIONS = [
    "### Summary",
    "### 🔴 Critical Issues",
    "### 🟡 Suggestions",
    "### 🟢 Good Practices",
    "### Score",
]


def gh_request(method: str, path: str, body: dict | None = None, params: dict | None = None) -> dict | list:
    token = os.environ["GITHUB_TOKEN"]
    url = f"{GITHUB_API_URL}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "AIRE2026-AI-Evals/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return []
        raise


def get_merged_prs(repo: str, since: datetime) -> list[dict]:
    result = gh_request("GET", f"/repos/{repo}/pulls", params={
        "state": "closed",
        "sort": "updated",
        "direction": "desc",
        "per_page": "50",
    })
    if not isinstance(result, list):
        return []
    merged = []
    for pr in result:
        if pr.get("merged_at"):
            merged_at = datetime.fromisoformat(pr["merged_at"].replace("Z", "+00:00"))
            if merged_at >= since:
                merged.append(pr)
    return merged


def get_pr_comments(repo: str, pr_number: int) -> list[dict]:
    result = gh_request("GET", f"/repos/{repo}/issues/{pr_number}/comments")
    return result if isinstance(result, list) else []


def get_comment_reactions(repo: str, comment_id: int) -> dict:
    result = gh_request("GET", f"/repos/{repo}/issues/comments/{comment_id}/reactions",
                        params={"per_page": "100"})
    if not isinstance(result, list):
        return {"thumbs_up": 0, "thumbs_down": 0, "hooray": 0}
    counts = {"thumbs_up": 0, "thumbs_down": 0, "hooray": 0}
    for r in result:
        if r["content"] == "+1":
            counts["thumbs_up"] += 1
        elif r["content"] == "-1":
            counts["thumbs_down"] += 1
        elif r["content"] == "hooray":
            counts["hooray"] += 1
    return counts


def get_pr_commits_after(repo: str, pr_number: int, review_time: str) -> int:
    result = gh_request("GET", f"/repos/{repo}/pulls/{pr_number}/commits")
    if not isinstance(result, list):
        return 0
    review_dt = datetime.fromisoformat(review_time.replace("Z", "+00:00"))
    count = 0
    for commit in result:
        commit_time = commit.get("commit", {}).get("committer", {}).get("date", "")
        if commit_time:
            commit_dt = datetime.fromisoformat(commit_time.replace("Z", "+00:00"))
            if commit_dt > review_dt:
                count += 1
    return count


def check_format_compliance(review_body: str) -> dict:
    found = {section: section in review_body for section in REQUIRED_SECTIONS}
    score_match = re.search(r"(\d+(?:\.\d+)?)/10", review_body)
    base = {
        "sections_found": found,
        "all_sections_present": all(found.values()),
        "compliance_score": sum(found.values()) / len(REQUIRED_SECTIONS),
    }
    if score_match:
        return {**base, "pr_score": float(score_match.group(1))}
    return {**base, "pr_score": None}


def analyze_pr(repo: str, pr: dict) -> dict | None:
    pr_number = pr["number"]
    comments = get_pr_comments(repo, pr_number)

    ai_comment = next(
        (c for c in comments if AI_REVIEW_MARKER in c.get("body", "")),
        None
    )
    if not ai_comment:
        return None

    review_time = ai_comment["created_at"]
    reactions = get_comment_reactions(repo, ai_comment["id"])
    commits_after = get_pr_commits_after(repo, pr_number, review_time)
    format_check = check_format_compliance(ai_comment["body"])

    total_reactions = reactions["thumbs_up"] + reactions["thumbs_down"]
    precision_proxy = (reactions["thumbs_up"] / total_reactions) if total_reactions > 0 else None

    return {
        "pr_number": pr_number,
        "pr_title": pr["title"],
        "review_time": review_time,
        "format": format_check,
        "reactions": reactions,
        "precision_proxy": precision_proxy,
        "commits_after_review": commits_after,
        "had_followup": commits_after > 0,
        "review_snippet": ai_comment["body"][:500],
    }


def call_meta_evaluation(reviews_sample: list[dict]) -> str:
    if not reviews_sample:
        return "No reviews available for meta-evaluation."

    token = os.environ["GITHUB_TOKEN"]
    reviews_text = "\n\n---\n\n".join([
        f"PR #{r['pr_number']}: {r['pr_title']}\n\n{r['review_snippet']}..."
        for r in reviews_sample[:3]
    ])

    evals_md = (Path(__file__).parent.parent.parent / "EVALS.md").read_text()

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are evaluating the quality of AI code reviews. "
                    "Based on the evaluation criteria from EVALS.md, assess each review snippet. "
                    "Be concise (max 300 words total). Format: bullet points per PR."
                ),
            },
            {
                "role": "user",
                "content": f"## Evaluation Criteria (from EVALS.md)\n\n{evals_md[:2000]}\n\n"
                           f"## Review Samples\n\n{reviews_text}",
            },
        ],
        "temperature": 0.3,
        "max_tokens": 600,
    }

    req = urllib.request.Request(
        GITHUB_MODELS_URL,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "AIRE2026-AI-Evals/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
            return result["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Meta-evaluation failed: {e}"


def trend_arrow(current: float | None, previous: float | None) -> str:
    if current is None or previous is None:
        return "—"
    if current > previous + 0.02:
        return "↑"
    if current < previous - 0.02:
        return "↓"
    return "="


def status_emoji(value: float | None, good: float, ok: float) -> str:
    if value is None:
        return "⚪"
    if value >= good:
        return "🟢"
    if value >= ok:
        return "🟡"
    return "🔴"


def build_report(analyses: list[dict], meta_eval: str, week_label: str) -> str:
    n = len(analyses)
    if n == 0:
        return (
            f"## 📊 AI Review Evals — {week_label}\n\n"
            "No PRs with AI reviews found this week.\n"
        )

    format_scores = [a["format"]["compliance_score"] for a in analyses]
    avg_format = sum(format_scores) / len(format_scores)

    actionability = sum(1 for a in analyses if a["had_followup"]) / n

    precision_values = [a["precision_proxy"] for a in analyses if a["precision_proxy"] is not None]
    avg_precision = sum(precision_values) / len(precision_values) if precision_values else None

    pr_scores = [a["format"]["pr_score"] for a in analyses if a["format"]["pr_score"] is not None]
    avg_score = sum(pr_scores) / len(pr_scores) if pr_scores else None

    best = max(analyses, key=lambda a: a["format"]["pr_score"] or 0, default=None)
    worst = min(analyses, key=lambda a: a["format"]["pr_score"] or 10, default=None)

    score_display = f"{avg_score:.1f}" if avg_score else "N/A"
    precision_display = f"{avg_precision:.0%}" if avg_precision else "N/A (no reactions)"

    report = f"""## 📊 AI Review Evals — {week_label}

> Auto-generated by [ai-review-evals workflow](.github/workflows/ai-review-evals.yml)

### Метрики тижня

| Метрика | Значення | Оцінка |
|---------|----------|--------|
| PRs reviewed | {n} | — |
| Format compliance | {avg_format:.0%} | {status_emoji(avg_format, 0.95, 0.80)} |
| Actionability | {actionability:.0%} | {status_emoji(actionability, 0.40, 0.20)} |
| Precision (👍 rate) | {precision_display} | {status_emoji(avg_precision, 0.85, 0.70) if avg_precision else '⚪'} |
| Avg score given | {score_display} | {status_emoji((avg_score or 0) / 10, 0.7, 0.55) if avg_score else '⚪'} |

### Деталі по PRs

| PR | Score | Format | Followup commits | 👍 | 👎 |
|----|-------|--------|-----------------|----|----|
"""
    for a in analyses:
        sc = f"{a['format']['pr_score']}/10" if a["format"]["pr_score"] else "—"
        fmt = "✅" if a["format"]["all_sections_present"] else f"⚠️ {a['format']['compliance_score']:.0%}"
        fc = str(a["commits_after_review"]) if a["commits_after_review"] > 0 else "—"
        tp = a["reactions"]["thumbs_up"]
        fp = a["reactions"]["thumbs_down"]
        report += f"| #{a['pr_number']} {a['pr_title'][:40]} | {sc} | {fmt} | {fc} | {tp} | {fp} |\n"

    report += f"""
### Meta-evaluation (GitHub Models `{MODEL}`)

{meta_eval}

### Рекомендації щодо покращення

"""
    if avg_format < 0.95:
        report += "- ⚠️ Format compliance нижче 95% — перевір чи не змінився формат відповіді моделі\n"
    if actionability < 0.20:
        report += "- ⚠️ Actionability нижче 20% — рев'ю може бути надто загальним або ігноруватись\n"
    if avg_score and avg_score > 8.5:
        report += "- ⚠️ Середній score > 8.5 — AI може бути занадто м'яким (score bias)\n"
    if avg_score and avg_score < 5.0:
        report += "- ⚠️ Середній score < 5.0 — AI може бути занадто суворим\n"
    if not any([avg_format < 0.95, actionability < 0.20, avg_score and (avg_score > 8.5 or avg_score < 5.0)]):
        report += "- ✅ Всі метрики в нормі\n"

    if best and worst and best["pr_number"] != worst["pr_number"]:
        report += f"""
### Приклади тижня

- 🏆 **Best:** PR #{best['pr_number']} — {best['pr_title']} (score: {best['format']['pr_score']}/10)
- ⚠️ **Needs improvement:** PR #{worst['pr_number']} — {worst['pr_title']} (score: {worst['format']['pr_score']}/10)
"""

    report += f"\n---\n<sub>Reactions guide: 👍 valid finding · 👎 false positive · 🎉 excellent suggestion</sub>\n"
    return report


def ensure_label_exists(repo: str) -> None:
    try:
        gh_request("GET", f"/repos/{repo}/labels/{urllib.parse.quote(EVALS_ISSUE_LABEL)}")
    except Exception:
        try:
            gh_request("POST", f"/repos/{repo}/labels", {
                "name": EVALS_ISSUE_LABEL,
                "color": "0075ca",
                "description": "AI Review evaluation reports",
            })
        except Exception:
            pass


def create_or_update_issue(repo: str, week_label: str, body: str) -> None:
    ensure_label_exists(repo)
    title = f"📊 AI Review Evals — {week_label}"

    existing = gh_request("GET", f"/repos/{repo}/issues", params={
        "labels": EVALS_ISSUE_LABEL,
        "state": "open",
        "per_page": "10",
    })
    if isinstance(existing, list):
        for issue in existing:
            if week_label in issue.get("title", ""):
                gh_request("PATCH", f"/repos/{repo}/issues/{issue['number']}", {"body": body})
                print(f"Updated existing issue #{issue['number']}")
                return

    result = gh_request("POST", f"/repos/{repo}/issues", {
        "title": title,
        "body": body,
        "labels": [EVALS_ISSUE_LABEL],
    })
    print(f"Created issue #{result.get('number')}: {title}")


def main() -> None:
    required = ["GITHUB_TOKEN", "REPO"]
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        print(f"Missing env vars: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    repo = os.environ["REPO"]
    lookback_days = int(os.environ.get("LOOKBACK_DAYS", "7"))
    since = datetime.now(timezone.utc) - timedelta(days=lookback_days)

    week_label = datetime.now(timezone.utc).strftime("%Y-W%V")
    print(f"Evaluating PRs for {repo}, lookback: {lookback_days} days (week {week_label})")

    prs = get_merged_prs(repo, since)
    print(f"Found {len(prs)} merged PRs")

    analyses = []
    for pr in prs:
        print(f"  Analyzing PR #{pr['number']}...")
        analysis = analyze_pr(repo, pr)
        if analysis:
            analyses.append(analysis)
            print(f"    → AI review found, score: {analysis['format']['pr_score']}")
        else:
            print(f"    → No AI review")

    print(f"PRs with AI review: {len(analyses)}")

    meta_eval = call_meta_evaluation(analyses)

    report = build_report(analyses, meta_eval, week_label)
    print("\n" + "="*60)
    print(report)
    print("="*60)

    create_or_update_issue(repo, week_label, report)
    print("Done.")


if __name__ == "__main__":
    main()
