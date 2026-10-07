# PR 9 — Promotion Candidate Matching

## Repository state

**Expected branch:**  
`pr9-promotion-candidate-matching`

**Base branch:**  
`main`

**Dependencies:**

- PR 3 — Core Promotion Schema: merged.
- PR 4 — Promotion Lifecycle & History: merged.
- PR 5 — Benefit Model: merged.
- PR 6 — Promotion Source Provenance: merged.
- PR 7 — Product & Retailer Normalisation: merged.
- PR 8 — Purchase Input Contract: merged.
- Existing Python 3.13 application/domain boundaries, SQLAlchemy 2/PostgreSQL persistence, pytest/Testcontainers, and Ruff tooling.
- No new external provider, AI service, queue, worker, search engine, cache, or infrastructure dependency.

### Read first

Before making changes, read:

- `AGENTS.md`
- `.codex/tasks/TEMPLATE.md`
- `.codex/tasks/pr-3-core-promotion-schema.md`
- `.codex/tasks/pr-4-promotion-lifecycle-history.md`
- `.codex/tasks/pr-7-product-retailer-normalisation.md`
- `.codex/tasks/pr-8-purchase-input-contract.md`
- `backend/README.md`
- `backend/app/application/purchase_check.py`
- `backend/app/application/identity_matching.py`
- `backend/app/application/promotions.py`
- `backend/app/domain/identity_normalisation.py`
- `backend/app/domain/promotion_lifecycle.py`
- `backend/app/db/models/core.py`
- `backend/app/db/models/identity.py`
- `backend/app/db/repositories/identity_matching.py`
- `backend/app/db/repositories/promotions.py`
- `backend/tests/unit/test_product_retailer_matching.py`
- `backend/tests/unit/test_purchase_input.py`
- `backend/tests/integration/test_product_retailer_normalisation.py`
- `backend/pyproject.toml`

If a more narrowly scoped `AGENTS.md` exists on the implementation branch, read and follow it.

### Primary change area

Application orchestration and read-only promotion persistence for deterministic promotion candidate matching.

This PR introduces the broad pre-filter between purchase identity resolution and detailed eligibility evaluation.

Conceptually:

```text
CheckPurchaseRequest
        ↓
exact canonical identity resolution
        ↓
published promotion/variant candidate query
        ↓
candidate set for later detailed eligibility evaluation
```

This PR does not decide whether a candidate is eligible.

### Canonical implementation examples

Treat these as the preferred implementation references:

- `backend/app/application/purchase_check.py`
  - immutable transport-independent purchase input;
  - raw identity values remain distinct from canonical identities.
- `backend/app/application/identity_matching.py`
  - application-owned read-only matching boundary;
  - explicit `matched` / `not_found` / `ambiguous` outcomes;
  - no ORM objects crossing the application boundary.
- `backend/app/db/repositories/identity_matching.py`
  - deterministic SQLAlchemy reads;
  - no autoflush or runtime reference-data writes;
  - safe infrastructure error mapping.
- `backend/app/application/promotions.py`
  - application-owned promotion records and persistence protocols.
- `backend/app/db/repositories/promotions.py`
  - SQL filtering rather than loading all promotion rows and filtering in Python;
  - immutable application records;
  - safe `PromotionPersistenceError` handling.
- `backend/app/domain/promotion_lifecycle.py`
  - `active` means published current data;
  - `expired` means historical published data;
  - candidate and archived states are not normal runtime published data.

Do not introduce a generic query framework, rules engine, or eligibility abstraction solely for this PR.

### Relevant symbols

Inspect at minimum:

- `CheckPurchaseRequest`
- `IdentityResolver`
- `MatchResult`
- `MatchStatus`
- `IdentityPersistenceError`
- `PromotionStatus`
- `HISTORICAL_PUBLISHED_STATUSES`
- `PromotionPersistenceError`
- `Promotion`
- `PromotionVariant`
- `PromotionVariantProduct`
- `Manufacturer`
- `Product`
- `Retailer`
- `SqlAlchemyPromotionRepository`
- `SqlAlchemyIdentityRepository`

