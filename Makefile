.DEFAULT_GOAL := help
SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c

UV ?= UV_CACHE_DIR=.uv-cache uv
PYTHON := $(UV) run python
PYTEST := $(UV) run --extra dev python -m pytest
RUFF := $(UV) run --extra dev ruff
MYPY := $(UV) run --extra dev python -m mypy

COMPOSE := docker compose
COMPOSE_DEMO := $(COMPOSE) --profile demo
COMPOSE_OBS := $(COMPOSE) --profile observability
COMPOSE_TEST := $(COMPOSE) --profile test

DOCKER_IMAGE ?= y0ncha/aptitude-registry
DOCKER_TAG ?= latest
DOCKER_LOCAL_TAG ?= local
DOCKER_IMAGE_REF := $(DOCKER_IMAGE):$(DOCKER_TAG)
DOCKER_BUILDER ?= aptitude-multiarch
DOCKER_PLATFORMS ?= linux/amd64,linux/arm64
APP_IMAGE_DEFAULT := $(DOCKER_IMAGE):$(DOCKER_LOCAL_TAG)
export APP_IMAGE ?= $(APP_IMAGE_DEFAULT)

TEST_POSTGRES_DB ?= aptitude_test
TEST_POSTGRES_USER ?= postgres
TEST_POSTGRES_PASSWORD ?= postgres
TEST_POSTGRES_PORT ?= 5433
TEST_DATABASE_URL ?= postgresql+psycopg://$(TEST_POSTGRES_USER):$(TEST_POSTGRES_PASSWORD)@127.0.0.1:$(TEST_POSTGRES_PORT)/$(TEST_POSTGRES_DB)
TEST_DB_VOLUME ?= aptitude-test-postgres-data

APP_BASE_URL ?= http://127.0.0.1:8000
LOKI_URL ?= http://127.0.0.1:3100
PROMETHEUS_URL ?= http://127.0.0.1:9090
WAIT_ATTEMPTS ?= 30
WAIT_SLEEP_SECONDS ?= 1
LOKI_SMOKE_REQUEST_ID ?= loki-smoke

.PHONY: \
	help \
	run debug \
	quality lint format format-check typecheck \
	tests tests-unit tests-integration tests-integration-container \
	db db-test db-down migrate-up migrate-down \
	stack stack-demo stack-observability stack-observability-demo stack-down \
	smoke smoke-demo \
	image-build image-push \
	ci-quality ci-tests ci-observability ci-image ci-smoke \
	_test_db_up _test_db_wait _test_db_down _import_check _prometheus_check _observability_config_check \
	_stack_bootstrap _stack_seed_demo _stack_start_server _stack_start_observability _stack_cleanup_migrate _stack_down \
	_smoke_wait _smoke_verify _wait_app _wait_loki _wait_prometheus_targets _verify_service_endpoints _verify_loki_smoke \
	_image_builder_bootstrap

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

define test_db_up_commands
$(COMPOSE_TEST) up -d test-db
endef

define test_db_wait_commands
for attempt in $$(seq 1 $(WAIT_ATTEMPTS)); do \
	if $(COMPOSE_TEST) exec -T test-db pg_isready -U $(TEST_POSTGRES_USER) -d $(TEST_POSTGRES_DB) >/dev/null 2>&1; then \
		break; \
	fi; \
	sleep $(WAIT_SLEEP_SECONDS); \
done; \
$(COMPOSE_TEST) exec -T test-db pg_isready -U $(TEST_POSTGRES_USER) -d $(TEST_POSTGRES_DB)
endef

define test_db_down_commands
$(COMPOSE_TEST) rm -f -s -v test-db >/dev/null 2>&1 || true; \
docker volume rm -f $(TEST_DB_VOLUME) >/dev/null 2>&1 || true
endef

define stack_bootstrap_commands
$(COMPOSE) up -d db; \
if [ "$(APP_IMAGE)" = "$(APP_IMAGE_DEFAULT)" ]; then \
	$(COMPOSE) build server migrate; \
fi; \
$(COMPOSE) run --rm migrate
endef

define stack_seed_demo_commands
$(COMPOSE_DEMO) run --rm demo-seed
endef

