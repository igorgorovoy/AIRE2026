#!/usr/bin/env bash
# Build Docker images for the three Lab3 MCP servers.
#
# Usage:
#   ./mcp-servers/build.sh                          # ALZ as sibling directory
#   ./mcp-servers/build.sh /path/to/agentic-ai-landing-zone
#   ALZ=/path/to/alz ./mcp-servers/build.sh
#
# Options:
#   --load       Load images into Rancher Desktop VM after build
#   --no-cache   Pass --no-cache to docker build
#   --push       Push images (set REGISTRY env or image prefix)
#
# Environment:
#   ALZ          Path to agentic-ai-landing-zone root
#   REGISTRY     Registry prefix (e.g. ghcr.io/username); empty = local only
#   TAG          Image tag (default: latest)
set -euo pipefail

# ── Colors ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${CYAN}▶ $*${RESET}"; }
success() { echo -e "${GREEN}✔ $*${RESET}"; }
warn()    { echo -e "${YELLOW}⚠ $*${RESET}"; }
error()   { echo -e "${RED}✘ $*${RESET}" >&2; exit 1; }

# ── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAB3_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SRC_DIR="$SCRIPT_DIR/src"

# ── Arguments ────────────────────────────────────────────────────────────────
OPT_LOAD=false
OPT_NO_CACHE=false
OPT_PUSH=false
ALZ_ARG=""

for arg in "$@"; do
  case "$arg" in
    --load)     OPT_LOAD=true ;;
    --no-cache) OPT_NO_CACHE=true ;;
    --push)     OPT_PUSH=true ;;
    --*)        warn "Unknown option: $arg" ;;
    *)          ALZ_ARG="$arg" ;;
  esac
done

# ── ALZ path ─────────────────────────────────────────────────────────────────
ALZ="${ALZ_ARG:-${ALZ:-}}"
if [[ -z "$ALZ" ]]; then
  for relative in "../../agentic-ai-landing-zone" "../agentic-ai-landing-zone"; do
    CANDIDATE="$(cd "$LAB3_DIR/$relative" 2>/dev/null && pwd || true)"
    if [[ -d "$CANDIDATE" && -f "$CANDIDATE/requirements.txt" ]]; then
      ALZ="$CANDIDATE"
      info "ALZ auto-detected: $ALZ"
      break
    fi
  done
  if [[ -z "$ALZ" ]]; then
    error "agentic-ai-landing-zone not found.\nPass path as argument:\n  $0 /path/to/agentic-ai-landing-zone"
  fi
fi
[[ -d "$ALZ" ]] || error "ALZ does not exist: $ALZ"
[[ -f "$ALZ/requirements.txt" ]] || error "ALZ path looks wrong (no requirements.txt): $ALZ"

# ── Tag and registry ───────────────────────────────────────────────────────────
TAG="${TAG:-latest}"
REGISTRY="${REGISTRY:-}"
[[ -n "$REGISTRY" ]] && REGISTRY="${REGISTRY%/}/"

KB_IMAGE="${REGISTRY}mcp-knowledge-base:${TAG}"
LC_IMAGE="${REGISTRY}mcp-lesson-credits:${TAG}"
TK_IMAGE="${REGISTRY}mcp-tasks:${TAG}"

CACHE_FLAG=""
$OPT_NO_CACHE && CACHE_FLAG="--no-cache"

# ── Build helper ───────────────────────────────────────────────────────────────
build_image() {
  local name="$1" image="$2" context="$3" dockerfile="$4"
  echo ""
  echo -e "${BOLD}━━━ $name → $image ━━━${RESET}"
  local start; start=$(date +%s)

  if docker build $CACHE_FLAG -t "$image" -f "$dockerfile" "$context"; then
    local elapsed=$(( $(date +%s) - start ))
    success "$name built in ${elapsed}s"
  else
    error "Build failed: $name"
  fi
}

load_to_rancher() {
  local image="$1"
  info "Loading $image into Rancher Desktop VM docker..."
  docker save "$image" | rdctl shell -- sudo docker load \
    && success "Loaded: $image" \
    || warn "rdctl load failed for $image (check manually)"
}

push_image() {
  local image="$1"
  info "Pushing $image..."
  docker push "$image" && success "Pushed: $image" || warn "Push failed: $image"
}

# ── Header ─────────────────────────────────────────────────────────────────────
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

# ── Build images ─────────────────────────────────────────────────────────────
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

# ── Summary ────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}━━━ Built images ━━━${RESET}"
for img in "$KB_IMAGE" "$LC_IMAGE" "$TK_IMAGE"; do
  echo -e "  ${GREEN}✔${RESET} $img"
done

# ── Rancher Desktop load ───────────────────────────────────────────────────────
if $OPT_LOAD; then
  echo ""
  echo -e "${BOLD}━━━ Loading into Rancher Desktop ━━━${RESET}"
  command -v rdctl &>/dev/null || error "rdctl not found. Install Rancher Desktop."
  for img in "$KB_IMAGE" "$LC_IMAGE" "$TK_IMAGE"; do
    load_to_rancher "$img"
  done
fi

# ── Push ───────────────────────────────────────────────────────────────────────
if $OPT_PUSH; then
  echo ""
  echo -e "${BOLD}━━━ Push to registry ━━━${RESET}"
  [[ -z "$REGISTRY" ]] && error "REGISTRY not set. Example: REGISTRY=ghcr.io/username ./mcp-servers/build.sh --push"
  for img in "$KB_IMAGE" "$LC_IMAGE" "$TK_IMAGE"; do
    push_image "$img"
  done
fi

echo ""
success "Done!"
