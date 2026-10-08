# PR 17 — `check_purchase` Eligibility Service

## Repository state

**Expected branch:**  
`pr17-check-purchase-eligibility-service`

**Base branch:**  
`main`

**Dependencies:**

- PR 3–7 — core promotion graph, lifecycle/history, benefit types, provenance, canonical identity normalisation.
- PR 8 — `CheckPurchaseRequest` input contract.
- PR 9 — `match_promotion_candidates`, `PromotionCandidateSet`, and published promotion candidate query.
- PR 10–11 — pure eligibility rules, classification, and structured reason codes.
- PR 12–13 — fixed and relative/delayed claim windows.
- PR 14 — typed claim requirements.
- PR 15 — typed cashback rewards and persisted reward definitions.
- Existing SQLAlchemy/PostgreSQL, Alembic, pytest/Testcontainers, Ruff, and backend application/repository boundaries.

### Read first

- `AGENTS.md`
- `.codex/tasks/TEMPLATE.md`
- `.codex/tasks/pr-8-purchase-input-contract.md`
- `.codex/tasks/pr-9-promotion-candidate-matching.md`
- `.codex/tasks/pr-10-core-eligibility-rules.md`
- `.codex/tasks/pr-11-eligibility-result-classification.md`
- `.codex/tasks/pr-12-fixed-claim-windows.md`
- `.codex/tasks/pr-13-relative-delayed-claim-windows.md`
- `.codex/tasks/pr-14-promotion-requirements.md`
- `.codex/tasks/pr-15-reward-calculation.md`
- `backend/README.md`
- Existing implementation and tests for the symbols below.
- Any more narrowly scoped `AGENTS.md` added before implementation.

### Primary change area

**Application service / eligibility orchestration** with a narrow, read-only promotion-details projection at the established repository boundary. The service composes existing domain components rather than implementing another eligibility engine.

### Canonical implementation examples

- `backend/app/application/purchase_check.py::CheckPurchaseRequest` — validated purchase input and natural home of the new use case.
- `backend/app/application/promotion_candidate_matching.py::match_promotion_candidates` — canonical identity and candidate flow.
- `backend/app/application/identity_matching.py::IdentityResolver` — exact brand, retailer and model/SKU matching.
- `backend/app/domain/eligibility_rules.py::evaluate_eligibility_rules` — pure rule engine.
- `backend/app/domain/eligibility_result.py::classify_eligibility` — authoritative classification and precedence.
- `backend/app/domain/claim_windows.py` — fixed/relative date arithmetic.
- `backend/app/domain/requirements.py` — requirements as typed claim instructions.
- `backend/app/domain/benefits.py` and `backend/app/domain/rewards.py::calculate_reward` — typed benefits and GBP rewards.
- `backend/app/domain/promotion_provenance.py::validate_publication_provenance` — curated primary/claim source validation.
- `backend/app/db/repositories/promotions.py::SqlAlchemyPromotionRepository` — existing candidate and source reads.
- `backend/tests/integration/test_promotion_candidate_matching.py` — real PostgreSQL candidate matching precedent.
- `backend/tests/unit/test_eligibility_result.py`, `test_claim_windows.py`, `test_rewards.py` — regression precedents.

### Relevant symbols

```text
CheckPurchaseRequest
IdentityResolver, IdentityPersistenceError
PromotionCandidate, PromotionCandidateSet, UnresolvedPurchaseIdentity
match_promotion_candidates, PromotionCandidateRepository
SqlAlchemyPromotionRepository, PromotionPersistenceError
PurchaseEligibilityFacts, PromotionEligibilityRules
ManufacturerRule, ProductRule, RetailerRule, PurchaseDateRule
evaluate_eligibility_rules, RuleEvaluation, RuleStatus
EligibilityClassification, EligibilityResult, EligibilityReason
ClaimWindowStatus, classify_eligibility
FixedClaimWindow, RelativeClaimWindow, ClaimWindowEvaluation
evaluate_fixed_claim_window, evaluate_relative_claim_window
BenefitType, Benefit, RewardDefinition, calculate_reward
MissingPurchasePrice, MissingProductReward
Requirement, RequirementType
PromotionSourceRecord, PublishedProvenance, validate_publication_provenance
PromotionStatus, HISTORICAL_PUBLISHED_STATUSES
Promotion, PromotionVariant, PromotionVariantProduct
Benefit, BenefitReward, BenefitProductRewardValue (ORM)
Requirement, PromotionSource, Source (ORM)
```

### Expected change surface

```text
backend/app/application/purchase_check.py
backend/app/application/                     # optional focused DTO/port module
backend/app/db/repositories/promotions.py   # or narrowly related read adapter
backend/app/domain/eligibility_result.py    # minimal unconfigured-window extension only
backend/tests/unit/test_purchase_check.py
backend/tests/unit/test_eligibility_result.py
backend/tests/integration/test_check_purchase.py
backend/README.md
```

