# PR 4 — Promotion Lifecycle & History

## Repository state

**Expected branch:**
`pr4-promotion-lifecycle-history`

**Base branch:**
`main`

**Dependencies:**

- PR 1 — Project Foundation: merged.
- PR 2 — Foundation changes: merged.
- PR 3 — Core Promotion Schema: merged.
- Existing PostgreSQL, SQLAlchemy 2, Alembic, and Testcontainers foundation.
- `promotions.status` already contains the lifecycle states required by this task.
- No REST, MCP, ingestion, worker, scheduler, or frontend dependency.

### Read first

Before making changes, read:

- `AGENTS.md`
- nearest scoped `AGENTS.md`, if present
- `.codex/tasks/TEMPLATE.md`
- `.codex/tasks/pr-3-core-promotion-schema.md`
- `backend/README.md`
- `backend/app/db/models/core.py`
- `backend/app/db/models/__init__.py`
- `backend/migrations/versions/0002_core_promotion_schema.py`
- `backend/tests/conftest.py`
- `backend/tests/integration/test_core_promotion_schema.py`
- `backend/tests/integration/test_postgres_migrations.py`
- `backend/pyproject.toml`

### Primary change area

Promotion lifecycle domain/application behaviour and persistence queries.

PR 3 established the relational representation of promotion lifecycle state. PR 4 makes those states operational and ensures retirement retains promotion data. `expired` identifies historical published data; `archived` records are retained but may be unpublished candidates.

### Current repository state

`Promotion.status` already supports:

```text
discovered
extracted
review
active
expired
archived
```

through the database constraint:

```text
ck_promotions_status
```

PR 3 deliberately implemented persistence only. There is currently no:

- lifecycle transition service;
- promotion repository/query service;
- automatic state transition behaviour;
- publication workflow;
- promotion REST API;
- MCP promotion API.

The current database schema also permits explicit deletion of a promotion to cascade through promotion-owned records.

That low-level delete behaviour must **not** be used as the normal mechanism for expiring, withdrawing, superseding, or archiving promotions.

### Canonical implementation examples

Use:

- `Promotion` in `backend/app/db/models/core.py` as the persisted representation;
- lifecycle semantics already established by `.codex/tasks/pr-3-core-promotion-schema.md`;
- current SQLAlchemy 2 session patterns;
- existing PostgreSQL/Testcontainers fixtures;
- current migration conventions.

If a domain/application/repository convention has been added to `main` before implementation starts, follow that convention instead of creating a parallel architecture.

Do not introduce a generic repository framework solely for this task.

### Relevant symbols

Inspect before editing:

- `Promotion`
- `PromotionVariant`
- `PromotionVariantProduct`
- `Benefit`
- `Requirement`
- `PromotionSource`
- `Source`
- `Base`
- `db_session`
- `db_session_factory`
- `ck_promotions_status`
- `test_lifecycle_can_retain_incomplete_records`
- `test_published_and_historical_status_values`
- `test_owned_graph_cascades_preserve_references`

### Expected change surface

Expected additions or changes may include:

```text
backend/app/domain/
backend/app/application/
backend/app/db/repositories/
backend/tests/unit/
backend/tests/integration/
backend/README.md
```

Exact package names must follow architecture present on the implementation branch.

Expected responsibilities:

- one canonical Python lifecycle-state definition;
- deterministic lifecycle-transition validation;
- an application operation for changing promotion lifecycle state;
- persistence queries supporting lifecycle filters;
- active-promotion queries;
- historical-published promotion queries (expired only);
- general status-filtered queries for archived records;
- PostgreSQL tests proving expiration/archive preserve the promotion graph.

A database migration is **not expected** because PR 3 already introduced all required lifecycle states.

### Excluded areas

Do not implement:

- REST endpoints;
- MCP tools;
- purchase checking;
- eligibility evaluation;
- reward calculation;
- claim-window calculation;
- ingestion;
- scraping;
- AI extraction;
- source fetching;
- publication completeness validation;
- automatic promotion expiration;
- background workers;
- cron/scheduled jobs;
- frontend/UI;
- Redis;
- authentication/authorization;
- lifecycle event/audit tables;
- promotion versioning or supersession;
- hard-delete administration APIs;
- arbitrary rule engines.

