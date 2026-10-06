# PR 7 — Product & Retailer Normalisation

## Repository state

**Expected branch:**  
`pr7-product-retailer-normalisation`

**Base branch:**  
`main`

**Dependencies:**

- PR 3 — Core Promotion Schema: merged.
- PR 4 — Promotion Lifecycle & History: merged.
- PR 5 — Benefit Model: merged.
- PR 6 — Promotion Source Provenance: merged.
- Existing PostgreSQL, SQLAlchemy 2, Alembic, pytest/Testcontainers, and application/repository boundaries.
- No new external provider, AI service, search engine, queue, worker, or infrastructure dependency.

### Read first

Before making changes, read:

- `AGENTS.md`
- `.codex/tasks/TEMPLATE.md`
- `.codex/tasks/pr-3-core-promotion-schema.md`
- `.codex/tasks/pr-4-promotion-lifecycle-history.md`
- `.codex/tasks/pr-5-benefit-model.md`
- `.codex/tasks/pr-6-promotion-source-provenance.md`
- `backend/README.md`
- `backend/app/db/models/core.py`
- `backend/app/application/promotions.py`
- `backend/app/db/repositories/promotions.py`
- `backend/migrations/versions/0002_core_promotion_schema.py`
- `backend/tests/integration/test_core_promotion_schema.py`
- `backend/tests/conftest.py`
- `backend/pyproject.toml`

If a more narrowly scoped `AGENTS.md` exists on the implementation branch, read and follow it.

### Primary change area

Domain normalisation and deterministic canonical identity matching, backed by PostgreSQL reference data.

This PR introduces canonical matching for:

- manufacturer;
- product model/model alias;
- retailer-specific SKU;
- retailer;
- retailer group;
- purchase channel.

It does **not** determine promotion eligibility.

### Canonical implementation examples

Treat these as the preferred implementation references:

- `backend/app/domain/benefits.py`
  - immutable domain values;
  - stable enum values;
  - validation independent of persistence.
- `backend/app/domain/promotion_provenance.py`
  - deterministic domain validation;
  - explicit failure states;
  - no SQLAlchemy, FastAPI, network, or AI dependencies.
- `backend/app/application/promotions.py`
  - application-owned contracts and repository protocols.
- `backend/app/db/repositories/promotions.py`
  - SQLAlchemy-to-application mapping;
  - safe persistence error handling.
- `backend/app/db/models/core.py`
  - UUID identities;
  - timestamps;
  - relationships;
  - PostgreSQL constraints.
- `backend/tests/integration/test_core_promotion_schema.py`
  - real PostgreSQL constraints;
  - referential integrity;
  - migration/ORM parity.

There is currently no generic normalisation or identity-matching framework that must be preserved.

Do not introduce one solely for architectural abstraction.

### Relevant symbols

Inspect at minimum:

- `Manufacturer`
- `Product`
- `Product.model_number`
- `Retailer`
- `Promotion`
- `PromotionVariant`
- `PromotionVariantProduct`
- `Base`
- current Alembic head
- PostgreSQL Testcontainers fixtures
- migration/ORM metadata parity tests

### Expected change surface

Expected changes include:

```text
backend/app/domain/
backend/app/application/
backend/app/db/models/
backend/app/db/repositories/
backend/migrations/versions/
backend/tests/unit/
backend/tests/integration/
```

Likely additions include:

- deterministic text/identifier normalisation;
- match result types;
- purchase-channel canonicalisation;
- manufacturer aliases;
- product-model aliases;
- retailer aliases;
- retailer-specific product SKUs;
- retailer groups;
- retailer-group aliases where group-name matching requires them;
- retailer/group membership;
- repository queries supporting canonical resolution;
- one new Alembic migration.

The exact file split should follow the existing repository structure.

### Excluded areas

Do not implement:

- purchase-check REST endpoints;
- MCP tools;
- promotion candidate selection;
- eligibility evaluation;
- purchase-date evaluation;
- claim-window rules;
- price/currency rules;
- promotion retailer/product applicability evaluation;
- receipt/image parsing;
- retailer or manufacturer scraping;
- product catalogue retrieval;
- source retrieval;
- AI/LLM matching;
- semantic/vector search;
- fuzzy matching;
- phonetic matching;
- automatic alias discovery;
- frontend behaviour;
- customer purchase persistence;
- background jobs;
- scheduled normalisation/reconciliation;
- product or retailer administration UI.

### Unknowns Codex must verify

Before implementation verify:

- current Alembic head;
- whether a scoped backend `AGENTS.md` has appeared;
- whether any product/retailer application repository has since been introduced;
- whether `Product.model_number` semantics changed after this specification;
- whether a retailer-group concept already exists;
- whether a purchase-channel vocabulary already exists;
- current database error-wrapping conventions;
- current migration verification commands.

Do not create parallel abstractions when the implementation branch already contains an equivalent concept.

