#!/usr/bin/env bash
# Build Docker images for Lab4 A2A agents.
#
# Usage:
#   ./a2a-agents/build.sh                # build both images
#   ./a2a-agents/build.sh --load         # also load into Rancher Desktop VM
#   ./a2a-agents/build.sh --no-cache     # no build cache
#
# Environment:
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
# Dockerfiles COPY Lab4/... and Lab3/... — build context must be repo root.
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# agentic-ai-landing-zone: agents/, core/, requirements.txt needed by lesson-credits/tasks MCP.
ALZ="${ALZ:-}"
if [[ -z "$ALZ" ]]; then
  for candidate in "$REPO_ROOT/../agentic-ai-landing-zone" "$REPO_ROOT/../../agentic-ai-landing-zone"; do
    if [[ -d "$candidate/agents" && -d "$candidate/core" ]]; then
      ALZ="$(cd "$candidate" && pwd)"
      break
    fi
  done
fi

# ── Arguments ────────────────────────────────────────────────────────────────
OPT_LOAD=false
OPT_NO_CACHE=false
OPT_PUSH=false

for arg in "$@"; do
  case "$arg" in
    --load)     OPT_LOAD=true ;;
    --no-cache) OPT_NO_CACHE=true ;;
    --push)     OPT_PUSH=true ;;
    --*)        warn "Unknown option: $arg" ;;
  esac
done

# ── Tag and registry ─────────────────────────────────────────────────────────
TAG="${TAG:-latest}"
REGISTRY="${REGISTRY:-}"
[[ -n "$REGISTRY" ]] && REGISTRY="${REGISTRY%/}/"

ASSISTANT_IMAGE="${REGISTRY}a2a-assistant-agent:${TAG}"
ORCHESTRATOR_IMAGE="${REGISTRY}a2a-orchestrator-agent:${TAG}"

CACHE_FLAG=""
$OPT_NO_CACHE && CACHE_FLAG="--no-cache"

# ── Build helper ───────────────────────────────────────────────────────────────
build_image() {
  local name="$1" image="$2" dockerfile="$3"
  echo ""
  echo -e "${BOLD}━━━ $name → $image ━━━${RESET}"
  local start; start=$(date +%s)

  if docker build $CACHE_FLAG -t "$image" -f "$SCRIPT_DIR/$dockerfile" "$REPO_ROOT"; then
    local elapsed=$(( $(date +%s) - start ))
    success "$name built in ${elapsed}s"
  else
    error "Build failed: $name"
  fi
}

load_to_rancher() {
  local image="$1"
  info "Loading $image into Rancher Desktop VM docker..."
  # Pipe: docker save → rdctl shell → sudo docker load (no temp file)
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
echo "║   Lab4 — A2A Agents Image Build          ║"
echo "╚══════════════════════════════════════════╝"
echo -e "${RESET}"
echo "  DIR  : $SCRIPT_DIR"
echo "  CTX  : $REPO_ROOT (repo root for Lab4 + Lab3 COPY paths)"
echo "  TAG  : $TAG"
[[ -n "$REGISTRY" ]] && echo "  REG  : $REGISTRY"
$OPT_NO_CACHE && echo "  MODE : --no-cache"
$OPT_LOAD && echo "  LOAD : Rancher Desktop"
echo ""

# ── Stage ALZ deps for assistant image ────────────────────────────────────────
BUILD_ALZ="$REPO_ROOT/.build-alz"
cleanup_alz() { rm -rf "$BUILD_ALZ"; }
trap cleanup_alz EXIT

if [[ -n "$ALZ" && -d "$ALZ/agents" ]]; then
  info "Staging ALZ deps from $ALZ → $BUILD_ALZ"
  rm -rf "$BUILD_ALZ"
  mkdir -p "$BUILD_ALZ"
  cp -r "$ALZ/agents" "$BUILD_ALZ/agents"
  cp -r "$ALZ/core" "$BUILD_ALZ/core"
  cp "$ALZ/requirements.txt" "$BUILD_ALZ/requirements.txt"
  success "ALZ deps staged"
else
  warn "agentic-ai-landing-zone not found (ALZ=$ALZ). Lesson-credits and tasks MCP will fail at runtime."
  warn "Set ALZ=/path/to/agentic-ai-landing-zone or place it next to AIRE2026."
  rm -rf "$BUILD_ALZ"
  mkdir -p "$BUILD_ALZ/agents" "$BUILD_ALZ/core"
  echo "# ALZ not available" > "$BUILD_ALZ/requirements.txt"
  touch "$BUILD_ALZ/agents/__init__.py" "$BUILD_ALZ/core/__init__.py"
fi

# ── Build images ─────────────────────────────────────────────────────────────
build_image "assistant-agent"    "$ASSISTANT_IMAGE"    "Dockerfile.assistant"
build_image "orchestrator-agent" "$ORCHESTRATOR_IMAGE" "Dockerfile.orchestrator"

# ── Summary ────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}━━━ Built images ━━━${RESET}"
for img in "$ASSISTANT_IMAGE" "$ORCHESTRATOR_IMAGE"; do
  echo -e "  ${GREEN}✔${RESET} $img"
done

# ── Rancher Desktop load ───────────────────────────────────────────────────────
if $OPT_LOAD; then
  echo ""
  echo -e "${BOLD}━━━ Loading into Rancher Desktop ━━━${RESET}"
  command -v rdctl &>/dev/null || error "rdctl not found. Install Rancher Desktop."
  for img in "$ASSISTANT_IMAGE" "$ORCHESTRATOR_IMAGE"; do
    load_to_rancher "$img"
  done
fi

# ── Push ───────────────────────────────────────────────────────────────────────
if $OPT_PUSH; then
  echo ""
  echo -e "${BOLD}━━━ Push to registry ━━━${RESET}"
  [[ -z "$REGISTRY" ]] && error "REGISTRY not set. Example: REGISTRY=ghcr.io/username ./build.sh --push"
  for img in "$ASSISTANT_IMAGE" "$ORCHESTRATOR_IMAGE"; do
    push_image "$img"
  done
fi

echo ""
success "Done!"
