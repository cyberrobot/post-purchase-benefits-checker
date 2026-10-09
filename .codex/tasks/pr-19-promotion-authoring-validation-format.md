# PR 19 — Promotion Authoring & Validation Format

## Repository state

**Expected branch:**  
`pr19-promotion-authoring-validation-format`

**Base branch:**  
`main`

**Dependencies:**

- PR 3–4 — existing promotion graph, candidate lifecycle and `change_promotion_status` orchestration.
- PR 5–7 — benefit classifications, curated source provenance and canonical identity reference data.
- PR 10–15 — typed eligibility rules, classification, claim windows, requirements and rewards.
- PR 17–18 — canonical deterministic purchase check and independent, read-only public eligibility API.
- Existing PostgreSQL, SQLAlchemy 2, Alembic, Pydantic (already installed transitively), pytest/Testcontainers and Ruff.
- **Number verification:** PR #18, *Expose the v1 public eligibility HTTP API*, was the highest-numbered PR and was merged into `main` on **8 October 2026**. PR 19 is the next specification number. Verify again before creating an actual pull request.

### Read first

- `AGENTS.md`; any narrower `AGENTS.md` added before implementation.
- `.codex/tasks/TEMPLATE.md` and `.codex/tasks/pr-4-promotion-lifecycle-history.md`.
- `.codex/tasks/pr-6-promotion-source-provenance.md`, `.codex/tasks/pr-7-product-retailer-normalisation.md`.
- `.codex/tasks/pr-12-fixed-claim-windows.md`, `.codex/tasks/pr-13-relative-delayed-claim-windows.md`.
- `.codex/tasks/pr-14-promotion-requirements.md`, `.codex/tasks/pr-15-reward-calculation.md`.
- `.codex/tasks/pr-17-check-purchase-eligibility-service.md` and `backend/README.md`.
- Existing implementation and tests listed below. Inspect current `main` at implementation time.

### Primary change area

**Promotion authoring contract, pure validation, and the existing publication boundary.** This PR establishes how an untrusted or manually prepared candidate is represented, how errors are reported, and what persisted data must satisfy before `review → active` succeeds. It does **not** create the authoring/ingestion API or ingestion infrastructure.

### Canonical implementation examples

- `backend/app/application/promotions.py` — `PromotionRecord`, `PromotionRepository`, `change_promotion_status`, `StatusChange` and typed application errors.
- `backend/app/db/repositories/promotions.py` — `SqlAlchemyPromotionRepository`, `promotion_transaction`, existing conditional status update, provenance reads and batched association-loading patterns.
- `backend/app/db/models/core.py` — actual promotion/variant/product/benefit/reward/requirement/source columns and constraints.
- `backend/app/domain/promotion_lifecycle.py` — six states and permitted transitions.
- `backend/app/domain/promotion_provenance.py` — `PromotionSourceRecord` and `validate_publication_provenance`.
- `backend/app/domain/claim_windows.py`, `benefits.py`, `requirements.py`, `rewards.py` — existing typed business invariants.
- `backend/app/application/purchase_check_details.py::PublishedPromotionDetails` — existing read projection, **not** an authoring model.
- `backend/tests/integration/test_promotion_lifecycle.py` — transaction/concurrency/rollback precedent.
- `backend/tests/integration/test_core_promotion_schema.py` — incomplete candidates and graph/constraint fixtures.

### Relevant symbols

```text
PromotionStatus, validate_transition, HISTORICAL_PUBLISHED_STATUSES
PromotionRecord, PromotionRepository, PromotionConflict, PromotionPersistenceError
change_promotion_status, promotion_transaction, SqlAlchemyPromotionRepository
Manufacturer, Product, Retailer, Promotion, PromotionVariant
PromotionVariantProduct, Benefit, BenefitReward, BenefitProductRewardValue
Requirement, Source, PromotionSource
PromotionSourceRecord, validate_publication_provenance, PromotionProvenanceError
BenefitType, RequirementType, RewardType
FixedAmountReward, PercentageReward, ProductSpecificReward
FixedClaimWindow, RelativeClaimWindow
PublishedPromotionDetails, PublishedPromotionDataError
```

### Expected change surface

```text
backend/app/application/promotion_authoring.py       # NEW: v1 serialisable candidate contract
backend/app/domain/promotion_validation.py           # NEW: pure definition/completeness validator
backend/app/application/promotions.py                 # publication gate and typed failure
backend/app/db/repositories/promotions.py            # load coherent publication snapshot/lock
backend/tests/unit/test_promotion_authoring.py       # NEW
backend/tests/unit/test_promotion_validation.py      # NEW
backend/tests/unit/test_promotion_lifecycle.py       # targeted activation regressions
backend/tests/integration/test_promotion_publication.py  # NEW: real PostgreSQL
backend/tests/integration/test_promotion_lifecycle.py    # existing fixture regressions
backend/README.md                                    # format and validation instructions
```

