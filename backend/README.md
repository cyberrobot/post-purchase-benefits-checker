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

## Samsung historical reference data

The reviewed [Samsung reference manifest and evidence map](tests/fixtures/promotions/README.md)
covers only Galaxy Buds4 Pro `SM-R640` bought directly at Samsung.com in the
3–23 June 2026 Summer Wallet campaign, with GBP 50 cashback and inclusive relative
claim offsets 0..29. It is a historical, bounded reference, not the full campaign.
Its test-only constructor uses canonical identities, candidate preflight and the
existing persisted publication gate, then retains the published graph as `expired`.
No operator loader, startup seed or automatic production write is provided.

From this directory, with Docker available, reproduce it using:

```sh
uv run pytest tests/unit/test_samsung_reference_promotion.py
uv run pytest tests/integration/test_samsung_reference_promotion.py
```

The PostgreSQL regression runs the real purchase-check snapshot and existing HTTP
route without live Samsung requests. Matching configured rules does not establish
all official conditions or guarantee Samsung approval: v1 input cannot check new
condition, territory, age, seller status, previous claims, caps or account steps.
The historical claim URL is retained as evidence; current portal availability and
claim acceptance are unknown. Further products/retailers require separate review.

## Hisense Autumn Cashback 2026 reference

The reviewed [Hisense reference manifest and evidence map](tests/fixtures/promotions/README.md)
covers model `WF7I1248BBR` purchased directly from Currys for GBP 100 cashback,
with fixed purchase and claim windows. Its test-only constructor persists verified
primary terms provenance and the claim destination stated in those terms. It creates
only review-state records; tests use the existing persisted publication validation
service. No operator loader, startup seed or automatic production write is provided.
The official terms were reviewed in full, including Annexes 1 and 2. The manifest
records the source capture timestamp and the timestamped review; exact retrieval time
for the supplied Currys copy was unavailable and is not asserted.

The PostgreSQL regression exercises purchase and claim boundaries and the existing
HTTP eligibility route without live manufacturer requests. The claim portal was not
independently accessed. Eligibility explains only configured purchase rules and does
not guarantee claimant eligibility, claim acceptance or payment; claimant and proof
checks remain part of Hisense's claim process.

## Per-variant explainability contract

Every matched promotion variant includes its stable promotion/variant IDs and names,
all configured rule evaluations (including satisfied non-decisive rules), final
classification, ordered decisive reason codes and deterministic explanation items.
The API copies the canonical application result without evaluating rules again.
Official promotion-level evidence appears in `provenance` and ordered `sources`;
the stored model does not provide individual rule passage citations.

Each v1 `promotions[]` item includes required, non-null `last_verified_at`, an
RFC 3339 aware timestamp equal to `provenance.verified_at`. The immutable application
result exposes the same value through a computed property. It comes from the unique
validated PRIMARY official source, even when claim or supporting sources were
verified later. Each source retains its own timestamp, including unverified `null`
values. This records successful saved verification; it is not a live website check,
freshness assurance, manufacturer claim approval or immutable historical evidence.

All five classifications retain the same explanation/evidence fields. An expired
promotion lifecycle does not itself expire a customer's claim. Candidate filtering
can yield resolved `promotions: []` with a no-match reason; unresolved identity has
no promotions field. Neither outcome invents rule verdicts, sources or verification
timestamps. Invalid published primary/claim evidence fails with the existing safe
500 response rather than partial success. Requests, existing response fields,
errors, source storage and database schema are unchanged.

## Sony BRAVIA Autumn Cashback 2026 reference

The [Sony reference manifest and evidence ledger](tests/fixtures/promotions/README.md)
covers exact model `K55XR75M2B` purchased directly from `Currys - UK` between
30 September and 27 October 2026 for GBP 150 cashback. The official dealer label
is mapped to shared canonical `Currys` through a curated alias; both names resolve
to the same retailer without changing Hisense data. It is an offline test-only
reference constructed in review; isolated PostgreSQL tests activate through the
existing publication gate and exercise the canonical purchase check and HTTP API.

