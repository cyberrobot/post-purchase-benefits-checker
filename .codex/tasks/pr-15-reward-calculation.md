# PR 15 — Reward Calculation

## Repository state

**Expected branch:**  
`pr15-reward-calculation`

**Base branch:**  
`main`

**Dependencies:**

- PR 5 — Benefit Model: merged; defines the common `Benefit` / `BenefitType` domain contract and explicitly leaves structured reward values to later work.
- PR 7 — Product & Retailer Normalisation: merged; canonical product identity is `Product.id`.
- PR 8 — Purchase Input Contract: merged; purchase price is an exact GBP `Decimal` with at most two fractional decimal places and no implicit rounding.
- PR 10 — Core Eligibility Rules: merged; `PurchaseEligibilityFacts.product_id` and optional `purchase_price` provide the canonical inputs later purchase-check flows can reuse.
- PR 14 — Promotion Requirements: merged; current Alembic head on the reviewed `main` branch is `0006_promotion_requirements`.
- Existing PostgreSQL, SQLAlchemy 2, Alembic, pytest, Ruff, and Testcontainers backend foundation.
- No new runtime package, external provider, worker, queue, cache, or infrastructure dependency.

### Read first

Before making changes, read:

- `AGENTS.md`
- nearest scoped `AGENTS.md` if one exists on the implementation branch
- `.codex/tasks/TEMPLATE.md`
- `.codex/tasks/pr-5-benefit-model.md`
- `.codex/tasks/pr-7-product-retailer-normalisation.md`
- `.codex/tasks/pr-8-purchase-input-contract.md`
- `.codex/tasks/pr-10-core-eligibility-rules.md`
- `.codex/tasks/pr-14-promotion-requirements.md`
- `backend/README.md`
- `backend/app/domain/benefits.py`
- `backend/app/domain/purchase_values.py`
- `backend/app/domain/eligibility_rules.py`
- `backend/app/db/models/core.py`
- `backend/migrations/versions/0002_core_promotion_schema.py`
- `backend/migrations/versions/0006_promotion_requirements.py`
- `backend/tests/unit/test_benefits.py`
- `backend/tests/unit/test_purchase_input.py`
- `backend/tests/unit/test_eligibility_rules.py`
- `backend/tests/integration/test_core_promotion_schema.py`
- `backend/tests/integration/test_postgres_migrations.py`
- `.github/workflows/backend.yml`

Do not create missing architecture documentation solely for this PR.

### Primary change area

Domain model plus additive persistence for deterministic monetary reward definitions.

PR 15 introduces explicit structured reward values for promotion benefits and a pure domain calculation path for:

- fixed GBP amounts;
- percentages of the qualifying purchase price;
- product-specific GBP amounts keyed by canonical `Product.id`.

The implementation must extend the existing `Benefit` model by composition rather than putting cashback-only fields into the common PR-5 `Benefit` value.

### Canonical implementation examples

Treat these as the preferred implementation references:

- `backend/app/domain/benefits.py`
  - string-backed classifications;
  - immutable domain values;
  - persistence-independent validation.
- `backend/app/domain/purchase_values.py`
  - exact `Decimal` handling;
  - no float coercion;
  - no silent rounding.
- `backend/app/domain/eligibility_rules.py::PurchaseEligibilityFacts`
  - canonical `Product.id`;
  - optional exact purchase price.
- `backend/app/db/models/core.py::Benefit`
  - owning persisted benefit.
- `backend/app/db/models/core.py::Product`
  - canonical product identity.
- `backend/app/db/models/core.py::PromotionVariantProduct`
  - existing promotion/product association.
- `backend/tests/integration/test_core_promotion_schema.py`
  - PostgreSQL graph, FK, constraint, metadata, cascade, and domain/persistence parity coverage.
- `backend/tests/integration/test_postgres_migrations.py`
  - migration upgrade/downgrade and data-preservation conventions.

Do not parse reward values out of `Benefit.name` or `Benefit.description`.

### Relevant symbols

Inspect at minimum:

- `app.domain.benefits.Benefit`
- `app.domain.benefits.BenefitType`
- `app.domain.purchase_values.validate_purchase_price`
- `app.domain.eligibility_rules.PurchaseEligibilityFacts`
- `app.db.models.Benefit`
- `app.db.models.Product`
- `app.db.models.PromotionVariant`
- `app.db.models.PromotionVariantProduct`
- `ck_benefits_type`
- current Alembic head
- current backend verification commands