### Expected change surface

Expected changes should remain focused in:

```text
backend/app/application/
backend/app/db/repositories/
backend/tests/unit/
backend/tests/integration/
backend/README.md
```

Likely additions or updates include:

- one application-owned candidate result/reference contract;
- one application operation that resolves purchase identities then asks persistence for candidates;
- one narrow application-owned repository capability for candidate lookup;
- one SQLAlchemy query joining promotions, variants, and explicit product associations;
- unit tests for orchestration and unresolved identities;
- PostgreSQL integration tests for candidate filtering.

No schema or migration change is expected.

### Excluded areas

Do not implement:

- detailed eligibility evaluation;
- `eligible` / `ineligible` / `unknown` final purchase classifications;
- benefit value calculation;
- cashback amount calculation;
- extended-warranty duration calculation;
- free-gift qualification rules beyond broad promotion/product/retailer/date candidate filtering;
- claim-window evaluation;
- claim deadline calculation;
- requirement satisfaction;
- receipt, serial number, IMEI, invoice, barcode, or registration validation;
- minimum/maximum purchase-price rules;
- currency conversion;
- purchase-channel matching;
- retailer-group promotion applicability;
- retailer-group historical membership;
- promotion precedence or winner selection;
- deduplication of distinct matching promotion variants into one "best" promotion;
- REST routes;
- FastAPI request/response schemas;
- MCP tools;
- OpenAPI changes;
- purchase persistence;
- customer/account persistence;
- analytics/event persistence;
- scraping or external catalogue lookup;
- AI/LLM matching or eligibility;
- fuzzy, semantic, vector, or probabilistic matching;
- new database tables, columns, indexes, or migrations;
- background jobs;
- automatic promotion expiry;
- frontend behaviour.

### Unknowns Codex must verify

Before implementation verify:

- PR 8 remains the only `CheckPurchaseRequest` contract;
- no purchase-check orchestration or candidate-matching module has appeared since this specification was written;
- no scoped backend `AGENTS.md` has appeared;
- `active` and `expired` remain the only lifecycle states that unambiguously represent published data for normal/historical evaluation;
- `PromotionVariant.retailer_id = NULL` still means retailer-independent once published;
- zero `PromotionVariantProduct` rows still must not mean "all products";
- no retailer-group-to-promotion applicability relation has appeared;
- no purchase-channel field has been added to `CheckPurchaseRequest`;
- current repository error-wrapping and no-autoflush conventions remain unchanged;
- current lint, format, and test commands still match `backend/README.md` and `backend/pyproject.toml`.

Do not create parallel abstractions when equivalent behaviour already exists.

---

## Objective

After PR 9, the backend must be able to take a validated `CheckPurchaseRequest` and deterministically find the published promotion variants that are potentially applicable to that purchase before any detailed eligibility rules are evaluated.

The operation must:

1. resolve the request `brand` to one canonical `Manufacturer`;
2. resolve the request `retailer` to one canonical `Retailer`;
3. resolve the request `model` field to one canonical `Product` using both the matched manufacturer and retailer context, preserving PR 7 model-or-SKU semantics;
4. stop with an explicit unresolved-identity outcome when any required identity is not found or is ambiguous;
5. when all required identities resolve, query PostgreSQL for candidate promotion variants using only broad structured applicability:
   - canonical manufacturer;
   - canonical product;
   - canonical retailer or retailer-independent variant;
   - published lifecycle state;
   - purchase-date bounds when those bounds are known;
6. return an immutable, deterministic candidate set for a later eligibility evaluator.

A successful identity resolution with zero candidates is different from an unresolved identity.

No-candidate must mean:

```text
the purchase identities were resolved,
but no published promotion variant matched the broad candidate filters
```

It must not mean:

```text
brand/retailer/model could not be resolved
```