define stack_down_commands
$(COMPOSE_OBS) down -v
endef

define smoke_wait_commands
( $(call wait_for_url,$(APP_BASE_URL)/healthz) ); \
( $(call wait_for_url,$(LOKI_URL)/ready) ); \
( $(call wait_for_prometheus_targets) )
endef

define smoke_verify_commands
curl --fail $(APP_BASE_URL)/healthz; \
curl --fail $(APP_BASE_URL)/readyz; \
curl --fail $(APP_BASE_URL)/metrics; \
curl --fail $(LOKI_URL)/ready; \
curl --silent $(PROMETHEUS_URL)/api/v1/targets | grep '"job":"aptitude-registry"'; \
curl --silent $(PROMETHEUS_URL)/api/v1/targets | grep '"job":"loki"'; \
curl --silent $(PROMETHEUS_URL)/api/v1/targets | grep '"job":"otelcol"'; \
( $(call verify_loki_smoke) )
endef

##@ General
help: ## Show available targets
	@awk 'BEGIN {FS = ":.*## "}; /^##@/ {printf "\n%s\n", substr($$0, 5); next} /^[a-zA-Z0-9_.-]+:.*## / {printf "  %-28s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

##@ Local Development
run: ## Start the FastAPI dev server with reload enabled
	@printf "API %s\nDocs %s/docs\n" "$(APP_BASE_URL)" "$(APP_BASE_URL)"
	@UVICORN_RELOAD=true $(PYTHON) -m app.main

debug: ## Start the FastAPI dev server with debug logging
	@printf "API %s\nDocs %s/docs\nLog level DEBUG\n" "$(APP_BASE_URL)" "$(APP_BASE_URL)"
	@LOG_LEVEL=DEBUG UVICORN_RELOAD=false $(PYTHON) -m app.main

##@ Quality
quality: format-check lint typecheck ## Run static quality checks

lint: ## Run Ruff lint checks
	$(RUFF) check .

format: ## Format the codebase with Ruff
	$(RUFF) format .

format-check: ## Check code formatting with Ruff
	$(RUFF) format --check .

typecheck: ## Run mypy type checks
	$(MYPY) app

tests: ## Run the full test suite in one session against a managed test database
	trap 'status=$$?; $(call test_db_down_commands); exit $$status' EXIT; \
	$(call test_db_up_commands); \
	$(call test_db_wait_commands); \
	TEST_DATABASE_URL=$(TEST_DATABASE_URL) $(PYTEST)

tests-unit: ## Run the non-integration test suite
	$(PYTEST) -m "not integration"

tests-integration: ## Run the integration test suite against TEST_DATABASE_URL
	TEST_DATABASE_URL=$(TEST_DATABASE_URL) $(PYTEST) tests/integration

tests-integration-container: ## Run integration tests with a managed test database container
	trap 'status=$$?; $(call test_db_down_commands); exit $$status' EXIT; \
	$(call test_db_up_commands); \
	$(call test_db_wait_commands); \
	TEST_DATABASE_URL=$(TEST_DATABASE_URL) $(PYTEST) tests/integration

##@ Database
db: ## Start the local PostgreSQL service
	$(COMPOSE) up -d db

db-test: ## Start the dedicated PostgreSQL service for integration tests
	$(COMPOSE_TEST) up -d test-db

db-down: ## Stop and remove local Docker services and volumes
	$(COMPOSE) down -v

migrate-up: ## Apply the latest database migrations
	$(UV) run alembic upgrade head

migrate-down: ## Roll back the latest database migration
	$(UV) run alembic downgrade -1

##@ Docker Profiles
stack: _stack_bootstrap _stack_start_server _stack_cleanup_migrate ## Start the local app stack with bootstrap data only

stack-demo: _stack_bootstrap _stack_start_server _stack_seed_demo _stack_cleanup_migrate ## Start the local app stack and seed demo data

stack-observability: _stack_bootstrap _stack_start_observability _stack_cleanup_migrate ## Start the local app and observability stack

stack-observability-demo: _stack_bootstrap _stack_start_observability _stack_seed_demo _stack_cleanup_migrate ## Start the local app and observability stack with demo data

