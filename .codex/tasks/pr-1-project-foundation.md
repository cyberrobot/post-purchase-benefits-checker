# PR 1 — Project Foundation

## Summary

Create the initial backend service foundation for the Post-Purchase Benefits Checker.

This PR establishes the runnable FastAPI application, typed configuration, PostgreSQL connectivity, SQLAlchemy session management, Alembic migrations, automated test infrastructure, structured logging, and a basic health endpoint.

The objective is to provide a small, production-shaped foundation that subsequent PRs can build on without introducing product or domain behaviour prematurely.

---

## Goal

After this PR:

- the backend can be started locally;
- configuration is loaded and validated from environment variables;
- the application can connect to PostgreSQL;
- database migrations can be created and executed with Alembic;
- automated tests can run against a real PostgreSQL instance;
- the service exposes a basic health endpoint;
- application startup and failures are logged in a structured form;
- the project can be exercised consistently locally and in CI.

No promotion, purchase, eligibility, claim, ingestion, AI, REST domain API, or MCP functionality is implemented yet.

---

## Scope

### In scope

Implement:

- Python 3.13 backend project structure;
- FastAPI application entry point;
- application configuration using Pydantic settings;
- PostgreSQL configuration;
- SQLAlchemy 2 database engine/session setup;
- Alembic configuration and initial migration infrastructure;
- application lifecycle handling where required;
- basic health endpoint;
- structured logging foundation;
- Sentry configuration hook;
- pytest configuration;
- Testcontainers/PostgreSQL integration testing support;
- database test fixtures;
- migration tests/smoke tests;
- Docker support for the backend;
- local PostgreSQL development setup where required;
- GitHub Actions test execution;
- environment/configuration documentation.

### Out of scope

Do not implement:

- users or authentication;
- products;
- retailers;
- purchases;
- promotions;
- promotion ingestion;
- reward rules;
- eligibility rules;
- eligibility evaluation;
- claims;
- reminders;
- receipt ingestion;
- AI/LLM integrations;
- AI-assisted promotion extraction;
- external promotion providers;
- scraping;
- MCP tools;
- domain REST endpoints;
- background jobs;
- queues or workers;
- Redis;
- admin functionality.

These belong in subsequent PRs.

---

## Architecture

The backend is a FastAPI service with PostgreSQL as its authoritative persistent datastore.

The initial structure must leave clear boundaries between:

```text
API / MCP adapters
        ↓
application services
        ↓
domain logic
        ↓
repositories / persistence
        ↓
PostgreSQL
```

PR 1 does not need to implement all of these layers, but the project structure must not make FastAPI routes, SQLAlchemy models, or external integrations the future location of business rules.

REST and MCP interfaces will eventually call the same application/domain logic rather than maintain separate implementations.

### Deterministic eligibility boundary

Eligibility decisions will eventually be implemented as deterministic Python domain logic.

No AI or probabilistic logic belongs in the eligibility execution path.

AI may later assist with extracting candidate promotion information, but only approved structured data will become authoritative.

PR 1 should preserve this architectural boundary without implementing it.

---

## Backend structure

Create a backend structure along the lines of:

```text
backend/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── api/
│   │   ├── __init__.py
│   │   └── health.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── logging.py
│   │   └── sentry.py
│   └── db/
│       ├── __init__.py
│       ├── base.py
│       ├── engine.py
│       └── session.py
├── migrations/
│   ├── versions/
│   ├── env.py
│   └── script.py.mako
├── tests/
│   ├── conftest.py
│   ├── integration/
│   └── unit/
├── alembic.ini
├── pyproject.toml
├── Dockerfile
└── .env.example
```

Exact filenames may differ where an existing repository convention already exists.

Avoid adding empty abstraction layers purely to anticipate future requirements.

---

## Application entry point

Provide a single canonical FastAPI application factory or application entry point.

For example:

```python
app = FastAPI(...)
```

or:

```python
def create_app() -> FastAPI:
    ...
```

