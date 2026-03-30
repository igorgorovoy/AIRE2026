# Deploy Assistant Agent — Knowledge Base + Lesson Credits + Task Manager

**kagent** manifests: 3 × `MCPServer` + 1 × `Agent`. Docker image sources: [`../../../mcp-servers/src/`](../../../mcp-servers/src/).

| File | Description |
|------|-------------|
| `mcpserver-knowledge-base.yaml` | `MCPServer` `mcp-knowledge-base` |
| `mcpserver-lesson-credits.yaml` | `MCPServer` `mcp-lesson-credits` |
| `mcpserver-tasks.yaml` | `MCPServer` `mcp-tasks` |
| `agent.yaml` | `Agent` `assistant-agent` (references 3 MCP servers) |
| `kustomization.yaml` | Kustomize: apply all 4 resources |
| `all-in-one.yaml` | All 4 resources in one file |

## Prerequisites

1. Cluster has **kagent** (namespace `kagent`, CRDs `mcpservers`, `agents`).
2. **ModelConfig** `default-model-config`:

   ```bash
   kubectl get modelconfigs -n kagent
   ```

3. **Secret** with `OPENAI_API_KEY` (or another provider).
4. For `mcp-knowledge-base`: KB backend running and URL known.

## 1. Build Docker images

### mcp-knowledge-base (standalone)

```bash
# from Lab3 root
docker build -t mcp-knowledge-base:latest mcp-servers/src/knowledge-base
```

### mcp-lesson-credits and mcp-tasks (require agentic-ai-landing-zone)

Both depend on `agents/`, `core/` from `agentic-ai-landing-zone`.  
Build **from that repo root** with `-f` pointing at the Dockerfile.

```bash
ALZ=/path/to/agentic-ai-landing-zone
LAB3=/path/to/AIRE2026/Lab3

docker build -t mcp-lesson-credits:latest \
  -f "$LAB3/mcp-servers/src/lesson-credits/Dockerfile" "$ALZ"

docker build -t mcp-tasks:latest \
  -f "$LAB3/mcp-servers/src/tasks/Dockerfile" "$ALZ"
```

### Rancher Desktop / k3s (no registry)

Images from `docker build` are usually visible to Kubernetes.  
If the pod is `ImagePullBackOff`, load the image into the VM:

```bash
docker save mcp-knowledge-base:latest  -o ~/mcp-knowledge-base.tar
docker save mcp-lesson-credits:latest  -o ~/mcp-lesson-credits.tar
docker save mcp-tasks:latest           -o ~/mcp-tasks.tar

rdctl shell -- sh -lc 'sudo docker load -i ~/mcp-knowledge-base.tar'
rdctl shell -- sh -lc 'sudo docker load -i ~/mcp-lesson-credits.tar'
rdctl shell -- sh -lc 'sudo docker load -i ~/mcp-tasks.tar'
```

## 2. Set KB_API_BASE_URL

In `mcpserver-knowledge-base.yaml` (and `all-in-one.yaml`) set `KB_API_BASE_URL` to your backend URL:

```yaml
env:
  - name: KB_API_BASE_URL
    value: "http://<service>.<namespace>.svc.cluster.local:8000"
```

If the backend is outside the cluster, use an external URL or IP.

## 3. Apply manifests

From **Lab3 root**, pick **one** option:

### Option A — single file

```bash
kubectl apply -f manifests/kagent/assistant/all-in-one.yaml
```

### Option B — Kustomize

```bash
kubectl apply -k manifests/kagent/assistant
```

### Option C — sequential (MCPServer → Agent)

```bash
kubectl apply -f manifests/kagent/assistant/mcpserver-knowledge-base.yaml
kubectl apply -f manifests/kagent/assistant/mcpserver-lesson-credits.yaml
kubectl apply -f manifests/kagent/assistant/mcpserver-tasks.yaml
kubectl apply -f manifests/kagent/assistant/agent.yaml
```

## 4. Verification

```bash
kubectl get mcpservers,agents -n kagent
kubectl get pods -n kagent | grep -E 'mcp-|NAME'

kubectl describe mcpserver mcp-knowledge-base -n kagent
kubectl describe mcpserver mcp-lesson-credits  -n kagent
kubectl describe mcpserver mcp-tasks           -n kagent
kubectl describe agent     assistant-agent     -n kagent
```

Expected: pods `Running`, agent `Ready` / `Accepted`.

## 5. Services and access

### External access (LoadBalancer)

| Service | URL | Description |
|---------|-----|-------------|
| **kagent UI** | `http://192.168.64.4:8089/` | kagent web UI |
| **kagent API** | `http://192.168.64.4:8089/api` | kagent REST API |
| **Traefik HTTP** | `http://192.168.64.4:80` | Ingress controller |
| **Traefik HTTPS** | `https://192.168.64.4:443` | Ingress controller |

> `192.168.64.4` — Rancher Desktop external IP. Verify: `kubectl get svc -n agentgateway-system agentgateway-external`

### Agents (ClusterIP, namespace `kagent`)

| Service | Port | Description |
|---------|------|-------------|
| `assistant-agent` | 8080 | Our agent (Lab3) |
| `k8s-agent` | 8080 | Kubernetes agent |
| `observability-agent` | 8080 | Observability agent |
| `promql-agent` | 8080 | PromQL agent |
| `helm-agent` | 8080 | Helm agent |
| `kagent-grafana-mcp` | 8000 | Grafana MCP |