### Expected change surface

Expected additions or updates include:

```text
.codex/tasks/pr-15-reward-calculation.md
backend/app/domain/rewards.py
backend/app/db/models/core.py
backend/migrations/versions/0007_reward_calculation.py
backend/tests/unit/test_rewards.py
backend/tests/integration/test_core_promotion_schema.py
backend/tests/integration/test_postgres_migrations.py
backend/README.md
```

The expected revision ID is conceptually:

```text
0007_reward_calculation
```

Codex must verify the actual Alembic head before creating the migration.

No REST route, MCP tool, purchase-check orchestrator, or promotion repository change is expected merely to introduce the structured reward model. If a canonical reward persistence mapping/read contract has appeared on the implementation branch, extend it instead of creating a parallel abstraction.

### Excluded areas

Do not implement as part of this PR:

- basket-total rewards;
- multi-item basket calculation;
- quantity-based rewards;
- threshold/tier rewards such as “£20 when spending £200”;
- conditional bonuses such as “extra £50 when registered within 7 days”;
- mutually exclusive or combinable reward-condition graphs;
- reward caps or floors;
- “up to” reward ranges;
- coupons, vouchers, points, store credit, or non-cash units;
- currency conversion or multi-currency rewards;
- free-gift monetary valuation;
- extended-warranty monetary valuation;
- warranty-duration calculation;
- tax/VAT apportionment;
- partial refunds, returns, or post-purchase price adjustments;
- claim payment/fulfilment;
- claimant bank/payment details;
- eligibility classification changes;
- promotion candidate matching changes;
- claim-window changes;
- publication completeness validation beyond invariants local to the new reward values;
- ingestion, scraping, or AI extraction;
- REST endpoints;
- MCP tools;
- frontend/UI;
- generic JSON rule payloads;
- arbitrary executable expressions;
- a generic rules DSL;
- native PostgreSQL enums.

Do not reserve persisted `basket` or `conditional` discriminator values before those behaviours exist. Future support must be an explicit typed extension with a migration and tests.

### Unknowns Codex must verify

Before implementation:

- Verify `main` still has no reward/rule/calculation model beyond display-only `Benefit`.
- Verify `Benefit` still contains only `benefit_type`, `name`, and optional `description`.
- Verify purchase-price semantics still use exact GBP `Decimal` values with at most two fractional digits.
- Verify canonical product identity remains `Product.id`.
- Verify the current Alembic head and migration naming sequence.
- Verify no scoped backend `AGENTS.md` has been added.
- Verify CI commands still match `.github/workflows/backend.yml`.
- Verify no existing Numeric/Decimal persistence convention has been introduced since this spec was created; if one exists, reuse it where it preserves the invariants below.

If repository state has changed, adapt to the established design rather than introducing a parallel reward system.

---

## Objective

Introduce deterministic, structured monetary reward definitions and calculation for the three reward shapes needed now:

1. **Fixed amount**
   - Example: `£100 cashback`.
   - Calculation result is the configured exact GBP amount.

2. **Percentage**
   - Example: `10% cashback`.
   - Calculation result is the configured percentage of the qualifying purchase price.

3. **Product specific**
   - Example:
     - Product A → `£100`
     - Product B → `£150`
   - Calculation uses the already-resolved canonical `Product.id`.

After this PR:

- reward values are explicit structured data and are never parsed from benefit display text;
- supported reward definitions have stable typed discriminators;
- monetary amounts use exact `Decimal` semantics;
- percentage calculation is deterministic and produces an exact GBP amount rounded to pence using the rule defined below;
- missing required calculation input fails explicitly rather than guessing;
- an unmapped product-specific reward fails explicitly rather than returning zero or another product's value;
- structured reward definitions can be persisted and round-tripped through PostgreSQL;
- existing promotion/benefit rows survive migration unchanged;
- basket and conditional rewards remain unsupported but can be added later as new typed reward definitions without redesigning the PR-5 `Benefit` model.

Completion does **not** mean reward values are exposed through `check_purchase`, REST, MCP, or frontend responses. Those integrations remain later work.

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

