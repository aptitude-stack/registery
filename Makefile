.DEFAULT_GOAL := help
SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c

UV ?= UV_CACHE_DIR=.uv-cache uv
PYTHON := $(UV) run python
PYTEST := $(UV) run --extra dev python -m pytest
RUFF := $(UV) run --extra dev ruff
MYPY := $(UV) run --extra dev python -m mypy
COMPOSE := docker compose
COMPOSE_OBS := $(COMPOSE) --profile observability
COMPOSE_DEMO := $(COMPOSE) --profile demo

DOCKER_IMAGE ?= y0ncha/aptitude-registry
DOCKER_TAG ?= latest
DOCKER_IMAGE_REF := $(DOCKER_IMAGE):$(DOCKER_TAG)
DOCKER_PLATFORMS ?= linux/amd64,linux/arm64
DOCKER_BUILDER ?= aptitude-multiarch

APP_BASE_URL ?= http://127.0.0.1:8000
LOKI_URL ?= http://127.0.0.1:3100
PROMETHEUS_URL ?= http://127.0.0.1:9090
WAIT_ATTEMPTS ?= 30
WAIT_SLEEP_SECONDS ?= 1
LOKI_SMOKE_REQUEST_ID ?= loki-smoke

.PHONY: \
	help \
	run debug \
	quality check test test-unit test-integration lint format format-check typecheck import-check \
	migrate-up migrate-down db-up db-down prometheus-check observability-config-check \
	docker-migrate docker-demo-seed docker-up docker-up-demo observability-up observability-up-demo observability-down \
	docker-smoke docker-smoke-demo \
	docker-build docker-buildx-bootstrap docker-push \
	._docker-bootstrap ._docker-bootstrap-demo ._docker-up-observability ._docker-clean-migrate ._docker-down \
	._wait-app ._wait-loki ._wait-prometheus-targets ._verify-service-endpoints ._verify-loki-smoke

define wait_for_url
for attempt in $$(seq 1 $(WAIT_ATTEMPTS)); do \
	if curl --silent --fail $(1) >/dev/null 2>&1; then \
		exit 0; \
	fi; \
	sleep $(WAIT_SLEEP_SECONDS); \
done; \
echo "Timed out waiting for $(1)" >&2; \
exit 1
endef

define wait_for_prometheus_targets
for attempt in $$(seq 1 $(WAIT_ATTEMPTS)); do \
	targets_json=$$(curl --silent $(PROMETHEUS_URL)/api/v1/targets); \
	if printf '%s' "$$targets_json" | grep -q '"job":"aptitude-registry"' \
		&& printf '%s' "$$targets_json" | grep -q '"job":"loki"' \
		&& printf '%s' "$$targets_json" | grep -q '"job":"otelcol"'; then \
		exit 0; \
	fi; \
	sleep $(WAIT_SLEEP_SECONDS); \
done; \
echo "Timed out waiting for Prometheus targets" >&2; \
exit 1
endef

define verify_loki_smoke
curl --silent --fail -H 'X-Request-ID: $(LOKI_SMOKE_REQUEST_ID)' $(APP_BASE_URL)/healthz >/dev/null; \
start_ns=$$($(PYTHON) -c 'import time; print(time.time_ns() - 300_000_000_000)'); \
for attempt in $$(seq 1 $(WAIT_ATTEMPTS)); do \
	end_ns=$$($(PYTHON) -c 'import time; print(time.time_ns())'); \
	if curl --silent --get \
		--data-urlencode 'query={service_name="aptitude-registry"} |= "$(LOKI_SMOKE_REQUEST_ID)"' \
		--data-urlencode "start=$$start_ns" \
		--data-urlencode "end=$$end_ns" \
		--data-urlencode 'limit=20' \
		$(LOKI_URL)/loki/api/v1/query_range | \
	$(PYTHON) -c 'import json, sys; data = json.load(sys.stdin); raise SystemExit(0 if any(stream["values"] for stream in data["data"]["result"]) else 1)'; then \
		end_ns=$$($(PYTHON) -c 'import time; print(time.time_ns())'); \
		curl --silent --get \
			--data-urlencode 'query={service_name="aptitude-registry"} |= "$(LOKI_SMOKE_REQUEST_ID)"' \
			--data-urlencode "start=$$start_ns" \
			--data-urlencode "end=$$end_ns" \
			--data-urlencode 'limit=20' \
			$(LOKI_URL)/loki/api/v1/query_range | \
		$(PYTHON) -c 'import json, sys; data = json.load(sys.stdin); matches = [(ts, line) for stream in data["data"]["result"] for ts, line in stream["values"]]; print(matches[0][1]) if matches else sys.exit("No Loki records matched $(LOKI_SMOKE_REQUEST_ID)")'; \
		exit 0; \
	fi; \
	sleep $(WAIT_SLEEP_SECONDS); \
