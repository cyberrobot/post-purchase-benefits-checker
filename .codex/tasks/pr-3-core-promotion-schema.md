# PR 3 — Core Promotion Schema

## Repository state

**Expected branch:**  
`pr3-core-promotion-schema`

**Base branch:**  
`main`

**Dependencies:**  
- PR 1 — Project Foundation: merged.
- Existing PostgreSQL, SQLAlchemy 2, Alembic, and Testcontainers foundation.
- PR 2 is not a functional dependency. If it merges first, create/rebase this branch from the latest `main`.
- No new runtime service, external provider, or infrastructure dependency.

### Read first

Before making changes, read:

- `AGENTS.md`
- `.codex/tasks/TEMPLATE.md`
- `.codex/tasks/pr-1-project-foundation.md`
- `backend/README.md`
- `backend/app/db/base.py`
- `backend/app/db/engine.py`
- `backend/app/db/session.py`
- `backend/migrations/env.py`
- `backend/migrations/versions/0001_initial_baseline.py`
- `backend/tests/conftest.py`
- `backend/tests/integration/test_postgres_migrations.py`
- `backend/tests/integration/test_session_isolation.py`

As of the current `main` branch there is no scoped `backend/AGENTS.md`. If one exists on the implementation branch, read and follow it.

### Primary change area

Persistence and migration.

This PR introduces the first product-domain persistence model for promotions and their supporting reference/provenance data.

### Canonical implementation examples

Use the existing foundation as the implementation reference:

- `app.db.base.Base` for SQLAlchemy metadata.
- `backend/migrations/env.py` for Alembic metadata wiring.
- `0001_initial_baseline.py` for migration conventions.
- `backend/tests/conftest.py` for real PostgreSQL/Testcontainers fixtures.
- `test_postgres_migrations.py` for migration verification.

There is currently no existing product-domain SQLAlchemy model that must be preserved as a modelling precedent.

### Relevant symbols

Inspect before editing:

- `app.db.base.Base`
- `migrations.env.target_metadata`
- `postgres_container`
- `postgres_engine`
- `migrated_test_database`
- `db_session`
- `db_session_factory`

### Expected change surface

Expected additions or changes include:

- `backend/app/db/models/`
- `backend/app/db/models/__init__.py`
- SQLAlchemy model modules for the core promotion schema
- model registration required for `Base.metadata`
- `backend/migrations/env.py` if explicit model imports are required
- a new Alembic migration following the current migration head
- `backend/tests/integration/test_core_promotion_schema.py`
- `backend/tests/integration/test_postgres_migrations.py`

A small persistence-only helper or mixin may be added if it meaningfully removes duplication without introducing a generic repository framework.

### Excluded areas

Do not implement as part of this PR:

- REST endpoints
- MCP tools
- application services
- repositories/query services
- purchase records
- claims
- eligibility evaluation
- eligibility rules
- reward calculation or reward rules
- claim-window calculation
- promotion matching
- ingestion or scraping
- AI/LLM extraction
- publication workflows
- external HTTP requests
- authentication/authorization
- background workers or scheduled jobs
- frontend/UI
- Redis
- arbitrary JSON rule engines
- seed data for real manufacturers, products, retailers, or promotions

Do not add fields purely for anticipated features where the current model does not require them.

### Unknowns Codex must verify

Before implementation:

- Verify the current Alembic head after rebasing onto the implementation branch. Do not assume `0001_initial_baseline` is still head if another migration has merged.
- Verify whether PR 2 or another merged change introduced additional database/model conventions.
- Verify whether a scoped backend `AGENTS.md` has been added.
- Verify how model modules need to be imported so that all tables are present in `Base.metadata`.
- Verify whether naming conventions for indexes or constraints have been introduced since this specification was written.
- Verify the actual migration revision identifier from repository state rather than blindly using `0002`.

---

## Objective

Introduce the common relational data model used to describe post-purchase promotions.

After this PR, PostgreSQL must be able to persist a normalized promotion graph containing:

- manufacturers
- products
- retailers
- promotions
- promotion variants
- benefits
- requirements
- official/supporting sources

The model must support:

- a manufacturer owning multiple products and promotions;
- a promotion containing multiple variants;
- retailer-specific and retailer-independent variants;
- a variant applying to one or more products;
- a variant containing one or more benefits;
- a variant containing zero or more claim requirements;
- multiple evidence/source records for a promotion;
- source roles such as primary promotion information, terms, claim page, or supporting evidence;
- candidate, published, expired, and historical promotion lifecycle states without deleting historical promotions.

