# PR 13 — Relative & Delayed Claim Windows

## Repository state

**Expected branch:**  
`pr13-relative-delayed-claim-windows`

**Base branch:**  
`main`

**Dependencies:**

- PR 3 — Core Promotion Schema: merged.
- PR 4 — Promotion Lifecycle & History: merged.
- PR 6 — Promotion Source Provenance: merged.
- PR 8 — Purchase Input Contract: merged; `CheckPurchaseRequest.purchase_date` is the canonical caller-supplied purchase calendar date.
- PR 10 — Core Eligibility Rules: merged; purchase eligibility remains separate from claim timing.
- PR 11 — Eligibility Result Classification: merged; `ClaimWindowStatus` remains the canonical `open` / `not_yet_open` / `expired` contract.
- PR 12 — Fixed Claim Windows: merged; `FixedClaimWindow`, `ClaimWindowEvaluation`, `evaluate_fixed_claim_window(...)`, and fixed claim-date persistence already exist.
- Existing PostgreSQL, SQLAlchemy 2, Alembic, pytest, Ruff, and Testcontainers backend foundation.
- No new runtime package, external provider, worker, queue, cache, or infrastructure dependency.

### Read first

Before making changes, read:

- `AGENTS.md`
- `.codex/tasks/TEMPLATE.md`
- `.codex/tasks/pr-8-purchase-input-contract.md`
- `.codex/tasks/pr-10-core-eligibility-rules.md`
- `.codex/tasks/pr-11-eligibility-result-classification.md`
- `.codex/tasks/pr-12-fixed-claim-windows.md`
- `backend/README.md`
- `backend/app/application/purchase_check.py`
- `backend/app/application/promotions.py`
- `backend/app/domain/claim_windows.py`
- `backend/app/domain/eligibility_result.py`
- `backend/app/domain/purchase_values.py`
- `backend/app/db/models/core.py`
- `backend/app/db/repositories/promotions.py`
- `backend/migrations/versions/0004_fixed_claim_windows.py`
- `backend/tests/unit/test_claim_windows.py`
- `backend/tests/unit/test_purchase_input.py`
- `backend/tests/integration/test_fixed_claim_windows.py`
- `backend/tests/integration/test_postgres_migrations.py`

If a more narrowly scoped `AGENTS.md` exists on the implementation branch, read and follow it.

### Primary change area

Claim-window domain logic plus additive promotion persistence.

PR 13 adds purchase-relative claim windows such as:

```text
claim within 30 days of purchase
```

and delayed windows such as:

```text
claim between 30 and 60 days after purchase
```

The change must extend the existing PR 12 claim-window model rather than create parallel claim-status or evaluation concepts.

### Canonical implementation examples

Treat these as the preferred implementation references:

- `backend/app/domain/claim_windows.py`
  - `FixedClaimWindow`;
  - `ClaimWindowEvaluation`;
  - explicit calendar-date validation;
  - inclusive claim boundaries;
  - pure deterministic evaluation.
- `backend/app/domain/eligibility_result.py`
  - canonical `ClaimWindowStatus`.
- `backend/app/application/purchase_check.py`
  - canonical purchase `date`;
  - rejection of `datetime`;
  - transport-independent application contract.
- `backend/app/db/models/core.py`
  - existing promotion-level fixed claim-window persistence;
  - SQLAlchemy and CHECK-constraint conventions.
- `backend/app/application/promotions.py`
  - immutable `PromotionRecord`.
- `backend/app/db/repositories/promotions.py`
  - persistence-to-application mapping.
- `backend/migrations/versions/0004_fixed_claim_windows.py`
  - immediately preceding claim-window schema change.
- existing PostgreSQL integration tests
  - real constraint and migration verification.

Do not introduce a generic temporal rules engine, JSON rule representation, expression language, dynamic formulas, or AI/LLM claim-date interpretation.

### Relevant symbols

Inspect at minimum:

- `CheckPurchaseRequest`
- `FixedClaimWindow`
- `ClaimWindowEvaluation`
- `evaluate_fixed_claim_window`
- `ClaimWindowStatus`
- `Promotion`
- `PromotionRecord`
- `SqlAlchemyPromotionRepository`
- `_record`
- existing promotion claim-date CHECK constraints
- current Alembic head
- `validate_purchase_date` or equivalent calendar-date validation

### Expected change surface

Expected changes should remain focused in:

```text
backend/app/domain/claim_windows.py
backend/app/db/models/core.py
backend/app/application/promotions.py
backend/app/db/repositories/promotions.py
backend/migrations/versions/
backend/tests/unit/test_claim_windows.py
backend/tests/integration/
backend/README.md
```

Expected additions/updates include:

```text
backend/migrations/versions/0005_relative_delayed_claim_windows.py
backend/tests/integration/test_relative_claim_windows.py
backend/tests/integration/test_postgres_migrations.py
```

The migration revision above is expected from the current repository state. Codex must verify the actual Alembic head before creating the migration.

Small updates to existing fixed-window tests are acceptable where necessary to verify coexistence or exclusivity between window types.

### Excluded areas

Do not implement:

- natural-language parsing of phrases such as `"within 30 days"`;
- AI/LLM extraction or interpretation of claim rules;
- arbitrary date expressions or formulas;
- business-day calculations;
- working-day/holiday calendars;
- month-relative rules such as `"within 2 calendar months"`;
- timestamp or timezone-based claim windows;
- claim windows based on delivery, installation, registration, activation, invoice, redemption, or any event other than `purchase_date`;
- negative offsets representing dates before purchase;
- multiple claim windows for one promotion;
- combining fixed and relative windows for one promotion;
- final `check_purchase` orchestration;
- promotion/result precedence;
- winner/best-promotion selection;
- changes to PR 11 classifications or precedence;
- changes to PR 10 eligibility-rule semantics;
- changes to `CheckPurchaseRequest`;
- changes to promotion candidate matching;
- promotion publication completeness rules requiring a claim window;
- automatic promotion lifecycle expiry;
- claim submission records or claim-processing workflows;
- REST routes;
- FastAPI schemas;
- MCP tools;
- OpenAPI changes;
- scraping or ingestion;
- external provider calls;
- frontend behaviour.

### Unknowns Codex must verify

Before implementation verify:

- `backend/app/domain/claim_windows.py` still owns fixed-window calculation.
- `ClaimWindowEvaluation` still exposes:
  - `status`;
  - `opens_on`;
  - `deadline_on`.
- `ClaimWindowStatus` still contains exactly:
  - `open`;
  - `not_yet_open`;
  - `expired`.
- `CheckPurchaseRequest.purchase_date` remains a required Python calendar `date`.
- `Promotion` still persists:
  - `claim_start_date`;
  - `claim_end_date`.
- fixed claim dates still use the completeness and ordered-date constraints introduced by PR 12.
- no relative claim-window implementation has appeared.
- the current Alembic head is still `0004_fixed_claim_windows`.
- no configured backend type-check command exists unless repository configuration has changed.
- current verification commands still match `backend/README.md` and `backend/pyproject.toml`.

Do not create duplicate concepts when the repository already contains an equivalent implementation.

---

## Objective

After PR 13, the backend must support claim windows whose boundaries are calculated as whole calendar-day offsets from the purchase date.

The structured relative claim-window representation is conceptually:

```text
claim_start_offset_days
claim_end_offset_days
```

with:

```text
claim_start_offset_days = number of calendar days after purchase when claiming opens
claim_end_offset_days   = number of calendar days after purchase when claiming closes
```

Offset `0` means the purchase date itself.

Derived dates are:

```text
opens_on =
    purchase_date + claim_start_offset_days

deadline_on =
    purchase_date + claim_end_offset_days
```

Both resulting dates are inclusive.

For example:

```text
purchase_date = 2026-10-01
start offset  = 0
end offset    = 30

opens_on      = 2026-10-01
deadline_on   = 2026-10-31
```

This represents the structured rule:

```text
claim within 30 days of purchase
```

A delayed claim window is represented by a non-zero opening offset:

```text
purchase_date = 2026-10-01
start offset  = 30
end offset    = 60

opens_on      = 2026-10-31
deadline_on   = 2026-11-30
```

representing:

```text
claim between 30 and 60 days after purchase
```

The domain layer must calculate the concrete calendar dates and return the existing PR 12 `ClaimWindowEvaluation`.

PR 13 is complete when:

- relative offsets can be persisted safely;
- delayed relative windows are supported;
- fixed windows continue to behave unchanged;
- one promotion cannot configure both fixed and relative claim-window definitions;
- relative windows derive exact calendar opening/deadline dates from an explicit purchase date;
- derived dates are evaluated using the existing claim-window status semantics;
- no system clock is consulted;
- no natural-language interpretation or final purchase-check orchestration is introduced.

---

## Architecture and invariants

Preserve the existing claim-window architecture:

```text
published promotion data
        ↓
typed claim-window definition
        ↓
explicit purchase_date when required
        ↓
concrete opening/deadline dates
        ↓
ClaimWindowEvaluation
        ↓
existing ClaimWindowStatus
        ↓
PR 11 classifier in future orchestration
```

### Required invariants

1. **Relative claim timing is promotion-level data.**

   Relative offsets belong to `promotions`, matching the existing fixed-window representation.

