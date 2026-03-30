# Lab 5 — Phoenix + Qdrant on Kubernetes

Deploy [Phoenix](https://arize.com/docs/phoenix) (LLM observability) and [Qdrant](https://qdrant.tech) (vector database) on abox or your own k3s cluster.

## Prerequisites

- k3s cluster (Rancher Desktop / abox)
- `kubectl` configured
- Traefik Ingress Controller (default in k3s)
- `/etc/hosts` entries:
  ```
  127.0.0.1  phoenix.aire2026.local
  127.0.0.1  qdrant.aire2026.local
  ```

## UI Endpoints

| Service | URL | Port |
|---------|-----|------|
| Phoenix UI | http://phoenix.aire2026.local | 6006 |
| Phoenix OTLP (gRPC) | — | 4317 |
| Qdrant Dashboard | http://qdrant.aire2026.local | 6333 |
| Qdrant gRPC | — | 6334 |

---

## Level 1: Beginners — Plain Kubernetes Manifests

Deploy with `kubectl apply -k`:

```bash
kubectl apply -k Lab5/beginers/
```

Verify:

```bash
kubectl get pods -n observability
kubectl get ingress -n observability
```

Clean up:

```bash
kubectl delete -k Lab5/beginers/
```

### Structure

```
beginers/
├── namespace.yaml
├── kustomization.yaml
├── phoenix/
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── pvc.yaml
│   └── ingress.yaml
└── qdrant/
    ├── deployment.yaml
    ├── service.yaml
    ├── pvc.yaml
    └── ingress.yaml
```

---

## Level 2: Experienced — GitOps (Flux CD)

Requires Flux CD installed in the cluster (see Lab2).

Deploy the Flux resources:

```bash
kubectl apply -k Lab5/medium/releases/
```

Flux will reconcile HelmRelease resources and install both charts automatically.

Monitor reconciliation:

```bash
flux get helmreleases -n observability
flux get sources helm -n flux-system
```

### Structure

```
medium/
└── releases/
    ├── kustomization.yaml
    ├── phoenix.yaml      # HelmRepository + HelmRelease + Ingress
    └── qdrant.yaml       # HelmRepository + HelmRelease + Ingress
```

### Key Differences from Beginners

- Helm charts managed by Flux (auto-drift correction)
- HelmRepository sources: Phoenix OCI (GHCR); Qdrant classic index at [qdrant.github.io/qdrant-helm](https://qdrant.github.io/qdrant-helm) (Docker Hub OCI chart path is not published)
- Declarative — stored in git, applied by Flux Kustomization

---

## Level 3: Max — GitlessOps

Same Flux CD infrastructure, but **no git repository needed**. All Flux resources are created imperatively via `flux create` CLI commands.

```bash
./Lab5/max/deploy.sh
```

### How It Works

1. Creates namespace `observability`
2. `flux create source helm` — registers Helm repos (Phoenix: OCI; Qdrant: HTTPS index)
3. `flux create helmrelease` — creates HelmRelease resources imperatively
4. ConfigMaps hold Helm values (no file references needed)
5. Ingress applied via `kubectl apply`

### When to Use GitlessOps

- Rapid prototyping / experiments
- Environments without git access
- One-off deployments that don't need drift correction from git
- CI/CD pipelines that generate manifests dynamically

### Clean Up

```bash
flux delete helmrelease phoenix -n observability --silent
flux delete helmrelease qdrant  -n observability --silent
flux delete source helm phoenix -n flux-system --silent
flux delete source helm qdrant  -n flux-system --silent
kubectl delete namespace observability
```

---

## Verification

After deployment (any level), confirm both UIs are accessible:

```bash
# Phoenix health
curl -s http://phoenix.aire2026.local/healthz

# Qdrant health
curl -s http://qdrant.aire2026.local/healthz
```

Open in browser:
- **Phoenix**: http://phoenix.aire2026.local — LLM trace viewer
- **Qdrant**: http://qdrant.aire2026.local/dashboard — vector DB dashboard
