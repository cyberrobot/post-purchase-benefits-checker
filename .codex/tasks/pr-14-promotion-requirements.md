# PR 14 — Promotion Requirements

## Repository state

**Expected branch:**  
`pr14-promotion-requirements`

**Base branch:**  
`main`

**Dependencies:**

- PR 3 — Core Promotion Schema: merged; introduced `requirements`, `Requirement`, and the initial requirement classifications.
- PR 5 — Benefit Model: merged; provides the closest precedent for introducing a persistence-independent typed domain model over an existing persisted classification.
- PR 13 — Relative & Delayed Claim Windows: merged; current Alembic head is `0005_relative_claim_windows`.
- Existing PostgreSQL, SQLAlchemy 2, Alembic, pytest, Ruff, and Testcontainers backend foundation.
- No new runtime package, external provider, worker, queue, cache, or infrastructure dependency.

### Read first

Before making changes, read:

- `AGENTS.md`
- `.codex/tasks/TEMPLATE.md`
- `.codex/tasks/pr-3-core-promotion-schema.md`
- `.codex/tasks/pr-5-benefit-model.md`
- `.codex/tasks/pr-13-relative-delayed-claim-windows.md`
- `backend/README.md`
- `backend/app/domain/benefits.py`
- `backend/app/db/models/core.py`
- `backend/app/application/promotions.py`
- `backend/app/db/repositories/promotions.py`
- `backend/migrations/versions/0002_core_promotion_schema.py`
- `backend/migrations/versions/0005_relative_delayed_claim_windows.py`
- `backend/tests/unit/test_benefits.py`
- `backend/tests/integration/test_core_promotion_schema.py`
- `backend/tests/integration/test_postgres_migrations.py`
- `.github/workflows/backend.yml`

If a more narrowly scoped `AGENTS.md` exists on the implementation branch, read and follow it.

### Primary change area

Domain model plus a small additive promotion-requirements persistence evolution.

PR 14 introduces the canonical domain representation of evidence and actions a customer must provide or complete when claiming a promotion.

The existing PR 3 persistence model must be extended rather than replaced.

### Canonical implementation examples

Treat these as the preferred implementation references:

- `backend/app/domain/benefits.py`
  - string-backed domain classifications;
  - immutable domain values;
  - persistence-independent validation.
- `backend/tests/unit/test_benefits.py`
  - enum stability;
  - immutability;
  - unsupported classification coverage.
- `backend/app/db/models/core.py::Requirement`
  - existing requirement persistence representation.
- `backend/app/db/models/core.py::PromotionVariant`
  - requirements belong to promotion variants.
- `backend/migrations/versions/0002_core_promotion_schema.py`
  - original `requirements` table and `ck_requirements_type`.
- `backend/tests/integration/test_core_promotion_schema.py`
  - existing PostgreSQL requirement constraint and graph coverage.
- `backend/tests/integration/test_postgres_migrations.py`
  - migration upgrade/downgrade conventions.

Do not introduce a second requirements table or generic rule engine.

### Relevant symbols

Inspect at minimum:

- `app.db.models.Requirement`
- `app.db.models.PromotionVariant`
- `app.domain.benefits.Benefit`
- `app.domain.benefits.BenefitType`
- `ck_requirements_type`
- the `requirements` relationship on `PromotionVariant`
- the `graph` fixture in `test_core_promotion_schema.py`
- current Alembic head
- current backend verification commands

### Expected change surface

Expected additions or updates include:

```text
backend/app/domain/requirements.py
backend/app/db/models/core.py
backend/migrations/versions/
backend/tests/unit/test_requirements.py
backend/tests/integration/test_core_promotion_schema.py
backend/tests/integration/test_postgres_migrations.py
backend/README.md
```

Expected migration from the current repository state:

```text
backend/migrations/versions/0006_promotion_requirements.py
```

The expected revision ID is conceptually:

```text
0006_promotion_requirements
```

Codex must verify the actual Alembic head before creating it.

No application repository change is expected merely to introduce the domain model. If repository state has gained a canonical promotion-variant read contract before implementation begins, use that contract rather than creating a parallel repository solely for this PR.

