# PR 6 — Promotion Source Provenance

## Repository state

**Expected branch:**  
`pr6-promotion-source-provenance`

**Base branch:**  
`main`

**Dependencies:**

- PR 1 — Project Foundation: merged.
- PR 3 — Core Promotion Schema: merged and provides `sources` and `promotion_sources`.
- PR 4 — Promotion Lifecycle & History: merged and provides the `review → active` publication transition boundary.
- PR 5 — Benefit Model is present on current `main` but is not a functional dependency of this task.
- Existing PostgreSQL, SQLAlchemy 2, Alembic, and Testcontainers foundation.
- Existing source roles already include `primary`, `terms`, `claim`, and `supporting`.
- Existing source records already contain URL, source type, retrieval timestamp, and optional verification timestamp.
- No REST, MCP, source-fetching, ingestion, worker, scheduler, or frontend dependency.

### Read first

Before making changes, read:

- `AGENTS.md`
- nearest scoped `AGENTS.md`, if one exists
- `.codex/tasks/TEMPLATE.md`
- `.codex/tasks/pr-3-core-promotion-schema.md`
- `.codex/tasks/pr-4-promotion-lifecycle-history.md`
- `.codex/tasks/pr-5-benefit-model.md`
- `backend/README.md`
- `backend/app/application/promotions.py`
- `backend/app/domain/promotion_lifecycle.py`
- `backend/app/db/models/core.py`
- `backend/app/db/repositories/promotions.py`
- `backend/migrations/versions/0002_core_promotion_schema.py`
- `backend/tests/unit/test_promotion_lifecycle.py`
- `backend/tests/integration/test_core_promotion_schema.py`
- `backend/tests/integration/test_promotion_lifecycle.py`
- `backend/tests/conftest.py`
- `backend/pyproject.toml`

### Primary change area

Promotion publication validation and source provenance.

PR 3 established the persistence representation for source evidence. PR 4 established the lifecycle operation that publishes a promotion through:

```text
review → active
```

PR 6 connects those two capabilities.

A promotion must not become published unless the required official source provenance exists and has been verified.

### Current repository state

The existing persistence model already provides:

```text
sources.url
sources.source_type
sources.retrieved_at
sources.verified_at

promotion_sources.promotion_id
promotion_sources.source_id
promotion_sources.role
```

Supported source types are:

```text
web_page
pdf
other
```

Supported source roles are:

```text
primary
terms
claim
supporting
```

Existing role semantics from PR 3 are:

- `primary` — principal official promotion page/document;
- `terms` — official terms and conditions;
- `claim` — official claim/registration destination;
- `supporting` — additional official evidence.

The `claim` role is already the canonical representation of a claim URL.

The schema deliberately allows repeated retrieval of the same URL as separate `Source` records so historical evidence is not overwritten.

The database also already enforces:

```text
verified_at >= retrieved_at
```

when `verified_at` is present.

Do **not** introduce duplicate fields such as:

```text
promotions.source_url
promotions.claim_url
promotions.source_type
promotions.retrieved_at
promotions.verified_at
```

unless repository state has materially changed and the existing normalized model can no longer satisfy the requirement.

The missing behaviour is publication enforcement: PR 4 currently allows `review → active` without examining source provenance.

### Canonical implementation examples

Use:

- `PromotionStatus` and `validate_transition()` in `backend/app/domain/promotion_lifecycle.py`;
- `change_promotion_status()` in `backend/app/application/promotions.py`;
- `PromotionRepository` as the application-owned persistence boundary;
- `SqlAlchemyPromotionRepository` in `backend/app/db/repositories/promotions.py`;
- `Source` and `PromotionSource` in `backend/app/db/models/core.py`;
- existing PostgreSQL/Testcontainers fixtures;
- existing lifecycle concurrency and transaction behaviour.

Do not introduce a second publication service that bypasses `change_promotion_status()` solely for this task.

Publication provenance validation should compose with the existing lifecycle operation.

### Relevant symbols

Inspect before editing:

- `PromotionStatus`
- `validate_transition`
- `change_promotion_status`
- `PromotionRepository`
- `PromotionRecord`
- `SqlAlchemyPromotionRepository`
- `promotion_transaction`
- `Promotion`
- `Source`
- `PromotionSource`
- `ck_sources_type`
- `ck_sources_verification_dates`
- `ck_promotion_sources_role`
- `test_application_allowed`
- `test_application_errors`
- `test_application_commit_is_visible_in_new_session`
- `test_retirement_preserves_entire_graph`
- `test_complete_graph_and_metadata`