---

## Objective

After PR 7, the backend must be able to resolve commonly supplied purchase identity values to canonical persisted entities deterministically.

The matching layer must support:

```text
manufacturer input
        ↓
canonical Manufacturer

model or retailer SKU
        ↓
canonical Product

retailer input
        ↓
canonical Retailer

retailer-group input
        ↓
canonical RetailerGroup

purchase-channel input
        ↓
canonical PurchaseChannel
```

Matching must explicitly distinguish:

```text
matched
not_found
ambiguous
```

A successful match returns canonical identity.

An ambiguous value must remain ambiguous.

The system must never silently choose:

- the first database row;
- the oldest/newest record;
- the closest spelling;
- the most popular entity;
- a fuzzy match;
- an LLM-generated guess.

This PR establishes reusable identity resolution only.

It must not conclude that a canonical purchase is eligible for any promotion.

---

## Architecture and invariants

Preserve the established dependency direction:

```text
transport
    ↓
application
    ↓
domain
    ↓
application-owned ports
    ↓
SQLAlchemy/PostgreSQL adapters
```

### Canonical entity identity

Canonical persisted identities are:

```text
Manufacturer.id
Product.id
Retailer.id
RetailerGroup.id
```

User-supplied strings are matching inputs, not identity.

Aliases must point to canonical entities rather than creating parallel copies of those entities.

A retailer SKU maps to a canonical product.

### Deterministic matching

For identical:

- input;
- persisted reference data;
- application version;

matching must produce an equivalent result.

Matching must not depend on:

- LLM calls;
- external HTTP requests;
- embeddings;
- vector similarity;
- search-engine ranking;
- approximate string-distance thresholds;
- database row order.

### Ambiguity is valid information

Multiple distinct canonical candidates mean:

```text
ambiguous
```

They do not mean:

```text
take the first candidate
```

Ambiguity must remain distinguishable from:

```text
not_found
invalid input
infrastructure failure
```

### Context scopes identifiers

Product model matching is manufacturer-scoped.

Retailer SKU matching is retailer-scoped.

Do not assume:

```text
model_number is globally unique
```

The existing schema explicitly permits model-number reuse.

Do not assume:

```text
SKU is globally unique
```

The same SKU text may legitimately be used by multiple retailers.

### Identity is not eligibility

Canonicalisation must remain separate from eligibility.

For example:

```text
Samsung
+ QE55S95D
+ Currys
+ online
```

resolving successfully does not establish that:

- a promotion exists;
- Currys participates;
- the model qualifies;
- online purchases qualify;
- the purchase date qualifies.

Those checks belong to later PRs.

### Historical promotion data

Adding or modifying aliases, SKUs, retailer groups, or matching data must not:

- change promotion lifecycle state;
- rewrite historical promotions;
- rewrite promotion provenance;
- duplicate products or retailers.

---

## API and contract changes

No public REST or MCP contract changes.

An internal application/domain matching contract may be introduced.

Prefer a result model conceptually equivalent to:

```python
MatchStatus:
    MATCHED
    NOT_FOUND
    AMBIGUOUS
```

and:

```python
MatchResult:
    status
    canonical_id
    candidate_ids
```

Exact names may follow repository conventions.

Requirements:

- `MATCHED` has exactly one canonical identity.
- `NOT_FOUND` has no canonical identity.
- `AMBIGUOUS` has two or more distinct candidates.
- candidate ordering is deterministic.
- infrastructure failures do not become `NOT_FOUND`.
- invalid input does not silently become `NOT_FOUND`.
- SQLAlchemy models must not cross the application boundary.

---

## Domain and application behaviour

### Human-readable text normalisation

Introduce one deterministic normalisation function for manufacturer, retailer, retailer-group, and similar human-readable aliases.

At minimum:

1. Input must be a string.
2. Apply Unicode NFKC normalisation.
3. Trim leading/trailing whitespace.
4. Apply Unicode case folding.
5. Collapse consecutive internal whitespace to one ASCII space.
6. Reject an empty result.

Examples:

```text
"  Example   Retailer " -> "example retailer"
"EXAMPLE RETAILER"      -> "example retailer"
```

Do not broadly discard punctuation.

For example these must not automatically become equivalent:

```text
A+B
AB
A-B
```

Such equivalence requires an explicit alias.

### Identifier normalisation

Model numbers and SKUs need a conservative identifier normaliser.

At minimum:

1. Input must be a string.
2. Apply Unicode NFKC normalisation.
3. Trim leading/trailing whitespace.
4. Case-fold.
5. Remove whitespace within the identifier.
6. Reject an empty result.

Preserve punctuation.

Examples:

```text
" QE55 S95D " -> "qe55s95d"
"AB-123"      -> "ab-123"
"AB123"       -> "ab123"
```

Do not automatically make:

```text
AB-123 == AB123
```

An explicit model alias may express that relationship when required.