### Excluded areas

Do not implement:

- uploading receipts;
- storing receipt images or files;
- storing claimant serial numbers;
- storing claimant IMEI values;
- storing invoice documents;
- storing barcode images or scanned barcode values;
- storing installation photographs;
- claim submission records;
- claim-processing workflows;
- customer document storage;
- OCR;
- image analysis;
- evidence verification;
- serial-number verification;
- barcode validation;
- IMEI validation;
- registration with manufacturers;
- installation verification;
- conditional requirement rules;
- requirement completion state;
- requirement satisfaction evaluation;
- changes to eligibility classification;
- changes to `check_purchase`;
- promotion candidate matching changes;
- promotion publication completeness rules;
- claim-window changes;
- benefit/reward calculation;
- ingestion or scraping;
- AI/LLM extraction;
- REST routes;
- FastAPI schemas;
- MCP tools;
- frontend behaviour;
- generic rules DSLs;
- arbitrary JSON requirement payloads;
- executable expressions;
- native PostgreSQL enum types.

PR 14 models **what a promotion requires**. It does not collect, verify, or evaluate the customer's actual evidence.

### Unknowns Codex must verify

Before implementation verify:

- `requirements` still belongs to `promotion_variants`.
- `Requirement` still contains:
  - `promotion_variant_id`;
  - `requirement_type`;
  - `description`.
- `ck_requirements_type` still permits exactly:
  - `receipt`;
  - `serial_number`;
  - `registration`;
  - `invoice`;
  - `barcode`;
  - `imei`.
- no requirement domain model has already been introduced.
- no installation-evidence classification already exists.
- duplicate requirement classifications within one variant are still representable.
- `description` remains nullable.
- current Alembic head is still `0005_relative_claim_windows`.
- no configured backend type-check command exists unless repository configuration has changed.
- CI still runs Ruff and pytest using the commands currently documented in `backend/README.md` and `.github/workflows/backend.yml`.

Do not create duplicate concepts when equivalent functionality already exists.

---

## Objective

Introduce a canonical structured domain representation for promotion claim requirements.

After PR 14, backend domain code must be able to represent requirements such as:

```text
receipt
serial number
product registration
invoice
barcode
IMEI
installation evidence
```

using stable machine-readable classifications rather than deriving meaning from free-form descriptions.

The model must distinguish the structured requirement classification from optional human-readable instructions.

For example:

```text
type: receipt
description: Upload a clear copy of the original purchase receipt.
```

or:

```text
type: registration
description: Register the appliance with the manufacturer before submitting the claim.
```

or:

```text
type: installation_evidence
description: Provide evidence that the product was installed by an approved installer.
```

PR 14 is complete when:

- a canonical requirement domain model exists;
- all existing PR 3 requirement classifications remain supported;
- `installation_evidence` becomes a supported structured classification;
- the persisted PostgreSQL constraint and domain classification remain aligned;
- unsupported classifications fail explicitly;
- existing requirement rows are preserved;
- requirements remain associated with promotion variants;
- no claimant evidence or claim-processing workflow is introduced.

---

## Architecture and invariants

Preserve the existing architecture:

```text
published promotion variant
        ↓
structured requirement definitions
        ↓
Requirement domain values
        ↓
future purchase/claim presentation or orchestration
```

Requirements describe the promotion's claim process.

They do not themselves determine purchase eligibility.

### Required invariants

1. **Requirements belong to promotion variants.**

   Retain the existing relationship:

   ```text
   Promotion
       ↓
   PromotionVariant
       ↓
   Requirement
   ```

   Do not move requirements onto the manufacturer, product, promotion, purchase, or benefit model.

2. **Requirement classification is structured.**

   Meaning must come from a controlled requirement type, not by parsing `description`.

3. **Existing classifications remain valid.**

   Preserve:

   ```text
   receipt
   serial_number
   registration
   invoice
   barcode
   imei
   ```

4. **Add installation evidence explicitly.**

   Add:

   ```text
   installation_evidence
   ```

5. **Do not remove IMEI merely because it is not named in the PR title.**

   It is already part of the persisted PR 3 contract and remains supported.

