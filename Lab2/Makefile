help:
	@echo "Available targets:"
	@echo "  run    - Bootstrap the full environment (install tools, provision cluster)"
	@echo "  down   - Destroy the cluster and all resources"
	@echo "  push   - Bump patch version, tag, and push to trigger CI"
	@echo "  tools  - Install necessary tools only"
	@echo "  tofu   - Initialize OpenTofu"
	@echo "  apply  - Apply OpenTofu configuration"
	@echo "  flux-version   - Show Flux CD CLI version (via scripts/flux.sh)"
	@echo "  flux-reconcile - Reconcile releases-crds + releases Kustomizations"
	@echo "  flux-ui        - Port-forward Flux Status Web UI (http://127.0.0.1:9080)"

run:
	@bash scripts/setup.sh

tools:
	@curl -fsSL https://get.opentofu.org/install-opentofu.sh | sh -s -- --install-method standalone
	@curl -sS https://webi.sh/k9s | bash

tofu:
	@cd bootstrap && tofu init

apply:
	@cd bootstrap && tofu apply -auto-approve

flux-version:
	@bash scripts/flux.sh version

flux-reconcile:
	@bash scripts/flux.sh reconcile kustomization releases-crds -n flux-system --with-source
	@bash scripts/flux.sh reconcile kustomization releases -n flux-system --with-source
	@bash scripts/flux.sh get all

flux-ui:
	@echo "Flux Status Web UI → http://127.0.0.1:9080/  (Ctrl+C to stop)"
	kubectl -n flux-system port-forward svc/flux-operator 9080:9080

down:
	@cd bootstrap && tofu destroy -auto-approve

push:
	@git fetch origin --tags --force
	$(eval TAG=$(shell git tag --list 'v*' | sort -V | tail -1 | sed 's/^v//' || echo "0.0.0"))
	$(eval MAJOR=$(shell echo $(TAG) | cut -d. -f1))
	$(eval MINOR=$(shell echo $(TAG) | cut -d. -f2))
	$(eval PATCH=$(shell echo $(TAG) | cut -d. -f3))
	$(eval NEW_TAG=v$(MAJOR).$(MINOR).$(shell echo $$(($(PATCH)+1))))
	@git tag $(NEW_TAG)
	@git push origin main $(NEW_TAG)
	@echo "Tagged and pushed $(NEW_TAG)"
