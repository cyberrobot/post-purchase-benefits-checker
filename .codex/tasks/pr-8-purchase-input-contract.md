# PR 8 — Purchase Input Contract

## Repository state

**Expected branch:**  
`pr8-purchase-input-contract`

**Base branch:**  
`main`

**Dependencies:**

- PR 3 — Core Promotion Schema: merged.
- PR 4 — Promotion Lifecycle & History: merged.
- PR 5 — Benefit Model: merged.
- PR 6 — Promotion Source Provenance: merged.
- PR 7 — Product & Retailer Normalisation: merged.
- Existing Python 3.13 application/domain boundaries and pytest/Ruff tooling.
- No new database, transport, provider, AI, queue, worker, or infrastructure dependency.

### Read first

Before making changes, read:

- `AGENTS.md`
- `.codex/tasks/TEMPLATE.md`
- `.codex/tasks/pr-7-product-retailer-normalisation.md`
- `backend/README.md`
- `backend/app/application/identity_matching.py`
- `backend/app/domain/identity_normalisation.py`
- `backend/tests/unit/test_identity_normalisation.py`
- `backend/tests/unit/test_product_retailer_matching.py`
- `backend/pyproject.toml`

If a more narrowly scoped `AGENTS.md` exists on the implementation branch, read and follow it.

### Primary change area

Application-owned purchase-check input contract.

This PR defines the structured request accepted by the future canonical:

```text
check_purchase(input) -> structured eligibility result
```

The request contains:

```text
brand
model
retailer
purchase_date
purchase_price?
```

This PR defines and validates the input value only.

It does **not** implement:

- identity resolution orchestration;
- promotion candidate selection;
- eligibility evaluation;
- a REST endpoint;
- an MCP tool;
- a response/result contract.

### Canonical implementation examples

Treat these as the preferred implementation references:

- `backend/app/application/identity_matching.py`
  - application-owned contracts;
  - no FastAPI or SQLAlchemy types crossing the application boundary;
  - deterministic validation before persistence reads.
- `backend/app/domain/identity_normalisation.py`
  - immutable value types;
  - conservative deterministic text validation;
  - stable handling of malformed identity input.
- `backend/app/domain/benefits.py`
  - immutable domain values;
  - explicit validation;
  - stable enum/value semantics.
- `backend/tests/unit/test_identity_normalisation.py`
  - boundary-focused deterministic unit tests.
- `backend/tests/unit/test_product_retailer_matching.py`
  - application-contract behaviour without persistence or network access.

There is currently no public `check_purchase` transport contract that must be preserved.

Do not create one solely for this PR.

### Relevant symbols

Inspect at minimum:

- `IdentityResolver`
- `IdentityRepository`
- `MatchResult`
- `MatchStatus`
- `normalise_text`
- `normalise_identifier`
- `Manufacturer`
- `Product`
- `Retailer`
- current backend package structure
- current backend test and lint commands

### Expected change surface

Expected changes are small and should be limited to areas equivalent to:

```text
backend/app/application/
backend/tests/unit/
backend/README.md
```

Likely additions:

```text
backend/app/application/purchase_check.py
backend/tests/unit/test_purchase_input.py
```

A small domain helper may be added only if validation cannot be expressed cleanly through the existing identity-normalisation primitives without duplicating business rules.

No persistence or migration change is expected.

### Excluded areas

Do not implement:

- REST routes;
- FastAPI request/response schemas;
- MCP tools;
- OpenAPI changes;
- identity lookup or canonicalisation as part of request construction;
- promotion matching;
- promotion applicability checks;
- eligibility rules;
- claim-window rules;
- promotion precedence;
- result classifications such as eligible/ineligible/unknown;
- price-threshold eligibility;
- currency conversion;
- purchase-channel input;
- retailer-group input;
- receipt/image parsing;
- OCR;
- scraping;
- external product lookup;
- product catalogue retrieval;
- AI/LLM extraction or matching;
- purchase persistence;
- customer/account persistence;
- analytics/event persistence;
- new migrations;
- background jobs;
- frontend behaviour.

### Unknowns Codex must verify

Before implementation verify:

- no `check_purchase` request type has appeared since this specification was written;
- no scoped backend `AGENTS.md` has appeared;
- the current identity input length and control-character rules still live in `identity_normalisation.py`;
- no existing money/value object already defines the required purchase-price semantics;
- no existing date-value helper already defines purchase-date semantics;
- no REST or MCP purchase-check contract has appeared that this application contract must remain compatible with;
- the actual lint/format/test commands still match `backend/README.md` and `backend/pyproject.toml`.

Do not create parallel abstractions when the implementation branch already contains an equivalent concept.

---

## Objective

After PR 8, the backend must have one explicit, immutable, transport-independent application request type representing the information a caller supplies to a future `check_purchase` use case.

Conceptually:

```python
CheckPurchaseRequest(
    brand=...,
    model=...,
    retailer=...,
    purchase_date=...,
    purchase_price=...,
)
```

The contract must represent exactly these inputs:

```text
brand: required string
model: required string
retailer: required string
purchase_date: required calendar date
purchase_price: optional decimal monetary amount
```

The request must:

- validate structural input errors deterministically;
- preserve the caller-supplied brand, model, and retailer text rather than replacing it with canonical database identities;
- preserve `None` for an omitted purchase price rather than converting it to zero;
- use exact decimal money semantics rather than binary floating point;
- remain independent of FastAPI, MCP, SQLAlchemy, PostgreSQL, network services, and AI;
- be reusable unchanged by future REST and MCP adapters.

This PR is complete when callers inside the application can construct a valid purchase-check request and malformed request values are rejected predictably without performing identity lookup, database access, eligibility evaluation, or any side effect.

---

## Architecture and invariants

Preserve the established dependency direction:

```text
REST / MCP
    ↓
application use cases and application-owned contracts
    ↓
domain rules and identity normalisation
    ↓
application-owned ports
    ↓
infrastructure adapters
```

### Application-owned request

`CheckPurchaseRequest` belongs to the application boundary because it is the shared input to the future application use case.

It must not be a FastAPI/Pydantic transport model.

Future transport adapters may parse their wire representation with Pydantic, but they must map into the same application request instead of maintaining separate business semantics.

### Raw input is not canonical identity

The following request fields are caller-supplied identity input:

```text
brand
model
retailer
```

They are not:

```text
Manufacturer.id
Product.id
Retailer.id
```

Request construction must not perform canonical matching.

Later application orchestration will use the PR 7 identity resolver to distinguish:

```text
matched
not_found
ambiguous
```

A syntactically valid but unknown brand, model, or retailer must therefore remain a valid `CheckPurchaseRequest`.

For example:

```text
brand="A Brand Not Yet In Reference Data"
```

must not fail merely because no canonical manufacturer exists.

### Caller-facing brand terminology

The external/request field is named:

```text
brand
```

The persisted canonical concept remains:

```text
Manufacturer
```

Do not rename the request field to `manufacturer` in this PR.

Later resolution may map:

```text
request.brand
    ↓
IdentityResolver.resolve_manufacturer(...)
    ↓
Manufacturer.id
```

### Model input

The request field is named:

```text
model
```

It represents caller-supplied product model/identifier text.

PR 8 does not decide whether later orchestration treats the value strictly as a manufacturer-scoped model or also attempts retailer-SKU resolution.

That resolution policy belongs to the purchase-check orchestration PR.

Request construction must therefore only validate that `model` is a valid bounded identifier input.

### Purchase date is a calendar date

`purchase_date` represents the calendar date on which the purchase occurred.

It is not:

- a timestamp;
- a timezone-aware datetime;
- an evaluation date;
- a claim date.

The application contract uses:

```python
datetime.date
```

and must reject `datetime.datetime` even though Python's `datetime` is a subclass of `date`.

No timezone conversion applies to a calendar purchase date.

### Purchase price is optional information

`purchase_price` may be:

```text
None
```

A missing price means:

```text
not supplied / unknown
```

It must never silently mean:

```text
0
```

A future price-dependent eligibility rule must be able to distinguish those states.

### Money is exact

Use:

```python
Decimal
```

for `purchase_price`.

Do not use:

```python
float
```

Do not silently round caller input.

Because the current product is UK-focused and this request intentionally contains no currency field, the value represents a GBP purchase amount for this contract.

Do not add a currency field in PR 8.

If multi-currency support is required later, extend the contract explicitly rather than inferring currency from retailer, locale, or formatting.

### Deterministic validation

For identical field values and application version, request construction must produce an equivalent outcome.

Validation must not depend on:

- the current database contents;
- the current date/time;
- network access;
- LLM calls;
- fuzzy matching;
- locale-dependent parsing;
- retailer-specific behaviour.

### No current-date validation

PR 8 must not reject a `purchase_date` merely because it is later than the machine's current date.

"Future purchase" is a use-case/business validation question that requires an explicit evaluation date or clock.

Do not introduce wall-clock dependence into this pure request contract.

---

## API and contract changes

This PR introduces one internal application contract.

No public REST or MCP contract changes are made.

### `CheckPurchaseRequest`

Preferred shape:

```python
@dataclass(frozen=True, slots=True)
class CheckPurchaseRequest:
    brand: str
    model: str
    retailer: str
    purchase_date: date
    purchase_price: Decimal | None = None
```

Exact implementation details may follow repository conventions, but the field names and meanings above are required.

### Field: `brand`

Required.

Application type:

```python
str
```

Validation:

- must be a string;
- must satisfy the same bounded human-readable identity-input rules used by `normalise_text`;
- leading/trailing/internal whitespace may remain in the stored raw field;
- whitespace-only input is invalid;
- unsupported control characters are invalid;
- oversized identity input is invalid;
- validation must not require a matching `Manufacturer`.

The implementation may call:

```python
normalise_text(brand)
```

for validation while retaining the original `brand` value.

Do not store the normalised text as a replacement for the raw field.

### Field: `model`

Required.

Application type:

```python
str
```

Validation:

- must be a string;
- must satisfy the same bounded identifier-input rules used by `normalise_identifier`;
- whitespace-only input is invalid;
- unsupported control characters are invalid;
- oversized identity input is invalid;
- punctuation is valid and must not be broadly stripped;
- validation must not require a matching `Product`.

The implementation may call:

```python
normalise_identifier(model)
```

for validation while retaining the original `model` value.

Do not remove punctuation or persist a normalised replacement inside the request.

### Field: `retailer`

Required.

Application type:

```python
str
```

Validation:

- must be a string;
- must satisfy the same bounded human-readable identity-input rules used by `normalise_text`;
- whitespace-only input is invalid;
- unsupported control characters are invalid;
- oversized identity input is invalid;
- validation must not require a matching `Retailer`.

The implementation may call:

```python
normalise_text(retailer)
```

for validation while retaining the original `retailer` value.

### Field: `purchase_date`

Required.

Application type:

```python
date
```

Validation:

- must be an actual `datetime.date`;
- `datetime.datetime` is invalid;
- strings are not parsed by the application request constructor;
- timestamps are not accepted;
- no time component is accepted;
- no timezone is accepted;
- no "today" or future/past comparison occurs in PR 8.

Future JSON adapters should represent this as an ISO 8601 full-date value:

```text
YYYY-MM-DD
```

but transport parsing is outside this PR.

### Field: `purchase_price`

Optional.

Application type:

```python
Decimal | None
```

Default:

```python
None
```

Validation when supplied:

- must be a `Decimal`;
- must be finite;
- must be greater than or equal to zero;
- must have no more than two fractional decimal places;
- must not be silently rounded or quantized;
- `float` input is invalid;
- `NaN` is invalid;
- positive or negative infinity is invalid;
- negative values are invalid.

Valid examples:

```python
None
Decimal("0")
Decimal("0.00")
Decimal("19.99")
Decimal("1299")
Decimal("1299.00")
```

Invalid examples:

```python
-1
Decimal("-0.01")
Decimal("19.999")
Decimal("NaN")
Decimal("Infinity")
19.99  # float
"19.99"
"£19.99"
```

The application contract does not parse currency symbols, thousands separators, or locale-specific money strings.

Transport adapters may later parse an external representation into `Decimal`, but the application boundary must receive an exact decimal value.

### Immutability

A successfully constructed request must be immutable.

Callers must create a new request rather than mutating a request already being evaluated.

### Extra fields

The application request exposes only the five fields defined above.

Do not add speculative fields such as:

```text
currency
purchase_channel
retailer_group
sku
quantity
postcode
country
email
receipt
customer_id
promotion_code
evaluation_date
```

without a separate requirement.

### Error behaviour

Follow existing application/domain conventions.

At minimum:

- wrong Python field types must fail predictably;
- structurally invalid field values must fail predictably;
- validation must occur before any future persistence/network work;
- errors must not contain database/provider details because none are required to validate this contract.