6. **Use stable lower-case snake-case persisted values.**

   Python member names should conceptually be:

   ```text
   RECEIPT
   SERIAL_NUMBER
   REGISTRATION
   INVOICE
   BARCODE
   IMEI
   INSTALLATION_EVIDENCE
   ```

7. **Requirement descriptions are instructions, not executable rules.**

   `description` may explain what the claimant needs to provide or do.

   Runtime code must not inspect or parse the prose to infer:

   - eligibility;
   - requirement type;
   - conditionality;
   - claim timing;
   - validation behaviour.

8. **Actual claimant evidence is not part of this model.**

   A requirement such as:

   ```text
   serial_number
   ```

   means a serial number will be required.

   It does not store:

   ```text
   ABC123456
   ```

9. **Requirements are definitions, not completion state.**

   Do not add fields such as:

   ```text
   completed
   supplied
   verified
   accepted
   rejected
   uploaded_at
   ```

10. **Evidence and actions share one focused model.**

    `receipt`, `invoice`, and `installation_evidence` describe evidence.

    `registration` describes an action.

    There is currently no runtime behaviour requiring a separate persisted `requirement_kind` or evidence/action discriminator.

    Do not duplicate classification state merely to label these groups.

11. **Multiple requirements per variant remain supported.**

    A promotion may require, for example:

    ```text
    receipt
    serial_number
    registration
    ```

    simultaneously.

12. **Do not introduce uniqueness that the current schema does not require.**

    More than one requirement with the same classification may remain representable when the source terms genuinely contain separate instructions.

    Do not add a speculative unique constraint on:

    ```text
    (promotion_variant_id, requirement_type)
    ```

13. **Descriptions remain optional.**

    Classification alone remains sufficient to represent a structured requirement.

14. **Controlled extensibility remains explicit.**

    Future requirement types require:

    - a domain classification;
    - persistence-constraint alignment;
    - migration when necessary;
    - tests.

    Unknown strings must not silently become an `OTHER` requirement.

15. **Requirements do not alter eligibility in PR 14.**

    Their existence must not change:

    ```text
    ELIGIBLE
    POTENTIALLY_ELIGIBLE
    NOT_ELIGIBLE
    CLAIM_NOT_YET_OPEN
    EXPIRED
    ```

16. **No external or model-provider call is required.**

    Construction and classification are deterministic plain Python behaviour.

---

## API and contract changes

No public REST, MCP, or OpenAPI contract changes.

No `CheckPurchaseRequest` change.

No eligibility-result contract change.

### Requirement classification contract

Introduce a stable string-backed classification in:

```text
backend/app/domain/requirements.py
```

conceptually:

```python
class RequirementType(StrEnum):
    RECEIPT = "receipt"
    SERIAL_NUMBER = "serial_number"
    REGISTRATION = "registration"
    INVOICE = "invoice"
    BARCODE = "barcode"
    IMEI = "imei"
    INSTALLATION_EVIDENCE = "installation_evidence"
```

Exact implementation should follow the established `BenefitType` conventions.

### Requirement domain value

Introduce an immutable persistence-independent value conceptually equivalent to:

```python
@dataclass(frozen=True, slots=True)
class Requirement:
    requirement_type: RequirementType
    description: str | None = None
```

Construction must:

- convert a supported persisted string into the corresponding `RequirementType`;
- preserve an existing `RequirementType`;
- reject unsupported classifications explicitly;
- require `description` to be `str | None`;
- perform no persistence access;
- perform no network access;
- perform no eligibility evaluation;
- perform no description parsing.

Do not introduce subclasses such as:

```text
ReceiptRequirement
SerialNumberRequirement
InvoiceRequirement
InstallationEvidenceRequirement
```

solely to represent the different classifications.

The common value is sufficient until classifications require genuinely different structured behaviour.

---

## Domain and application behaviour

### Supported classifications

The canonical set after PR 14 is:

| Domain member | Persisted value | Meaning |
| --- | --- | --- |
| `RECEIPT` | `receipt` | Proof-of-purchase receipt is required |
| `SERIAL_NUMBER` | `serial_number` | Product serial number is required |
| `REGISTRATION` | `registration` | Registration action is required |
| `INVOICE` | `invoice` | Invoice or equivalent proof is required |
| `BARCODE` | `barcode` | Product/package barcode is required |
| `IMEI` | `imei` | Device IMEI is required |
| `INSTALLATION_EVIDENCE` | `installation_evidence` | Evidence of installation is required |

These classifications identify the requirement.

They do not specify how the requirement is validated.

### Description semantics

Valid examples:

```python
Requirement(
    RequirementType.RECEIPT,
    "Upload the original purchase receipt.",
)
```

```python
Requirement(
    RequirementType.REGISTRATION,
    "Register the product before submitting the cashback claim.",
)
```

```python
Requirement(
    RequirementType.INSTALLATION_EVIDENCE,
    "Provide an installer invoice or installation certificate.",
)
```

A missing description is valid:

```python
Requirement(RequirementType.SERIAL_NUMBER)
```

The description is display/instructional text.

Do not extract structured behaviour from it.

### Unsupported classifications

Examples such as:

```text
proof
document
photo
installer
warranty_card
other
RECEIPT
```

must not silently map to one of the supported classifications.

If future source ingestion encounters an unsupported requirement, that future ingestion/publication boundary must retain or reject the candidate appropriately rather than inventing a supported requirement.

PR 14 does not implement that workflow.

### Evidence versus claimant data

The model represents:

```text
Requirement(type=serial_number)
```

not:

```text
serial_number="ABC-123"
```

Likewise it represents:

```text
Requirement(type=receipt)
```

not receipt contents, file paths, object-storage URLs, images, extracted purchase values, or OCR results.

### Relation to eligibility rules

Promotion requirements are not PR 10 eligibility rules.

For example:

```text
purchase must be from Retailer X
```

is an eligibility restriction.

```text
submit the receipt when claiming
```

is a claim requirement.

Do not model the latter as a `PromotionEligibilityRules` entry.

### Relation to claim windows

Requirements and claim windows are independent.

For example:

```text
claim within 30 days
```

defines **when** the customer may claim.

```text
provide receipt and serial number
```

defines **what** the customer needs when claiming.

PR 14 must not combine these concepts.

### Relation to benefits

Benefits describe what the promotion provides:

```text
cashback
extended warranty
free gift
```

Requirements describe what the customer must supply or do:

```text
receipt
registration
installation evidence
```

Do not add requirement information to `Benefit`.

---

## Persistence, transactions, and migrations

The existing `requirements` table remains the source of persisted requirement definitions.

### Existing table

Retain the current shape:

```text
requirements
├── id
├── promotion_variant_id
├── requirement_type
├── description
├── created_at
└── updated_at
```

No new column is required.

No new table is required.

No new index is expected.

### Requirement type constraint

Update:

```text
ck_requirements_type
```

from the current supported set:

```text
receipt
serial_number
registration
invoice
barcode
imei
```

to:

```text
receipt
serial_number
registration
invoice
barcode
imei
installation_evidence
```

Update both:

- SQLAlchemy metadata;
- Alembic schema state.

Do not edit migration `0002_core_promotion_schema.py`.

Create a new migration from the current head.

### Expected migration

Conceptually:

```text
0006_promotion_requirements
```

with:

```text
down_revision = "0005_relative_claim_windows"
```

Codex must verify both values before implementation.

### Upgrade behaviour

Upgrade must:

1. preserve all existing requirement rows;
2. remove/replace the existing `ck_requirements_type`;
3. recreate it with the new allowed set;
4. add no default;
5. rewrite no existing requirement value;
6. create no installation-evidence rows automatically.

Existing values must remain byte-for-byte unchanged.

### Downgrade behaviour

Downgrade restores the pre-PR-14 allowed set.

It must never silently:

- delete `installation_evidence` requirements;
- convert them to another type;
- rewrite them into description text.

If no `installation_evidence` rows exist, downgrade must restore the previous constraint successfully.

If `installation_evidence` rows exist, downgrade must fail safely rather than destroy or reinterpret them.

The failed downgrade must leave the schema/data in a usable PR-14 state.

