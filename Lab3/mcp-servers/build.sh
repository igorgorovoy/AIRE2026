#!/usr/bin/env bash
# Збірка Docker-образів для трьох MCP-серверів Lab3.
#
# Використання:
#   ./mcp-servers/build.sh                          # ALZ — сусідній каталог
#   ./mcp-servers/build.sh /path/to/agentic-ai-landing-zone
#   ALZ=/path/to/alz ./mcp-servers/build.sh
#
# Опції:
#   --load       Завантажити образи у Rancher Desktop VM після збірки
#   --no-cache   Додати --no-cache до docker build
#   --push       Запушити образи (потрібен REGISTRY env або префікс у назвах)
#
# Змінні середовища:
#   ALZ          Шлях до кореня agentic-ai-landing-zone
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
LAB3_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SRC_DIR="$SCRIPT_DIR/src"

# ── Аргументи ────────────────────────────────────────────────────────────────
OPT_LOAD=false
OPT_NO_CACHE=false
OPT_PUSH=false
ALZ_ARG=""

for arg in "$@"; do
  case "$arg" in
    --load)     OPT_LOAD=true ;;
    --no-cache) OPT_NO_CACHE=true ;;
    --push)     OPT_PUSH=true ;;
    --*)        warn "Невідома опція: $arg" ;;
    *)          ALZ_ARG="$arg" ;;
  esac
done

# ── ALZ path ─────────────────────────────────────────────────────────────────
ALZ="${ALZ_ARG:-${ALZ:-}}"
if [[ -z "$ALZ" ]]; then
  # Шукаємо agentic-ai-landing-zone відносно Lab3:
  #   Lab3 → AIRE2026/Lab3, ALZ → personal/agentic-ai-landing-zone (два рівні вгору)
  for relative in "../../agentic-ai-landing-zone" "../agentic-ai-landing-zone"; do
    CANDIDATE="$(cd "$LAB3_DIR/$relative" 2>/dev/null && pwd || true)"
    if [[ -d "$CANDIDATE" && -f "$CANDIDATE/requirements.txt" ]]; then
      ALZ="$CANDIDATE"
      info "ALZ автовизначено: $ALZ"
      break
    fi
  done
  if [[ -z "$ALZ" ]]; then
    error "Не знайдено agentic-ai-landing-zone.\nПередайте шлях аргументом:\n  $0 /path/to/agentic-ai-landing-zone"
  fi
fi
[[ -d "$ALZ" ]] || error "ALZ не існує: $ALZ"
[[ -f "$ALZ/requirements.txt" ]] || error "Схоже, ALZ вказаний неправильно (немає requirements.txt): $ALZ"

# ── Тег та реєстр ────────────────────────────────────────────────────────────
TAG="${TAG:-latest}"
REGISTRY="${REGISTRY:-}"
[[ -n "$REGISTRY" ]] && REGISTRY="${REGISTRY%/}/"

KB_IMAGE="${REGISTRY}mcp-knowledge-base:${TAG}"
LC_IMAGE="${REGISTRY}mcp-lesson-credits:${TAG}"
TK_IMAGE="${REGISTRY}mcp-tasks:${TAG}"

CACHE_FLAG=""
$OPT_NO_CACHE && CACHE_FLAG="--no-cache"

# ── Функція збірки ───────────────────────────────────────────────────────────
build_image() {
  local name="$1" image="$2" context="$3" dockerfile="$4"
  echo ""
  echo -e "${BOLD}━━━ $name → $image ━━━${RESET}"
  local start; start=$(date +%s)

  if docker build $CACHE_FLAG -t "$image" -f "$dockerfile" "$context"; then
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
echo "║   Lab3 — MCP Servers Image Build         ║"
echo "╚══════════════════════════════════════════╝"
echo -e "${RESET}"
echo "  LAB3 : $LAB3_DIR"
echo "  ALZ  : $ALZ"
echo "  TAG  : $TAG"
[[ -n "$REGISTRY" ]] && echo "  REG  : $REGISTRY"
$OPT_NO_CACHE && echo "  MODE : --no-cache"
$OPT_LOAD && echo "  LOAD : Rancher Desktop"
echo ""

# ── Збірка образів ───────────────────────────────────────────────────────────
build_image \
  "knowledge-base" "$KB_IMAGE" \
  "$SRC_DIR/knowledge-base" \
  "$SRC_DIR/knowledge-base/Dockerfile"

build_image \
  "lesson-credits" "$LC_IMAGE" \
  "$ALZ" \
  "$SRC_DIR/lesson-credits/Dockerfile"

build_image \
  "tasks" "$TK_IMAGE" \
  "$ALZ" \
  "$SRC_DIR/tasks/Dockerfile"

# ── Підсумок ─────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}━━━ Зібрані образи ━━━${RESET}"
for img in "$KB_IMAGE" "$LC_IMAGE" "$TK_IMAGE"; do
  echo -e "  ${GREEN}✔${RESET} $img"
done

# ── Rancher Desktop load ─────────────────────────────────────────────────────
if $OPT_LOAD; then
  echo ""
  echo -e "${BOLD}━━━ Завантаження в Rancher Desktop ━━━${RESET}"
  command -v rdctl &>/dev/null || error "rdctl не знайдено. Встановіть Rancher Desktop."
  for img in "$KB_IMAGE" "$LC_IMAGE" "$TK_IMAGE"; do
    load_to_rancher "$img"
  done
fi

# ── Push ─────────────────────────────────────────────────────────────────────
if $OPT_PUSH; then
  echo ""
  echo -e "${BOLD}━━━ Push до реєстру ━━━${RESET}"
  [[ -z "$REGISTRY" ]] && error "REGISTRY не задано. Приклад: REGISTRY=ghcr.io/username ./mcp-servers/build.sh --push"
  for img in "$KB_IMAGE" "$LC_IMAGE" "$TK_IMAGE"; do
    push_image "$img"
  done
fi

echo ""
success "Готово!"
