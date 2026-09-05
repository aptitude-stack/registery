.DEFAULT_GOAL := help
SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c

UV ?= UV_CACHE_DIR=.uv-cache uv
PYTHON := $(UV) run python
PYTEST := $(UV) run --extra dev python -m pytest
RUFF := $(UV) run --extra dev ruff
MYPY := $(UV) run --extra dev python -m mypy

COMPOSE := docker compose
COMPOSE_TEST := $(COMPOSE) -p aptitude-tests -f docker-compose.test.yml

DOCKER_IMAGE ?= y0ncha/aptitude-registry
DOCKER_TAG ?= latest
DOCKER_LOCAL_TAG ?= local
DOCKER_IMAGE_REF := $(DOCKER_IMAGE):$(DOCKER_TAG)
DOCKER_BUILDER ?= aptitude-multiarch
DOCKER_PLATFORMS ?= linux/amd64,linux/arm64
APP_IMAGE_DEFAULT := $(DOCKER_IMAGE):$(DOCKER_LOCAL_TAG)
export APP_IMAGE ?= $(APP_IMAGE_DEFAULT)
export POSTGRES_IMAGE ?= pgvector/pgvector:pg15

TEST_POSTGRES_DB ?= aptitude_test
TEST_POSTGRES_USER ?= postgres
TEST_POSTGRES_PASSWORD ?= postgres
TEST_POSTGRES_PORT ?= 5433
TEST_DATABASE_URL ?= postgresql+psycopg://$(TEST_POSTGRES_USER):$(TEST_POSTGRES_PASSWORD)@127.0.0.1:$(TEST_POSTGRES_PORT)/$(TEST_POSTGRES_DB)

APP_BASE_URL ?= http://127.0.0.1:8000
PRODUCTION_BASE_URL ?= https://api.aptitude-registry.dev
WAIT_ATTEMPTS ?= 30
WAIT_SLEEP_SECONDS ?= 1
TEST_DB_WAIT_ATTEMPTS ?= 90
TEST_DB_WAIT_SLEEP_SECONDS ?= 1
PRODUCTION_WAIT_ATTEMPTS ?= 120
PRODUCTION_WAIT_SLEEP_SECONDS ?= 5

.PHONY: \
	help \
	run-dev run-prod quality test format build rotate \
	_ci-quality _ci-test _ci-image _ci-smoke _ci-production-smoke _ci-down \
	_format-check _lint _format _typecheck _test _import-check \
	_test-db-up _test-db-wait _test-db-down \
	_run-stack _stack-down _smoke-wait _smoke-verify _production-smoke-wait _production-smoke-verify \
	_wait-app _verify-service-endpoints _wait-production-app _verify-production-service-endpoints \
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

define test_db_up_commands
$(COMPOSE_TEST) up -d test-db
endef

define test_db_wait_commands
test_db_ready=0; \
for attempt in $$(seq 1 $(TEST_DB_WAIT_ATTEMPTS)); do \
	if $(COMPOSE_TEST) exec -T test-db pg_isready -U $(TEST_POSTGRES_USER) -d $(TEST_POSTGRES_DB) >/dev/null 2>&1; then \
		test_db_ready=1; \
		break; \
	fi; \
	sleep $(TEST_DB_WAIT_SLEEP_SECONDS); \
done; \
if [ "$$test_db_ready" != "1" ]; then \
	echo "Timed out waiting for test database to accept connections after $(TEST_DB_WAIT_ATTEMPTS) attempts." >&2; \
	$(COMPOSE_TEST) logs test-db >&2; \
	exit 1; \
fi; \
$(COMPOSE_TEST) exec -T test-db pg_isready -U $(TEST_POSTGRES_USER) -d $(TEST_POSTGRES_DB)
endef

define test_db_down_commands
$(COMPOSE_TEST) down
endef

define stack_bootstrap_commands
docker volume create aptitude-local_aptitude-postgres-data >/dev/null; \
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
$(call compose_with_env,$(1)) up -d server
endef