### MCP servers (namespace `kagent`)

| Service | Port | Description |
|---------|------|-------------|
| `mcp-knowledge-base` | 3000 | Knowledge Base (Lab3) |
| `mcp-lesson-credits` | 3000 | Lesson Credits (Lab3) |
| `mcp-tasks` | 3000 | Task Manager (Lab3) |

### Open kagent UI

Direct (Rancher Desktop):
```
http://192.168.64.4:8089/
```

Or port-forward if external IP is unavailable:
```bash
kubectl -n agentgateway-system port-forward svc/agentgateway-external 8089:8089
```
Browser: **http://127.0.0.1:8089/** → select **assistant-agent**.

Sample prompts:
- *"How many lessons are left for English. Mary?"*
- *"Show open cards on board X"*
- *"Find the AWS document in the knowledge base"*

## 6. Remove (optional)

```bash
kubectl delete -f manifests/kagent/assistant/all-in-one.yaml
# or
kubectl delete -k manifests/kagent/assistant
```

## Troubleshooting

### `Failed to create MCP session` / `TaskGroup` in UI

1. Check all MCPServer pods are `Running`:
   ```bash
   kubectl get pods -n kagent | grep mcp
   kubectl logs -n kagent -l app.kubernetes.io/name=mcp-lesson-credits --tail=50
   ```
2. Check controller:
   ```bash
   kubectl logs -n kagent -l app.kubernetes.io/name=kagent-controller --tail=100
   ```
3. Tool names in `toolNames` must match `server.py` (`@mcp.tool()`).

### `ImagePullBackOff`

- Ensure `imagePullPolicy: IfNotPresent` is set.
- For k3s/Rancher Desktop: load image via `docker save` + `rdctl shell` (see section 1).

### `ModuleNotFoundError: agents` or `core`

- Image `mcp-lesson-credits` / `mcp-tasks` was not built from `agentic-ai-landing-zone` root.
- Ensure `-f` points to the correct Dockerfile and build context is ALZ root.

### Delete tools (`tasks_delete_card` and others)

Tool `tasks_delete_card` is **always visible** in MCP (`@mcp.tool()` unconditional) — the agent may call it. Actual deletion is **disabled by default**.

**Delete tools per server:**

| Server | Tool | Guard | State |
|--------|------|-------|-------|
| `mcp-tasks` | `tasks_delete_card` | `ENABLE_DELETE_TOOLS` | blocked (`=0`) |
| `mcp-lesson-credits` | `lessons_delete_transaction` | `ENABLE_DELETE_TOOLS` | blocked (`=0`) |
| `mcp-knowledge-base` | — | — | no delete tools |

**Protection stack:**

| Level | Value | Result |
|-------|-------|--------|
| Container env (manifest) | `ENABLE_DELETE_TOOLS=0` | `False` |
| Secret `dot-env` | `ENABLE_DELETE_TOOLS=0` | `False` |
| `server.py` check | `"0" in ("1","true","yes")` | `False` |

When invoked, tools return: `"Deletion disabled. Set ENABLE_DELETE_TOOLS=1 in .env."` — no data is deleted.

**To enable deletion** (intentional):

```bash
kubectl set env deployment/mcp-tasks -n kagent ENABLE_DELETE_TOOLS=1
kubectl set env deployment/mcp-lesson-credits -n kagent ENABLE_DELETE_TOOLS=1

# Persistent — set ENABLE_DELETE_TOOLS: "1" in mcpserver-*.yaml
kubectl apply -f manifests/kagent/assistant/mcpserver-tasks.yaml
kubectl apply -f manifests/kagent/assistant/mcpserver-lesson-credits.yaml
```

> **Caution:** the agent can delete data without extra confirmation.

### Data lost after pod restart

- Default `STORAGE_BACKEND=local` → data in `emptyDir` inside the container.
- For persistence: mount a `PersistentVolumeClaim` or switch to lakeFS.

### `Unable to connect` / Gateway returns 404

**Symptom:** browser cannot open `http://192.168.64.4:8089/`, or Gateway returns `404 route not found`.

**Cause:** Flux CD manages Gateway via OCI artifact (`oci://ghcr.io/den-vasyliev/abox/releases`), not Git. After each sync the Gateway port resets to `80`, and ServiceLB (`svclb-agentgateway-external`) cannot bind because port 80 is taken by the Rancher Desktop SSH tunnel.

**Diagnostics:**

```bash
kubectl get gateway agentgateway-external -n agentgateway-system \
  -o jsonpath='{.spec.listeners[0].port}'
kubectl get pods -n kube-system | grep svclb-agentgateway
```

**Fix:**

```bash
flux suspend kustomization releases

kubectl patch gateway agentgateway-external -n agentgateway-system \
  --type='json' -p='[{"op":"replace","path":"/spec/listeners/0/port","value":8089}]'

kubectl rollout restart deployment agentgateway-external -n agentgateway-system
kubectl rollout status deployment agentgateway-external -n agentgateway-system
```

> **After cluster reboot** Flux may resume — repeat steps 1–3.

**Verify:**

```bash
curl -s -o /dev/null -w "%{http_code}" http://192.168.64.4:8089/
# expect: 200
```

**Alternative without Flux changes** — port-forward to UI:

```bash
kubectl -n kagent port-forward svc/kagent-ui 8089:8080
# Browser: http://127.0.0.1:8089/
```
