#!/usr/bin/env bash
# Збірка Docker-образів для A2A-агентів Lab4.
#
# Використання:
#   ./a2a-agents/build.sh                # збірка обох образів
#   ./a2a-agents/build.sh --load         # + завантажити у Rancher Desktop VM
#   ./a2a-agents/build.sh --no-cache     # без кешу
#
# Змінні середовища:
#   REGISTRY     Префікс реєстру (напр. ghcr.io/username); порожньо — локально
#   TAG          Тег образу (default: latest)
set -euo pipefail

# ── Кольори ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${CYAN}▶ $*${RESET}"; }
success() { echo -e "${GREEN}✔ $*${RESET}"; }
warn()    { echo -e "${YELLOW}⚠ $*${RESET}"; }
error()   { echo -e "${RED}✘ $*${RESET}" >&2; exit 1; }

# ── Шляхи ────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Аргументи ────────────────────────────────────────────────────────────────
OPT_LOAD=false
OPT_NO_CACHE=false
OPT_PUSH=false

for arg in "$@"; do
  case "$arg" in
    --load)     OPT_LOAD=true ;;
    --no-cache) OPT_NO_CACHE=true ;;
    --push)     OPT_PUSH=true ;;
    --*)        warn "Невідома опція: $arg" ;;
  esac
done

# ── Тег та реєстр ────────────────────────────────────────────────────────────
TAG="${TAG:-latest}"
REGISTRY="${REGISTRY:-}"
[[ -n "$REGISTRY" ]] && REGISTRY="${REGISTRY%/}/"

ASSISTANT_IMAGE="${REGISTRY}a2a-assistant-agent:${TAG}"
ORCHESTRATOR_IMAGE="${REGISTRY}a2a-orchestrator-agent:${TAG}"

CACHE_FLAG=""
$OPT_NO_CACHE && CACHE_FLAG="--no-cache"

# ── Функція збірки ───────────────────────────────────────────────────────────
build_image() {
  local name="$1" image="$2" dockerfile="$3"
  echo ""
  echo -e "${BOLD}━━━ $name → $image ━━━${RESET}"
  local start; start=$(date +%s)

  if docker build $CACHE_FLAG -t "$image" -f "$SCRIPT_DIR/$dockerfile" "$SCRIPT_DIR"; then
    local elapsed=$(( $(date +%s) - start ))
    success "$name зібрано за ${elapsed}s"
  else
    error "Збірка $name провалилась"
  fi
}

load_to_rancher() {
  local image="$1"
  info "Передаю $image у Rancher Desktop VM docker..."
  # Pipe напряму: docker save → rdctl shell → sudo docker load (без тимчасового файлу)
  docker save "$image" | rdctl shell -- sudo docker load \
    && success "Завантажено: $image" \
    || warn "rdctl load не вдався для $image (перевірте вручну)"
}

push_image() {
  local image="$1"
  info "Пушу $image..."
  docker push "$image" && success "Запушено: $image" || warn "Push не вдався: $image"
}

# ── Заголовок ────────────────────────────────────────────────────────────────
echo -e "${BOLD}"
echo "╔══════════════════════════════════════════╗"
echo "║   Lab4 — A2A Agents Image Build          ║"
echo "╚══════════════════════════════════════════╝"
echo -e "${RESET}"
echo "  DIR  : $SCRIPT_DIR"
echo "  TAG  : $TAG"
[[ -n "$REGISTRY" ]] && echo "  REG  : $REGISTRY"
$OPT_NO_CACHE && echo "  MODE : --no-cache"
$OPT_LOAD && echo "  LOAD : Rancher Desktop"
echo ""

# ── Збірка образів ───────────────────────────────────────────────────────────
build_image "assistant-agent"    "$ASSISTANT_IMAGE"    "Dockerfile.assistant"
build_image "orchestrator-agent" "$ORCHESTRATOR_IMAGE" "Dockerfile.orchestrator"

# ── Підсумок ─────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}━━━ Зібрані образи ━━━${RESET}"
for img in "$ASSISTANT_IMAGE" "$ORCHESTRATOR_IMAGE"; do
  echo -e "  ${GREEN}✔${RESET} $img"
done

# ── Rancher Desktop load ─────────────────────────────────────────────────────
if $OPT_LOAD; then
  echo ""
  echo -e "${BOLD}━━━ Завантаження в Rancher Desktop ━━━${RESET}"
  command -v rdctl &>/dev/null || error "rdctl не знайдено. Встановіть Rancher Desktop."
  for img in "$ASSISTANT_IMAGE" "$ORCHESTRATOR_IMAGE"; do
    load_to_rancher "$img"
  done
fi

# ── Push ─────────────────────────────────────────────────────────────────────
if $OPT_PUSH; then
  echo ""
  echo -e "${BOLD}━━━ Push до реєстру ━━━${RESET}"
  [[ -z "$REGISTRY" ]] && error "REGISTRY не задано. Приклад: REGISTRY=ghcr.io/username ./build.sh --push"
  for img in "$ASSISTANT_IMAGE" "$ORCHESTRATOR_IMAGE"; do
    push_image "$img"
  done
fi

echo ""
success "Готово!"
