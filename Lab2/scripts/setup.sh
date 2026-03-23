#!/bin/bash
set -euo pipefail

LOG=/tmp/setup.log
exec > >(tee -a "$LOG") 2>&1

log() { echo "[$(date '+%H:%M:%S')] $*"; }

log "=== k8sdiy-env setup start ==="

# Install OpenTofu
log "Installing OpenTofu..."
curl -fsSL https://get.opentofu.org/install-opentofu.sh | sh -s -- --install-method standalone
log "OpenTofu installed"

# Install K9s
log "Installing K9s..."
curl -sS https://webi.sh/k9s | sh
log "K9s installed"

# Add aliases to bashrc
cat >> ~/.bashrc <<'EOF'

# k8sdiy-env aliases
alias kk="EDITOR='code --wait' k9s"
alias tf=tofu
alias k=kubectl
EOF

EXPECTED_CONTEXT="${KUBE_CONTEXT:-rancher-desktop}"

log "Checking Kubernetes context..."
CURRENT_CONTEXT=$(kubectl config current-context 2>/dev/null || true)
if [ -z "$CURRENT_CONTEXT" ]; then
  log "ERROR: kubectl context is not configured. Enable Kubernetes in Rancher Desktop first."
  exit 1
fi

if [ "$CURRENT_CONTEXT" != "$EXPECTED_CONTEXT" ]; then
  log "ERROR: current context is '$CURRENT_CONTEXT', expected '$EXPECTED_CONTEXT'."
  log "Run: kubectl config use-context $EXPECTED_CONTEXT"
  exit 1
fi

if ! kubectl cluster-info >/dev/null 2>&1; then
  log "ERROR: Kubernetes API is not reachable for context '$EXPECTED_CONTEXT'."
  exit 1
fi
log "Kubernetes context is ready: $EXPECTED_CONTEXT"

# Initialize Tofu
log "Running tofu init..."
cd bootstrap
tofu init
log "tofu init done"

log "Running tofu apply..."
tofu apply -auto-approve
log "tofu apply done"

export KUBECONFIG=~/.kube/config

cd ..

log "=== setup complete ==="
