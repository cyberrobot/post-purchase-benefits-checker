# PR 10 — Core Eligibility Rules

## Repository state

**Expected branch:**  
`pr10-core-eligibility-rules`

**Base branch:**  
`main`

**Dependencies:**

- PR 3 — Core Promotion Schema: merged.
- PR 4 — Promotion Lifecycle & History: merged.
- PR 5 — Benefit Model: merged.
- PR 6 — Promotion Source Provenance: merged.
- PR 7 — Product & Retailer Normalisation: merged.
- PR 8 — Purchase Input Contract: merged.
- PR 9 — Promotion Candidate Matching: merged.
- Existing Python 3.13 domain/application boundaries and pytest/Ruff tooling.
- No new database, migration, transport, provider, AI, queue, worker, cache, or infrastructure dependency.

### Read first

Before making changes, read:

- `AGENTS.md`
- `.codex/tasks/TEMPLATE.md`
- `.codex/tasks/pr-7-product-retailer-normalisation.md`
- `.codex/tasks/pr-8-purchase-input-contract.md`
- `.codex/tasks/pr-9-promotion-candidate-matching.md`
- `backend/README.md`
- `backend/app/application/purchase_check.py`
- `backend/app/application/promotion_candidate_matching.py`
- `backend/app/application/identity_matching.py`
- `backend/app/domain/identity_normalisation.py`
- `backend/app/domain/benefits.py`
- `backend/app/db/models/core.py`
- `backend/tests/unit/test_identity_normalisation.py`
- `backend/tests/unit/test_purchase_input.py`
- `backend/tests/unit/test_promotion_candidate_matching.py`
- `backend/pyproject.toml`

If a more narrowly scoped `AGENTS.md` exists on the implementation branch, read and follow it.

### Primary change area

Pure domain eligibility rules.

This PR introduces deterministic, composable rule evaluation for the core purchase attributes required by the MVP:

- manufacturer;
- product resolved from model/SKU;
- retailer;
- purchase channel;
- purchase date;
- purchase price;
- product condition;
- purchase country.

Conceptually:

```text
canonical purchase facts
        +
typed eligibility rules
        ↓
deterministic per-rule evaluations
```

This PR does **not** produce a final purchase eligibility classification.

### Canonical implementation examples

Treat these as the preferred implementation references:

- `backend/app/domain/identity_normalisation.py`
  - immutable domain values;
  - stable enums;
  - deterministic validation;
  - explicit unsupported outcomes;
  - no persistence/network/framework dependency.
- `backend/app/domain/benefits.py`
  - small domain-owned values;
  - explicit validation;
  - stable external/persisted enum semantics.
- `backend/app/application/purchase_check.py`
  - exact `Decimal` purchase-price semantics;
  - calendar-date semantics;
  - distinction between missing and zero price.
- `backend/app/application/promotion_candidate_matching.py`
  - canonical manufacturer/product/retailer IDs;
  - model/SKU has already been resolved to `Product.id`;
  - candidate matching remains separate from detailed eligibility.

Do not introduce:

- a general-purpose rules engine;
- a rules DSL;
- expression parsing;
- `eval`;
- dynamic Python rule loading;
- JSON-logic style execution;
- plugin execution;
- AI/LLM-based eligibility.

### Relevant symbols

Inspect at minimum:

- `CheckPurchaseRequest`
- `ResolvedPurchaseIdentity`
- `PromotionCandidate`
- `PromotionCandidateSet`
- `IdentityResolver`
- `PurchaseChannel`
- `resolve_purchase_channel`
- `MatchStatus`
- `Manufacturer`
- `Product`
- `Retailer`
- `Promotion`
- `PromotionVariant`
- `PromotionVariantProduct`

### Expected change surface

Expected changes should remain focused in:

```text
backend/app/domain/
backend/tests/unit/
backend/README.md
```

Likely additions include:

```text
backend/app/domain/eligibility_rules.py
backend/tests/unit/test_eligibility_rules.py
```

A small refactor of shared purchase-date or exact-money validation is acceptable only when required to prevent duplicate validation semantics between `CheckPurchaseRequest` and the new domain facts.

No database or application orchestration change is expected.

### Excluded areas

Do not implement:

- final result classifications such as:
  - `ELIGIBLE`;
  - `POTENTIALLY_ELIGIBLE`;
  - `NOT_ELIGIBLE`;
  - `CLAIM_NOT_YET_OPEN`;
  - `EXPIRED`;
- final promotion/purchase eligibility aggregation;
- promotion precedence;
- choosing a winning promotion;
- benefit calculation;
- cashback calculation;
- warranty duration calculation;
- free-gift calculation;
- claim-window calculation;
- fixed claim deadlines;
- relative claim deadlines;
- delayed claim windows;
- requirement satisfaction;
- receipt, invoice, serial number, IMEI, registration, or barcode checks;
- quantity or multi-product/basket rules;
- retailer-group eligibility;
- historical retailer-group applicability;
- customer residency rules;
- shipping-address rules;
- billing-address rules;
- currency conversion;
- non-GBP price evaluation;
- identity resolution;
- candidate matching changes;
- extensions to `CheckPurchaseRequest`;
- REST routes;
- FastAPI schemas;
- MCP tools;
- OpenAPI changes;
- rule persistence;
- new eligibility-rule tables;
- Alembic migrations;
- promotion authoring format;
- publication completeness validation;
- scraping;
- external product lookup;
- AI/LLM evaluation;
- frontend behaviour.

### Unknowns Codex must verify

Before implementation verify:

- PR 9 remains the canonical promotion-candidate matching implementation;
- no eligibility-rule module has appeared since this specification was written;
- no final eligibility-result contract has appeared;
- `PurchaseChannel` still defines `online` and `in_store`;
- `CheckPurchaseRequest` still contains only:
  - `brand`;
  - `model`;
  - `retailer`;
  - `purchase_date`;
  - `purchase_price`;
- purchase price remains GBP and uses exact `Decimal` semantics;
- no existing product-condition vocabulary has appeared;
- no existing country-code value object has appeared;
- no shared purchase date/money validation helper already exists;
- current lint/format/test commands still match `backend/README.md` and `backend/pyproject.toml`.

Do not create parallel concepts when the repository already contains an equivalent implementation.

---

## Objective

After PR 10, the backend must contain a pure deterministic domain layer capable of evaluating the core eligibility constraints of one promotion variant against canonical purchase facts.

The supported rule dimensions are:

```text
manufacturer
product / model / SKU
retailer
purchase channel
purchase date
purchase price
product condition
country
```

The engine must operate only on already-normalised or canonical values.

In particular:

```text
raw model/SKU
    ↓ PR 7 identity resolution
canonical Product.id
    ↓
product eligibility rule
```

Eligibility rules must never independently compare raw model or SKU strings.

For every configured rule, evaluation must return one of:

```text
satisfied
not_satisfied
unknown
```

These are **rule-level outcomes**, not final purchase classifications.

Examples:

```text
required retailer matches
→ satisfied

purchase price below required minimum
→ not_satisfied

promotion requires online purchase
but purchase channel is not known
→ unknown
```

The rule layer must:

- be deterministic;
- be independent of PostgreSQL;
- be independent of SQLAlchemy;
- be independent of FastAPI/MCP;
- perform no network requests;
- perform no LLM calls;
- preserve exact money semantics;
- preserve inclusive date/price boundary semantics;
- distinguish absent purchase facts from failed rules;
- provide stable machine-readable reason codes;
- produce deterministic rule ordering.

This PR is complete when all eight rule categories can be represented and evaluated through pure Python domain values with dense boundary-focused unit coverage.

---

## Architecture and invariants

Preserve the dependency direction:

```text
future REST / MCP
        ↓
future check_purchase application service
        ↓
candidate matching + eligibility orchestration
        ↓
domain eligibility rules
```

The new rule layer must not depend upward on application or transport concerns.

### Core invariants