Reward definition and calculation belong in the domain layer.

The domain implementation must not import:

- FastAPI;
- SQLAlchemy;
- Alembic;
- database sessions;
- application configuration;
- HTTP clients;
- model/AI provider libraries.

Task-specific invariants:

1. Reward definitions are structured data, not display text.
2. `Benefit.name` and `Benefit.description` remain human-readable only.
3. The PR-5 `Benefit` shape must not gain cashback-only amount/percentage/product fields.
4. Initial reward discriminators are exactly:
   - `fixed_amount`
   - `percentage`
   - `product_specific`
5. Unknown reward discriminators fail explicitly.
6. Do not add an `OTHER` fallback.
7. Monetary reward amounts are GBP in this PR.
8. Monetary amounts use `Decimal`, never binary float.
9. Configured fixed/product-specific amounts are finite, strictly positive, and have at most two fractional decimal places.
10. A percentage is a finite `Decimal`, strictly greater than zero and no greater than 100, with at most four fractional decimal places.
11. Percentage calculation uses the qualifying purchase price exactly as represented by the existing purchase-price contract.
12. Percentage results are rounded to two decimal places using `ROUND_HALF_UP`.
13. Percentage calculation must not depend on ambient/global `decimal.Context` precision or rounding settings.
14. Product-specific values are keyed by canonical `Product.id` UUIDs, never raw model/SKU text.
15. A product-specific definition is non-empty and cannot contain the same product more than once.
16. Product-specific input order must not affect equality or calculation behaviour; freeze/canonicalise supplied mutable collections.
17. An unmapped product is a configuration/incomplete-definition error, not a zero-value reward.
18. A missing purchase price for a percentage reward is missing calculation input, not a zero-price assumption.
19. Direct reward calculation must be pure and deterministic.
20. No LLM call may decide or calculate a reward.
21. The persistence representation must not use arbitrary JSON or executable rule text.
22. Future basket/conditional support must be additive and typed; existing fixed/percentage/product-specific semantics must remain stable.
23. No existing benefit, eligibility, claim-window, provenance, lifecycle, or requirement semantics change in this PR.

### Canonical domain shape

The implementation should conceptually provide a string-backed discriminator such as:

```python
class RewardType(StrEnum):
    FIXED_AMOUNT = "fixed_amount"
    PERCENTAGE = "percentage"
    PRODUCT_SPECIFIC = "product_specific"
```

and immutable typed values equivalent in meaning to:

```python
@dataclass(frozen=True, slots=True)
class FixedAmountReward:
    amount: Decimal

@dataclass(frozen=True, slots=True)
class PercentageReward:
    percentage: Decimal

@dataclass(frozen=True, slots=True)
class ProductRewardValue:
    product_id: UUID
    amount: Decimal

@dataclass(frozen=True, slots=True)
class ProductSpecificReward:
    values: tuple[ProductRewardValue, ...]
```

Exact class names may follow existing repository conventions, but callers must not need untyped dictionaries to distinguish or evaluate the three supported forms.

A union/alias such as:

```python
RewardDefinition = FixedAmountReward | PercentageReward | ProductSpecificReward
```

is appropriate if it fits the implementation.

Each typed definition must expose or map unambiguously to its stable `RewardType`.

### Calculation input

The domain calculation entry point may use explicit keyword inputs or a small immutable input value. The semantics must be:

- fixed amount needs no purchase-price or product lookup to determine its value;
- percentage requires a known purchase price;
- product-specific calculation requires a canonical product ID.

Do not make reward calculation depend on the full `CheckPurchaseRequest` or transport schemas.

Reusing validated semantics from `PurchaseEligibilityFacts` is encouraged, but avoid coupling rewards to unrelated eligibility fields.

---

## API and contract changes

No REST, MCP, or externally visible HTTP contract changes.

This PR introduces internal domain and persistence contracts only.

### `RewardType`

Purpose:

Represent the stable reward-definition discriminator.

Stable values:

| Python member | Persisted value |
| --- | --- |
| `RewardType.FIXED_AMOUNT` | `fixed_amount` |
| `RewardType.PERCENTAGE` | `percentage` |
| `RewardType.PRODUCT_SPECIFIC` | `product_specific` |

Requirements:

- string-backed;
- case-sensitive;
- stable across domain/persistence boundaries;
- unknown strings rejected explicitly;
- no aliasing/fuzzy matching.

### Fixed-amount definition

Required information:

- `amount: Decimal`

Validation:

- exact GBP amount;
- finite;
- `> 0`;
- at most two fractional decimal places;
- no float coercion;
- no implicit quantisation/rounding on construction.

### Percentage definition

Required information:

- `percentage: Decimal`

Validation:

- finite;
- `> 0`;
- `<= 100`;
- at most four fractional decimal places;
- no float coercion;
- no implicit rounding on construction.

The percentage is represented in percentage points:

```text
10       means 10%
12.5     means 12.5%
0.25     means 0.25%
```

It is **not** represented as `0.10` for 10%.

### Product-specific definition

Required information:

- one or more `(product_id, amount)` pairs.

Validation:

- every `product_id` is a UUID;
- each amount follows fixed-amount monetary validation;
- product IDs are unique inside one definition;
- empty definitions fail;
- caller-provided mutable collections are copied/frozen;
- mapping order has no business meaning.

### Calculation result

The calculation result must expose the exact GBP amount as a `Decimal` with two fractional decimal places where percentage rounding is required.

A dedicated immutable result value is optional if it adds clarity, but do not introduce a transport DTO solely for this PR.

### Domain failures

Expected deterministic failures must be distinguishable from programmer/infrastructure failures.

At minimum distinguish:

- invalid reward configuration/value at construction;
- missing purchase price for percentage calculation;
- invalid calculation input type/value;
- no configured product-specific reward for the supplied canonical product.

Exact exception names may follow repository conventions.

Do not convert these failures into eligibility classifications in this PR.

---

## Domain and application behaviour

### Fixed amount

For:

```text
FixedAmountReward(amount=Decimal("100.00"))
```

the calculated reward is exactly:

```text
Decimal("100.00")
```

Purchase price must not change the value.

No cap, floor, threshold, or condition is applied.

### Percentage

For a configured percentage `p` and qualifying purchase price `x`:

```text
raw = x * p / 100
result = raw rounded to GBP pence using ROUND_HALF_UP
```

Examples:

```text
purchase £199.99, percentage 10%   -> £20.00
purchase £100.00, percentage 12.5% -> £12.50
purchase £0.10, percentage 5%      -> £0.01
purchase £0.00, percentage 10%     -> £0.00
```

The last example is valid because the purchase-price contract permits a known zero price; the reward definition itself must still have a positive percentage.

If purchase price is unknown (`None`), calculation fails explicitly.

Do not:

- treat missing price as zero;
- parse a price from text;
- round the purchase price first;
- use float arithmetic;
- use the process-global decimal rounding mode;
- silently clamp results.

### Product specific

Given a definition equivalent to:

```text
Product A UUID -> £100.00
Product B UUID -> £150.00
```

calculation for Product A returns exactly `£100.00`; Product B returns exactly `£150.00`.

If Product C is supplied and has no configured value, fail explicitly.

Do not:

- fall back to the first entry;
- use display names/model numbers/SKUs at calculation time;
- return zero;
- infer a nearest product;
- use AI/fuzzy matching.

Raw model/SKU resolution remains PR-7/application-layer work performed before reward calculation.

### Relationship to eligibility

Reward calculation and eligibility classification remain separate concerns.

This PR must not make a purchase eligible merely because a reward can be calculated.

Likewise, the reward calculator must not evaluate:

- manufacturer applicability;
- retailer applicability;
- date windows;
- condition;
- country;
- claim status;
- promotion lifecycle.

A future application flow may calculate a reward only after the relevant promotion variant has been resolved/evaluated.

### Relationship to benefit type

The current monetary use case is cashback.

Do not add monetary valuation semantics for:

- `extended_warranty`;
- `free_gift`.

Persisted reward definitions are owned by a specific `Benefit` so future application/publication code can associate structured reward data with the correct benefit.

This PR does not add a cross-table database trigger to prove that every reward-owning benefit is `cashback`. If the implementation introduces an application/domain mapper that combines a `Benefit` with its reward, it must reject semantically incompatible benefit/reward combinations rather than treating warranty/gift values as cashback.

Broader publication completeness/compatibility validation remains follow-up work.

