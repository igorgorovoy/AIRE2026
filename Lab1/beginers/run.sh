#!/usr/bin/env bash
# Lab1 beginners: install agentgateway, configure Gemini, run gateway, verify access
# Docs: https://agentgateway.dev/docs/standalone/latest/

set -e
LAB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$LAB_DIR"
CONFIG="$LAB_DIR/config.yaml"
AGENTGATEWAY_VERSION="${AGENTGATEWAY_VERSION:-v1.0.0-rc.2}"

echo "=== 1. Installing agentgateway (binary) ==="
# https://agentgateway.dev/docs/standalone/latest/deployment/binary/
need_install() {
  if ! command -v agentgateway &>/dev/null; then return 0; fi
  local out
  out=$(agentgateway --version 2>/dev/null) || return 0
  if [[ "$out" != *"version"* && "$out" != *"git_revision"* ]]; then return 0; fi
  return 1
}
if need_install; then
  OS=$(uname -s | tr '[:upper:]' '[:lower:]')
  # darwin releases are arm64-only; on Linux pick the real arch
  if [[ "$OS" == "darwin" ]]; then
    ARCH="arm64"
  else
    case "$(uname -m)" in
      x86_64) ARCH="amd64" ;;
      aarch64|arm64) ARCH="arm64" ;;
      *) echo "Unsupported architecture: $(uname -m)"; exit 1 ;;
    esac
  fi
  DIST="agentgateway-${OS}-${ARCH}"
  URL="https://github.com/agentgateway/agentgateway/releases/download/${AGENTGATEWAY_VERSION}/${DIST}"
  echo "Downloading $URL ..."
  # -f: fail on HTTP 4xx/5xx (do not save an HTML error page)
  curl -sSLf -o "/tmp/${DIST}" "$URL" \
    || { echo "Error: failed to download $URL"; exit 1; }
  chmod +x "/tmp/${DIST}"
  if [[ -w /usr/local/bin ]]; then
    cp "/tmp/${DIST}" /usr/local/bin/agentgateway
  else
    echo "sudo required to copy to /usr/local/bin:"
    sudo cp "/tmp/${DIST}" /usr/local/bin/agentgateway
  fi
  echo "agentgateway installed to /usr/local/bin/agentgateway"
else
  echo "agentgateway already installed: $(agentgateway --version 2>/dev/null | head -1)"
fi
echo ""
echo "=== 2. config.yaml ==="
if [[ ! -f "$CONFIG" ]]; then
  echo "Error: $CONFIG not found."; exit 1
fi
echo "Using: $CONFIG"
echo ""

echo "=== 3. Provider API keys ==="
MISSING=0

if [[ -z "${GEMINI_API_KEY:-}" ]]; then
  echo "  [!] GEMINI_API_KEY not set — Gemini backend will be unavailable"
  echo "      Get a key: https://aistudio.google.com/api-keys"
  MISSING=1
else
  echo "  [+] GEMINI_API_KEY    set (${#GEMINI_API_KEY} chars)"
fi

if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
  echo "  [ ] ANTHROPIC_API_KEY not set — Anthropic backend will be unavailable"
  echo "      Get a key: https://console.anthropic.com/settings/keys"
else
  echo "  [+] ANTHROPIC_API_KEY set (${#ANTHROPIC_API_KEY} chars)"
fi

if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "  [ ] OPENAI_API_KEY    not set — OpenAI backend will be unavailable"
  echo "      Get a key: https://platform.openai.com/api-keys"
else
  echo "  [+] OPENAI_API_KEY    set (${#OPENAI_API_KEY} chars)"
fi

if [[ "$MISSING" -eq 1 ]]; then
  echo ""
  echo "  Minimum required: GEMINI_API_KEY (default route)."
  echo "  Set it and re-run: export GEMINI_API_KEY=your-key && ./run.sh"
  exit 1
fi

echo ""
echo "=== 4. Starting gateway ==="
echo "  • API:  http://localhost:3000"
echo "  • UI:   http://localhost:15000/ui/"
echo "  • Routing: x-provider: gemini | anthropic | openai"
echo "  • Stop: Ctrl+C"
echo ""
agentgateway -f "$CONFIG"