### Expected change surface

Expected additions or changes may include:

```text
backend/app/domain/
backend/app/application/promotions.py
backend/app/db/repositories/promotions.py
backend/tests/unit/
backend/tests/integration/
backend/README.md
```

A focused domain module such as:

```text
backend/app/domain/promotion_provenance.py
```

is appropriate if it keeps provenance classification and validation separate from lifecycle transition mechanics.

A database migration is **not expected** because PR 3 already persists every field required by this PR.

If implementation discovers that a schema change is genuinely required, Codex must explain why the existing normalized `sources` / `promotion_sources` representation is insufficient before adding a migration.

### Excluded areas

Do not implement:

- REST endpoints;
- MCP tools;
- source discovery;
- HTTP retrieval;
- scraping;
- PDF downloading;
- manufacturer-domain allow-lists;
- DNS or hostname verification;
- SSRF-sensitive network operations;
- AI extraction;
- ingestion pipelines;
- automatic promotion discovery;
- full promotion completeness validation;
- product applicability validation;
- benefit completeness validation;
- purchase eligibility;
- reward calculation;
- claim-window calculation;
- promotion versioning;
- source-content hashing;
- source-content archival;
- source mutation APIs;
- frontend/UI;
- authentication/authorization;
- background workers;
- scheduled verification;
- automatic re-verification;
- automatic expiration.

This PR adds the **source-provenance publication prerequisite only**.

Other publication completeness rules may be added by later PRs and must be able to compose with this validation.

### Unknowns Codex must verify

Before implementation:

- Verify current `main` still contains the PR 3 source schema.
- Verify current `main` still contains the PR 4 lifecycle application operation.
- Verify `review → active` remains the only normal candidate-to-published transition.
- Verify source roles and source types have not changed.
- Verify the current Alembic head.
- Verify whether a scoped backend `AGENTS.md` has been added.
- Verify no publication-validation abstraction has already been introduced.
- Verify no source repository/application contract has already been introduced.
- Verify transaction ownership remains with `promotion_transaction`.
- Verify existing test and verification commands from repository configuration.

Do not guess when repository state can answer the question.

---

## Objective

Require complete, verified official source provenance before a promotion can be published.

After this PR:

- the principal official promotion source is represented by the existing `primary` source association;
- the official claim destination is represented by the existing `claim` source association;
- source type has one canonical application/domain representation aligned with persisted values;
- source roles used by publication provenance have one canonical application/domain representation where appropriate;
- publication provenance can be loaded through the application-owned persistence boundary without exposing ORM objects;
- a `review → active` transition validates required provenance before changing status;
- publication fails when required provenance is missing or invalid;
- publication failure leaves the promotion in `review`;
- a published promotion has an official source URL;
- a published promotion has a supported source type;
- a published promotion has a retrieval timestamp;
- a published promotion has a verification timestamp;
- a published promotion has an official claim URL;
- sources used to establish publication provenance are verified;
- expiration and archival continue retaining existing provenance;
- historical `expired` promotions therefore retain the provenance established when they were published;
- candidate promotions may continue to contain missing or incomplete provenance;
- no source URL or provenance fields are duplicated onto `promotions`;
- no network call or LLM call is required to publish or validate stored provenance.

Completion means publication provenance validation, application/repository integration, transaction behaviour, and PostgreSQL integration coverage are implemented and passing.

---

## Architecture and invariants

Preserve the repository dependency direction:

```text
transport
    ↓
application
    ↓
domain
    ↓
application-owned persistence boundary
    ↓
SQLAlchemy / PostgreSQL
```

No transport implementation is required.

Task-specific invariants:

1. Source provenance remains normalized through `sources` and `promotion_sources`.
2. A `Source` represents one retrieved evidence record, not merely one globally unique URL.
3. Repeated retrievals of the same URL remain representable as separate `Source` records.
4. `primary` identifies the principal official promotion source used for publication provenance.
5. `claim` identifies the official claim/registration destination.
6. Publication must not infer officiality from URL text, hostname naming, title text, or source contents.
7. A source association marked `primary` or `claim` is treated as curated official provenance only after application publication validation.
8. `review → active` must fail unless required source provenance exists.
9. Candidate states may contain incomplete provenance.
10. `active` represents a promotion that has passed this source-provenance publication gate.
11. `expired` is previously published data and must retain the source provenance that supported publication.
12. `archived` may represent either unpublished candidate data or formerly published data; provenance must be retained when present, but archived status alone does not imply that publication provenance once existed.
13. Publication provenance validation must be deterministic.
14. Publication provenance validation must not invoke an LLM.
15. Publication provenance validation must not perform an outbound network request.
16. Publication must not copy source URLs or timestamps into duplicate promotion-level columns.
17. `verified_at` used for publication must be non-null.
18. Verification must not predate retrieval.
19. Published provenance timestamps remain timezone-aware timestamps; do not reduce them to lossy date-only values.
20. Unsupported source types fail explicitly.
21. Missing claim provenance does not silently become an empty or `NULL` claim URL on a published promotion.
22. Missing primary provenance does not fall back to a `terms` or `supporting` source.
23. The publication operation remains atomic with the lifecycle state change.
24. Failed publication validation must perform no lifecycle write.
25. Existing retirement behaviour must continue to retain source associations and evidence records.

---

## API and contract changes

No REST or MCP contract changes.

This PR introduces internal domain/application and persistence contracts only.

### Source type

Define one canonical application/domain representation for the persisted values:

```text
web_page
pdf
other
```

A Python `StrEnum` or equivalent is appropriate.

Persisted values must remain exactly compatible with `ck_sources_type`.

Unknown source types must fail explicitly rather than becoming `other` automatically.

`other` is an explicit persisted classification, not a fallback for invalid input.

### Source role

Where publication logic requires a typed source-role representation, use stable values matching persistence:

```text
primary
terms
claim
supporting
```

Do not invent parallel names such as:

```text
official
registration
main
evidence
```

for the same concepts.

### Provenance application record

Introduce an application-owned immutable source/provenance representation equivalent to:

```text
source_id
role
url
source_type
retrieved_at
verified_at
```

Exact naming may follow repository conventions.

Do not return SQLAlchemy `Source` or `PromotionSource` objects through the application boundary.

### Repository capability

Extend the promotion persistence boundary with a capability equivalent to:

```text
list_promotion_sources(promotion_id)
```

or:

```text
get_promotion_provenance(promotion_id)
```

It must retrieve source associations and the source evidence required for deterministic publication validation.

Do not introduce a generic source CRUD repository solely for this task.

---

## Domain and application behaviour

### Published provenance model

The domain/application layer should be able to derive publication provenance equivalent to:

```text
official_source_url
source_type
retrieved_at
verified_at
claim_url
```

from normalized source associations.

The canonical official source is supplied by a source associated with:

```text
role = primary
```

The canonical claim URL is supplied by a source associated with:

```text
role = claim
```

The persisted source records remain the source of truth.

The derived publication representation must not become another persisted copy.

### Publication provenance requirements

Before `review → active` succeeds, validation must establish all of the following.

#### Official source

A `primary` source association exists.

Its source must provide:

- non-empty URL;
- supported source type;
- timezone-aware `retrieved_at`;
- non-null timezone-aware `verified_at`;
- `verified_at >= retrieved_at`.

This source supplies:

```text
official_source_url
source_type
retrieved_at
verified_at
```

for the published provenance view.

#### Claim source

A `claim` source association exists.

Its source must provide:

- non-empty claim URL;
- supported source type;
- timezone-aware `retrieved_at`;
- non-null timezone-aware `verified_at`;
- `verified_at >= retrieved_at`.

The claim source supplies:

```text
claim_url
```

The claim source may have the same URL value as another source record where that accurately represents the promotion.

Do not require URL values themselves to be globally unique.

### Multiple sources with the same role

The current schema permits multiple source associations with the same role.

Do not add an arbitrary database uniqueness rule merely to simplify this PR.

Publication provenance must nevertheless be deterministic.

Codex must inspect repository state and implement one explicit policy rather than relying on incidental SQL ordering.

Preferred policy for this PR:

- exactly one `primary` association must be eligible to satisfy publication;
- exactly one `claim` association must be eligible to satisfy publication;
- multiple `terms` and `supporting` sources remain allowed.

If multiple `primary` or multiple `claim` associations are present and the repository has no existing canonical-selection mechanism, publication must fail as ambiguous rather than silently choosing one.

Do not select a source by incidental insertion order, UUID order, relationship order, or database row order.

### URL semantics

This PR validates stored provenance; it does not establish a source-retrieval security boundary.

At minimum, required publication URLs must:

- be strings;
- be non-empty after trimming;
- represent an absolute HTTP or HTTPS URL using deterministic local parsing.

Do not:

