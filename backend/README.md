# Post-Purchase Benefits Checker backend

Python 3.13, FastAPI, SQLAlchemy 2, and PostgreSQL service exposing process health through `GET /health` and purchase eligibility through `POST /api/v1/eligibility/check`.

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


## Promotion claim requirements

`app.domain.requirements.Requirement` is an immutable, slotted domain value with
`requirement_type` and optional `description`. `RequirementType` defines the stable,
case-sensitive values `receipt`, `serial_number`, `registration`, `invoice`,
`barcode`, `imei`, and `installation_evidence`. Supported persisted strings are
converted to the canonical classification; unsupported values raise `ValueError`.
Descriptions must be strings or `None` and remain unparsed instruction text.

Requirements define what a claimant must supply or do, independently of benefits,
eligibility and claim windows. They contain no claimant evidence, completion state,
verification or submission behaviour. The existing `app.db.models.Requirement`
remains owned by its promotion variant, with unchanged cascade/FK behaviour.
Multiple definitions of the same classification remain permitted.

Migration `0006_promotion_requirements`, based on `0005_relative_claim_windows`,
extends `ck_requirements_type` to accept `installation_evidence`. It changes no
columns, defaults, indexes or existing rows. Apply it before writing installation
requirements. Downgrade restores the legacy six classifications only if existing
rows satisfy that constraint. If installation requirements exist, PostgreSQL rejects
the downgrade and rolls back the schema and revision change, preserving every row.
There is no automatic deletion or conversion. Future classifications require an
explicit domain member, constraint migration and domain/PostgreSQL coverage.

## Structured GBP rewards

`app.domain.rewards` provides frozen, slotted `FixedAmountReward`, `PercentageReward`,
`ProductRewardValue`, and `ProductSpecificReward` values. `RewardType` has exactly
`fixed_amount`, `percentage`, and `product_specific`. Definitions compose with benefits;
common benefit display text is never parsed or changed.

Call `calculate_reward(definition, purchase_price=..., product_id=...)` to return a GBP
`Decimal`. Fixed and product-specific values return the exact configured amount.
Percentages are percentage points (`10` means 10%) and use the exact qualifying price,
rounding only the result to pence with `ROUND_HALF_UP`, independently of ambient Decimal
precision, rounding, traps, and exponent limits. Missing price raises `MissingPurchasePrice`;
an unmapped canonical product UUID raises `MissingProductReward`. Wrong input types raise
`TypeError`; invalid values raise `ValueError`. Known zero purchase price remains valid.
Configured amounts must be finite, positive Decimals with at most two fractional places;
percentages must be in `(0, 100]` with at most four. No coercion or constructor rounding occurs.
Product mappings are non-empty, unique by `Product.id`, copied and sorted for immutable,
order-independent equality.

Migration `0007_reward_calculation` adds `benefit_rewards` (zero/one definition per benefit)
and `benefit_product_reward_values` (one exact amount per canonical product), with an index
on `product_id`. Unscaled PostgreSQL NUMERIC columns retain precision for database checks
rather than silently rounding invalid input. Checks enforce discriminator, field shape,
finite positive amounts, percentage bounds and fractional places even for direct SQL.
Benefit deletion cascades through rewards; product references restrict deletion. Writes
use caller-owned transactions; write a definition and its product values atomically.
Existing promotion graphs and benefits are unchanged, with no backfill. Apply the migration
before using the new tables. Empty downgrade and re-upgrade are supported; populated
downgrade explicitly refuses data loss while preserving tables, rows, checks and revision.

Runtime eligibility, REST/MCP and purchase-check results are unchanged. Publication validation
must later enforce compatible reward definitions and complete product coverage. Basket,
conditional, tier, cap and non-GBP rewards remain unsupported. Future support should add a
new explicit domain discriminator/value/calculator and additive typed migration, together
with publication validation and tests; it must preserve current semantics and common benefit
fields. See the [PR 15 specification](../.codex/tasks/pr-15-reward-calculation.md).

## Canonical purchase check

`app.application.purchase_check.check_purchase` composes exact canonical identity
matching, published candidate discovery, structured rules, claim timing, rewards,
requirements and verified provenance. Pass the existing `CheckPurchaseRequest` and
an explicit calendar `evaluation_date`; the operation does not use a clock, make
remote requests, interpret descriptions, or mutate data. Future REST/MCP adapters
must call this same operation.

For PostgreSQL wiring, use `purchase_check_snapshot` from the established promotion
repository module with a factory creating a **fresh dedicated Session**:

```python
with purchase_check_snapshot(session_factory) as (resolver, promotions):
    result = check_purchase(
        request,
        evaluation_date=evaluation_date,
        identity_resolver=resolver,
        promotion_repository=promotions,
    )
```

This boundary shares a read-only repeatable-read transaction across identity,
candidate and batched graph reads and always rolls it back before closing the
session. Reused sessions with pending data or existing transactions are rejected.
The injected application ports can also be implemented in memory; alternative
persistence wiring must provide the same coherent snapshot guarantee. All returned
values are immutable and fully materialised, usable after session close.

A resolved empty result has `no_matching_published_promotions`; unresolved identities
retain their field, match status and candidate UUIDs. Neither is an evaluated
negative eligibility finding. Each active/expired candidate variant has a separate
result in candidate order. Benefits and requirements sort by persisted UUID; sources
sort by `(role.value, source_id)`. Malformed published data raises
`PublishedPromotionDataError`, while infrastructure errors preserve the established
safe persistence exceptions. A missing claim window means potential eligibility,
with `claim_window_unspecified`. Percentage cashback without a known price remains
uncalculated with `purchase_price_required_for_reward`; it does not change eligibility.

Only persisted manufacturer/product/retailer/date applicability is checked. Price
restrictions, country, channel and condition have no persisted rule/input plumbing
yet. Requirements remain claim instructions, not satisfied evidence. Recorded terms
may not contain every manufacturer condition, and results do not guarantee claim
acceptance. Publication completeness beyond provenance, historical reconstruction
and public transports remain subsequent work. No schema, configuration or external
provider changes accompany this operation.

## Public eligibility HTTP API (v1)

`POST /api/v1/eligibility/check` accepts `application/json` (including a charset parameter).
It is a public, read-only query: no API key, customer session, or idempotency key is needed.
OpenAPI is available at `/openapi.json`; `/docs` describes both discriminated response models.

```sh
curl -X POST http://localhost:8000/api/v1/eligibility/check \
  -H 'Content-Type: application/json' \
  -d '{"brand":"Example Brand","model":"MODEL-123","retailer":"Example Retailer","purchase_date":"2026-10-01","purchase_price":"799.99"}'
```

Identity fields are required strings, limited to 255 characters before and after the existing
identity normalisation. Their original spelling is passed to the application service.
`purchase_date` is a strict `YYYY-MM-DD` calendar date, including future purchases.
Optional `purchase_price` is null or an exact non-negative GBP string with at most two pence
digits and **12 integer digits** (an API wire limit). JSON numbers, exponent notation, currency
symbols, additional keys and a client evaluation date are rejected. Missing/null price differs
from `"0"` or `"0.00"`. No currency field exists in v1.

A successful check returns `200` and either `outcome: "unresolved_identity"` with the unresolved
field, status (`not_found` or `ambiguous`), candidate UUIDs and explanation, or `outcome: "resolved"`
with canonical identity UUIDs, every matching published variant and the complete application
result. Resolved no-match has `promotions: []` and
`no_match_reason: "no_matching_published_promotions"`; neither uncertainty nor no-match implies
ineligibility. The server chooses the Europe/London evaluation date once per check.
Promotion classifications are `ELIGIBLE`, `POTENTIALLY_ELIGIBLE`, `NOT_ELIGIBLE`,
`CLAIM_NOT_YET_OPEN` and `EXPIRED`. Published lifecycle `expired` remains distinct from an
expired claim window. Requirements are claim instructions; eligibility is not a claim guarantee.

Result arrays preserve application order. Missing claim windows and unavailable money are null;
GBP amounts are exact decimal strings preserving scale. Dates, UUIDs and aware source timestamps
use ISO/RFC 3339 strings. Supporting sources may have null verification timestamps. Source and
claim URLs are passive data. Every call uses one fresh read-only repeatable-read PostgreSQL
snapshot, rolled back and closed on both success and failure. There are no writes or outbound
source/model-provider calls.

Errors use `application/problem+json` with `type`, `title`, `status`, `detail`, `code`, and a generated
`request_id`; the same ID is returned in `X-Request-ID`. Codes are `request_too_large` (413),
`unsupported_media_type` (415), `invalid_purchase_request` (422), `published_data_invalid` (500),
`internal_server_error` (500), and `eligibility_unavailable` (503). Errors never echo rejected input
or database details. The 429 `rate_limited` response is reserved for the production gateway.