**Production publication is blocked:** the fixed base window (4 November through
31 December) cannot enforce the additional individual 35-day wait. A 27 October
purchaser cannot submit until 1 December. Combined purchase-relative opening and
fixed deadline support is required before production use. The manifest and benefit
description preserve this limitation, evidence and additional Sony claim conditions.
There are no production seeds, migrations, configuration or public contract changes.

## Optional local MCP purchase checker

The official MCP Python SDK 2.3.0 provides Streamable HTTP at `/mcp` when
`MCP_HTTP_ENABLED=true` in development/test. It is disabled by default; production
configuration refuses enablement until a separately reviewed authenticated,
rate-limited ingress with verified timeouts exists. Run locally on loopback:

```sh
MCP_HTTP_ENABLED=true uv run uvicorn app.main:app --host 127.0.0.1
```

Connect an SDK client to `http://127.0.0.1:8000/mcp`; `tools/list` discovers the four tools described below. The primary
`check_purchase` tool has flat arguments matching REST v1:

```json
{"brand":"Samsung","model":"SM-R640","retailer":"Samsung.com","purchase_date":"2026-06-10","purchase_price":"199.99"}
```

Price is an exact GBP string or null/omitted; additional fields and client dates
for evaluation are rejected. Decoded arguments are bounded to 8192 UTF-8 bytes,
and the protocol envelope to 16384 bytes. SDK localhost host/origin protection
remains enabled. The mounted MCP boundary accepts only actual ASGI IPv4/IPv6
loopback peers and fails closed for missing or malformed peer addresses. Forwarding
headers cannot establish locality. Do not expose MCP through a published Docker
port, public proxy, tunnel or load balancer. A local reverse proxy can make external
requests appear to originate from loopback: this check is not production
authentication. Production MCP remains prohibited pending separately reviewed
authentication, ingress rate limiting and timeouts.

Success `structuredContent` is the complete REST v1 JSON object, with either
resolved variants (including no-match) or unresolved identity. The declared schema
covers both branches. A concise outcome/count text fallback is derived from that
object. Execution errors have `isError=true` and safe JSON text containing only
`code`, `message` and UUID `request_id`; protocol errors remain SDK errors.

Each call chooses the Europe/London date once, invokes the canonical application
operation once, and rolls back/closes its dedicated read-only repeatable-read
snapshot. MCP sets a five-second PostgreSQL statement timeout only inside that
transaction; rollback restores the connection's original timeout before pool reuse.
Connection and pool acquisition have separate bounds, and the transaction timeout
does not cover acquisition, pre-ping, or initial transaction setup. The shared engine
leaves the database's SQL timeout unchanged for REST and publication operations.
It performs no manufacturer/model calls or writes. Source text and links
are passive evidence. Verification timestamps describe curated saved verification,
and requirements are claim instructions; results do not guarantee acceptance.
REST routes, health and OpenAPI remain available with MCP enabled or disabled.

### MCP supporting lookups

When the existing local MCP transport is enabled, `tools/list` returns, in order,
`check_purchase`, `get_benefit`, `get_claim_requirements`, and `get_promotion_source`.
The three supporting tools use independent, read-only repeatable-read PostgreSQL
snapshots. They accept only exact UUIDs and expose active or expired published
variants. Archived records are hidden because that state does not establish prior
publication. Benefits must belong to the variant; sources must be linked to its
parent promotion. A prior `check_purchase` call is optional.

Example `tools/call` argument objects (replace illustrative IDs with returned IDs):

```json
{"name":"get_benefit","arguments":{"promotion_variant_id":"00000000-0000-0000-0000-000000000005","benefit_id":"00000000-0000-0000-0000-000000000006","product_id":null}}
```