This PR is complete when candidate selection is deterministic, read-only, PostgreSQL-backed, preserves historical published promotions, and cannot accidentally turn identity uncertainty or incomplete detailed eligibility information into an ineligible decision.

---

## Architecture and invariants

Preserve the established dependency direction:

```text
future REST / MCP
        ↓
purchase-check application use case
        ↓
promotion candidate matching
        ↓
identity resolver + application-owned candidate repository port
        ↓
SQLAlchemy / PostgreSQL adapters
```

Task-specific invariants:

1. Candidate matching is not eligibility evaluation.
2. Candidate matching must return a superset of promotions that may pass later detailed eligibility checks; it must not apply unsupported detailed rules early.
3. Runtime candidate matching is deterministic and must not invoke an LLM, external HTTP service, search engine, embedding model, or fuzzy matcher.
4. Only canonical identities from PR 7 may be used in promotion persistence queries.
5. Raw brand/model/retailer strings must never be compared directly against promotion persistence fields.
6. Ambiguous identity must never choose the first candidate.
7. Identity not-found and ambiguity must remain distinguishable from a genuinely empty promotion candidate set.
8. Infrastructure failure must remain distinguishable from all domain/matching outcomes.
9. Only unambiguously published lifecycle states participate:
   - `active`;
   - `expired`.
10. `discovered`, `extracted`, `review`, and `archived` must not participate in candidate matching.
11. Expired promotions must remain available for historical purchase checks.
12. Archived promotions must remain excluded because the current schema cannot prove that every archived record was previously published.
13. A promotion variant must explicitly reference the resolved `Product` through `PromotionVariantProduct` to become a candidate.
14. Zero product associations must never mean "all products".
15. A published variant with `retailer_id = NULL` is retailer-independent and may match any resolved retailer.
16. A published variant with a non-null `retailer_id` matches only that exact canonical retailer.
17. Retailer-group membership must not imply promotion applicability in this PR.
18. Purchase start/end bounds are inclusive.
19. A missing purchase-date bound cannot safely exclude a promotion at candidate-selection time.
20. `purchase_price` is carried by `CheckPurchaseRequest` for later rule evaluation but does not affect PR 9 candidate selection.
21. Candidate matching is read-only and must not create aliases, SKU mappings, group memberships, promotions, or any other persisted data.
22. Distinct matching variants remain distinct candidates. Do not invent promotion/variant precedence.
23. Candidate ordering must be deterministic.
24. SQLAlchemy ORM instances must not cross the application boundary.

---

## API and contract changes

No public REST or MCP contract changes.

This PR introduces internal application contracts only.

### Candidate matching operation

Provide one canonical application operation equivalent to:

```python
match_promotion_candidates(
    request: CheckPurchaseRequest,
    identity_resolver: IdentityResolver,
    repository: PromotionCandidateRepository,
) -> PromotionCandidateSet | UnresolvedPurchaseIdentity
```

Exact names and object placement may follow current repository conventions, but the semantics below are required.

Do not add a second purchase-input type.

### Resolved purchase identity

A successful resolution must expose immutable canonical identifiers equivalent to:

```text
manufacturer_id: UUID
retailer_id: UUID
product_id: UUID
```

These identifiers are derived for the candidate-search operation.

Do not mutate or replace the raw fields inside `CheckPurchaseRequest`.

### Unresolved identity outcome

Expected identity uncertainty must be returned explicitly rather than represented as an empty candidate list.

The unresolved result must identify:

- which request field failed:
  - `brand`;
  - `retailer`;
  - `model`;
- the PR 7 match status:
  - `not_found`;
  - `ambiguous`;
- the deterministic candidate IDs already supplied by `MatchResult` when ambiguous.

Do not classify invalid `CheckPurchaseRequest` construction as unresolved identity; malformed structural input is already rejected by PR 8.

Do not classify `IdentityPersistenceError` as unresolved identity.

### Candidate reference

Each candidate must identify the exact promotion variant selected by the broad filter.

Use an immutable application-owned record containing at least:

```text
promotion_id: UUID
promotion_variant_id: UUID
promotion_status: PromotionStatus
retailer_id: UUID | None
purchase_start_date: date | None
purchase_end_date: date | None
```

Additional minimal persisted identifiers may be included only when they are directly useful to later evaluation and do not cause ORM leakage.

Do not load benefits, requirements, sources, or arbitrary full ORM graphs merely to build the PR 9 candidate list.

### Empty candidate set

When manufacturer, retailer, and product all resolve successfully but no rows satisfy the candidate query, return a successful candidate-set result with:

```text
candidates = ()
```

Do not turn this case into:

- identity `not_found`;
- an infrastructure exception;
- an eligible/ineligible result.

### Backward compatibility

PR 8 `CheckPurchaseRequest` remains unchanged.

Existing identity and lifecycle public/internal behaviour remains unchanged.

No transport contract exists to break.

### Idempotency

The operation is read-only.

Repeated calls against the same request and same persisted reference/promotion data must produce equivalent resolved identities and candidate ordering.

---

## Domain and application behaviour

### Resolution order

Resolve required identities in this order:

```text
brand
→ retailer
→ model/product
→ promotion candidates
```

#### Brand

Call the existing manufacturer resolver using `request.brand`.

If the result is:

- `matched`: continue with its canonical `Manufacturer.id`;
- `not_found`: return unresolved brand;
- `ambiguous`: return unresolved brand.

Do not infer manufacturer identity from the model/SKU when the supplied brand cannot be resolved.

#### Retailer

After manufacturer resolution succeeds, resolve `request.retailer`.

If the result is:

- `matched`: continue with its canonical `Retailer.id`;
- `not_found`: return unresolved retailer;
- `ambiguous`: return unresolved retailer.

Do not infer the retailer from a SKU, URL, retailer group, source, or promotion data.

#### Product

After manufacturer and retailer resolution succeed, resolve `request.model` with the existing combined product resolver using both canonical contexts:

```text
manufacturer_id = resolved manufacturer
retailer_id = resolved retailer
```

This preserves PR 7 behaviour in which the same input may match:

- a manufacturer-scoped product model/model alias;
- a retailer-scoped SKU;
- both, when they resolve to the same `Product`.

If model and SKU evidence resolve to different products, the existing resolver returns `ambiguous` and PR 9 must return unresolved model.

Do not prefer model over SKU or SKU over model.

### Candidate query

Once all identities resolve, query persistence for candidate variants equivalent to:

```sql
SELECT promotion + variant candidate fields
FROM promotions
JOIN promotion_variants
  ON promotion_variants.promotion_id = promotions.id
JOIN promotion_variant_products
  ON promotion_variant_products.promotion_variant_id = promotion_variants.id
WHERE promotions.manufacturer_id = :manufacturer_id
  AND promotions.status IN ('active', 'expired')
  AND promotion_variant_products.product_id = :product_id
  AND (
        promotion_variants.retailer_id IS NULL
        OR promotion_variants.retailer_id = :retailer_id
      )
  AND (
        promotions.purchase_start_date IS NULL
        OR promotions.purchase_start_date <= :purchase_date
      )
  AND (
        promotions.purchase_end_date IS NULL
        OR promotions.purchase_end_date >= :purchase_date
      )
ORDER BY promotions.created_at DESC,
         promotions.id,
         promotion_variants.id
```

The exact SQLAlchemy expression may differ, but the observable semantics must match.

Apply these filters in PostgreSQL rather than loading all promotions/variants and filtering them in Python.

### Published lifecycle filtering

Candidate matching includes:

- `active`: current validated/published data;
- `expired`: historical published data retained for historical purchase checking.

Candidate matching excludes:

- `discovered`;
- `extracted`;
- `review`;
- `archived`.

Do not use `list_active_promotions` alone for PR 9 because that would incorrectly hide historical promotions from a purchase made during an expired promotion's purchase period.