An alternative narrow module split is acceptable. Do not create a second, generic promotion repository or eligibility engine. Update existing fixtures deliberately if stricter publication validation makes them invalid.

### Excluded areas

- No new REST/MCP endpoints, user accounts, permissions system, frontend, admin editor, batch import CLI or production candidate-write service.
- No autonomous AI extraction, LLM calls, scraping, OCR, source fetch, scheduler, queue, external source verification or manufacturer claim submission.
- No new promotion lifecycle status, automatic activation, lifecycle rewrites, migration or historical versioning system.
- No direct authoring of `active`, `expired` or `archived` status; those remain lifecycle operations.
- No generic JSON rules DSL, custom expressions, dynamic Python imports or executable rule text.
- No publishing country, condition, purchase-channel or purchase-price eligibility restrictions: the pure rule engine knows some of these concepts, but the **current persisted promotion graph and `check_purchase` projection do not support them**. Reject these authoring fields rather than silently dropping them.
- No widening the public purchase input (`brand`, `model`, `retailer`, `purchase_date`, optional `purchase_price`) or changing v1 eligibility responses.
- No retroactive rewrite, auto-unpublish or destructive repair of existing `active`/`expired` rows.

### Unknowns Codex must verify

1. The highest existing PR and task filename remain #18 and the new filename is not already present.
2. `change_promotion_status` still checks provenance only on the `review → active` transition and uses `update_status(expected, target)` as a compare-and-swap.
3. `promotion_transaction` owns a fresh session/commit/rollback; no API already writes the promotion graph.
4. Current schema holds one `manufacturer_id`, optional purchase dates, mutually exclusive fixed/relative claim columns, variant/retailer/product associations, typed benefits/rewards/requirements and sources.
5. The current read path can return an unknown cashback amount when a reward is unconfigured and can return `POTENTIALLY_ELIGIBLE` when claim windows are missing. **PR 19 intentionally makes both cases publication-blocking for newly activated data.**
6. `source.verified_at` and curated source roles are the current provenance evidence; there is no persisted reviewer identity, signed verification or source content hash. Do not imply otherwise.
7. Product/manufacturer agreement is not enforced across the current product-link graph by a database constraint.
8. Existing integration fixtures may manually insert `active` records that would now fail a publication gate. Do not rewrite unrelated persistence tests solely to force historical fixtures through the new path.
9. Check installed Pydantic version and commands from `backend/pyproject.toml`, `backend/README.md` and CI; do not invent a typecheck command.

---

## Objective

Backend authors and later ingestion/AI adapters can prepare a **versioned, JSON-serialisable `CandidatePromotionV1` document** describing one promotion, its canonical product/retailer applicability, claim timing, benefits, rewards, requirements and source references. A deterministic validator reports missing, unsupported, ambiguous and contradictory fields with stable machine-readable issue codes and paths.

**A candidate document is never authoritative.** The `review → active` operation must load the **current persisted promotion graph**, validate it against the same domain publication rules and existing curated provenance requirements, and commit the status change only when the whole promotion passes. Invalid/incomplete candidates remain non-active, with precise diagnostics and no partial publication. Existing active/historical eligibility behaviour remains unchanged.

Completion means a typed candidate can be parsed and round-tripped, validated with predictable issues, and an actual PostgreSQL `review` promotion cannot be activated through the supported application path unless its complete graph passes publication validation.

---

## Architecture and invariants

```text
Manual / future AI / future ingestion input (untrusted JSON-like data)
    -> CandidatePromotionV1 parsing and strict field/type validation (application)
    -> pure authoring/domain checks -> ValidationReport (no writes)
    -> future explicit candidate persistence/review workflow (NOT this PR)

Existing persisted Promotion(status=review) + related rows
    -> promotion_transaction + lock/reload authoritative graph
    -> persistence adapter maps ORM rows to immutable domain validation input
    -> pure publication validation + existing validate_publication_provenance
    -> zero blocking issues: conditional review -> active update and commit
    -> blocking issue(s): PromotionPublicationError and rollback

Runtime eligibility: unchanged, reads published active/expired graph only.
```

Invariants:

1. **The active gate validates persisted data, not the caller's last draft or validation report.** An earlier successful preflight cannot be reused as publication approval after data changes.
2. Both authoring and activation use shared pure typed/domain checks; ORM and Pydantic types do not enter domain code. Never independently reimplement a subset of rules in the controller.
3. Structurally valid **but incomplete** documents are allowed for draft/review preparation; *publication* applies strictly stronger completeness and provenance checks.
4. Candidate input must not set or infer lifecycle status. Only the existing application lifecycle service can change it.
5. A validation failure never changes any promotion row, linked row, source row or lifecycle timestamp.
6. Do not reinterpret `retailer_id: null` as unknown: for a complete variant it means explicitly unrestricted retailer applicability, which source evidence must support. Unknown applicability must remain an incomplete draft; it must not accidentally turn into a universal rule.
7. Product references are canonical UUIDs; no fuzzy names, unverified AI-generated UUIDs or automatic reference-data creation.
8. The validator must not infer rules from descriptions, names, website text or requirement descriptions.
9. Existing active/expired historical data remain queryable. New strictness applies to **new activation**, not background reads or retirement.
10. Use the existing source-role verification code rather than adding a separate, weaker definition of an official source.