stack-down: _stack_down ## Stop the local Docker stack and remove volumes

smoke: ## Verify the local app and observability stack
	trap 'status=$$?; $(call stack_down_commands); exit $$status' EXIT; \
	$(call stack_bootstrap_commands); \
	$(COMPOSE_OBS) up -d server observability; \
	$(COMPOSE) rm -f -s migrate >/dev/null 2>&1 || true; \
	$(call smoke_wait_commands); \
	$(call smoke_verify_commands)

smoke-demo: ## Verify the local app and observability stack with demo data
	trap 'status=$$?; $(call stack_down_commands); exit $$status' EXIT; \
	$(call stack_bootstrap_commands); \
	$(COMPOSE_OBS) up -d server observability; \
	$(call stack_seed_demo_commands); \
	$(COMPOSE) rm -f -s migrate >/dev/null 2>&1 || true; \
	$(call smoke_wait_commands); \
	$(call smoke_verify_commands)

##@ Images
image-build: ## Build the CI image locally
	docker buildx build --load -t $(DOCKER_IMAGE_REF) .

image-push: _image_builder_bootstrap ## Build and push the multi-arch Docker image
	docker buildx build --builder $(DOCKER_BUILDER) --platform $(DOCKER_PLATFORMS) --push -t $(DOCKER_IMAGE_REF) .

##@ CI
ci-quality: quality _import_check ## Run the CI quality gate

ci-tests: tests ## Run the CI test gate

ci-observability: _prometheus_check _observability_config_check ## Run the CI observability gate

ci-image: image-build ## Build the CI smoke-test image

ci-smoke: smoke ## Run the CI smoke gate

_test_db_up:
	$(call test_db_up_commands)

_test_db_wait:
	$(call test_db_wait_commands)

_test_db_down:
	@$(call test_db_down_commands)

_import_check:
	$(PYTHON) -c "from app.main import app"

_prometheus_check:
	docker run --rm \
		--entrypoint promtool \
		-v "$$PWD/ops/monitoring/prometheus:/etc/prometheus:ro" \
		prom/prometheus:v3.5.1 \
		check config /etc/prometheus/prometheus.yml

_observability_config_check:
	$(COMPOSE_OBS) config >/dev/null

_stack_bootstrap:
	$(call stack_bootstrap_commands)

_stack_seed_demo:
	$(call stack_seed_demo_commands)

_stack_start_server:
	$(COMPOSE) up -d server

_stack_start_observability:
	$(COMPOSE_OBS) up -d server observability

_stack_cleanup_migrate:
	@$(COMPOSE) rm -f -s migrate >/dev/null 2>&1 || true

_stack_down:
	$(call stack_down_commands)

_smoke_wait: _wait_app _wait_loki _wait_prometheus_targets

_smoke_verify: _verify_service_endpoints _verify_loki_smoke

_wait_app:
	@$(call wait_for_url,$(APP_BASE_URL)/healthz)

_wait_loki:
	@$(call wait_for_url,$(LOKI_URL)/ready)

_wait_prometheus_targets:
	@$(call wait_for_prometheus_targets)

_verify_service_endpoints:
	curl --fail $(APP_BASE_URL)/healthz
	curl --fail $(APP_BASE_URL)/readyz
	curl --fail $(APP_BASE_URL)/metrics
	curl --fail $(LOKI_URL)/ready
	curl --silent $(PROMETHEUS_URL)/api/v1/targets | grep '"job":"aptitude-registry"'
	curl --silent $(PROMETHEUS_URL)/api/v1/targets | grep '"job":"loki"'
	curl --silent $(PROMETHEUS_URL)/api/v1/targets | grep '"job":"otelcol"'

_verify_loki_smoke:
	@$(call verify_loki_smoke)

_image_builder_bootstrap:
	@docker buildx inspect $(DOCKER_BUILDER) >/dev/null 2>&1 || docker buildx create --name $(DOCKER_BUILDER) --driver docker-container >/dev/null
	@docker buildx inspect --bootstrap $(DOCKER_BUILDER) >/dev/null