A dedicated validation exception may be introduced only if it materially improves future transport error mapping.

Do not introduce an elaborate error hierarchy solely for PR 8.

### Backward compatibility

No existing public request contract exists.

This is therefore additive.

Once future REST/MCP contracts consume this request, field names and semantics become externally significant and should be changed only deliberately.

### Idempotency

Request construction is pure and side-effect free.

Constructing the same valid request repeatedly must not create or mutate persisted state.

---

## Domain and application behaviour

### Construction sequence

Conceptually validate in this order:

```text
brand shape
model shape
retailer shape
purchase_date type/shape
purchase_price type/value
    ↓
immutable CheckPurchaseRequest
```

The exact implementation order is not externally significant, but no validation step may cause database/network/AI access.

### Identity input validation

Reuse the existing PR 7 validation rules rather than inventing a looser parallel contract.

Conceptually:

```python
normalise_text(brand)
normalise_identifier(model)
normalise_text(retailer)
```

These calls are for validation only.

The request retains the raw original values.

Example:

```python
request = CheckPurchaseRequest(
    brand="  Samsung ",
    model=" QE55 S95D ",
    retailer=" Currys ",
    purchase_date=date(2026, 9, 12),
)
```

may remain:

```text
brand == "  Samsung "
model == " QE55 S95D "
retailer == " Currys "
```

A later resolver is responsible for canonical normalisation and matching.

This preserves:

- caller input for explanation/debugging when appropriate;
- one canonical normalisation implementation;
- clear separation between request validation and identity resolution.

### Unknown reference data is not malformed input

These are different conditions:

```text
invalid input shape
unknown canonical identity
ambiguous canonical identity
```

PR 8 handles only the first.

Examples of syntactically valid request values that may later resolve to `not_found`:

```text
brand="Example New Brand"
model="ABC-123"
retailer="Example Retailer"
```

Do not query reference data during request construction to reject these values.

### Ambiguity is not request invalidity

Likewise, an input that later resolves to multiple canonical identities is still a structurally valid purchase request.

For example:

```text
retailer="Example"
```

may later produce:

```text
ambiguous
```

That outcome belongs to the future application use case, not the request constructor.

### Purchase price precision

No implicit rounding.

For example:

```text
19.999
```

must not become:

```text
20.00
```

A caller must submit an exact acceptable amount.

### Zero versus missing price

These are distinct:

```python
purchase_price=None
purchase_price=Decimal("0")
```

The request must preserve that distinction.

### Date semantics

The request records only the supplied calendar date.

It must not derive:

- purchase timestamp;
- timezone;
- local midnight;
- evaluation date;
- claim-window date;
- promotion lookup period.

Those belong to later behaviour.

### No eligibility outcome

Construction must never return or imply:

```text
eligible
ineligible
unknown
no_promotion
```

The contract contains input only.

### No canonical IDs

Do not add hidden or eagerly populated fields such as:

```text
manufacturer_id
product_id
retailer_id
retailer_group_ids
```

to `CheckPurchaseRequest`.

Canonical resolution should produce a separate later application value so raw input and resolved identity remain distinguishable.

---

## Persistence, transactions, and migrations

None.

PR 8 does not:

- add tables;
- add columns;
- change constraints;
- add indexes;
- write purchase records;
- change promotion records;
- change alias/reference data;
- require an Alembic revision.

Request construction has no transaction boundary because it has no persistence side effects.

Existing migration head remains unchanged.

PostgreSQL integration tests are not required for this PR unless the implementation unexpectedly changes persistence, which should be treated as a scope deviation and explained.

---

## External services and network access

None.

Request construction must not perform:

- HTTP requests;
- DNS resolution;
- retailer lookup;
- manufacturer lookup;
- product-catalogue lookup;
- source retrieval;
- AI/model calls.

No timeout, retry, credential, or provider configuration is introduced.

---

## Security and privacy

The request is untrusted caller input.

Validation must:

- enforce existing bounded identity-input rules for `brand`, `model`, and `retailer`;
- reject unsupported control characters;
- reject malformed money values;
- reject malformed date values;
- avoid dynamic code execution or locale-dependent parsing.

Do not:

- log full purchase requests as part of implementing this value object;
- add customer identity or payment-card fields;
- accept arbitrary executable expressions;
- infer or fetch URLs from these fields;
- perform SQL/string interpolation from these values.

