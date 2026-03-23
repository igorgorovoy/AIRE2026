# MCP-сервер «додати два числа» (лабораторна kagent)

- `server.py` — [FastMCP](https://github.com/jlowin/fastmcp) з одним інструментом `add_two_numbers`.
- `Dockerfile` — образ для `MCPServer` у кластері.
- `k8s.yaml` — симлінк на канонічні маніфести: [`manifests/kagent/add-two-mcp/all-in-one.yaml`](../../../manifests/kagent/add-two-mcp/all-in-one.yaml).

## Збірка образу

З **кореня Lab2**:

```bash
docker build -t add-two-mcp:latest docs/examples/add-two-mcp
```

### Rancher Desktop: образ без registry

Якщо под `mcp-add-two` у `ImagePullBackOff` (kubelet не бачить локальний образ), імпортуй tar у Docker daemon VM:

```bash
docker save add-two-mcp:latest -o "$HOME/add-two-mcp.tar"
rdctl shell -- sh -lc 'sudo docker load -i '"$HOME"'/add-two-mcp.tar'
kubectl delete pod -n kagent -l app.kubernetes.io/name=mcp-add-two
kubectl get pods -n kagent | grep mcp-add-two
```

Детальніше: [`manifests/kagent/add-two-mcp/README.md`](../../../manifests/kagent/add-two-mcp/README.md) (розділ Rancher Desktop).

## Деплой маніфестів

Повна інструкція (передумови, `kubectl apply`, перевірка, UI, видалення):

**[`manifests/kagent/add-two-mcp/README.md`](../../../manifests/kagent/add-two-mcp/README.md)**

Коротко з кореня Lab2:

```bash
kubectl apply -f manifests/kagent/add-two-mcp/all-in-one.yaml
# або: kubectl apply -k manifests/kagent/add-two-mcp
```

На **Rancher Desktop** образ зазвичай доступний Kubernetes без додаткового `docker push`. Якщо под не стартує через образ — див. розділ «Rancher Desktop» у README маніфестів.