The schema must provide strong relational integrity and provenance while remaining independent from eligibility evaluation, reward calculation, ingestion, REST, MCP, and AI behaviour.

Completion means the ORM mappings, Alembic migration, relational constraints, and PostgreSQL integration tests exist and pass against a real PostgreSQL instance.

---

## Architecture and invariants

Preserve the repository architecture:

- SQLAlchemy models are persistence concerns and must not contain FastAPI behaviour.
- Domain decisions must not depend on SQLAlchemy sessions or ORM objects.
- Alembic is the only mechanism used to evolve the production database schema.
- Runtime eligibility remains deterministic and is not implemented in this PR.
- AI-extracted data must eventually pass a separate validation/publication boundary before becoming usable by runtime eligibility.
- Promotion provenance must remain representable independently from ingestion implementation.

Task-specific invariants:

1. A `Product` belongs to exactly one `Manufacturer`.
2. A `Promotion` belongs to exactly one `Manufacturer`.
3. A `PromotionVariant` belongs to exactly one `Promotion`.
4. A retailer-specific variant references at most one `Retailer`.
5. One promotion may contain multiple variants for the same retailer when product or benefit terms differ.
6. A variant may reference multiple products.
7. Benefits belong to promotion variants, not directly to manufacturers or retailers.
8. Requirements belong to promotion variants.
9. Sources are independent evidence records and may be associated with promotions through an explicit association table.
10. Repeated retrieval of the same URL must remain representable. Do not make source URL globally unique.
11. Deleting reference data must not silently change promotion meaning. Manufacturer, product, retailer, and associated source deletion must be restricted while referenced.
12. Component records belonging exclusively to a promotion may cascade when that promotion or variant is explicitly deleted.
13. Historical promotions should normally transition to `expired` or `archived` rather than be deleted.
14. Candidate states may contain incomplete data. Completeness rules required before publication belong to the later validation/publication layer.
15. `NULL retailer_id` on an active variant means the variant is not restricted to a specific retailer. In non-published candidate states it may also represent information not yet fully extracted; later publication validation must distinguish and validate this before activation.
16. An absence of product associations must not be interpreted by runtime code as "all products". Later publication validation must require explicit product applicability unless a future rule type explicitly defines broader scope.
17. Do not use native PostgreSQL enum types for extensible business classifications. Prefer bounded text columns with named CHECK constraints so values can evolve through ordinary migrations.
18. Do not store executable expressions, Python code, SQL, prompt fragments, or arbitrary executable promotion rules in the schema.

---

## API and contract changes

None.

This PR introduces persistence contracts only.

No REST route, MCP tool, OpenAPI schema, request/response model, or externally consumed application interface should change.

---

## Domain and application behaviour

This PR does not implement application behaviour.

It establishes persistence semantics that future application behaviour must respect.

### Promotion lifecycle

`promotions.status` must support the initial values:

- `discovered`
- `extracted`
- `review`
- `active`
- `expired`
- `archived`

Semantics:

- `discovered`: promotion identity/evidence has been discovered but structured extraction may be incomplete.
- `extracted`: structured candidate data exists but has not passed publication validation.
- `review`: candidate data is awaiting or undergoing validation.
- `active`: validated/published promotion eligible for future runtime consideration.
- `expired`: previously published promotion retained for historical purchase checking.
- `archived`: retained record that is no longer part of normal active processing.

This PR only persists lifecycle state. It must not implement automatic state transitions or publication.

No code introduced by this PR may automatically move candidate data to `active`.

### Benefit types

The initial supported benefit classifications are:

- `cashback`
- `extended_warranty`
- `free_gift`

A benefit records what kind of benefit exists and its human-readable identity/description.

This PR must **not** implement:

- fixed reward amounts
- percentages
- basket tiers
- product-specific reward amounts
- conditional bonuses
- reward calculation

Those belong to the later reward-rule model.

### Requirement types

The initial structured requirement classifications are:

- `receipt`
- `serial_number`
- `registration`
- `invoice`
- `barcode`
- `imei`

Requirements describe evidence or actions required when claiming a promotion.

Conditional requirement evaluation is out of scope.

