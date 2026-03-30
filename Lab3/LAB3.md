# Lab 3 — Personal assistant with three MCP servers

> **Goal:** deploy an assistant agent in Kubernetes (via kagent) that uses three MCP servers for Knowledge Base, lesson credits, and task management.

## Architecture

```
┌─────────────────────────────────────────────┐
│              kagent UI / Chat               │
└──────────────────┬──────────────────────────┘
                   │
         ┌─────────▼─────────┐
         │  assistant-agent  │  (Agent kagent.dev/v1alpha2)
         │  modelConfig:     │
         │  default-model-   │
         │  config           │
         └──┬──────┬──────┬──┘
            │      │      │
    ┌───────▼─┐ ┌──▼──────┐ ┌────────▼────────┐
    │  mcp-   │ │  mcp-   │ │   mcp-tasks     │
    │knowledge│ │lesson-  │ │                 │
    │ -base   │ │credits  │ │ Task Manager    │
    │         │ │         │ │ workspaces,     │
    │ Obsidian│ │ lessons │ │ boards, cards   │
    │ vault   │ │ calendar│ │ comments, etc.  │
    └────┬────┘ └────┬────┘ └────────┬────────┘
         │           │               │
    HTTP API    local/lakeFS    local/lakeFS
    (backend)    storage          storage
```

## Lab 3 layout

```
Lab3/
├── LAB3.md                                ← this file
├── mcp-servers/
│   └── src/
│       ├── knowledge-base/
│       │   ├── Dockerfile                 ← standalone image
│       │   └── server.py                  ← copy from agentic-ai-landing-zone
│       ├── lesson-credits/
│       │   ├── Dockerfile                 ← build from ALZ root
│       │   └── server.py                  ← copy from agentic-ai-landing-zone
│       └── tasks/
│           ├── Dockerfile                 ← build from ALZ root
│           └── server.py                  ← copy from agentic-ai-landing-zone
└── manifests/
    └── kagent/
        └── assistant/
            ├── README.md
            ├── mcpserver-knowledge-base.yaml
            ├── mcpserver-lesson-credits.yaml
            ├── mcpserver-tasks.yaml
            ├── agent.yaml
            ├── all-in-one.yaml            ← 3 MCPServer + Agent in one file
            └── kustomization.yaml
```

## MCP servers

| Image | Source | Dependencies |
|-------|--------|--------------|
| `mcp-knowledge-base:latest` | `mcp-servers/src/knowledge-base/` | `mcp[cli]`, `python-dotenv` |
| `mcp-lesson-credits:latest` | root of `agentic-ai-landing-zone` | + `langgraph`, `langchain-core`, `agents/`, `core/` |
| `mcp-tasks:latest` | root of `agentic-ai-landing-zone` | + `langgraph`, `langchain-core`, `agents/`, `core/`, `scripts/` |

### Environment variables

| Server | Variable | Default | Description |
|--------|----------|---------|-------------|
| knowledge-base | `KB_API_BASE_URL` | `http://localhost:8000` | KB backend URL |
| knowledge-base | `API_KEY` | `""` | X-API-Key header (if required) |
| lesson-credits | `STORAGE_BACKEND` | `local` | `local` or `lakefs` |
| tasks | `STORAGE_BACKEND` | `local` | `local` or `lakefs` |
| tasks | `ENABLE_DELETE_TOOLS` | `0` | `1` — enable delete tools |
| lesson-credits, tasks | `LAKEFS_ENDPOINT` | — | for `STORAGE_BACKEND=lakefs` |
| lesson-credits, tasks | `LAKEFS_ACCESS_KEY_ID` | — | lakeFS access key ID |
| lesson-credits, tasks | `LAKEFS_SECRET_ACCESS_KEY` | — | lakeFS secret key |
| lesson-credits, tasks | `LAKEFS_REPOSITORY` | — | lakeFS repository name |
| lesson-credits, tasks | `LAKEFS_BRANCH` | `main` | lakeFS branch |