The application enforces an **8192 byte body limit**, including streamed bodies without
Content-Length. No cross-origin browser allowance is configured; same-origin and standalone HTTP
clients work. Breaking contract changes require `/api/v2`; optional additive fields preserve
existing meanings. No database migration or MCP contract is introduced.

**Production exposure is blocked pending a separate ingress control change.** This repository has
no verified gateway rate limiter or request timeout policy. Configure and verify a production
edge rate limit (initial suggestion: 60 requests/minute/IP with a modest burst, 429 and Retry-After)
and bounded request timeouts before public exposure. Align configurable gateway errors with the
problem contract. An optional future browser UI must use exact-origin CORS without credentials.

## Candidate promotion authoring (schema version 1)

`app.application.promotion_authoring.parse_candidate_promotion(mapping)` parses an internal
JSON document with `schema_version: 1` and a `promotion` body. Serialize with
`candidate.model_dump(mode="json")`; UUIDs, ISO calendar dates, nulls and decimal strings
round-trip without floating point money. Unknown fields (including lifecycle status,
country/channel/condition/price rules and source URLs or verification timestamps) are rejected.
No authoring write endpoint or candidate persistence operation is introduced.

The body contains canonical `manufacturer_id`, `name`, `slug`, purchase date bounds,
a fixed (`type`, `start_date`, `end_date`) or relative (`type`, `start_offset_days`,
`end_offset_days`) `claim_window`, `variants` and `sources`. Incomplete drafts may use null
identity/display/date/window fields and empty arrays. Each variant must explicitly include
`retailer_id`: null means all retailers, never unknown scope. It contains `code`, optional
`name`, canonical `product_ids`, `benefits` and `requirements`. Benefits use the existing
cashback/extended_warranty/free_gift types. Cashback rewards discriminate on `type`:
`fixed_amount` with `amount_gbp: "50.00"`, `percentage` with `percentage: "10.5000"`, or
`product_specific` with `values: [{product_id: "<UUID>", amount_gbp: "40.00"}]`.
Requirements use existing requirement types and optional plain text descriptions.
Sources contain only curated `source_id` and primary/terms/claim/supporting `role`.

Relative claim offsets must remain representable as calendar dates for every purchase date
allowed by the promotion. Validation checks this with the existing relative-window domain
evaluator at the latest allowed purchase date. When `purchase_end_date` is open-ended, the
latest supported date is `date.max`, so only zero-offset relative windows are representable;
fixed claim windows and open-ended purchase ranges remain supported. An unrepresentable
window is rejected with `invalid_claim_window` at `/promotion/claim_window`. Runtime
evaluation maps legacy invalid relative windows to a published-data integrity error rather
than classifying them as ineligible.

Parsing bounds each document to 256 KiB and 12 levels, 50 variants, 200 product references,
20 benefits/30 requirements per variant, 30 sources, 255 character names/codes and 2,000
character descriptions. Money uses positive decimal strings with at most two decimal places;
percentages allow four places and must not exceed 100. Neither scientific notation nor
JSON floating point values are accepted. Descriptions are passive instructions, never rules.

`validate_candidate_promotion(candidate)` produces immutable issues with stable codes,
JSON Pointer paths, safe messages and error severity. Preflight always reports unresolved
references and cannot authorize publication. `CandidateInputError.report` contains parse
issues; `PromotionPublicationError.report` contains publication issues. Curators can inspect
these codes/paths and correct the existing persisted candidate before retrying activation.

Only the existing `review → active` operation validates the current PostgreSQL graph.
It requires purchase bounds, exactly one valid claim window, a manufacturer, named variants
with matching canonical products and benefits, complete cashback rewards, supported
requirements, and verified curated primary and claim sources. Product-specific rewards
cover exactly the variant products. Provenance uses actual stored URLs and timestamps;
source IDs in a candidate are not evidence. Invalid data blocks the whole promotion and
rolls back without changing timestamps or linked data. Active no-ops and retirement retain
historical behaviour; existing published rows are not repaired or backfilled.

Publication takes a parent promotion row lock before reading associations and retains the
conditional status update. Every future controlled graph editor must acquire that same lock
before editing and recheck lifecycle status; published graph changes must use coordinated
application transactions. Direct out-of-band SQL writes are operationally prohibited and
are not protected by this lock discipline. Database immutability/permissions, candidate
write idempotency, curator authentication/audit, source curation/content versioning and
unsupported eligibility dimensions require separate designs.