### Eligibility-specific rules

Not implemented in this PR.

Do not introduce SKU/date/price/quantity/country/channel eligibility evaluators or rule-expression storage.

Purchase dates stored on promotions describe the known promotion purchase period only; determining whether a purchase qualifies remains a later application/domain responsibility.

### Ingestion/publication rules

No ingestion or publication workflow is implemented.

The schema must merely allow future ingestion to persist candidate promotions and provenance without making candidate records implicitly eligible.

Future publication logic must be able to require, at minimum, valid product applicability, benefits, dates where required by the promotion, and verified official provenance before activation.

---

## Persistence, transactions, and migrations

### Identifier strategy

Use UUID primary keys for domain entities.

Use application-side UUID generation consistent with Python 3.13 and the repository's dependency set. Do not introduce a PostgreSQL extension solely to generate IDs.

Association tables may use composite primary keys instead of surrogate UUIDs.

Use timezone-aware timestamps for persisted timestamps.

### `manufacturers`

Required fields:

| Column | Requirements |
| --- | --- |
| `id` | UUID primary key |
| `name` | non-empty bounded string, not null |
| `slug` | stable normalized identifier, not null, unique |
| `created_at` | timezone-aware timestamp, not null, database default |
| `updated_at` | timezone-aware timestamp, not null, database default; application-managed on updates |

No manufacturer-specific scraping or provider configuration belongs here.

### `products`

Required fields:

| Column | Requirements |
| --- | --- |
| `id` | UUID primary key |
| `manufacturer_id` | FK to `manufacturers.id`, not null |
| `name` | non-empty bounded string, not null |
| `slug` | stable manufacturer-scoped identifier, not null |
| `model_number` | nullable bounded string |
| `created_at` | timezone-aware timestamp |
| `updated_at` | timezone-aware timestamp |

Constraints:

- unique `(manufacturer_id, slug)`
- deleting a referenced manufacturer must be restricted

Do not assume `model_number` is globally unique.

Do not add retailer SKUs or arbitrary identifier tables in this PR.

### `retailers`

Required fields:

| Column | Requirements |
| --- | --- |
| `id` | UUID primary key |
| `name` | non-empty bounded string, not null |
| `slug` | stable normalized identifier, not null, unique |
| `created_at` | timezone-aware timestamp |
| `updated_at` | timezone-aware timestamp |

Do not add retailer API credentials, scraping configuration, or network details.

### `promotions`

Required fields:

| Column | Requirements |
| --- | --- |
| `id` | UUID primary key |
| `manufacturer_id` | FK to `manufacturers.id`, not null |
| `name` | promotion/campaign display name, not null |
| `slug` | stable manufacturer-scoped identifier, not null |
| `status` | bounded text with lifecycle CHECK constraint |
| `purchase_start_date` | nullable `DATE` |
| `purchase_end_date` | nullable `DATE` |
| `created_at` | timezone-aware timestamp |
| `updated_at` | timezone-aware timestamp |

Constraints:

- unique `(manufacturer_id, slug)`
- when both dates are present, `purchase_start_date <= purchase_end_date`
- manufacturer deletion restricted while promotions exist
- status limited to the lifecycle values defined above

Dates are nullable because early candidate states may be incomplete.

Do not add claim-window fields here. Claim-window semantics are a separate domain concept.

### `promotion_variants`

Required fields:

| Column | Requirements |
| --- | --- |
| `id` | UUID primary key |
| `promotion_id` | FK to `promotions.id`, not null |
| `retailer_id` | nullable FK to `retailers.id` |
| `code` | stable promotion-scoped variant identifier |
| `name` | optional human-readable variant label |
| `created_at` | timezone-aware timestamp |
| `updated_at` | timezone-aware timestamp |

Constraints:

- unique `(promotion_id, code)`
- promotion deletion cascades to its variants
- retailer deletion is restricted while referenced by a variant

`retailer_id = NULL` represents a retailer-independent variant once the promotion is published.

Do not add retailer/channel eligibility logic in this PR.

### `promotion_variant_products`

Create an explicit many-to-many association between promotion variants and products.

Columns:

- `promotion_variant_id`
- `product_id`

Requirements:

- composite primary key on both columns
- variant deletion cascades association rows
- product deletion is restricted while referenced
- duplicate associations are impossible

Do not treat zero product rows as meaning every product.