## Prerequisites

1. **kagent** deployed in namespace `kagent` (CRDs: `mcpservers.kagent.dev`, `agents.kagent.dev`).
2. **ModelConfig** `default-model-config` and a Secret with the provider API key (OpenAI or other).
3. **Docker** and Kubernetes access (`kubectl`).
4. (Optional) **agentic-ai-landing-zone** repo — to build `lesson-credits` and `tasks` images.

```bash
# Verify kagent
kubectl get modelconfigs,mcpservers,agents -n kagent
```

## Step 1 — Build Docker images

> **Prerequisite:** Docker is running and available from the CLI (`docker info`). For Rancher Desktop, the app should be running.

Set repository paths:

```bash
export LAB3=/path/to/AIRE2026/Lab3
export ALZ=/path/to/agentic-ai-landing-zone
```

### knowledge-base

```bash
docker build -t mcp-knowledge-base:latest "$LAB3/mcp-servers/src/knowledge-base"
```

### lesson-credits

```bash
docker build -t mcp-lesson-credits:latest \
  -f "$LAB3/mcp-servers/src/lesson-credits/Dockerfile" "$ALZ"
```

### tasks

```bash
docker build -t mcp-tasks:latest \
  -f "$LAB3/mcp-servers/src/tasks/Dockerfile" "$ALZ"
```

### Rancher Desktop / k3s (no registry)

If Kubernetes cannot see images after `docker build`, load them into the VM:

```bash
for img in mcp-knowledge-base mcp-lesson-credits mcp-tasks; do
  docker save "${img}:latest" -o ~/"${img}.tar"
  rdctl shell -- sh -lc "sudo docker load -i ~/${img}.tar"
done
```

## Step 2 — Create credentials Secret

MCP servers receive configuration via kagent `secretRefs`. Each Secret key becomes a separate environment variable in the container (one variable = one key in `stringData`).

Copy the example and fill in real values:

```bash
cp manifests/kagent/assistant/secrets-example.yaml \
   manifests/kagent/assistant/secrets.yaml
# edit secrets.yaml — set real endpoints, keys, etc.
```

Apply the Secret **before** MCP server manifests:

```bash
kubectl apply -f manifests/kagent/assistant/secrets.yaml
```

> `secrets.yaml` is in `.gitignore` — it will not be committed.

### Secret structure

> **Important:** kagent injects each Secret key as a separate env var. Use **one key = one variable** (not a multiline `dot-env` blob).

Example for lesson-credits / tasks:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: mcp-lesson-credits-secrets
  namespace: kagent
type: Opaque
stringData:
  STORAGE_BACKEND: "lakefs"
  LAKEFS_ENDPOINT: "http://<lakefs-host>:8001"
  LAKEFS_ACCESS_KEY_ID: "<access-key>"        # replace with real key
  LAKEFS_SECRET_ACCESS_KEY: "<secret-key>"    # replace with real key
  LAKEFS_REPOSITORY: "<repo-name>"
  LAKEFS_BRANCH: "main"
```

Example for knowledge-base:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: mcp-knowledge-base-secrets
  namespace: kagent
type: Opaque
stringData:
  KB_API_BASE_URL: "http://<service-ip-or-hostname>:8000"
  API_KEY: "<optional-api-key>"               # replace if needed
```

> Full template: `manifests/kagent/assistant/secrets-example.yaml`. Copy to `secrets.yaml` and replace `<...>` with real values.

## Step 3 — Configure KB_API_BASE_URL

If the knowledge-base backend is outside the cluster, set `KB_API_BASE_URL` in Secret `mcp-knowledge-base-secrets` (see structure above).

## Step 5 — Apply manifests

From **Lab3 root**, choose **one** option:

```bash
# Option A — single file
kubectl apply -f manifests/kagent/assistant/all-in-one.yaml

# Option B — Kustomize
kubectl apply -k manifests/kagent/assistant

# Option C — one by one
kubectl apply -f manifests/kagent/assistant/mcpserver-knowledge-base.yaml
kubectl apply -f manifests/kagent/assistant/mcpserver-lesson-credits.yaml
kubectl apply -f manifests/kagent/assistant/mcpserver-tasks.yaml
kubectl apply -f manifests/kagent/assistant/agent.yaml
```

## Step 6 — Verify deployment

### 6.1 Overall resource status

```bash
kubectl get mcpservers,agents -n kagent
kubectl get pods -n kagent | grep -E 'mcp-|NAME'
```

Expected: pods `Running`, agent `Ready` / `Accepted`.

### 6.2 Env vars in pods (storage backend)

Confirm secrets are injected and `STORAGE_BACKEND=lakefs`:

```bash
# Check each MCP server
for svc in mcp-knowledge-base mcp-lesson-credits mcp-tasks; do
  POD=$(kubectl get pod -n kagent -l app.kubernetes.io/name=$svc -o name | head -1)
  echo "=== $svc ==="
  kubectl exec -n kagent "$POD" -- env | grep -E 'STORAGE|LAKEFS|KB_API|ENABLE_DELETE'
done
```

Expected for lesson-credits / tasks:
```
STORAGE_BACKEND=lakefs
LAKEFS_ENDPOINT=http://...
LAKEFS_ACCESS_KEY_ID=...
ENABLE_DELETE_TOOLS=0
```

### 6.3 Logs and details

```bash
# CRD details
kubectl describe mcpserver mcp-knowledge-base -n kagent
kubectl describe mcpserver mcp-lesson-credits  -n kagent
kubectl describe mcpserver mcp-tasks           -n kagent
kubectl describe agent     assistant-agent     -n kagent

# MCP server logs
kubectl logs -n kagent -l app.kubernetes.io/name=mcp-knowledge-base  --tail=30
kubectl logs -n kagent -l app.kubernetes.io/name=mcp-lesson-credits  --tail=30
kubectl logs -n kagent -l app.kubernetes.io/name=mcp-tasks           --tail=30
```

### 6.4 Functional check via UI

In kagent UI → **assistant-agent**, try:

| Server | Sample prompt | Expected |
|--------|---------------|----------|
| knowledge-base | "How many documents are in the knowledge base?" | Count from LakeFS/backend |
| lesson-credits | "How many lessons are left?" | Balance from LakeFS |
| tasks | "Show all workspaces" | List of workspaces |

If answers match real data, deployment succeeded.

## Step 7 — Open kagent UI

Direct access (Rancher Desktop):

```
http://192.168.64.4:8089/
```

Or port-forward if external IP is unavailable:

```bash
kubectl -n kagent port-forward svc/kagent-ui 8089:8080
```

Browser: **http://127.0.0.1:8089/** → select **assistant-agent**.

> **Port 8089 note:** Gateway listens on `8089` instead of default `80` because port `80` conflicts with the Rancher Desktop SSH tunnel — `svclb-agentgateway-external` fails with `EADDRINUSE`. After a cluster reboot, Flux may reset the config; see Troubleshooting → "kagent UI unavailable".

### Sample prompts

**Knowledge Base:**
```
Find the document about AWS Skill Builder in the knowledge base
How many documents are in the knowledge base?
```

**Lesson Credits:**
```
How many lessons are left for English. *** ?
Deduct 1 lesson for English. ***
```

**Task Manager:**
```
Show all workspaces
Create a card "Verify Lab3" in list To Do on board Work
```

## Teardown

```bash
kubectl delete -f manifests/kagent/assistant/all-in-one.yaml
# or
kubectl delete -k manifests/kagent/assistant
```

## Troubleshooting

See [`manifests/kagent/assistant/README.md`](manifests/kagent/assistant/README.md) for detailed troubleshooting.

