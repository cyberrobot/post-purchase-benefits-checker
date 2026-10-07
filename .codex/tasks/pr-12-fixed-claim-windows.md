# PR 12 — Fixed Claim Windows

## Repository state

**Expected branch:**  
`pr12-fixed-claim-windows`

**Base branch:**  
`main`

**Dependencies:**  
- PR 3 — Core Promotion Schema: merged; `promotions` currently owns promotion-level purchase dates and has no claim-window columns.
- PR 4 — Promotion Lifecycle & History: merged; promotion lifecycle state remains distinct from claim-window state.
- PR 6 — Promotion Source Provenance: merged; publication provenance behaviour remains unchanged.
- PR 10 — Core Eligibility Rules: merged; purchase eligibility rules remain separate from claim timing.
- PR 11 — Eligibility Result Classification: merged; `ClaimWindowStatus` is the canonical `open` / `not_yet_open` / `expired` contract consumed by final classification.
- Existing PostgreSQL, SQLAlchemy 2, Alembic, pytest, Ruff, and Testcontainers backend foundation.
- No new runtime package, external provider, worker, or infrastructure dependency.

### Read first

Before making changes, read:

- `AGENTS.md`
- `.codex/tasks/TEMPLATE.md`
- `.codex/tasks/pr-3-core-promotion-schema.md`
- `.codex/tasks/pr-4-promotion-lifecycle-history.md`
- `.codex/tasks/pr-10-core-eligibility-rules.md`
- `.codex/tasks/pr-11-eligibility-result-classification.md`
- `backend/README.md`
- `backend/app/db/models/core.py`
- `backend/app/application/promotions.py`
- `backend/app/db/repositories/promotions.py`
- `backend/app/domain/eligibility_result.py`
- `backend/app/domain/promotion_lifecycle.py`
- latest file under `backend/migrations/versions/`
- `backend/tests/integration/test_core_promotion_schema.py`
- `backend/tests/integration/test_postgres_migrations.py`
- `backend/tests/integration/test_promotion_lifecycle.py`
- `backend/tests/unit/test_eligibility_result.py`

As of the current `main` branch there is no scoped `backend/AGENTS.md`. If one exists on the implementation branch, read and follow it.

### Primary change area

Claim-window domain logic plus additive promotion persistence.

This PR introduces:

- persisted fixed claim-opening and claim-deadline calendar dates for promotions;
- a pure deterministic fixed-window evaluator;
- reuse of PR 11 `ClaimWindowStatus` rather than a parallel status contract.

### Canonical implementation examples

Treat these as the preferred implementation references:

- `backend/app/domain/eligibility_result.py`
  - canonical `ClaimWindowStatus` values;
  - immutable deterministic domain values;
  - strict type validation;
  - no clock, persistence, network, or framework dependency.
- `backend/app/domain/eligibility_rules.py`
  - calendar `date` validation;
  - immutable value objects;
  - explicit inclusive date-bound semantics;
  - domain-only deterministic evaluation.
- `backend/app/db/models/core.py`
  - promotion-level date persistence;
  - SQLAlchemy typing and CHECK-constraint conventions.
- `backend/app/application/promotions.py`
  - immutable `PromotionRecord` application contract.
- `backend/app/db/repositories/promotions.py`
  - ORM-to-application record mapping;
  - safe persistence boundary.
- current Alembic migration head
  - additive schema-change conventions.
- PostgreSQL integration tests
  - real PostgreSQL constraint and migration verification.

Do not introduce a generic temporal rules engine, date-expression DSL, dynamic rule execution, or AI/LLM-based claim timing.

### Relevant symbols

Inspect at minimum:

- `Promotion`
- `PromotionRecord`
- `SqlAlchemyPromotionRepository`
- `_record`
- `PromotionStatus`
- `ClaimWindowStatus`
- `EligibilityClassification`
- `EligibilityResult`
- `classify_eligibility`
- shared purchase/date validation helpers, if any
- current Alembic head and promotion-table constraints