The change surface is guidance, not an absolute restriction. Explain necessary departures. **No schema migration is expected**: the schema already represents promotion/variant applicability, fixed/relative windows, benefits/rewards, requirements and source links.

### Excluded areas

Do not add:

- REST endpoints, public Pydantic response schemas, MCP tools, or frontend changes. A later transport PR must call this same service.
- New purchase-input fields without a separate input-contract change.
- User accounts, saved purchases, claim submission/tracking, evidence uploads/verification, OCR, manufacturer registration, or claim fulfilment.
- Live source fetching, AI/LLM evaluation, scraping, source ingestion, or publication workflows.
- New generic eligibility DSL, arbitrary JSON rules, speculative rule persistence, or unrequested migrations.
- Basket or conditional rewards, benefit-combining, offer ranking, or choosing a single “best” promotion.
- Inferred purchase channel, country, or product condition from retailer strings, website domains, or descriptions.
- Historical snapshots/version reconstruction that the current database does not support.
- Infrastructure dependencies, workers, queues, caches, or configuration changes.

### Unknowns Codex must verify

Verify the current implementation before editing:

1. `CheckPurchaseRequest` still contains only `brand`, `model`, `retailer`, `purchase_date`, and optional `purchase_price`; it does not contain channel, condition, or country.
2. Candidate search filters canonical identities, published `active`/`expired` lifecycle states and inclusive purchase-date bounds. `archived` is **not** proof of previous publication.
3. `PromotionCandidate` currently contains scalar IDs/status/retailer/date bounds, **not** full benefit/reward/requirement/window/source detail.
4. `PromotionEligibilityRules` is presently a pure domain model. There is no persisted typed price-threshold, channel, condition or country rule definition to load.
5. The existing classifier accepts only `ClaimWindowStatus.OPEN`, `.NOT_YET_OPEN`, or `.EXPIRED`; a missing configured window is not represented.
6. Fixed/relative claim pairs are promotion-level, nullable, complete-or-absent and mutually exclusive.
7. A `BenefitReward` is optional, rewards are monetary cashback data, and non-cash benefit types should not be assigned a GBP amount.
8. `Requirement` belongs to a promotion variant; curated sources belong to the parent promotion.
9. Publication provenance requires a unique verified primary and claim source.
10. No REST/MCP purchase-check adapter already exists on this branch.
11. Current Alembic head, session ownership, isolation behaviour, real-PostgreSQL fixtures and documented verification commands are unchanged.

If the branch already has equivalent functionality, reuse it instead of duplicating it.

---

## Objective

Create **one canonical, transport-independent `check_purchase` application operation** that takes a validated purchase, an explicitly supplied evaluation date, and injected read dependencies.

For each published candidate promotion variant it must:

1. Resolve exact canonical identities and discover candidates using PR 9.
2. Load the complete persisted, structured promotion/variant graph through the established SQLAlchemy repository boundary.
3. Derive canonical facts and only the eligibility rules actually represented in structured promotion data.
4. Run PR 10 rules and PR 11 classification with its existing precedence.
5. Evaluate fixed or relative claim timing using PR 12/13, including opening and deadline dates.
6. Calculate known cashback rewards with PR 15 and preserve non-monetary benefit types.
7. Include PR 14 claim requirements and PR 6 validated primary/claim source provenance.
8. Return one immutable, explainable result per variant, with explicit uncertainty/error handling and no writes, remote calls or LLM dependency.

The result must let a caller explain **which published benefits could apply, why, what the known cashback amount is, when claiming opens/closes, what evidence/actions are required, and the verified source/claim links**.

A successful check is *not* a guarantee that the manufacturer will accept a claim. It reflects the structured published terms presently supported by this codebase.

---

## Architecture and invariants

```text
future REST / MCP adapters
          ↓
CheckPurchaseRequest + explicit evaluation_date
          ↓
check_purchase application service
    ├── identity resolver + PR 9 candidate search
    ├── typed promotion-details read projection
    ├── PR 10 rule evaluation
    ├── PR 12/13 claim-window evaluation
    ├── PR 11 eligibility classifier
    ├── PR 15 cashback calculation
    ├── PR 14 requirement definitions
    └── PR 6 source/provenance validation
          ↓
immutable typed application results and explanations
```

Required invariants:

1. Runtime decisions depend on validated request, explicit evaluation date and structured **published** promotion data only. No LLM, live website or natural-language rule interpretation.
2. Domain rule functions are independent of FastAPI, MCP, SQLAlchemy and sessions. Transport adapters, when later introduced, reuse the service.
3. Published candidates are exactly `active` and `expired` under the current schema. Discovered/extracted/review/archived records must never be exposed as published results.
4. Promotion lifecycle `expired` is **not** a synonym for an individual's `ClaimWindowStatus.EXPIRED`.
5. PR 9 candidate matching remains intentionally broad. No candidates is not a definitive evaluated `NOT_ELIGIBLE` finding.
6. Ambiguous/not-found identity, an empty candidate set, unknown purchase facts and infrastructure failure have different representations.
7. One matched promotion variant produces **one** result; do not pick, merge or rank variants, even when several belong to one promotion.
8. Only canonical manufacturer, retailer and product UUIDs drive applicability. Raw model/SKU text and product/retailer names are not eligibility comparison values.
9. Rules absent from structured data do not magically become restrictions; genuinely configured unknown facts do not magically pass. Do not derive hidden constraints from descriptions.
10. PR 11 classification precedence remains canonical for all known rule and claim-window states.
11. Absent claim-window configuration must never be assumed `OPEN` or silently mapped to a fabricated date range.
12. Benefit reward value is separate from purchase eligibility. Missing percentage calculation inputs must not become zero amounts or automatic failed eligibility.
13. Claim requirements are passive definitions/instructions, not proof that a user already supplied evidence.
14. Official and claim URLs come only from curated source roles and retain retrieval/verification metadata.
15. The application result contains no ORM objects and works after the database session closes.
16. For identical inputs, evaluation date and unchanged persisted snapshot, the result is deterministic. One check reads a coherent PostgreSQL snapshot and performs no mutations.

---

## API and contract changes

**No new public REST, MCP or OpenAPI contract in PR 17.** Define internal application interfaces only.

### Canonical application operation

Expose an operation conceptually equivalent to:

```python
check_purchase(
    request: CheckPurchaseRequest,
    *,
    evaluation_date: date,
    identity_resolver: IdentityResolver,
    promotion_repository: CheckPurchaseRepository,
) -> CheckPurchaseResult | UnresolvedPurchaseIdentity
```

Exact naming and injected wiring can follow established conventions, but there must be **one** authoritative orchestration path. Preserve `CheckPurchaseRequest` without creating a duplicate type or adding new caller fields here.

- Validate that `request` is a `CheckPurchaseRequest`.
- Validate `evaluation_date` as a plain calendar `date`, explicitly rejecting `datetime`, strings and `None`.
- Do not call `date.today()` or read the process/system clock inside the core operation.
- Reuse `match_promotion_candidates(...)` once, preserving identity resolution order and existing candidate filtering.
- Inject repositories/resolvers rather than constructing engine/session infrastructure inside domain code.
- Expected identity uncertainty is a result; corrupted published data and persistence failures are exceptions, not eligibility classifications.
- Read-only operation: identical repeated calls create no state changes and need no write idempotency key.

### Result contract

A successfully **resolved** check returns immutable application-owned values equivalent to:

```text
CheckPurchaseResult
  evaluation_date: date
  resolved_identity: ResolvedPurchaseIdentity
  promotions: tuple[CheckPurchasePromotionResult, ...]
  no_match_reason: stable code | None
```

An empty `promotions` tuple with `no_matching_published_promotions` means identities resolved but no published promotion matched the broad candidate filters. An unresolved brand, retailer or model must instead return the established `UnresolvedPurchaseIdentity` (or a wrapper that faithfully preserves `field`, `MatchStatus`, and candidate UUIDs). Do **not** classify either outcome as `NOT_ELIGIBLE`.

Each promotion-variant result must include, at minimum:

```text
promotion_id: UUID
promotion_variant_id: UUID
promotion_name: str
variant_name / label: str | None
promotion_status: PromotionStatus
eligibility: EligibilityResult
claim_window: ClaimWindowEvaluation | None
benefits: tuple[CheckPurchaseBenefit, ...]
requirements: tuple[Requirement, ...]
provenance: PublishedProvenance
sources: tuple[PromotionSourceRecord, ...]
explanation: stable deterministic display text or ordered explanation items
```

`EligibilityResult` must preserve all PR 10 `rule_evaluations`, every decisive PR 11 `EligibilityReason`/code and the claim-window state. Claim opening/deadline dates are provided by the existing `ClaimWindowEvaluation` contract and **not** recreated in a second calendar arithmetic implementation.

Per-benefit values should include typed `Benefit` metadata and nullable `cashback_reward_gbp: Decimal`, with a stable `reward_unavailable_reason` when a cashback amount cannot be calculated. For warranty/free gift, no monetary reward is asserted. No `float`, raw ORM object, opaque JSON rule blob or unvalidated arbitrary string discriminator should cross this boundary.

Deterministic ordering is part of the contract: preserve PR 9 candidate order; sort benefits/requirements by stable persisted IDs and source associations by a documented stable key. Keep distinct variants, even if their metadata looks identical.