### Extensibility for basket and conditional rewards

The design must leave a clear typed extension path.

A future basket reward should be able to add a new discriminator and typed configuration without:

- modifying the PR-5 common `Benefit` fields;
- parsing display text;
- replacing the existing reward tables;
- changing fixed/percentage/product-specific semantics.

A future conditional reward should similarly use explicit typed conditions/values rather than arbitrary executable expressions or JSON blobs.

Expected future evolution is approximately:

1. add a new domain reward classification;
2. add a typed domain value/calculator;
3. migrate the database constraint and any required typed columns/tables;
4. add validation/publication rules;
5. add unit and PostgreSQL tests.

Do not implement those future types now.

---

## Persistence, transactions, and migrations

PR 15 requires an additive schema change because the existing `benefits` table contains only:

- benefit classification;
- display name;
- optional description;
- ownership/timestamps.

Do not add reward-specific columns directly to the common `benefits` table unless repository state has changed and a clearly superior established pattern now exists. The preferred reviewed design is composition.

### Preferred persisted shape

Introduce an owned one-to-zero/one reward definition for a benefit, conceptually:

```text
benefit_rewards
- benefit_id        PK, FK -> benefits.id ON DELETE CASCADE
- reward_type       varchar(32), NOT NULL
- fixed_amount      numeric, nullable
- percentage        numeric, nullable
```

with a discriminator constraint supporting exactly:

```text
fixed_amount
percentage
product_specific
```

and a shape constraint equivalent to:

```text
fixed_amount:
  fixed_amount IS NOT NULL
  percentage IS NULL

percentage:
  fixed_amount IS NULL
  percentage IS NOT NULL

product_specific:
  fixed_amount IS NULL
  percentage IS NULL
```

For product-specific values introduce an owned table conceptually:

```text
benefit_product_reward_values
- benefit_id   FK -> benefit_rewards.benefit_id ON DELETE CASCADE
- product_id   FK -> products.id ON DELETE RESTRICT
- amount       numeric, NOT NULL
- PK (benefit_id, product_id)
```

Add an index on `product_id` if required for the FK/delete access pattern, consistent with existing schema conventions.

Exact SQLAlchemy class names may follow repository naming conventions.

### Numeric storage

Do not use `FLOAT`, `REAL`, Python float, or another binary floating-point representation.

Database storage must preserve the same exactness rules as the domain and must not silently round over-precision input.

A PostgreSQL `NUMERIC(p, s)` column can round values to its declared scale before a later check sees them, so Codex must not rely on scale declaration alone if that would silently turn invalid input such as `12.345` into `12.35`.

Use PostgreSQL Numeric/Decimal storage plus constraints that make these invariants observable:

- fixed/product-specific amounts are finite;
- amounts are `> 0`;
- amounts have at most two fractional decimal places;
- percentages are finite;
- percentages are `> 0` and `<= 100`;
- percentages have at most four fractional decimal places.

The exact PostgreSQL expression may follow a proven repository/tested approach, but direct SQL must not be able to bypass these value invariants merely because ORM validation was skipped.

### One reward per benefit

A benefit may own at most one reward definition.

Using `benefit_id` as the `benefit_rewards` primary key is preferred and naturally enforces this.

A benefit may also have no structured reward definition; existing benefit rows must remain valid after migration.

### Product-specific rows

The database must guarantee:

- referenced benefit reward exists;
- referenced product exists;
- duplicate `(benefit_id, product_id)` rows are impossible;
- product deletion is restricted while a reward references it;
- deleting the owning benefit cascades through its reward and product-specific values.

The database does not need a trigger that proves a product-specific reward entry is also present in the owning promotion variant's `promotion_variant_products` set.

That cross-table completeness invariant belongs to future publication validation. The domain calculation itself only operates on explicit configured canonical product IDs and must fail on a missing mapping.

### Migration

Expected migration:

```text
0007_reward_calculation
down_revision = 0006_promotion_requirements
```

Codex must verify the real head before implementation.

Upgrade must:

- create the new reward tables/constraints/indexes;
- preserve all existing manufacturers, products, promotions, variants, benefits, requirements, sources, and associations unchanged;
- require no backfill;
- leave existing benefits with no structured reward definition.

Do not rewrite earlier migration files.

### Safe downgrade