This PR introduces no authentication or authorization behaviour because it exposes no transport endpoint.

Future transport adapters remain responsible for their authentication, authorization, request-size, and rate-limit boundaries.

---

## Configuration and deployment

None.

### Environment variables

No new, changed, or removed environment variables.

### Runtime/deployment changes

None.

No Docker, Railway, process, worker, health-check, startup, or shutdown change is required.

---

## Observability and operations

No new operational telemetry is required for constructing a pure immutable request value.

Do not add logging or metrics solely for successful request construction.

Future `check_purchase` orchestration may record safe low-cardinality result categories such as identity resolution or eligibility outcome, but that is outside PR 8.

Validation errors must remain distinguishable from later infrastructure failures at the application boundary.

---

## Failure, consistency, and recovery

Request construction is pure and side-effect free.

There is no partial persisted state to recover.

### Invalid text input

Required final state:

```text
construction fails
no request object is returned
no external work occurs
```

### Invalid purchase date

Required final state:

```text
construction fails
no request object is returned
no external work occurs
```

### Invalid purchase price

Required final state:

```text
construction fails
no rounding/coercion occurs
no request object is returned
no external work occurs
```

### Unknown brand/model/retailer

Required final state:

```text
request construction succeeds
```

Canonical resolution happens later.

### Ambiguous brand/model/retailer

Required final state:

```text
request construction succeeds
```

Ambiguity is discovered and represented later by identity resolution.

### Repeated construction

Required final state:

```text
equivalent input
-> equivalent immutable request
-> no duplicate side effects
```

---

## Acceptance criteria

### Behaviour

- [ ] A transport-independent `CheckPurchaseRequest` application contract exists.
- [ ] The request has exactly `brand`, `model`, `retailer`, `purchase_date`, and optional `purchase_price`.
- [ ] `brand`, `model`, and `retailer` are required strings.
- [ ] `brand` and `retailer` are validated with semantics consistent with `normalise_text`.
- [ ] `model` is validated with semantics consistent with `normalise_identifier`.
- [ ] Valid raw identity strings are retained rather than replaced by normalised values.
- [ ] Unknown canonical identities do not make request construction fail.
- [ ] Ambiguous canonical identities do not make request construction fail.
- [ ] No identity repository query occurs during request construction.
- [ ] `purchase_date` is a calendar `date`, not a `datetime`.
- [ ] Request construction does not compare `purchase_date` with wall-clock "today".
- [ ] `purchase_price` defaults to `None`.
- [ ] `None` and `Decimal("0")` remain distinct.
- [ ] Supplied prices use `Decimal`, are finite, non-negative, and have at most two fractional decimal places.
- [ ] Floats and money strings are not silently coerced by the application contract.
- [ ] Prices are never silently rounded.
- [ ] The request is immutable.
- [ ] Constructing a request performs no database, network, AI, or persistence work.
- [ ] No eligibility result is calculated in this PR.
- [ ] Existing behaviour outside the stated change surface remains unchanged.

### Data and consistency

- [ ] No database schema change is introduced.
- [ ] No Alembic migration is introduced.
- [ ] No purchase/customer record is persisted.
- [ ] Existing promotion, provenance, lifecycle, identity, alias, SKU, and retailer-group data are unchanged.
- [ ] Raw request identity values remain separate from future canonical UUIDs.

### Security

- [ ] Untrusted text fields remain bounded by the established identity-input rules.
- [ ] Unsupported control characters are rejected.
- [ ] Malformed/non-finite/negative/over-precision money values are rejected.
- [ ] No dynamic evaluation, external lookup, or unsafe parsing is introduced.
- [ ] No secrets or internal infrastructure details are exposed.
- [ ] No new personal or payment-card data fields are introduced.

### Operations

- [ ] No new external call, environment variable, deployment process, health check, or background job is introduced.
- [ ] Validation remains a pure local operation.

### Code quality

- [ ] Existing application/domain dependency direction is preserved.
- [ ] The contract does not depend on FastAPI, Pydantic transport models, SQLAlchemy, or PostgreSQL.
- [ ] Existing identity-normalisation validation is reused where suitable rather than duplicated.
- [ ] No unnecessary generic validation framework is introduced.
- [ ] No speculative request fields are added.
- [ ] Ruff lint and format checks pass.
- [ ] Targeted unit tests pass.
- [ ] The broader backend test suite passes.