- resolve DNS;
- follow redirects;
- contact the URL;
- infer that a hostname belongs to the manufacturer;
- treat page contents as trusted instructions.

Network-level official-source validation belongs to source retrieval/verification work.

Do not rewrite or normalize persisted URLs in a way that loses evidence identity.

### Publication transition

`review → active` is the publication event.

Conceptually:

```text
load promotion
→ validate lifecycle transition
→ load promotion source provenance
→ validate publication provenance
→ conditionally persist review → active
→ commit
```

The provenance check and status transition must occur within the same application transaction.

If provenance validation fails:

```text
status remains review
```

and no lifecycle update is attempted.

### Other lifecycle transitions

Provenance validation is required only when entering `active`.

Transitions such as:

```text
discovered → extracted
extracted → review
review → extracted
discovered → archived
extracted → archived
review → archived
active → expired
active → archived
expired → archived
```

must not become dependent on publication-provenance completeness.

Candidate promotions are explicitly allowed to be incomplete.

### Same-state transitions

Existing same-state idempotency remains unchanged.

For example:

```text
active → active
```

remains a no-op.

This PR must not turn an idempotent same-state request into an implicit re-publication or source re-verification workflow.

### Expired promotions

`active → expired` preserves the complete promotion graph.

Because activation requires provenance, a promotion reaching `expired` through the normal lifecycle path retains:

- official source evidence;
- claim source evidence;
- retrieval timestamps;
- verification timestamps;
- source classifications.

Expiry must not copy, rewrite, or delete provenance.

### Archived promotions

Archival must continue retaining source provenance.

However:

```text
archived
```

does not prove prior publication because candidates may archive without ever reaching `active`.

Do not require all archived promotions to satisfy publication provenance.

### Publication validation error

Introduce an explicit domain/application error for invalid publication provenance.

Names may follow repository conventions, for example:

```text
PromotionProvenanceError
```

or:

```text
PromotionNotPublishable
```

The error must remain distinguishable from:

- promotion not found;
- invalid lifecycle transition;
- lifecycle concurrency conflict;
- database/infrastructure failure.

Use stable reason information where useful for tests and future transport mapping.

Representative provenance failures include:

```text
missing_primary_source
missing_claim_source
ambiguous_primary_source
ambiguous_claim_source
primary_source_unverified
claim_source_unverified
invalid_primary_url
invalid_claim_url
unsupported_source_type
invalid_retrieval_timestamp
invalid_verification_timestamp
```

Exact implementation may consolidate cases where appropriate, but tests must not rely only on fragile exception-message matching.

### Publication completeness boundary

This PR implements only the source-provenance component of publication validation.

It must **not** imply that source provenance alone makes a promotion semantically complete.

Future publication gates may additionally require:

- product applicability;
- promotion variants;
- supported benefits;
- promotion dates;
- retailer semantics;
- structured reward rules;
- claim-window information;
- other eligibility data.

Design the source validation so those checks can later compose with the same `review → active` boundary rather than requiring another publication path.

---

## Persistence, transactions, and migrations

### Existing schema

Use the existing tables:

```text
sources
promotion_sources
promotions
```

Required published provenance is already persisted as:

| Published concept | Existing storage |
| --- | --- |
| Official source URL | `sources.url` linked with `promotion_sources.role = 'primary'` |
| Source type | primary `sources.source_type` |
| Retrieval date/time | primary `sources.retrieved_at` |
| Verification date/time | primary `sources.verified_at` |
| Claim URL | `sources.url` linked with `promotion_sources.role = 'claim'` |

The claim source also retains its own source type, retrieval timestamp, and verification timestamp.

### Database changes

No new table or column is expected.

Do not add duplicate columns to `promotions`.

Do not rewrite migration `0002_core_promotion_schema.py`.

Do not introduce a PostgreSQL native enum.

Do not make `sources.url` globally unique.

Do not delete or collapse repeated source retrieval records.

### Constraints

Continue relying on existing database constraints for:

```text
source_type
source role
verified_at >= retrieved_at
foreign-key integrity
```

Cross-table publication completeness belongs to the application/domain publication boundary rather than a trigger or opaque database procedure.

Do not introduce a PostgreSQL trigger solely to prevent `active` status without provenance.

### Transaction boundary

Publication must remain one transaction.

Conceptually:

```text
read current promotion state
→ read source associations/evidence
→ validate source provenance
→ conditional lifecycle update
→ commit
```

Any failure before commit leaves the promotion unpublished.

### Concurrency

Preserve the conditional lifecycle write introduced by PR 4.