### Expected change surface

Expected changes should remain focused in:

```text
backend/app/domain/
backend/app/db/models/core.py
backend/app/application/promotions.py
backend/app/db/repositories/promotions.py
backend/migrations/versions/
backend/tests/unit/
backend/tests/integration/
backend/README.md
```

Likely additions/updates include:

```text
backend/app/domain/claim_windows.py
backend/app/db/models/core.py
backend/app/application/promotions.py
backend/app/db/repositories/promotions.py
backend/migrations/versions/0004_fixed_claim_windows.py
backend/tests/unit/test_claim_windows.py
backend/tests/integration/test_fixed_claim_windows.py
backend/tests/integration/test_postgres_migrations.py
backend/README.md
```

The migration filename/revision above is expected from the current repository state. Codex must verify the actual Alembic head before creating it and use the correct next revision.

A small update to existing promotion lifecycle/repository tests is acceptable when `PromotionRecord` gains the persisted claim-date fields.

### Excluded areas

Do not implement:

- relative claim deadlines such as `claim within 30 days of purchase`;
- delayed claim windows such as `claim between 30 and 60 days after purchase`;
- any claim date derived from `purchase_date`;
- duration/offset-based claim rules;
- a generic `claim_rule`, `claim_window_type`, or extensible rule DSL solely for future claim-window types;
- evaluation against `date.today()`, `datetime.now()`, or any other system clock;
- timezone conversion or timestamp claim semantics;
- final `check_purchase` orchestration;
- mapping promotion candidates into final eligibility results;
- promotion precedence or winner/best-promotion selection;
- changes to PR 11 classification values or precedence;
- changes to PR 10 eligibility-rule semantics;
- changes to `CheckPurchaseRequest`;
- changes to promotion candidate matching or candidate query filtering;
- automatic lifecycle expiry when a claim deadline passes;
- deriving claim status from `PromotionStatus.EXPIRED`;
- benefit calculation;
- cashback calculation;
- warranty duration calculation;
- free-gift calculation;
- promotion requirements or requirement satisfaction;
- claim submission records;
- claim processing workflows;
- REST routes;
- FastAPI request/response schemas;
- MCP tools;
- OpenAPI changes;
- scraping or ingestion;
- external provider calls;
- AI/LLM evaluation;
- frontend behaviour.

### Unknowns Codex must verify

Before implementation verify:

- PR 11 remains the canonical owner of `ClaimWindowStatus` and still defines exactly:
  - `open`;
  - `not_yet_open`;
  - `expired`.
- No fixed claim-window model/evaluator has appeared since this specification was written.
- `Promotion` still has only `purchase_start_date` and `purchase_end_date` as promotion-level business dates.
- `PromotionRecord` still mirrors promotion-level persisted fields.
- PR 9 candidate matching still excludes claim-window evaluation.
- `PromotionStatus.EXPIRED` still means historical published lifecycle state rather than claim expiry.
- No configured backend type-check command exists unless repository configuration has changed.
- Current Alembic head is verified from repository state before naming the migration.
- Existing migration and PostgreSQL integration-test conventions still match `backend/README.md` and current tests.

Do not create parallel concepts when the repository already contains an equivalent implementation.

---

## Objective

After PR 12, the backend must support promotions with a **fixed calendar claim window** consisting of:

```text
claim start date
claim end/deadline date
```

For this PR the persisted promotion fields are:

```text
claim_start_date
claim_end_date
```

Their semantics are:

```text
claim_start_date = first calendar date on which a claim may be submitted
claim_end_date   = last calendar date on which a claim may be submitted
```

Both boundaries are inclusive.

A promotion may have no fixed claim window, represented by:

```text
claim_start_date = NULL
claim_end_date   = NULL
```

A configured fixed claim window is atomic: both dates must be present and valid.

The domain layer must expose a pure deterministic fixed-window evaluator that accepts:

```text
fixed claim window
+
explicit evaluation date
```

and returns the existing PR 11 claim-window state:

```text
evaluation_date < claim_start_date
→ ClaimWindowStatus.NOT_YET_OPEN

claim_start_date <= evaluation_date <= claim_end_date
→ ClaimWindowStatus.OPEN

evaluation_date > claim_end_date
→ ClaimWindowStatus.EXPIRED
```

The evaluator must also retain/expose the fixed opening and deadline dates through its typed domain result so later application orchestration can explain when the claim opens and when it expires without recalculating the window.

PR 12 must not use the current system date implicitly. The caller supplies the evaluation date.

PR 12 is complete when:

- fixed claim dates can be persisted safely on a promotion;
- invalid or partial fixed windows cannot be stored as valid promotion data;
- fixed windows can be evaluated deterministically for a supplied calendar date;
- the result reuses PR 11 `ClaimWindowStatus`;
- opening/deadline boundaries are covered by tests;
- existing promotions remain valid after migration with no fixed window configured;
- no relative/delayed claim logic or final purchase-check orchestration is introduced.

---

## Architecture and invariants

Preserve the existing backend boundaries:

```text
PostgreSQL promotion record
        ↓
application/repository mapping
        ↓
typed fixed claim-window domain value
        ↓
pure fixed-window evaluation
        ↓
existing ClaimWindowStatus
        ↓
PR 11 classifier (future orchestration)
```

### Required invariants

1. **Fixed claim timing is promotion-level data.**

   The new dates belong to `promotions`, matching the task requirement and the existing promotion-level purchase-date model.

   Do not move fixed claim dates onto individual `promotion_variants` in this PR.

2. **A fixed window is complete or absent.**

   Valid persisted states are:

   ```text
   both NULL
   ```

   or:

   ```text
   both non-NULL
   ```

   A row with only one claim date is invalid.

3. **Configured fixed dates are ordered.**

   ```text
   claim_start_date <= claim_end_date
   ```

   A one-day claim window is valid.

4. **Claim status is derived from an explicit evaluation date.**

   No system clock access belongs in the domain evaluator.

5. **Calendar dates remain calendar dates.**

   Use Python `date` / PostgreSQL `DATE` semantics.

   Do not accept a `datetime` as a domain `date`, even though `datetime` subclasses `date` in Python.

6. **Claim-window state and promotion lifecycle state remain independent.**

   Never infer:

   ```text
   PromotionStatus.EXPIRED
   → ClaimWindowStatus.EXPIRED
   ```

   and never automatically mutate promotion lifecycle state because the fixed claim deadline has passed.

7. **PR 11 owns the claim-window status vocabulary.**

   Reuse `ClaimWindowStatus`; do not define a duplicate enum.

8. **Absence of a fixed window does not mean `OPEN`.**

   `NULL` / `NULL` means this promotion has no fixed claim-window definition in PR 12. It must not be silently interpreted as an always-open claim period.

   Future application/publication work may decide whether every published promotion must have some supported claim-window type.

9. **Runtime decisions remain deterministic.**

   No LLM, network, persistence query, environment configuration, or random value may influence fixed-window evaluation.

10. **Do not add future claim-window abstractions prematurely.**

    Relative/delayed windows are separate follow-up work. Add only the minimum fixed-window contract needed now.

---

## API and contract changes

No public REST, MCP, or OpenAPI contract changes.

### Internal domain contract

Add a fixed claim-window value, conceptually:

```python
@dataclass(frozen=True, slots=True)
class FixedClaimWindow:
    start_date: date
    end_date: date
```

Construction requirements:

- `start_date` must be a Python calendar `date`, not `datetime`;
- `end_date` must be a Python calendar `date`, not `datetime`;
- `start_date <= end_date`;
- wrong types raise `TypeError`;
- inverted bounds raise `ValueError`.

Add a typed evaluation result, conceptually:

```python
@dataclass(frozen=True, slots=True)
class ClaimWindowEvaluation:
    status: ClaimWindowStatus
    opens_on: date
    deadline_on: date
```

The exact symbol names may follow established repository naming conventions, but the contract must preserve:

- canonical PR 11 status;
- opening date;
- deadline date;
- immutability;
- deterministic equality.

Add a pure evaluator, conceptually:

```python
evaluate_fixed_claim_window(
    window: FixedClaimWindow,
    evaluation_date: date,
) -> ClaimWindowEvaluation
```

Do not accept raw persisted `None` values in this evaluator. Persistence-to-domain mapping must construct a fixed window only when both stored dates are present.

### Internal application persistence contract

Update `PromotionRecord` to expose:

```text
claim_start_date: date | None
claim_end_date: date | None
```

Preserve existing field semantics and lifecycle behaviour.

This is an internal application contract change only.

### Backward compatibility

Existing promotions with no fixed claim window must continue to load successfully with:

```text
claim_start_date = None
claim_end_date = None
```

No existing caller may be forced to synthesize fake claim dates.

---

## Domain and application behaviour

### Fixed claim-window evaluation

Given:

```text
start = 2026-11-01
end   = 2026-11-30
```

#### Before opening

```text
evaluation_date = 2026-10-31
→ NOT_YET_OPEN
```

The returned evaluation must preserve:

```text
opens_on = 2026-11-01
deadline_on = 2026-11-30
```

#### Opening boundary

```text
evaluation_date = 2026-11-01
→ OPEN
```

The opening day is claimable.

#### Inside window

```text
evaluation_date = 2026-11-15
→ OPEN
```

#### Deadline boundary

```text
evaluation_date = 2026-11-30
→ OPEN
```

The deadline day is claimable.

#### After deadline

```text
evaluation_date = 2026-12-01
→ EXPIRED
```

### One-day fixed window

This is valid:

```text
start = 2026-11-30
end   = 2026-11-30
```

Required behaviour:

```text
2026-11-29 → NOT_YET_OPEN
2026-11-30 → OPEN
2026-12-01 → EXPIRED
```

### Relation to purchase eligibility

Fixed claim timing must not evaluate:

- manufacturer;
- model/SKU/product;
- retailer;
- purchase channel;
- purchase date eligibility;
- purchase price;
- condition;
- country.

PR 10 owns those rule outcomes.

A fixed claim window is evaluated independently and later supplied to PR 11 classification by future application orchestration.

### Relation to purchase date

A fixed claim window is absolute calendar data.

The evaluator must not receive or use `purchase_date` to derive its boundaries.

For example:

```text
promotion fixed claim window:
2026-11-01 through 2026-11-30
```

remains those dates for every otherwise applicable purchase.

Purchase-relative and delayed windows belong to a later PR.

### Relation to lifecycle

A claim window may be:

```text
OPEN
NOT_YET_OPEN
EXPIRED
```

without causing any lifecycle state transition.

Likewise a historical `PromotionStatus.EXPIRED` record must not bypass fixed-window evaluation or be treated as claim-expired by definition.

### Missing fixed claim window

Persistence may return:

```text
claim_start_date = None
claim_end_date = None
```

This represents absence of a fixed-window definition.

PR 12 must not convert absence into any `ClaimWindowStatus`.

Do not add an `UNKNOWN`, `NONE`, or `UNBOUNDED` member to PR 11 `ClaimWindowStatus` in this PR.

### Partial persisted window

The database must reject:

```text
claim_start_date set + claim_end_date NULL
```

and:

```text
claim_start_date NULL + claim_end_date set
```

Application/domain code must not normalize or guess the missing bound.

### Invalid order

Reject:

```text
claim_start_date > claim_end_date
```

Do not swap the values automatically.

### Determinism

Equivalent inputs must always produce equivalent results:

```text
same fixed window
+
same evaluation date
→ same ClaimWindowEvaluation
```

---

## Persistence, transactions, and migrations

### `promotions` table