done; \
echo "Timed out waiting for Loki record $(LOKI_SMOKE_REQUEST_ID)" >&2; \
exit 1
endef

##@ General
help: ## Show available targets
	@awk 'BEGIN {FS = ":.*## "}; /^##@/ {printf "\n%s\n", substr($$0, 5); next} /^[a-zA-Z0-9_.-]+:.*## / {printf "  %-24s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

##@ Local Development
run: ## Start the FastAPI dev server with reload enabled
	@printf "\033[1;36m==>\033[0m \033[1mStarting FastAPI dev server\033[0m\n"
	@printf "\033[0;36m    API:\033[0m  %s\n" "$(APP_BASE_URL)"
	@printf "\033[0;36m   Docs:\033[0m  %s/docs\n" "$(APP_BASE_URL)"
	@printf "\033[0;36m   Stop:\033[0m  Ctrl+C\n\n"
	@UVICORN_RELOAD=true $(PYTHON) -m app.main

debug: ## Start the FastAPI dev server with debug logging
	@printf "\033[1;36m==>\033[0m \033[1mStarting FastAPI dev server in debug mode\033[0m\n"
	@printf "\033[0;36m    API:\033[0m  %s\n" "$(APP_BASE_URL)"
	@printf "\033[0;36m   Docs:\033[0m  %s/docs\n" "$(APP_BASE_URL)"
	@printf "\033[0;36m  Level:\033[0m  DEBUG\n"
	@printf "\033[0;36m   Stop:\033[0m  Ctrl+C\n\n"
	@LOG_LEVEL=DEBUG UVICORN_RELOAD=false $(PYTHON) -m app.main

##@ Quality
quality: format-check lint typecheck ## Run static quality checks

check: quality ## Compatibility alias for static quality checks

test: ## Run the test suite
	$(PYTEST)

test-unit: ## Run the non-integration test suite
	$(PYTEST) -m "not integration"

test-integration: ## Run the integration test suite
	$(PYTEST) tests/integration

lint: ## Run Ruff lint checks
	$(RUFF) check .

format: ## Format the codebase with Ruff
	$(RUFF) format .

format-check: ## Check code formatting with Ruff
	$(RUFF) format --check .

typecheck: ## Run mypy type checks
	$(MYPY) app

import-check: ## Import the app entrypoint to catch startup regressions
	$(PYTHON) -c "from app.main import app"

##@ Database
migrate-up: ## Apply the latest database migrations
	$(UV) run alembic upgrade head

migrate-down: ## Roll back the latest database migration
	$(UV) run alembic downgrade -1

db-up: ## Start the local PostgreSQL service
	$(COMPOSE) up -d db

db-down: ## Stop and remove the local Docker services and volumes
	$(COMPOSE) down -v

prometheus-check: ## Validate the Prometheus config and rules
	docker run --rm \
		--entrypoint promtool \
		-v "$$PWD/ops/monitoring/prometheus:/etc/prometheus:ro" \
		prom/prometheus:v3.5.1 \
		check config /etc/prometheus/prometheus.yml