define stack_cleanup_commands
$(call compose_with_env,$(1)) rm -f -s migrate >/dev/null 2>&1 || true
endef

define stack_down_commands
$(call compose_with_env,$(1)) down
endef

define smoke_wait_commands
( $(call wait_for_url,$(APP_BASE_URL)/healthz) )
endef

define smoke_verify_commands
curl --fail $(APP_BASE_URL)/healthz; \
curl --fail $(APP_BASE_URL)/readyz
endef

#-----------------------------------------------------------------------------------

## User
help: ## Show available targets
	@awk 'BEGIN {FS = ":.*## "}; /^[a-zA-Z0-9][a-zA-Z0-9-]*:.*## / {printf "  %-10s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

run-dev: RUN_APP_ENV := dev
run-dev: RUN_DEMO := 1
run-dev: _run-stack ## Start the Docker stack with APP_ENV=dev and demo data

run-prod: RUN_APP_ENV := prod
run-prod: RUN_DEMO := 0
run-prod: _run-stack ## Start the Docker stack with APP_ENV=prod

quality: _format-check _lint _typecheck ## Run format check, lint, and type checks

test: _test ## Run the full test suite

format: _format ## Format the codebase with Ruff

build: _image-push ## Build and push the multi-platform Docker image

rotate: ## Generate production service token rotation env values
	$(PYTHON) scripts/generate_service_token.py

#-----------------------------------------------------------------------------------

## CI
_ci-quality:
	$(MAKE) quality
	$(MAKE) _import-check

_ci-test:
	$(MAKE) test

_ci-image:
	$(MAKE) _image-load

_ci-smoke:
	trap 'status=$$?; $(call stack_down_commands,prod); exit $$status' EXIT; \
	$(call stack_bootstrap_commands,prod,0); \
	$(call stack_start_commands,prod); \
	$(call stack_cleanup_commands,prod); \
	$(call smoke_wait_commands); \
	$(call smoke_verify_commands)

_ci-production-smoke:
	$(MAKE) _production-smoke-wait
	$(MAKE) _production-smoke-verify

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

_run-stack:
	$(call stack_bootstrap_commands,$(RUN_APP_ENV),$(RUN_DEMO))
	$(call stack_start_commands,$(RUN_APP_ENV))
	$(if $(filter 1,$(RUN_DEMO)),$(call stack_seed_demo_commands,$(RUN_APP_ENV)))
	$(call stack_cleanup_commands,$(RUN_APP_ENV))

_stack-down:
	$(call stack_down_commands,prod)

_smoke-wait: _wait-app

_smoke-verify: _verify-service-endpoints

_production-smoke-wait: _wait-production-app

_production-smoke-verify: _verify-production-service-endpoints

_wait-app:
	@$(call wait_for_url,$(APP_BASE_URL)/healthz)

_verify-service-endpoints:
	curl --fail $(APP_BASE_URL)/healthz
	curl --fail $(APP_BASE_URL)/readyz

_wait-production-app:
	@WAIT_ATTEMPTS=$(PRODUCTION_WAIT_ATTEMPTS) WAIT_SLEEP_SECONDS=$(PRODUCTION_WAIT_SLEEP_SECONDS) $(MAKE) _wait-app APP_BASE_URL=$(PRODUCTION_BASE_URL)

_verify-production-service-endpoints:
	$(MAKE) _verify-service-endpoints APP_BASE_URL=$(PRODUCTION_BASE_URL)

_image-load:
	docker buildx build --load -t $(DOCKER_IMAGE_REF) .

_image-builder-bootstrap:
	@docker buildx inspect $(DOCKER_BUILDER) >/dev/null 2>&1 || docker buildx create --name $(DOCKER_BUILDER) --driver docker-container >/dev/null

_image-push: _image-builder-bootstrap
	docker buildx build --builder $(DOCKER_BUILDER) --platform $(DOCKER_PLATFORMS) --push -t $(DOCKER_IMAGE_REF) .