1. Eligibility evaluation is deterministic.
2. LLM output never decides eligibility.
3. Rule evaluation performs no database or network access.
4. Rules operate on typed structured data.
5. Raw brand/model/retailer strings are not eligibility-rule inputs.
6. Manufacturer, product, and retailer rules use canonical UUID identities.
7. Model/SKU eligibility is represented by canonical `Product.id`.
8. Purchase channel uses the existing `PurchaseChannel` classification.
9. Purchase date is a calendar `date`, not a timestamp.
10. Purchase-price evaluation uses `Decimal`, never `float`.
11. Price comparison uses GBP semantics already established by `CheckPurchaseRequest`.
12. Missing caller information must not automatically fail a rule.
13. Unsupported or malformed rule definitions must not become `unknown`; invalid rules must fail construction/validation.
14. `unknown` means the rule is valid but the required purchase fact is unavailable.
15. A failed rule means the known purchase fact contradicts the rule.
16. No final `eligible`/`not eligible` classification is produced in this PR.
17. Rule ordering is deterministic but is not rule precedence.
18. Evaluation must not stop after the first failed rule.
19. Every configured rule should be evaluated so later result composition can explain all known failures and uncertainties.
20. Do not introduce arbitrary executable rule definitions.

---

## API and contract changes

No public REST or MCP contract changes.

This PR introduces domain contracts only.

### `RuleKind`

Introduce a stable domain enum equivalent to:

```python
class RuleKind(StrEnum):
    MANUFACTURER = "manufacturer"
    PRODUCT = "product"
    RETAILER = "retailer"
    PURCHASE_CHANNEL = "purchase_channel"
    PURCHASE_DATE = "purchase_date"
    PURCHASE_PRICE = "purchase_price"
    CONDITION = "condition"
    COUNTRY = "country"
```

These values must remain stable because later result/explainability contracts may expose them.

### `RuleStatus`

Introduce a rule-level outcome classification equivalent to:

```python
class RuleStatus(StrEnum):
    SATISFIED = "satisfied"
    NOT_SATISFIED = "not_satisfied"
    UNKNOWN = "unknown"
```

Do not use:

```text
eligible
ineligible
potentially_eligible
```

for individual rules.

Those belong to the later result-classification layer.

### `RuleEvaluation`

Provide an immutable rule result equivalent to:

```python
@dataclass(frozen=True, slots=True)
class RuleEvaluation:
    kind: RuleKind
    status: RuleStatus
    reason_code: str
```

The exact implementation may use a reason-code enum if that is cleaner.

Requirements:

- immutable;
- deterministic;
- no human prose required;
- no database objects;
- no transport models;
- stable machine-readable `reason_code`;
- no sensitive purchase payloads embedded in the result.

Later explainability may map reason codes to display text.

Do not make display strings the business contract.

### Purchase eligibility facts

Introduce an immutable domain input equivalent to:

```python
@dataclass(frozen=True, slots=True)
class PurchaseEligibilityFacts:
    manufacturer_id: UUID
    product_id: UUID
    retailer_id: UUID
    purchase_date: date
    purchase_price: Decimal | None = None
    purchase_channel: PurchaseChannel | None = None
    condition: PurchaseCondition | None = None
    country_code: str | None = None
```

This is not a replacement for `CheckPurchaseRequest`.

`CheckPurchaseRequest` remains the raw application input.

Conceptually:

```text
CheckPurchaseRequest
        ↓
PR 7 / PR 9 identity resolution
        ↓
canonical purchase facts
        ↓
eligibility rules
```

Future application orchestration may construct `PurchaseEligibilityFacts`.

PR 10 does not implement that orchestration.

### Required canonical facts

These must be required:

```text
manufacturer_id
product_id
retailer_id
purchase_date
```

They represent information already required/resolved by PRs 8 and 9.

UUID fields must contain actual `UUID` values.

Do not accept raw names or identifiers in their place.

### Optional purchase facts

These may be unknown:

```text
purchase_price
purchase_channel
condition
country_code
```

Missing information is represented by:

```python
None
```

Do not invent sentinel strings such as:

```text
unknown
n/a
other
```

### Purchase price

When supplied, `purchase_price` must preserve PR 8 semantics:

- `Decimal`;
- finite;
- non-negative;
- no more than two fractional decimal places;
- no coercion from `float`;
- no silent rounding;
- GBP;
- zero differs from missing.

Prefer sharing validation with `CheckPurchaseRequest` rather than duplicating the implementation.

### Purchase date

`purchase_date` must preserve PR 8 semantics:

- actual `datetime.date`;
- `datetime.datetime` rejected;
- no timezone;
- no current-date comparison;
- no parsing inside the domain rule layer.