### Manufacturer matching

Manufacturer matching must consider:

- canonical manufacturer slug;
- canonical manufacturer name;
- curated manufacturer aliases.

After normalisation:

```text
0 distinct manufacturer IDs
-> NOT_FOUND

1 distinct manufacturer ID
-> MATCHED

2+ distinct manufacturer IDs
-> AMBIGUOUS
```

Do not automatically create aliases from failed runtime lookups.

### Retailer matching

Retailer matching follows the same semantics:

- canonical slug;
- canonical name;
- curated aliases.

Do not infer retailers from:

- URLs;
- payment descriptors;
- receipt OCR;
- email domains;
- retailer groups;
- external search.

Those belong to future input/ingestion work.

### Product model matching

Model matching requires canonical manufacturer context.

Within that manufacturer, candidates may come from:

- `Product.model_number`;
- curated product-model aliases.

Use identifier normalisation.

The existing:

```text
Product.model_number
```

must remain available and must remain non-globally-unique.

Do not add a global model-number uniqueness constraint.

If two products belonging to the same manufacturer resolve from the same model input:

```text
AMBIGUOUS
```

### Retailer SKU matching

Introduce retailer-specific product SKU mappings.

A mapping represents:

```text
Retailer
+ retailer SKU
-> Product
```

Matching requires canonical retailer context.

Use identifier normalisation.

Do not treat SKU as globally unique.

When manufacturer context is supplied, a SKU candidate that belongs to another manufacturer must not be accepted as the purchase product.

### Combined model/SKU input

A caller may have one field representing:

```text
model or SKU
```

The matching layer must support combining exact deterministic candidates from:

```text
manufacturer-scoped model/model alias
retailer-scoped SKU
```

Deduplicate by canonical `Product.id`.

Then:

```text
0 product IDs -> NOT_FOUND
1 product ID  -> MATCHED
2+ product IDs -> AMBIGUOUS
```

Important conflict case:

```text
model -> Product A
SKU   -> Product B
```

must return:

```text
AMBIGUOUS
```

Do not implicitly prefer one identifier source over the other.

### Retailer groups

Introduce canonical retailer groups.

A retailer group has at minimum:

```text
id
name
slug
created_at
updated_at
```

Use the same canonical identity and slug conventions as manufacturers and retailers.

Support deterministic matching by:

- canonical slug;
- canonical name;
- curated alias where aliases are required.

Group match results follow:

```text
MATCHED
NOT_FOUND
AMBIGUOUS
```

### Retailer-group membership

Represent group membership explicitly.

A retailer may belong to:

```text
zero
one
multiple
```

retailer groups.

Do not implement the relationship as a single:

```text
retailers.retailer_group_id
```

column.

Use an explicit association table.

PR 7 does not define historical/effective-date group membership.

Therefore later eligibility logic must not assume present-day group membership accurately represents a historical purchase until temporal semantics are explicitly introduced.

### Purchase channel

Introduce a small domain-owned `PurchaseChannel` classification.

Initial canonical values:

```text
online
in_store
```

At minimum support deterministic aliases:

```text
online:
- online
- web
- website

in_store:
- in_store
- in-store
- instore
- store
- shop
```

Alias input uses the human-readable text normaliser.

Unsupported channel text must not silently map to:

```text
other
```

It remains unsupported/not found.

Do not introduce speculative channel classifications merely to make the enum appear complete.

The enum must remain straightforward to extend when real promotion data requires additional channels.

### Curated aliases

Aliases are curated reference data.

Runtime matching must never mutate alias data.

Do not "learn" aliases from user input automatically.

Adding the identical alias for the same canonical entity must either:

- be idempotent through the owning write operation; or
- fail predictably through a uniqueness constraint.

Alias collisions across different canonical entities may exist.

When they do, resolution must return:

```text
AMBIGUOUS
```

rather than forbidding the data purely so lookup always returns one row.

---

## Persistence, transactions, and migrations

Persistence changes are required.

Create a new Alembic revision after the current migration head.

Do not rewrite:

```text
0002_core_promotion_schema.py
```

### Existing canonical entities

Retain:

```text
manufacturers
products
retailers
```

as canonical identity tables.

Retain:

```text
products.model_number
```

No existing canonical product/manufacturer/retailer row should require recreation.

### Manufacturer aliases

Add a table equivalent to:

```text
manufacturer_aliases
```

Fields conceptually include:

```text
manufacturer_id
alias
normalised_alias
```

Requirements:

- manufacturer FK is not null;
- alias is bounded and non-empty;
- normalised alias is bounded and non-empty;
- duplicate `(manufacturer_id, normalised_alias)` is rejected;
- lookup by `normalised_alias` is indexed;
- deletion of an otherwise deletable manufacturer may remove its owned aliases;
- aliases cannot survive without their manufacturer.

Do not make `normalised_alias` globally unique because ambiguity must remain representable.