This PR defines promotion retention using the existing promotion record itself. The current schema does not retain publication history for archived records.

A lifecycle event log recording every past transition is a separate concern.

### Unknowns Codex must verify

Before implementation:

- Verify PR 3 remains merged into `main`.
- Verify the current Alembic head.
- Verify the six current lifecycle values have not changed.
- Verify whether a scoped backend `AGENTS.md` now exists.
- Verify whether domain/application/repository conventions have been introduced since PR 3.
- Verify whether any promotion query or lifecycle code already exists.
- Verify transaction ownership from current repository state.
- Verify whether any application-level promotion deletion path has been added.
- Verify existing test and verification commands from current configuration.

Do not guess when repository state can answer the question.

---

## Objective

Implement explicit promotion lifecycle behaviour around the persistence model introduced in PR 3.

After this PR:

- promotion lifecycle states have one canonical application/domain representation;
- permitted lifecycle transitions are explicitly defined;
- invalid transitions are rejected;
- same-state transitions are idempotent;
- promotion expiration changes state rather than deleting data;
- promotion archival changes state rather than deleting data;
- expired promotions remain queryable;
- archived promotions remain queryable;
- promotion variants, benefits, requirements, product associations, and source provenance remain available after expiry or archival;
- only `expired` promotions are classified as historical published data;
- active promotions can be queried independently from historical published (`expired`) promotions;
- lookup by promotion identity does not hide non-active records;
- normal lifecycle code has no hard-delete path.

Completion means lifecycle behaviour, historical retention, persistence queries, concurrency behaviour, and PostgreSQL integration coverage are implemented and passing.

---

## Architecture and invariants

Preserve the repository dependency direction:

```text
transport
    ↓
application
    ↓
domain
    ↓
application-owned persistence boundary
    ↓
SQLAlchemy / PostgreSQL
```

No transport implementation is required by this PR.

Task-specific invariants:

1. Promotion lifecycle state is explicit and bounded.
2. Persisted lifecycle values remain exactly:

   ```text
   discovered
   extracted
   review
   active
   expired
   archived
   ```

3. Do not introduce a second promotion status/lifecycle column.
4. Do not introduce a PostgreSQL native enum.
5. Candidate states are:

   ```text
   discovered
   extracted
   review
   ```

6. `active` represents validated/published promotion data.
7. `expired` is the historical published state and unambiguously represents a previously published promotion retained for historical evaluation.
8. `archived` is retained data excluded from normal processing, whether or not it was ever published.
9. Archived promotions alone do not prove prior publication because candidate states may transition directly to `archived`.
10. Lifecycle transitions never delete the promotion.
11. Lifecycle transitions never delete promotion variants.
12. Lifecycle transitions never delete benefits.
13. Lifecycle transitions never delete requirements.
14. Lifecycle transitions never delete product associations.
15. Lifecycle transitions never delete source associations or provenance.
16. Direct promotion lookup must work for every lifecycle state.
17. Persistence must not impose an implicit global `status = 'active'` filter.
18. Active-only consumers must explicitly request active promotions.
19. Historical-published consumers must explicitly request `expired`.
20. Candidate promotions must not be mistaken for historical published promotions.
21. Archived records remain available by identity and explicit status filtering.
22. Lifecycle business rules belong outside SQLAlchemy ORM models.
23. Lifecycle behaviour must be deterministic.
24. Lifecycle transitions must not invoke an LLM or other external service.
25. Explicit low-level deletion may remain supported by the database, but deletion is not a lifecycle state transition.
26. Expiry, archival, withdrawal, or normal lifecycle retirement must never call `Session.delete()` or execute `DELETE FROM promotions`.

---

## API and contract changes

No REST or MCP contract changes.

This PR introduces internal application/domain and persistence contracts only.

### Required internal capabilities

The implementation must provide capabilities equivalent to:

```text
change_promotion_status(promotion_id, target_status)

get_promotion(promotion_id)

list_promotions(statuses=...)

list_active_promotions(...)

list_historical_promotions(...)
```