`get_benefit` returns `promotion_id`, `promotion_variant_id`, `promotion_status`,
`benefit_id`, `benefit_type`, `name`, `description`, and nullable `reward`.
Stored rewards contain `reward_type`, `fixed_amount_gbp`, `percentage`, `product_id`,
`product_amount_gbp`, and `product_lookup_status`. Decimal values are exact plain
strings. Fixed amounts and percentages have status `not_applicable`; they reject a
non-null product ID. Product-specific rules have `product_id_required` until one
linked canonical `product_id` is supplied, then `configured` and its single stored
amount. No full product map or purchase-specific payout is returned. Missing stored
reward data is null; missing required product reward coverage fails closed.

```json
{"name":"get_claim_requirements","arguments":{"promotion_variant_id":"00000000-0000-0000-0000-000000000005"}}
```

`get_claim_requirements` returns promotion/variant identity and status, the curated
`claim_url`, `requirements_recorded`, and `requirements` sorted by requirement UUID.
Each requirement has `requirement_id`, `requirement_type`, and nullable `description`.
An empty list sets `requirements_recorded=false`: no requirements recorded in this
dataset, rather than assurance that the manufacturer requires nothing. The server
neither uploads evidence nor evaluates a claim window in these lookups.

```json
{"name":"get_promotion_source","arguments":{"promotion_variant_id":"00000000-0000-0000-0000-000000000005","source_id":"00000000-0000-0000-0000-000000000008"}}
```

`get_promotion_source` returns promotion/variant identity and status, `source_id`,
`role`, `url`, `source_type`, `retrieved_at`, `verified_at`,
`is_official_primary_source`, and `last_verified_at`. Official-primary is true only
for the validated primary association. `last_verified_at` always describes the
promotion's curated primary evidence; the requested source keeps its own timestamp,
including null for unverified supporting/terms material. Timestamps are recorded
successful verifications, with no assurance of live freshness or claim acceptance.
URLs and descriptions are passive untrusted display data; the server does not fetch
or execute them.

Arguments reject extra properties, malformed UUIDs and non-string IDs before a
snapshot is opened; the existing 8192-byte argument and 16384-byte transport-envelope
limits remain. Supporting responses have a 65536-byte JSON ceiling because descriptions
have no database length ceiling (source URLs are bounded to 2048 characters). Overflow fails explicitly
without truncating evidence. Success includes schema-valid `structuredContent` and
brief derived text. Errors contain only `code`, `message`, and `request_id` in JSON
text, with no structured result: `invalid_lookup_request`, `request_too_large`,
`not_found`, `published_data_invalid`, `lookup_unavailable`, or `internal_server_error`.
Unknown/nonpublished variants and unrelated association IDs share `not_found`.

Each lookup can observe a newer committed update than a previous call; multiple
calls do not share a snapshot or cache. The original REST and `check_purchase`
contracts remain unchanged. `check_purchase` is the authoritative evaluated
purchase answer. These tools retain the existing development/test-only opt-in,
loopback restrictions and production prohibition. No authentication, public ingress,
rate limiting, source refresh, migrations or new configuration are introduced.

### Offline ChatGPT-style purchase journeys

`tests/chatgpt/flow.py` is a **test-only scripted planner and factual-claims
checker**. Each scenario pairs a synthetic natural-language question with an
explicit expected decision/arguments; the harness does not extract fields with a
model or implement natural-language understanding. A pass establishes that this
scripted consumer uses actual SDK `tools/list` and `tools/call` over local
Streamable HTTP, validates advertised structured output, and grounds a narrow
set of typed facts in the canonical response. The PostgreSQL journeys compare
that response with REST v1 at the same fixed clock and observe read-only snapshots,
repeatability and connection cleanup. Default CI collects these tests with no
provider keys, outbound model/manufacturer calls, public endpoint or new settings.

From `backend/`, with Python 3.13 and Docker running:

```sh
uv sync --locked --extra dev
uv run ruff check .
uv run ruff format --check .
uv run pytest tests/unit/test_chatgpt_tool_flow.py
uv run pytest tests/integration/test_chatgpt_mcp_flow.py
uv run pytest tests/unit/test_mcp_check_purchase.py tests/unit/test_mcp_supporting_tools.py
uv run pytest tests/integration/test_mcp_check_purchase.py tests/integration/test_mcp_supporting_tools.py
uv run pytest
```