### Retailer aliases

Add:

```text
retailer_aliases
```

with equivalent semantics:

```text
retailer_id
alias
normalised_alias
```

Require:

- referential integrity;
- per-retailer duplicate protection;
- normalised lookup index.

### Product model aliases

Add:

```text
product_model_aliases
```

Fields conceptually include:

```text
product_id
alias
normalised_alias
```

Use identifier normalisation.

Require:

- product FK;
- bounded non-empty values;
- uniqueness of `(product_id, normalised_alias)`;
- lookup index.

Do not make a model alias globally unique.

Do not replace or remove `products.model_number`.

### Retailer product SKUs

Add:

```text
retailer_product_skus
```

Fields conceptually include:

```text
retailer_id
product_id
sku
normalised_sku
```

Require:

- valid retailer FK;
- valid product FK;
- bounded non-empty SKU;
- bounded non-empty normalised SKU;
- index on `(retailer_id, normalised_sku)`;
- duplicate identical retailer/product/SKU mappings rejected.

Do not impose:

```text
UNIQUE(retailer_id, normalised_sku)
```

if that would make a genuinely ambiguous persisted mapping impossible to detect.

A single retailer/SKU resolving to multiple products must be representable as an integrity/data-quality problem surfaced as:

```text
AMBIGUOUS
```

by the matching layer.

### Retailer groups

Add:

```text
retailer_groups
```

following existing reference-entity conventions.

Fields:

```text
id
name
slug
created_at
updated_at
```

Require:

- UUID primary key;
- non-empty name;
- valid canonical slug;
- unique slug;
- timezone-aware timestamps consistent with existing mappings.

### Retailer-group aliases

If raw retailer-group names are part of the resolver contract, add:

```text
retailer_group_aliases
```

equivalent to manufacturer/retailer aliases.

If inspection during implementation shows group aliases have no consumer and canonical name/slug matching is sufficient for this PR, omit the table and document the decision.

Do not add unused infrastructure merely for symmetry.

### Retailer-group membership

Add an explicit association such as:

```text
retailer_group_members
```

with:

```text
retailer_group_id
retailer_id
```

Require:

- composite primary key or equivalent uniqueness;
- duplicate membership rejection;
- valid FKs;
- index supporting lookup by retailer;
- no orphan memberships.

Deleting association rows must not delete canonical retailers or groups.

### Normalised canonical fields

Do not add redundant `normalised_name` columns to every existing canonical table unless the implementation demonstrates they are required for a correct indexed lookup.

For the expected small reference sets, repository code may:

- perform scoped database retrieval;
- normalise canonical persisted names in Python;
- combine those candidates with indexed alias-table candidates.

Do not prematurely denormalise every display field.

If implementation chooses persisted normalised keys for demonstrated query reasons, document:

- backfill semantics;
- Unicode normalisation behaviour;
- database/application consistency enforcement.

### Transactions

Matching queries are read-only.

Writes to aliases, SKUs, groups, and memberships must use normal SQLAlchemy transaction ownership.

Do not hold transactions across external calls.

There are no external calls in PR 7.

### Idempotency and concurrency

PostgreSQL constraints must protect at least:

- duplicate alias for the same manufacturer;
- duplicate alias for the same retailer;
- duplicate model alias for the same product;
- duplicate identical retailer/product/SKU mapping;
- duplicate retailer/group membership.

Concurrent retries must not create duplicate reference rows.

Where collisions across distinct entities are intentionally permitted, matching must return `AMBIGUOUS`.

### Migration/backfill

No real manufacturer, product, retailer, SKU, or group catalogue is seeded.

Existing:

```text
manufacturers.name
manufacturers.slug
products.model_number
retailers.name
retailers.slug
```

are already valid canonical inputs and therefore do not require duplicate alias rows to be generated.

The migration must preserve:

- all current products;
- all current manufacturers;
- all current retailers;
- all promotions;
- lifecycle state;
- benefits;
- sources;
- provenance.

Verify migration correctness against real PostgreSQL.

---

## External services and network access

None.

Normalisation and matching operate entirely on:

- deterministic Python logic;
- persisted PostgreSQL reference data.

PR 7 must not call:

- manufacturer sites;
- retailer sites;
- search engines;
- product APIs;
- AI providers;
- model providers;
- DNS resolution;
- external catalogue services.

---

## Security and privacy

This PR processes product/retailer reference data, not customer personal information.

Requirements:

- treat matching input as untrusted;
- bound string lengths at appropriate boundaries;
- reject invalid/empty normalised values;
- use SQLAlchemy bound parameters rather than constructed SQL;
- do not execute identifier content;
- do not deserialize arbitrary data;
- do not expose SQL/database errors as ordinary match failures;
- do not log arbitrary raw user-supplied values where identifiers may later originate from receipts or customer data;
- prefer result category and canonical IDs in diagnostics.

