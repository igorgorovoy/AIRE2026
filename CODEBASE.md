# CODEBASE.md — AI Review Context

> Gives the AI reviewer context for the AIRE2026 repository.
> Update when adding components or changing architecture.

## Project goal

**AIRE2026** is the course repo for AI & Reliability Engineering 2026.
It demonstrates AI agents and an LLM gateway using [agentgateway](https://agentgateway.dev) and [kagent](https://kagent.dev) on Kubernetes.

## Layout

```
AIRE2026/
├── Lab1/
│   ├── beginers/          # Standalone: agentgateway binary + config.yaml
│   │   ├── run.sh         # Bash: install + run
│   │   └── config.yaml    # agentgateway config (YAML)
│   ├── medium/            # Kubernetes: Helm + kagent
│   │   ├── run.sh         # Bash: Helm install + kubectl apply
│   │   ├── k8s/
│   │   │   ├── agentgateway/  # Gateway, Backends, HTTPRoute manifests
│   │   │   ├── kagent/        # ModelConfig, Agent manifests
│   │   │   └── ingress.yaml   # Traefik Ingress
│   │   └── screenshots/   # Documentation screenshots
│   └── max/               # Advanced (WIP)
├── .github/
│   ├── workflows/         # GitHub Actions
│   └── scripts/           # Python scripts for workflows
├── CODEBASE.md            # This file
├── REVIEW.md              # AI review criteria
└── EVALS.md               # Review evaluation methodology
```

## Tech stack

| Component | Technology | Version |
|-----------|------------|---------|
| LLM Gateway | agentgateway | v1.0.0-rc.2 (standalone), v2.2.1 (k8s) |
| AI Agents | kagent | v0.7.23 |
| Kubernetes | k3s (Rancher Desktop) | v1.x |
| Helm | Helm | v3.x |
| Ingress | Traefik | v3.x |
| CI/CD | GitHub Actions | — |
| AI Review | GitHub Models | gpt-4o-mini |

## Key files

### `Lab1/beginers/config.yaml`
- Standalone agentgateway YAML config
- Defines `binds`, `listeners`, `routes`, `backends`, `policies`
- Env vars via `$VAR_NAME`
- Schema: `https://agentgateway.dev/schema/config`

### `Lab1/beginers/run.sh`
- Bash with `set -e` (fail-fast)
- Downloads agentgateway binary from GitHub Releases
- Checks API keys before start
- Supports darwin/linux, arm64/amd64

### `Lab1/medium/run.sh`
- Bash with `set -euo pipefail`
- Installs Gateway API CRDs, agentgateway (Helm), kagent (Helm)
- `kapply()` uses `--validate=false` for unstable API server behavior
- Disables all kagent demo agents (avoids OOMKill on single-node k3s)

### `Lab1/medium/k8s/agentgateway/gateway.yaml`
- `Gateway`, `AgentgatewayBackend`, `HTTPRoute`
- Gateway API v1 (`gateway.networking.k8s.io/v1`)

### `Lab1/medium/k8s/kagent/`
- `kagent-model.yaml`: `ModelConfig` (kagent.dev/v1alpha2)
- `kagent-agent.yaml`: `Agent` (kagent.dev/v1alpha2), `type: Declarative`

## Conventions

### Bash
- Prefer `set -euo pipefail` or at least `set -e`
- Colored helpers: `info()`, `warn()`, `error()`, `step()`
- Check dependencies at script start
- No hardcoded secrets — only `${VAR:-}` from env
- Idempotency: `--dry-run=client | apply` instead of create

### Kubernetes manifests
- `apiVersion` matches installed CRDs
- Namespace explicit on every resource
- Labels: `app.kubernetes.io/name`, `app.kubernetes.io/component`

### Secrets
- `.env` in `.gitignore`
- No API keys in code or committed manifests
- In cluster: `kubectl create secret --from-literal` from env

### Documentation
- README per lab directory
- Screenshots in `screenshots/` with descriptive names

## Known environment limits

- **k3s single-node:** SQLite backend (kine) struggles with >5 concurrent heavy Helm installs
- **Rancher Desktop Lima VM:** limited RAM; kagent demo profile can OOM
- **agentgateway k8s UI:** not available (standalone only)
- **Traefik CRD overlap:** Gateway API CRDs may need Helm ownership annotations