### Detail-loading read port

Introduce a small application-owned read capability equivalent to:

```python
load_check_purchase_candidates(
    candidate_variant_ids: tuple[UUID, ...],
) -> tuple[PublishedPromotionDetails, ...]
```

Its DTOs must be immutable, materialised, detached from the SQLAlchemy session, and represent exactly the requested candidates, including:

- parent promotion identity/name/status/manufacturer and purchase-date bounds;
- variant ID/name/retailer and associated product IDs;
- fixed or relative claim-window values (or explicitly neither);
- all variant benefits with reward discriminator and typed values, including product-specific mapping;
- all variant requirements (type and description);
- parent promotion source associations, roles, URLs, source type and retrieval/verification timestamps.

Use application-owned typed values; SQLAlchemy and SQL types stop at the adapter boundary. Avoid multiple overlapping repository abstractions if extending the existing promotion read adapter is sufficient.

### Minimal absent-claim-window extension

The PR 11 classifier currently knows only `ClaimWindowStatus.OPEN`, `.NOT_YET_OPEN`, `.EXPIRED`. **None** of those means “claim window not configured.”

Make the smallest compatible domain change to represent an unconfigured claim window, conceptually `claim_window_status: ClaimWindowStatus | None` on `classify_eligibility(...)` and `EligibilityResult`. Add one stable classification-specific reason such as `CLAIM_WINDOW_UNSPECIFIED` / `claim_window_unspecified`.

- If no known eligibility rule fails and no unknown rule remains, an absent window results in `POTENTIALLY_ELIGIBLE`, *not* `ELIGIBLE`.
- If a known rule fails, retain `NOT_ELIGIBLE` and its decisive rule reasons.
- If a rule is unknown, retain `POTENTIALLY_ELIGIBLE`, reporting rule uncertainty and the missing window when both apply.
- Preserve existing behaviour for all three non-None claim states and all five existing classification values.
- Do not introduce a sixth eligibility classification or treat malformed partial claim-window data as “unconfigured.”

---

## Domain and application behaviour

### 1. Candidate discovery and identity uncertainty

Use `match_promotion_candidates(request, identity_resolver, promotion_repository)` as the only candidate matching implementation.

Resolution is brand → retailer → model/SKU → candidate query. If any required identity is ambiguous or not found, stop, preserving the existing field/status/candidate-ID outcome and a deterministic explanatory mapping. Do not try to infer manufacturer from product, pick the first ambiguous SKU, or continue loading candidate details.

If all identities resolve but the published candidate set is empty, return a normal empty check result with the distinct `no_matching_published_promotions` reason. Candidate matching already removes purchases outside known inclusive purchase-date ranges; **do not fabricate `NOT_ELIGIBLE` results for rows that were never candidates**.

### 2. Hydrate and validate full candidate data

Fetch details only for the exact candidate variant IDs. Verify that the result is one-to-one with those IDs and contains no missing, duplicate, unpublished, wrong-parent, or cross-variant records. Such mismatches are data/consistency failures, not normal negative matches.

Construct immutable typed `Benefit`, `Requirement`, reward and source values using established domain constructors. Reject incompatible benefit/reward types, unsupported stored discriminators, invalid source roles, malformed monetary definitions and incomplete/conflicting persisted windows. A matched published variant with no benefits is invalid published content for this use case; fail instead of claiming an actionable eligible offer.

Use `validate_publication_provenance(source_records)` to derive `PublishedProvenance`. A unique verified primary and claim source is mandatory. Missing, ambiguous or unverified required sources are data errors, **not** null/guessed claim URLs. Additional source links may be returned with their exact role and timestamps; do not automatically call unverified supporting material “official.” No HTTP fetching or parsing is performed.

### 3. Construct purchase facts and configured rules

Construct `PurchaseEligibilityFacts` from the resolved IDs, request date and optional exact `Decimal` price:

```python
PurchaseEligibilityFacts(
    manufacturer_id=identity.manufacturer_id,
    product_id=identity.product_id,
    retailer_id=identity.retailer_id,
    purchase_date=request.purchase_date,
    purchase_price=request.purchase_price,
    purchase_channel=None,
    condition=None,
    country_code=None,
)
```

The last three fields are currently absent from PR 8. Do not infer them from a retailer, website, or UK-focused product context.

Build the candidate's `PromotionEligibilityRules` from persisted applicability that **actually exists**:

| Rule dimension | Structured source |
| --- | --- |
| Manufacturer | `Promotion.manufacturer_id` |
| Product | Linked `PromotionVariantProduct.product_id` values for this exact variant |
| Retailer | `PromotionVariant.retailer_id` when non-null; null imposes no retailer restriction |
| Purchase date | Known `Promotion.purchase_start_date` and/or `purchase_end_date` (inclusive) |