---

## API and contract changes

No REST, MCP or public HTTP contract changes. **The new contract is an internal, versioned JSON authoring document**, exposed through focused Python application functions for later callers. Do not register a public write route.

### Authoring format — `CandidatePromotionV1`

Prefer a Pydantic v2 application-layer schema with `extra="forbid"`, explicit strict field types, finite bounded arrays and deterministic serialisation. Validation must produce no side effects. The root is:

```text
schema_version: Literal[1]              # required; unsupported versions rejected
promotion: CandidatePromotionBody        # required
```

`CandidatePromotionBody` fields:

| Field | Type | Draft semantics | Publication requirement |
|---|---|---|---|
| `manufacturer_id` | UUID or `null` | `null` = unresolved | Existing canonical manufacturer required |
| `name` | string or `null` | No inferred name | Non-blank, <=255 chars |
| `slug` | string or `null` | Candidate may need curation | Lowercase hyphenated slug, <=255 chars; uniqueness within manufacturer |
| `purchase_start_date` | ISO `YYYY-MM-DD` or `null` | Unknown until verified | At least one purchase boundary; inclusive; start <= end |
| `purchase_end_date` | ISO `YYYY-MM-DD` or `null` | Unknown until verified | At least one purchase boundary; inclusive; start <= end |
| `claim_window` | discriminated fixed/relative object or `null` | `null` = unresolved | Exactly one supported claim-window form, required |
| `variants` | array of variants | May be empty while incomplete | >=1 valid variant |
| `sources` | array of source links | May be empty while incomplete | Exactly one curated primary and one curated claim source; see below |

`variants[]`:

- `code: string | null` — required before publication, non-blank, <=255 chars, unique per promotion.
- `name: string | null` — optional display name, <=255 chars when provided.
- `retailer_id: UUID | null` — required **key** for each variant; UUID means only that retailer, `null` means explicitly all retailers. Do **not** make omitted key equivalent to `null`. If the source does not establish scope, do not present the variant as publishable.
- `product_ids: UUID[]` — unique canonical products; empty draft is valid, empty published variant is not. All linked products must belong to the promotion manufacturer.
- `benefits: CandidateBenefit[]` — >=1 per published variant, no unsupported enum values.
- `requirements: CandidateRequirement[]` — zero or more structured claim instructions; an empty array is valid when no requirements are established.

`benefits[]`:

- `type`: one of `cashback`, `extended_warranty`, `free_gift` (`BenefitType` values).
- `name`: non-blank string, <=255 characters for publication.
- `description`: optional plain text, not executable rules or a source of amount/duration inference.
- `reward`: nullable **discriminated** object. Required for published cashback; prohibited for non-cashback (current model does not encode warranty/gift quantities).
- Cashback `reward` forms, mapping exactly to existing `RewardType` and domain types:
  - `{"type":"fixed_amount","amount_gbp":"50.00"}`.
  - `{"type":"percentage","percentage":"10.5000"}`.
  - `{"type":"product_specific","values":[{"product_id":"<UUID>","amount_gbp":"40.00"}]}`.
- Monetary/percentage values are **decimal strings**, never JSON floating-point numbers: fixed/product amount >0 with <=2 fractional digits; percentage >0 and <=100 with <=4 fractional digits. Reject nonfinite/scientific/extra-precision representations rather than silently rounding. Product-specific entries must be unique and cover **exactly** the variant's `product_ids` when publishing; do not silently publish unmatched products.

`requirements[]`:

- `type`: `receipt`, `serial_number`, `registration`, `invoice`, `barcode`, `imei` or `installation_evidence` (`RequirementType`).
- `description`: optional plain-text instructions. Repeated requirement types are allowed, as in the existing database, where descriptions distinguish multiple instructions.

`claim_window` is **one** of:

```json
{"type":"fixed","start_date":"2026-11-01","end_date":"2026-12-31"}
```

```json
{"type":"relative","start_offset_days":30,"end_offset_days":60}
```

- Use strict discriminated parsing. Both bounds required for either form, inclusive. Fixed start <= end. Relative offsets are real integers (not booleans), >=0, start <= end. No mixed fixed/relative fields, negative offsets or inferred dates.
- `null` is permitted for incomplete drafts only. This v1 does **not** represent no-claim-required or unbounded claim windows; such cases need an explicit later domain/persistence design, not silent omission.

`sources[]`:

- `source_id: UUID` — reference to an **already curated** `Source` row; no arbitrary URL is accepted as authoritative by this contract.
- `role: "primary" | "terms" | "claim" | "supporting"` — mirrors `SourceRole`; no unrecognised roles.
- Source IDs must be unique within a promotion (matching the existing link primary key). Multiple roles cannot be assigned to the same persisted `Source` association.
- Exactly one primary and one claim link are required to publish. The repository must resolve both to existing sources and call **`validate_publication_provenance`** on actual stored URL/type/retrieved/verified data. Terms/supporting links are optional.
- Creating/curating a new `Source` record from a discovered URL is a **later ingestion task**. A model-produced `verified_at`, URL, role or source ID is never accepted as proof of source verification. Trusted source curation is an operational prerequisite; the present schema does not record who verified it.

**No** `status`, `active`, `eligibility_result`, arbitrary `rules`, `claim_url` override, free-text `product_match`, `manufacturer_name` shortcut, extra unsupported eligibility conditions or unrecognised fields are accepted. Output is a candidate definition, not a decision that the promotion qualifies for publication.

### Complete example (illustrative UUIDs; not seeded data)

```json
{
  "schema_version": 1,
  "promotion": {
    "manufacturer_id": "00000000-0000-4000-8000-000000000001",
    "name": "Autumn appliance cashback",
    "slug": "autumn-appliance-cashback",
    "purchase_start_date": "2026-10-01",
    "purchase_end_date": "2026-11-30",
    "claim_window": {
      "type": "relative",
      "start_offset_days": 30,
      "end_offset_days": 60
    },
    "variants": [
      {
        "code": "all-retailers",
        "name": "Selected appliance",
        "retailer_id": null,
        "product_ids": ["00000000-0000-4000-8000-000000000002"],
        "benefits": [
          {
            "type": "cashback",
            "name": "£50 cashback",
            "description": null,
            "reward": {"type": "fixed_amount", "amount_gbp": "50.00"}
          }
        ],
        "requirements": [
          {"type": "receipt", "description": "Retain the original receipt."}
        ]
      }
    ],
    "sources": [
      {"source_id": "00000000-0000-4000-8000-000000000003", "role": "primary"},
      {"source_id": "00000000-0000-4000-8000-000000000004", "role": "claim"}
    ]
  }
}
```

The two example source IDs must point to actual **verified** sources in PostgreSQL for publication to succeed. Their fabricated values are shown only to document the shape.

### Internal function contracts

Define (names may be narrowly adapted to fit existing code):

```python
parse_candidate_promotion(raw: Mapping[str, object]) -> CandidatePromotionV1
validate_candidate_promotion(candidate: CandidatePromotionV1) -> ValidationReport
validate_promotion_for_publication(snapshot: PromotionValidationSnapshot) -> ValidationReport
```

- `parse_candidate_promotion` rejects malformed shape, unknown keys/versions, bad enum/type/date/decimal forms and oversized payloads with **structured, path-aware** input validation; no DB and no network.
- `validate_candidate_promotion` is a deterministic, pure **preflight** for internally consistent supported content. It may identify incomplete fields; it **cannot approve publication** because references/provenance have not been looked up. A structurally well-formed partial draft may be returned with blocking issues.
- `validate_promotion_for_publication` validates a complete immutable snapshot from the current database; it reuses the same domain validation functions, checks resolved identity/linkage and verified provenance, and returns a report. It performs no write, fetch, external call or AI step.
- `ValidationReport`: immutable `issues` with `{code, path, message, severity}`. Use stable enum/string codes and JSON Pointer-style paths (`/promotion/variants/0/product_ids`). `severity=error` blocks publication; `warning` does not. Expose a derived `can_publish = not any(error)` **only for persisted publication-snapshot validation**; preflight readiness is not an authorisation token. Issue order must be deterministic (stable check order, then array index and code), not dependent on unordered sets/SQL row order.
- `PromotionPublicationError`: application-level failure containing safe structured issues/report. Do not leak ORM values, SQL or raw third-party text through an exception string. Keep `PromotionNotFound`, `InvalidPromotionTransition`, `PromotionConflict`, `PromotionPersistenceError` and `PromotionProvenanceError` distinct where appropriate.
- If existing code assumes a single `PromotionProvenanceError`, preserve its stable reason codes; map them to publication issues rather than silently replacing existing public/application semantics.
- Pure validators must raise neither misleading ineligibility classifications nor persistence errors. Reference lookup/transaction failures remain separate infrastructure failures.

Recommended stable issue codes (extend only as actual checks require):

```text
unsupported_schema_version, unsupported_field, invalid_field_type,
missing_manufacturer, manufacturer_not_found, missing_promotion_name,
invalid_promotion_slug, duplicate_promotion_slug, missing_purchase_window,
invalid_purchase_window, missing_claim_window, invalid_claim_window,
missing_variant, missing_variant_code, duplicate_variant_code,
retailer_not_found, missing_product, product_not_found,
product_manufacturer_mismatch, duplicate_product,
missing_benefit, unsupported_benefit_type, missing_benefit_name,
missing_cashback_reward, invalid_reward, unsupported_reward_type,
noncashback_reward_not_supported, product_reward_coverage_mismatch,
unsupported_requirement_type, duplicate_source_link,
missing_primary_source, ambiguous_primary_source,
missing_claim_source, ambiguous_claim_source,
source_not_found, source_unverified, invalid_source_provenance,
unsupported_persisted_rule
```

