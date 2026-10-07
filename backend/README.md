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
Expired and archived promotions cannot reactivate. Same-state requests are no-ops.

Call `change_promotion_status(partial(promotion_transaction, session_factory), id, status)`
from the application layer. The operation owns a dedicated session and transaction,
commits before returning, and rolls back on failure. The repository conditionally
updates the expected state; a competing write is reconciled as an already-completed
no-op or `PromotionConflict`. Not-found, invalid-transition, and persistence failures
are distinct exceptions. Do not share a session containing pending ORM changes.

`SqlAlchemyPromotionRepository` returns immutable application records rather than ORM
objects. Identity lookup includes every state. General queries accept explicit state
filters; active queries select only active. Historical published queries select only
expired (and accept only expired as an explicit non-empty state filter). Results order
by `created_at DESC, id ASC`.
The complete retained graph remains accessible through the existing persistence models.
`expired` is historical published data. `archived` is retained data excluded from normal
processing and may represent either a formerly published promotion or an abandoned
candidate. The current schema does not persist publication history, so archived records
cannot reliably be classified as previously published and are excluded from historical
published queries. Archived records remain available through `get_promotion(id)` and
`list_promotions(statuses=[PromotionStatus.ARCHIVED])`. Distinguishing formerly published
archives from never-published archives requires future publication history/versioning.

Retirement updates status and the normal update timestamp, preserving dates, graph,
references, and provenance. No reads or startup paths expire promotions automatically.
The review → active transition validates source provenance in the same transaction
before attempting the conditional status update. Broader publication completeness
(product applicability, benefits, dates, and eligibility rules) remains future work. No transport API,
new migration, audit log, or versioning workflow is introduced.

## Benefit domain model

`app.domain.benefits.Benefit` is an immutable value containing `benefit_type`, `name`,
and optional `description`. `BenefitType` defines the stable, case-sensitive values
`cashback`, `extended_warranty`, and `free_gift`, matching the existing persistence
constraint. Construction validates classification and text types; unsupported
classifications raise `ValueError` without a fallback.

Names and descriptions are display text, not a source for calculating reward amounts,
warranty durations, or eligibility. Future structured reward/value models should
compose with this common value. Adding a classification requires an explicit enum
member, a new migration updating `ck_benefits_type`, and domain/PostgreSQL tests.
The domain model is separate from `app.db.models.Benefit`; no schema or transport
change is introduced. See the [PR 5 specification](../.codex/tasks/pr-5-benefit-model.md).


## Publication source provenance

`app.domain.promotion_provenance` defines canonical `SourceType` and `SourceRole`
values, immutable `PromotionSourceRecord` evidence, and a derived `PublishedProvenance`
view. `list_promotion_sources(id)` loads normalized evidence through the application
repository boundary without returning ORM objects or duplicating persisted fields.

Publication requires exactly one primary and one claim association. Both require
an absolute HTTP(S) URL, a supported classification, and timezone-aware retrieval
and verification timestamps with verification at or after retrieval. Multiple primary
or claim associations are ambiguous, even when one is incomplete; terms/supporting
sources never substitute. Repeated retrievals and equal URL values remain allowed.
URLs are parsed locally without rewriting the stored evidence, fetching content,
resolving DNS, or inferring manufacturer ownership. The curated role and recorded
verification supply official provenance; this gate does not independently verify it.

`PromotionProvenanceError.reason_code` identifies expected publication rejection.
Missing, ambiguous, unverified, invalid URL, unsupported classification, and invalid
timestamp failures remain distinct from lifecycle, conflict, and safe persistence
errors. Rejection performs no lifecycle write, and correcting evidence allows retry.
Other transitions and same-state requests do not load or revalidate provenance.
Expiry and archival preserve evidence. No migration or transport change is required.

## Canonical purchase identity resolution