### `benefits`

Required fields:

| Column | Requirements |
| --- | --- |
| `id` | UUID primary key |
| `promotion_variant_id` | FK to `promotion_variants.id`, not null |
| `benefit_type` | bounded text with CHECK constraint |
| `name` | human-readable benefit label, not null |
| `description` | nullable text |
| `created_at` | timezone-aware timestamp |
| `updated_at` | timezone-aware timestamp |

Allowed initial `benefit_type` values:

- `cashback`
- `extended_warranty`
- `free_gift`

Variant deletion cascades benefits.

Do not store reward calculation logic in this table.

### `requirements`

Required fields:

| Column | Requirements |
| --- | --- |
| `id` | UUID primary key |
| `promotion_variant_id` | FK to `promotion_variants.id`, not null |
| `requirement_type` | bounded text with CHECK constraint |
| `description` | nullable text/instructions |
| `created_at` | timezone-aware timestamp |
| `updated_at` | timezone-aware timestamp |

Allowed initial requirement types:

- `receipt`
- `serial_number`
- `registration`
- `invoice`
- `barcode`
- `imei`

Variant deletion cascades requirements.

Do not introduce conditional rule expressions.

### `sources`

A source represents a particular retrieved evidence record, not merely a globally unique URL.

Required fields:

| Column | Requirements |
| --- | --- |
| `id` | UUID primary key |
| `url` | source URL, not null |
| `source_type` | bounded text |
| `title` | nullable human-readable title |
| `retrieved_at` | timezone-aware timestamp, not null |
| `verified_at` | nullable timezone-aware timestamp |

Initial `source_type` values:

- `web_page`
- `pdf`
- `other`

Constraints:

- `verified_at` must be greater than or equal to `retrieved_at` when present
- URL must **not** be globally unique

URL network/security validation belongs to the later retrieval boundary, not this persistence model.

A later retrieval of the same URL must be able to create another source record so historical evidence is not overwritten.

### `promotion_sources`

Create an explicit many-to-many association between promotions and sources.

Columns:

| Column | Requirements |
| --- | --- |
| `promotion_id` | FK to `promotions.id` |
| `source_id` | FK to `sources.id` |
| `role` | bounded text indicating how the source relates to the promotion |

Use a composite primary key on `(promotion_id, source_id)`.

Initial source roles:

- `primary`
- `terms`
- `claim`
- `supporting`

Semantics:

- `primary`: principal official promotion page/document.
- `terms`: official terms and conditions.
- `claim`: official claim/registration destination.
- `supporting`: additional official evidence.

Promotion deletion cascades association rows.

Source deletion is restricted while the source remains associated with a promotion.

The `claim` role is the canonical way for later application code to identify an official claim URL. Do not duplicate claim URL state on `promotions` unless a later requirement demonstrates that the association model is insufficient.

### Indexes

Add indexes required for normal foreign-key relationship access and integrity operations where PostgreSQL does not provide them automatically.

Do not add speculative eligibility-oriented indexes yet, such as complex combinations of:

- status
- purchase date
- retailer
- product
- manufacturer

Those should be introduced when concrete eligibility query patterns exist and can be measured.

### Transactions

The migration must run transactionally under the existing Alembic/PostgreSQL setup.

No new application transaction boundary is introduced because this PR contains no write service.

Future application code creating a complete promotion graph should own its transaction at the application/service boundary rather than committing independently from individual model objects.

### Migration

Create a new Alembic revision from the actual current migration head.

The upgrade must create tables in dependency-safe order.

The downgrade must remove them in reverse dependency order without modifying `0001_initial_baseline.py` or other deployed migration history.

Do not seed real promotion data from the migration.

### Migration correctness

Verify against the repository's real PostgreSQL Testcontainer.

Migration tests must demonstrate:

1. a fresh database upgrades to the new head;
2. expected core tables exist;
3. expected constraints exist and work;
4. downgrading one revision removes the core promotion schema while leaving the previous foundation revision intact;
5. upgrading again restores the schema successfully.

Update the existing migration-head assertions accordingly.

Do not continue asserting that downgrading one revision results in no Alembic revision once a second revision exists.

---

## External services and network access

None.

This PR must not make external HTTP calls.

Source URLs are persisted as untrusted data only.

No URL should be fetched, resolved, redirected, or otherwise contacted as part of model creation or tests.

