# PR 5 — Benefit Model

## Repository state

**Expected branch:**  
`pr5-benefit-model`

**Base branch:**  
`main`

**Dependencies:**  

- PR 3 — Core Promotion Schema: merged.
- PR 4 — Promotion Lifecycle & History: merged.
- Existing `benefits` persistence model and `ck_benefits_type` database constraint.
- Existing Python 3.13 domain architecture.
- No new runtime service, external provider, package, or infrastructure dependency.

### Read first

Before making changes, read:

- `AGENTS.md`
- `.codex/tasks/TEMPLATE.md`
- `.codex/tasks/pr-3-core-promotion-schema.md`
- `.codex/tasks/pr-4-promotion-lifecycle-history.md`
- `backend/README.md`
- `backend/app/domain/promotion_lifecycle.py`
- `backend/app/application/promotions.py`
- `backend/app/db/models/core.py`
- `backend/app/db/repositories/promotions.py`
- `backend/migrations/versions/0002_core_promotion_schema.py`
- `backend/tests/integration/test_core_promotion_schema.py`
- `backend/tests/unit/test_promotion_lifecycle.py`
- `.github/workflows/backend.yml`

As of the current `main` branch there is no scoped `backend/AGENTS.md`. If one exists on the implementation branch, read and follow it.

### Primary change area

Domain model.

This PR introduces the canonical domain representation of a promotion benefit and its supported benefit classifications.

Persistence support for the initial classifications already exists from PR 3. This PR must build on that schema rather than creating a competing benefit representation.

### Canonical implementation examples

Use:

- `backend/app/domain/promotion_lifecycle.py` as the precedent for stable string-backed domain classifications.
- `backend/app/db/models/core.py::Benefit` as the existing persistence representation.
- `backend/migrations/versions/0002_core_promotion_schema.py` as the source of the existing persisted benefit-type values.
- `backend/tests/unit/test_promotion_lifecycle.py` as the unit-test style precedent for domain classifications.
- `backend/tests/integration/test_core_promotion_schema.py` as the PostgreSQL verification point for persisted benefit types.

The domain `Benefit` introduced by this PR must not become a SQLAlchemy model and must not depend on SQLAlchemy.

### Relevant symbols

Inspect before editing:

- `app.db.models.Benefit`
- `app.db.models.PromotionVariant`
- `app.domain.promotion_lifecycle.PromotionStatus`
- `app.application.promotions.PromotionRecord`
- `Base.metadata`
- `ck_benefits_type`
- the `graph` fixture in `test_core_promotion_schema.py`

### Expected change surface

Expected additions or changes include:

- `.codex/tasks/pr-5-benefit-model.md`
- `backend/app/domain/benefits.py`
- `backend/tests/unit/test_benefits.py`
- `backend/tests/integration/test_core_promotion_schema.py` where useful to verify domain/persistence value parity

Small changes to documentation are permitted if they clarify the benefit-model contract.

Changes to `backend/app/db/models/core.py` should only be made if required to keep the existing persistence representation aligned with the new domain contract.

No schema migration is expected from the current `main` state.

### Excluded areas

Do not implement as part of this PR:

- cashback amount calculation
- percentage cashback
- fixed monetary reward values
- tiered or basket-value rewards
- product-specific reward amounts
- warranty-duration calculations
- warranty start/end-date calculation
- gift monetary valuation
- gift stock or fulfilment
- conditional bonuses
- reward rules
- eligibility rules
- claim windows
- claim models
- purchase models
- promotion matching
- publication validation
- ingestion or scraping
- AI/LLM extraction
- REST endpoints
- MCP tools
- authentication/authorization
- background jobs
- frontend/UI
- arbitrary JSON benefit payloads
- arbitrary executable rule expressions
- generic rules DSLs
- native PostgreSQL enum types

Do not create three independent persistence models or three unrelated domain hierarchies solely because three benefit classifications currently exist.

### Unknowns Codex must verify

Before implementation:

- Verify `main` still contains exactly the persisted benefit values:
  - `cashback`
  - `extended_warranty`
  - `free_gift`
- Verify `ck_benefits_type` still constrains those values.
- Verify no later merged change has already introduced `BenefitType`, a benefit domain model, or a reward-rule model.
- Verify the current Alembic head before concluding that no migration is required.
- Verify no scoped backend `AGENTS.md` has been added.
- Verify CI still uses the commands defined in `.github/workflows/backend.yml`.

If repository state has changed, adapt to the established model rather than introducing a parallel abstraction.

---

## Objective

Introduce a canonical, persistence-independent domain model for promotion benefits.

After this PR, backend domain code must have an explicit representation for:

- `CASHBACK`
- `EXTENDED_WARRANTY`
- `FREE_GIFT`

with stable persisted values:

- `cashback`
- `extended_warranty`
- `free_gift`

The benefit model must represent the common information already established by PR 3:

- benefit classification;
- human-readable name;
- optional human-readable description.

The model must provide a controlled extension point for adding future benefit classifications without requiring callers to use separate models, tables, or branching architectures for every benefit type.

Completion means:

- the three initial benefit types exist as a stable domain contract;
- a common domain `Benefit` model exists;
- the domain model has no FastAPI, SQLAlchemy, persistence, network, or AI dependencies;
- existing persisted values remain unchanged;
- domain and PostgreSQL tests verify that supported values stay aligned;
- unsupported benefit classifications fail explicitly rather than silently degrading into another type;
- no reward calculation or eligibility behaviour is introduced.

---

## Architecture and invariants

Preserve the repository architecture:

```text
REST / MCP
    ↓
application use cases
    ↓
domain rules and models
    ↓
application-owned ports
    ↓
infrastructure adapters
```

The benefit model belongs in the domain layer.

It must not import:

- FastAPI
- SQLAlchemy
- Alembic
- database sessions
- application configuration
- HTTP clients
- model/AI provider libraries

Task-specific invariants:

1. A benefit has exactly one supported benefit classification.
2. Initial classifications are `cashback`, `extended_warranty`, and `free_gift`.
3. Python enum/member names should be:
   - `CASHBACK`
   - `EXTENDED_WARRANTY`
   - `FREE_GIFT`
4. Persisted/string values must remain lower-case snake case for compatibility with PR 3.
5. The domain must not reinterpret existing persisted benefit values.
6. A benefit retains a human-readable `name`.
7. A benefit may retain an optional human-readable `description`.
8. Benefit classification and reward calculation are separate concerns.
9. The common `Benefit` shape must not contain cashback-only, warranty-only, or gift-only fields.
10. Adding another supported classification in future must not require redesigning existing consumers of the common `Benefit` model.
11. Extensibility is controlled extensibility. It does not mean arbitrary unknown strings are silently accepted as supported benefits.
12. Unknown benefit classifications must fail explicitly at the boundary where persisted/extracted data is converted into the domain type.
13. Do not introduce an `OTHER` fallback solely to suppress unsupported values.
14. Do not use a native PostgreSQL enum.
15. Do not introduce a runtime plugin/registration system for benefit types when an explicit domain classification is sufficient.
16. The model must remain usable by the future deterministic eligibility/reward layers without depending on them.

### Canonical domain shape

The implementation should conceptually provide:

```python
class BenefitType(StrEnum):
    CASHBACK = "cashback"
    EXTENDED_WARRANTY = "extended_warranty"
    FREE_GIFT = "free_gift"
```

and a common immutable benefit value such as:

```python
@dataclass(frozen=True, slots=True)
class Benefit:
    benefit_type: BenefitType
    name: str
    description: str | None = None
```

Exact implementation details may follow repository conventions, but the observable semantics above must remain.

Do not create:

```text
CashbackBenefit
ExtendedWarrantyBenefit
FreeGiftBenefit
```

as three parallel models when they contain no type-specific domain behaviour.

Future type-specific reward/value models may compose with `Benefit` rather than forcing the base benefit concept into a growing union of unrelated fields.

---

## API and contract changes

No REST, MCP, or external API contract changes.

This PR introduces an internal domain contract:

### `BenefitType`

Purpose:

Represent the stable classification of a benefit.

Initial values:

| Python member | Stable value |
| --- | --- |
| `BenefitType.CASHBACK` | `cashback` |
| `BenefitType.EXTENDED_WARRANTY` | `extended_warranty` |
| `BenefitType.FREE_GIFT` | `free_gift` |

Requirements:

- String-backed.
- Stable across persistence/domain boundaries.
- Case-sensitive.
- Unknown values must not silently map to another type.
- Do not change existing persisted strings to uppercase.

### `Benefit`

Purpose:

Represent the common domain concept of a benefit independently from its ORM representation.

Required information:

- `benefit_type: BenefitType`
- `name: str`
- `description: str | None`

Persistence identifiers such as `id` and `promotion_variant_id` do not need to be part of this pure domain value unless an existing concrete application use case requires them.

Do not make transport schemas depend directly on this model in this PR.

---

## Domain and application behaviour

### Benefit classification

The following conversions must be deterministic:

```text
"cashback"           -> BenefitType.CASHBACK
"extended_warranty" -> BenefitType.EXTENDED_WARRANTY
"free_gift"          -> BenefitType.FREE_GIFT
```