Do not add:

- customer names;
- addresses;
- receipts;
- payment data;
- email data;
- tracking identifiers.

No authentication/authorization change is required.

---

## Configuration and deployment

No environment-variable changes.

No new runtime service.

No changes intended for:

- Docker image;
- Railway configuration;
- startup/shutdown behaviour;
- health endpoints;
- workers;
- cron jobs;
- Redis;
- external credentials.

Deployment requires the normal Alembic migration to be applied before code depending on the new tables executes.

---

## Observability and operations

No new telemetry system is required.

Where matching is instrumented through existing structured logging, useful low-cardinality fields include:

```text
operation=resolve_manufacturer
result=matched|not_found|ambiguous
candidate_count
```

For entity matches, safe canonical IDs may be included where existing conventions permit.

Do not emit full arbitrary matching input merely for diagnostics.

Expected match failures such as:

```text
not_found
ambiguous
```

are domain/application outcomes.

Database failures remain infrastructure failures.

---

## Failure, consistency, and recovery

### Invalid input

For values that normalise to empty or otherwise violate the domain contract:

```text
reject as invalid input
```

Do not query PostgreSQL and return `NOT_FOUND`.

### No candidate

When no deterministic canonical candidate exists:

```text
NOT_FOUND
```

Do not attempt fuzzy matching.

### Alias collision

When two canonical entities share the same accepted normalised alias:

```text
AMBIGUOUS
```

Do not choose based on row order.

### Duplicate canonical-name match

If persisted canonical names normalise to the same value and resolve to multiple entities:

```text
AMBIGUOUS
```

### Model collision

When the same manufacturer/model input resolves to multiple product IDs:

```text
AMBIGUOUS
```

### Model versus SKU conflict

If:

```text
model -> Product A
SKU   -> Product B
```

return:

```text
AMBIGUOUS
```

### Database failure

A repository/database failure must:

- remain distinguishable from `NOT_FOUND`;
- use the established safe persistence/application error boundary;
- not produce a guessed match.

### Duplicate write retry

When the same alias/SKU/membership write is retried concurrently:

- constraints prevent duplicate rows;
- transaction remains recoverable;
- no duplicate business identity is created.

### Failed migration

The schema upgrade must remain transactional where PostgreSQL/Alembic permits.

An unsuccessful migration must not leave application code believing the new matching tables are available.

---

## Acceptance criteria

### Normalisation

- [x] Human-readable matching applies Unicode NFKC.
- [x] Human-readable matching trims whitespace.
- [x] Human-readable matching case-folds input.
- [x] Human-readable matching collapses internal whitespace.
- [x] Identifier matching applies Unicode NFKC.
- [x] Identifier matching removes identifier whitespace.
- [x] Identifier matching case-folds.
- [x] Identifier punctuation is preserved.
- [x] Empty normalised values are rejected.
- [x] Normalisation performs no network or AI call.

### Manufacturer matching

- [x] Canonical manufacturer slug can resolve a manufacturer.
- [x] Canonical manufacturer name can resolve a manufacturer.
- [x] Curated manufacturer alias can resolve a manufacturer.
- [x] Missing manufacturer returns `NOT_FOUND`.
- [x] Colliding manufacturer input returns `AMBIGUOUS`.
- [x] Failed matching does not create an alias.

### Retailer matching

- [x] Canonical retailer slug can resolve a retailer.
- [x] Canonical retailer name can resolve a retailer.
- [x] Curated retailer alias can resolve a retailer.
- [x] Missing retailer returns `NOT_FOUND`.
- [x] Colliding retailer input returns `AMBIGUOUS`.

### Product/model/SKU matching

- [x] Existing `Product.model_number` participates in model matching.
- [x] Product-model aliases participate in matching.
- [x] Model matching is manufacturer-scoped.
- [x] Model numbers remain non-globally-unique.
- [x] Retailer SKUs map to canonical products.
- [x] SKU matching is retailer-scoped.
- [x] SKUs are not globally unique.
- [x] No product match returns `NOT_FOUND`.
- [x] Multiple product candidates return `AMBIGUOUS`.
- [x] A model/SKU conflict returns `AMBIGUOUS`.
- [x] Identical candidates discovered through model and SKU collapse to one product ID.

### Retailer groups

- [x] Canonical retailer groups can be persisted.
- [x] Group slugs are canonical and unique.
- [x] Group names are non-empty.
- [x] Retailer-group identity can be matched deterministically.
- [x] Retailers can belong to zero groups.
- [x] Retailers can belong to one group.
- [x] Retailers can belong to multiple groups.
- [x] Duplicate memberships are rejected.
- [x] Membership does not imply promotion eligibility.

### Purchase channels