### `PurchaseCondition`

Introduce a minimal canonical condition enum.

Initial values:

```python
class PurchaseCondition(StrEnum):
    NEW = "new"
    REFURBISHED = "refurbished"
    USED = "used"
```

Do not add:

```text
other
unknown
```

`None` represents unavailable purchase-condition information.

The enum must remain straightforward to extend when real promotion data requires another explicit condition.

Rules must not infer condition from:

- retailer;
- model;
- price;
- SKU;
- product name;
- promotion wording.

### Country code

`country_code` represents the country in which the purchase was made.

It does **not** represent:

- nationality;
- residence;
- delivery destination;
- billing address;
- payment-card country.

Use canonical ISO-style two-letter uppercase codes such as:

```text
GB
IE
```

The domain contract must require canonical syntax:

```text
exactly two ASCII uppercase letters
```

Do not perform network lookup or locale inference.

Do not silently convert arbitrary values such as:

```text
UK
United Kingdom
England
uk
```

inside the rule evaluator.

Input normalisation, if later required by a transport contract, belongs outside the rule engine.

---

## Domain and application behaviour

### Typed rule forms

Implement explicit typed rule forms.

Do not implement a generic:

```text
field + operator + arbitrary value
```

rules DSL.

Preferred conceptual forms are described below.

Exact class names may follow repository conventions.

### Manufacturer rule

Conceptually:

```python
ManufacturerRule(
    manufacturer_ids=frozenset({...})
)
```

At least one canonical UUID is required.

Evaluation:

```text
purchase manufacturer in allowed manufacturers
→ satisfied

purchase manufacturer not in allowed manufacturers
→ not_satisfied
```

Manufacturer identity is always present in `PurchaseEligibilityFacts`.

No `unknown` result is expected for a valid manufacturer rule.

Suggested reason codes:

```text
manufacturer_match
manufacturer_mismatch
```

Do not compare manufacturer names, aliases, slugs, or raw request text.

### Product / model / SKU rule

Conceptually:

```python
ProductRule(
    product_ids=frozenset({...})
)
```

At least one canonical `Product.id` is required.

Evaluation:

```text
purchase product in allowed products
→ satisfied

purchase product not in allowed products
→ not_satisfied
```

Suggested reason codes:

```text
product_match
product_mismatch
```

Model and retailer SKU have already been canonicalised by PR 7.

Do not add separate runtime rule comparison against:

```text
model_number string
SKU string
model alias
SKU alias
```

For eligibility purposes:

```text
model/SKU rule
=
canonical Product.id rule
```

### Retailer rule

Conceptually:

```python
RetailerRule(
    retailer_ids=frozenset({...})
)
```

At least one canonical retailer UUID is required when the rule exists.

Evaluation:

```text
purchase retailer in allowed retailers
→ satisfied

purchase retailer not in allowed retailers
→ not_satisfied
```

Suggested reason codes:

```text
retailer_match
retailer_mismatch
```

The absence of a retailer rule means the eligibility policy does not restrict retailer.

Do not:

- infer retailer-group eligibility;
- evaluate current retailer-group memberships;
- match retailer names directly.

### Purchase-channel rule

Conceptually:

```python
PurchaseChannelRule(
    channels=frozenset({
        PurchaseChannel.ONLINE,
        PurchaseChannel.IN_STORE,
    })
)
```

At least one channel is required.

Evaluation:

```text
purchase_channel is None
→ unknown

known channel is allowed
→ satisfied

known channel is not allowed
→ not_satisfied
```

Suggested reason codes:

```text
purchase_channel_match
purchase_channel_mismatch
purchase_channel_unknown
```

Reuse the existing PR 7 `PurchaseChannel` enum.

Do not reimplement channel alias normalisation inside eligibility evaluation.

Raw values such as:

```text
web
shop
website
```

belong to `resolve_purchase_channel(...)` before rule evaluation.

### Purchase-date rule

Conceptually:

```python
PurchaseDateRule(
    start_date: date | None,
    end_date: date | None,
)
```

At least one bound must be present when a date rule exists.

If both bounds are present:

```text
start_date <= end_date
```

must hold.

Boundaries are inclusive.

Evaluation:

```text
purchase_date == start_date
→ satisfied

purchase_date == end_date
→ satisfied

purchase_date < start_date
→ not_satisfied

purchase_date > end_date
→ not_satisfied
```

A null bound is open:

```text
start_date=None
→ no lower bound

end_date=None
→ no upper bound
```

Suggested reason codes:

```text
purchase_date_match
purchase_date_before_start
purchase_date_after_end
```

`purchase_date` itself is required in the facts, so valid date-rule evaluation does not return `unknown`.

Do not:

- compare against today's date;
- calculate claim dates;
- interpret promotion expiry lifecycle state here.

### Purchase-price rule

Conceptually:

```python
PurchasePriceRule(
    minimum: Decimal | None,
    maximum: Decimal | None,
)
```

At least one bound must be supplied when a price rule exists.

Both bounds use GBP.

Validation:

- actual `Decimal`;
- finite;
- non-negative;
- at most two fractional decimal places;
- no silent rounding;
- if both exist:

```text
minimum <= maximum
```

Boundaries are inclusive.

Evaluation:

```text
purchase_price is None
→ unknown

purchase_price == minimum
→ satisfied

purchase_price == maximum
→ satisfied

purchase_price < minimum
→ not_satisfied

purchase_price > maximum
→ not_satisfied
```

Suggested reason codes:

```text
purchase_price_match
purchase_price_below_minimum
purchase_price_above_maximum
purchase_price_unknown
```

Zero is a valid known amount.

Do not interpret:

```python
Decimal("0")
```

as missing.

Do not perform currency conversion.

### Product-condition rule

Conceptually:

```python
PurchaseConditionRule(
    conditions=frozenset({
        PurchaseCondition.NEW,
    })
)
```

At least one condition is required.

Evaluation:

```text
condition is None
→ unknown

known condition is allowed
→ satisfied

known condition is not allowed
→ not_satisfied
```

Suggested reason codes:

```text
condition_match
condition_mismatch
condition_unknown
```

Example:

```text
rule = NEW only
purchase = REFURBISHED

→ not_satisfied
```

Do not infer `NEW` merely because:

- the retailer is a major retailer;
- a price is supplied;
- the product is a current model.

### Country rule

Conceptually:

```python
CountryRule(
    country_codes=frozenset({"GB"})
)
```

At least one canonical country code is required.

Evaluation:

```text
country_code is None
→ unknown

known country is allowed
→ satisfied

known country is not allowed
→ not_satisfied
```

Suggested reason codes:

```text
country_match
country_mismatch
country_unknown
```

Country matching is exact after canonicalisation.

Do not infer country from:

- retailer;
- currency;
- user IP;
- locale;
- product model;
- application deployment location.

### Rule collection

Provide an immutable aggregate equivalent to:

```python
@dataclass(frozen=True, slots=True)
class PromotionEligibilityRules:
    manufacturer: ManufacturerRule | None = None
    product: ProductRule | None = None
    retailer: RetailerRule | None = None
    purchase_channel: PurchaseChannelRule | None = None
    purchase_date: PurchaseDateRule | None = None
    purchase_price: PurchasePriceRule | None = None
    condition: PurchaseConditionRule | None = None
    country: CountryRule | None = None
```

Exact representation may differ, but:

- each dimension has an explicit typed rule;
- an absent rule means that dimension imposes no eligibility restriction;
- an absent rule does not produce `unknown`;
- malformed configured rules fail validation rather than disappearing.

### Evaluation operation

Provide one pure operation equivalent to:

```python
evaluate_eligibility_rules(
    facts: PurchaseEligibilityFacts,
    rules: PromotionEligibilityRules,
) -> tuple[RuleEvaluation, ...]
```

Evaluate configured rules in stable order:

```text
manufacturer
product
retailer
purchase_channel
purchase_date
purchase_price
condition
country
```

Only configured rules need to produce results.

Do not produce synthetic results for dimensions with no rule.

For example:

```text
rules:
- manufacturer
- product
- purchase_price

→ exactly three RuleEvaluation values
```

### No short-circuiting

Evaluate every configured rule.

Example:

```text
retailer mismatches
purchase price is missing
country mismatches
```

must be capable of returning:

```text
retailer        → not_satisfied
purchase_price  → unknown
country         → not_satisfied
```

Do not stop after the retailer failure.

A later classification layer decides what those outcomes mean collectively.

### Missing information

These conditions are different:

```text
rule absent
purchase fact missing
purchase fact contradicts rule
```

Required semantics:

```text
rule absent
→ no restriction / no RuleEvaluation

rule exists + required optional fact missing
→ unknown

rule exists + known fact violates rule
→ not_satisfied
```

Never turn missing information into `not_satisfied`.

### Determinism

For identical:

```text
facts
rules
application version
```

evaluation must return equivalent:

```text
statuses
reason codes
ordering
```

No result may depend on:

- current time;
- database row order;
- random values;
- network availability;
- locale;
- external service state;
- AI/model output.

---

## Persistence, transactions, and migrations

None.

PR 10 defines the core domain rule forms and evaluation semantics only.

Do not add:

- `eligibility_rules` tables;
- JSON rule blobs;
- rule-expression columns;
- rule DSL persistence;
- generic operator/value tables;
- new SQLAlchemy mappings;
- Alembic migrations.

The existing persistence schema already represents some applicability information such as:

```text
Promotion.manufacturer_id
PromotionVariantProduct.product_id
PromotionVariant.retailer_id
Promotion.purchase_start_date
Promotion.purchase_end_date
```

PR 10 must not duplicate those fields into another persistence model.

Mapping published promotion data into `PromotionEligibilityRules` belongs to later application/promotion authoring integration.

Keeping the rule evaluator independent of persistence allows the same deterministic semantics to be reused regardless of how rule definitions are stored.

### Migration verification

N/A.

Current migration head must remain unchanged.

---

## External services and network access

None.

Eligibility evaluation must not perform:

- HTTP requests;
- DNS resolution;
- manufacturer lookups;
- retailer lookups;
- product catalogue searches;
- search-engine queries;
- AI/model calls;
- vector search;
- currency-rate lookup.

No timeout, retry, credentials, or external configuration is introduced.

---

## Security and privacy

This PR introduces no transport surface and persists no user data.

Required properties:

- domain types validate their own important invariants;
- no dynamic rule execution;
- no `eval` or `exec`;
- no user-controlled imports;
- no SQL;
- no URL fetching;
- no arbitrary expression language;
- no logging of complete purchase inputs;
- reason codes contain no customer-identifying information;
- country evaluation must not infer location from IP or device information;
- malformed rules fail safely before evaluation.

The eligibility-rule domain must remain safe to call with untrusted facts that have already crossed the application input boundary.

---

## Configuration and deployment

None.

No new:

- environment variables;
- secrets;
- packages;
- Docker changes;
- Railway configuration;
- startup behaviour;
- worker processes;
- schedules;
- health/readiness changes.

---

## Observability and operations

No new telemetry is required.

The core rule evaluator is a pure function/domain operation and must not emit logs for every rule evaluation.

Future application-level `check_purchase` orchestration may record low-cardinality information such as:

```text
final result category
number of failed rules
number of unknown rules
promotion ID
```

but that is outside PR 10.

Do not log:

- full purchase input;
- raw model/SKU strings;
- arbitrary user-provided data;
- database information.

---

## Failure, consistency, and recovery

PR 10 has no persistence or side effects.

### Invalid rule definition

Examples:

- empty manufacturer set;
- empty product set;
- empty retailer set;
- empty purchase-channel set;
- date rule with no bounds;
- date start after date end;
- invalid price type;
- negative price bound;
- price with excessive fractional precision;
- minimum price greater than maximum;
- empty condition set;
- empty country set;
- malformed country code.

Required behaviour:

```text
fail construction deterministically
```

Do not defer malformed rule definitions into runtime `unknown`.

### Missing optional purchase fact

Examples:

```text
price rule exists + purchase_price=None
channel rule exists + purchase_channel=None
condition rule exists + condition=None
country rule exists + country_code=None
```

Required behaviour:

```text
RuleStatus.UNKNOWN
```

No side effect occurs.

### Known mismatching fact

Required behaviour:

```text
RuleStatus.NOT_SATISFIED
```

Do not throw an exception for an ordinary eligibility mismatch.

### Infrastructure failure