Use canonical `PromotionProvenanceError.reason_code` for precise source errors when possible (e.g. `primary_source_unverified`, `invalid_primary_url`); do not collapse distinct source errors into a generic message.

---

## Domain and application behaviour

### Draft preflight

1. Parse the explicit v1 structure; `extra="forbid"` throughout. Do not accept untyped free-form metadata as rules.
2. Validate provided fields with existing domain value objects wherever possible. Do not invent alternative money, date, benefit or requirements semantics.
3. Report absent fields and unresolved canonical references as **incomplete** rather than guessing/filling values. Draft `null` dates, product lists, claim window and source lists do not create an active rule.
4. Duplicated variant codes, duplicate product IDs within one variant, duplicate source IDs and ambiguous reward definitions produce blocking issues; repeated equivalent source-role assertions do not become implicit deduplication.
5. Accept legitimate multiple variants, multiple benefits/requirements and multiple retailer-specific variants. Cross-variant product overlap is allowed; no arbitrary “first variant wins”.
6. Ensure round-tripping through `model_dump(mode="json")`/reparse is deterministic and retains `null`, ISO dates, UUIDs and decimal strings without binary floating-point loss.
7. Bound string/list/document size at the authoring boundary. Suggested defaults: max 50 variants, max 200 product references across the document, max 20 benefits and 30 requirements per variant, max 30 source links, max 255-character identifiers/names and max 2,000-character descriptions. Implement limits in one place, with tests; do not silently truncate.

### Strict publication validation

Before a `review → active` transition, in addition to syntactic/type correctness, check all of the following **against the persisted graph**:

1. Promotion exists and is presently `review` (normal transition validation remains authoritative).
2. Manufacturer exists; slug/name are valid; `(manufacturer_id, slug)` uniqueness is enforced by the existing database constraint; a conflicting identity is a rejection or persistence constraint failure, never an overwrite.
3. At least one variant exists; codes are present/unique; every variant contains >=1 valid canonical product of the promotion manufacturer and >=1 named supported benefit.
4. Any retailer association references a real retailer. `NULL` retailer means any retailer and must have been consciously curated; publication validator must not replace an unresolved draft value with `NULL`. This workflow has no external proof of curation, so the source-review policy remains a prerequisite.
5. Purchase date restrictions include at least one known bound and are ordered; a missing bound is intentionally open-ended, *not* an unspecified restriction. Require the verified source to support the entered range, without attempting NLP-based legal interpretation.
6. Exactly one valid fixed or relative claim window exists. Invalid/incomplete/mixed/negative/reversed windows block activation; compare using existing pure claim-window validators.
7. Every cashback benefit has exactly one valid typed reward; every noncashback benefit has no reward. Product-specific rewards have exactly one positive GBP amount for **each and only** product in that variant. No new support for warranty/gift amounts or conditions is implied.
8. Every requirement is a supported `RequirementType`. Descriptions are claim instructions only; do not interpret them as eligibility conditions.
9. Exactly one primary and one claim source association exist and resolve to curated `Source` rows. Run the existing provenance validator (HTTPS or HTTP absolute URLs as currently supported; verified/retrieved timestamps aware and ordered). No external fetching or verification inference occurs.
10. All source/variant/benefit/reference identities are internally consistent; incomplete, dangling or unsupported field projections fail closed. The schema/ORM can enforce some of these invariants, but *not* all across tables.
11. Reject unsupported eligibility constraints instead of publishing a weakened version (for now this means disallowing unsupported authored fields; do not pretend the graph implements purchase-price thresholds, channel, condition or country rules).
12. Collect multiple deterministic, independent issues where feasible; never convert a schema or data-integrity failure into `NOT_ELIGIBLE` or a success response.

A published `active` promotion is **not** proof its raw source claims are true. It is the system's authoritative *structured rule* after curated evidence and deterministic checks; the reviewer is responsible for factual verification. The validator cannot independently establish manufacturer ownership or completeness of legal terms from a URL.

### Lifecycle, duplication and idempotency

- Only `review → active` runs the new completeness check. `discovered → extracted → review` may retain incomplete candidates; `review → extracted`, retirement and archive semantics stay unchanged.
- Repeated `active → active` remains a no-op and must not unexpectedly revalidate or modify existing historical rows. Invalid transitions remain rejected **before** expensive publication loads.
- Publication and graph loading execute in the existing single transaction; take a row-level lock on the parent `Promotion` before loading its associations. The supported future graph-write path must acquire that same parent lock before modifying variants/sources/benefits so the checked snapshot cannot be changed by a cooperating writer between validation and activation.
- Keep the existing conditional status update/compare-and-swap semantics for stale updates; do not silently overwrite a competing transition or double-publish. Concurrent review/activate and review/edit operations must either serialise safely or return a conflict and require revalidation.
- The current codebase has no general supported candidate-write path or database triggers protecting all direct SQL writers. **Do not claim** this PR makes direct, out-of-band DB edits race-proof. Document the remaining operational restriction: published rules and graph mutations must go through controlled, transactionally coordinated paths. Add a follow-up if database-enforced immutability/permissions become necessary.
- Duplicate candidate document submissions are **not** persisted by this PR. Existing manufacturer/slug and variant-code uniqueness must be preserved; later authoring writes will need explicit upsert/idempotency semantics and source-version reconciliation.

