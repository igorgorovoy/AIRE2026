# Deploy MCP “add two numbers” + agent `add-numbers-agent`

**kagent** manifests: `MCPServer` + `Agent`. Docker image source: [`../../docs/examples/add-two-mcp/`](../../docs/examples/add-two-mcp/).

| File | Description |
|------|-------------|
| `mcpserver.yaml` | `MCPServer` `mcp-add-two` only |
| `agent.yaml` | `Agent` `add-numbers-agent` only |
| `kustomization.yaml` | Kustomize: apply both resources |
| `all-in-one.yaml` | Both resources in one file |

## Prerequisites

1. Cluster has **kagent** (namespace `kagent`, CRDs `mcpservers`, `agents`).
2. **ModelConfig** (usually `default-model-config`):

   ```bash
   kubectl get modelconfigs -n kagent
   ```

3. **Secret** with `OPENAI_API_KEY` for the provider (see [`LAB2.md`](../../LAB2.md), model / OpenAI section).

## 1. Build Docker image

From **Lab2 repo root** (where `manifests/` and `docs/` live):

```bash
docker build -t add-two-mcp:latest docs/examples/add-two-mcp
```

### Rancher Desktop

Images from **`docker build`** usually share the same store as Kubernetes on Rancher Desktop. If the pod is `ImagePullBackOff` / `ErrImageNeverPull`:

- In **Rancher Desktop → Kubernetes**, use the same container runtime as Docker (or push to a registry the cluster can pull).
- Or push to GHCR/Docker Hub and set `image:` in `mcpserver.yaml` to e.g. `ghcr.io/<user>/add-two-mcp:latest`.

#### Without Docker registry (import into Rancher Desktop VM)

If kubelet tries Docker Hub (`pull access denied for add-two-mcp`) and the local build is not on the node — save a tar and load into the **Docker daemon inside the VM** via `rdctl shell`:

```bash
# from Lab2 root
docker build -t add-two-mcp:latest docs/examples/add-two-mcp
docker save add-two-mcp:latest -o "$HOME/add-two-mcp.tar"

rdctl shell -- sh -lc 'sudo docker load -i '"$HOME"'/add-two-mcp.tar'

kubectl delete pod -n kagent -l app.kubernetes.io/name=mcp-add-two
kubectl get pods -n kagent | grep mcp-add-two
```

On macOS, `$HOME/add-two-mcp.tar` is usually visible in `rdctl shell` at the same path. If `load` cannot find the file, save the tar to a directory that is mounted in the VM or copy manually.

## 2. Apply manifests

From **Lab2 root**, run **one** of:

### Option A — single file

```bash
kubectl apply -f manifests/kagent/add-two-mcp/all-in-one.yaml
```

### Option B — Kustomize

```bash
kubectl apply -k manifests/kagent/add-two-mcp
```

### Option C — sequential

```bash
kubectl apply -f manifests/kagent/add-two-mcp/mcpserver.yaml
kubectl apply -f manifests/kagent/add-two-mcp/agent.yaml
```

## 3. Verification

```bash
kubectl get mcpservers,agents -n kagent
kubectl get pods -n kagent | grep -E 'add-two|mcp-add|NAME'
kubectl describe mcpserver mcp-add-two -n kagent
kubectl describe agent add-numbers-agent -n kagent
```

Expected: MCP pods `Running`, agent **Ready** / **Accepted** (depends on CRD version).

## 4. Open kagent UI

```bash
kubectl -n agentgateway-system port-forward svc/agentgateway-external 8080:80
```

Browser: **http://127.0.0.1:8080/** → select **add-numbers-agent**, try chat (*“Add 17 and 25”*).

### Example success

[`LAB2.md`](../../LAB2.md) (**“Success”** section) has screenshots: MCP `add_two_numbers` call, chat reply, k9s pods — under [`images/lab/`](../../images/lab/).

## 5. Remove (optional)

```bash
kubectl delete -f manifests/kagent/add-two-mcp/all-in-one.yaml
# or
kubectl delete -k manifests/kagent/add-two-mcp
```

## Troubleshooting

### `Failed to create MCP session` / `TaskGroup` in UI

1. In `spec.declarative.tools[].mcpServer` include full CRD reference, especially **`apiGroup: kagent.dev`** next to `kind: MCPServer` and `name` (see [kagent troubleshooting](https://github.com/kagent-dev/kagent/blob/main/docs/troubleshooting.md)).
2. Check MCP pods and controller:

   ```bash
   kubectl get pods,mcpserver,agent -n kagent
   kubectl logs -n kagent -l app.kubernetes.io/name=kagent-controller --tail=100
   kubectl describe mcpserver mcp-add-two -n kagent
   ```

3. If MCP pod is **CrashLoop** / **ImagePullBackOff**:
   - Manifest sets **`imagePullPolicy: IfNotPresent`**: for tag `:latest` Kubernetes may still use **`Always`** and pull a non-existent image from Docker Hub.
   - Rebuild `add-two-mcp:latest` and ensure **Rancher Desktop / k3s** shares the image store with `docker build` (see section 1). If still missing on the node, try a tag other than `latest`, e.g. `add-two-mcp:local`, or `imagePullPolicy: Never` only after the image is definitely loaded in the cluster runtime.
   - On **Rancher Desktop** without registry: see **“Without Docker registry”** above (`docker save` → `rdctl shell` → `sudo docker load`).

## Notes

- If `kubectl explain mcpserver` shows a different `apiVersion`, adjust YAML for your cluster.
- Tool name in `toolNames` must match `server.py` (`add_two_numbers`).