Do not regress to an unconditional:

```sql
UPDATE promotions SET status = 'active'
```

after provenance validation.

If another lifecycle transaction changes the promotion after it was read, retain the existing reconciliation/conflict semantics.

No source-mutation application path is introduced in this PR.

If repository state has gained concurrent source-association mutation before implementation begins, Codex must ensure publication cannot validate one provenance set and commit against a materially different one without conflict or appropriate locking.

Do not introduce distributed locking.

### Migration

A migration is not expected.

Current Alembic head should remain unchanged unless implementation discovers a genuine schema requirement.

If a migration becomes necessary:

- create a new revision from the actual current head;
- do not edit existing deployed revisions;
- explain why the normalized PR 3 model could not satisfy the requirement;
- verify upgrade/downgrade behaviour against PostgreSQL.

### Backfill

No data backfill is expected.

This repository currently establishes publication through application lifecycle behaviour rather than migrating an existing production corpus.

Do not fabricate source provenance for existing records.

Never populate a missing verification timestamp with `created_at`, `retrieved_at`, the migration time, or another guessed value.

---

## External services and network access

None.

PR 6 does not retrieve or verify remote content.

No HTTP client, browser, model provider, scraping library, DNS lookup, or external API is required.

Persisted URLs remain untrusted data.

Publication validation operates only on already stored source evidence.

---

## Security and privacy

This PR handles public promotion/source metadata rather than customer data.

Requirements:

- Treat every persisted URL as untrusted input.
- Do not fetch source or claim URLs during publication.
- Do not resolve or follow redirects.
- Do not execute or deserialize source content.
- Do not infer trust merely because a URL contains a manufacturer name.
- Do not add credentials, cookies, tokens, headers, or provider secrets to provenance records.
- Do not expose SQLAlchemy/database exceptions as publication-domain errors.
- Avoid logging full URLs where they could contain sensitive query parameters or tokens; prefer source IDs and promotion IDs for diagnostics.
- Do not add receipt, customer, payment, address, or other personal data.
- Do not introduce an arbitrary metadata/JSON field as a provenance escape hatch.

No authentication or authorization change is required.

Future source retrieval must separately enforce the SSRF controls defined by repository guidance.

---

## Configuration and deployment

None.

### Environment variables

No new, changed, or removed environment variables.

### Runtime/deployment changes

No intended changes to:

- Docker image;
- Railway/deployment configuration;
- health/readiness behaviour;
- workers;
- cron jobs;
- database connection configuration;
- startup/shutdown lifecycle.

---

## Observability and operations

Use the existing observability stack only where the application currently records comparable failures.

Publication provenance failure is an expected domain rejection, not an infrastructure exception.

Where structured diagnostics are emitted, prefer fields such as:

```text
promotion_id
operation=publish_promotion
result=rejected
reason_code=missing_claim_source
```

Do not log:

- full source documents;
- raw page contents;
- credentials;
- cookies;
- unnecessary full URLs.

Database failures must remain distinguishable from domain provenance rejection and must continue using safe application-facing errors.

No new metrics, tracing system, dashboard, or alert is required solely for this PR.

---

## Failure, consistency, and recovery

### Missing primary source

If `review → active` is requested without a valid `primary` source:

```text
publication rejected
promotion remains review
```

No lifecycle write occurs.

### Missing claim source

If no valid `claim` source exists:

```text
publication rejected
promotion remains review
```

Do not publish with `claim_url = NULL`.

### Unverified source

If required provenance has:

```text
verified_at = NULL
```

publication is rejected.

Do not silently treat retrieval as verification.

### Invalid verification chronology

Existing PostgreSQL constraints reject:

```text
verified_at < retrieved_at
```

Domain/application mapping must not reinterpret this invalid state as valid provenance.

### Ambiguous required role

If multiple sources satisfy `primary` or `claim` and no existing canonical-selection mechanism exists:

```text
publication rejected as ambiguous
```

Do not choose one incidentally.

### Database failure while loading provenance

If the provenance query fails:

- raise the established safe persistence/infrastructure error;
- roll back the application transaction;
- leave status unchanged.

### Database failure while publishing

If provenance validates but the status write or commit fails:

- roll back;
- leave the previously committed status authoritative;
- do not report successful publication.

### Concurrent lifecycle change

Retain PR 4 semantics:

- reconcile if another transaction already produced the requested target state;
- otherwise surface `PromotionConflict`.

Do not silently overwrite the competing state.

### Retirement after publication