The current schema does **not** contain typed persisted purchase-price bounds or purchase-channel/condition/country restrictions. It is incorrect to invent these constraints, parse them out of prose, or assert they were checked. Their structured storage and input-contract extension remain follow-up work. Future *configured* rules whose purchase facts are absent must use the existing `RuleStatus.UNKNOWN` path, never default to satisfied.

Run `evaluate_eligibility_rules(...)` across all mapped configured dimensions. Never short-circuit on a first failure; retain ordered rule evaluations. Do not compare raw brand/model/SKU/retailer strings or duplicate PR 10's rule semantics in the application service.

### 4. Claim-window evaluation

This is independent of promotion lifecycle and purchase-date eligibility:

- Both fixed dates configured → create `FixedClaimWindow` and call `evaluate_fixed_claim_window(window, evaluation_date)`.
- Both relative day offsets configured → create `RelativeClaimWindow` and call `evaluate_relative_claim_window(window, request.purchase_date, evaluation_date)`.
- Neither pair configured → return `claim_window=None` and use the conservative missing-window classification extension above.
- Any partial, inverted or mutually conflicting definition → data integrity error, not an invented open window or silent fallback.

Opening and deadline dates are **inclusive**. Relative offsets are calendar days after the purchase date, with offset zero meaning the purchase date; delays are not counted from today's date. Date arithmetic overflow is an explicit error. The supplied `evaluation_date` must be reused consistently for every candidate (no implicit system clock or timezone conversion).

A historically published promotion with `PromotionStatus.EXPIRED` still requires evaluation of its own claim window. Do **not** map lifecycle expiration to `ClaimWindowStatus.EXPIRED`.

### 5. Classification and precedence

Use the existing PR 11 `classify_eligibility(...)` for each candidate with complete rule outcomes and the determined (or absent) claim state.

Mandatory precedence:

1. Any `NOT_SATISFIED` rule → `NOT_ELIGIBLE`; include all known failed-rule reason codes.
2. Otherwise any `UNKNOWN` rule → `POTENTIALLY_ELIGIBLE`; include all unknown reasons (and disclose missing window if also absent).
3. Otherwise missing claim window → `POTENTIALLY_ELIGIBLE` with `claim_window_unspecified`.
4. Otherwise claim not yet open → `CLAIM_NOT_YET_OPEN`.
5. Otherwise claim expired → `EXPIRED`.
6. Otherwise claim open → `ELIGIBLE`.

Preserve all rule evaluations, including non-decisive ones. Do not add a new classification or reimplement precedence in an application-layer if/else chain when the classifier can be extended minimally.

### 6. Benefit and reward composition

Return **all** benefits belonging to each matched variant, not just cashback:

- Fixed cashback: call `calculate_reward` and preserve exact configured `Decimal` value.
- Percentage cashback: use `request.purchase_price`, preserving PR 15 precision and `ROUND_HALF_UP` pence rounding. If price is `None`, catch only `MissingPurchasePrice`, set the amount to `None` and include `purchase_price_required_for_reward`.
- Product-specific cashback: pass resolved canonical `Product.id`. `MissingProductReward` for a candidate explicitly linked to that product is an inconsistent published reward definition: **raise a data-integrity error**. Never choose another product's amount or substitute zero.
- Cashback with no optional persisted reward definition: amount is `None`, reason `reward_not_configured`. The database currently permits missing reward definitions; do not parse the benefit name to guess money.
- `EXTENDED_WARRANTY` / `FREE_GIFT`: return benefit metadata with no monetary valuation.
- Monetary reward associated with warranty/gift, malformed or unsupported reward type, or invalid amount: fail explicitly as incompatible published data.

Reward calculability and purchase eligibility are separate. Missing a purchase price solely needed to calculate an otherwise eligible percentage reward must not automatically turn the purchase `NOT_ELIGIBLE` or `POTENTIALLY_ELIGIBLE` unless a **separate configured price rule** actually requires that fact.

Do not sum benefits, rank offers, or invent values for gifts or warranties.

### 7. Requirements, source links and explanations

Include every structured `Requirement` for the variant, including duplicates when persisted, with optional original description. These are evidence/action instructions only (receipt, serial number, registration, invoice, barcode, IMEI, installation evidence). Do not infer conditional eligibility from description, collect files, or imply that the claimant has satisfied them.

Expose exact validated `PublishedProvenance` including official source URL/type, retrieval and verification timestamps, and claim URL. Preserve any additional associated sources without relabelling their verification status or roles.

Provide **stable machine-readable reason codes** and simple deterministic, human-readable explanations (or explicit ordered explanation items suitable for display). Example copy, conditional on actual classified facts:

```text
ELIGIBLE + claim_window_open
  "The recorded eligibility rules match this purchase, and the claim window is open."
CLAIM_NOT_YET_OPEN
  "The recorded eligibility rules match; claiming opens on <date>."
EXPIRED
  "The recorded eligibility rules match, but the claim deadline has passed."
POTENTIALLY_ELIGIBLE + claim_window_unspecified
  "The recorded eligibility rules match, but the claim period is not available."
No candidates
  "No matching published promotion was found for this purchase."
```

Explain actual unknown rule reasons rather than claiming all rules passed. Reason codes, not English copy, are the semantic contract. Never promise manufacturer acceptance, parse free text to decide eligibility, or expose internal SQL exceptions to users. Keep ordering stable and format dates/money deterministically when displayed.

### 8. Multiple results, ordering and determinism

One candidate **variant** = one result. A promotion with two matching variants returns two distinct results. Never choose the newest or highest cashback offer as an implicit winner, and do not collapse retailer-specific and retailer-independent variants.

Keep the candidate order supplied by PR 9 (currently promotion creation date descending, promotion ID, variant ID). Restore it explicitly if hydration changes database order. Use stable persisted-ID ordering within benefits and requirements and documented stable source order. ORM join multiplicity must not duplicate result records.

No writes, publication changes, source timestamp updates or implicit caching. Identical input + evaluation date + fixed database snapshot must produce an equivalent result.

---

## Persistence, transactions, and migrations

**No schema or migration change.** Use existing tables:

```text
promotions
promotion_variants
promotion_variant_products
benefits
benefit_rewards
benefit_product_reward_values
requirements
promotion_sources
sources
```

Extend the established `SqlAlchemyPromotionRepository` or a narrowly related read adapter to return typed fully materialised candidate snapshots.

Required read behaviour:

- Restrict detail queries to IDs from the canonical candidate search.
- Use eager/batched loading or a bounded number of SQL queries; avoid one details query per candidate/benefit/requirement/source.
- Keep associations correctly scoped to variant/promotion; do not create duplicate results via cross-products of related tables.
- Materialise immutable DTOs while the session is open. No lazy ORM relationship access after returning.
- Protect read operations against autoflush, do not write/change lifecycle/commit data, and map SQLAlchemy exceptions to safe existing persistence exceptions.
- Candidate matching and detail hydration must observe one **coherent PostgreSQL snapshot**, e.g. through a dedicated read-only repeatable-read transaction at the request/wiring boundary, sharing session/transaction context with both identity and promotion reads. Do not let adjacent independent `READ COMMITTED` reads silently mix versions after concurrent edits.
- If a confirmed candidate disappears/mismatches within that snapshot, report a consistency/data issue rather than silently dropping it.
- No new indexes without a demonstrated query need, no destruction/backfill, no rewriting previous migration revisions.

Verify real PostgreSQL reads with current Alembic head, complete fixed/relative claim promotions, multi-benefit/variant graphs, requirements and source links. Preserve all existing migration tests.

---

## External services and network access

**None.** Runtime purchase checking uses PostgreSQL plus pure local computation. Source and claim URLs are passive result values. Do not request remote URLs, invoke AI/model providers, enrich purchase identities over the network or add retries/timeouts for nonexistent external dependencies.

---

## Security and privacy

- Validate request/evaluation-date types and never silently coerce unsafe values.
- Enforce published lifecycle boundaries; direct hydration of an unpublished/wrong candidate must not expose it as an eligible result.
- Use SQLAlchemy bound parameters for IDs, not interpolated SQL or executable rule text.
- Treat stored source URLs/descriptions as passive untrusted data, not code, instructions, or destinations for outbound requests.
- Do not log raw purchase details, claimant evidence, full source text, secrets, internal exceptions, or URL tokens.
- Keep the service transport-independent. Future REST/MCP adapters must add their own authentication/authorization (where applicable), rate/resource limits, wire schema and safe error mapping; they must not duplicate business rules.
- Use bounded/batched reads to avoid N+1 query amplification as the candidate set grows.

---

## Configuration and deployment

**None.** No environment variables, Docker/runtime changes, Railway configuration, queues, workers, health/readiness changes, database migrations, or new dependencies.

---

## Observability and operations

Use the existing structured logging/Sentry integration at appropriate application and infrastructure boundaries; do not introduce another telemetry stack. Useful low-cardinality diagnostics include:

```text
check_purchase_completed:
  candidate_count
  result_count
  classification_counts
  missing_claim_window_count
  missing_reward_amount_count

check_purchase_failed:
  category = validation | data_integrity | persistence
```

Expected unresolved identities and valid no-match results are normal outcomes, not infrastructure incidents. Actual malformed published data and database faults need safe internal diagnostics. Avoid logging brand/model/retailer strings, purchase price, source URLs, raw payloads, or UUIDs as metric labels.

