UV ?= UV_CACHE_DIR=.uv-cache uv
DOCKER_IMAGE ?= y0ncha/aptitude-registry
DOCKER_TAG ?= latest
DOCKER_IMAGE_REF := $(DOCKER_IMAGE):$(DOCKER_TAG)
DOCKER_PLATFORMS ?= linux/amd64,linux/arm64
DOCKER_BUILDER ?= aptitude-multiarch

.PHONY: run debug test lint format typecheck migrate-up migrate-down db-up db-down docker-migrate observability-up observability-down docker-smoke docker-build docker-buildx-bootstrap docker-push docker-build-push

run:
	@printf "\033[1;36m==>\033[0m \033[1mStarting FastAPI dev server\033[0m\n"
	@printf "\033[0;36m    API:\033[0m  http://127.0.0.1:8000\n"
	@printf "\033[0;36m   Docs:\033[0m  http://127.0.0.1:8000/docs\n"
	@printf "\033[0;36m   Stop:\033[0m  Ctrl+C\n\n"
	@UVICORN_RELOAD=true $(UV) run python -m app.main

debug:
	@printf "\033[1;36m==>\033[0m \033[1mStarting FastAPI dev server in debug mode\033[0m\n"
	@printf "\033[0;36m    API:\033[0m  http://127.0.0.1:8000\n"
	@printf "\033[0;36m   Docs:\033[0m  http://127.0.0.1:8000/docs\n"
	@printf "\033[0;36m  Level:\033[0m  DEBUG\n"
	@printf "\033[0;36m   Stop:\033[0m  Ctrl+C\n\n"
	@LOG_LEVEL=DEBUG UVICORN_RELOAD=false $(UV) run python -m app.main

test:
	$(UV) run --extra dev python -m pytest

lint:
	$(UV) run --extra dev ruff check .

format:
	$(UV) run --extra dev ruff format .

typecheck:
	$(UV) run --extra dev python -m mypy app

migrate-up:
	$(UV) run alembic upgrade head

migrate-down:
	$(UV) run alembic downgrade -1

db-up:
	docker compose up -d db

db-down:
	docker compose down -v

docker-migrate:
	docker compose --profile observability run --rm migrate

observability-up:
	docker compose --profile observability up -d db
	docker compose --profile observability build server migrate
	docker compose --profile observability run --rm migrate
	docker compose --profile observability up -d server observability

observability-down:
	docker compose --profile observability down -v

docker-smoke:
	docker compose --profile observability up -d db
	docker compose --profile observability build server migrate
	docker compose --profile observability run --rm migrate
	docker compose --profile observability up -d server observability
	@for attempt in $$(seq 1 30); do \
		if curl --silent --fail http://127.0.0.1:8000/healthz >/dev/null 2>&1; then \
			break; \
		fi; \
		sleep 1; \
	done
	@for attempt in $$(seq 1 30); do \
		if curl --silent --fail http://127.0.0.1:3100/ready >/dev/null 2>&1; then \
			break; \
		fi; \
		sleep 1; \
	done
	@for attempt in $$(seq 1 30); do \
		if curl --silent http://127.0.0.1:9090/api/v1/targets | grep -q '"job":"aptitude-registry"' \
			&& curl --silent http://127.0.0.1:9090/api/v1/targets | grep -q '"job":"loki"' \
			&& curl --silent http://127.0.0.1:9090/api/v1/targets | grep -q '"job":"otelcol"'; then \
			break; \
		fi; \
		sleep 1; \
	done
	curl --fail http://127.0.0.1:8000/healthz
	curl --fail http://127.0.0.1:8000/readyz
	curl --fail http://127.0.0.1:8000/metrics
	curl --fail http://127.0.0.1:3100/ready
	curl --silent http://127.0.0.1:9090/api/v1/targets | grep '"job":"aptitude-registry"'
	curl --silent http://127.0.0.1:9090/api/v1/targets | grep '"job":"loki"'
	curl --silent http://127.0.0.1:9090/api/v1/targets | grep '"job":"otelcol"'
	curl --silent --fail -H 'X-Request-ID: loki-smoke' http://127.0.0.1:8000/healthz >/dev/null
	@START=$$(python3 -c 'import time; print(time.time_ns() - 300_000_000_000)'); \
	for attempt in $$(seq 1 30); do \
		END=$$(python3 -c 'import time; print(time.time_ns())'); \
		if curl --silent --get --data-urlencode 'query={service_name="aptitude-registry"} |= "loki-smoke"' --data-urlencode "start=$${START}" --data-urlencode "end=$${END}" --data-urlencode 'limit=20' http://127.0.0.1:3100/loki/api/v1/query_range | python3 -c 'import json, sys; data = json.load(sys.stdin); raise SystemExit(0 if any(stream["values"] for stream in data["data"]["result"]) else 1)'; then \
			break; \
		fi; \
		sleep 1; \
	done; \
	END=$$(python3 -c 'import time; print(time.time_ns())'); \
	curl --silent --get --data-urlencode 'query={service_name="aptitude-registry"} |= "loki-smoke"' --data-urlencode "start=$${START}" --data-urlencode "end=$${END}" --data-urlencode 'limit=20' http://127.0.0.1:3100/loki/api/v1/query_range | python3 -c 'import json, sys; data = json.load(sys.stdin); matches = [(ts, line) for stream in data["data"]["result"] for ts, line in stream["values"]]; print(matches[0][1]) if matches else sys.exit("No Loki records matched loki-smoke")'
	docker compose --profile observability down -v

docker-build:
	docker buildx build --load -t $(DOCKER_IMAGE_REF) .

docker-buildx-bootstrap:
	@docker buildx inspect $(DOCKER_BUILDER) >/dev/null 2>&1 || docker buildx create --name $(DOCKER_BUILDER) --driver docker-container >/dev/null
	@docker buildx inspect --bootstrap $(DOCKER_BUILDER) >/dev/null

docker-push: docker-buildx-bootstrap
	docker buildx build --builder $(DOCKER_BUILDER) --platform $(DOCKER_PLATFORMS) --push -t $(DOCKER_IMAGE_REF) .

docker-build-push: docker-push
