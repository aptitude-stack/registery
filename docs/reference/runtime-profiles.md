# Runtime Profiles and Environment Variables

This repo has two different kinds of "profiles". They solve different problems and should not be mixed together.

## Runtime Profile: `APP_ENV`

`APP_ENV` is the application's runtime profile. It is validated and accepts only:

- `dev`: local development and fast iteration
- `prod`: deployed or production-like execution

`APP_ENV` changes runtime posture such as logging and future environment-specific wiring. It does not change the public HTTP contract. The same routes, request shapes, and response shapes must exist in both profiles.

There is no `test`, `container`, or `staging` runtime profile in the app.

## Compose Profiles

Docker Compose also uses profiles, but those are orchestration selectors, not app runtime modes.

Current Compose profiles include:

- `demo`: adds the demo seed job
- `observability`: adds Prometheus, Grafana, Loki, and related tooling
- `test`: adds the dedicated test PostgreSQL container

These Compose profiles decide which containers run. They do not define new FastAPI behaviors or new `APP_ENV` values.

## Test and CI Environments

Tests and CI are execution environments, not runtime profiles.

- Most tests should boot the app with `APP_ENV=prod` when they need production-like behavior.
- Tests should use `APP_ENV=dev` only when they explicitly validate local-development behavior.
- The dedicated test database is selected with `TEST_DATABASE_URL`, not with a special app runtime profile.

## Common Variables

- `APP_ENV`: runtime profile for the app (`dev` or `prod`)
- `DATABASE_URL`: primary application database
- `TEST_DATABASE_URL`: dedicated database used by integration-test flows
- `AUTH_TOKENS_JSON`: bearer tokens and scopes used by authenticated routes
- `LOG_LEVEL`, `LOG_FORMAT`, `LOG_FILE_PATH`: logging configuration

## Practical Defaults

- `make run-dev` starts the checked-in Compose stack with `APP_ENV=dev`, the `demo` profile, and the `observability` profile
- `make run-prod` starts the checked-in Compose stack with `APP_ENV=prod` and the `observability` profile
- raw `docker compose` usage defaults the checked-in app services to `APP_ENV=prod` unless you override `APP_ENV`
- `make test` manages the dedicated `test` profile database container for the full test suite
- `LOG_FORMAT=auto` prefers readable local logs in `dev` and structured JSON logs in `prod`