Do not include `archived` merely because it may once have been active; the current final status cannot distinguish a formerly published archived promotion from an abandoned candidate.

### Purchase-date matching

Date boundaries are calendar dates and are inclusive.

Examples:

```text
purchase_date == purchase_start_date
→ candidate

purchase_date == purchase_end_date
→ candidate

purchase_date < known purchase_start_date
→ not a candidate

purchase_date > known purchase_end_date
→ not a candidate
```

A null bound means the current structured record cannot use that bound to exclude the promotion at this broad stage:

```text
purchase_start_date = NULL
→ no lower-bound exclusion

purchase_end_date = NULL
→ no upper-bound exclusion
```

Do not reinterpret null as:

- today;
- promotion creation date;
- zero date;
- automatically ineligible.

Later publication completeness and detailed eligibility may treat missing required rule data as unknown/invalid according to their own contract.

### Retailer applicability

For published candidate matching:

```text
variant.retailer_id = resolved retailer
→ candidate if all other broad filters match

variant.retailer_id = NULL
→ retailer-independent candidate if all other broad filters match

variant.retailer_id = another retailer
→ not a candidate
```

Do not use current retailer-group membership to match a variant.

The schema has no promotion-to-retailer-group applicability relation in scope for PR 9.

### Product applicability

A candidate variant must have an explicit `PromotionVariantProduct` row for the resolved `Product.id`.

No product rows means no product match.

Do not infer product applicability from:

- same manufacturer;
- product name similarity;
- retailer SKU text after identity resolution;
- absence of restrictions;
- benefits or requirement descriptions.

### Purchase price

`request.purchase_price` must not alter candidate selection in PR 9.

Two otherwise identical requests differing only by `purchase_price` must produce the same identity resolution and candidate set.

Price belongs to later structured eligibility-rule evaluation.

### Multiple candidates

Multiple promotions and/or multiple variants of the same promotion may match.

Return all matching candidate variants.

Do not:

- choose the newest;
- choose the highest-value benefit;
- choose retailer-specific over retailer-independent;
- collapse multiple variants of one promotion;
- apply benefit precedence;
- apply promotion precedence.

Those are later eligibility/result-composition concerns.

### Failure handling

Expected identity uncertainty returns the explicit unresolved outcome.

Persistence failures must raise safe infrastructure/application errors using existing conventions.

Do not return a partial candidate set after:

- identity persistence failure;
- promotion candidate query failure.

Do not convert a database failure into an empty candidate set.

---

## Persistence, transactions, and migrations

No schema or migration change is expected.

### Repository capability

Introduce or extend an application-owned read port with a capability equivalent to:

```python
find_promotion_candidates(
    *,
    manufacturer_id: UUID,
    product_id: UUID,
    retailer_id: UUID,
    purchase_date: date,
) -> tuple[PromotionCandidate, ...]
```

Prefer a narrow candidate-specific protocol if extending the lifecycle-oriented `PromotionRepository` would make unrelated lifecycle callers depend on candidate-only methods.

The existing `SqlAlchemyPromotionRepository` may implement both protocols when that keeps infrastructure cohesive.

### Query requirements

The PostgreSQL query must:

- join through `PromotionVariantProduct`;
- filter manufacturer in SQL;
- filter lifecycle state in SQL;
- filter product in SQL;
- filter direct/retailer-independent applicability in SQL;
- filter known date bounds in SQL;
- use deterministic ordering;
- return application-owned immutable records;
- avoid ORM object leakage;
- avoid writes and explicit locks;
- avoid loading full unrelated promotion graphs.

### No-autoflush / read-only behaviour

Candidate matching must not flush unrelated pending ORM changes merely because a read occurs.

Follow the established identity matching no-autoflush/read-only convention where necessary.

The operation must issue no `INSERT`, `UPDATE`, or `DELETE` statements.

### Indexes

Do not add speculative indexes or a migration in PR 9.

The current schema already indexes the key variant/product association directions used by this small initial dataset.

