#!/usr/bin/env bash
# Lab1 medium: agentgateway + kagent on Kubernetes (Helm)
# Docs:
#   agentgateway k8s: https://agentgateway.dev/docs/kubernetes/latest/quickstart/install
#   kagent:           https://kagent.dev/docs/kagent/getting-started/quickstart
#
# WARNING: Do NOT run `kagent install --profile demo` on single-node k3s —
# the demo profile installs ~10 agents and overloads the kine/SQLite backend.

set -euo pipefail
LAB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
K8S_DIR="$LAB_DIR/k8s"

AGENTGATEWAY_VERSION="v2.2.1"
KAGENT_NAMESPACE="kagent"
AGENTGATEWAY_NS="agentgateway-system"

# ── Colors ───────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}[+]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
error() { echo -e "${RED}[✗]${NC} $*"; exit 1; }
step()  { echo -e "\n${GREEN}===${NC} $* ${GREEN}===${NC}"; }

# kubectl apply with --validate=false (avoids TLS timeout loading OpenAPI schema)
kapply() { kubectl apply --validate=false "$@"; }

# ── 0. Prerequisites ───────────────────────────────────────────────────────────
step "0. Tooling check"
for tool in kubectl helm; do
  if ! command -v "$tool" &>/dev/null; then
    case "$tool" in
      kubectl) error "kubectl not found. Install: https://kubernetes.io/docs/tasks/tools/" ;;
      helm)    error "helm not found. Install: https://helm.sh/docs/intro/install/" ;;
    esac
  else
    info "$tool: $(${tool} version --client 2>/dev/null | head -1 || ${tool} version 2>/dev/null | head -1)"
  fi
done

# Install kagent CLI if missing
if ! command -v kagent &>/dev/null; then
  warn "kagent CLI not found — installing..."
  if command -v brew &>/dev/null; then
    brew install kagent
  else
    curl -fsSL https://raw.githubusercontent.com/kagent-dev/kagent/refs/heads/main/scripts/get-kagent | bash
  fi
  info "kagent installed: $(kagent version 2>/dev/null | head -1)"
else
  info "kagent: $(kagent version 2>/dev/null | head -1)"
fi

# Cluster connectivity (Rancher Desktop / k3s)
kubectl cluster-info &>/dev/null || error "Cannot reach Kubernetes cluster.\n  Ensure Rancher Desktop is running: https://rancherdesktop.io/"
CONTEXT=$(kubectl config current-context)
info "Cluster: $CONTEXT"
[[ "$CONTEXT" != "rancher-desktop" ]] && warn "Current context is '$CONTEXT' — expected 'rancher-desktop'. Try: kubectl config use-context rancher-desktop"

# ── 1. API keys ────────────────────────────────────────────────────────────────
step "1. API key check"
[[ -z "${GEMINI_API_KEY:-}"    ]] && error "GEMINI_API_KEY not set.\n  export GEMINI_API_KEY=your-key"
info "GEMINI_API_KEY    (${#GEMINI_API_KEY} chars)"
[[ -z "${ANTHROPIC_API_KEY:-}" ]] && warn  "ANTHROPIC_API_KEY not set — Anthropic backend will be unavailable"  || info "ANTHROPIC_API_KEY (${#ANTHROPIC_API_KEY} chars)"
[[ -z "${OPENAI_API_KEY:-}"    ]] && warn  "OPENAI_API_KEY not set — OpenAI backend will be unavailable"        || info "OPENAI_API_KEY    (${#OPENAI_API_KEY} chars)"

# ── 2. Gateway API CRDs ────────────────────────────────────────────────────────
step "2. Install Gateway API CRDs"
kubectl apply --server-side --force-conflicts \
  -f https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.4.0/standard-install.yaml
info "Gateway API CRDs installed"

# ── 3. agentgateway Helm ─────────────────────────────────────────────────────
step "3. Install agentgateway (Helm)"
kubectl create namespace "$AGENTGATEWAY_NS" --dry-run=client -o yaml | kapply -f -

helm upgrade -i agentgateway-crds oci://ghcr.io/kgateway-dev/charts/agentgateway-crds \
  --namespace "$AGENTGATEWAY_NS" \
  --version "$AGENTGATEWAY_VERSION" \
  --set controller.image.pullPolicy=Always \
  --wait
info "agentgateway-crds installed"

helm upgrade -i agentgateway oci://ghcr.io/kgateway-dev/charts/agentgateway \
  --namespace "$AGENTGATEWAY_NS" \
  --version "$AGENTGATEWAY_VERSION" \
  --set controller.image.pullPolicy=Always \
  --set controller.extraEnv.KGW_ENABLE_GATEWAY_API_EXPERIMENTAL_FEATURES=true \
  --wait
info "agentgateway installed"

kubectl wait --for=condition=Available deployment/agentgateway \
  -n "$AGENTGATEWAY_NS" --timeout=120s

# ── 4. Per-provider Secrets ───────────────────────────────────────────────────
step "4. Create Secrets for each LLM provider"
kubectl create secret generic gemini-secret \
  --namespace "$AGENTGATEWAY_NS" \
  --from-literal=Authorization="${GEMINI_API_KEY}" \
  --dry-run=client -o yaml | kapply -f -
info "Applied Secret gemini-secret (agentgateway-system)"