Prefer an application factory if it materially improves test isolation or configuration injection.

Application startup must not perform destructive or implicit database migrations.

Database migrations are executed explicitly through Alembic.

---

## Configuration

Application configuration must be typed and validated.

Use Pydantic settings rather than directly reading environment variables throughout the codebase.

Configuration should include at minimum:

```text
APP_ENV
DATABASE_URL
LOG_LEVEL
SENTRY_DSN
```

Additional settings may be introduced only where required by this PR.

### Requirements

- environment variables are read in one central configuration module;
- configuration values have explicit types;
- required production configuration fails clearly when missing;
- secrets are never committed;
- `.env.example` contains safe example values only;
- test configuration can be overridden without mutating global process state unexpectedly;
- business/domain code must not read environment variables directly.

Development conveniences must not silently weaken production configuration.

---

## Database

Use:

- PostgreSQL;
- SQLAlchemy 2;
- explicit session management.

Create the shared database infrastructure required by later repositories and application services.

### Connection handling

The application must:

- create connections through a central SQLAlchemy engine;
- expose a reusable session dependency/factory;
- cleanly close sessions after use;
- roll back failed transactions;
- avoid creating ad-hoc engines throughout the application.

Database credentials must come exclusively from configuration.

### Session ownership

Request-level code must have clear session ownership.

A database session must not be stored globally and reused across requests.

Future application services must be able to receive database/repository dependencies without depending directly on FastAPI globals.

---

## Schema and migrations

Configure Alembic against the same SQLAlchemy metadata used by the application.

PR 1 should create migration infrastructure even if no meaningful domain tables exist yet.

### Requirements

Developers must be able to run commands equivalent to:

```bash
alembic upgrade head
```

and:

```bash
alembic downgrade -1
```

Migration configuration must obtain the database connection from application configuration rather than duplicating credentials.

### Initial migration

If no persistent application table is required by this PR, an empty baseline migration is acceptable.

Do not introduce speculative domain tables simply to make the first migration non-empty.

### Migration safety

Migrations must:

- be deterministic;
- be committed to source control;
- not execute automatically on application import;
- fail clearly when PostgreSQL is unavailable;
- support deployment against a fresh database.

---

## API contract

### `GET /health`

Provide a basic process-health endpoint.

#### Success response

```http
HTTP/1.1 200 OK
Content-Type: application/json
```

```json
{
  "status": "ok"
}
```

### Behaviour

The endpoint:

- confirms the FastAPI process is running;
- must not require authentication;
- must not expose configuration values;
- must not expose database credentials;
- must not expose stack traces;
- must remain cheap to call;
- must not call external services.

The basic `/health` endpoint should not become a comprehensive dependency diagnostic endpoint.

More detailed liveness/readiness checks may be introduced separately when deployment requirements justify them.

---

## Error handling

This PR should establish only the minimum error-handling infrastructure necessary for the foundation.

Unexpected server errors must:

- be logged;
- avoid exposing stack traces or secrets to clients;
- return normal HTTP server-error semantics.

Do not introduce a complex application-wide domain error hierarchy before domain errors exist.

---

## Logging

Use structured application logging.

Logs should be machine-readable and suitable for production aggregation.

At minimum, application logs should support:

- timestamp;
- log level;
- logger/module;
- message.

Where a request context exists, leave room for future correlation/request IDs.

### Sensitive information

Never log:

- database passwords;
- complete connection strings containing credentials;
- API keys;
- tokens;
- secrets.

---

## Sentry

Provide the configuration hook required to initialise Sentry when a DSN is configured.

Requirements:

- Sentry must be optional for local development and tests;
- absence of `SENTRY_DSN` must not prevent startup;
- Sentry configuration must remain centralised;
- sensitive configuration must not be attached to events.

Detailed tracing/performance configuration is outside this PR unless already required by repository conventions.

---

## Security

Although this PR does not introduce user-facing product functionality, the foundation must follow secure defaults.

Requirements:

- no secrets committed to source control;
- health responses expose no sensitive information;
- configuration is validated;
- database credentials are environment-driven;
- production failures do not expose Python tracebacks to API consumers;
- dependencies should be version constrained according to repository policy.

No authentication or authorization model should be invented in this PR.

---

## Idempotency and concurrency

No user-facing write operations are introduced in this PR, so application-level idempotency handling is not required.

Database infrastructure must nevertheless avoid patterns that would prevent later transaction/concurrency handling.

In particular:

- do not create global mutable sessions;
- do not commit automatically from generic repository helpers;
- do not hide transaction ownership across unrelated abstraction layers.

Actual concurrency rules belong with the domain operations that require them.

---

## External services

There are no external business-service integrations in this PR.

The database and optional Sentry integration are infrastructure dependencies only.

Do not add generic HTTP client wrappers, retry libraries, provider interfaces, or circuit breakers before an actual provider use case exists.

---

## Testing

Use:

- pytest;
- Testcontainers;
- PostgreSQL.

SQLite must not be used as a substitute for PostgreSQL integration testing.

Application behaviour depending on PostgreSQL should be tested against PostgreSQL.

### Unit tests

Add focused tests for configuration and infrastructure behaviour where valuable.

Examples:

- valid configuration loads correctly;
- invalid required configuration fails clearly;
- optional Sentry configuration does not prevent startup.

Avoid unit tests whose only purpose is testing framework internals.

### API tests

Test:

```text
GET /health
```

Expected result:

```text
200
{"status": "ok"}
```

### Database integration tests

Provide shared fixtures capable of:

1. starting PostgreSQL using Testcontainers;
2. constructing the test database URL;
3. applying Alembic migrations;
4. opening application database sessions;
5. isolating tests appropriately;
6. cleaning resources after the test session.

At least one integration test must demonstrate successful communication with the real PostgreSQL test database.

### Migration test

Verify that a completely fresh PostgreSQL database can successfully run:

```text
alembic upgrade head
```

Where practical, verify that the migration state matches the expected head revision.

---

## Docker

Provide a production-oriented Dockerfile for the backend.

Requirements:

- Python 3.13 runtime;
- deterministic dependency installation;
- application code copied explicitly;
- sensible working directory;
- service starts through the canonical application entry point;
- development-only dependencies need not be included in the production image where the package setup supports separation.

Do not embed environment-specific credentials or `.env` files into the image.

---

## Local development

A developer should be able to:

1. install backend dependencies;
2. configure environment variables;
3. start PostgreSQL;
4. execute migrations;
5. run the FastAPI service;
6. call `/health`;
7. run the complete test suite.

Document the required commands in the appropriate backend README or existing project documentation.

---

## CI

Configure GitHub Actions, or extend the existing workflow, so backend changes can execute:

```text
dependency installation
→ static/configuration checks required by the repository
→ tests
→ migration/integration tests
```

Testcontainers may manage PostgreSQL itself where supported by the CI environment.

CI must fail when:

- tests fail;
- application imports fail;
- migrations cannot be applied to a fresh PostgreSQL database.

Do not add deployment infrastructure in this PR.

---

## Performance

There are no significant application performance requirements yet.

However:

- `/health` should have no unnecessary database or external-service calls;
- database engines must use normal SQLAlchemy connection pooling rather than opening a new engine for every request;
- application startup should not perform expensive external operations.

Premature caching or optimisation is out of scope.

---

## Data model

No product-domain schema is required in PR 1.

Do not create placeholder tables for:

- promotions;
- purchases;
- products;
- retailers;
- benefits;
- claims;
- eligibility results;
- users.

Those schemas should be introduced by the PR that owns their behaviour and invariants.

---

## AI boundary

No AI integration is introduced.

The foundation must not introduce OpenAI SDK dependencies, prompts, embeddings, vector databases, or generic LLM abstractions.

When AI capabilities are added later, they must remain outside the authoritative eligibility decision path.

---

## MCP boundary

No MCP server or MCP tools are introduced in this PR.