If implementation reveals a demonstrated query-plan problem that cannot reasonably be handled without a new index, stop and document the evidence rather than silently expanding this PR's schema scope.

### Transactions

PR 9 performs reads only.

The caller owns the session/read transaction.

Do not introduce row locks, distributed locks, or long-lived write transactions.

A persistence failure aborts the operation; no state needs rollback beyond normal caller/session error handling because PR 9 has no writes.

### Migration verification

N/A — no migration is expected.

Existing migration/integration coverage must continue to pass unchanged.

---

## External services and network access

None.

Candidate matching must not perform:

- HTTP requests;
- manufacturer-site lookup;
- retailer-site lookup;
- search-engine lookup;
- AI/model calls;
- vector search;
- DNS resolution.

No timeout, retry, credential, or rate-limit configuration is introduced.

---

## Security and privacy

This PR adds no public transport surface and no new sensitive persisted data.

Required properties:

- treat `CheckPurchaseRequest` as already structurally validated by PR 8;
- use bound SQLAlchemy expressions, never string-built SQL from request values;
- use only canonical UUIDs in promotion candidate queries;
- do not log full purchase payloads merely for candidate matching;
- do not expose SQLAlchemy/database exception details;
- do not infer or persist aliases from runtime input;
- do not make any outbound request based on user-controlled identity text;
- keep `purchase_price` unused in this stage rather than accidentally embedding future financial eligibility assumptions.

Candidate matching must remain safe for punctuation-heavy model strings because those values are resolved through the existing parameterised identity layer before promotion lookup.

---

## Configuration and deployment

None.

No new:

- environment variables;
- secrets;
- packages;
- Docker changes;
- Railway settings;
- worker processes;
- cron jobs;
- health/readiness changes.

---

## Observability and operations

No new telemetry stack or dedicated metric is required for this internal pre-filter.

Keep the matching operation free of ad hoc logging.

Future public `check_purchase` orchestration may record low-cardinality outcomes such as:

- identity unresolved field/status;
- candidate count;
- final eligibility classification;

but PR 9 does not need to introduce those transport/use-case logs prematurely.

If existing error reporting observes an unexpected `PromotionPersistenceError` or `IdentityPersistenceError`, preserve the established safe exception boundary and correlation behaviour.

Do not log raw full purchase details, SQL statements, or database credentials.

---

## Failure, consistency, and recovery

PR 9 has no writes, so partial failure must never leave persisted state.

### Brand not found or ambiguous

Required final state:

- return unresolved brand outcome;
- do not resolve retailer/product;
- do not query promotions;
- no writes.

### Retailer not found or ambiguous

Required final state:

- preserve successful manufacturer resolution only as internal operation context;
- return unresolved retailer outcome;
- do not resolve product;
- do not query promotions;
- no writes.

### Product not found or ambiguous

Required final state:

- return unresolved model outcome;
- do not query promotions;
- no writes.

### Identity repository failure

Required final state:

- surface safe `IdentityPersistenceError`;
- do not translate to `not_found`;
- do not query later stages after the failure;
- no partial candidate result.

### Promotion candidate repository failure

Required final state:

- surface safe `PromotionPersistenceError` or the established equivalent;
- do not return an empty/partial candidate set;
- no writes.

### Concurrent reference/promotion maintenance

PR 9 must not add locks.

Each invocation must remain read-only and deterministic for the data visible to its read transaction/session.

Do not attempt to "repair" changing reference data during a runtime lookup.

### Duplicate rows

Persistence constraints already prevent duplicate product links for the same variant/product pair.

If multiple distinct variants satisfy the filter, all remain candidates.

Do not deduplicate by `promotion_id` and accidentally discard variant-level applicability.

---

## Acceptance criteria

### Behaviour

