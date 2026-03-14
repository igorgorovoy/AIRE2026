#!/usr/bin/env bash
# Lab1 medium: agentgateway + kagent у Kubernetes (Helm deployment)
# Документація:
#   agentgateway k8s: https://agentgateway.dev/docs/kubernetes/latest/quickstart/install
#   kagent:           https://kagent.dev/docs/kagent/getting-started/quickstart
#
# УВАГА: НЕ запускайте `kagent install --profile demo` на single-node k3s —
# demo профіль встановлює ~10 агентів, що перевантажують kine/SQLite backend.

set -euo pipefail
LAB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
K8S_DIR="$LAB_DIR/k8s"

AGENTGATEWAY_VERSION="v2.2.1"
KAGENT_NAMESPACE="kagent"
AGENTGATEWAY_NS="agentgateway-system"

# ── Кольори ───────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}[+]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
error() { echo -e "${RED}[✗]${NC} $*"; exit 1; }
step()  { echo -e "\n${GREEN}===${NC} $* ${GREEN}===${NC}"; }

# kubectl apply з --validate=false (уникаємо TLS timeout при завантаженні OpenAPI схеми)
kapply() { kubectl apply --validate=false "$@"; }

# ── 0. Передумови ─────────────────────────────────────────────────────────────
step "0. Перевірка інструментів"
for tool in kubectl helm; do
  if ! command -v "$tool" &>/dev/null; then
    case "$tool" in
      kubectl) error "kubectl не знайдено. Встановіть: https://kubernetes.io/docs/tasks/tools/" ;;
      helm)    error "helm не знайдено. Встановіть: https://helm.sh/docs/intro/install/" ;;
    esac
  else
    info "$tool: $(${tool} version --client 2>/dev/null | head -1 || ${tool} version 2>/dev/null | head -1)"
  fi
done

# Встановлення kagent CLI якщо відсутній
if ! command -v kagent &>/dev/null; then
  warn "kagent CLI не знайдено — встановлюємо автоматично..."
  if command -v brew &>/dev/null; then
    brew install kagent
  else
    curl -fsSL https://raw.githubusercontent.com/kagent-dev/kagent/refs/heads/main/scripts/get-kagent | bash
  fi
  info "kagent встановлено: $(kagent version 2>/dev/null | head -1)"
else
  info "kagent: $(kagent version 2>/dev/null | head -1)"
fi

# Перевірка підключення до кластера (Rancher Desktop / k3s)
kubectl cluster-info &>/dev/null || error "Немає підключення до Kubernetes кластера.\n  Переконайтесь, що Rancher Desktop запущено: https://rancherdesktop.io/"
CONTEXT=$(kubectl config current-context)
info "Кластер: $CONTEXT"
[[ "$CONTEXT" != "rancher-desktop" ]] && warn "Поточний контекст '$CONTEXT' — очікується 'rancher-desktop'. Перевірте: kubectl config use-context rancher-desktop"

# ── 1. API ключі ──────────────────────────────────────────────────────────────
step "1. Перевірка API ключів"
[[ -z "${GEMINI_API_KEY:-}"    ]] && error "GEMINI_API_KEY не встановлено.\n  export GEMINI_API_KEY=your-key"
info "GEMINI_API_KEY    (${#GEMINI_API_KEY} символів)"
[[ -z "${ANTHROPIC_API_KEY:-}" ]] && warn  "ANTHROPIC_API_KEY не встановлено — Anthropic backend буде недоступний"  || info "ANTHROPIC_API_KEY (${#ANTHROPIC_API_KEY} символів)"
[[ -z "${OPENAI_API_KEY:-}"    ]] && warn  "OPENAI_API_KEY не встановлено — OpenAI backend буде недоступний"        || info "OPENAI_API_KEY    (${#OPENAI_API_KEY} символів)"

# ── 2. Gateway API CRDs ────────────────────────────────────────────────────────
step "2. Встановлення Gateway API CRDs"
kubectl apply --server-side --force-conflicts \
  -f https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.4.0/standard-install.yaml
info "Gateway API CRDs встановлено"

# ── 3. agentgateway Helm ──────────────────────────────────────────────────────
step "3. Встановлення agentgateway (Helm)"
kubectl create namespace "$AGENTGATEWAY_NS" --dry-run=client -o yaml | kapply -f -

helm upgrade -i agentgateway-crds oci://ghcr.io/kgateway-dev/charts/agentgateway-crds \
  --namespace "$AGENTGATEWAY_NS" \
  --version "$AGENTGATEWAY_VERSION" \
  --set controller.image.pullPolicy=Always \
  --wait
info "agentgateway-crds встановлено"

helm upgrade -i agentgateway oci://ghcr.io/kgateway-dev/charts/agentgateway \
  --namespace "$AGENTGATEWAY_NS" \
  --version "$AGENTGATEWAY_VERSION" \
  --set controller.image.pullPolicy=Always \
  --set controller.extraEnv.KGW_ENABLE_GATEWAY_API_EXPERIMENTAL_FEATURES=true \
  --wait
info "agentgateway встановлено"

kubectl wait --for=condition=Available deployment/agentgateway \
  -n "$AGENTGATEWAY_NS" --timeout=120s

