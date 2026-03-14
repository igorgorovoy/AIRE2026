#!/usr/bin/env bash
# Lab1 medium: agentgateway + kagent у Kubernetes (Helm deployment)
# Документація:
#   agentgateway k8s: https://agentgateway.dev/docs/kubernetes/latest/quickstart/install
#   kagent:           https://kagent.dev/docs/kagent/getting-started/quickstart

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
kubectl create namespace "$AGENTGATEWAY_NS" --dry-run=client -o yaml | kubectl apply -f -

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

# ── 4. Secret з API ключами ───────────────────────────────────────────────────
step "4. Створення Secrets для кожного LLM провайдера"
# AgentgatewayBackend очікує Secret з ключем "Authorization" = значення API ключа
kubectl create secret generic gemini-secret \
  --namespace "$AGENTGATEWAY_NS" \
  --from-literal=Authorization="${GEMINI_API_KEY}" \
  --dry-run=client -o yaml | kubectl apply -f -
info "Secret gemini-secret застосовано"

kubectl create secret generic anthropic-secret \
  --namespace "$AGENTGATEWAY_NS" \
  --from-literal=Authorization="${ANTHROPIC_API_KEY:-placeholder}" \
  --dry-run=client -o yaml | kubectl apply -f -
info "Secret anthropic-secret застосовано"

kubectl create secret generic openai-secret \
  --namespace "$AGENTGATEWAY_NS" \
  --from-literal=Authorization="${OPENAI_API_KEY:-placeholder}" \
  --dry-run=client -o yaml | kubectl apply -f -
info "Secret openai-secret застосовано"

# ── 5. Gateway + Backends + HTTPRoute ─────────────────────────────────────────
step "5. Деплой Gateway, AgentgatewayBackends та HTTPRoute"
kubectl apply -f "$K8S_DIR/agentgateway/gateway.yaml"
info "Gateway, Backends та HTTPRoute застосовано"

# ── 6. kagent ─────────────────────────────────────────────────────────────────
step "6. Встановлення kagent у кластер"
kagent install --profile demo
info "kagent встановлено (profile: demo)"

# ── 7. kagent ModelConfig + Agent ────────────────────────────────────────────
step "7. Налаштування kagent: ModelConfig та Agent"
kubectl create namespace "$KAGENT_NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

kubectl create secret generic gemini-secret \
  --namespace "$KAGENT_NAMESPACE" \
  --from-literal=Authorization="${GEMINI_API_KEY}" \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl apply -f "$K8S_DIR/kagent/kagent-model.yaml"
kubectl apply -f "$K8S_DIR/kagent/kagent-agent.yaml"
info "ModelConfig та Agent застосовано"

# ── 8. Port-forward та перевірка ─────────────────────────────────────────────
step "8. Статус та доступ"
echo ""
info "Pods у $AGENTGATEWAY_NS:"
kubectl get pods -n "$AGENTGATEWAY_NS"
echo ""
info "Gateway:"
kubectl get gateway agentgateway-proxy -n "$AGENTGATEWAY_NS" 2>/dev/null || true
echo ""

cat <<'EOF'

─────────────────────────────────────────────────────────
  Для тестування agentgateway (port-forward):
    kubectl port-forward deployment/agentgateway-proxy \
      -n agentgateway-system 8080:8080

  Тестовий запит (Gemini, у другому терміналі):
    curl localhost:8080/v1/chat/completions \
      -H "Content-Type: application/json" \
      -d '{"model":"gemini-2.5-flash","messages":[{"role":"user","content":"Привіт!"}]}'

  Тестовий запит (Anthropic):
    curl localhost:8080/v1/chat/completions \
      -H "Content-Type: application/json" \
      -H "x-provider: anthropic" \
      -d '{"model":"claude-3-5-haiku-20241022","messages":[{"role":"user","content":"Привіт!"}]}'

  kagent dashboard:
    kagent dashboard

  kagent invoke (helm-agent):
    kagent invoke -t "What Helm charts are in my cluster?" --agent helm-agent

  Видалення всього:
    helm uninstall agentgateway agentgateway-crds -n agentgateway-system
    kagent uninstall
─────────────────────────────────────────────────────────

EOF