Dropping the new reward tables would destroy structured reward data.

Therefore:

- downgrade is allowed when the PR-15 reward tables contain no reward definitions;
- if reward data exists, downgrade must fail explicitly before dropping data;
- a failed downgrade must leave:
  - the Alembic revision unchanged;
  - the reward tables present;
  - reward rows intact;
  - constraints intact and usable.

After an empty successful downgrade to `0006_promotion_requirements`, re-upgrade to head must succeed.

### Transactions

No new public write use case is introduced.

Existing caller-owned SQLAlchemy transaction conventions remain unchanged.

When tests or future callers create a product-specific reward, the base reward definition and its product-value rows should be written atomically in one transaction.

No transaction may remain open across network/model calls because this PR introduces none.

---

## External services and network access

None.

No manufacturer site, AI provider, payment service, queue, Redis instance, or other network dependency is introduced.

---

## Security and privacy

No new authentication or personal-data boundary is introduced.

Requirements:

- reward values are passive structured data;
- never evaluate arbitrary expressions;
- never use `eval`, `exec`, dynamic imports, or user-controlled code;
- do not introduce generic JSON solely to avoid typed reward models;
- reject invalid/unsupported discriminators explicitly;
- direct database constraints must protect critical numeric invariants where practical;
- do not log claimant payment information because none is introduced;
- no secrets or credentials are added.

Future AI-assisted extraction may propose reward candidates, but candidate values remain untrusted and must pass domain/publication validation before runtime use. PR 15 does not add that extraction path.

---

## Configuration and deployment

None.

### Environment variables

None.

### Runtime/deployment changes

None.

No Docker, Railway, worker, process, health-check, startup, or shutdown changes are expected.

A schema migration must be applied before application code that expects the new reward tables is deployed.

---

## Observability and operations

No new production telemetry is required.

Reward calculation is a pure deterministic domain operation and must not emit logs itself.

If a later application use case catches expected reward-domain failures, that boundary may log a safe reason/category using the existing telemetry stack.

Do not log raw claimant financial/payment details; none are needed for this calculation.

Health/readiness behaviour remains unchanged.

---

## Failure, consistency, and recovery

### Invalid reward definition

Construction with:

- unsupported reward type;
- float monetary values;
- non-finite Decimal values;
- zero/negative configured amounts;
- amount precision beyond two fractional places;
- zero/negative percentage;
- percentage over 100;
- percentage precision beyond four fractional places;
- invalid product UUID;
- duplicate product mapping;
- empty product-specific mapping;

must fail deterministically.

No partial mutable domain object should remain.

### Missing purchase price

Percentage calculation with `purchase_price=None` fails explicitly.

It must not:

- return zero;
- return the uncalculated percentage;
- invent a price;
- read another field.

Retrying with a valid purchase price is safe.

### Invalid purchase price

If percentage calculation receives a purchase price that violates the established PR-8 semantics, fail through the established validation semantics.

Do not coerce or round it.

### Missing product-specific value

If the canonical product ID has no configured product-specific amount, fail explicitly as incomplete/invalid reward configuration for that product.

Do not return another product's value.

### Persistence constraint failure

Database constraint/FK/uniqueness failures must roll back according to the caller's transaction boundary.

A failed insert must not create a partially usable reward graph.

### Migration failure

Migration DDL must remain transactional under the repository's PostgreSQL/Alembic conventions.

A failed upgrade must not report the new revision as applied.

A downgrade refused because reward data exists must leave the PR-15 schema/data intact.

---

## Acceptance criteria

### Behaviour

- [ ] `RewardType` defines exactly `fixed_amount`, `percentage`, and `product_specific`.
- [ ] Fixed-amount rewards calculate to the exact configured GBP amount.
- [ ] Percentage rewards calculate deterministically from exact purchase price.
- [ ] Percentage results use `ROUND_HALF_UP` to GBP pence.
- [ ] Percentage calculation is independent of ambient Decimal context settings.
- [ ] Missing purchase price fails explicitly.
- [ ] Product-specific rewards are keyed by canonical `Product.id`.
- [ ] Product-specific calculation returns the exact configured amount for the supplied product.
- [ ] Missing product mapping fails explicitly.
- [ ] Display `Benefit.name` / `description` are never parsed for reward values.
- [ ] Existing eligibility, lifecycle, claim-window, requirement, matching, and provenance behaviour remains unchanged.
- [ ] Basket and conditional rewards are not implemented or accepted as supported persisted discriminator values.