# ── 4. Secrets для LLM провайдерів ────────────────────────────────────────────
step "4. Створення Secrets для кожного LLM провайдера"
kubectl create secret generic gemini-secret \
  --namespace "$AGENTGATEWAY_NS" \
  --from-literal=Authorization="${GEMINI_API_KEY}" \
  --dry-run=client -o yaml | kapply -f -
info "Secret gemini-secret (agentgateway-system) застосовано"

kubectl create secret generic anthropic-secret \
  --namespace "$AGENTGATEWAY_NS" \
  --from-literal=Authorization="${ANTHROPIC_API_KEY:-placeholder}" \
  --dry-run=client -o yaml | kapply -f -
info "Secret anthropic-secret (agentgateway-system) застосовано"

kubectl create secret generic openai-secret \
  --namespace "$AGENTGATEWAY_NS" \
  --from-literal=Authorization="${OPENAI_API_KEY:-placeholder}" \
  --dry-run=client -o yaml | kapply -f -
info "Secret openai-secret (agentgateway-system) застосовано"

# ── 5. Gateway + Backends + HTTPRoute ─────────────────────────────────────────
step "5. Деплой Gateway, AgentgatewayBackends та HTTPRoute"
kapply -f "$K8S_DIR/agentgateway/gateway.yaml"
info "Gateway, Backends та HTTPRoute застосовано"

# ── 6. kagent (minimal профіль) ───────────────────────────────────────────────
step "6. Встановлення kagent у кластер"
# --profile minimal: тільки kagent-api + kagent-controller (без demo агентів)
# --profile demo (~10 агентів) перевантажує kine/SQLite на single-node k3s
# Helm install з вимкненими demo агентами (уникаємо перевантаження kine/SQLite)
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
info "kagent core встановлено (без demo агентів)"

# Чекаємо поки kagent-controller стане Ready (kagent-api → kagent-controller у v0.7+)
info "Очікування kagent-controller..."
kubectl wait --for=condition=Available deployment/kagent-controller \
  -n "$KAGENT_NAMESPACE" --timeout=120s 2>/dev/null \
  || warn "kagent-controller ще не Ready — перевірте: kubectl get pods -n $KAGENT_NAMESPACE"

# ── 7. kagent ModelConfig + Agent ────────────────────────────────────────────
step "7. Налаштування kagent: ModelConfig та Agent"

# Secret для kagent namespace (kagent → agentgateway authentication)
kubectl create secret generic gemini-secret \
  --namespace "$KAGENT_NAMESPACE" \
  --from-literal=Authorization="${GEMINI_API_KEY}" \
  --dry-run=client -o yaml | kapply -f -
info "Secret gemini-secret (kagent) застосовано"

kapply -f "$K8S_DIR/kagent/kagent-model.yaml"
info "ModelConfig agentgateway-gemini застосовано"

kapply -f "$K8S_DIR/kagent/kagent-agent.yaml"
info "Agent k8s-agentgateway-agent застосовано"

# ── 8. Ingress (Traefik) ──────────────────────────────────────────────────────
step "8. Ingress для kagent-ui та agentgateway-proxy"
kapply -f "$K8S_DIR/ingress.yaml"
info "Ingress застосовано"

# /etc/hosts (якщо ще немає)
if ! grep -q "aire2026.local" /etc/hosts 2>/dev/null; then
  warn "Додайте в /etc/hosts:"
  warn "  echo '192.168.64.4  kagent.aire2026.local api.aire2026.local' | sudo tee -a /etc/hosts"
fi

# ── 9. Статус ─────────────────────────────────────────────────────────────────
step "9. Статус деплойменту"
echo ""
info "Pods у $AGENTGATEWAY_NS:"
kubectl get pods -n "$AGENTGATEWAY_NS"
echo ""
info "Pods у $KAGENT_NAMESPACE:"
kubectl get pods -n "$KAGENT_NAMESPACE"
echo ""
info "Gateway:"
kubectl get gateway agentgateway-proxy -n "$AGENTGATEWAY_NS" 2>/dev/null || true
echo ""
info "ModelConfig та Agents:"
kubectl get modelconfig,agents -n "$KAGENT_NAMESPACE" 2>/dev/null || true

echo ""
echo -e "${GREEN}✓ Деплой завершено!${NC}"
echo ""
echo "  ┌─────────────────────────────────────────────────────────────┐"
echo "  │  Доступ без port-forward (потрібен рядок у /etc/hosts):    │"
echo "  │                                                             │"
echo "  │  kagent UI:      http://kagent.aire2026.local              │"
echo "  │  agentgateway:   http://api.aire2026.local                  │"
echo "  │                                                             │"
echo "  │  sudo tee -a /etc/hosts <<< \\                              │"
echo "  │    '192.168.64.4 kagent.aire2026.local api.aire2026.local'  │"
echo "  └─────────────────────────────────────────────────────────────┘"
echo ""
echo "  Тест API:"
echo "    curl -s http://api.aire2026.local/v1/chat/completions \\"
echo "      -H 'Content-Type: application/json' \\"
echo "      -d '{\"model\":\"gemini-2.5-flash\",\"messages\":[{\"role\":\"user\",\"content\":\"ping\"}]}'"