- [ ] A valid `CheckPurchaseRequest` can be passed to one application candidate-matching operation.
- [ ] Brand is resolved with the existing manufacturer resolver.
- [ ] Retailer is resolved with the existing retailer resolver.
- [ ] Model is resolved with the existing combined product resolver using both canonical manufacturer and retailer context.
- [ ] `not_found` and `ambiguous` identity outcomes are explicit and never represented as an empty promotion candidate set.
- [ ] Ambiguous identity never selects the first candidate.
- [ ] A fully resolved purchase can return zero, one, or many candidate variants.
- [ ] Candidate matching includes active promotions.
- [ ] Candidate matching includes expired historical published promotions when their broad applicability matches the purchase.
- [ ] Discovered, extracted, review, and archived promotions are excluded.
- [ ] Known purchase date bounds are inclusive.
- [ ] A known start date after the purchase excludes the promotion.
- [ ] A known end date before the purchase excludes the promotion.
- [ ] A null start or end bound does not exclude the promotion at candidate stage.
- [ ] An exact retailer variant matches its retailer.
- [ ] A retailer-independent variant with `retailer_id = NULL` may match any resolved retailer.
- [ ] A variant restricted to another retailer is excluded.
- [ ] The resolved product must have an explicit `PromotionVariantProduct` association.
- [ ] Zero product associations never mean all products.
- [ ] `purchase_price` does not affect the PR 9 candidate set.
- [ ] Multiple matching variants remain separate candidates.
- [ ] Candidate ordering is deterministic.
- [ ] Candidate matching performs no detailed eligibility, claim-window, benefit-value, requirement, precedence, channel, or retailer-group evaluation.

### Data and consistency

- [ ] Candidate lookup is performed in PostgreSQL rather than by loading every promotion and filtering in Python.
- [ ] Candidate matching is read-only and performs no `INSERT`, `UPDATE`, or `DELETE`.
- [ ] SQLAlchemy ORM instances do not cross the application boundary.
- [ ] Candidate/unvalidated promotion states cannot enter runtime candidate results.
- [ ] Historical expired promotion rows and their retained graph are not modified.
- [ ] No schema or migration change is introduced.
- [ ] No speculative database index is introduced.

### Security

- [ ] Promotion lookup uses bound SQLAlchemy expressions and canonical UUIDs.
- [ ] Database exceptions are mapped to the established safe persistence error.
- [ ] Identity persistence failure is never converted to `not_found`.
- [ ] No outbound request is derived from purchase identity input.
- [ ] No runtime lookup creates or mutates aliases/SKUs/reference data.
- [ ] No sensitive or unnecessary purchase payload is added to logs.

### Operations

- [ ] Existing health/readiness behaviour remains unchanged.
- [ ] No new environment or deployment configuration is required.
- [ ] Failure paths return/raise intentional application outcomes without leaking SQL details.
- [ ] The matcher introduces no new external dependency or retry loop.

### Code quality

- [ ] Existing application/domain/persistence boundaries are preserved.
- [ ] `CheckPurchaseRequest` is reused unchanged.
- [ ] Existing `MatchResult`/`MatchStatus` semantics are reused rather than duplicated.
- [ ] Existing `PromotionStatus` values are reused rather than duplicated as raw lifecycle logic.
- [ ] No unnecessary generic repository, rules engine, or unrelated refactor is introduced.
- [ ] Ruff formatting/linting and all relevant tests pass.

---

## Tests to add or update

### Unit tests

Add focused unit coverage, likely in:

```text
backend/tests/unit/test_promotion_candidate_matching.py
```

Cover at minimum:

- matched brand → matched retailer → matched product → repository candidate query;
- product resolution receives both `manufacturer_id` and `retailer_id`;
- brand `not_found` returns unresolved brand and performs no later matching/query;
- brand `ambiguous` returns unresolved brand and never picks a candidate;
- retailer `not_found` returns unresolved retailer and performs no product/promotion query;
- retailer `ambiguous` returns unresolved retailer;
- product `not_found` returns unresolved model and performs no promotion query;
- product `ambiguous` returns unresolved model;
- identity persistence failure propagates as infrastructure failure;
- promotion persistence failure propagates and is not converted to an empty set;
- fully resolved identity plus empty repository result returns a successful empty candidate tuple;
- multiple repository candidates are preserved;
- different `purchase_price` values do not change candidate selection;
- the application operation performs no network or persistence writes.

