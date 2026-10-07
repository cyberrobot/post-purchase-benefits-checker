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
`YYYY-MM-DD`) into this shared contract. Detailed eligibility and transport endpoints
remain future work.

## Promotion candidate matching

Call `match_promotion_candidates(request, identity_resolver, repository)` from
`app.application.promotion_candidate_matching`, using the existing `IdentityResolver`
and `SqlAlchemyPromotionRepository(session)`. It resolves brand, retailer, then the
model-or-SKU field with both canonical manufacturer and retailer contexts. Raw request
fields remain unchanged. `UnresolvedPurchaseIdentity` identifies the failed request
field, PR 7 match status, and deterministic candidate IDs; it stops later lookups.
Identity/promotion persistence failures propagate as safe errors, never empty results.

Successful `PromotionCandidateSet` results contain immutable `ResolvedPurchaseIdentity`
UUIDs and a tuple of `PromotionCandidate` variant references. An empty tuple means all
identities resolved but no published variant passed the broad filters. Candidates are
potential applicability only, without an eligible/ineligible classification.

The adapter filters in PostgreSQL by manufacturer, explicit product association,
exact retailer or retailer-independent (`NULL`) variant, `active`/`expired` status,
and inclusive known purchase-date bounds. Missing bounds remain open at this stage;
no product links never means all products. Archived and unpublished records are excluded.
All matching variants remain separate, ordered by promotion `created_at DESC`,
promotion ID, then variant ID. Reads select only candidate fields and suppress autoflush;
the caller owns the read session/transaction. No locks or writes are introduced.

Price, claim windows, benefits, requirements, channels, and retailer groups do not
affect candidate selection. Detailed eligibility evaluation is later work. No schema,
public REST/MCP contract, dependency, or configuration changes are required.

## Core eligibility rules

`app.domain.eligibility_rules` evaluates typed restrictions against immutable
`PurchaseEligibilityFacts`: canonical manufacturer, product, and retailer UUIDs plus
a required calendar purchase date. Model/SKU applicability uses the resolved
`Product.id`, never raw identifiers. Price, channel, product condition, and purchase
country are optional facts; no values are inferred from identities or other facts.
`PurchaseChannel` is reused from identity normalisation; `PurchaseCondition` defines
`new`, `refurbished`, and `used`. Country codes require exactly two ASCII uppercase
letters, with exact matching and no alias conversion or country registry lookup.

`PromotionEligibilityRules` holds optional `ManufacturerRule`, `ProductRule`,
`RetailerRule`, `PurchaseChannelRule`, `PurchaseDateRule`, `PurchasePriceRule`,
`PurchaseConditionRule`, and `CountryRule` values. Membership rules require a
non-empty set of canonical values and freeze supplied mutable sets. Date and price
rules require at least one bound, allow an open opposite bound, reject inverted
ranges, and include both boundaries. Shared `app.domain.purchase_values` validation
preserves `CheckPurchaseRequest` date/price semantics: no timestamps, parsing,
rounding, non-finite/negative prices, floats, or more than two fractional places.
Prices and thresholds are exact GBP `Decimal` values; zero is known information.
Wrong types raise `TypeError`; invalid values raise `ValueError` at construction.

Call `evaluate_eligibility_rules(facts, rules)` to get a tuple of immutable
`RuleEvaluation` values in manufacturer, product, retailer, channel, date, price,
condition, country order. Each contains a stable `RuleKind`, `RuleStatus`
(`satisfied`, `not_satisfied`, `unknown`), and `RuleReasonCode`. A configured rule
with a missing optional fact produces `unknown`; a known mismatch produces
`not_satisfied`. An absent rule imposes no restriction and produces no result.
Every configured rule is evaluated, including those after a failure.

Evaluation uses no clock, database, network, configuration, logging, or model provider.
These are per-rule outcomes only. Mapping published promotion records into rules,
application orchestration, claim-window calculation, requirements,
and reward calculation remain later work. PR 7–9 matching, the five-field
`CheckPurchaseRequest`, persistence, migration head, and REST/MCP remain unchanged.

## Eligibility result classification

Call `app.domain.eligibility_result.classify_eligibility(rule_evaluations,
claim_window_status)` for one promotion variant. It consumes the PR 10 tuple of
`RuleEvaluation` values and a canonical `ClaimWindowStatus`: `open`, `not_yet_open`,
or `expired`. Claim timing is supplied by the caller; no dates are calculated and
no clock, persistence, network, or model provider is consulted.

