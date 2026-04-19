.DEFAULT_GOAL := help
SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c

UV ?= UV_CACHE_DIR=.uv-cache uv
PYTHON := $(UV) run python
PYTEST := $(UV) run --extra dev python -m pytest
RUFF := $(UV) run --extra dev ruff
MYPY := $(UV) run --extra dev python -m mypy

COMPOSE := docker compose
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
METRICS_BEARER_TOKEN ?= admin-token.dev-admin-secret

.PHONY: \
	help \
	run-dev run-prod quality test format build \
	_ci-quality _ci-test _ci-observability _ci-image _ci-smoke _ci-down \
	_format-check _lint _format _typecheck _test _import-check \
	_test-db-up _test-db-wait _test-db-down \
	_prometheus-check _observability-config-check \
	_run-stack _stack-down _smoke-wait _smoke-verify \
	_wait-app _wait-loki _wait-prometheus-targets _verify-service-endpoints _verify-loki-smoke \
	_image-load _image-builder-bootstrap _image-push

define compose_with_env
APP_ENV=$(1) $(if $(strip $(2)),$(COMPOSE) $(2),$(COMPOSE))
endef

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
$(call compose_with_env,$(1)) up -d db; \
if [ "$(APP_IMAGE)" = "$(APP_IMAGE_DEFAULT)" ]; then \
	$(call compose_with_env,$(1)) build server migrate$(if $(filter 1,$(2)), demo-seed); \
fi; \
$(call compose_with_env,$(1)) run --rm migrate
endef

define stack_seed_demo_commands
$(call compose_with_env,$(1),--profile demo) run --rm demo-seed
endef

define stack_start_commands
$(call compose_with_env,$(1),--profile observability) up -d server observability
endef

define stack_cleanup_commands
$(call compose_with_env,$(1)) rm -f -s migrate >/dev/null 2>&1 || true
endef

define stack_down_commands
$(call compose_with_env,$(1),--profile observability) down -v
endef

define smoke_wait_commands
( $(call wait_for_url,$(APP_BASE_URL)/healthz) ); \
( $(call wait_for_url,$(LOKI_URL)/ready) ); \
( $(call wait_for_prometheus_targets) )
endef

define smoke_verify_commands
curl --fail $(APP_BASE_URL)/healthz; \
curl --fail $(APP_BASE_URL)/readyz; \
curl --fail -H 'Authorization: Bearer $(METRICS_BEARER_TOKEN)' $(APP_BASE_URL)/metrics; \
curl --fail $(LOKI_URL)/ready; \
curl --silent $(PROMETHEUS_URL)/api/v1/targets | grep '"job":"aptitude-registry"'; \
curl --silent $(PROMETHEUS_URL)/api/v1/targets | grep '"job":"loki"'; \
curl --silent $(PROMETHEUS_URL)/api/v1/targets | grep '"job":"otelcol"'; \
( $(call verify_loki_smoke) )
endef

#-----------------------------------------------------------------------------------

## User
help: ## Show available targets
	@awk 'BEGIN {FS = ":.*## "}; /^[a-zA-Z0-9][a-zA-Z0-9-]*:.*## / {printf "  %-10s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

run-dev: RUN_APP_ENV := dev
run-dev: RUN_DEMO := 1
run-dev: _run-stack ## Start the Docker stack with APP_ENV=dev, demo data, and observability

run-prod: RUN_APP_ENV := prod
run-prod: RUN_DEMO := 0
run-prod: _run-stack ## Start the Docker stack with APP_ENV=prod and observability

quality: _format-check _lint _typecheck ## Run format check, lint, and type checks

test: _test ## Run the full test suite

format: _format ## Format the codebase with Ruff

build: _image-push ## Build and push the multi-platform Docker image

#-----------------------------------------------------------------------------------

## CI
_ci-quality:
	$(MAKE) quality
	$(MAKE) _import-check

