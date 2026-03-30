# MCP server “add two numbers” (kagent lab)

- `server.py` — [FastMCP](https://github.com/jlowin/fastmcp) with tool `add_two_numbers`.
- `Dockerfile` — image for `MCPServer` in the cluster.
- `k8s.yaml` — symlink to canonical manifests: [`manifests/kagent/add-two-mcp/all-in-one.yaml`](../../../manifests/kagent/add-two-mcp/all-in-one.yaml).

## Build image

From **Lab2 root**:

```bash
docker build -t add-two-mcp:latest docs/examples/add-two-mcp
```

### Rancher Desktop: no registry

If pod `mcp-add-two` is `ImagePullBackOff` (kubelet does not see local image), import tar into the VM Docker daemon:

```bash
docker save add-two-mcp:latest -o "$HOME/add-two-mcp.tar"
rdctl shell -- sh -lc 'sudo docker load -i '"$HOME"'/add-two-mcp.tar'
kubectl delete pod -n kagent -l app.kubernetes.io/name=mcp-add-two
kubectl get pods -n kagent | grep mcp-add-two
```

More: [`manifests/kagent/add-two-mcp/README.md`](../../../manifests/kagent/add-two-mcp/README.md) (Rancher Desktop section).

## Deploy manifests

Full steps (prerequisites, `kubectl apply`, verify, UI, teardown):

**[`manifests/kagent/add-two-mcp/README.md`](../../../manifests/kagent/add-two-mcp/README.md)**

Short version from Lab2 root:

```bash
kubectl apply -f manifests/kagent/add-two-mcp/all-in-one.yaml
# or: kubectl apply -k manifests/kagent/add-two-mcp
```

On **Rancher Desktop** the image is usually visible to Kubernetes without `docker push`. If the pod fails on image, see the Rancher Desktop section in the manifests README.