Any `not_satisfied` outcome produces `NOT_ELIGIBLE`, ahead of unknowns and claim
timing. Otherwise, any `unknown` produces `POTENTIALLY_ELIGIBLE`, ahead of claim
timing. With all configured rules satisfied (including an empty rule tuple), the
claim state produces `ELIGIBLE`, `CLAIM_NOT_YET_OPEN`, or `EXPIRED`, respectively.
`PromotionStatus.EXPIRED` denotes historical publication and is rejected as claim
timing; it never directly determines the result.

The immutable `EligibilityResult` retains classification, reasons, the complete
original evaluations, and supplied claim state. Rule-driven decision reasons retain
every decisive PR 10 reason code and rule kind in input order. For satisfied/empty
rules, reasons always contain `all_configured_rules_satisfied` followed by the
appropriate `claim_window_open`, `claim_window_not_yet_open`, or
`claim_window_expired` code. Reasons contain predefined enums, not display prose
or raw purchase payloads. Wrong types raise `TypeError`; an empty result reason
tuple raises `ValueError`. Candidate matching and application/transport contracts
remain unchanged; purchase-check orchestration and claim-window evaluation are
future work.


## Fixed claim windows

`app.domain.claim_windows.FixedClaimWindow(start_date, end_date)` holds a complete,
immutable pair of calendar dates. Construction rejects timestamps, wrong types,
and inverted bounds; a one-day window is valid. Call
`evaluate_fixed_claim_window(window, evaluation_date)` with an explicit calendar date.
Both bounds are inclusive: before opening returns PR 11 `not_yet_open`, opening
through deadline returns `open`, and after deadline returns `expired`. The immutable
`ClaimWindowEvaluation` retains canonical `ClaimWindowStatus`, `opens_on`, and
`deadline_on`. No system clock, purchase date, or lifecycle state is used.

Migration `0004_fixed_claim_windows` adds nullable PostgreSQL `DATE` columns
`promotions.claim_start_date` and `promotions.claim_end_date`. The
`ck_promotions_claim_dates_complete` and `ck_promotions_claim_dates` checks enforce
both absent or both present, and ordered bounds. Existing rows retain `NULL`/`NULL`
without backfill or defaults. Apply the migration before deploying code that reads
the fields. Downgrade removes the checks and columns, discarding configured claim dates.

`PromotionRecord` and promotion repository reads preserve both fields; absent dates
represent no fixed definition and supply no claim status. Construct a domain window
only when both dates exist. Publication completeness, purchase-check orchestration,
and transport contracts remain future work. Claim expiry never changes promotion
lifecycle or candidate filtering.


## Relative and delayed claim windows

`RelativeClaimWindow(start_offset_days, end_offset_days)` stores immutable whole
non-negative calendar-day offsets from the purchase date. Exact Python integers
are required; booleans, strings, floats, decimals, negative or inverted bounds
are rejected. Equal offsets define a one-day window, and zero means purchase day.

Call `evaluate_relative_claim_window(window, purchase_date, evaluation_date)` with
explicit calendar dates (timestamps are rejected). It derives opening and deadline
dates using calendar-day arithmetic, then reuses fixed-window inclusive evaluation
and the existing `ClaimWindowEvaluation`/`ClaimWindowStatus` contracts. For a
2026-10-01 purchase, offsets 0..30 give 2026-10-01 through 2026-10-31; offsets
30..60 give 2026-10-31 through 2026-11-30. Month/year boundaries and leap days follow
Python date arithmetic. Unrepresentable derived dates raise a stable `ValueError`,
without clamping or returning a claim status. No clock or lifecycle state is used.

Migration `0005_relative_claim_windows` (file `0005_relative_delayed_claim_windows.py`)
adds nullable PostgreSQL integers `promotions.claim_start_offset_days` and
`promotions.claim_end_offset_days`. Its revision ID fits Alembic's 32-character
version field. The checks `ck_promotions_claim_offset_days_complete`,
`ck_promotions_claim_offset_days_nonnegative`, `ck_promotions_claim_offset_days`,
and `ck_promotions_claim_window_single_type` require complete, non-negative, ordered
offsets and prohibit configuring fixed and relative definitions together. Either
form or neither is valid. Existing rows retain fixed data and receive NULL offsets
without defaults or backfill. No offset indexes or type discriminator are added.
Apply this migration before deploying code reading the new fields. Downgrade drops
only the new constraints/columns, discarding relative offsets and preserving fixed dates.

`PromotionRecord` and repository reads preserve exact offsets without calculating
claim dates. Missing definitions produce no implicit claim status. Wording
normalization, publication completeness, mapping persisted definitions into the
canonical evaluator, final purchase-check orchestration/classification, and REST/MCP
contracts remain later work. `CheckPurchaseRequest` is unchanged.
