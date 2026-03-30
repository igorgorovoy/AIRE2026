# Lab 7 — «Vin's Questions»

This is an **analysis of our own AIRE2026 repository** in answer to the interviewer’s questions: what the labs actually contain, where the gaps are, and what follows from agentgateway/kagent docs outside the repo. It is not a contractor hiring checklist.

**Repo context:** Lab1 — agentgateway (standalone + Helm/k8s), Lab3 — kagent, MCP under `Lab3/mcp-servers`, Lab4 — A2A (`a2a`), Lab5 — Phoenix/Qdrant, etc. (manifests exist; depends on deployment). In Vin’s materials we read **kgateway** as **agentgateway** — there is no separate product by that name in the repo.

---

## 1. «Agent got stuck» — what does our setup show?

In **our MCP code** one «long silence» path is already visible: in `Lab3/mcp-servers/src/knowledge-base/server.py` HTTP to the KB backend uses `timeout=60`; in `tasks/server.py` — `subprocess.run(..., timeout=60)`. Until that fires, it looks like a hang from the outside.

**What the repo does not have:** a single layer that caps the whole kagent agent tool-loop by time or iteration count — that is not `AgentgatewayBackend` or our YAML. If the stall is not in MCP but in the LLM or kagent runtime, our diagnosis is **pod logs**, optionally **Phoenix** (Lab5) if you deployed it.

**Environment limits** from `CODEBASE.md` still apply: single-node k3s, kagent demo profile caused OOM — so «stuck» sometimes looks like a **killed pod**, not an app-level timeout.

---

## 2. Timeout / circuit breaker «from the framework»

**agentgateway** (what we install in Lab1): the docs describe P2C and health/latency across backends within a group — [load balancing](https://agentgateway.dev/docs/kubernetes/latest/llm/load-balancing/). That is not a standalone circuit breaker with states.

**In our Lab1 manifests** we did not document a global LLM request timeout as part of the teaching minimum; real limits sit in the client, Ingress, or **our** Python MCP (timeout examples above).

**Conclusion for the repo:** relying on «the gateway cuts everything off» is not documented for our lab; we do have point timeouts in MCP.

---

## 3. Model failover (agentgateway)

From the [failover docs](https://agentgateway.dev/docs/kubernetes/latest/llm/failover/): `spec.ai.groups` on `AgentgatewayBackend` are priority tiers; within a tier there is load balancing.

**Limitation we record in this analysis:** moving to a **lower** tier per the docs is tied to **429** and correct rate-limit headers. 503, timeout, connection refused for tier failover is **not** the same as an automatic jump to the next group.

**In our Lab1** besides the gateway there is an explicit **manual** provider choice via `x-provider` in `Lab1/beginers/config.yaml` — that is header-based routing, not an automatic model cascade.

---

## 4. OpenAI → Claude → local automatically

In theory the same `groups` on `AgentgatewayBackend`; **but** the limitation in §3 remains: «local died on timeout» ≠ guaranteed Claude fallback per the documented behaviour.

**In the repository** the more transparent path is stronger: three backends and switching via `x-provider`, not a hidden cascade.

---

## 5. Response formats across providers

Our path through agentgateway targets an **OpenAI-like** contract for the client. **In the lab** we do not have a separate test layer that checks streaming / `tool_calls` / different `usage` across all three providers.

**MCP in Lab3** standardises **tools** (`@mcp.tool()`), not the LLM response body. If a parser expects one JSON shape and a provider returns another, that shows up in integration, not «out of the box» from the repo.

---

## 6. Versioning kagent agents

**What we have:** version = **git + image tags + YAML**. For example `Lab3/manifests/kagent/assistant/agent.yaml` and kustomize; changing `ModelConfig` changes behaviour the same way as changing the MCP image.

**Not in the repo:** a dedicated agent version registry or npm-style UI; to see what is in the cluster you use `kubectl get agent -n kagent` and pod images.

---

## 7. Blue/green, canary

**Generic Kubernetes** applies to our MCP Deployments and controllers: rollout, second deployment, undo.

**agentgateway** supports [traffic split](https://agentgateway.dev/docs/kubernetes/latest/traffic-management/traffic-split/) between backends — that is **models/routes**, not swapping our agent code.

**In the repo:** we did not commit a dedicated canary flow for agents (Helm/Argo); extending the lab would use standard k8s patterns.

---

## 8–9. FastMCP / path to MCP

**From the code:** all three servers under `Lab3/mcp-servers/src/` use `from mcp.server.fastmcp import FastMCP` — that is part of the official Python **`mcp`** SDK, not necessarily the separate PyPI `fastmcp` package under another namespace.

**Conclusion:** for **this** repository the choice is already FastMCP-style inside `mcp`. The rest is still what the lab has: `.env`, lakeFS, deploy into `kagent`, debug via logs.

---

## 10–13. FinOps: tokens, per-agent, budgets

**What we have in the repo:** routing to different models via agentgateway (Lab1); billing on the provider side by API keys.

**What we do not have:** a ready FinOps dashboard per agent, or aggregation of `usage` by `agent_id` in repo code. Lab5 (Phoenix) **can** help with traces/metrics if wired to calls — but that is not «flip a file and budgets appear».

Hard per-agent / per-token quotas are **not implemented** as a separate service in our lab — that would be a layer above the gateway or in the orchestrator.

---

## 14. vLLM and many tool calls

**In AIRE2026** vLLM as a service is **not captured** to the same extent as agentgateway/kagent. This answer is about the class of system: vLLM serves **one (or streaming) request** at a time; a long agent means many sequential requests. It can work, but it does **not** reduce step count — that is agent logic.

---

## 15. llm-d scheduler

**There is no llm-d in the repository** — no chart, no manifests. The question is about an external stack ([Inference Scheduler](https://llm-d.ai/docs/architecture/Components/inference-scheduler)): spreading load across vLLM/SGLang replicas. For our lab that is **not part of the submitted setup**; it is an option for scaling inference beyond the course repo.

---

## References used to support claims

- [agentgateway — failover](https://agentgateway.dev/docs/kubernetes/latest/llm/failover/)  
- [agentgateway — load balancing](https://agentgateway.dev/docs/kubernetes/latest/llm/load-balancing/)  
- [agentgateway — traffic split](https://agentgateway.dev/docs/kubernetes/latest/traffic-management/traffic-split/)  
- [llm-d — Inference Scheduler](https://llm-d.ai/docs/architecture/Components/inference-scheduler)  
- Repo code: `Lab3/mcp-servers/src/knowledge-base/server.py`, `.../tasks/server.py` (`FastMCP`, `timeout=60`)

---

## Where this file lives

Path in clone: `Lab7/LAB7.md`. On GitHub: `https://github.com/OWNER/AIRE2026/blob/<branch>/Lab7/LAB7.md` (replace OWNER and branch).