Unsupported values such as:

```text
"rebate"
"gift"
"warranty"
"CASHBACK"
"other"
""
```

must not silently become a supported `BenefitType`.

Use normal explicit domain validation/error behaviour rather than fuzzy matching, case folding, aliases, or AI interpretation.

### Common benefit model

All three classifications use the same common benefit model.

For example:

```text
Benefit(
    benefit_type=CASHBACK,
    name="£100 cashback",
)
```

```text
Benefit(
    benefit_type=EXTENDED_WARRANTY,
    name="5 year warranty",
)
```

```text
Benefit(
    benefit_type=FREE_GIFT,
    name="Free headphones",
)
```

The human-readable name describes the offered benefit but must not become the source of deterministic reward calculations.

Later code must not parse monetary amounts, durations, product identifiers, or eligibility conditions back out of `name` or `description`.

Those values require explicit structured models in later work.

### Extensibility

The design must make future classification additions local and deliberate.

For a future type such as:

```text
trade_in_bonus
```

the expected evolution should be approximately:

1. Add the stable domain classification.
2. Update the database constraint through a new Alembic migration.
3. Add domain and persistence tests.
4. Add any genuinely required typed reward/value behaviour separately.

Existing `Benefit` consumers should not require structural changes merely because another classification is introduced.

Do not solve future extensibility using arbitrary dictionaries such as:

```python
details: dict[str, Any]
```

or unconstrained JSON blobs.

Typed models should be introduced incrementally when real benefit-specific data is required.

### Reward/value separation

This PR must not decide:

- how much cashback is payable;
- whether cashback is fixed or percentage-based;
- how warranty duration is calculated;
- whether a stated warranty duration means an extension or total warranty period;
- the monetary value of a free gift;
- whether a gift changes by product;
- which reward applies based on purchase price or product;
- whether a benefit is available for a particular purchase.

Those are later rule/value/eligibility concerns.

---

## Persistence, transactions, and migrations

The current repository already contains:

```text
benefits
```

with:

- `id`
- `promotion_variant_id`
- `benefit_type`
- `name`
- `description`
- timestamps

and the database constraint:

```text
ck_benefits_type
```

supporting:

```text
cashback
extended_warranty
free_gift
```

### Expected schema changes

None.

Do not rewrite `0002_core_promotion_schema.py`.

Do not create a migration merely to recreate the existing three values.

### Domain/persistence alignment

The existing database values and the new domain values must remain identical.

Tests must make accidental drift visible.

For example, if a future developer adds:

```python
BenefitType.TRADE_IN_BONUS = "trade_in_bonus"
```

without extending the persistence constraint through a new migration, PostgreSQL integration coverage should expose that mismatch rather than allowing domain and storage contracts to diverge silently.

### Future extension path

Adding a new supported benefit type later requires:

- adding the domain classification;
- creating a new Alembic migration altering `ck_benefits_type`;
- updating persistence integration tests.

This controlled migration requirement is intentional.

"Extensible" does not require accepting unknown database values.

### Transactions

No new write use case or transaction boundary is introduced.

Existing benefit persistence remains owned by the promotion graph and existing SQLAlchemy transaction behaviour.

### Deletion behaviour

Existing semantics remain unchanged:

```text
Promotion
  -> PromotionVariant
      -> Benefit
```

Benefit rows remain owned by their promotion variant and may cascade when the owning variant is explicitly deleted.

No new delete behaviour is introduced.

---

## External services and network access

None.

No external HTTP service, AI provider, manufacturer site, message queue, Redis service, or other network dependency is introduced.

---

## Security and privacy

There is no new authentication or personal-data boundary.

However:

- unsupported benefit classifications must be rejected explicitly;
- human-readable benefit text must remain data rather than executable instructions;
- no `eval`, dynamic imports, SQL fragments, executable expressions, or arbitrary rule payloads may be stored or executed;
- do not add arbitrary JSON specifically to avoid defining proper future benefit structures;
- future extracted values remain untrusted until validated through the publication boundary.

No secrets or credentials are introduced.

---

## Configuration and deployment

None.

### Environment variables

None.

### Runtime/deployment changes

None.

No Docker, Railway, process, worker, health-check, or startup changes are expected.

---

## Observability and operations

No new production telemetry is required.

This PR introduces a pure domain concept and no new operational flow.

Do not add logging from the domain model.

Unsupported benefit types should surface through the caller's established validation/error boundary when such callers are introduced.

---

## Failure, consistency, and recovery

### Unsupported domain value

Attempting to construct/parse a `BenefitType` from an unsupported value must fail deterministically.