- [x] `online` resolves deterministically.
- [x] `web` resolves to `online`.
- [x] `website` resolves to `online`.
- [x] `in_store` resolves deterministically.
- [x] `in-store` resolves to `in_store`.
- [x] `instore` resolves to `in_store`.
- [x] `store` resolves to `in_store`.
- [x] `shop` resolves to `in_store`.
- [x] Unsupported channels are not silently mapped to `other`.
- [x] Purchase-channel matching is extensible without introducing a rules DSL.

### Data and consistency

- [x] Existing canonical manufacturer/product/retailer IDs remain unchanged.
- [x] Existing `Product.model_number` remains intact.
- [x] Existing promotion rows remain unchanged.
- [x] Existing lifecycle state remains unchanged.
- [x] Existing promotion provenance remains unchanged.
- [x] Duplicate per-entity aliases are prevented.
- [x] Duplicate identical SKU mappings are prevented.
- [x] Duplicate retailer/group membership is prevented.
- [x] Cross-entity alias collisions remain representable and return `AMBIGUOUS`.
- [x] New migration applies against real PostgreSQL.
- [x] ORM metadata and Alembic schema remain in parity.

### Architecture

- [x] Domain normalisation does not depend on SQLAlchemy.
- [x] Domain normalisation does not depend on FastAPI.
- [x] Domain normalisation does not depend on Alembic.
- [x] Domain normalisation does not depend on AI/network providers.
- [x] SQLAlchemy rows do not leak through application contracts.
- [x] No generic repository framework is introduced.
- [x] No fuzzy matching framework is introduced.
- [x] No eligibility logic is introduced.
- [x] Existing promotion application behaviour remains unchanged.

### Security

- [x] Untrusted strings are validated.
- [x] Empty normalised identifiers are rejected.
- [x] Database errors are not presented as normal match failures.
- [x] Matching uses safe parameterised persistence queries.
- [x] No external requests occur.
- [x] No secrets or customer data are introduced.

### Scope

- [x] No public REST endpoint is added.
- [x] No MCP tool is added.
- [x] No eligibility engine is added.
- [x] No promotion matching is added.
- [x] No source ingestion is added.
- [x] No scraping is added.
- [x] No AI extraction/matching is added.
- [x] No receipt processing is added.
- [x] No background worker is added.
- [x] No frontend change is added.

### Code quality

- [x] Ruff formatting passes.
- [x] Ruff lint passes.
- [x] Targeted unit tests pass.
- [x] PostgreSQL integration tests pass.
- [x] Full backend test suite passes.
- [x] Migration verification passes.
- [x] No unnecessary dependency is introduced.

---

## Tests to add or update

### Unit tests

Add a focused module such as:

```text
backend/tests/unit/test_identity_normalisation.py
```

and/or:

```text
backend/tests/unit/test_product_retailer_matching.py
```

depending on the implementation structure.

Cover at minimum:

#### Human text normalisation

Test:

```text
leading/trailing whitespace
multiple internal spaces
case differences
Unicode NFKC equivalence
empty input
whitespace-only input
punctuation preservation
```

#### Identifier normalisation

Test:

```text
" QE55 S95D " -> "qe55s95d"
"AB-123" != "AB123"
case-insensitive identifiers
Unicode normalisation
empty identifiers rejected
```

#### Match result invariants

Verify:

```text
zero candidates -> NOT_FOUND
one unique ID -> MATCHED
multiple unique IDs -> AMBIGUOUS
duplicate references to same ID -> MATCHED
```

#### Purchase channels

Cover every supported canonical value and alias.

Verify unsupported values remain unsupported/not found.

### PostgreSQL integration tests

Add a focused module such as:

```text
backend/tests/integration/test_product_retailer_normalisation.py
```

Use the existing PostgreSQL/Testcontainers infrastructure.

Cover at minimum:

#### Manufacturer aliases

Persist:

```text
Manufacturer
ManufacturerAlias
```

Verify canonical name, slug, and alias resolve to the same manufacturer.

#### Manufacturer ambiguity

Create two manufacturers with a colliding normalised alias.

Verify lookup returns:

```text
AMBIGUOUS
```

#### Retailer aliases

Equivalent canonical/alias tests for retailers.

#### Model matching

Create two manufacturers with the same model-number text on separate products.

Verify manufacturer scope resolves correctly.

Also create two products under the same manufacturer whose accepted model identifiers collide and verify:

```text
AMBIGUOUS
```

#### Product-model aliases

Verify alternate model spelling resolves to the existing canonical product without creating another product.

#### Retailer SKU

Create:

```text
Retailer A + SKU 123 -> Product A
Retailer B + SKU 123 -> Product B
```

Verify retailer scope resolves each independently.

#### SKU ambiguity

Create two mappings for the same retailer and normalised SKU pointing to different products.

Verify:

```text
AMBIGUOUS
```

#### Combined model/SKU

Verify:

```text
model -> Product A
SKU -> Product A
```

returns one matched canonical product.

Verify:

```text
model -> Product A
SKU -> Product B
```