---

## Tests to add or update

### Unit tests

Add focused coverage, preferably in:

```text
backend/tests/unit/test_purchase_input.py
```

Cover at minimum:

#### Valid construction

- ordinary brand/model/retailer values;
- identity strings containing valid punctuation;
- identity strings containing whitespace that normalisation can validly handle;
- exact 255-character identity boundary where supported by the existing normalisers;
- calendar purchase dates;
- omitted purchase price;
- zero price;
- whole-pound decimal price;
- two-decimal-place price.

#### Identity field failures

For each relevant field:

```text
brand
model
retailer
```

cover:

- wrong Python type;
- empty string;
- whitespace-only input;
- oversized input;
- unsupported control characters.

Assert failure occurs without identity-repository/database interaction.

#### Raw-value preservation

Verify that validation does not silently replace:

```text
"  Example Brand "
```

with:

```text
"example brand"
```

inside the request.

Verify the same principle for model and retailer.

#### Purchase-date failures

Cover:

- string date rejected at application boundary;
- `datetime` rejected;
- `None` rejected;
- unrelated type rejected.

Also verify a future calendar date is not rejected solely because it is later than the machine date.

Do not rely on wall-clock time in the test; use a fixed clearly future date permitted by the `date` type.

#### Purchase-price failures

Cover:

- float rejected;
- string rejected;
- negative Decimal rejected;
- `NaN` rejected;
- positive infinity rejected;
- negative infinity rejected;
- more than two fractional decimal places rejected.

Verify no value is silently rounded.

#### Immutability

Verify fields cannot be mutated after construction.

#### Equality/determinism

Equivalent valid field values should produce equal request values when the chosen implementation provides value equality.

### PostgreSQL integration tests

N/A.

No persistence behaviour changes.

### API/application tests

No FastAPI transport tests are required because no endpoint is introduced.

The unit test above is the application-contract coverage for this PR.

If an existing application contract test location has appeared by implementation time, use it rather than adding a parallel test convention.

### MCP contract tests

N/A.

No MCP tool is introduced.

### External-boundary tests

N/A.

No external boundary is introduced.

---

## Verification commands

Codex must verify the commands against the implementation branch before completion.

From `backend/`:

```bash
# Install/sync dependencies when required
uv sync --locked --extra dev

# Formatting check
uv run ruff format --check .

# Lint
uv run ruff check .

# Type checking
# N/A — no type checker is currently configured in backend/pyproject.toml.

# Targeted tests
uv run pytest tests/unit/test_purchase_input.py

# PostgreSQL integration tests
# N/A — persistence is unchanged.

# MCP/API contract tests
# N/A — no transport contract changes.

# Broader backend test suite
uv run pytest

# Migration verification
# N/A — no migration is introduced.
```

Do not add a type-check command merely because the generic task template contains one.

If repository tooling changes before implementation, use the actual configured command rather than preserving stale commands from this specification.

If a required command cannot run in the available environment, document:

1. the command that should have been run;
2. why it could not be run;
3. what verification was performed instead;
4. the remaining risk.

Never weaken, skip, or rewrite a failing test merely to make verification green unless the test is demonstrably incorrect because the required behaviour changed; explain that case explicitly.

---

## Completion report

When implementation is complete, provide a concise report containing:

### Changed

Summarise:

- the new `CheckPurchaseRequest` contract;
- validation semantics for identity strings, date, and optional price;
- any README documentation added.

### Database and migrations

`None`.

### API/MCP contracts

`None`.

No public REST or MCP transport is introduced by PR 8.

### Tests and verification

List:

- tests added or updated;
- verification commands actually run;
- their results.

Do not claim an unrun command passed.

### External configuration

`None`.

### Deviations

Describe any meaningful deviation from this task specification and why it was necessary.

Use `None` when there were no deviations.

### Remaining risks or follow-up

Expected follow-up work includes later PRs for:

- canonical purchase identity resolution orchestration;
- structured `check_purchase` result contract;
- promotion candidate selection;
- deterministic eligibility evaluation;
- REST and MCP adapters sharing the same application use case;
- explicit currency support if the product expands beyond the current UK/GBP contract.

Do not implement those follow-ups inside PR 8.