It must not:

- fall back to cashback;
- fall back to a generic type;
- return `None` silently;
- perform fuzzy matching;
- depend on an LLM.

### Unsupported persisted value

PostgreSQL must continue rejecting unsupported `benefit_type` values through the existing database constraint.

### Domain/database drift

Tests must ensure the domain's supported classifications remain persistable by the current schema.

A future domain type added without the required schema migration should therefore fail verification.

### Existing data

Existing rows containing:

```text
cashback
extended_warranty
free_gift
```

must retain exactly the same meaning.

There is no backfill.

There is no data migration.

---

## Acceptance criteria

### Behaviour

- [x] `BenefitType.CASHBACK` exists with stable value `cashback`.
- [x] `BenefitType.EXTENDED_WARRANTY` exists with stable value `extended_warranty`.
- [x] `BenefitType.FREE_GIFT` exists with stable value `free_gift`.
- [x] A common domain `Benefit` model represents benefit type, name, and optional description.
- [x] The domain benefit model is independent of FastAPI, SQLAlchemy, Alembic, network clients, AI providers, and application startup state.
- [x] Unknown benefit types fail explicitly.
- [x] No fallback/`OTHER` classification masks unsupported data.
- [x] Benefit names/descriptions are not parsed to derive deterministic reward values.
- [x] Existing promotion lifecycle behaviour remains unchanged.
- [x] Existing persistence behaviour remains unchanged.

### Extensibility

- [x] The implementation does not create separate parallel models solely for cashback, warranty, and gift classifications.
- [x] The common `Benefit` shape does not contain type-specific nullable fields.
- [x] Adding a future benefit classification is a localized domain + migration + test change.
- [x] No arbitrary dictionary/JSON structure is introduced as a generic escape hatch for future benefit types.
- [x] No general-purpose benefit plugin framework or rule DSL is introduced.

### Data and consistency

- [x] Existing persisted lower-case values remain unchanged.
- [x] PostgreSQL continues accepting all three supported benefit types.
- [x] PostgreSQL continues rejecting unsupported benefit types.
- [x] Domain benefit-type values and persisted benefit-type values are verified to remain aligned.
- [x] `benefits` continue belonging to `promotion_variants`.
- [x] Existing cascade behaviour remains unchanged.
- [x] No existing migration is rewritten.
- [x] No migration is added unless repository state has materially changed from the inspected `main`.

### Architecture

- [x] Benefit classification is represented in the domain layer.
- [x] Domain code has no ORM/session dependency.
- [x] Persistence remains an infrastructure concern.
- [x] Reward calculation remains separate from benefit classification.
- [x] Runtime eligibility remains deterministic and unaffected by this PR.

### Scope

- [x] No cashback amount logic is introduced.
- [x] No percentages or tiers are introduced.
- [x] No warranty calculation is introduced.
- [x] No gift valuation/fulfilment logic is introduced.
- [x] No reward-rule model is introduced.
- [x] No eligibility rules are introduced.
- [x] No REST or MCP contract is introduced.
- [x] No ingestion or AI behaviour is introduced.

### Code quality

- [x] Existing architecture and naming conventions are preserved.
- [x] No unnecessary dependency is introduced.
- [x] Ruff lint passes.
- [x] Ruff format check passes.
- [x] Targeted unit tests pass.
- [x] PostgreSQL integration tests pass.
- [x] The broader backend test suite passes.

---

## Tests to add or update

### Unit tests

Add:

```text
backend/tests/unit/test_benefits.py
```

Cover at minimum:

#### Stable classification values

Assert exactly:

```text
CASHBACK           -> cashback
EXTENDED_WARRANTY -> extended_warranty
FREE_GIFT          -> free_gift
```

#### String behaviour

If `StrEnum` is used, verify values behave as the stable strings expected by domain/persistence mapping.

#### Unsupported values

Verify unsupported values raise explicitly.

Include representative cases such as:

```text
rebate
gift
warranty
CASHBACK
other
empty string
```

Do not make tests depend on fuzzy or case-insensitive conversion.

#### Benefit construction

Verify the common model can represent each of the three classifications with:

- name;
- optional description.

#### Immutability

If the model is intentionally immutable, verify the established immutable semantics.

Do not test dataclass implementation details beyond behaviour that forms part of the domain contract.

### PostgreSQL integration tests

Update:

```text
backend/tests/integration/test_core_promotion_schema.py
```

where useful.

Verify:

- every `BenefitType` stable value can be persisted in `benefits`;
- values round-trip unchanged;
- an unsupported value remains rejected by PostgreSQL;
- the existing benefit FK/cascade behaviour remains intact;
- database and ORM metadata remain migration-clean.