---

## Failure, consistency, and recovery

| Scenario | Required outcome |
| --- | --- |
| Invalid `CheckPurchaseRequest` or `evaluation_date` | Input error before repository work. |
| Brand/retailer/model not found or ambiguous | Typed unresolved identity, no detail queries. |
| Resolved identities, zero published candidates | Empty successful check with explicit no-match reason. |
| Identity/candidate/detail SQL failure | Safe persistence exception; never no-match/`NOT_ELIGIBLE`. |
| Candidate details missing, duplicated, mismatched or unpublished | Data/consistency error; do not suppress the candidate. |
| No primary or claim source, duplicate role, missing verification | Published-data error; no invented URL. |
| Both claim-window types absent | `POTENTIALLY_ELIGIBLE` unless a known failed rule decides `NOT_ELIGIBLE`; explicit reason. |
| Partial/mixed/malformed claim-window definition | Published-data error, not the normal absent-window path. |
| Claim-window calendar overflow | Explicit invalid-data error; no clamping. |
| Missing percentage price | Nullable cashback amount plus reason; eligibility unchanged unless separate price rule. |
| Missing product-specific amount for matched product | Data-integrity error; no zero/fallback. |
| Cashback with no reward definition | Null amount + `reward_not_configured`; no guess. |
| Unsupported reward/benefit/requirement data | Safe explicit data error; no silent omission. |
| Concurrent publication/variant/source/reward update | Coherent read snapshot or safe whole-check failure; no mixed result. |
| Duplicate same check | Same result for same date/snapshot; no writes. |

One malformed matched candidate must not cause a misleading partial-success response that simply omits it. Partial-result semantics require a separate explicitly designed contract.

---

## Acceptance criteria

### Behaviour

- [ ] One canonical application-layer `check_purchase` composes all existing PR 9–15 primitives, with explicit evaluation date and injected dependencies.
- [ ] PR 9 identity resolution, published candidate inclusion and purchase-date filters remain unchanged.
- [ ] One output per matched published variant includes identifiers, lifecycle state, complete eligibility/reason details, claim-window evaluation, benefits/rewards, requirements and validated sources.
- [ ] PR 10 rule evaluations and PR 11 precedence are reused, not reimplemented.
- [ ] Fixed/relative/delayed window results correctly include inclusive opening/deadline dates.
- [ ] Missing claim window cannot result in `ELIGIBLE` and has a stable uncertainty reason.
- [ ] Cashback values use PR 15 exact GBP semantics; missing calculation inputs and absent definitions are explicit.
- [ ] Warranty/gift benefits are retained with no fictional GBP amount.
- [ ] Explanations reflect actual decisive reasons and never guarantee claim approval.
- [ ] No-match, unresolved identity, unknown information, invalid published data and infrastructure errors remain distinguishable.

### Data and consistency

- [ ] Only active/expired published candidates are available for runtime eligibility.
- [ ] Candidate and hydrated graph data come from a coherent PostgreSQL snapshot and are fully detached from ORM sessions.
- [ ] Multiple variants, benefits, requirements and sources do not cause duplicate/lost rows or cross-association.
- [ ] Read operation does not write; no Alembic migration is introduced.
- [ ] Inconsistent/corrupt published records are not silently dropped or shown as actionable eligible promotions.

### Security

- [ ] Input validation and published-data boundaries are enforced.
- [ ] No dynamic SQL injection surface, unsafe source retrieval, LLM eligibility decision, claimant evidence storage or leak of internal errors.
- [ ] Telemetry and outputs avoid credentials and unnecessary personal data.

### Operations

- [ ] Expected uncertainty is not logged as an infrastructure exception.
- [ ] Existing health/logging/error reporting remains intact and malformed data failures are diagnosable.
- [ ] Read performance is bounded and repeated checks have no side effects.

### Code quality

- [ ] Existing architecture boundaries are preserved; no duplicate classifier, domain engine, reward calculator or identity resolver.
- [ ] No speculative migration, dependency, REST endpoint, MCP tool, or unrelated refactor.
- [ ] Ruff and targeted/full unit and real PostgreSQL integration suites pass.

---

## Tests to add or update

### Unit tests

Create `backend/tests/unit/test_purchase_check.py` using in-memory fake ports and fixed evaluation dates/UUIDs. Cover:

- One complete active fixed-window promotion with cashback, multiple requirements and validated official/claim sources.
- Historically published `PromotionStatus.EXPIRED` with still-open claim window; no lifecycle-to-claim-status shortcut.
- Inclusive fixed claim opening/deadline boundaries and days just outside; relative `0..30`, delayed `30..60`, leap-year/year transitions.
- Multiple matching promotions and multiple matching variants of one promotion; stable order, no winner selection/duplication.
- Resolved empty candidate set versus unresolved brand, retailer and model with both `not_found` and `ambiguous`.
- Unpublished/archived detail rejection and mismatched/duplicate/missing detail records.
- Known failed rule before unknown, unknown before claim status; regression for all five PR 11 classifications.
- No configured claim window → potentially eligible with `claim_window_unspecified`; partial/conflicting definition rejected.
- Only persisted supported applicability is mapped; no channel/condition/country inferred.
- Fixed £100, 10% of £199.99 → £20.00 and product-specific calculation; `Decimal` exactness and absence of floats.
- Missing price for percentage reward yields null amount with explanation, **not** failed eligibility; missing product mapping raises data error.
- Cashback without reward definition; non-monetary benefits without amount; incompatible benefit/reward errors.
- Typed requirements including installation evidence and repeated requirement kinds are retained; descriptions not interpreted.
- Curated official+claim source and metadata round-trip; missing/ambiguous/unverified sources rejected.
- Unsupported persisted types, missing published benefits, invalid inputs, safe infrastructure failures, immutable output and deterministic explanations.

Update `backend/tests/unit/test_eligibility_result.py` with the minimal `None` claim-window support, while asserting no changed behaviour for all existing known claim statuses and reason precedence.

### PostgreSQL integration tests

Add `backend/tests/integration/test_check_purchase.py` using the existing PostgreSQL/Testcontainers approach:

- Seed complete manufacturer, product, retailer, active promotion, expired published promotion, variants, product links, rewards, requirements and curated sources.
- Exercise the actual identity → candidate → details path inside one appropriate read transaction/snapshot.
- Round-trip fixed, relative and absent claim timing from the real persisted types.
- Retrieve fixed, percentage, product-specific cashback and non-cash benefits with correct variant ownership.
- Verify retailer-specific versus unrestricted variants; stable one-result-per-variant ordering despite multiple related rows.
- Verify unpublished/archived filtering; preserve historically published `expired` record.
- Verify fully materialised results are valid after SQLAlchemy session close.
- Prove no inserts/updates/deletes occur during checks, including error paths and no-autoflush behaviour.
- Test consistent snapshot isolation during concurrent record modification, or explicitly demonstrate repeatable-read visibility using separate PostgreSQL connections.
- Verify malformed published-data and persistence-failure paths do not become no-match.
- Keep `test_postgres_migrations.py` and the existing candidate matching integration suite green; no new migration.

### API/application tests

**Application tests only.** Direct service tests cover internal signatures, result contracts, input checks and error distinctions. No FastAPI route, HTTP status, OpenAPI or transport validation changes in this PR.

### MCP contract tests

**N/A.** No MCP tool is added. Future MCP adapter must use the same service.

### External-boundary tests

**N/A.** No remote call is made; stored source URLs are passive output.

---

## Verification commands

From `backend/`:

```bash
uv sync --locked --extra dev
uv run ruff check .
uv run ruff format --check .
uv run pytest tests/unit/test_purchase_check.py tests/unit/test_eligibility_result.py
uv run pytest tests/integration/test_check_purchase.py
uv run pytest tests/integration/test_promotion_candidate_matching.py
uv run pytest tests/integration/test_postgres_migrations.py
uv run pytest
```

PostgreSQL/Testcontainers tests require the existing Docker environment. Confirm the current backend README/CI conventions before running. Report commands actually executed, not hypothetical passes. No type checker is currently required by backend CI; do not invent a passing check.

---

## Completion report

### Changed

- Canonical service entry point, typed result/port shapes, detail read adapter and deterministic explanation mappings.
- Existing domain evaluators reused unchanged, except the minimal absent-window classifier extension.

### Database and migrations

- Confirm no database schema or Alembic migration changes.
- Describe transaction ownership, snapshot isolation and real PostgreSQL verification.

### API/MCP contracts

- Confirm no public REST/MCP changes and no duplicated business rules.

### Tests and verification

- New/updated tests and exact executed commands with pass/fail/blocked outcomes.
- State whether PostgreSQL/Testcontainers was actually available.

### External configuration

- Confirm no new configuration, credentials, external providers, or deployment changes.

### Deviations

- Explain any departure from the proposed service, DTO/port or absent-window contracts with rationale.

### Remaining risks or follow-up

- Publication completeness validation **beyond provenance** is a separate task. Recorded structured terms may not represent every condition in original manufacturer terms; do not claim otherwise.
- Price restriction rules, country, purchase channel and condition are implemented as pure domain concepts but have no complete persisted rule and caller-input plumbing yet.
- Historical snapshots of edited promotions are not introduced.
- Public REST/MCP adapters, their authentication/rate limits/error wire format and frontend remain subsequent PRs.