Add nullable PostgreSQL `DATE` columns:

| Column | Requirements |
| --- | --- |
| `claim_start_date` | nullable `DATE`; first date a fixed claim may be submitted |
| `claim_end_date` | nullable `DATE`; last date a fixed claim may be submitted |

Add database constraints enforcing the fixed-window invariants.

Conceptually:

```sql
(
  claim_start_date IS NULL
  AND claim_end_date IS NULL
)
OR
(
  claim_start_date IS NOT NULL
  AND claim_end_date IS NOT NULL
)
```

and:

```sql
claim_start_date <= claim_end_date
```

Use repository naming conventions for stable CHECK-constraint names.

Expected names may be similar to:

```text
ck_promotions_claim_dates_complete
ck_promotions_claim_dates
```

but Codex must follow existing naming style and avoid collisions.

### SQLAlchemy model

Update `Promotion` with:

```python
claim_start_date: Mapped[date | None] = mapped_column(Date)
claim_end_date: Mapped[date | None] = mapped_column(Date)
```

and matching CHECK constraints.

Do not add indexes for the claim dates in PR 12.

There is no demonstrated query that filters promotions by fixed claim date yet; speculative indexes are out of scope.

### Application/repository mapping

Update `PromotionRecord` and `_record(...)` so promotion reads preserve both claim dates.

Do not change repository transaction ownership.

Do not add claim-window business logic inside SQLAlchemy repositories.

### Migration

Create one additive Alembic migration from the verified current head.

From current `main`, the expected revision is conceptually:

```text
0004_fixed_claim_windows
```

The migration must:

1. add both nullable `DATE` columns;
2. add the complete-pair CHECK constraint;
3. add the ordered-date CHECK constraint;
4. preserve all existing promotion rows and graph data;
5. require no data backfill;
6. leave existing rows as `NULL` / `NULL`;
7. support downgrade by removing the new constraints and columns in a safe order.

### Existing data

No existing promotion row should gain fabricated claim dates.

Existing rows remain:

```text
claim_start_date = NULL
claim_end_date = NULL
```

This is backward compatible because PR 12 treats absence as no fixed-window definition rather than an implicit claim state.

### Migration compatibility

The change is additive and nullable, so older application versions that do not reference the new columns remain schema-compatible during rollout.

Do not introduce a server default or populate synthetic dates.

### Transactions

No new multi-step write transaction is introduced.

Existing transaction boundaries remain unchanged.

Database constraints are the final integrity boundary for persisted fixed-window completeness/order regardless of caller.

### PostgreSQL verification

Verify against a real PostgreSQL Testcontainer that:

- migration from the prior head succeeds;
- an existing promotion survives upgrade with both new fields `NULL`;
- a complete valid fixed window persists and reloads;
- a one-day fixed window persists;
- partial windows fail with the expected CHECK constraint;
- inverted windows fail with the expected CHECK constraint;
- SQLAlchemy metadata and migrated schema remain in sync;
- downgrade/upgrade behaviour remains valid where the existing migration test harness supports it.

---

## External services and network access

None.

Fixed claim-window persistence/evaluation must perform no:

- HTTP requests;
- source fetching;
- AI/model requests;
- Redis/cache access;
- product lookup;
- time service call;
- provider API call.

---

## Security and privacy

No new authentication or authorization boundary is introduced.

Requirements:

- treat claim dates as validated structured domain data, not executable expressions;
- do not accept user-controlled code, date expressions, or arbitrary formulas;
- do not log full purchase/customer data from the pure evaluator;
- do not convert database or programming failures into claim-window states;
- preserve safe persistence exception behaviour at existing repository boundaries;
- do not introduce PII into claim-window domain values or reason/status contracts.

No secrets, credentials, or external content handling are added.

---

## Configuration and deployment

No configuration change.

### Environment variables

None.

### Runtime/deployment changes

One database migration must be applied before code that reads/writes the new columns is deployed.

No changes are required to:

- Docker image dependencies;
- Railway/runtime configuration;
- startup/shutdown logic;
- health/readiness routes;
- workers;
- cron/scheduled jobs;
- logging configuration;
- Sentry configuration.

Application startup must continue not to run migrations automatically.

---

## Observability and operations

No new telemetry infrastructure is required.

The pure domain evaluator must not emit a log entry for every evaluation.

Migration/persistence failures continue through existing database/application diagnostics.

Future purchase-check orchestration may record low-cardinality fields such as:

```text
claim_window_status
promotion_id
```

but that is outside PR 12.

Do not log arbitrary source text, purchase payloads, or user data merely to diagnose fixed-window evaluation.

---

## Failure, consistency, and recovery

### Invalid fixed-window construction

Examples:

- non-`date` start;
- non-`date` end;
- `datetime` passed as a date;
- start after end.

Required behaviour:

```text
fail construction immediately
```

Do not return a claim status for an invalid definition.

### Invalid evaluation date

Wrong type, including `datetime`, must fail before evaluation.

Do not coerce strings or timestamps in the domain layer.

### Partial persisted window

The database must reject the write atomically through its CHECK constraint.

No row may commit in a partially configured fixed-window state.

### Inverted persisted window

The database must reject the write atomically.

Do not repair or swap bounds automatically.

### Existing promotion after migration

Existing rows with no fixed claim data remain valid as `NULL` / `NULL`.

No claim status is inferred from that absence.

### Database failure

Existing safe promotion persistence failure semantics remain unchanged.

Infrastructure failure must never become:

```text
ClaimWindowStatus.OPEN
ClaimWindowStatus.NOT_YET_OPEN
ClaimWindowStatus.EXPIRED
```

### Lifecycle concurrency

PR 12 must not alter lifecycle update concurrency or status-transition behaviour.

Adding claim-date fields to `PromotionRecord` must not change `change_promotion_status(...)` transaction ownership, optimistic conditional update behaviour, or conflict handling.

### Retry/recovery

Domain evaluation is pure and safely repeatable.

Migration is deterministic and contains no external side effects.

---

## Acceptance criteria

### Behaviour

- [ ] A typed fixed claim-window domain value exists.
- [ ] A fixed window contains an opening/start date and an end/deadline date.
- [ ] Fixed claim-window dates use calendar `date` semantics, not timestamps.
- [ ] `datetime` values are rejected where a pure `date` is required.
- [ ] Fixed-window construction rejects start dates after end dates.
- [ ] A one-day fixed window is valid.
- [ ] Evaluation accepts an explicit evaluation date and does not consult the system clock.
- [ ] Evaluation before the start returns PR 11 `ClaimWindowStatus.NOT_YET_OPEN`.
- [ ] Evaluation on the start date returns `ClaimWindowStatus.OPEN`.
- [ ] Evaluation between the boundaries returns `ClaimWindowStatus.OPEN`.
- [ ] Evaluation on the end/deadline date returns `ClaimWindowStatus.OPEN`.
- [ ] Evaluation after the end/deadline returns `ClaimWindowStatus.EXPIRED`.
- [ ] The evaluation result exposes the fixed opening and deadline dates as typed values.
- [ ] Repeated evaluation with equivalent inputs returns equivalent immutable results.
- [ ] No new claim-window status enum duplicates PR 11.
- [ ] `PromotionStatus.EXPIRED` is not accepted as or translated into claim-window expiry.
- [ ] Absence of a fixed window is not treated as implicitly open.
- [ ] No purchase-date-relative or delayed-window arithmetic is introduced.
- [ ] Existing PR 10 and PR 11 behaviour remains unchanged.

### Data and consistency