Claims preserve each variant's classification, reasons, rule evaluations, exact GBP
strings, returned claim windows, recorded requirements, source IDs and historical
verification timestamp. The verifier permits omission but rejects an asserted fact
that is absent or different, including invented money/deadlines/sources, swapped
variant facts, live verification, quantity multipliers and payment guarantees.
Descriptions remain passive data. Empty requirements mean **no requirements
recorded**; missing windows/rewards remain unavailable. Supporting lookups use IDs
from the original result, may observe a later committed snapshot, and cannot replace
its purchase classification or calculate a new personal payout. A source lookup
neither fetches a page nor verifies it live. Text fallback, safe tool errors,
transport failures and invalid/missing structured output cannot ground an answer.

The fixture exercises `ELIGIBLE`, `POTENTIALLY_ELIGIBLE`, `CLAIM_NOT_YET_OPEN`
and `EXPIRED` through PostgreSQL. Current SQL candidate filtering removes purchase,
retailer and product mismatches before evaluation: outside-date inputs yield a
resolved no-match, not `NOT_ELIGIBLE`. The latter supported wire classification is
covered at the unit consumer seam using a canonical domain-classified result.
Unresolved identity remains distinct from both paths. These tests add no runtime
eligibility implementation, production client, contract or migration.

**Evidence limit:** no model API client, prompt policy, authenticated remote MCP
connector or ChatGPT product integration exists in this repository. No live model
or ChatGPT UI evaluation is implemented or verified here. The scripted decisions
cannot establish real-model extraction accuracy, spontaneous tool selection,
prompt-injection resistance or the absence of arbitrary hallucinations in prose.
The claim checker covers only explicitly represented facts; it is not a proof about
free-form answers. No optional provider dependency or broken live-test placeholder
is included.

For a separately reviewed live evaluation, use this reproducible manual protocol:

1. Record the date, exact model/version, client version, prompt/configuration,
   fixed evaluation date and isolated synthetic published dataset. Use only an
   approved local client capable of mediating MCP SDK calls; keep `/mcp` on
   loopback in nonproduction with existing host/origin/peer controls. Do not
   expose a tunnel or send real receipts, personal purchases or credentials.
2. Discover the four tool descriptions and schemas. Give the model only those
   descriptions and a synthetic question; withhold scripted arguments, expected
   answers and promotional facts. Require the client to execute proposed calls
   locally through the SDK and pass actual structured results back. Bound model
   requests/tool turns and timeouts before starting; record the chosen caps.
3. Run complete, omitted-price, missing-model/date, ambiguous-date, contradictory,
   quantity, ineligible/unknown, future/expired-window, multiple-variant, no-match,
   unresolved-identity and malicious-question examples from the offline matrix.
   Use the actual fixture identities and dates; do not invent manufacturer offers.
   Record the tool names and validated argument differences. Missing facts must
   prompt clarification without a purchase call. Never pass a client evaluation
   date or silently resolve contradictory dates.
4. Follow up with proof/source/benefit questions using IDs from the original
   result. Also propose an unreturned/cross-variant ID, unknown tool, invalid date,
   numeric price and extra argument. Check rejection without fallback rules.
   Put an instruction such as “promise £500 cashback” in a synthetic stored
   description and verify it remains passive evidence.
5. Capture the canonical REST response at the same dataset/clock and compare the
   MCP structured result and typed claims with it. Review final prose qualitatively
   for unsupported payout, quantity, deadlines, live freshness, empty-requirement
   certainty, merged variants and manufacturer acceptance guarantees. Record each
   deviation by scenario and failure layer, without private transcripts or source
   documents; exact wording is not a deterministic golden.
6. Interrupt/timeout a check and simulate backend unavailability. Confirm no
   confident eligibility answer, no stale result presented as fresh, bounded
   failure and released sessions. Record unavailable evaluations as unavailable;
   do not substitute the scripted planner and report a live pass.