### Error and success semantics

- A valid, complete persisted graph returns a normal successful `StatusChange` and becomes active on commit.
- Invalid draft shape returns typed parse failures with field paths; invalid or incomplete publication graph yields a `PromotionPublicationError(report)` and rolls back. Neither changes any database state.
- Missing promotion, invalid lifecycle transition, concurrency conflict and PostgreSQL unavailable remain separate errors.
- Failure must be observable via safe issue codes, without losing provenance, deleting candidates, or creating an intermediate `active` state.

---

## Persistence, transactions, and migrations

**No migration or new table is expected.** Reuse existing `promotions`, `promotion_variants`, `promotion_variant_products`, `benefits`, `benefit_rewards`, `benefit_product_reward_values`, `requirements`, `sources` and `promotion_sources` as the authoritative data at publication time. The authoring document is an in-memory/serialisable contract, **not** a new JSONB source of truth or persisted approval flag.

- Add a narrowly scoped repository method such as `get_publication_snapshot_for_update(promotion_id)` that locks `promotions` and returns a fully-loaded **immutable** validation projection (including canonical product manufacturer IDs, retailer existence, all benefits/reward child rows, requirements, source associations and source metadata). Do not return live SQLAlchemy models to the domain.
- Lock the parent before reading the related graph within the same transaction. Ensure ORM autoflush cannot accidentally mutate records during validation; the transaction should be dedicated/fresh as with existing `promotion_transaction`.
- Preserve the current `update_status(promotion_id, expected, target)` compare-and-swap and rollback-on-error behaviour. A complete validation does not itself write or stamp a lasting approval.
- If a concurrent writer changes the graph outside the coordinated parent lock, document that as a prohibited/out-of-band operation rather than misrepresenting the validation as serialisable across all writers.
- Do not invent a schema-level `validated=true` field or let stale preflight reports authorise activation.
- Existing active/expired/archived data are not modified or backfilled. Pre-existing manual `active` rows that violate the new rules remain a separate data-quality follow-up; the public runtime already surfaces invalid published data as an error rather than fake ineligibility.
- Do not change existing Alembic revisions. If implementation demonstrates an unavoidable migration, document the precise gap first, use a new reversible revision and real PostgreSQL validation, and seek explicit scope justification.

**Real PostgreSQL verification:** run the new publication integration suite through existing Testcontainers, including an actual commit/reload and rollback/no-write snapshot. No SQLite substitute for locks, uniqueness or isolation behaviour.

---

## External services and network access

**None.** The candidate parser and validator do not fetch manufacturer pages, contact AI providers, resolve DNS or follow claim links. They work only with supplied authoring content and already persisted curated source records.

Later source-retrieval/AI extraction adapters must be separate, bounded, SSRF-safe and untrusted; do not build them in PR 19.

---

## Security and privacy

- The authoring contract is **internal**, not an unauthenticated write API. Any future exposed endpoint must add independently specified authentication, authorisation, object-level access control, request size/rate limits and audit trails before accepting edits or activation.
- Strictly reject unknown properties, unsupported rule forms, executable content-as-rules and bogus UUIDs; prevent mass assignment of lifecycle status or source verification through candidate documents.
- Treat names, descriptions, and external source text as passive, untrusted strings. Never execute or interpolate them as Python, SQL, shell commands, templates or LLM instructions.
- Do not trust source IDs, URLs, timestamps or claimed verification merely because they appear in an extracted payload. Resolve authoritative source associations from PostgreSQL and use the established publication-provenance checker.
- Limit the depth, string length, array cardinality and total document size at parsing. Do not add an unauthenticated network, filesystem, HTTP or provider operation as part of validation.
- Logs may contain promotion ID, validation stage, issue code and counts; exclude full third-party content, source documents, receipts and personal information. Safe exception strings must not include SQL or raw untrusted body text.

---

## Configuration and deployment

### Environment variables

**None.** No new secret, toggle, external service or feature flag is needed.

### Runtime/deployment changes

**None.** The existing Python/FastAPI process, `uv` lockfile, Docker configuration, startup and `/health` behaviour remain unchanged unless adding Pydantic as an explicit direct project dependency is required by repository policy. Inspect dependency metadata before touching the lockfile.

---

## Observability and operations