kubectl create secret generic anthropic-secret \
  --namespace "$AGENTGATEWAY_NS" \
  --from-literal=Authorization="${ANTHROPIC_API_KEY:-placeholder}" \
  --dry-run=client -o yaml | kapply -f -
info "Applied Secret anthropic-secret (agentgateway-system)"

kubectl create secret generic openai-secret \
  --namespace "$AGENTGATEWAY_NS" \
  --from-literal=Authorization="${OPENAI_API_KEY:-placeholder}" \
  --dry-run=client -o yaml | kapply -f -
info "Applied Secret openai-secret (agentgateway-system)"

# ── 5. Gateway + Backends + HTTPRoute ─────────────────────────────────────────
step "5. Deploy Gateway, AgentgatewayBackends, and HTTPRoute"
kapply -f "$K8S_DIR/agentgateway/gateway.yaml"
info "Applied Gateway, Backends, and HTTPRoute"

# ── 6. kagent (minimal stack) ─────────────────────────────────────────────────
step "6. Install kagent in the cluster"
# Helm with demo agents disabled (avoids overloading kine/SQLite on single-node k3s)
helm upgrade -i kagent-crds oci://ghcr.io/kagent-dev/kagent/helm/kagent-crds \
  --namespace "$KAGENT_NAMESPACE" --create-namespace \
  --wait --timeout 60s
helm upgrade -i kagent oci://ghcr.io/kagent-dev/kagent/helm/kagent \
  --namespace "$KAGENT_NAMESPACE" \
  --set agents.k8s-agent.enabled=false \
  --set agents.kgateway-agent.enabled=false \
  --set agents.istio-agent.enabled=false \
  --set agents.promql-agent.enabled=false \
  --set agents.observability-agent.enabled=false \
  --set agents.argo-rollouts-agent.enabled=false \
  --set agents.helm-agent.enabled=false \
  --set agents.cilium-policy-agent.enabled=false \
  --set agents.cilium-manager-agent.enabled=false \
  --set agents.cilium-debug-agent.enabled=false \
  --wait --timeout 120s
info "kagent core installed (no demo agents)"

info "Waiting for kagent-controller..."
kubectl wait --for=condition=Available deployment/kagent-controller \
  -n "$KAGENT_NAMESPACE" --timeout=120s 2>/dev/null \
  || warn "kagent-controller not Ready yet — check: kubectl get pods -n $KAGENT_NAMESPACE"

# ── 7. kagent ModelConfig + Agent ────────────────────────────────────────────
step "7. Configure kagent: ModelConfig and Agent"

# Secret in kagent namespace (kagent → agentgateway auth)
kubectl create secret generic gemini-secret \
  --namespace "$KAGENT_NAMESPACE" \
  --from-literal=Authorization="${GEMINI_API_KEY}" \
  --dry-run=client -o yaml | kapply -f -
info "Applied Secret gemini-secret (kagent)"

kapply -f "$K8S_DIR/kagent/kagent-model.yaml"
info "Applied ModelConfig agentgateway-gemini"

kapply -f "$K8S_DIR/kagent/kagent-agent.yaml"
info "Applied Agent k8s-agentgateway-agent"

# ── 8. Ingress (Traefik) ─────────────────────────────────────────────────────
step "8. Ingress for kagent-ui and agentgateway-proxy"
kapply -f "$K8S_DIR/ingress.yaml"
info "Ingress applied"

# /etc/hosts hint
if ! grep -q "aire2026.local" /etc/hosts 2>/dev/null; then
  warn "Add to /etc/hosts:"
  warn "  echo '192.168.64.4  kagent.aire2026.local api.aire2026.local' | sudo tee -a /etc/hosts"
fi

# ── 9. Status ────────────────────────────────────────────────────────────────
step "9. Deployment status"
echo ""
info "Pods in $AGENTGATEWAY_NS:"
kubectl get pods -n "$AGENTGATEWAY_NS"
echo ""
info "Pods in $KAGENT_NAMESPACE:"
kubectl get pods -n "$KAGENT_NAMESPACE"
echo ""
info "Gateway:"
kubectl get gateway agentgateway-proxy -n "$AGENTGATEWAY_NS" 2>/dev/null || true
echo ""
info "ModelConfig and Agents:"
kubectl get modelconfig,agents -n "$KAGENT_NAMESPACE" 2>/dev/null || true

echo ""
echo -e "${GREEN}✓ Deploy complete!${NC}"
echo ""
echo "  ┌─────────────────────────────────────────────────────────────┐"
echo "  │  Access without port-forward (needs /etc/hosts line):       │"
echo "  │                                                             │"
echo "  │  kagent UI:      http://kagent.aire2026.local              │"
echo "  │  agentgateway:   http://api.aire2026.local                  │"
echo "  │                                                             │"
echo "  │  sudo tee -a /etc/hosts <<< \\                              │"
echo "  │    '192.168.64.4 kagent.aire2026.local api.aire2026.local'  │"
echo "  └─────────────────────────────────────────────────────────────┘"
echo ""
echo "  API test:"
echo "    curl -s http://api.aire2026.local/v1/chat/completions \\"
echo "      -H 'Content-Type: application/json' \\"
echo "      -d '{\"model\":\"gemini-2.5-flash\",\"messages\":[{\"role\":\"user\",\"content\":\"ping\"}]}'"