N/A.

The rule evaluator has no infrastructure dependency.

### Retry/recovery

N/A.

Evaluation is pure and safely repeatable.

---

## Acceptance criteria

### Behaviour

- [ ] Core deterministic rule types exist for manufacturer, product/model/SKU, retailer, purchase channel, purchase date, purchase price, product condition, and country.
- [ ] Model/SKU eligibility uses canonical `Product.id`, not raw model or SKU strings.
- [ ] Rule evaluation returns only `satisfied`, `not_satisfied`, or `unknown`.
- [ ] Rule results include stable machine-readable reason codes.
- [ ] Missing optional purchase information produces `unknown` only when a configured rule requires that fact.
- [ ] A missing rule means no restriction and does not produce `unknown`.
- [ ] Known mismatches produce `not_satisfied`.
- [ ] Date boundaries are inclusive.
- [ ] Price boundaries are inclusive.
- [ ] Price uses exact GBP `Decimal` semantics.
- [ ] Zero price remains distinct from missing price.
- [ ] Purchase-channel rules reuse `PurchaseChannel`.
- [ ] Condition uses an explicit canonical enum.
- [ ] Country matching uses canonical two-letter uppercase codes.
- [ ] All configured rules are evaluated; evaluation does not short-circuit.
- [ ] Rule result ordering is deterministic.
- [ ] The same facts and rules produce equivalent results repeatedly.
- [ ] No final eligibility classification is introduced.
- [ ] Existing PR 7–9 behaviour remains unchanged.

### Data and consistency

- [ ] No database schema changes are introduced.
- [ ] No existing promotion data is rewritten.
- [ ] No raw identity input is stored or compared by the rule engine.
- [ ] No generic executable rules representation is introduced.
- [ ] Domain rule definitions are immutable after successful construction.

### Security

- [ ] No dynamic expression execution exists.
- [ ] No external requests occur during evaluation.
- [ ] Malformed values are rejected deterministically.
- [ ] Missing information is not silently treated as a failed rule.
- [ ] No sensitive purchase payload is included in reason codes or logs.

### Operations

- [ ] No new infrastructure, configuration, or deployment dependency is introduced.
- [ ] No per-rule ad hoc logging is introduced.
- [ ] Existing health/readiness behaviour remains unchanged.

### Code quality

- [ ] Eligibility rules live in the domain layer.
- [ ] FastAPI, SQLAlchemy, sessions, configuration, and provider clients do not appear in the rule module.
- [ ] Existing `PurchaseChannel` is reused.
- [ ] Existing purchase date/price semantics are reused rather than redefined incompatibly.
- [ ] No unnecessary abstraction/framework/dependency is introduced.
- [ ] Ruff formatting/linting and targeted/broader tests pass.

---

## Tests to add or update

### Unit tests

Add focused domain coverage, likely:

```text
backend/tests/unit/test_eligibility_rules.py
```

Cover at minimum the following.

#### Contracts and immutability

- `RuleKind` stable values;
- `RuleStatus` stable values;
- `PurchaseCondition` stable values;
- rule values are immutable;
- purchase facts are immutable;
- rule evaluations are immutable;
- invalid UUID facts fail predictably;
- `datetime` is rejected as a purchase date;
- malformed country codes fail predictably.

#### Manufacturer

- exact manufacturer match;
- manufacturer mismatch;
- empty allowed manufacturer set rejected;
- non-UUID canonical values rejected.

#### Product / model / SKU

- exact canonical product match;
- product mismatch;
- multiple allowed products;
- empty product set rejected;
- no raw model/SKU comparison exists.

#### Retailer

- exact retailer match;
- retailer mismatch;
- multiple allowed retailers;
- empty retailer rule rejected.

#### Purchase channel

- online matches online;
- in-store matches in-store;
- allowed set containing both;
- known channel mismatch;
- missing purchase channel → `unknown`;
- empty channel rule rejected;
- unsupported strings are not coerced by the eligibility evaluator.

#### Purchase date

- exact start date included;
- exact end date included;
- one day before start fails;
- one day after end fails;
- start-only rule;
- end-only rule;
- both-null rule rejected;
- start after end rejected;
- leap-day boundary;
- no current-time dependency.

#### Purchase price