Names may differ to match established repository conventions.

Do not implement a general-purpose CRUD abstraction.

### Get promotion by ID

Lookup by promotion identity must:

- return `discovered` promotions;
- return `extracted` promotions;
- return `review` promotions;
- return `active` promotions;
- return `expired` promotions;
- return `archived` promotions;
- return not-found only when the promotion genuinely does not exist.

Expired or archived must not be interpreted as deleted.

### General lifecycle filtering

Persistence queries must support explicitly filtering by one or more valid lifecycle states.

Do not load every promotion and filter lifecycle state in Python.

### Active query

Active-specific queries return only:

```text
active
```

Candidate, expired, and archived states must not leak into normal active results.

### Historical-published query

`list_historical_promotions(...)` returns only:

```text
expired
```

An explicit state filter may be omitted or contain only `expired`. Supplying `archived` or any other state is invalid for this historical-published query.

`discovered`, `extracted`, and `review` are candidate states, not historical published promotions. `archived` is also excluded because it may represent either a formerly published promotion or an abandoned candidate.

Archived promotions remain queryable through `get_promotion(promotion_id)` and `list_promotions(statuses=[PromotionStatus.ARCHIVED])`.

### Ordering

Multi-row queries introduced by this PR must have deterministic ordering.

Follow an existing repository convention if one exists.

Otherwise prefer a stable order such as:

```text
created_at DESC, id
```

Do not rely on incidental PostgreSQL row order.

---

## Domain and application behaviour

### Canonical lifecycle type

Define lifecycle states once in domain/application code.

A Python `StrEnum` or equivalent strongly typed domain representation is appropriate.

Persisted values must remain exactly compatible with PR 3.

Avoid scattering lifecycle string literals across application and persistence code.

### Lifecycle semantics

#### `discovered`

Promotion identity or evidence has been found, but structured promotion data may be incomplete.

Not published.

#### `extracted`

Structured candidate data exists.

Not published.

#### `review`

Candidate promotion data is awaiting or undergoing validation/review.

Not published.

#### `active`

Validated/published promotion available for normal runtime consideration.

#### `expired`

Previously active promotion that is no longer current.

The promotion and its complete graph remain persisted and queryable as historical published data.

#### `archived`

Retained promotion excluded from normal processing. It may be an abandoned/unpublished candidate or a formerly published promotion. Archiving is not deletion and does not establish prior publication.

The current schema does not retain enough information to distinguish `active → archived` from `discovered → archived`, `extracted → archived`, or `review → archived` once only the final state remains. Archived records therefore are not classified as historical published promotions. Distinguishing these cases requires future publication history, lifecycle event history, or promotion versioning/supersession, all outside this PR.

### Allowed transitions

Implement an explicit transition matrix.

Initial allowed transitions:

```text
discovered → extracted
discovered → archived

extracted → review
extracted → archived

review → extracted
review → active
review → archived

active → expired
active → archived

expired → archived
```

`review → extracted` supports returning candidate data for correction.

### Same-state transitions

Same-state requests are idempotent no-ops.

Examples:

```text
active → active
expired → expired
archived → archived
```

They must succeed without recreating data or producing duplicate effects.

### Invalid transitions

All transitions not explicitly allowed above are rejected.

Examples:

```text
discovered → active
extracted → active
expired → active
expired → review
archived → active
archived → discovered
```

Candidate data must not bypass review/publication.

Expired historical published data must not simply be mutated back into an active promotion because this could rewrite historical meaning. Archived records also cannot be reactivated under the transition matrix.

Republishing or superseding a historical promotion belongs to later promotion-versioning/publication work.

### Errors

Lifecycle logic must distinguish:

- promotion not found;
- invalid lifecycle transition;
- concurrent lifecycle conflict;
- database/infrastructure failure.

Do not expose SQLAlchemy exceptions as lifecycle-domain errors.

### Transaction boundary

Changing lifecycle state must be atomic.

Conceptually:

```text
load current persisted status
→ validate requested transition
→ persist lifecycle update
→ commit
```

If any step fails before commit, the previous status remains authoritative.

### Concurrency