_ci-test:
	$(MAKE) test

_ci-observability:
	$(MAKE) _prometheus-check
	$(MAKE) _observability-config-check

_ci-image:
	$(MAKE) _image-load

_ci-smoke:
	trap 'status=$$?; $(call stack_down_commands,prod); exit $$status' EXIT; \
	$(call stack_bootstrap_commands,prod,0); \
	$(call stack_start_commands,prod); \
	$(call stack_cleanup_commands,prod); \
	$(call smoke_wait_commands); \
	$(call smoke_verify_commands)

_ci-down:
	$(call stack_down_commands,prod)

#-----------------------------------------------------------------------------------

## Helpers
_format-check:
	$(RUFF) format --check .

_lint:
	$(RUFF) check .

_format:
	$(RUFF) format .

_typecheck:
	$(MYPY) app

_test:
	trap 'status=$$?; $(call test_db_down_commands); exit $$status' EXIT; \
	$(call test_db_up_commands); \
	$(call test_db_wait_commands); \
	TEST_DATABASE_URL=$(TEST_DATABASE_URL) $(PYTEST)

_import-check:
	$(PYTHON) -c "from app.main import app"

_test-db-up:
	$(call test_db_up_commands)

_test-db-wait:
	$(call test_db_wait_commands)

_test-db-down:
	@$(call test_db_down_commands)

_prometheus-check:
	docker run --rm \
		--entrypoint promtool \
		-v "$$PWD/ops/monitoring/prometheus:/etc/prometheus:ro" \
		prom/prometheus:v3.5.1 \
		check config /etc/prometheus/prometheus.yml

_observability-config-check:
	$(call compose_with_env,prod,--profile observability) config >/dev/null

_run-stack:
	$(call stack_bootstrap_commands,$(RUN_APP_ENV),$(RUN_DEMO))
	$(call stack_start_commands,$(RUN_APP_ENV))
	$(if $(filter 1,$(RUN_DEMO)),$(call stack_seed_demo_commands,$(RUN_APP_ENV)))
	$(call stack_cleanup_commands,$(RUN_APP_ENV))

_stack-down:
	$(call stack_down_commands,prod)

_smoke-wait: _wait-app _wait-loki _wait-prometheus-targets

_smoke-verify: _verify-service-endpoints _verify-loki-smoke

_wait-app:
	@$(call wait_for_url,$(APP_BASE_URL)/healthz)

_wait-loki:
	@$(call wait_for_url,$(LOKI_URL)/ready)

_wait-prometheus-targets:
	@$(call wait_for_prometheus_targets)

_verify-service-endpoints:
	curl --fail $(APP_BASE_URL)/healthz
	curl --fail $(APP_BASE_URL)/readyz
	curl --fail -H 'Authorization: Bearer $(METRICS_BEARER_TOKEN)' $(APP_BASE_URL)/metrics
	curl --fail $(LOKI_URL)/ready
	curl --silent $(PROMETHEUS_URL)/api/v1/targets | grep '"job":"aptitude-registry"'
	curl --silent $(PROMETHEUS_URL)/api/v1/targets | grep '"job":"loki"'
	curl --silent $(PROMETHEUS_URL)/api/v1/targets | grep '"job":"otelcol"'

_verify-loki-smoke:
	@$(call verify_loki_smoke)

_image-load:
	docker buildx build --load -t $(DOCKER_IMAGE_REF) .

_image-builder-bootstrap:
	@docker buildx inspect $(DOCKER_BUILDER) >/dev/null 2>&1 || docker buildx create --name $(DOCKER_BUILDER) --driver docker-container >/dev/null
	@docker buildx inspect --bootstrap $(DOCKER_BUILDER) >/dev/null

_image-push: _image-builder-bootstrap
	docker buildx build --builder $(DOCKER_BUILDER) --platform $(DOCKER_PLATFORMS) --push -t $(DOCKER_IMAGE_REF) .
