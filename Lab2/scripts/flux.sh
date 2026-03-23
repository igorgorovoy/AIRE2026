#!/usr/bin/env bash
# Flux CD CLI wrapper: використовує лише бінарник з Homebrew (opt/flux),
# щоб НЕ підхоплювати застарілий `flux` з PATH (~/.local/bin тощо).
#
# Явний шлях: FLUX_BIN=/шлях/до/flux bash scripts/flux.sh version

set -euo pipefail

if [[ -n "${FLUX_BIN:-}" && -x "${FLUX_BIN}" ]]; then
  exec "${FLUX_BIN}" "$@"
fi

candidates=()

if command -v brew >/dev/null 2>&1; then
  hb="$(brew --prefix 2>/dev/null || true)"
  # Типове місце Flux CD після `brew install fluxcd/tap/flux`
  [[ -n "$hb" ]] && candidates+=("${hb}/opt/flux/bin/flux")
  for formula in flux "fluxcd/tap/flux"; do
    pfx="$(brew --prefix "${formula}" 2>/dev/null || true)"
    [[ -n "$pfx" ]] && candidates+=("${pfx}/bin/flux")
  done
fi

# Фолбек без brew (типові префікси)
candidates+=(
  /opt/homebrew/opt/flux/bin/flux
  /usr/local/opt/flux/bin/flux
  /opt/homebrew/bin/flux
  /usr/local/bin/flux
)

# Без declare -A (bash 3.2 на macOS): уникаємо повторів шляху
_tried=""
for c in "${candidates[@]}"; do
  [[ -z "$c" || ! -x "$c" ]] && continue
  case " ${_tried} " in *" ${c} "*) continue ;; esac
  _tried="${_tried} ${c} "
  exec "$c" "$@"
done

echo "flux CLI (Flux CD) не знайдено або не встановлено через Homebrew." >&2
echo "Встановлення: brew install fluxcd/tap/flux" >&2
echo "Потім: export FLUX_BIN=\"\$(brew --prefix)/opt/flux/bin/flux\"" >&2
exit 1