`active → expired` and `active → archived` must not delete or rewrite source evidence.

### Retry after provenance rejection

A caller may correct/add source evidence and retry:

```text
review → active
```

The retry must evaluate the current persisted provenance.

A failed earlier attempt must not leave a partial publication marker.

---

## Acceptance criteria

### Behaviour

- [x] `review → active` validates source provenance before changing status.
- [x] A promotion with complete verified provenance can transition from `review` to `active`.
- [x] A promotion missing its `primary` source cannot become active.
- [x] A promotion missing its `claim` source cannot become active.
- [x] A promotion with an unverified required source cannot become active.
- [x] Ambiguous canonical `primary` provenance is rejected.
- [x] Ambiguous canonical `claim` provenance is rejected.
- [x] Invalid required URLs are rejected.
- [x] Unsupported source types are rejected explicitly.
- [x] Publication provenance validation does not perform a network request.
- [x] Publication provenance validation does not invoke an LLM.
- [x] Candidate lifecycle transitions remain usable with incomplete provenance.
- [x] Same-state lifecycle requests remain idempotent.
- [x] Existing lifecycle conflict behaviour remains unchanged.
- [x] Existing active/expired/archive query semantics remain unchanged.

### Provenance

- [x] Every promotion published through the application boundary has an official source URL.
- [x] Every promotion published through the application boundary has a supported source type.
- [x] Every promotion published through the application boundary has a retrieval timestamp.
- [x] Every promotion published through the application boundary has a verification timestamp.
- [x] Every promotion published through the application boundary has an official claim URL.
- [x] Required publication source timestamps are timezone-aware.
- [x] Required publication sources have `verified_at >= retrieved_at`.
- [x] `primary` is the canonical official promotion source role.
- [x] `claim` is the canonical claim URL role.
- [x] `terms` and `supporting` do not silently substitute for missing required roles.
- [x] Expiration retains the complete source provenance.
- [x] Archival retains source provenance that already exists.
- [x] Repeated retrieval of the same URL remains representable.
- [x] Source evidence is not copied into duplicate promotion-level columns.

### Data and consistency

- [x] Existing `sources` and `promotion_sources` remain the source of truth.
- [x] Existing source-type values remain unchanged.
- [x] Existing source-role values remain unchanged.
- [x] Existing source verification constraint remains unchanged.
- [x] No existing migration is rewritten.
- [x] No migration is added unless repository state demonstrates a genuine schema requirement.
- [x] Failed publication validation leaves persisted promotion state unchanged.
- [x] Database failure during publication rolls back the operation.
- [x] Provenance validation and lifecycle publication execute within one application transaction.
- [x] Existing conditional lifecycle update/concurrency protection is preserved.

### Architecture

- [x] Source provenance rules are represented outside SQLAlchemy ORM models.
- [x] Domain provenance code does not depend on FastAPI, SQLAlchemy, Alembic, network clients, AI providers, or application startup state.
- [x] ORM objects are not exposed through the application contract.
- [x] Existing publication/lifecycle path is extended rather than duplicated.
- [x] No generic repository framework is introduced.
- [x] No general publication rule engine or DSL is introduced.
- [x] Future publication validations can compose with the same activation boundary.

### Security

- [x] Stored URLs are treated as untrusted data.
- [x] No URL is fetched during validation.
- [x] No DNS resolution or redirect following occurs.
- [x] No secret-bearing source metadata is introduced.
- [x] Infrastructure errors remain safely wrapped.
- [x] Logs do not unnecessarily expose full source URLs or source contents.

### Scope

- [x] No source ingestion is implemented.
- [x] No scraping is implemented.
- [x] No AI extraction is implemented.
- [x] No automatic verification is implemented.
- [x] No product/benefit/date completeness rules beyond provenance are added.
- [x] No purchase eligibility logic is added.
- [x] No REST contract is introduced.
- [x] No MCP contract is introduced.
- [x] No frontend behaviour is introduced.
- [x] No background job or scheduler is introduced.

### Code quality

- [x] Existing architecture and naming conventions are preserved.
- [x] No unnecessary dependency is introduced.
- [x] Ruff lint passes.
- [x] Ruff format check passes.
- [x] Targeted unit tests pass.
- [x] PostgreSQL integration tests pass.
- [x] The broader backend test suite passes.

---

## Tests to add or update

### Unit tests

Add a focused test module such as:

```text
backend/tests/unit/test_promotion_provenance.py
```

and update:

```text
backend/tests/unit/test_promotion_lifecycle.py
```