`app.domain.identity_normalisation` provides NFKC/case-fold normalisation: human
text collapses whitespace, while model/SKU identifiers remove whitespace. Both
preserve punctuation and reject non-string, empty, oversized, or unsupported
control-character input. Raw and normalised inputs are bounded to 255 characters;
Unicode expansion is checked after normalisation too.

Use `IdentityResolver(SqlAlchemyIdentityRepository(session))` for internal
read-only reference resolution. The caller owns the session/transaction; resolver
queries suppress autoflush and never create aliases or other reference data.
`resolve_manufacturer`, `resolve_retailer`, and `resolve_retailer_group` combine
canonical names/slugs with curated aliases. `resolve_model` requires a canonical
manufacturer UUID; `resolve_sku` requires a retailer UUID and may also constrain
manufacturer. `resolve_product(value, manufacturer_id=..., retailer_id=...)`
combines model and SKU candidates for a single model-or-SKU field, requiring at
least one context. It excludes SKU candidates from another supplied manufacturer.

`MatchResult` exposes `status` (`matched`, `not_found`, `ambiguous`), `canonical_id`
(only for one distinct candidate), and sorted, deduplicated UUID `candidate_ids`.
Results do not depend on database row order. Invalid input fails before queries;
database failures or invalid persisted canonical text raise a safe
`IdentityPersistenceError`, never a guessed match. Null/blank legacy model numbers
remain persisted but do not supply an accepted identifier.

`resolve_purchase_channel` is a domain-only operation. It resolves online/web/website
and in_store/in-store/instore/store/shop, returning `ChannelMatchResult` with a
canonical `PurchaseChannel` or `not_found`. Unsupported values have no fallback.

Migration `0003_identity_normalisation` adds manufacturer, retailer, product-model,
and retailer-group aliases, retailer product SKUs, retailer groups and memberships.
Group aliases are consumed by raw group-name resolution. No canonical display-field
normalised columns, seeded catalogue, or alias backfill is required. Existing
canonical IDs, model numbers, promotion state/graph and provenance are retained.
Apply the migration before using the new repository.

Curated ORM alias/SKU writes derive their normalised key on insert/update using the
domain functions, including when the raw value changes. Direct SQL and bulk writes
bypass these hooks and must explicitly supply keys from those same functions. Such
writes belong to trusted reference-data maintenance, not runtime matching. PostgreSQL
bounds/non-empty checks, composite primary keys, foreign keys and lookup indexes
protect integrity. A duplicate per-owner alias, identical SKU mapping, or membership
fails with a uniqueness violation; the caller owns rollback/savepoint recovery.
Collisions across distinct identities remain representable. Alias owners cascade
owned aliases; SKU references restrict canonical retailer/product deletion;
memberships cascade on parent deletion without deleting other canonical entities.

`retailer_group_ids` returns zero/one/multiple current group UUIDs. Membership has
no historical effective dates and supplies no promotion eligibility inference.
All resolution remains separate from purchase transports, promotion selection,
eligibility and ingestion. No external calls, configuration or dependencies are added.

## Purchase input contract

`app.application.purchase_check.CheckPurchaseRequest` is an immutable application
value with required `brand`, `model`, `retailer`, and `purchase_date`, plus optional
`purchase_price` (default `None`). Identity fields reuse the bounded PR 7 normalisers
for validation while retaining the caller's exact raw strings. Unknown or ambiguous
canonical identities remain valid input; construction performs no reference lookup.

`purchase_date` must be a Python calendar `date`; `datetime` and strings are rejected.
No comparison with today occurs. `purchase_price` represents a UK/GBP amount and must
be a finite, non-negative `Decimal` with at most two fractional decimal places.
No coercion, rounding, or quantization occurs, and missing price differs from zero.
Wrong types raise `TypeError`; invalid values raise `ValueError`.

Construction is pure and independent of persistence, network services, and transport
frameworks. Future REST/MCP adapters should parse wire values (including ISO full-date
`YYYY-MM-DD`) into this shared contract. Identity-resolution orchestration, eligibility,
result contracts, and transport endpoints remain future work.