- [ ] `promotions` persists nullable `claim_start_date` and `claim_end_date` columns.
- [ ] Existing rows migrate with both fields `NULL` and retain all existing data.
- [ ] Both claim dates may be `NULL` together.
- [ ] A configured fixed window requires both claim dates to be non-`NULL`.
- [ ] The database rejects a row with only one claim date populated.
- [ ] The database rejects `claim_start_date > claim_end_date`.
- [ ] The database accepts `claim_start_date == claim_end_date`.
- [ ] `PromotionRecord` and repository mapping preserve the two new fields.
- [ ] No speculative claim-date index is introduced.
- [ ] Migration applies successfully to a real PostgreSQL test database.
- [ ] SQLAlchemy metadata matches the migrated database schema.
- [ ] Existing promotion lifecycle/history/provenance data remains intact.

### Security

- [ ] No dynamic date expressions, user code, or rule execution are introduced.
- [ ] Infrastructure/programming failures are not converted into claim statuses.
- [ ] No secrets or unnecessary personal data are added to logs or domain results.

### Operations

- [ ] No external service, retry policy, worker, or schedule is introduced.
- [ ] Existing health/readiness behaviour remains unchanged.
- [ ] Migration behaviour is covered by the established PostgreSQL integration-test approach.

### Code quality

- [ ] Existing architecture and dependency boundaries are preserved.
- [ ] Claim timing remains independent from FastAPI, SQLAlchemy ORM objects, and MCP.
- [ ] The domain evaluator imports/reuses PR 11 `ClaimWindowStatus` rather than duplicating it.
- [ ] No unnecessary dependency or unrelated refactor is introduced.
- [ ] Existing internal/public contracts remain backward compatible except for the intentional additive `PromotionRecord` fields.
- [ ] Ruff formatting/linting and relevant unit/integration/full tests pass.

---

## Tests to add or update

### Unit tests

Add focused coverage in:

```text
backend/tests/unit/test_claim_windows.py
```

Cover at minimum:

#### Stable contract

Verify:

- fixed-window value is immutable;
- evaluation result is immutable;
- returned status is the exact existing `ClaimWindowStatus` type;
- no parallel status enum is introduced.

#### Before opening

```text
start = 2026-11-01
end   = 2026-11-30
as_of = 2026-10-31
→ NOT_YET_OPEN
```

Verify returned opening/deadline dates.

#### Opening boundary

```text
as_of = start
→ OPEN
```

#### Inside window

```text
start < as_of < end
→ OPEN
```

#### Deadline boundary

```text
as_of = end
→ OPEN
```

#### After deadline

```text
as_of > end
→ EXPIRED
```

#### One-day window

Cover before/on/after a window where:

```text
start == end
```

#### Invalid fixed window

Reject:

- start after end;
- string dates;
- `datetime` values;
- `None` bounds;
- arbitrary objects.

Use `TypeError` for wrong types and `ValueError` for invalid ordered values, following existing domain conventions.

#### Invalid evaluation input

Reject:

- string evaluation date;
- `datetime` evaluation value;
- `None`;
- arbitrary object.

#### Determinism

Repeated equivalent evaluation returns equivalent results without clock/environment dependence.

### PostgreSQL integration tests

Add focused coverage in:

```text
backend/tests/integration/test_fixed_claim_windows.py
```

and update migration coverage where appropriate:

```text
backend/tests/integration/test_postgres_migrations.py
```

Cover at minimum:

#### Valid persistence

Persist/reload a promotion with:

```text
claim_start_date = 2026-11-01
claim_end_date   = 2026-11-30
```

Verify exact dates survive round trip.

#### No fixed window

Persist/reload:

```text
NULL / NULL
```

Verify it remains valid.

#### Partial start only

Attempt:

```text
claim_start_date != NULL
claim_end_date = NULL
```

and assert PostgreSQL rejects the configured completeness constraint.

#### Partial end only

Attempt:

```text
claim_start_date = NULL
claim_end_date != NULL
```

and assert rejection.

#### Inverted dates

Attempt:

```text
claim_start_date > claim_end_date
```

and assert the date-order constraint rejects it.

#### One-day window

Verify:

```text
claim_start_date == claim_end_date
```