where publication orchestration behaviour belongs there.

Cover at minimum:

#### Stable source type values

Verify exactly:

```text
WEB_PAGE -> web_page
PDF      -> pdf
OTHER    -> other
```

If source-role types are introduced, verify exactly:

```text
PRIMARY    -> primary
TERMS      -> terms
CLAIM      -> claim
SUPPORTING -> supporting
```

#### Valid publication provenance

Verify a complete source set produces provenance containing:

```text
official_source_url
source_type
retrieved_at
verified_at
claim_url
```

#### Missing primary

Verify publication provenance validation rejects a source set without:

```text
primary
```

#### Missing claim

Verify validation rejects a source set without:

```text
claim
```

#### Unverified primary

Verify:

```text
primary.verified_at = None
```

is rejected.

#### Unverified claim

Verify:

```text
claim.verified_at = None
```

is rejected.

#### Ambiguous primary

Verify multiple eligible `primary` associations are rejected unless repository state already provides an explicit canonical mechanism.

#### Ambiguous claim

Verify multiple eligible `claim` associations are rejected.

#### Invalid URL

Cover representative invalid required URL values such as:

```text
empty string
whitespace
relative/path
manufacturer.example/path
ftp://example.test/file
```

Do not perform network calls in these tests.

#### Unsupported source classification

Verify unsupported source types fail explicitly rather than mapping to `other`.

#### Publication orchestration

Verify:

```text
review + complete provenance → active
```

and:

```text
review + incomplete provenance → remains review
```

The failing case must verify the repository status update is not invoked.

#### Non-publication transitions

Verify incomplete source provenance does not block transitions that do not enter `active`.

### PostgreSQL integration tests

Add a focused module such as:

```text
backend/tests/integration/test_promotion_source_provenance.py
```

or extend the lifecycle integration tests where that provides clearer ownership.

Use the repository's real PostgreSQL/Testcontainers setup.

Cover at minimum:

#### Successful publication

Create a `review` promotion with:

- valid `primary` source;
- valid `claim` source;
- source type;
- retrieval timestamps;
- verification timestamps.

Publish through the real application transaction.

Verify:

```text
status == active
```

and verify persisted source records/associations remain unchanged.

#### Missing primary

Attempt publication without a `primary` association.

Verify:

```text
status == review
```

after the failed transaction.

#### Missing claim

Attempt publication without a `claim` association.

Verify status remains `review`.

#### Unverified evidence

Attempt publication with a required source having:

```text
verified_at = NULL
```

Verify publication is rejected and no status write commits.

#### Ambiguous required role

Persist multiple `primary` or `claim` source associations.

Verify publication is rejected deterministically.

#### Provenance retention on expiry

Publish a promotion successfully, snapshot its source rows and associations, then perform:

```text
active → expired
```

Verify provenance remains byte-for-byte/equivalent persisted state apart from unrelated lifecycle metadata.

#### Provenance retention on archive

Verify an active promotion archived through the lifecycle retains all source associations.

#### Candidate incompleteness

Verify `discovered`, `extracted`, and `review` records may still exist without publication provenance.

#### Existing database constraints

Retain coverage proving:

```text
verified_at >= retrieved_at
```

and valid source-type/source-role constraints.

#### ORM/migration parity

Continue verifying SQLAlchemy metadata matches the actual Alembic schema.

No migration should be generated merely because domain/application provenance types were added.

### API/application tests

No FastAPI contract changes.

Application behaviour is covered through unit and integration tests around `change_promotion_status()` and the application-owned repository boundary.

### MCP contract tests

N/A.

### External-boundary tests

N/A.

No external HTTP, scraping, AI, or provider boundary is introduced.

Tests must not contact real manufacturer, retailer, or claim websites.

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

The current repository does not configure a type-checking command or type-checker dependency in `pyproject.toml`.

Do not invent one for this PR.

### Targeted unit tests

If provenance tests are added as a dedicated module:

```bash
uv run pytest tests/unit/test_promotion_provenance.py tests/unit/test_promotion_lifecycle.py
```

### PostgreSQL integration tests

```bash
uv run pytest tests/integration/test_promotion_source_provenance.py tests/integration/test_promotion_lifecycle.py tests/integration/test_core_promotion_schema.py
```

Adjust only if the implementation places the coverage in existing test modules.

Docker must be available because the repository uses PostgreSQL Testcontainers.

### Broader backend test suite

```bash
uv run pytest
```

### Migration verification

A migration is not expected.

Verify the current migration head remains correct:

```bash
uv run alembic heads
```

and rely on the PostgreSQL integration suite's metadata/migration parity checks.

If implementation unexpectedly requires a migration, additionally run against a real PostgreSQL database:

```bash
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head
```

and ensure migration integration tests pass.

Do not edit `0002_core_promotion_schema.py` merely to avoid creating a legitimate new revision.

---

## Completion report

When implementation is complete, provide:

### Changed

Summarise:

- publication source-provenance domain representation;
- canonical source type/role handling introduced;
- provenance loading through the application persistence boundary;
- `review → active` provenance validation;
- tests added or updated.

### Database and migrations

Expected:

```text
None.

Existing sources and promotion_sources schema retained unchanged.
Existing provenance fields and constraints remain the source of truth.
```

If that is not true, list the new migration and explain why the existing schema was insufficient.

### API/MCP contracts

Expected:

```text
None.
```

### Tests and verification

List:

- unit tests added/updated;
- PostgreSQL integration tests added/updated;
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

when there were no deviations.

### Remaining risks or follow-up

Expected later work includes:

- broader promotion publication completeness validation;
- verified product applicability;
- structured reward/value rules;
- eligibility rules;
- claim-window semantics;
- source discovery and retrieval;
- SSRF-safe source fetching;
- source content/version hashing where required;
- promotion/source versioning and supersession;
- scheduled source re-verification;
- runtime eligibility provenance exposure through REST/MCP.

Do not implement those as part of PR 6.

## Implementation verification — 2026-10-06

Implemented on `pr6-promotion-source-provenance` from fetched `origin/main`
`13dabf6`, containing PRs 3–5. Local main was stale; the remote main was used.
No scoped backend AGENTS.md, publication-validation abstraction, generic source
repository, canonical source-selection mechanism, or source-mutation application
path exists. Transaction ownership remains with `promotion_transaction`; the only
normal activation transition is review → active. Alembic head is unchanged at
`0002_core_promotion_schema`.

Acceptance evidence:

- `app/domain/promotion_provenance.py`: standard-library-only immutable evidence
  and derived view, canonical stable source types/roles, explicit reason codes,
  unique required-role policy, local HTTP(S) parsing, aware timestamps and chronology.
  No fetching, DNS, LLM, officiality inference, or persisted duplication.
- `app/application/promotions.py`: provenance reads and validation after lifecycle
  validation and before the existing conditional status write, in one transaction.
  Same-state requests and transitions outside activation skip provenance reads.
- `app/db/repositories/promotions.py`: joined scalar evidence mapped to immutable
  records; database errors retain the safe persistence boundary. Schema unchanged.
- Unit coverage verifies stable values, derived evidence, missing/ambiguous/unverified
  roles, invalid URLs/classifications/timestamps, offsets, immutable records,
  rejection before writes, corrected retry, no-op behaviour, other transitions,
  and activation conflict reconciliation.
- PostgreSQL coverage verifies publication, evidence mapping, both required roles'
  rejection cases, zero UPDATE on rejection, corrected retry, query/update/commit
  rollback, source classification round trips, expiry/archive retention, committed
  activation visible in a new session, existing constraints, migration parity,
  incomplete candidates, and existing lifecycle concurrency/query semantics.
- Scope review confirms no migration, dependency, transport, network, configuration,
  ingestion, eligibility, or broader completeness changes.

Commands run from backend with `UV_CACHE_DIR=/private/tmp/ppbc-uv-cache`:

```bash
uv sync --locked --extra dev
uv run ruff check --fix .
uv run ruff format .
uv run pytest tests/unit/test_promotion_provenance.py tests/unit/test_promotion_lifecycle.py
uv run alembic heads
uv run pytest tests/integration/test_promotion_source_provenance.py tests/integration/test_promotion_lifecycle.py tests/integration/test_core_promotion_schema.py --tb=short
uv run ruff format --check .
uv run ruff check .
uv run pytest --tb=short
```

Targeted unit run: 105 passed before adding 11 additional lifecycle cases.
Targeted PostgreSQL run: 85 passed. Final full suite: 240 passed, one pre-existing
Starlette/httpx deprecation warning. Final lint and format checks passed.
Initial lint findings were corrected. PostgreSQL checks ran with Docker access.
`git diff --check` passed. No type checker is configured, so none was introduced.

Database/migrations, API/MCP contracts, external configuration: None.
Deviations: None. Remaining issues within PR 6 scope: None.
Broader publication completeness and all other excluded capabilities remain later work.