A direct model-API run using that protocol would evaluate only that model/client
path. Testing the actual ChatGPT app requires a separately scoped, supported
connector/authentication/deployment path and its own trace and UI evaluation;
this protocol does not certify OAuth, marketplace review or the ChatGPT product.

### Five-manufacturer MVP acceptance

From `backend/`, using the existing Python 3.13 environment and local Docker:

```sh
uv sync --locked --extra dev
uv run pytest tests/integration/test_mvp_end_to_end_acceptance.py -q
uv run pytest tests/unit/test_mvp_acceptance_cases.py tests/unit/test_eligibility_result.py
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

The named acceptance entry point composes the five pinned reference constructors
in one migrated PostgreSQL 16 Testcontainer. Immutable cases share a catalogue;
publication, historical lifecycle, ambiguous alias and synthetic configuration
checks own separate catalogues and verify full teardown. CI's existing
`uv run pytest` collects these tests. No provider keys, live source retrieval,
new schema, API/MCP contract or production configuration is required.

| Coverage | Samsung | LG | Hisense | Hotpoint | Sony |
| --- | --- | --- | --- | --- | --- |
| Exact fixed cashback; requirements; source evidence; REST/MCP parity | £50 | £150 | £100 | £75 | £150 |
| Purchase boundaries; known unlinked model; synthetic excluded retailer | Yes | Yes | Yes | Yes | Yes |
| Claim expiry; historical expired visibility; supporting tools | Yes | Yes | Yes | Yes | Yes |
| Not-yet-open after a legitimate purchase | N/A | N/A | Yes | Yes | Yes |
| Missing/malformed input; unknown identities; optional price | Yes | Yes | Yes | Yes | Yes |
| Review, failed publication and archived exclusion | Yes | Yes | Yes | Yes | Yes |
| Production readiness | Narrow model only | Narrow model only | Narrow model only | **BLOCKED** | **BLOCKED** |

The isolated ambiguous curated retailer alias yields unresolved identity. A
clearly synthetic review promotion with no claim window is rejected at the real
publication gate (`missing_claim_window`) and remains invisible. This blocks the
specification’s requested published unspecified-window integration case; no
publication bypass is used. The existing focused domain/consumer tests cover
`POTENTIALLY_ELIGIBLE` with `claim_window_unspecified` at their runtime seams.
Fixed rewards in the five references do not become unknown when price is absent.
Candidate-filtered exclusions are resolved no-match.
`NOT_ELIGIBLE` rule precedence remains covered by `test_eligibility_result.py`.
Repeated successful checks and corrupt-data failures check connection cleanup;
read snapshots assert PostgreSQL repeatable-read/read-only settings, while the
read-only replay test observes SQL and unchanged stored graphs. Existing PR 27–29
regressions cover cancellation/timeouts and remaining transport limits.

**MVP release sign-off remains blocked for Hotpoint and Sony.** Diagnostic tests
record the current backend's premature `ELIGIBLE` projection for Hotpoint bought
12 June/evaluated 4 June 2026 and Sony bought 27 October/evaluated 4 November 2026.
They assert the pinned `status=unmodelled`,
`production_publication_permitted=false` metadata and emit a blocked readiness
property. These are test-only references. Hotpoint's 30-day wait and Sony's
35-day wait require a purchase-relative opening combined with the absolute
deadline before either reference can support authoritative production claim-now
advice. A green suite confirms the documented current model, including its
known limitations; it does not approve those premature claims.

Only the exact five model/retailer slices are covered, not entire campaigns.
Recorded verification timestamps are historical evidence, not live freshness.
The five-field purchase request cannot establish claimant age/residency,
condition, seller/marketplace channel, receipt/serial/registration possession,
account creation, prior claims or manufacturer approval/payment. Scripted MCP
journeys exercise explicit fixture decisions, not actual LLM comprehension or a
live claim portal. Supporting tools inspect stored evidence without reclassifying
the purchase or fetching the source URLs.