A clear migration failure is preferable to hidden data loss.

### Foreign keys and deletion

Existing behaviour remains unchanged:

```text
requirements.promotion_variant_id
    → promotion_variants.id
```

Variant deletion continues to cascade owned requirement rows.

No reference-data deletion semantics change.

### Transaction behaviour

Domain construction has no transaction.

Normal requirement writes continue to rely on caller-owned SQLAlchemy transaction behaviour.

A database rejection of an unsupported requirement type must roll back normally without leaving a partially persisted requirement.

---

## External services and network access

None.

PR 14 introduces no:

- HTTP requests;
- manufacturer API calls;
- object storage;
- OCR provider;
- AI/model provider;
- registration provider;
- serial-number service;
- barcode service.

---

## Security and privacy

PR 14 defines promotion metadata, not claimant evidence.

The implementation must not introduce storage or logging of:

- receipt contents;
- invoice contents;
- customer names or addresses;
- serial-number values;
- IMEI values;
- scanned barcodes;
- installation photographs;
- installation certificates belonging to a claimant;
- payment information.

The requirement `description` contains promotion instructions only.

Treat description text as data. Do not execute it, interpolate it into SQL, or use it as a rule/program expression.

No authentication or authorization boundary changes are introduced.

---

## Configuration and deployment

None.

No new:

- environment variables;
- secrets;
- runtime packages;
- Docker changes;
- Railway configuration;
- workers;
- scheduled jobs;
- health/readiness behaviour.

The database migration must be applied before code depends on `installation_evidence` being accepted by PostgreSQL.

---

## Observability and operations

No new telemetry is required.

Expected domain validation failures do not require new metrics, traces, or logging infrastructure.

Database constraint failures continue through existing persistence/transaction behaviour.

Do not add logging solely for successful creation of requirement domain values.

Do not log future claimant evidence values under this task.

---

## Failure, consistency, and recovery

### Unsupported domain classification

Given:

```text
requirement_type = "unsupported"
```

domain construction must fail explicitly.

It must not fall back to:

```text
receipt
other
unknown
```

### Unsupported persisted classification

A direct PostgreSQL write using a value outside the supported set must fail against:

```text
ck_requirements_type
```

### Existing data during upgrade

All existing:

```text
receipt
serial_number
registration
invoice
barcode
imei
```

rows must survive upgrade unchanged.

### Migration failure

Constraint replacement must occur transactionally according to PostgreSQL/Alembic conventions.

A failed migration must not leave `ck_requirements_type` missing while reporting a successful migration revision.

### Downgrade containing installation evidence

If an `installation_evidence` row exists, downgrade must fail rather than delete or reinterpret the row.

The installation requirement and PR-14 schema must remain intact after rollback.

---

## Acceptance criteria

### Behaviour

- [ ] `RequirementType` exists as the canonical structured requirement classification.
- [ ] `Requirement` exists as an immutable domain value.
- [ ] Existing persisted classifications remain supported.
- [ ] `installation_evidence` is supported.
- [ ] Supported persisted strings map deterministically to their domain classification.
- [ ] Unsupported classifications fail explicitly.
- [ ] Optional descriptions are preserved as display/instruction text only.
- [ ] Requirements remain independent of eligibility and claim-window evaluation.
- [ ] No claimant evidence, completion state, verification, or submission workflow is introduced.

### Data and consistency

- [ ] `requirements` remains associated with promotion variants.
- [ ] Existing requirement rows survive migration unchanged.
- [ ] PostgreSQL accepts every canonical `RequirementType`.
- [ ] PostgreSQL rejects unsupported values.
- [ ] `ck_requirements_type` and `RequirementType` contain the same supported values.
- [ ] No speculative uniqueness constraint is added.
- [ ] No new requirement table or JSON rule representation is introduced.
- [ ] Migration upgrade succeeds against real PostgreSQL.
- [ ] Downgrade succeeds when no `installation_evidence` data exists.
- [ ] Downgrade refuses to silently lose existing `installation_evidence` data.
- [ ] Re-upgrade succeeds after a valid downgrade.

### Security

