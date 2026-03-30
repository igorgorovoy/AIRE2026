# EVALS.md — AI Review Evaluation Methodology

> Defines how to evaluate AI reviews produced by the `ai-review.yml` workflow.
> Results are published weekly by `ai-review-evals.yml`.

---

## Quality metrics

### 1. Precision
**Definition:** Share of AI findings that are real issues.

```
Precision = True Positives / (True Positives + False Positives)
```

| Rating | Precision | Description |
|--------|-----------|-------------|
| Excellent | ≥ 0.85 | Almost all findings are valid |
| Good | 0.70–0.84 | Acceptable quality |
| Poor | < 0.70 | Too many false positives |

**Measurement:** After a PR merges, mark AI comments as `valid` / `false-positive` via GitHub reactions:
- 👍 = valid finding
- 👎 = false positive

---

### 2. Actionability
**Definition:** Whether AI comments led to code changes.

```
Actionability = PRs_with_followup_commits / PRs_with_AI_review
```

**Measurement:** Automated — the workflow checks for commits after the AI review before merge.

| Rating | Rate | Description |
|--------|------|-------------|
| Excellent | ≥ 0.40 | Reviews drive improvements |
| Good | 0.20–0.39 | Moderate impact |
| Poor | < 0.20 | Reviews ignored |

---

### 3. Coverage
**Definition:** Whether AI found all important issues.

Checked manually on a sample of PRs:
- Compare with human review on the same PRs
- Count issues found by humans but missed by AI

| Rating | Miss Rate | Description |
|--------|-----------|-------------|
| Excellent | ≤ 0.10 | Almost nothing missed |
| Good | 0.11–0.25 | Acceptable coverage |
| Poor | > 0.25 | Many missed issues |

---

### 4. Format Compliance
**Definition:** Whether AI follows the structure in `REVIEW.md`.

Automatic check for sections:
- `### Summary` ✓/✗
- `### 🔴 Critical Issues` ✓/✗
- `### 🟡 Suggestions` ✓/✗
- `### 🟢 Good Practices` ✓/✗
- `### Score` ✓/✗

---

### 5. Score Distribution
**Definition:** Distribution of PR scores (1–10) to detect bias.

Target distribution:
```
Score 1-4:  ~10% (serious issues)
Score 5-6:  ~20% (needs work)
Score 7-8:  ~50% (good shape)
Score 9-10: ~20% (excellent)
```

Warning: if >60% get 9–10 — AI may be too lenient.
Warning: if >40% get 1–4 — AI may be too harsh.

---

## Eval workflow algorithm

`ai-review-evals.yml` runs weekly:

```python
1. Fetch merged PRs for the past week (GitHub API)
2. For each PR with an AI review:
   a. Check all sections exist (Format Compliance)
   b. Count commits after AI review (Actionability)
   c. Collect 👍/👎 on AI comments (Precision proxy)
   d. Extract Score from review text
3. Aggregate weekly metrics
4. Compare with the previous week (trend)
5. Call GitHub Models for meta-evaluation:
   - provide 3 sample reviews
   - ask for quality rating against the criteria above
6. Publish report as a GitHub Issue with label 'ai-evals'
```

---

## Report format (published as Issue)

```markdown
## 📊 AI Review Evals — Week YYYY-WW

### Weekly metrics

| Metric | Value | Trend | Rating |
|--------|-------|-------|--------|
| PRs reviewed | N | ↑/↓/= | — |
| Format compliance | X% | ↑/↓/= | 🟢/🟡/🔴 |
| Actionability | X% | ↑/↓/= | 🟢/🟡/🔴 |
| Precision (👍 rate) | X% | ↑/↓/= | 🟢/🟡/🔴 |
| Avg score given | X.X | ↑/↓/= | 🟢/🟡/🔴 |

### Meta-evaluation (GitHub Models)
[AI quality assessment of 3 random reviews from the week]

### Recommendations
[What to improve in REVIEW.md or the workflow]

### Examples from the week
- 🏆 Best: PR #N — [reason]
- ⚠️ Worst: PR #N — [reason]
```

---

## Baseline (initial expectations)

For the first 4 weeks after launch:

| Metric | Minimum baseline |
|--------|------------------|
| Format compliance | ≥ 95% |
| Actionability | ≥ 20% |
| Avg score | 6.0–8.5 |

If any metric is below baseline, an Issue with the `bug` label is created automatically.

---

## How to label AI comments

React to AI review comments:
- 👍 — valid and useful finding
- 👎 — false positive / not applicable
- 🎉 — exceptionally useful suggestion (for a best-of collection)

This enables Precision measurement without manual analysis.