### Data and consistency

- [ ] Existing `benefits` rows remain valid and unchanged after migration.
- [ ] A benefit may have zero or one structured reward definition.
- [ ] Reward definitions use exact PostgreSQL Numeric/Decimal storage, not floating point.
- [ ] Database constraints reject unsupported reward types.
- [ ] Database constraints reject invalid fixed/percentage field combinations.
- [ ] Database constraints reject non-positive configured monetary amounts.
- [ ] Database constraints reject configured monetary amounts with more than two fractional decimal places without silently rounding them into validity.
- [ ] Database constraints reject percentage values outside `(0, 100]`.
- [ ] Database constraints reject percentages with more than four fractional decimal places without silently rounding them into validity.
- [ ] Product-specific values reference existing canonical products.
- [ ] Duplicate product entries for one reward are rejected.
- [ ] Deleting a benefit cascades to its owned reward data.
- [ ] Deleting a product referenced by product-specific reward data is restricted.
- [ ] Migration upgrade succeeds on real PostgreSQL.
- [ ] Empty downgrade succeeds and re-upgrade succeeds.
- [ ] Downgrade with reward data refuses destructive data loss and leaves the schema/data/revision intact.
- [ ] SQLAlchemy metadata and migrated PostgreSQL schema remain aligned.

### Security

- [ ] No executable rule language or arbitrary evaluation is introduced.
- [ ] Invalid/untrusted numeric values are validated.
- [ ] No secrets, claimant payment details, or unnecessary PII are introduced.
- [ ] No network boundary is introduced.

### Operations

- [ ] No new environment configuration is required.
- [ ] Existing health/readiness behaviour remains unchanged.
- [ ] No new external services are required.

### Code quality

- [ ] Domain reward code has no FastAPI, SQLAlchemy, Alembic, network, or AI dependency.
- [ ] The PR-5 common `Benefit` value is not polluted with reward-type-specific fields.
- [ ] Existing architecture/dependency direction is preserved.
- [ ] No generic rules engine or unrelated refactor is introduced.
- [ ] No unnecessary third-party dependency is added.
- [ ] Ruff formatting/linting passes.
- [ ] Targeted unit tests pass.
- [ ] PostgreSQL integration/migration tests pass.
- [ ] Full backend pytest suite passes.

---

## Tests to add or update

### Unit tests

Add:

```text
backend/tests/unit/test_rewards.py
```

Cover at minimum:

1. stable `RewardType` names/values;
2. enum/string conversion;
3. unsupported/case-mismatched reward types;
4. fixed amount:
   - valid integer/two-decimal Decimal values;
   - exact return value;
   - float rejection;
   - `NaN`, infinities, zero, negative, and >2-decimal rejection;
5. percentage:
   - valid integer/fractional percentage points;
   - exact calculation;
   - `0 < percentage <= 100`;
   - >4-decimal rejection;
   - float rejection;
   - `NaN`/infinity rejection;
6. percentage rounding:
   - values below/above half-penny boundaries;
   - exact half-penny uses `ROUND_HALF_UP`;
   - examples such as `10% of £199.99 == £20.00`;
7. calculation remains identical after changing ambient Decimal precision/rounding mode;
8. missing purchase price;
9. invalid purchase-price type/value follows existing validation semantics;
10. zero purchase price remains known input and can calculate a zero result;
11. product-specific:
    - multiple canonical UUID values;
    - exact product lookup;
    - input-order independence;
    - duplicate product rejection;
    - empty mapping rejection;
    - invalid product ID rejection;
    - invalid amount rejection;
    - unmapped product failure;
12. immutable/frozen behaviour;
13. no accidental mutable instance dictionary where current domain-value convention uses `slots=True`;
14. no parsing of `Benefit.name` or `description`.

### PostgreSQL integration tests

Update:

```text
backend/tests/integration/test_core_promotion_schema.py
```

Cover:

- fixed reward round-trip;
- percentage reward round-trip;
- product-specific reward round-trip;
- exact Decimal values survive persistence/reload;
- one reward per benefit;
- supported reward-type constraint;
- type-specific field-shape constraint;
- positive amount constraint;
- amount fractional-place constraint without silent rounding;
- percentage range/precision constraints;
- product FK;
- duplicate `(benefit_id, product_id)` rejection;
- benefit delete cascades reward and product-value rows;
- referenced product delete is restricted;
- metadata/migrated schema parity remains clean.

Use direct SQL/SQLAlchemy Core where useful to prove database constraints independently from domain constructors.

Do not replace PostgreSQL behaviour with SQLite tests.

### Migration tests

Update:

```text
backend/tests/integration/test_postgres_migrations.py
```

Cover:

- current head is the new PR-15 revision;
- downgrade to `0006_promotion_requirements`;
- pre-existing benefit/promotion graph remains unchanged;
- upgrade creates empty reward tables without backfill;
- all canonical reward types can be persisted after upgrade;
- unsupported types/invalid values remain rejected;
- SQLAlchemy metadata matches the upgraded schema;
- downgrade succeeds when reward tables are empty;
- re-upgrade succeeds;
- downgrade fails when reward data exists;
- failed downgrade preserves revision, tables, constraints, and rows;
- database remains usable after the refused downgrade.

### API/application tests

N/A.

No public transport or application orchestration contract changes.

### MCP contract tests

N/A.

### External-boundary tests

N/A.

No external boundary is introduced.

---

## Verification commands

Run from `backend/`.

Codex must verify these commands still match repository configuration before claiming completion.

### Install/sync dependencies

```bash
uv sync --locked --extra dev
```

### Formatting

```bash
uv run ruff format --check .
```

### Lint

```bash
uv run ruff check .
```

### Type checking

```text
N/A on the reviewed repository state.
```

No backend type-check command is currently configured.

Codex must verify this has not changed.

### Targeted unit tests

```bash
uv run pytest tests/unit/test_rewards.py
```

### Relevant persistence tests

```bash
uv run pytest tests/integration/test_core_promotion_schema.py
```

### Migration/PostgreSQL tests

```bash
uv run pytest tests/integration/test_postgres_migrations.py
```

### Combined targeted verification

```bash
uv run pytest \
  tests/unit/test_rewards.py \
  tests/integration/test_core_promotion_schema.py \
  tests/integration/test_postgres_migrations.py
```

### Broader backend suite

```bash
uv run pytest
```

### Manual migration verification where a development PostgreSQL database is available

```bash
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head
```

The downgrade command is expected to refuse when PR-15 reward data exists; test the empty and populated cases deliberately rather than treating the safe refusal as a migration defect.

Do not claim commands passed unless they were actually run.

If Docker/PostgreSQL is unavailable, report:

1. the command that could not run;
2. why;
3. what was verified instead;
4. the remaining migration risk.

Never weaken or delete a failing constraint/migration test merely to make verification green unless the specification itself is demonstrably wrong; document any such deviation.

---

## Completion report

When implementation is complete, provide:

### Changed

Summarise:

- reward domain classifications;
- fixed/percentage/product-specific typed values;
- deterministic calculation behaviour;
- percentage rounding semantics;
- persistence tables/relationships/constraints;
- documentation changes.

### Database and migrations

State:

- migration revision;
- tables/constraints/indexes added;
- existing-data preservation;
- empty downgrade behaviour;
- populated safe-downgrade refusal.

### API/MCP contracts

```text
None.
```

### Tests and verification

List:

- unit tests added;
- PostgreSQL integration tests updated;
- migration tests updated;
- exact commands run;
- results.

Do not claim unrun verification passed.

### External configuration

```text
None.
```

### Deviations

Describe any meaningful departure from this specification and why it was required.

Use:

```text
None.
```

when there were no deviations.

### Remaining risks or follow-up

Potential future work is explicitly outside PR 15 and may include:

- exposing calculated rewards in purchase-check/application results;
- publication validation that a cashback benefit has a compatible complete reward definition;
- validating product-specific reward coverage against all applicable variant products;
- basket/threshold/tier reward definitions;
- conditional bonus rules;
- caps/floors;
- multi-currency rewards;
- voucher/points/store-credit units;
- ingestion/extraction of structured reward values;
- claim payment/fulfilment.

Do not implement these merely because PR 15 creates the extension point.
