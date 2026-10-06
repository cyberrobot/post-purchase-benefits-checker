# Post-Purchase Benefits Checker backend

Python 3.13, FastAPI, SQLAlchemy 2, and PostgreSQL foundation. The service currently exposes only process health; product and eligibility behaviour will be added in later changes.

The full [PR 1 project foundation specification](../.codex/tasks/pr-1-project-foundation.md) is kept in this repository.

## Local setup

From `backend/`:

```bash
uv sync --locked --extra dev
source .venv/bin/activate
cp .env.example .env
docker compose -p benefits-checker up -d postgres
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

`GET http://localhost:8000/health` returns `{"status":"ok"}` without querying PostgreSQL. `DATABASE_URL` is required and must be a PostgreSQL URL. The example credentials are for local development only.

## Migrations

Alembic reads the same validated `DATABASE_URL` setting as the application:

```bash
uv run alembic upgrade head
uv run alembic downgrade -1
```

Migrations run explicitly; application startup never modifies the schema.

## Tests and checks

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

The PostgreSQL integration test starts a disposable PostgreSQL Testcontainer, runs the migration against a fresh database, and verifies a real query. It requires Docker to be available to the current user.

## Docker image

Build from this directory with `docker build -t benefits-checker-api .`. Provide `DATABASE_URL` at runtime. Run migrations separately before serving traffic:

```bash
docker run --rm -e DATABASE_URL='postgresql+psycopg://...' -p 8000:8000 benefits-checker-api
```

## Configuration

| Variable       | Required | Description                                                     |
| -------------- | -------- | --------------------------------------------------------------- |
| `APP_ENV`      | No       | `development`, `test`, or `production` (default: `development`) |
| `DATABASE_URL` | Yes      | PostgreSQL SQLAlchemy URL using the psycopg 3 driver            |
| `LOG_LEVEL`    | No       | Standard log level (default: `INFO`)                            |
| `SENTRY_DSN`   | No       | Enables Sentry when set; PII and local variables are disabled   |

## Future publication validation

Every product associated with a promotion variant must belong to the same manufacturer
as the parent promotion. PR 3's foreign keys enforce reference existence, but do not
enforce this cross-table invariant. A later domain/application publication boundary
must enforce it before activation, together with promotion completeness validation.
Candidate states (`discovered`, `extracted`, and `review`) may remain incomplete;
`active` represents validated/published data. Publication validation is outside PR 3.

## Promotion lifecycle and history

`app.domain.promotion_lifecycle.PromotionStatus` defines the six existing persisted
states. Candidate transitions are discovered → extracted → review; review may return
to extracted or move to active. Active may expire; any non-archived state may archive.
Historical states cannot reactivate. Same-state requests are no-ops.

Call `change_promotion_status(partial(promotion_transaction, session_factory), id, status)`
from the application layer. The operation owns a dedicated session and transaction,
commits before returning, and rolls back on failure. The repository conditionally
updates the expected state; a competing write is reconciled as an already-completed
no-op or `PromotionConflict`. Not-found, invalid-transition, and persistence failures
are distinct exceptions. Do not share a session containing pending ORM changes.

`SqlAlchemyPromotionRepository` returns immutable application records rather than ORM
objects. Identity lookup includes every state. General queries accept explicit state
filters; active queries select only active, historical queries select expired/archived
and optionally a narrower subset. Results order by `created_at DESC, id ASC`.
The complete retained graph remains accessible through the existing persistence models.
Archival can include discarded candidates, so archival alone does not prove publication.

Retirement updates status and the normal update timestamp, preserving dates, graph,
references, and provenance. No reads or startup paths expire promotions automatically.
This internal lifecycle operation does not validate publication completeness; callers
must establish that separately before requesting review → active. No transport API,
new migration, audit log, or versioning workflow is introduced.