Use small fakes/stubs rather than mocking SQLAlchemy internals.

### PostgreSQL integration tests

Add real PostgreSQL coverage, likely in:

```text
backend/tests/integration/test_promotion_candidate_matching.py
```

Use the existing Testcontainers/migrated-database fixtures.

Cover at minimum:

- active + correct manufacturer/product/direct retailer/date is returned;
- expired + historical purchase within known bounds is returned;
- discovered/extracted/review/archived rows are excluded;
- wrong manufacturer is excluded;
- wrong product is excluded;
- no `PromotionVariantProduct` link is excluded;
- direct variant for another retailer is excluded;
- `retailer_id = NULL` variant is included;
- purchase exactly on start date is included;
- purchase exactly on end date is included;
- purchase before known start is excluded;
- purchase after known end is excluded;
- null start with otherwise matching data is included;
- null end with otherwise matching data is included;
- both null bounds with otherwise matching published data are included;
- two matching variants of one promotion remain two candidates;
- two matching promotions are both returned;
- candidate order is stable and explicitly asserted;
- candidate reads do not autoflush unrelated pending ORM writes;
- the candidate query issues only `SELECT` statements;
- a failed PostgreSQL transaction is wrapped as the safe promotion persistence error without leaking SQL details.

Where practical, use the real `IdentityResolver` + `SqlAlchemyIdentityRepository` + candidate repository together for at least one end-to-end application-level integration test.

### API/application tests

Application behaviour is covered above.

REST/FastAPI contract tests: N/A — no route or wire contract changes.

### MCP contract tests

N/A — MCP is unchanged.

### External-boundary tests

N/A — no external service or model/provider boundary is introduced.

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
# N/A — backend/pyproject.toml currently configures no mypy/pyright command.
# Do not invent a type-checker requirement for this PR.

# Targeted unit tests
uv run pytest tests/unit/test_promotion_candidate_matching.py

# PostgreSQL integration tests
uv run pytest tests/integration/test_promotion_candidate_matching.py

# Existing closely related regression tests
uv run pytest tests/unit/test_product_retailer_matching.py tests/unit/test_purchase_input.py
uv run pytest tests/integration/test_product_retailer_normalisation.py tests/integration/test_promotion_lifecycle.py

# Broader backend test suite
uv run pytest

# Migration verification
# N/A — no schema/migration change is expected.
```

If the implementation places tests under different repository-conventional filenames, use the actual paths and report them.

If Docker/Testcontainers is unavailable, document:

1. the exact PostgreSQL integration command that could not run;
2. why it could not run;
3. what non-PostgreSQL verification was run instead;
4. the remaining persistence-query risk.

Do not substitute SQLite for the required PostgreSQL candidate-query coverage.

Never weaken or delete a failing existing lifecycle/identity test merely to make PR 9 green.

---

## Completion report

When implementation is complete, provide:

### Changed

Summarise:

- the application candidate-matching operation;
- the resolved/unresolved identity result contract;
- the candidate reference contract;
- the SQLAlchemy candidate query;
- any README documentation updated.

### Database and migrations

None expected.

If this changes, explain why the PR expanded beyond the specification before claiming completion.

### API/MCP contracts

None.

### Tests and verification

List:

- unit tests added/updated;
- PostgreSQL integration tests added/updated;
- exact verification commands run;
- results.

Do not claim an unrun command passed.

### External configuration

None.

### Deviations

Describe any meaningful deviation from this specification and why it was necessary.

Use `None` when there were no deviations.

### Remaining risks or follow-up

Expected later work includes detailed eligibility/rule evaluation and the final shared `check_purchase` result/transport surfaces.

List only unresolved PR 9 risks beyond those planned later stages.

Use `None` when PR 9 itself is complete.