- Emit one structured application event for publication attempt outcome (`publication_validation_succeeded`, `publication_validation_rejected` or `publication_validation_failed`) with promotion ID, issue count, safe issue codes and transaction/correlation ID when already available.
- Distinguish a normal blocking validation report from a PostgreSQL/transaction failure. Do not report expected authoring mistakes as an infrastructure outage or uncaught Sentry error.
- No new metrics platform, dashboard, cron job or health check. Preserve existing logging/Sentry configuration and safe redaction.
- Document how a future curator can inspect a deterministic validation report and correct the persisted candidate without recreating an existing promotion.

---

## Failure, consistency, and recovery

| Scenario | Required result |
|---|---|
| Malformed input, unknown field/version, unexpected lifecycle `status` field | Reject at parsing with stable field path; no writes |
| Valid draft missing canonical identity/source/claim window/reward | Return blocking preflight issues; draft remains a candidate |
| Source unverified, duplicate primary/claim or invalid timestamp/URL | Block activation through existing provenance rules; no status change |
| Product linked to a different manufacturer | Block activation; never silently remove that product |
| Missing reward for cashback or incomplete product-specific mapping | Block activation; no guessed amount |
| One variant valid, another invalid | Block **entire** promotion; never partly activate |
| Two activation attempts or stale expected status | Serialize/compare-and-swap; at most one meaningful change, established no-op/conflict result |
| Candidate edit races with publication using supported writer discipline | Parent lock serializes edits/validation; changed graph must be revalidated |
| Database read/update/commit fails | Roll back transaction; raise safe persistence error, not validation/ineligibility result |
| Caller retries after uncertain commit | Re-read status; same-state active remains idempotent and must not duplicate rows |
| Existing invalid `active` row encountered by purchase check | Preserve existing published-data error semantics; do not auto-repair as part of PR 19 |

---

## Acceptance criteria

### Behaviour

- [ ] `CandidatePromotionV1` is documented, versioned, strictly parsed and round-trips deterministically as JSON without float-based money loss.
- [ ] Partial but correctly shaped draft values may be represented without being considered publishable.
- [ ] A deterministic validation report identifies stable `code`, JSON Pointer `path`, safe message and severity for each issue.
- [ ] Claims, rewards, benefits, requirements and identifiers reuse existing domain semantics rather than defining a competing evaluator.
- [ ] Unsupported fields/rules, unknown enum values, unknown versions and malformed discriminated objects are rejected, never ignored or mapped to defaults.
- [ ] A `review` promotion with fully valid persisted graph and verified curated sources becomes `active` via the existing lifecycle service.
- [ ] Any missing/ambiguous rule, incomplete variant, incorrect canonical product link or unverified source prevents **all** publication with no write.
- [ ] Draft validation alone can **never** approve the current persisted graph or set publication status.
- [ ] Existing eligibility GET/POST surfaces, `check_purchase`, retirement and same-state lifecycle semantics are unchanged.

### Data and consistency

- [ ] Publication validation uses a complete immutable ORM-to-domain snapshot from PostgreSQL within one transaction.
- [ ] Parent promotion lock and compare-and-swap are exercised in tests. Future supported graph writers must respect the lock discipline.
- [ ] No migration, persisted approval flag, JSON rules blob or change to existing published graph is introduced without documented justification.
- [ ] Empty product/benefit/variant graphs, mismatched manufacturer links and incomplete reward coverage cannot become newly active.
- [ ] Verified primary and claim source requirements use the existing provenance validator.
- [ ] Validation failure/rollback leaves candidate and associated rows byte-for-byte unchanged, including timestamps.

### Security

- [ ] Candidate data cannot mass-assign `status` or source verification and cannot bypass application publication checks.
- [ ] No new unauthenticated write endpoint, outbound request or LLM-driven publication path is added.
- [ ] Inputs, arrays, plain-text fields and error/log payloads are bounded and safe.

### Operations

- [ ] Expected validation rejection is distinguishable from infrastructure failure in logs/result types.
- [ ] Stable reasons/paths support future manual curation without logging raw source text.
- [ ] No health/readiness/regression issue is introduced.

### Code quality

- [ ] Domain remains independent of Pydantic/FastAPI/SQLAlchemy; application owns orchestration, repository owns ORM and locks.
- [ ] No parallel eligibility engine, extra infrastructure, speculative schema or unrelated refactor.
- [ ] Existing Ruff checks and relevant unit/PostgreSQL suites pass.

---

## Tests to add or update

### Unit tests

**New:** `backend/tests/unit/test_promotion_authoring.py`

- Parse/serialise the example document and a deliberately incomplete document; fixed/relative windows; every current benefit/requirement/reward type.
- Unknown `schema_version`, added `status`/unsupported rule property, invalid UUID/date, number instead of decimal string, non-finite/over-precise money, bool offset, mixed window shapes.
- Missing vs explicit `retailer_id: null`, strings/arrays over bound, duplicate codes/product IDs/source IDs, unsupported enum.
- Stable paths/codes/order and no mutation of input on parse/reparse.