observability-config-check: ## Validate the observability compose profile
	$(COMPOSE_OBS) config >/dev/null

##@ Docker Local Stack
docker-migrate: ## Run migrations inside the Docker stack
	$(COMPOSE_OBS) run --rm migrate
	@$(MAKE) ._docker-clean-migrate

docker-demo-seed: ## Seed demo data inside the Docker stack
	$(COMPOSE_DEMO) run --rm demo-seed
	@$(MAKE) ._docker-clean-migrate

docker-up: ._docker-bootstrap ## Start the local app stack with bootstrap data only
	$(COMPOSE) up -d server

docker-up-demo: ._docker-bootstrap-demo ## Start the local app stack with demo data loaded
	$(COMPOSE) up -d server

observability-up: ._docker-bootstrap ._docker-up-observability ._docker-clean-migrate ## Start the local app and observability stack

observability-up-demo: ._docker-bootstrap-demo ._docker-up-observability ._docker-clean-migrate ## Start the local app and observability stack with demo data

observability-down: ._docker-down ## Stop the observability stack and remove volumes

._docker-bootstrap:
	$(COMPOSE_OBS) up -d db
ifeq ($(strip $(APP_IMAGE)),)
	$(COMPOSE_OBS) build server migrate
endif
	$(COMPOSE_OBS) run --rm migrate

._docker-bootstrap-demo: ._docker-bootstrap
	$(COMPOSE_DEMO) run --rm demo-seed

._docker-up-observability:
	$(COMPOSE_OBS) up -d server observability

._docker-clean-migrate:
	@$(COMPOSE_OBS) rm -f -s migrate >/dev/null 2>&1 || true

._docker-down:
	$(COMPOSE_OBS) down -v

##@ Smoke Tests
docker-smoke: ._docker-bootstrap ._docker-up-observability ._docker-clean-migrate ._wait-app ._wait-loki ._wait-prometheus-targets ._verify-service-endpoints ._verify-loki-smoke ._docker-down ## Verify the local app and observability stack

docker-smoke-demo: ._docker-bootstrap-demo ._docker-up-observability ._docker-clean-migrate ._wait-app ._wait-loki ._wait-prometheus-targets ._verify-service-endpoints ._verify-loki-smoke ._docker-down ## Verify the local app and observability stack with demo data

._wait-app:
	@$(call wait_for_url,$(APP_BASE_URL)/healthz)

._wait-loki:
	@$(call wait_for_url,$(LOKI_URL)/ready)

._wait-prometheus-targets:
	@$(call wait_for_prometheus_targets)

._verify-service-endpoints:
	curl --fail $(APP_BASE_URL)/healthz
	curl --fail $(APP_BASE_URL)/readyz
	curl --fail $(APP_BASE_URL)/metrics
	curl --fail $(LOKI_URL)/ready
	curl --silent $(PROMETHEUS_URL)/api/v1/targets | grep '"job":"aptitude-registry"'
	curl --silent $(PROMETHEUS_URL)/api/v1/targets | grep '"job":"loki"'
	curl --silent $(PROMETHEUS_URL)/api/v1/targets | grep '"job":"otelcol"'

._verify-loki-smoke:
	@$(call verify_loki_smoke)

##@ Release Images
docker-build: ## Build the local Docker image
	docker buildx build --load -t $(DOCKER_IMAGE_REF) .

docker-buildx-bootstrap: ## Ensure the multi-arch Docker builder exists and is bootstrapped
	@docker buildx inspect $(DOCKER_BUILDER) >/dev/null 2>&1 || docker buildx create --name $(DOCKER_BUILDER) --driver docker-container >/dev/null
	@docker buildx inspect --bootstrap $(DOCKER_BUILDER) >/dev/null

docker-push: docker-buildx-bootstrap ## Build and push the multi-arch Docker image
	docker buildx build --builder $(DOCKER_BUILDER) --platform $(DOCKER_PLATFORMS) --push -t $(DOCKER_IMAGE_REF) .