returns:

```text
AMBIGUOUS
```

#### Retailer groups

Verify:

- group persistence;
- slug uniqueness;
- retailer with zero groups;
- retailer with one group;
- retailer with multiple groups;
- duplicate membership rejection;
- group deletion/membership FK behaviour.

#### Duplicate alias/mapping constraints

Verify database rejection of:

- duplicate same manufacturer alias;
- duplicate same retailer alias;
- duplicate same product model alias;
- duplicate identical retailer/product/SKU mapping;
- duplicate retailer/group membership.

#### Reference deletion

Verify new alias/SKU/membership relationships do not allow silent corruption of referenced canonical data.

#### Migration preservation

Start from the previous migration, create representative existing:

```text
Manufacturer
Product
Retailer
Promotion
Source/provenance
```

data where practical through the repository's migration-test approach.

Upgrade to the new migration.

Verify existing identity and promotion data remains intact.

#### ORM/migration parity

Retain or extend `compare_metadata` coverage so SQLAlchemy metadata matches the migrated PostgreSQL schema.

### API/application tests

No FastAPI contract change.

Test internal application resolution operations directly if the implementation adds application-level orchestration.

Verify infrastructure failures remain distinguishable from matching outcomes.

### MCP contract tests

N/A.

### External-boundary tests

N/A.

No HTTP, AI, model-provider, or external product-data boundary is introduced.

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

The current repository does not configure a type-checker dependency or command.

Do not add one solely for PR 7.

### Targeted unit tests

Adjust exact filenames to the implementation:

```bash
uv run pytest tests/unit/test_identity_normalisation.py tests/unit/test_product_retailer_matching.py
```

### PostgreSQL integration tests

```bash
uv run pytest tests/integration/test_product_retailer_normalisation.py tests/integration/test_core_promotion_schema.py
```

Docker must be available because integration tests use PostgreSQL Testcontainers.

### Broader backend suite

```bash
uv run pytest
```

### Migration verification

Verify the new revision is the single expected head:

```bash
uv run alembic heads
```

Against a real PostgreSQL database run:

```bash
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head
```

and ensure migration/metadata integration tests pass.

Do not modify a previously deployed migration to avoid creating the new PR 7 revision.

If any command cannot run, report:

1. the exact command;
2. why it could not run;
3. what was verified instead;
4. the remaining risk.

---

## Completion report

When implementation is complete provide:

### Changed

Summarise:

- normalisation functions introduced;
- canonical matching results;
- manufacturer aliases;
- product-model aliases;
- retailer aliases;
- retailer-specific SKU mappings;
- retailer groups/memberships;
- purchase-channel matching;
- repository/application matching paths.

### Database and migrations

List:

- new Alembic revision;
- tables/indexes/constraints added;
- any backfill performed.

Explicitly confirm whether existing:

```text
manufacturers
products
retailers
promotions
sources
promotion_sources
```

were preserved unchanged.

### API/MCP contracts

Expected:

```text
None.
```

### Tests and verification

List:

- unit tests added;
- PostgreSQL integration tests added;
- exact verification commands run;
- results.

Do not claim an unrun command passed.

### External configuration

Expected:

```text
None.
```

### Deviations

Describe any meaningful deviation from this specification and why it was necessary.

Use:

```text
None.
```

when there were none.

### Remaining risks or follow-up

Expected follow-up work includes:

- purchase-input transport contracts;
- promotion candidate selection using canonical identities;
- retailer/retailer-group promotion applicability;
- purchase-channel eligibility rules;
- purchase-date eligibility;
- claim-window semantics;
- price/currency rules;
- deterministic complete purchase eligibility;
- receipt/input extraction;
- curated normalisation administration or ingestion;
- temporal retailer-group membership if historical group membership becomes relevant.

Do not implement those capabilities in PR 7.

## Implementation verification — 2026-10-06

Implemented on `pr7-product-retailer-normalisation` from fetched `origin/main`
`cb85df2`, containing PRs 3–6. Local main was stale; remote main was used.
The prior Alembic head was `0002_core_promotion_schema`. No scoped backend
AGENTS.md, existing identity repository, retailer groups or purchase-channel
vocabulary existed. Product model numbers remain nullable and non-unique.
No dependency, configuration, transport, eligibility or ingestion code changed.

All acceptance checkboxes above are satisfied. Evidence by acceptance area:

| Criteria | Implementation and verification evidence |
| --- | --- |
| Normalisation | `app/domain/identity_normalisation.py`; unit tests for NFKC, Unicode case folding, whitespace, punctuation, empty/type/length/control-character validation, repeatability and stable enums. Only standard-library imports. Raw and normalised strings are bounded to 255 characters. |
| Match result contract | Immutable `MatchResult`; derived status/canonical identity and sorted distinct UUID candidates. Unit tests cover zero/one/multiple IDs, duplicate references, deterministic ordering, immutability and invalid identities. |
| Manufacturer, retailer and group matching | Application `IdentityResolver` and `SqlAlchemyIdentityRepository` combine canonical names/slugs with indexed aliases. PostgreSQL tests cover canonical/alias matches, not found, same-ID deduplication, alias collisions, canonical-name collisions, alias/name collisions and alias/slug collisions. Lookups never learn aliases. Group aliases have a concrete consumer in `resolve_retailer_group`. |
| Models and SKUs | Manufacturer-scoped canonical models and model aliases; retailer-scoped SKUs; optional manufacturer filtering. Tests cover model reuse between manufacturers, same-manufacturer model collisions, alias ambiguity, retained model numbers, nullable/blank legacy models, same SKU across retailers, SKU ambiguity, unknown contexts, exact punctuation, model/SKU agreement/conflict and cross-manufacturer exclusion. |
| Groups and channels | PostgreSQL group UUIDs, aware timestamps, unique canonical slugs, non-empty names, zero/one/multiple memberships and deletion integrity. Domain tests exercise every channel alias and unsupported inputs with no fallback. Membership queries return current IDs only and never infer eligibility. |
| Data integrity and concurrency | ORM insert/update hooks derive alias/SKU keys. Composite primary keys reject per-entity duplicates while retaining cross-entity ambiguity. PostgreSQL tests cover every association FK, bounded/non-empty columns, all duplicate kinds and recovery, independent simultaneous transaction races, ORM/raw deletion restrictions/cascades and SKU/alias updates. |
| Migration preservation | `0003_identity_normalisation` creates seven additive tables with lookup/FK indexes, composite uniqueness, checks and FK deletion policies. No seed or backfill. Isolated PostgreSQL migration test starts at 0002 with the complete representative existing graph and compares all original rows before/after upgrade and downgrade. Canonical rows resolve without alias backfill. Existing manufacturers, products, retailers, promotions, sources and promotion_sources are preserved unchanged, including IDs, model text, lifecycle state, benefits and provenance. |
| Migration correctness | Real PostgreSQL CLI upgrade → downgrade -1 → upgrade, retained baseline downgrade/upgrade coverage, single expected head, and existing `compare_metadata` schema parity tests all pass. Earlier migrations remain unmodified. |
| Security/failures/architecture | Application input/context validation occurs before repository reads. Scalar UUID contracts prevent ORM leakage. Queries use SQLAlchemy bound parameters; hostile identifier text remains data. Real PostgreSQL failure tests verify safe errors and transaction recovery for all lookup paths, including memberships. Read-only statement capture and pending-row tests demonstrate no INSERT/UPDATE/DELETE/autoflush. Invalid persisted canonical text produces a safe infrastructure failure rather than not found. |
| Scope and compatibility | Diff review and unchanged promotion lifecycle/provenance, health, configuration and session tests confirm no new public endpoints, MCP tools, eligibility logic, source ingestion, scraping, AI, external requests, receipt processing, worker, frontend or dependencies. No generic repository/fuzzy framework was introduced. |

Commands run from `backend/` with `UV_CACHE_DIR=/private/tmp/ppbc-uv-cache`:

```bash
uv sync --locked --extra dev
uv run ruff format --check .
uv run ruff check .
uv run pytest tests/unit/test_identity_normalisation.py tests/unit/test_product_retailer_matching.py
uv run pytest tests/integration/test_product_retailer_normalisation.py tests/integration/test_core_promotion_schema.py tests/integration/test_postgres_migrations.py --tb=short
uv run alembic heads
uv run pytest --tb=short
```

Formatting fixes were run from the repository root, with the same cache setting:

```bash
uv run --project backend ruff check --fix backend
uv run --project backend ruff format backend
```

Final results: **114 targeted unit tests passed**, **172 targeted PostgreSQL tests
passed**, and **474 full backend tests passed**. Ruff lint/format checks passed.
`alembic heads` reports only `0003_identity_normalisation`. The PostgreSQL fixture
and migration tests execute the actual `alembic upgrade head`, `alembic downgrade -1`
and `alembic upgrade head` commands against disposable PostgreSQL, as well as a
baseline rollback/re-upgrade. The preservation test separately runs the migration
round trip through Alembic's Python API on an isolated transactional schema.
`git diff --check` passed. Initial lint formatting findings were corrected.
One pre-existing Starlette/httpx deprecation warning remains. No type checker is
configured, so none was added or claimed. Docker packaging was unchanged.

Database: seven new reference tables; no backfill or catalogue seeds.
API/MCP contracts: None. External configuration: None (apply the migration before use).
Deviations: None. Remaining issues within PR 7 scope: None.

Direct SQL/bulk reference maintenance must derive normalised keys with the same
domain functions because SQL bypasses ORM hooks. Current group memberships have
no historical effective dates. All follow-up capabilities listed in the original
specification remain deferred as required.
