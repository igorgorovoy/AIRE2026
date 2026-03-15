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
echo ""
echo "=== 2. Конфігурація config.yaml ==="
if [[ ! -f "$CONFIG" ]]; then
  echo "Помилка: $CONFIG не знайдено."; exit 1
fi
echo "Використовується: $CONFIG"
echo ""

echo "=== 3. API ключі провайдерів ==="
MISSING=0

if [[ -z "${GEMINI_API_KEY:-}" ]]; then
  echo "  [!] GEMINI_API_KEY не встановлено — Gemini backend буде недоступний"
  echo "      Отримати: https://aistudio.google.com/api-keys"
  MISSING=1
else
  echo "  [+] GEMINI_API_KEY    встановлено (${#GEMINI_API_KEY} символів)"
fi

if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
  echo "  [ ] ANTHROPIC_API_KEY не встановлено — Anthropic backend буде недоступний"
  echo "      Отримати: https://console.anthropic.com/settings/keys"
else
  echo "  [+] ANTHROPIC_API_KEY встановлено (${#ANTHROPIC_API_KEY} символів)"
fi

if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "  [ ] OPENAI_API_KEY    не встановлено — OpenAI backend буде недоступний"
  echo "      Отримати: https://platform.openai.com/api-keys"
else
  echo "  [+] OPENAI_API_KEY    встановлено (${#OPENAI_API_KEY} символів)"
fi

if [[ "$MISSING" -eq 1 ]]; then
  echo ""
  echo "  Необхідний мінімум: GEMINI_API_KEY (маршрут за замовчуванням)."
  echo "  Встановіть і перезапустіть: export GEMINI_API_KEY=your-key && ./run.sh"
  exit 1
fi

echo ""
echo "=== 4. Запуск gateway ==="
echo "  • API:  http://localhost:3000"
echo "  • UI:   http://localhost:15000/ui/"
echo "  • Routing: x-provider: gemini | anthropic | openai"
echo "  • Зупинити: Ctrl+C"
echo ""
agentgateway -f "$CONFIG"
##