Do not implement an unsafe stale read followed by an unconditional update.

Two concurrent lifecycle operations must not silently overwrite one another.

Prefer an atomic conditional update conceptually equivalent to:

```sql
UPDATE promotions
SET status = :target
WHERE id = :promotion_id
  AND status = :expected;
```

or an established repository row-locking/optimistic-concurrency mechanism.

If no row is updated because another transaction changed the status:

- reload/reconcile current state;
- if it already equals the requested target, treat the operation as idempotent success;
- otherwise return a lifecycle/concurrency conflict.

Do not introduce distributed locks.

### Expiration timing

This PR does not automatically detect when promotions should expire.

Do not introduce:

- cron;
- workers;
- schedulers;
- startup scans;
- read-time mutation.

A later ingestion/operations task may call the lifecycle application operation when expiration is detected.

Reading an active promotion whose `purchase_end_date` is in the past must not silently mutate it.

### Retained promotion data

Transitioning to `expired` or `archived` changes lifecycle state only. Both states retain records and provenance; only `expired` is classified as historical published data.

It must not modify or remove:

- promotion dates;
- variants;
- retailer associations;
- product associations;
- benefits;
- requirements;
- source provenance.

Historical correction/versioning is outside this PR.

---

## Persistence, transactions, and migrations

### Existing schema

PR 3 already provides:

```text
promotions.status VARCHAR(32) NOT NULL
```

and:

```text
ck_promotions_status
```

with all six lifecycle values.

Do not duplicate this schema.

### Migration requirement

No migration is expected.

Do not modify:

```text
backend/migrations/versions/0002_core_promotion_schema.py
```

to retrofit application behaviour into deployed migration history.

If implementation-branch repository state demonstrates that a database change is genuinely required:

- create a new Alembic revision;
- do not edit deployed migrations;
- explain why;
- verify the migration against real PostgreSQL.

### Retention behaviour

These transitions must perform `UPDATE`, not `DELETE`:

```text
active → expired
active → archived
expired → archived
```

After each transition, the following remain persisted:

- promotion;
- promotion variants;
- promotion/product links;
- benefits;
- requirements;
- promotion/source links;
- referenced sources;
- referenced manufacturer;
- referenced products;
- referenced retailers.

### Existing deletion cascade

PR 3 intentionally allows explicitly deleting a promotion to cascade through owned child rows.

Do not alter this behaviour merely to implement lifecycle retention.

A database `ON DELETE CASCADE` defines what happens **if deletion occurs**.

The lifecycle invariant is instead that normal retirement **does not perform deletion**.

### Persistence boundary

Introduce the smallest promotion-specific persistence abstraction necessary for:

- lookup;
- lifecycle update;
- lifecycle filtering;
- active queries;
- historical-published queries (expired only).

Do not introduce a generic `Repository[T]`.

### Indexes

Do not add a status index speculatively.

The dataset is currently small and there is not yet evidence that lifecycle filtering requires a dedicated index.

If query behaviour later demonstrates a need, introduce the index through a separate justified migration.

---

## External services and network access

None.

This PR must not call:

- manufacturer websites;
- retailer websites;
- model providers;
- external APIs;
- Redis;
- queues.

---

## Security and privacy

There is no new external authorization boundary.

Still preserve:

- lifecycle inputs validated against the canonical state type;
- parameterized SQLAlchemy queries;
- no raw SQL interpolation using status values;
- no leaking database exceptions through domain/application contracts;
- provenance retained for expired historical published promotions and archived records;
- no full source-document logging.

No new credentials, secrets, or PII are required.

---

## Configuration and deployment

None.

No new:

- environment variables;
- Docker services;
- worker processes;
- scheduled jobs;
- Railway settings;
- credentials;
- health/readiness behaviour.

Startup must not mutate promotion lifecycle state.

---

## Observability and operations

Do not introduce a new telemetry stack.

Where lifecycle operations cross an existing structured logging boundary, useful fields are:

```text
promotion_id
previous_status
target_status
result
```

Useful result categories:

```text
changed
no_op
invalid_transition
not_found
conflict
failure
```

Expected invalid domain transitions are not infrastructure failures.

