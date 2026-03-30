#!/usr/bin/env bash
# Flux CD CLI wrapper: prefers the Homebrew binary (opt/flux) so we do NOT pick up
# an outdated `flux` from PATH (~/.local/bin, etc.).
#
# Explicit path: FLUX_BIN=/path/to/flux bash scripts/flux.sh version

set -euo pipefail

if [[ -n "${FLUX_BIN:-}" && -x "${FLUX_BIN}" ]]; then
  exec "${FLUX_BIN}" "$@"
fi

candidates=()

if command -v brew >/dev/null 2>&1; then
  hb="$(brew --prefix 2>/dev/null || true)"
  # Typical Flux CD location after `brew install fluxcd/tap/flux`
  [[ -n "$hb" ]] && candidates+=("${hb}/opt/flux/bin/flux")
  for formula in flux "fluxcd/tap/flux"; do
    pfx="$(brew --prefix "${formula}" 2>/dev/null || true)"
    [[ -n "$pfx" ]] && candidates+=("${pfx}/bin/flux")
  done
fi

# Fallback without brew (common prefixes)
candidates+=(
  /opt/homebrew/opt/flux/bin/flux
  /usr/local/opt/flux/bin/flux
  /opt/homebrew/bin/flux
  /usr/local/bin/flux
)

# No declare -A (bash 3.2 on macOS): dedupe candidate paths
_tried=""
for c in "${candidates[@]}"; do
  [[ -z "$c" || ! -x "$c" ]] && continue
  case " ${_tried} " in *" ${c} "*) continue ;; esac
  _tried="${_tried} ${c} "
  exec "$c" "$@"
done

echo "flux CLI (Flux CD) not found or not installed via Homebrew." >&2
echo "Install: brew install fluxcd/tap/flux" >&2
echo "Then: export FLUX_BIN=\"\$(brew --prefix)/opt/flux/bin/flux\"" >&2
exit 1