2. **Relative offsets are measured from the purchase calendar date.**

   They are not measured from:

   - current date;
   - delivery;
   - payment settlement;
   - registration;
   - activation;
   - source retrieval;
   - promotion publication.

3. **Offset zero means the purchase date.**

   Conceptually:

   ```text
   purchase_date + 0 days = purchase_date
   ```

4. **Relative offsets are whole non-negative calendar days.**

   Valid:

   ```text
   0
   1
   30
   60
   ```

   Invalid:

   ```text
   -1
   1.5
   "30"
   True
   ```

   `bool` must be rejected even though it subclasses `int` in Python.

5. **A relative window is complete or absent.**

   Valid:

   ```text
   both relative offsets NULL
   ```

   or:

   ```text
   both relative offsets non-NULL
   ```

   One populated relative bound is invalid.

6. **Relative bounds are ordered.**

   ```text
   claim_start_offset_days <= claim_end_offset_days
   ```

   Equal offsets produce a one-day claim window.

7. **Fixed and relative definitions are mutually exclusive.**

   A promotion may have:

   ```text
   fixed window
   ```

   or:

   ```text
   relative window
   ```

   or:

   ```text
   no supported claim window yet
   ```

   It must not have both fixed and relative definitions simultaneously.

8. **No persisted claim-window type discriminator is required.**

   The configured form can be determined from the existing fixed fields and new relative fields.

   Do not add a `claim_window_type` column merely to duplicate that state.

9. **Derived dates use existing fixed-window semantics.**

   Relative evaluation must reuse the same inclusive opening/deadline behaviour as PR 12.

   Prefer deriving the concrete dates and delegating status evaluation to existing fixed-window logic instead of duplicating the comparison rules.

10. **The system clock is never an implicit input.**

    Both:

    ```text
    purchase_date
    evaluation_date
    ```

    are supplied explicitly.

11. **Calendar dates remain calendar dates.**

    No timestamps, timezone conversions, or 24-hour duration semantics.

12. **Claim timing remains independent of promotion lifecycle.**

    `PromotionStatus.EXPIRED` must not substitute for relative claim-window evaluation.

13. **Absence of a configured window is not implicitly open.**

    No fixed window plus no relative window remains absence of a supported claim-window definition.

14. **Runtime calculation remains deterministic.**

    For the same:

    ```text
    relative offsets
    purchase_date
    evaluation_date
    ```

    the result must be equivalent.

---

## API and contract changes

No public REST, MCP, or OpenAPI contract changes.

`CheckPurchaseRequest` remains unchanged.

### Relative claim-window domain contract

Extend `backend/app/domain/claim_windows.py` with an immutable relative definition, conceptually:

```python
@dataclass(frozen=True, slots=True)
class RelativeClaimWindow:
    start_offset_days: int
    end_offset_days: int
```

Construction requirements:

- values must be exact Python `int` values;
- `bool` is rejected;
- both values must be non-negative;
- `start_offset_days <= end_offset_days`;
- wrong types raise `TypeError`;
- invalid numeric values/order raise `ValueError`.

Do not silently coerce strings, floats, decimals, or booleans.

### Relative evaluation

Expose pure deterministic behaviour conceptually equivalent to:

```python
evaluate_relative_claim_window(
    window: RelativeClaimWindow,
    purchase_date: date,
    evaluation_date: date,
) -> ClaimWindowEvaluation
```

Exact naming may follow repository conventions.

The evaluator must:

1. validate the supplied window type;
2. validate `purchase_date` as a calendar `date`, rejecting `datetime`;
3. validate `evaluation_date` as a calendar `date`, rejecting `datetime`;
4. derive concrete opening/deadline dates using calendar-day offsets;
5. evaluate those dates with the same inclusive semantics as `FixedClaimWindow`;
6. return the existing `ClaimWindowEvaluation`.

Do not create:

```text
RelativeClaimWindowEvaluation
```

or another claim-status result type unless repository state makes reuse impossible.

### Optional minimal combined type

A simple domain typing alias such as:

```python
ClaimWindow = FixedClaimWindow | RelativeClaimWindow
```

is acceptable if useful to consumers.

Do not introduce an inheritance hierarchy, registration system, visitor framework, rule registry, or generic temporal-rule engine solely for these two forms.

### Application persistence contract

Extend `PromotionRecord` with:

```text
claim_start_offset_days: int | None
claim_end_offset_days: int | None
```

Existing fields remain unchanged:

```text
claim_start_date
claim_end_date
```

Existing callers that do not use relative windows must remain compatible.

---

## Domain and application behaviour

### Relative window: claim immediately through 30 days

Given:

```text
purchase_date = 2026-10-01

start_offset_days = 0
end_offset_days   = 30
```

derive:

```text
opens_on    = 2026-10-01
deadline_on = 2026-10-31
```

Required evaluation:

```text
2026-09-30 → NOT_YET_OPEN
2026-10-01 → OPEN
2026-10-15 → OPEN
2026-10-31 → OPEN
2026-11-01 → EXPIRED
```

### Delayed window: 30 through 60 days after purchase

Given:

```text
purchase_date = 2026-10-01

start_offset_days = 30
end_offset_days   = 60
```

derive:

```text
opens_on    = 2026-10-31
deadline_on = 2026-11-30
```

Required evaluation:

```text
2026-10-30 → NOT_YET_OPEN
2026-10-31 → OPEN
2026-11-15 → OPEN
2026-11-30 → OPEN
2026-12-01 → EXPIRED
```

### One-day relative window

This is valid:

```text
start_offset_days = 30
end_offset_days   = 30
```

For:

```text
purchase_date = 2026-10-01
```

the only open claim date is:

```text
2026-10-31
```

Required behaviour:

```text
2026-10-30 → NOT_YET_OPEN
2026-10-31 → OPEN
2026-11-01 → EXPIRED
```

### Purchase-date calendar arithmetic

Use Python calendar-date arithmetic equivalent to:

```python
purchase_date + timedelta(days=offset)
```

This naturally handles:

- month boundaries;
- year boundaries;
- leap years.

Examples:

```text
2026-01-31 + 30 days
→ 2026-03-02
```

and:

```text
2028-02-01 + 28 days
→ 2028-02-29
```

Do not implement "same day next month" or calendar-month arithmetic.

### Date-range overflow

A valid persisted offset may still be impossible to add to an extreme Python date such as `date.max`.

If deriving either bound would exceed Python's supported calendar range:

```text
fail deterministically
```

Do not clamp the date to `date.max` and do not return a claim status.

Map arithmetic overflow to a stable domain value error consistent with existing validation conventions rather than leaking an unpredictable partially evaluated result.

### Natural-language wording

PR 13 stores/evaluates normalized structured offsets.

It does not decide whether arbitrary marketing wording means:

```text
0..30
```

versus:

```text
1..30
```

or another interval.

Any future ingestion/publication process must normalize the source terms explicitly before publication.

Runtime evaluation consumes only the validated structured offsets.

### Relation to fixed windows

Existing fixed behaviour remains unchanged.

For a fixed window:

```text
claim_start_date = 2026-11-01
claim_end_date   = 2026-11-30
```

`purchase_date` remains irrelevant to calculation.

For a relative window:

```text
claim_start_offset_days = 30
claim_end_offset_days   = 60
```

the purchase date is required to derive concrete dates.

Both forms ultimately produce:

```text
ClaimWindowEvaluation(
    status=...,
    opens_on=...,
    deadline_on=...,
)
```

### Relation to purchase eligibility

Relative claim timing must not evaluate:

- manufacturer;
- product/model/SKU;
- retailer;
- purchase channel;
- whether the purchase date itself satisfies a promotion purchase-period rule;
- price;
- condition;
- country.

PR 10 owns those rule outcomes.

A purchase may satisfy a promotion's eligible purchase period while its relative claim window is:

```text
NOT_YET_OPEN
OPEN
EXPIRED
```

### Relation to `CheckPurchaseRequest`

Do not modify `CheckPurchaseRequest`.

Its existing:

```text
purchase_date
```

already supplies the data required by future application orchestration.

PR 13 only provides the domain/persistence capability required to evaluate a relative window once the caller supplies that date.

### Relation to result classification

PR 13 returns the existing:

```text
ClaimWindowStatus
```

through `ClaimWindowEvaluation`.

Do not call `classify_eligibility(...)` as part of relative-window evaluation.

That composition belongs to later purchase-check orchestration.

### Relation to lifecycle

Do not:

```text
claim deadline passed
→ update Promotion.status
```

and do not:

```text
Promotion.status == expired
→ relative claim status expired
```

Lifecycle/history and customer-specific claim timing remain independent.

---

## Persistence, transactions, and migrations

### `promotions` table

Add nullable integer columns:

| Column | Meaning |
| --- | --- |
| `claim_start_offset_days` | whole calendar days after purchase before claims may start |
| `claim_end_offset_days` | whole calendar days after purchase through which claims remain open |

Use PostgreSQL integer semantics consistent with SQLAlchemy `Integer`.

Do not use:

- floating-point types;
- strings;
- JSON;
- interval/timestamp columns.

### Relative completeness constraint

Require:

```sql
(
  claim_start_offset_days IS NULL
  AND claim_end_offset_days IS NULL
)
OR
(
  claim_start_offset_days IS NOT NULL
  AND claim_end_offset_days IS NOT NULL
)
```

Use a stable repository-style name, expected conceptually as:

```text
ck_promotions_claim_offset_days_complete
```

### Non-negative offset constraint

When configured:

```text
claim_start_offset_days >= 0
claim_end_offset_days >= 0
```

Expected conceptual name:

```text
ck_promotions_claim_offset_days_nonnegative
```

### Ordered-offset constraint

Require:

```text
claim_start_offset_days <= claim_end_offset_days
```

Expected conceptual name:

```text
ck_promotions_claim_offset_days
```

A one-day relative window where both values are equal must remain valid.

### Fixed/relative exclusivity constraint

A promotion must not configure both:

```text
claim_start_date / claim_end_date
```

and:

```text
claim_start_offset_days / claim_end_offset_days
```

at the same time.

Add a PostgreSQL CHECK constraint enforcing this regardless of caller.

Conceptually:

```sql
NOT (
  claim_start_date IS NOT NULL
  AND claim_start_offset_days IS NOT NULL
)
```

The exact expression may use complete-pair semantics for clarity.

Expected conceptual name:

```text
ck_promotions_claim_window_single_type
```

Do not remove or weaken PR 12's fixed-window constraints.

### SQLAlchemy model

Extend `Promotion` with conceptually:

```python
claim_start_offset_days: Mapped[int | None] = mapped_column(Integer)
claim_end_offset_days: Mapped[int | None] = mapped_column(Integer)
```

plus matching CHECK constraints.

### Application/repository mapping

Extend:

```text
PromotionRecord
```

and:

```text
SqlAlchemyPromotionRepository._record(...)
```

so both offsets round-trip exactly.

Do not calculate relative claim dates inside the repository.

Repositories load structured promotion data; the domain owns date calculation.

### No `claim_window_type` column

Do not add a persisted discriminator in this PR.

Existing persistence already naturally distinguishes:

```text
fixed:
claim_start_date/end_date populated

relative:
claim_start_offset_days/end_offset_days populated

none:
both pairs absent
```

Database exclusivity prevents ambiguity.

### Migration

Create one additive Alembic migration from the verified current head.

From current `main`, the expected revision is:

```text
0005_relative_delayed_claim_windows
```

Expected `down_revision`:

```text
0004_fixed_claim_windows
```

The migration must:

1. add both nullable relative-offset columns;
2. add the relative-pair completeness constraint;
3. add the non-negative constraint;
4. add the ordered-offset constraint;
5. add the fixed-versus-relative exclusivity constraint;
6. preserve all existing rows;
7. require no backfill;
8. leave existing rows with the new columns `NULL`;
9. preserve existing fixed claim windows unchanged;
10. support downgrade by removing new constraints and columns without modifying PR 12 fields.

### Existing data

Existing fixed promotions such as:

```text
claim_start_date = 2026-11-01
claim_end_date   = 2026-11-30
```

must migrate to:

```text
claim_start_date        = 2026-11-01
claim_end_date          = 2026-11-30
claim_start_offset_days = NULL
claim_end_offset_days   = NULL
```

Existing promotions without fixed windows remain:

```text
NULL / NULL
NULL / NULL
```

No synthetic relative rules may be generated.

### Indexes

Do not add indexes for relative-offset columns.

No current query filters or orders promotions using these offsets.

### Transactions

No new multi-step write transaction is introduced.

Existing transaction ownership remains unchanged.

PostgreSQL constraints are the final integrity boundary preventing:

- partial relative windows;
- negative offsets;
- inverted offsets;
- simultaneous fixed and relative definitions.

### PostgreSQL verification

Verify against a real PostgreSQL Testcontainer that:

- migration from `0004_fixed_claim_windows` succeeds;
- an existing promotion survives migration unchanged;
- an existing fixed claim window survives migration unchanged;
- new relative columns are nullable and have no server defaults;
- valid relative windows persist and reload;
- zero offsets persist;
- delayed windows persist;
- equal offsets persist;
- partial relative windows fail;
- negative relative offsets fail;
- inverted relative windows fail;
- fixed plus relative fields fail;
- SQLAlchemy metadata matches the migrated schema;
- downgrade to PR 12 removes only the PR 13 columns/constraints;
- re-upgrade succeeds.

---

## External services and network access

None.

Relative claim-window evaluation must perform no:

- HTTP request;
- AI/model request;
- source retrieval;
- cache lookup;
- database query;
- time service call;
- external holiday/calendar lookup.

---

## Security and privacy

No new authentication or authorization boundary is introduced.

Requirements:

- offsets are validated numeric structured data;
- do not execute or interpret arbitrary date expressions;
- do not introduce `eval`, formulas, Python expressions, SQL fragments, or executable rule text;
- reject malformed offset types rather than coercing them;
- infrastructure errors must not become claim statuses;
- date arithmetic failures must not silently produce a valid-looking claim result;
- do not log complete customer purchase payloads from pure domain evaluation;
- do not introduce PII into claim-window domain values.

No secrets, credentials, or new external content boundary is introduced.

---

## Configuration and deployment

No configuration change.

### Environment variables

None.

### Runtime/deployment changes

One additive database migration must be applied before application code that reads the new columns is deployed.

No changes are required to:

- Docker dependencies;
- Railway/runtime configuration;
- workers;
- cron jobs;
- health/readiness behaviour;
- logging configuration;
- Sentry configuration;
- startup/shutdown behaviour.

Application startup must continue not to run migrations automatically.

---

## Observability and operations

No new telemetry infrastructure is required.

Pure relative-window calculation must not emit per-evaluation log events.

Existing database diagnostics handle persistence/migration failures.

Future purchase-check orchestration may record low-cardinality information such as:

```text
claim_window_kind=relative
claim_window_status=open
promotion_id=...
```

but that orchestration is outside PR 13.

Do not log raw customer payloads or promotion source content merely to evaluate offsets.

---

## Failure, consistency, and recovery

### Invalid relative-window construction

Reject immediately:

- negative start offset;
- negative end offset;
- start offset greater than end offset;
- strings;
- floats;
- decimal values;
- `None`;
- `bool`;
- arbitrary objects.

Wrong types raise `TypeError`.

Invalid numeric values/order raise `ValueError`.

### Invalid purchase date

Reject values such as:

```text
"2026-10-01"
datetime(...)
None
integer timestamp
```

before performing arithmetic.

Do not parse or coerce them in the domain layer.

### Invalid evaluation date

Apply the same strict calendar-date semantics used by PR 12.

### Date arithmetic overflow

If:

```text
purchase_date + offset
```

cannot be represented by Python's calendar-date range:

- fail deterministically;
- return no claim status;
- do not clamp or wrap;
- expose a stable domain validation/value failure.

### Partial persisted relative window

PostgreSQL must reject the write atomically.

No row may commit with only one relative bound populated.

### Negative persisted offset

PostgreSQL must reject the write atomically.

### Inverted persisted relative window

PostgreSQL must reject the write atomically.

### Fixed and relative window configured together

PostgreSQL must reject the write atomically.

Do not define precedence such as:

```text
fixed wins
```

or:

```text
relative wins
```

Ambiguous persisted state is invalid.

### Database failure

Existing safe promotion persistence failure semantics remain unchanged.

A persistence failure must never be translated into:

```text
OPEN
NOT_YET_OPEN
EXPIRED
```

### Existing fixed-window behaviour

PR 13 must not alter fixed-window evaluation semantics.

PR 12 regression tests must continue to pass.

### Retry/recovery

Relative evaluation is pure and safely repeatable.

The migration contains no external side effects or data backfill.

---

## Acceptance criteria

### Behaviour

- [ ] `RelativeClaimWindow` or an equivalently focused immutable domain value exists.
- [ ] Relative windows use start/end whole-day offsets from `purchase_date`.
- [ ] Offset zero represents the purchase date.
- [ ] Negative offsets are rejected.
- [ ] Non-integer offsets are rejected.
- [ ] `bool` offsets are rejected.
- [ ] Start offsets greater than end offsets are rejected.
- [ ] Equal offsets are valid.
- [ ] Purchase dates use strict calendar `date` semantics.
- [ ] Evaluation dates use strict calendar `date` semantics.
- [ ] `datetime` values are rejected for both dates.
- [ ] Relative evaluation receives the purchase date explicitly.
- [ ] Relative evaluation receives the evaluation date explicitly.
- [ ] No system clock is consulted.
- [ ] Derived opening date is `purchase_date + start_offset_days`.
- [ ] Derived deadline is `purchase_date + end_offset_days`.
- [ ] Both derived boundaries are inclusive.
- [ ] `0..30` supports an immediate `"within 30 days"` style rule.
- [ ] `30..60` supports a delayed `"between 30 and 60 days"` style rule.
- [ ] Month boundaries are handled by calendar arithmetic.
- [ ] Year boundaries are handled correctly.
- [ ] Leap-year arithmetic is handled correctly.
- [ ] Calendar overflow fails without producing a claim status.
- [ ] Relative evaluation returns the existing `ClaimWindowEvaluation`.
- [ ] Relative evaluation reuses existing `ClaimWindowStatus`.
- [ ] Fixed-window behaviour remains unchanged.
- [ ] No natural-language parsing is introduced.
- [ ] No final eligibility orchestration is introduced.
- [ ] PR 10 and PR 11 behaviour remains unchanged.