- [ ] No claimant receipt, invoice, serial number, IMEI, barcode, or installation evidence value is persisted by this PR.
- [ ] Requirement descriptions remain passive text.
- [ ] No secrets or personal evidence are added to logs.
- [ ] No external network/provider boundary is introduced.

### Operations

- [ ] No new environment configuration is required.
- [ ] Existing health/readiness behaviour remains unchanged.
- [ ] No new external services are required.

### Code quality

- [ ] Domain code does not depend on SQLAlchemy, FastAPI, Alembic, networking, or AI libraries.
- [ ] Existing architecture and dependency direction are preserved.
- [ ] No generic requirement/rules framework is introduced.
- [ ] No unrelated refactor is included.
- [ ] Ruff checks pass.
- [ ] Targeted tests pass.
- [ ] PostgreSQL integration/migration tests pass.
- [ ] Full backend pytest suite passes.

---

## Tests to add or update

### Unit tests

Add:

```text
backend/tests/unit/test_requirements.py
```

Cover at minimum:

1. exact stable classification values:

   ```text
   receipt
   serial_number
   registration
   invoice
   barcode
   imei
   installation_evidence
   ```

2. enum/string conversion;
3. construction from every supported `RequirementType`;
4. construction from supported persisted string values;
5. unsupported classifications;
6. case-sensitive rejection where appropriate;
7. optional description;
8. invalid non-string descriptions;
9. immutable/frozen behaviour;
10. slots/no accidental mutable instance dictionary, consistent with the current domain-value convention;
11. no parsing or transformation of description text.

### PostgreSQL integration tests

Update:

```text
backend/tests/integration/test_core_promotion_schema.py
```

Cover:

- all canonical requirement types persist successfully;
- `installation_evidence` persists successfully;
- unsupported requirement classifications still fail with `ck_requirements_type`;
- persisted values reconstruct equivalent domain `Requirement` values;
- the existing promotion graph can contain the complete supported requirement set;
- existing cascade/FK behaviour remains unchanged.

Update:

```text
backend/tests/integration/test_postgres_migrations.py
```

Cover:

- current migration head is the new PR-14 revision;
- upgrade from `0005_relative_claim_windows`;
- pre-existing requirement rows are preserved;
- `installation_evidence` becomes accepted after upgrade;
- unsupported values remain rejected;
- SQLAlchemy metadata and migrated schema remain aligned;
- downgrade with only legacy requirement types succeeds and restores the old constraint;
- re-upgrade succeeds;
- downgrade does not silently discard an existing `installation_evidence` requirement.

Do not replace these PostgreSQL checks with SQLite tests.

### API/application tests

N/A.

No application use case or public transport contract changes.

### MCP contract tests

N/A.

### External-boundary tests

N/A.

No external boundary is introduced.

---

## Verification commands

Run from `backend/`.

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
N/A on the current repository state.
```

No backend type-check command is currently configured.

Codex must verify this has not changed before completion.

### Targeted unit tests

```bash
uv run pytest tests/unit/test_requirements.py
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
  tests/unit/test_requirements.py \
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

Do not claim commands passed unless they were actually run.

If Docker/PostgreSQL is unavailable, report:

1. the command that could not run;
2. why;
3. what was verified instead;
4. the remaining migration risk.

Never weaken migration or constraint tests merely to make verification green.

---

## Completion report

When implementation is complete, provide:

### Changed

Summarise:

- requirement domain model;
- supported classifications;
- `installation_evidence`;
- persistence-constraint alignment;
- documentation changes.

### Database and migrations

State:

- migration revision;
- `ck_requirements_type` change;
- upgrade preservation behaviour;
- downgrade behaviour.

### API/MCP contracts

```text
None.
```

### Tests and verification

List:

- unit tests added;
- PostgreSQL tests updated;
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

Potential future work is explicitly outside PR 14 and may include:

- requirement publication completeness;
- exposing requirements in purchase-check results;
- claim-submission models;
- customer evidence upload/storage;
- requirement completion state;
- evidence verification;
- conditional requirements;
- structured installation/registration rules.

Do not implement these merely because the new domain model makes them possible.