---

## Security and privacy

The schema contains public promotion metadata and provenance rather than customer data.

Requirements:

- Treat persisted source URLs and source metadata as untrusted input.
- Do not execute, fetch, import, deserialize, or evaluate source content.
- Do not introduce arbitrary executable promotion-rule fields.
- Do not store credentials, cookies, tokens, API keys, or provider secrets in source or promotion records.
- Use explicit bounded string fields where practical rather than unbounded arbitrary metadata blobs.
- Preserve source provenance rather than overwriting previously retrieved evidence.
- Do not add receipt, customer, payment, address, or other personal-data tables in this PR.

No authentication/authorization change is required.

---

## Configuration and deployment

None.

### Environment variables

No new environment variables.

### Runtime/deployment changes

No intended changes to:

- Docker image structure
- Railway configuration
- health/readiness behaviour
- PostgreSQL connection configuration
- worker processes
- scheduled jobs

The normal deployment requirement to apply Alembic migrations before serving the new application version remains unchanged.

---

## Observability and operations

No new runtime observability is required because this PR introduces no new request, job, or external-service execution path.

Existing startup, health, logging, and Sentry behaviour must remain unchanged.

Migration failures must remain visible through the existing Alembic/process output.

Do not add a new telemetry dependency.

---

## Failure, consistency, and recovery

Important consistency cases:

### Invalid relationship

Foreign-key constraints must prevent orphaned products, promotions, variants, benefits, requirements, and associations.

### Duplicate association

Attempting to associate the same product with the same promotion variant twice must fail through the composite primary key.

Attempting to associate the same source with the same promotion twice must fail through the composite primary key.

### Invalid lifecycle/type value

Unsupported promotion statuses, benefit types, requirement types, source types, or source roles must fail through database CHECK constraints.

### Invalid purchase period

A promotion with both dates present and `purchase_start_date > purchase_end_date` must be rejected.

### Invalid verification chronology

A source with `verified_at < retrieved_at` must be rejected.

### Referenced reference-data deletion

Deleting a manufacturer, product, retailer, or associated source that is still required by persisted promotion data must fail rather than silently altering the meaning of the promotion.

### Promotion deletion

If a promotion is explicitly deleted, its owned variant graph and promotion-source association rows may cascade.

Independent manufacturer, product, retailer, and source records must not be implicitly deleted.

### Migration failure

A failed migration must roll back through the existing PostgreSQL/Alembic transaction semantics rather than leave a partially created core schema.

---

## Acceptance criteria

### Behaviour

- [ ] The database can persist manufacturers, products, retailers, promotions, promotion variants, benefits, requirements, and sources.
- [ ] Promotions can contain multiple variants.
- [ ] Variants can be retailer-specific or retailer-independent.
- [ ] Variants can reference multiple products.
- [ ] Variants can contain multiple benefits and requirements.
- [ ] Promotions can reference multiple evidence sources with explicit source roles.
- [ ] Expired/archived promotions remain representable without deletion.
- [ ] No eligibility, reward calculation, claim-window, ingestion, REST, MCP, or AI behaviour is introduced.

### Data and consistency

- [ ] All primary entities use UUID identities.
- [ ] Required foreign keys and uniqueness constraints are enforced by PostgreSQL.
- [ ] Promotion status is constrained to the defined lifecycle.
- [ ] Benefit type is constrained to the initial supported values.
- [ ] Requirement type is constrained to the initial supported values.
- [ ] Source type and promotion-source role are constrained.
- [ ] Promotion purchase-date ordering is database-enforced.
- [ ] Source verification chronology is database-enforced.
- [ ] Source URLs are not globally unique, allowing historical retrieval records.
- [ ] Duplicate variant/product and promotion/source relationships cannot be created.
- [ ] Reference-data deletion cannot silently invalidate persisted promotion meaning.
- [ ] Candidate/unvalidated lifecycle states remain distinguishable from `active`.
- [ ] The migration applies successfully to a real PostgreSQL instance.
- [ ] One-revision downgrade returns the database to the previous foundation revision.
- [ ] Re-upgrade succeeds after downgrade.

### Security

- [ ] No secrets or customer personal data are introduced.
- [ ] Source URLs remain passive persisted data.
- [ ] No arbitrary executable rule representation is added.
- [ ] No network access occurs during schema/model operations or tests.