Prefer using the domain classification values in the persistence test rather than maintaining another unconnected hard-coded list where practical.

This test should make domain/schema drift visible when another benefit classification is introduced later.

### API/application tests

N/A.

No API or application use case changes are required.

### MCP contract tests

N/A.

### External-boundary tests

N/A.

---

## Verification commands

Run from `backend/`.

### Install/sync dependencies

```bash
uv sync --locked --extra dev
```

### Formatting check

```bash
uv run ruff format --check .
```

### Lint

```bash
uv run ruff check .
```

### Type checking

N/A.

The current repository does not configure a type-checking command or type-checker dependency in `pyproject.toml` or backend CI. Do not invent one for this PR.

### Targeted unit tests

```bash
uv run pytest tests/unit/test_benefits.py
```

### PostgreSQL integration tests

```bash
uv run pytest tests/integration/test_core_promotion_schema.py
```

Docker must be available because the repository uses PostgreSQL Testcontainers.

### Broader backend test suite

```bash
uv run pytest
```

### Migration verification

Because no migration is expected, verify the existing schema through the PostgreSQL integration suite and metadata comparison.

If implementation unexpectedly requires a migration, additionally verify:

```bash
uv run alembic upgrade head
```

against a fresh PostgreSQL database and ensure the existing migration integration tests pass.

Do not edit an existing migration merely to avoid adding a legitimate new migration.

---

## Completion report

When implementation is complete, provide:

### Changed

Summarise:

- the new benefit domain model;
- the supported `BenefitType` classifications;
- any mapping/alignment changes;
- tests added or updated.

### Database and migrations

Expected:

```text
None.
Existing benefits schema and ck_benefits_type retained unchanged.
```

If that is not true, state the migration and why it was necessary.

### API/MCP contracts

```text
None.
```

### Tests and verification

List:

- unit tests added;
- PostgreSQL tests updated;
- exact commands run;
- results.

Do not claim an unrun command passed.

### External configuration

```text
None.
```

### Deviations

Describe any meaningful deviation from this specification.

Use:

```text
None.
```

when there were no deviations.

### Remaining risks or follow-up

Expected later work includes:

- structured reward/value rules;
- cashback amount and percentage models;
- warranty-specific structured value/rule semantics where required;
- gift-specific structured value semantics where required;
- publication validation;
- deterministic eligibility evaluation;
- purchase matching;
- REST/MCP exposure.

Do not implement those as part of PR 5.

## Implementation verification — 2026-10-06

Implemented on `pr5-benefit-model` from fetched `origin/main` at `1916c37`,
which includes PR 3 and PR 4. No scoped backend AGENTS.md, existing benefit
domain model, or reward-rule model was present. Alembic head remains
`0002_core_promotion_schema`; ORM and migration benefit constraints both retain
exactly `cashback`, `extended_warranty`, and `free_gift`.

Acceptance evidence:

- `app/domain/benefits.py`: standard-library-only StrEnum and immutable common
  value with explicit classification validation; no reward or eligibility behaviour.
- `tests/unit/test_benefits.py`: 26 passing cases for exact values, string conversion,
  all classifications, optional description, invalid inputs, and immutability.
- `tests/integration/test_core_promotion_schema.py`: 55 passing cases including
  every enum member's PostgreSQL round trip, unsupported classifications rejected
  by `ck_benefits_type`, existing ownership/cascades, and migration/metadata parity.
- Full backend suite: 166 passed, including lifecycle retention and migration
  downgrade/re-upgrade regression coverage. One existing Starlette/httpx deprecation
  warning was emitted.
- Scope review: only the domain value, tests, README, and this task document changed.
  ORM, migrations, dependencies, application use cases, transports, and configuration
  are unchanged.

Commands run from `backend/` (with `UV_CACHE_DIR=/private/tmp/ppbc-uv-cache`
to use a writable cache):

```bash
uv sync --locked --extra dev
uv run ruff format tests/integration/test_core_promotion_schema.py
uv run ruff format --check .
uv run ruff check .
uv run pytest tests/unit/test_benefits.py
uv run alembic heads
uv run pytest tests/integration/test_core_promotion_schema.py --tb=short
uv run pytest --tb=short
```

All final checks passed. The first formatting check identified one assertion to
format; it was corrected. The initial integration invocation inside the sandbox
could not access Docker; the PostgreSQL and full-suite commands passed after
running with Docker access. `git diff --check` also passed.

Database/migrations, REST/MCP contracts, and external configuration: None.
Deviations: None. Remaining issues: None within PR 5 scope.