Do not log entire promotion graphs or complete source documents.

---

## Failure, consistency, and recovery

### Promotion not found

Return the established application not-found result.

Do not implicitly create a promotion.

### Invalid transition

Reject the transition.

The persisted lifecycle state remains unchanged.

### Same-state transition

Return idempotent success/no-op.

### Database failure before commit

Rollback.

The previous lifecycle state remains authoritative.

### Successful commit

The new status is immediately authoritative and queryable by identity/status; `expired` is returned by historical-published queries, while `archived` is not.

No second persistence operation is required.

### Concurrent update

Never silently overwrite a newer lifecycle state.

Resolve as either:

- same-state idempotent success; or
- explicit concurrency/lifecycle conflict.

### Expire/archive operation

A successful lifecycle transition that causes owned promotion records or source provenance to disappear is a defect.

### Query failure

Do not translate infrastructure errors into:

- empty results;
- not found;
- invalid lifecycle transitions.

Surface them through the established application failure boundary.

---

## Acceptance criteria

### Lifecycle

- [ ] One canonical Python lifecycle-state representation exists.
- [ ] Persisted lifecycle values remain unchanged from PR 3.
- [ ] Allowed transitions are explicit.
- [ ] Every allowed transition is tested.
- [ ] Invalid transitions are rejected.
- [ ] Same-state transitions are idempotent.
- [ ] Candidate states cannot skip directly to `active`.
- [ ] `expired` cannot directly return to `active`.
- [ ] `archived` cannot directly return to `active`.
- [ ] Lifecycle operations perform no promotion hard deletes.
- [ ] Lifecycle logic is independent of LLMs, network services, workers, and schedulers.

### Query behaviour

- [ ] Lookup by ID returns candidate promotions.
- [ ] Lookup by ID returns active promotions.
- [ ] Lookup by ID returns expired promotions.
- [ ] Lookup by ID returns archived promotions.
- [ ] Active queries return only `active`.
- [ ] Historical-published queries return `expired` and do not return `archived`.
- [ ] `list_historical_promotions([expired])` works; archived is rejected as a historical-published filter.
- [ ] Candidate promotions are not classified as historical published promotions.
- [ ] Archived candidates remain retrievable by ID and explicit archived status filtering.
- [ ] Active → archived promotions remain retrievable by explicit archived status filtering.
- [ ] No implicit active-only filter hides archived or expired records from identity/general queries.
- [ ] Multi-row query ordering is deterministic.

### Historical retention

- [ ] `active → expired` retains the promotion.
- [ ] `active → archived` retains the promotion.
- [ ] `expired → archived` retains the promotion.
- [ ] Promotion variants remain queryable after expiry.
- [ ] Product associations remain after expiry.
- [ ] Benefits remain after expiry.
- [ ] Requirements remain after expiry.
- [ ] Promotion/source associations remain after expiry.
- [ ] Source provenance remains available after expiry and archival.
- [ ] Lifecycle operations never execute `Session.delete(promotion)`.
- [ ] Lifecycle operations never execute `DELETE FROM promotions`.

### Consistency

- [ ] Status updates are atomic.
- [ ] Failed transitions leave persisted state unchanged.
- [ ] Concurrent lifecycle changes cannot silently overwrite one another.
- [ ] Repeated same-state requests do not introduce duplicate effects.
- [ ] Database failures remain distinguishable from lifecycle-domain results.

### Schema

- [ ] No duplicate lifecycle/status column is introduced.
- [ ] No PostgreSQL enum is introduced.
- [ ] Existing Alembic migrations are not rewritten.
- [ ] No new migration is added unless repository state proves one is required.

### Architecture

- [ ] Lifecycle rules do not import SQLAlchemy.
- [ ] SQLAlchemy models remain persistence concerns.
- [ ] Application code owns lifecycle orchestration.
- [ ] SQL querying remains behind the persistence boundary.
- [ ] No generic repository framework is introduced.
- [ ] No REST or MCP surface is added.

---

## Tests to add or update

### Unit tests

Add lifecycle unit coverage, preferably:

```text
backend/tests/unit/test_promotion_lifecycle.py
```