### Operations

- [ ] Existing `/health` behaviour remains unchanged.
- [ ] Existing configuration remains unchanged.
- [ ] Existing PostgreSQL/Testcontainers test infrastructure is reused.
- [ ] No new infrastructure or telemetry dependency is introduced.

### Code quality

- [ ] SQLAlchemy 2 patterns are used consistently.
- [ ] Models remain inside the persistence boundary.
- [ ] Alembic metadata includes every new model.
- [ ] Existing migration history is not rewritten.
- [ ] No unnecessary repository/service abstraction is introduced.
- [ ] No native PostgreSQL enum is introduced for extensible business classifications.
- [ ] Ruff formatting/linting and the affected pytest suites pass.

---

## Tests to add or update

### Unit tests

N/A.

This PR primarily introduces PostgreSQL mappings and relational constraints. These behaviours should be tested against PostgreSQL rather than duplicated with isolated unit mocks.

If a pure helper is introduced for reasons independent of SQLAlchemy, add focused unit coverage only for that helper.

### PostgreSQL integration tests

Add:

`backend/tests/integration/test_core_promotion_schema.py`

Cover at minimum:

- creation of a complete valid graph:
  - manufacturer
  - product
  - retailer
  - promotion
  - variant
  - variant/product association
  - benefit
  - requirement
  - source
  - promotion/source association
- relationship navigation through SQLAlchemy where mappings expose relationships
- manufacturer/product/promotion uniqueness constraints
- promotion/variant code uniqueness
- duplicate association rejection
- invalid promotion status rejection
- invalid benefit type rejection
- invalid requirement type rejection
- invalid source type/role rejection
- reversed purchase-date rejection
- invalid retrieved/verified timestamp ordering
- reference deletion restrictions
- owned promotion/variant cascade behaviour
- preservation of independent source/reference rows following permitted cascades

Update:

`backend/tests/integration/test_postgres_migrations.py`

Verify the actual new migration head and its downgrade/re-upgrade behaviour.

Use the existing real PostgreSQL Testcontainer fixtures.

Do not use SQLite for these tests.

### API/application tests

N/A.

No API or application service changes.

### MCP contract tests

N/A.

MCP is unchanged.

### External-boundary tests

N/A.

No external boundary is introduced.

---

## Verification commands

Run from `backend/`.

```bash
# Install/sync dependencies
uv sync --locked --extra dev

# Formatting check
uv run ruff format --check .

# Lint
uv run ruff check .

# Type checking
# N/A — the current repository does not configure a type-check command or mypy dependency.

# Targeted PostgreSQL schema tests
uv run pytest tests/integration/test_core_promotion_schema.py -v

# Migration verification
uv run pytest tests/integration/test_postgres_migrations.py -v

# PostgreSQL integration suite
uv run pytest -m integration

# Broader backend test suite
uv run pytest

# Explicit migration smoke check against configured PostgreSQL when appropriate
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head
```

Docker must be available for Testcontainers-backed PostgreSQL tests.

Do not invent a type-check command unless the repository gains a configured type checker before implementation.

If repository commands change before implementation, use the commands defined by the current `pyproject.toml`, README, and CI rather than preserving stale commands from this specification.

If a required command cannot be run, report:

1. the command;
2. why it could not run;
3. what was verified instead;
4. the remaining risk.

---

## Completion report

When implementation is complete, report:

### Changed

Summarise:

- SQLAlchemy models added;
- relationships introduced;
- lifecycle/type constraints;
- provenance/source modelling;
- significant model-registration changes.

### Database and migrations

State:

- migration revision created;
- tables created;
- foreign keys;
- uniqueness/check constraints;
- indexes;
- cascade/restrict behaviour;
- downgrade verification.

### API/MCP contracts

`None`.

### Tests and verification

List:

- integration tests added or updated;
- exact commands actually run;
- results.

Do not claim an unrun command passed.

### External configuration

`None`.

### Deviations

Describe any meaningful deviation from this specification and why it was necessary.

Use `None` when there were no deviations.

### Remaining risks or follow-up

Expected later work includes, but is not part of this PR:

- reward rules
- eligibility rules
- claim windows
- publication validation
- promotion ingestion
- deterministic purchase matching
- purchase/claim models
- REST/MCP exposure

Do not implement those follow-ups opportunistically as part of PR 3.