### Data and consistency

- [ ] `promotions.claim_start_offset_days` exists as nullable integer data.
- [ ] `promotions.claim_end_offset_days` exists as nullable integer data.
- [ ] Existing promotions migrate with both new fields `NULL`.
- [ ] Existing fixed claim windows survive migration unchanged.
- [ ] Both relative fields may be `NULL` together.
- [ ] A configured relative window requires both fields.
- [ ] The database rejects partial relative windows.
- [ ] The database rejects negative relative offsets.
- [ ] The database rejects start offset greater than end offset.
- [ ] The database accepts start offset equal to end offset.
- [ ] The database accepts start offset zero.
- [ ] A promotion cannot persist both a fixed and relative window.
- [ ] A promotion may still have neither supported window type.
- [ ] `PromotionRecord` preserves both new relative fields.
- [ ] Repository mapping preserves exact offset values.
- [ ] No claim-window discriminator column is introduced.
- [ ] No speculative offset index is introduced.
- [ ] Migration applies successfully to real PostgreSQL.
- [ ] SQLAlchemy metadata matches migrated PostgreSQL schema.
- [ ] Downgrade to PR 12 preserves PR 12 fixed-window columns and data.

### Security

- [ ] No executable rule/date expression mechanism is introduced.
- [ ] Malformed values are rejected rather than coerced.
- [ ] Infrastructure failures are not translated into claim statuses.
- [ ] No secrets or unnecessary personal data are added to logs/results.

### Operations

- [ ] No new external service is introduced.
- [ ] No worker, schedule, retry policy, or cache is introduced.
- [ ] Existing health/readiness behaviour remains unchanged.
- [ ] Migration behaviour is covered by PostgreSQL integration tests.

### Code quality

- [ ] Existing architecture and dependency direction are preserved.
- [ ] Relative calculation remains independent of FastAPI, SQLAlchemy ORM objects, and MCP.
- [ ] Existing fixed-window logic is reused rather than duplicated where practical.
- [ ] Existing PR 12 `ClaimWindowEvaluation` remains canonical.
- [ ] Existing PR 11 `ClaimWindowStatus` remains canonical.
- [ ] No generic temporal-rule framework is introduced.
- [ ] No unnecessary runtime dependency or unrelated refactor is introduced.
- [ ] Ruff formatting/linting and relevant unit/integration/full tests pass.

---

## Tests to add or update

### Unit tests

Extend:

```text
backend/tests/unit/test_claim_windows.py
```

Cover at minimum:

#### Relative domain contract

Verify:

- value is immutable;
- exact expected fields;
- equality is deterministic;
- returned evaluation uses the exact existing `ClaimWindowEvaluation`;
- returned status is the exact existing `ClaimWindowStatus`.

#### Immediate relative window

```text
purchase = 2026-10-01
offsets  = 0..30

opens_on    = 2026-10-01
deadline_on = 2026-10-31
```

Cover:

```text
before opening
opening boundary
inside window
deadline boundary
after deadline
```

#### Delayed relative window

```text
purchase = 2026-10-01
offsets  = 30..60

opens_on    = 2026-10-31
deadline_on = 2026-11-30
```

Cover the same five evaluation positions.

#### One-day relative window

```text
30..30
```

Cover before/on/after.

#### Zero-day relative window

```text
0..0
```

The purchase date itself must be the sole open claim date.

#### Month/year boundaries

Include representative cases crossing:

- month end;
- year end.

#### Leap year

Verify deterministic arithmetic through February 29.

#### Invalid offset types

Reject:

- string;
- float;
- `Decimal`;
- `None`;
- `bool`;
- arbitrary object.

#### Invalid offset values

Reject:

```text
-1..30
0..-1
60..30
```

#### Invalid purchase date

Reject:

- string;
- `datetime`;
- timezone-aware `datetime`;
- `None`;
- integer timestamp.

#### Invalid evaluation date

Apply equivalent rejection coverage.

#### Overflow

Use a date/offset pair that exceeds Python's representable date range and verify a deterministic failure with no claim result.

#### Fixed regression

Existing `evaluate_fixed_claim_window(...)` tests must remain unchanged or continue producing identical outcomes.

### PostgreSQL integration tests

Add:

```text
backend/tests/integration/test_relative_claim_windows.py
```

and update:

```text
backend/tests/integration/test_postgres_migrations.py
```

Cover at minimum:

#### Relative round trip

Persist:

```text
claim_start_offset_days = 0
claim_end_offset_days   = 30
```