Cover:

- all allowed transitions;
- forbidden candidate-to-active bypasses;
- expired-to-active rejection;
- archived-to-active rejection;
- same-state idempotency;
- all six lifecycle values;
- stable lifecycle error/result behaviour.

These tests must not require PostgreSQL.

### PostgreSQL integration tests

Add focused lifecycle persistence coverage, preferably:

```text
backend/tests/integration/test_promotion_lifecycle.py
```

Use the existing Testcontainers/PostgreSQL infrastructure.

At minimum:

1. create a complete `active` promotion graph;
2. transition it to `expired`;
3. clear/close the current ORM state;
4. reload the promotion;
5. verify the promotion still exists;
6. verify variants still exist;
7. verify product associations still exist;
8. verify benefits still exist;
9. verify requirements still exist;
10. verify promotion/source links still exist;
11. verify source provenance remains reachable;
12. verify the expired promotion appears in historical-published queries;
13. verify it no longer appears in active queries.

Add equivalent retention coverage for archival.

Also cover:

- `list_historical_promotions()` returns `expired` and excludes `archived`;
- `list_historical_promotions([expired])` works; explicit `archived` is rejected;
- candidate → archived remains retrievable by ID and explicit archived status filtering;
- active → archived remains retrievable by explicit archived status filtering;
- active-only queries return only active;
- lookup by ID returns all six lifecycle states;
- explicit multi-status filtering;
- deterministic query ordering;
- invalid transition rollback;
- stale/concurrent update handling.

### Existing regression tests

The existing:

```text
backend/tests/integration/test_core_promotion_schema.py
```

must continue to pass.

In particular, do **not** remove or weaken its explicit deletion/cascade coverage.

Explicit database deletion and normal lifecycle retirement are different behaviours.

### REST tests

N/A.

### MCP tests

N/A.

### External-service tests

N/A.

---

## Verification commands

Run from:

```text
backend/
```

### Dependency sync

```bash
uv sync --locked --extra dev
```

### Formatting

```bash
uv run ruff format --check .
```

### Lint

```bash
uv run ruff check .
```

### Targeted unit tests

```bash
uv run pytest tests/unit/test_promotion_lifecycle.py
```

Use the actual test path if repository conventions result in another filename.

### Targeted PostgreSQL integration tests

```bash
uv run pytest tests/integration/test_promotion_lifecycle.py
```

Docker must be available.

### Existing promotion-schema regression

```bash
uv run pytest tests/integration/test_core_promotion_schema.py
```

### Broader backend suite

```bash
uv run pytest
```

### Type checking

N/A based on the current `backend/pyproject.toml`.

Do not introduce mypy or another static type-checking dependency solely for this task.

### Migration verification

No migration is expected.

If repository state legitimately requires one, run the repository's PostgreSQL migration verification and at minimum:

```bash
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head
```

against a disposable PostgreSQL database.

If a required command cannot run, report:

1. the exact command;
2. why it could not run;
3. what was verified instead;
4. remaining risk.

Never report an unrun check as passed.

---

## Completion report

### Changed

Summarise:

- lifecycle domain representation;
- transition rules;
- lifecycle application operation;
- active/history persistence queries;
- historical retention behaviour.

### Database and migrations

Expected:

```text
None.
```

If different, list the new migration and justification.

### API/MCP contracts

Expected:

```text
None.
```

### Tests and verification

Report:

- unit tests added/updated;
- PostgreSQL integration tests added/updated;
- regression tests run;
- Ruff commands run;
- full pytest result;
- migration checks if applicable.

### External configuration

Expected:

```text
None.
```

### Deviations

State meaningful deviations from this specification and why.

Otherwise:

```text
None.
```

### Remaining risks or follow-up

Potential later work includes:

- publication completeness validation;
- automated expiration detection/scheduling;
- promotion versioning and supersession;
- lifecycle audit/event history;
- administrative REST/MCP lifecycle operations;
- eligibility behaviour using active and expired historical-published promotion data.
- Persisted publication/lifecycle history to distinguish formerly published archives from never-published archives.

Do not implement those as part of PR 4 unless explicitly required.