Future MCP tools and REST endpoints must reuse shared application/domain services.

Do not create MCP-specific business logic during foundation work.

---

## Failure semantics

Expected infrastructure failures should behave predictably.

### Invalid configuration

The application should fail startup with a clear configuration error rather than continue with an invalid configuration.

### PostgreSQL unavailable

Operations requiring the database must fail clearly.

The basic `/health` process endpoint may continue to report process health independently of database readiness.

### Migration failure

Migration commands must exit unsuccessfully and surface the underlying migration/database failure.

### Sentry unavailable or unconfigured

Missing optional Sentry configuration must not prevent local/test application startup.

---

## Acceptance criteria

### Service

- [ ] Backend runs on Python 3.13.
- [ ] FastAPI application starts successfully.
- [ ] There is one canonical application entry point.
- [ ] `GET /health` returns HTTP `200`.
- [ ] `/health` returns `{"status": "ok"}`.
- [ ] `/health` exposes no sensitive configuration.

### Configuration

- [ ] Configuration is centralised using Pydantic settings.
- [ ] Database configuration is environment-driven.
- [ ] Secrets are not committed.
- [ ] `.env.example` contains only safe example values.
- [ ] Invalid required configuration fails clearly.

### Database

- [ ] SQLAlchemy 2 is configured.
- [ ] PostgreSQL is the database used by application infrastructure.
- [ ] A reusable database-session dependency/factory exists.
- [ ] Sessions are correctly closed.
- [ ] Failed transactions can be rolled back.
- [ ] No request-shared global session exists.

### Migrations

- [ ] Alembic is configured.
- [ ] A fresh PostgreSQL database can run `alembic upgrade head`.
- [ ] Migration configuration uses the application's database configuration.
- [ ] Migrations do not run implicitly when the application starts.
- [ ] No speculative domain tables are introduced.

### Testing

- [ ] pytest is configured.
- [ ] `/health` is covered by an API test.
- [ ] PostgreSQL integration tests use Testcontainers.
- [ ] SQLite is not used as a substitute for PostgreSQL.
- [ ] Tests can apply Alembic migrations to a fresh test database.
- [ ] At least one test verifies actual PostgreSQL connectivity.
- [ ] Tests clean up their database/container resources.

### Observability

- [ ] Structured logging is configured.
- [ ] Sensitive configuration is not logged.
- [ ] Optional Sentry initialisation is supported.
- [ ] The application works without Sentry configured.

### Developer experience

- [ ] Backend dependencies are reproducible.
- [ ] Dockerfile is provided.
- [ ] Local setup is documented.
- [ ] Migration commands are documented.
- [ ] Test commands are documented.
- [ ] CI runs the backend test suite.

---

## Test plan

Run the service locally and verify:

```bash
curl http://localhost:<port>/health
```

returns:

```json
{
  "status": "ok"
}
```

Run:

```bash
pytest
```

and verify all unit and integration tests pass.

Against a fresh PostgreSQL database:

```bash
alembic upgrade head
```

must complete successfully.

Verify configuration failures by supplying an invalid or missing required database configuration and confirming that the application fails clearly without exposing secrets.

Verify the Docker image builds and the service can start from the built image with valid environment configuration.

---

## Definition of done

PR 1 is complete when a developer can clone the repository, configure the documented environment, start PostgreSQL, apply all migrations, start the FastAPI backend, receive a successful `/health` response, and execute the complete test suite against PostgreSQL.

The resulting foundation must be sufficient for subsequent PRs to add domain models, repositories, application services, REST endpoints, and MCP adapters without restructuring the core backend infrastructure.

---

## Completion report

When implementing this PR, the final implementation report should state:

- files/modules added or materially changed;
- configuration introduced;
- database/session approach used;
- Alembic revision created;
- test coverage added;
- commands executed;
- CI result where available;
- any deliberate deviation from this specification;
- any follow-up work deferred to later PRs.

Do not report the PR as complete if migrations or PostgreSQL integration tests have not actually been exercised.