### kagent UI unavailable (`Unable to connect` / `404`)

Flux CD may reset the Gateway to port `80` (OCI artifact, not Git). Port `80` conflicts with the Rancher Desktop SSH tunnel — ServiceLB pod cannot start.

```bash
flux suspend kustomization releases

kubectl patch gateway agentgateway-external -n agentgateway-system \
  --type='json' -p='[{"op":"replace","path":"/spec/listeners/0/port","value":8089}]'

kubectl rollout restart deployment agentgateway-external -n agentgateway-system

curl -s -o /dev/null -w "%{http_code}" http://192.168.64.4:8089/
# expect: 200
```

> After a cluster reboot, repeat these steps.

### MCP server runs but returns empty data / "local storage"

Symptom: agent calls MCP but data does not match the storage web UI.

Cause: `STORAGE_BACKEND=local` from Dockerfile overrides Secret if Secret was applied incorrectly.

```bash
kubectl get secret mcp-lesson-credits-secrets -n kagent -o yaml

POD=$(kubectl get pod -n kagent -l app.kubernetes.io/name=mcp-lesson-credits -o name | head -1)
kubectl exec -n kagent "$POD" -- env | grep STORAGE

kubectl delete secret mcp-lesson-credits-secrets -n kagent
kubectl apply -f manifests/kagent/assistant/secrets.yaml

kubectl rollout restart deployment -n kagent -l app.kubernetes.io/name=mcp-lesson-credits
```

### Service down / pod CrashLoopBackOff

```bash
kubectl describe pod -n kagent -l app.kubernetes.io/name=mcp-lesson-credits
kubectl logs -n kagent -l app.kubernetes.io/name=mcp-lesson-credits --previous --tail=50
```

Common causes:
- Wrong `image:` tag — `ErrImagePull`
- Missing Secret — `secretRef` points to a missing resource
- Port 80 conflict — see "kagent UI unavailable"

### Quick diagnostics

```bash
kubectl logs -n kagent -l app.kubernetes.io/name=kagent-controller --tail=100
kubectl rollout restart deployment -n kagent -l app.kubernetes.io/name=mcp-lesson-credits
```

---

## Demo session

Session after connecting MCP servers to LakeFS (March 24, 2026).

### Cluster state (k9s)

All 31 pods `Running`, three MCP servers with 0 restarts — lakeFS connected:

![k9s cluster state](docs/screenshots/Screenshot%202026-03-24%20at%2022.45.23.png)

### Lesson balance request

Agent calls `lessons_list_calendars` and `lessons_get_balance`:

![Balance request](docs/screenshots/Screenshot%202026-03-24%20at%2022.39.00.png)

### Reply: balance and suggested actions

![Agent reply](docs/screenshots/Screenshot%202026-03-24%20at%2022.39.07.png)

### Transaction history

Prompt *"show payment history"* — agent lists operations:

![History start](docs/screenshots/Screenshot%202026-03-24%20at%2022.39.14.png)

### Top-up

Prompt *"add 5 more lessons and show the table"* — `lessons_top_up`, balance becomes 8:

![Top-up](docs/screenshots/Screenshot%202026-03-24%20at%2022.39.51.png)

### Transaction table after top-up

![Transaction table](docs/screenshots/Screenshot%202026-03-24%20at%2022.40.00.png)

### Task Manager — project list

Prompt *"show current projects"* — `tasks_list_workspaces`:

![Project list](docs/screenshots/Screenshot%202026-03-24%20at%2022.42.08.png)

---

### ModuleNotFoundError: agents / core

Image was not built from `agentic-ai-landing-zone` root. Verify:

```bash
docker build -t mcp-lesson-credits:latest \
  -f "$LAB3/mcp-servers/src/lesson-credits/Dockerfile" \
  "$ALZ"   # ← build context = ALZ root
```