Reload and verify exact integers.

Verify repository mapping returns the same values through `PromotionRecord`.

#### Delayed window

Persist:

```text
30 / 60
```

and verify round trip.

#### Equal offsets

Persist:

```text
30 / 30
```

successfully.

#### Relative window absent

Persist:

```text
NULL / NULL
```

successfully.

#### Partial start only

Reject:

```text
start != NULL
end = NULL
```

and assert the expected named CHECK constraint.

#### Partial end only

Reject:

```text
start = NULL
end != NULL
```

#### Negative start

Reject:

```text
-1 / 30
```

#### Negative end

Reject a negative end value.

#### Inverted range

Reject:

```text
60 / 30
```

#### Fixed plus relative

Persist valid fixed dates plus valid relative offsets in the same promotion and assert PostgreSQL rejects the window-type exclusivity constraint.

#### Existing fixed window

Verify a promotion containing only:

```text
claim_start_date
claim_end_date
```

remains valid.

#### Migration upgrade

Using the established PostgreSQL migration harness:

1. migrate to `0004_fixed_claim_windows`;
2. create representative rows:
   - no claim window;
   - valid fixed claim window;
3. upgrade to PR 13 head;
4. verify both rows survive unchanged;
5. verify new relative fields are `NULL`;
6. verify new columns/constraints exist;
7. verify metadata matches;
8. downgrade one migration;
9. verify relative columns disappear while fixed columns remain;
10. upgrade to head again.

Do not substitute SQLite for PostgreSQL constraint tests.

### API/application tests

No new public API tests are required.

Update promotion application/repository tests only as necessary for the additive `PromotionRecord` fields.

`CheckPurchaseRequest` regression tests should remain unchanged because PR 13 must not alter its contract.

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

# Targeted claim-window unit tests
uv run pytest tests/unit/test_claim_windows.py

# Claim classification and purchase-date regression coverage
uv run pytest \
  tests/unit/test_claim_windows.py \
  tests/unit/test_eligibility_result.py \
  tests/unit/test_purchase_input.py

# Relative/fixed claim-window PostgreSQL integration coverage
uv run pytest -m integration \
  tests/integration/test_relative_claim_windows.py \
  tests/integration/test_fixed_claim_windows.py \
  tests/integration/test_postgres_migrations.py

# Promotion persistence/lifecycle regression coverage
uv run pytest -m integration \
  tests/integration/test_core_promotion_schema.py \
  tests/integration/test_promotion_lifecycle.py

# Broader backend test suite
uv run pytest

# Migration verification against configured PostgreSQL when running manually
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head
```

Before direct Alembic verification, use the repository's normal disposable/local PostgreSQL configuration.

Do not run destructive migration verification against shared or production data.

Do not invent a mypy or equivalent command unless repository configuration has changed.

If any required command cannot run, document:

1. the exact command;
2. why it could not run;
3. what was verified instead;
4. remaining risk.

Never weaken or delete a PR 8, PR 10, PR 11, or PR 12 assertion merely to make PR 13 pass unless the assertion is demonstrably incompatible with the required additive behaviour; explain any such case explicitly.

---

## Completion report

When implementation is complete, provide a concise report containing:

### Changed

Summarise:

- relative claim-window domain value;
- purchase-date-derived calendar calculation;
- delayed claim-window behaviour;
- reuse of PR 12 evaluation/status contracts;
- promotion persistence additions;
- fixed/relative exclusivity;
- tests added/updated.

### Database and migrations

List:

- migration revision;
- `promotions.claim_start_offset_days`;
- `promotions.claim_end_offset_days`;
- completeness constraint;
- non-negative constraint;
- ordered-offset constraint;
- fixed/relative exclusivity constraint;
- migration/backward-compatibility verification performed.

### API/MCP contracts

None.

`CheckPurchaseRequest` remains unchanged.

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

Describe any meaningful deviation from this specification and why it was required.

Use `None` when there were no deviations.

### Remaining risks or follow-up

Expected later work includes:

- publication validation deciding whether a published promotion must have exactly one supported claim-window form;
- parsing/normalizing official promotion wording into structured fixed or relative window data;
- claim windows based on events other than purchase date;
- month/business-day based rules if real promotions require them;
- final `check_purchase` orchestration;
- mapping a promotion's configured fixed/relative window into the canonical evaluator;
- feeding evaluated claim-window status into PR 11 classification;
- evaluating all matched promotion candidates;
- promotion/result precedence;
- REST/MCP transport contracts;
- user-facing claim-opening/deadline explanations.

Do not implement those concerns as part of PR 13.

List only additional unresolved PR 13 issues beyond these deliberately deferred areas.

Use `None` when PR 13 itself is complete.