- exact minimum included;
- exact maximum included;
- below minimum fails;
- above maximum fails;
- minimum-only rule;
- maximum-only rule;
- zero amount;
- `None` → `unknown`;
- `Decimal("0")` remains known;
- negative bound rejected;
- `NaN` rejected;
- infinity rejected;
- `float` rejected;
- values with more than two fractional places rejected;
- no rounding occurs;
- minimum greater than maximum rejected;
- Decimal context precision does not alter semantics.

#### Condition

- `new` matches `new`;
- refurbished mismatch when new-only;
- multi-condition rule;
- missing condition → `unknown`;
- empty condition rule rejected.

#### Country

- `GB` matches `GB`;
- `IE` does not match GB-only;
- multiple allowed country codes;
- missing country → `unknown`;
- lowercase country code rejected rather than silently normalised;
- long/short/non-letter codes rejected;
- empty country rule rejected.

#### Aggregate evaluation

Cover:

```text
manufacturer
product
retailer
purchase channel
purchase date
purchase price
condition
country
```

with mixed:

```text
satisfied
not_satisfied
unknown
```

outcomes.

Assert:

- every configured rule is evaluated;
- evaluation does not stop on the first failure;
- output order is stable;
- two identical evaluations are value-equal;
- absent rules generate no results;
- no database/network/application objects are required.

### Existing regression tests

If shared date/price validation is refactored, update or preserve:

```text
backend/tests/unit/test_purchase_input.py
```

Existing PR 7–9 tests must continue to pass, especially:

```text
backend/tests/unit/test_identity_normalisation.py
backend/tests/unit/test_product_retailer_matching.py
backend/tests/unit/test_purchase_input.py
backend/tests/unit/test_promotion_candidate_matching.py
```

### PostgreSQL integration tests

N/A.

No persistence changes are expected.

Do not add PostgreSQL integration tests solely for pure rule evaluation.

### API/application tests

N/A.

No application orchestration or public contract changes.

### MCP contract tests

N/A.

MCP is unchanged.

### External-boundary tests

N/A.

No external dependency is introduced.

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

# Targeted eligibility-rule tests
uv run pytest tests/unit/test_eligibility_rules.py

# Closely related regression tests
uv run pytest \
  tests/unit/test_identity_normalisation.py \
  tests/unit/test_product_retailer_matching.py \
  tests/unit/test_purchase_input.py \
  tests/unit/test_promotion_candidate_matching.py

# Broader backend test suite
uv run pytest

# PostgreSQL integration tests
# N/A — PR 10 has no persistence change.

# API/MCP contract tests
# N/A — no transport changes.

# Migration verification
# N/A — no schema change is expected.
```

If test files are placed under different repository-conventional names, use the actual paths and report them.

If an expected command cannot run, document:

1. the command that should have run;
2. why it could not run;
3. what was verified instead;
4. the remaining risk.

Never weaken an existing PR 7–9 test merely to make PR 10 pass.

---

## Completion report

When implementation is complete, provide:

### Changed

Summarise:

- the core eligibility fact contract;
- typed eligibility rules added;
- rule-level status model;
- stable reason codes;
- deterministic aggregate evaluator;
- any shared purchase date/price validation refactor.

### Database and migrations

None.

If persistence changes become necessary, stop and explain why the PR must expand before implementing a generic rules-storage model.

### API/MCP contracts

None.

`CheckPurchaseRequest` must remain unchanged.

### Tests and verification

List:

- unit tests added/updated;
- regression tests run;
- exact verification commands;
- actual results.

Do not claim an unrun command passed.

### External configuration

None.

### Deviations

Describe any meaningful deviation from this specification and why it was necessary.

Use `None` when there were no deviations.

### Remaining risks or follow-up

Expected later work includes:

- composing rule outcomes into final purchase eligibility classifications;
- fixed and relative/delayed claim windows;
- promotion requirements;
- reward calculation;
- the canonical `check_purchase` eligibility service;
- persisted/authorable structured promotion rule data;
- REST/MCP transport surfaces;
- explainability/display mapping.

Do not implement those concerns as part of PR 10.

List only additional unresolved PR 10 issues beyond those deliberately deferred areas.

Use `None` when PR 10 itself is complete.