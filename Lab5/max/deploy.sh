#!/usr/bin/env bash
set -euo pipefail

# -------------------------------------------------------------------
# Lab5 Max: GitlessOps — deploy Phoenix + Qdrant via Flux CLI
# No git repo needed. All Flux resources created imperatively.
#
# Phoenix has no official Helm chart — deployed as plain K8s resources.
# Qdrant uses official Helm chart via Flux HelmRelease.
# -------------------------------------------------------------------

# --- helpers --------------------------------------------------------
info()  { printf '\033[1;34m[INFO]\033[0m  %s\n' "$*"; }
step()  { printf '\033[1;32m[STEP]\033[0m  %s\n' "$*"; }
warn()  { printf '\033[1;33m[WARN]\033[0m  %s\n' "$*"; }
error() { printf '\033[1;31m[ERROR]\033[0m %s\n' "$*" >&2; }

# --- preflight ------------------------------------------------------
for cmd in kubectl flux; do
  command -v "$cmd" >/dev/null || { error "$cmd not found"; exit 1; }
done

NAMESPACE="observability"

step "Creating namespace $NAMESPACE"
kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

# -------------------------------------------------------------------
# Qdrant — official Helm repo (GitHub Pages)
# -------------------------------------------------------------------
step "Creating Flux HelmRepository: qdrant (https://qdrant.github.io/qdrant-helm)"
flux create source helm qdrant \
  --url=https://qdrant.github.io/qdrant-helm \
  --namespace=flux-system

# Values must exist before HelmRelease references them
step "Creating ConfigMap: qdrant-values"
kubectl apply -f - <<'EOF'
apiVersion: v1
kind: ConfigMap
metadata:
  name: qdrant-values
  namespace: observability
data:
  values.yaml: |
    replicaCount: 1
    persistence:
      size: 5Gi
    resources:
      requests:
        memory: 256Mi
        cpu: 100m
      limits:
        memory: 1Gi
EOF

step "Creating Flux HelmRelease: qdrant"
flux create helmrelease qdrant \
  --namespace="$NAMESPACE" \
  --source=HelmRepository/qdrant.flux-system \
  --chart=qdrant \
  --chart-version="1.17.1" \
  --create-target-namespace \
  --values-from=ConfigMap/qdrant-values

# -------------------------------------------------------------------
# Phoenix — no Helm chart available, deploy as plain K8s resources
# -------------------------------------------------------------------
step "Deploying Phoenix (plain manifests — no Helm chart exists)"
kubectl apply -f - <<'EOF'
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: phoenix-data
  namespace: observability
  labels:
    app.kubernetes.io/name: phoenix
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 2Gi
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: phoenix
  namespace: observability
  labels:
    app.kubernetes.io/name: phoenix
    app.kubernetes.io/component: tracing
spec:
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: phoenix
  template:
    metadata:
      labels:
        app.kubernetes.io/name: phoenix
    spec:
      containers:
        - name: phoenix
          image: arizephoenix/phoenix:latest
          ports:
            - name: http
              containerPort: 6006
            - name: grpc
              containerPort: 4317
          env:
            - name: PHOENIX_WORKING_DIR
              value: /data
          volumeMounts:
            - name: data
              mountPath: /data
          resources:
            requests:
              memory: 256Mi
              cpu: 100m
            limits:
              memory: 1Gi
      volumes:
        - name: data
          persistentVolumeClaim:
            claimName: phoenix-data
---
apiVersion: v1
kind: Service
metadata:
  name: phoenix
  namespace: observability
  labels:
    app.kubernetes.io/name: phoenix
spec:
  selector:
    app.kubernetes.io/name: phoenix
  ports:
    - name: http
      port: 6006
      targetPort: 6006
    - name: grpc
      port: 4317
      targetPort: 4317
EOF

# -------------------------------------------------------------------
# Ingress — Traefik
# -------------------------------------------------------------------
step "Creating Ingress resources for UI access"
kubectl apply -f - <<'EOF'
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: phoenix
  namespace: observability
  annotations:
    traefik.ingress.kubernetes.io/router.entrypoints: web
spec:
  ingressClassName: traefik
  rules:
    - host: phoenix.aire2026.local
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: phoenix
                port:
                  number: 6006
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: qdrant
  namespace: observability
  annotations:
    traefik.ingress.kubernetes.io/router.entrypoints: web
spec:
  ingressClassName: traefik
  rules:
    - host: qdrant.aire2026.local
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: qdrant
                port:
                  number: 6333
EOF

# -------------------------------------------------------------------
# Wait & verify
# -------------------------------------------------------------------
step "Reconciling Qdrant HelmRelease..."
flux reconcile source helm qdrant  --namespace=flux-system 2>/dev/null || true
flux reconcile helmrelease qdrant  --namespace="$NAMESPACE" 2>/dev/null || true

info "Waiting for pods..."
kubectl rollout status deployment/phoenix -n "$NAMESPACE" --timeout=120s || true
kubectl get pods -n "$NAMESPACE"

echo ""
info "UI endpoints (add to /etc/hosts -> 127.0.0.1):"
info "  Phoenix:  http://phoenix.aire2026.local"
info "  Qdrant:   http://qdrant.aire2026.local"
echo ""
step "Done!"