persists successfully.

#### Repository/application mapping

Verify `SqlAlchemyPromotionRepository` returns `PromotionRecord` values containing the exact persisted claim dates without ORM leakage.

#### Migration upgrade

Where practical within the existing Testcontainers migration harness:

1. migrate to the previous head;
2. insert a representative promotion using the old schema;
3. migrate to the new head;
4. verify the row still exists and both new fields are `NULL`;
5. verify Alembic head and SQLAlchemy metadata are consistent.

Do not use SQLite to substitute for these PostgreSQL constraint checks.

### API/application tests

No new API tests are required.

Update existing promotion application/lifecycle tests only as needed for the additive `PromotionRecord` fields.

Do not add purchase-check orchestration tests in PR 12.

### MCP contract tests

N/A.

No MCP contract changes.

### External-boundary tests

N/A.

No external boundary is introduced.

---

## Verification commands

Run from `backend/`.

```bash
# Install/sync dependencies when required
uv sync --locked --extra dev

# Formatting check
uv run ruff format --check .

# Lint
uv run ruff check .

# Type checking
# N/A — no configured type-check command currently exists in backend/pyproject.toml.

# Targeted fixed-window unit tests
uv run pytest tests/unit/test_claim_windows.py

# Claim classification regression coverage
uv run pytest tests/unit/test_claim_windows.py tests/unit/test_eligibility_result.py

# PostgreSQL integration tests for the new persistence/migration behaviour
uv run pytest -m integration tests/integration/test_fixed_claim_windows.py tests/integration/test_postgres_migrations.py

# Promotion persistence/lifecycle regression coverage when affected
uv run pytest -m integration tests/integration/test_core_promotion_schema.py tests/integration/test_promotion_lifecycle.py

# Broader backend test suite
uv run pytest

# Migration verification against configured PostgreSQL when running manually
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head
```

Before running the direct Alembic commands, use the repository's normal local/test PostgreSQL configuration. Do not point destructive migration verification at shared or production data.

Do not invent a mypy or equivalent command unless repository configuration has changed and such a command now exists.

If any required command cannot run, document:

1. the exact command;
2. why it could not run;
3. what was verified instead;
4. the remaining risk.

Never weaken, skip, or rewrite a failing PR 10/11 or promotion persistence test merely to make PR 12 pass unless the test is demonstrably incorrect because this required additive behaviour changed its fixture/record shape; explain that case explicitly.

---

## Completion report

When implementation is complete, provide a concise report containing:

### Changed

Summarise:

- fixed claim-window domain model;
- explicit evaluation-date behaviour;
- opening/deadline boundary semantics;
- promotion persistence fields;
- repository/application record updates;
- tests added/updated.

### Database and migrations

List:

- migration revision;
- `promotions.claim_start_date`;
- `promotions.claim_end_date`;
- completeness CHECK constraint;
- ordering CHECK constraint;
- migration/backward-compatibility verification performed.

### API/MCP contracts

None.

### Tests and verification

List:

- unit tests added/updated;
- PostgreSQL integration tests added/updated;
- exact verification commands run;
- actual results.

Do not claim an unrun command passed.

### External configuration

None.

### Deviations

Describe any meaningful deviation from this specification and why it was necessary.

Use `None` when there were no deviations.

### Remaining risks or follow-up

Expected later work includes:

- relative claim deadlines;
- delayed claim windows;
- purchase-date-derived claim dates;
- a combined claim-window representation if required once more than one window type exists;
- publication completeness rules across supported claim-window types;
- mapping persisted promotion claim-window data into purchase-check orchestration;
- feeding evaluated claim-window status into PR 11 classification;
- evaluating all matched promotion candidates;
- promotion/result precedence;
- REST/MCP transport contracts;
- user-facing explanation formatting.

Do not implement those concerns as part of PR 12.

List only additional unresolved PR 12 issues beyond those deliberately deferred areas.

Use `None` when PR 12 itself is complete.