**New:** `backend/tests/unit/test_promotion_validation.py`

- Valid single-/multi-variant graph; valid fixed/relative inclusive boundaries; any-retailer and retailer-specific applicability.
- Incomplete product/benefit/claim/source graph; cashback without reward; reward on noncashback; wrong product-manufacturer; product-specific reward gaps/extras; unsupported rule forms.
- Multiple independent issues, deterministic ordering and immutability; source provenance delegated to established typed validator.
- Domain tests run with **no database/network**.

**Update where applicable:** `backend/tests/unit/test_promotion_lifecycle.py`

- `review → active` invokes publication gate; other transitions and repeated `active → active` do not; reject without calling `update_status`; preserve conflict/not-found behavior.

### PostgreSQL integration tests

**New:** `backend/tests/integration/test_promotion_publication.py`

1. Persist a full `review` graph with manufacturer, products, variant, benefits, typed cashback reward, requirements, an actual fixed/relative window and verified primary/claim source rows; activate and reload in a fresh session.
2. Parameterize incomplete graph cases (no variant, no products, cross-manufacturer product, no benefit, missing reward, incomplete product-specific values, invalid claim setup, no verified primary or claim, duplicate source role) and assert `review` plus graph/timestamps unchanged after rejection.
3. Confirm existing source verification failures retain stable reason detail; re-curation followed by retry may activate.
4. Exercise parent lock/concurrent activation and a cooperating graph edit with independent real PostgreSQL transactions; verify conflict/revalidation semantics without sleeps.
5. Force a repository read failure and commit failure; ensure safe persistence category and rollback.
6. Ensure rejected candidates do not appear in published-only candidate query; successful ones do.
7. Verify existing active/expired promotions remain queryable without retroactive validation or mutation.
8. Run against the migrated PostgreSQL schema; confirm no alembic drift if schema unchanged.

Do **not** require all legacy fixtures with manually seeded active status to pass publication validation; adapt only the lifecycle tests that exercise activation.

### API/application tests

- Application tests verify structured publication failures and transactional activation without adding transport routes.
- Regression-run the current `backend/tests/unit/test_eligibility_api.py`, `backend/tests/integration/test_eligibility_api.py`, and purchase-check tests; no public API schema change is permitted.

### MCP contract tests

**N/A** — no MCP transport is currently introduced or modified.

### External-boundary tests

**N/A** — no external requests or LLM dependency. Parsing/validation must work without network access.

---

## Verification commands

From `backend/`, using the repository's actual `pyproject.toml`/README configuration:

```bash
# Install/sync dependencies when required
uv sync --locked --extra dev

# Formatting and lint
uv run ruff format --check .
uv run ruff check .

# Type checking
# N/A — no mypy/pyright command or dependency is currently declared.
# Recheck pyproject.toml/CI at implementation time; do not invent one.

# New targeted domain/application checks
uv run pytest tests/unit/test_promotion_authoring.py tests/unit/test_promotion_validation.py tests/unit/test_promotion_lifecycle.py

# Existing provenance/domain coverage
uv run pytest tests/unit/test_promotion_provenance.py tests/unit/test_claim_windows.py tests/unit/test_rewards.py tests/unit/test_requirements.py

# Real PostgreSQL publication, lifecycle and graph tests (Docker required)
uv run pytest tests/integration/test_promotion_publication.py tests/integration/test_promotion_lifecycle.py tests/integration/test_core_promotion_schema.py

# Published candidate matching and purchase-check regressions
uv run pytest tests/integration/test_promotion_candidate_matching.py tests/integration/test_check_purchase.py tests/integration/test_eligibility_api.py

# Broader backend tests
uv run pytest

# Existing migration drift/real PostgreSQL checks (no new migration expected)
uv run pytest tests/integration/test_postgres_migrations.py
```

If any verification is unavailable, report the exact unrun command, blocker, checks actually completed and remaining risk. Never claim an unrun test passed or weaken a test merely to make CI green.

---

## Completion report

On implementation completion, report these sections concisely and truthfully.

### Changed

- New authoring document structure, parser, validation report and strict publication rules.
- Existing lifecycle integration and immutable persisted-graph projection, if changed.

### Database and migrations

- Expected: **None**. State any actual migrations, backfills or lock/transaction changes.

### API/MCP contracts

- Expected: **None** externally. Document the new internal Python contract and schema version.

### Tests and verification

- List actual new/updated tests, exact commands run and results; identify PostgreSQL/Docker limitations explicitly.

### External configuration

- Expected: **None**.

### Deviations

- List and justify any changed contract, validation invariant, scope or module placement. Otherwise `None`.

### Remaining risks or follow-up

- Candidate persistence/edit endpoints, curator authentication/audit and source creation/verification are future PRs.
- The database cannot independently prove human verification or prevent direct out-of-band graph edits; publish through controlled application writes only.
- Source-content versioning, publication history, unsupported eligibility dimensions and no-claim-required promotions require separate designs if needed.
