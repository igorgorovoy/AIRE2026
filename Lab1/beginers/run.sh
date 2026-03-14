#!/usr/bin/env bash
# Lab1 beginners: встановлення agentgateway, налаштування Gemini, запуск gateway та перевірка доступу
# Документація: https://agentgateway.dev/docs/standalone/latest/

set -e
LAB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$LAB_DIR"
CONFIG="$LAB_DIR/config.yaml"
AGENTGATEWAY_VERSION="${AGENTGATEWAY_VERSION:-v1.0.0-rc.2}"

echo "=== 1. Встановлення agentgateway (binary) ==="
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
  # darwin має тільки arm64-реліз; на Linux визначаємо реально
  if [[ "$OS" == "darwin" ]]; then
    ARCH="arm64"
  else
    case "$(uname -m)" in
      x86_64) ARCH="amd64" ;;
      aarch64|arm64) ARCH="arm64" ;;
      *) echo "Непідтримана архітектура: $(uname -m)"; exit 1 ;;
    esac
  fi
  DIST="agentgateway-${OS}-${ARCH}"
  URL="https://github.com/agentgateway/agentgateway/releases/download/${AGENTGATEWAY_VERSION}/${DIST}"
  echo "Завантаження $URL ..."
  # -f: завершити з помилкою при HTTP 4xx/5xx (не зберігати HTML-сторінку помилки)
  curl -sSLf -o "/tmp/${DIST}" "$URL" \
    || { echo "Помилка: не вдалось завантажити $URL"; exit 1; }
  chmod +x "/tmp/${DIST}"
  if [[ -w /usr/local/bin ]]; then
    cp "/tmp/${DIST}" /usr/local/bin/agentgateway
  else
    echo "Потрібні права для копіювання в /usr/local/bin:"
    sudo cp "/tmp/${DIST}" /usr/local/bin/agentgateway
  fi
  echo "agentgateway встановлено в /usr/local/bin/agentgateway"
else
  echo "agentgateway вже встановлено: $(agentgateway --version 2>/dev/null | head -1)"
fi
echo "=== 3. Конфігурація config.yaml ==="
if [[ ! -f "$CONFIG" ]]; then
  echo "Помилка: $CONFIG не знайдено."; exit 1
fi


echo "=== 4. API ключ Gemini ==="
if [[ -z "${GEMINI_API_KEY:-}" ]]; then
  echo "Встановіть GEMINI_API_KEY з https://aistudio.google.com/api-keys"
  echo "  export GEMINI_API_KEY=your-api-key"
  echo "Потім перезапустіть цей скрипт."
  exit 1
fi


agentgateway -f "$CONFIG"
