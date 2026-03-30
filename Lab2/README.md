# abox

> One command. Full AI infrastructure.

`make run` gives you a local Kubernetes cluster with everything an AI project needs: an AI-aware API gateway, an agent runtime, observability, distributed tracing, and an eval harness — ready to use.

## What's included

| Component | Role |
|---|---|
| **agentgateway v2.2.1** | AI-aware API gateway (Gateway API–native, MCP-aware) |
| **kagent** | Kubernetes-native AI agent framework |
| **Flux CD 2.x** | GitOps/GitLessOps operator — keeps the cluster in sync with OCI artifacts |
| **Rancher Desktop Kubernetes** | Local Kubernetes cluster used by bootstrap |

## Lab (beginners)

Step-by-step: **UI access (Flux / kagent / gateway), model, MCP, agent, success screenshots** — in [`LAB2.md`](./LAB2.md).

### Flux Status Web UI (browser)

After bootstrap, **Flux Operator** may expose a web UI on port **9080**. Locally:

```bash
kubectl -n flux-system port-forward svc/flux-operator 9080:9080
# http://127.0.0.1:9080/
```

Details: [`LAB2.md`](./LAB2.md) and [Flux Operator Web UI](https://fluxoperator.dev/web-ui/).

## Quickstart

```bash
make run
```

That's it. Installs OpenTofu and k9s, bootstraps Flux into your Rancher Desktop cluster, and reconciles all components. When it finishes:

```bash
kubectl get gateway,httproute -A        # gateway is up
kubectl get agents -n kagent            # agent runtime is up
kubectl get svc -n agentgateway-system  # check gateway Service endpoint
```

Point your AI app at the gateway endpoint on port 80. If your local LoadBalancer endpoint is not reachable, use `kubectl port-forward` as a fallback.

## How it works

```
make run  →  scripts/setup.sh
  → tofu apply (bootstrap/)
      → Flux Operator + FluxInstance
      → ResourceSetInputProvider   polls oci://ghcr.io/den-vasyliev/abox/releases
      → ResourceSet                creates OCIRepository + 2 Kustomizations
          → releases/crds/    gateway-api-crds, agentgateway-crds, kagent-crds
          → releases/         agentgateway (Gateway + GatewayClass)
                              kagent (agent runtime + HTTPRoute)
```

Everything after the cluster is **gitless GitOps via OCI**: no Git polling, no deploy keys. CI publishes `releases/` as an OCI artifact on every version tag. The cluster reconciles from that artifact automatically.

## Releasing

```bash
make push   # bumps patch version, tags, pushes → CI publishes OCI artifact → cluster reconciles
```

> **Note:** RSIP tag sorting is lexicographic. If the patch version would exceed 9, bump the minor instead: `git tag vX.Y+1.0`.

## Directory layout

| Path | Purpose |
|---|---|
| `bootstrap/` | OpenTofu: Flux bootstrap (operator, instance, RSIP, ResourceSet) on existing k8s context |
| `releases/crds/` | CRD HelmReleases: gateway-api, agentgateway, kagent |
| `releases/` | App HelmReleases + Gateway + HTTPRoutes |
| `manifests/kagent/add-two-mcp/` | MCP + Agent lab example: manifests and [deploy instructions](./manifests/kagent/add-two-mcp/README.md) |
| `docs/examples/add-two-mcp/` | Source for the same MCP Docker image |
| `scripts/setup.sh` | Full setup script (`make run`) |
| `.github/workflows/flux-push.yaml` | CI: publish `releases/` as OCI artifact on `v*` tags |

## Adding components

1. Put CRD charts in `releases/crds/` as HelmReleases.
2. Put app charts in `releases/` as HelmReleases.
3. Run `make push` — the cluster reconciles automatically.

The CRD kustomization runs first (`wait: true`), apps run after (`dependsOn: releases-crds`). This ordering is enforced by Flux and must be preserved.

## Troubleshooting

### `flux` CLI shows an old version (e.g. 2.5.0) but Homebrew installed 2.8.x

`PATH` often contains **another** `flux` (e.g. in `~/.local/bin`) that shadows Homebrew.

- Check: `type -a flux` — the first line may be an old binary.
- Flux CD from Homebrew: `$(brew --prefix)/opt/flux/bin/flux version`

This repo’s **`scripts/flux.sh` does not use `flux` from PATH** (only Homebrew `opt/flux`), so the version is correct:

```bash
bash scripts/flux.sh version
make flux-version
make flux-reconcile
```

To make the plain `flux` command in the terminal use the new binary, add to `~/.zshrc`:

```bash
flux() { command "$(brew --prefix)/opt/flux/bin/flux" "$@"; }
```

Or for one session: `export FLUX_BIN="$(brew --prefix)/opt/flux/bin/flux"` then `bash scripts/flux.sh …`.

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md).

## License

Apache 2.0 — see [LICENSE](./LICENSE).
