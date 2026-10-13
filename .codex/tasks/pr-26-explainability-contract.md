# PR 26 — Explainability Contract

## Repository state

**Expected branch:**  
`pr26-explainability-contract`

**Base branch:**  
`main`

**Dependencies:**

- PR 6 — published promotion source provenance, including curated primary and claim sources.
- PR 9–11 — candidate matching, rule evaluations, eligibility classification and stable reasons.
- PR 12–15 — claim windows, requirements and reward calculation.
- PR 17 — canonical `check_purchase` service and immutable per-variant result projection.
- PR 18 — public `POST /api/v1/eligibility/check` and explicit Pydantic response schemas.
- PR 19–25 — promotion validation and reference fixtures, where useful as existing regression inputs.
- Current Python 3.13, FastAPI/Pydantic, SQLAlchemy/PostgreSQL, pytest/Testcontainers and Ruff conventions.

### Read first

- `AGENTS.md` and any newly added, more narrowly scoped `AGENTS.md`.
- `.codex/tasks/TEMPLATE.md`.
- `.codex/tasks/pr-6-promotion-source-provenance.md`.
- `.codex/tasks/pr-10-core-eligibility-rules.md`.
- `.codex/tasks/pr-11-eligibility-result-classification.md`.
- `.codex/tasks/pr-17-check-purchase-eligibility-service.md`.
- `.codex/tasks/pr-18-eligibility-http-api.md`.
- `backend/README.md` and the concrete implementation/tests listed below.

### Primary change area

**Eligibility result explainability contract** across the existing immutable application result and its FastAPI v1 response mapping. This PR strengthens a single, shared explanation/evidence contract; it does **not** introduce an explanation engine or change eligibility decisions.

### Canonical implementation examples

- `backend/app/application/purchase_check.py::check_purchase`, `_evaluate_candidate`, `_explanations` — constructs results and human-readable explanations from established domain values.
- `backend/app/application/purchase_check_details.py::CheckPurchasePromotionResult`, `CheckPurchaseResult`, `PublishedPromotionDetails`, `PublishedPromotionDataError` — transport-independent immutable result types.
- `backend/app/domain/eligibility_rules.py::RuleEvaluation`, `RuleKind`, `RuleStatus`, `RuleReasonCode` — complete configured-rule outcomes.
- `backend/app/domain/eligibility_result.py::EligibilityResult`, `EligibilityReason`, `EligibilityClassification`, `EligibilityReasonCode` — classification, decisive reasons and claim-window state.
- `backend/app/domain/promotion_provenance.py::PublishedProvenance`, `PromotionSourceRecord`, `validate_publication_provenance` — official primary source and recorded verification evidence.
- `backend/app/api/schemas/eligibility.py::Promotion`, `Eligibility`, `Provenance`, `Source`, `map_result` — documented v1 wire contract.
- `backend/app/api/eligibility.py::eligibility_check` — thin route; existing error and evaluation-date behaviour.
- `backend/app/db/repositories/promotions.py::SqlAlchemyPromotionRepository.load_check_purchase_candidates`, `purchase_check_snapshot` — coherent, read-only materialisation.
- `backend/tests/unit/test_purchase_check.py`, `backend/tests/unit/test_eligibility_api.py`, `backend/tests/integration/test_check_purchase.py`, `backend/tests/integration/test_eligibility_api.py` — regression precedents.

### Relevant symbols

```text
CheckPurchaseRequest, check_purchase
CheckPurchaseResult, CheckPurchasePromotionResult, PublishedPromotionDetails
UnresolvedPurchaseIdentity, NoMatchReason
EligibilityResult, EligibilityClassification, EligibilityReason
EligibilityReasonCode, RuleEvaluation, RuleKind, RuleStatus, RuleReasonCode
ClaimWindowStatus, ClaimWindowEvaluation
PublishedProvenance, PromotionSourceRecord, SourceRole, SourceType
validate_publication_provenance, PublishedPromotionDataError
SqlAlchemyPromotionRepository, purchase_check_snapshot
Promotion, Eligibility, Reason, Rule, Provenance, Source, map_result  # API schemas
```

### Expected change surface

```text
backend/app/application/purchase_check_details.py  # minimal derived contract/accessor if needed
backend/app/application/purchase_check.py          # only if existing explanation invariants require fixing
backend/app/api/schemas/eligibility.py             # explicit last_verified_at + schema/mapping
backend/tests/unit/test_purchase_check.py
backend/tests/unit/test_eligibility_api.py
backend/tests/integration/test_check_purchase.py
backend/tests/integration/test_eligibility_api.py
backend/README.md                                 # explainability fields/meaning/limitations
```

Do **not** edit all of these by default; implement the smallest change that meets the acceptance criteria. Explain necessary changes outside this surface.

### Excluded areas

- Reimplementing candidate matching, rule evaluation, classification precedence, claim windows, rewards or requirements.
- Adding a second explanation generator in the REST adapter, frontend, MCP or an LLM.
- New eligibility classifications, reason/status codes, arbitrary rules, a generic explanation DSL or fabricated rule restrictions.
- New public endpoints, request fields, customer accounts, saved checks, receipt/OCR processing, claim submission or tracking.
- Live HTTP verification, crawling, scraping, AI extraction, source freshness scoring, scheduled re-verification or manufacturer authentication.
- Inventing per-rule evidence references that the current promotion model does not store.
- Source versioning, immutable historical snapshots, audit logs, database migrations or retrospective evidence reconstruction.
- Unrelated promotion fixtures, UI changes, CI/infrastructure changes or dependency updates.

### Unknowns Codex must verify

1. `main` still has no `.codex/tasks/pr-26-explainability-contract.md` and PR 26 has not been allocated elsewhere.
2. PR 17 already returns one `CheckPurchasePromotionResult` per published **variant**, preserving `promotion_id`, `promotion_variant_id`, names, status, complete rule evaluations, eligibility reasons, claim-window result, provenance and source records.
3. PR 18 maps those values to `Promotion` under `ResolvedResponse.promotions[]` in `POST /api/v1/eligibility/check`; there is no MCP surface yet.
4. `Promotion.provenance.verified_at` represents the curated **primary/official source** verification timestamp, while `Promotion.sources[]` retains each source's independent `verified_at` (possibly `null` for supporting/terms records).
5. Primary and claim sources are required to be unique and verified before published evaluation; terms/supporting sources are not interchangeable with the primary.
6. `EligibilityResult.reasons` are **decisive**, not necessarily all rule outcomes; `rule_evaluations` is the complete record of configured rules, including satisfied/non-decisive rules.
7. An absent claim window produces `POTENTIALLY_ELIGIBLE`/`claim_window_unspecified`, not a fabricated open period; the existing five classifications and their precedence remain canonical.
8. Broad candidate matching excludes already non-matching published promotions by identity and purchase-date bounds; a no-match response is not equivalent to a fully evaluated `NOT_ELIGIBLE` result.
9. Existing API dates and timestamps use ISO/RFC 3339 serialization and preserve aware datetime instants. Verify existing OpenAPI examples and test fixtures before extending them.
10. The read transaction is repeatable-read, read-only and must remain detached from the serialized result.
11. Check whether an accessor is useful or whether the HTTP mapping can safely derive the new field directly from `provenance.verified_at`; avoid redundant mutable state.
12. Check current test commands and whether type checking is configured; do not assume an executable mypy command exists.

---

## Objective

Guarantee that **each matched promotion-variant result** returned by the canonical `check_purchase` use case and public eligibility API is independently traceable to:

1. The exact matched **promotion and variant** (stable UUIDs plus names).
2. The **outcome of every configured eligibility rule** (rule kind, satisfied/not satisfied/unknown status and stable reason code).
3. The **final eligibility classification** and all decisive machine-readable **eligibility reasons**, with existing deterministic human-readable explanation items.
4. The curated **official source** and claim link, with existing per-source provenance.
5. One explicit, unambiguous **`last_verified_at`** timestamp for the official primary source, directly available on the matched promotion response.

The contract must be consistent between application results and their HTTP representation, stable for consumers, deterministic for unchanged inputs/data and impossible to satisfy by inventing or silently defaulting source/evaluation facts.

Successful **unresolved identity** and **resolved no-match** outcomes must remain distinct and honest: neither contains a matched promotion, rule verdict, source or verification date. They retain their existing structured reason/explanation instead.

The work is complete when contract tests prove all five guarantees for matching variants, source-timestamp selection is precise, and existing response fields/eligibility decisions remain unchanged.

---

## Architecture and invariants

```text
POST /api/v1/eligibility/check
    -> request adapter / purchase_check_snapshot
    -> canonical check_purchase
       -> candidate matching + typed published details
       -> pure rule evaluations + existing classifier
       -> validated PublishedProvenance + source records
       -> immutable CheckPurchasePromotionResult
    -> explicit Pydantic map_result
    -> one independently explainable Promotion per matched variant
```

Required invariants:

1. **One source of truth:** use current `EligibilityResult`, `RuleEvaluation`, `PublishedProvenance` and `PromotionSourceRecord`; the HTTP mapper copies/derives fields and performs no rule evaluation or source inference.
2. **Per variant, not per purchase:** every element in `promotions[]` is a complete explanation for its `promotion_id`/`promotion_variant_id`; do not choose a "best" offer or merge variants.
3. **Decisions unchanged:** preserve all five classification values and current failed-rule > unknown-rule > claim-window precedence. An explanation bug must not change a verdict.
4. **Rules vs reasons:** always expose *all configured* rule evaluations even when some satisfied rules are non-decisive. Expose the classifier's decisive reasons separately; do not claim it evaluated unconfigured rules.
5. **Stable structure:** keep the existing field names and enumerations (`eligibility.classification`, `eligibility.rule_evaluations`, `eligibility.reasons`, `explanation`, `provenance`, `sources`). Add only a clearly documented field for last official verification; do not wrap or rename v1 data.
6. **Verification is recorded evidence, not a live check:** `last_verified_at` denotes the saved successful verification timestamp of the **PRIMARY** official promotion source. It is **not** the request time, retrieval time, latest claim/supporting source timestamp or proof that today's terms remain unchanged.
7. **No fake per-rule citations:** present official promotion-level provenance; the current schema does not link individual rules to source passages/pages. Do not invent such links.
8. **Failure closed on invalid published provenance:** if a matched published promotion has no valid, unique verified primary/claim provenance, fail with the existing published-data error, not an apparently successful partially explained result or a guessed URL/time.
9. **Deterministic order:** preserve PR 9 promotion-variant order, PR 10 rule order, PR 11 reason order and PR 17 stable source/benefit/requirement order; no extra sorting during HTTP serialization.
10. **Immutable, no IO:** application result values remain detached and immutable. Rendering must not query the database, load a website, consult an LLM, mutate evidence or read the clock.
11. **Evidence separation:** promotion `status == expired` does not itself mean an individual's claim is expired. Purchase-date candidate filtering is not a per-rule failure report for excluded promotions.
12. **Scope honesty:** publication checks verify curated record structure/provenance; they do not guarantee manufacturer claim approval or certify the source was independently checked by this runtime call.

---

## API and contract changes

### Canonical application result

Keep `CheckPurchaseResult` and `CheckPurchasePromotionResult` as the canonical result objects; do not create a parallel explainability hierarchy. Each successful matched result must continue to expose:

```text
CheckPurchasePromotionResult
  promotion_id: UUID
  promotion_variant_id: UUID
  promotion_name: str
  variant_name: str | None
  promotion_status: PromotionStatus
  eligibility:
    classification: EligibilityClassification
    reasons: tuple[EligibilityReason, ...]           # decisive and ordered
    rule_evaluations: tuple[RuleEvaluation, ...]     # ALL configured rules
    claim_window_status: ClaimWindowStatus | None
  explanation: tuple[str, ...]                       # derived, deterministic
  provenance:
    official_source_url: str
    source_type: SourceType
    retrieved_at: aware datetime
    verified_at: aware datetime                     # official primary
    claim_url: str
  sources: tuple[PromotionSourceRecord, ...]          # role, URL, timestamps
  ... existing claim_window, benefits, requirements ...
```

Require a discoverable `last_verified_at` concept with the same aware datetime value as `provenance.verified_at`. **Preferred minimal implementation:** a read-only computed `CheckPurchasePromotionResult.last_verified_at` property that returns `self.provenance.verified_at`, or equivalent mapping directly from canonical provenance without introducing a second stored timestamp. If a property is added, it must not change positional construction semantics, dataclass equality or API clients' existing fields.

No new application input, evaluation-time parameter, result classification, source fetch or persisted source field is required.

### Public v1 response

**Endpoint:** existing `POST /api/v1/eligibility/check`.

**Request:** unchanged. `brand`, `model`, `retailer`, `purchase_date` and optional `purchase_price`; strict input semantics remain as defined in PR 18.

**Success:** unchanged `200 OK` and `CheckResponse` discriminated union, `outcome: "resolved" | "unresolved_identity"`.

**Change:** add **required, non-null `last_verified_at: datetime`** to each `Promotion` object inside a resolved `promotions[]` item. Preserve `provenance.verified_at` for backward compatibility and explicitly define:

```text
promotion.last_verified_at == promotion.provenance.verified_at
```

Serialize as an RFC 3339 timezone-aware timestamp with an explicit offset (UTC may be `Z`). This already contains the last verification **date**; clients can format the date for display without the backend inventing a new calendar date or losing the source's time-zone information. Do not convert to an unqualified local date. The value must be taken from the unique validated PRIMARY source's `verified_at` via the canonical published provenance; never use `datetime.now()`, `evaluation_date`, `retrieved_at`, `max(sources.verified_at)` or another role.

The other four explainability guarantees remain **required existing fields**, not optional summaries:

| Requirement | v1 field(s) | Contract |
| --- | --- | --- |
| Matched promotion | `promotion_id`, `promotion_variant_id`, `promotion_name`, `variant_name` | IDs are stable UUIDs; retain separate variants. |
| Rule outcomes | `eligibility.rule_evaluations[]` | Every configured rule has typed `kind`, `status`, `reason_code`, including non-decisive satisfied rules. |
| Eligibility reasons | `eligibility.classification`, `eligibility.reasons[]`, `explanation[]` | Preserve decisive typed codes and deterministic display items; at least one eligibility reason. |
| Official source | `provenance.official_source_url`, `provenance.source_type`, `provenance.claim_url`, `sources[]` | Curated primary/claim links and full role-specific evidence; supporting URLs are not silently considered official. |
| Last verification | `last_verified_at`, `provenance.verified_at` | Same aware instant verified for the primary official source. |

A representative **matched promotion item fragment** (retain all other existing fields in the real response):

```json
{
  "promotion_id": "00000000-0000-0000-0000-000000000101",
  "promotion_variant_id": "00000000-0000-0000-0000-000000000102",
  "promotion_name": "Example TV Cashback",
  "variant_name": "75-inch model",
  "promotion_status": "active",
  "eligibility": {
    "classification": "ELIGIBLE",
    "reasons": [
      {"code": "all_configured_rules_satisfied", "rule_kind": null},
      {"code": "claim_window_open", "rule_kind": null}
    ],
    "rule_evaluations": [
      {"kind": "manufacturer", "status": "satisfied", "reason_code": "manufacturer_match"},
      {"kind": "product", "status": "satisfied", "reason_code": "product_match"},
      {"kind": "retailer", "status": "satisfied", "reason_code": "retailer_match"},
      {"kind": "purchase_date", "status": "satisfied", "reason_code": "purchase_date_match"}
    ],
    "claim_window_status": "open"
  },
  "last_verified_at": "2026-10-10T14:30:00Z",
  "provenance": {
    "official_source_url": "https://example.com/promotion",
    "source_type": "web_page",
    "retrieved_at": "2026-10-09T09:00:00Z",
    "verified_at": "2026-10-10T14:30:00Z",
    "claim_url": "https://example.com/claim"
  },
  "explanation": [
    "The recorded eligibility rules match this purchase.",
    "The claim window is open."
  ]
}
```

The example illustrates the **relevant fragment only**; the actual `Promotion` response must still include its required `claim_window`, `benefits`, `requirements` and `sources` fields. Dates and URLs above are illustrative fixtures, not real promotions or statements of verified offers.

**No match / unresolved:** preserve the existing union cases with their reason/explanation, and **do not** add nullable promotion/source/verification placeholders to these outcome envelopes. An empty `promotions: []` is correct when no published promotion matched the candidate filters. Unresolved identity must not expose `promotions` at all. Neither is an evaluated negative offer.

**Authentication/authorization:** unchanged public, read-only endpoint. **Sorting/pagination:** unchanged; return all matched variants in canonical order. **Idempotency:** no writes; repeatable input/snapshot/evaluation date yields the same response. **Compatibility:** the new required field exists only on successful per-promotion items and is additive to v1; do not delete, rename, reinterpret or change nullability of existing response fields. Update OpenAPI schema/docs/examples accordingly.

**Errors:** preserve existing 413/415/422/500/503 problem responses, existing codes, safe diagnostic detail and request correlation; do not expose a partial 200 or reclassify invalid published evidence as no match. No new error status or new error envelope is expected.

---

## Domain and application behaviour

### 1. Matched promotion identity

- Match only published active/expired variants returned by the canonical candidate flow.
- Return exact persisted promotion and variant IDs/names; if two variants share a parent, each retains its own rule outcomes, benefits, sources and verification timestamp.
- A matched-but-invalid projected graph remains a `PublishedPromotionDataError`; no silently missing identity fields.

### 2. Rule evaluation and reasons

- Keep all configured `RuleEvaluation` instances generated by `evaluate_eligibility_rules`, even when the classifier's decisive reasons mention only failures or unknowns.
- Preserve enum values and ordering from the domain. `satisfied`, `not_satisfied` and `unknown` must stay distinct; do not convert unknown facts into `not_satisfied`.
- Keep `eligibility.reasons[]` exactly aligned with the canonical classifier's decisive reasons and `explanation[]` deterministic and based on those reasons.
- If the claim window is absent, do not invent one. Preserve the existing `POTENTIALLY_ELIGIBLE` and `claim_window_unspecified` behaviour when applicable.
- Claim-window opening/deadline dates, rewards and requirements remain in their existing fields rather than being duplicated in free-text explanations.
- Do not infer channels, purchase condition, country, price restrictions, manufacturer requirements or rule-to-source citations from promotional copy.

### 3. Primary-source last verification

- `validate_publication_provenance` remains authoritative for unique PRIMARY and CLAIM roles, acceptable URLs, aware retrieval/verification timestamps and verification-after-retrieval constraints.
- Derive `last_verified_at` from `PublishedProvenance.verified_at` **only**. A newer CLAIM verification or a newer SUPPORTING/TERMS record cannot make a promotion's primary rules appear newly verified.
- Retain individual source roles and `verified_at` values without alteration. A supporting/terms source with `verified_at: null` remains visibly unverified; this cannot be silently replaced by primary verification.
- Different offset representations of the same instant remain valid; do not strip timezone info or round to the day in the canonical contract.
- No "last verified today", "currently valid" or "manufacturer-approved" message may be generated solely from the presence of a stored timestamp.
- If a primary/claim record is missing, ambiguous or invalid, preserve the existing published-data error path and avoid partial success. Do not guess officialness from URL hostname.

### 4. No-match, unknown and multiple results

- Ambiguous/not-found input returns the existing `UnresolvedPurchaseIdentity` outcome and explanation, without a matched promotion.
- Resolved identity with no matching published candidates returns empty `promotions`, `no_matching_published_promotions`, and the existing explanation; it is not an ineligible verdict.
- If there are several matches, every returned variant must individually satisfy this contract. Never let an invalid second variant disappear while returning an apparently successful first variant.
- `NOT_ELIGIBLE`, `POTENTIALLY_ELIGIBLE`, `CLAIM_NOT_YET_OPEN`, `EXPIRED` and `ELIGIBLE` matched results must all have evidence and rule/reason fields, without a different response schema for negative decisions.

### 5. Ingestion/publication rules

No ingestion or publication workflow changes. Unvalidated candidate records cannot appear in normal eligibility results. Existing source-role validation is the minimum for published provenance; historical rule-level source snapshots are outside this PR.

---

## Persistence, transactions, and migrations

**None.** `Source.verified_at` and all other needed fields already exist. The new field is a derived read-only application/API value and must not be written or stored a second time.

- Retain current PostgreSQL repeatable-read, read-only purchase-check snapshot and ORM-to-immutable projection.
- Keep historical active/expired visibility and current source associations unchanged.
- **No Alembic revision, data backfill, new table/index/column or altered source timestamp is expected.**
- Verify against the existing real PostgreSQL/Testcontainers integration fixtures that both eligibility and official verification are read from the same coherent snapshot, and that repeated requests create no writes.

---

## External services and network access

**None.** Reading and displaying a previously curated URL does not trigger a network request. Do not add background verification, HTTP fetches, manufacturer APIs, model-provider calls, retries or external dependencies.

---

## Security and privacy

- Preserve the endpoint's existing body limits, input validation, public read-only semantics and safe `application/problem+json` mapping.
- Only return already-curated, valid source URLs and provenance; never trust arbitrary submitted links or invent an official source from hostnames.
- Treat source descriptions/URLs as **data**, never instructions or rendered executable HTML. The API returns structured strings; avoid unsafe HTML/Markdown injection or auto-fetch on the server.
- Do not include request bodies, personal purchase details, full source URLs (which may contain query parameters), credentials, exception messages or raw source documents in logs/Sentry.
- Validation failures in published content must not leak database details or partially trustworthy results.
- No new access-control mechanism, secrets or user personal data storage is required.

---

## Configuration and deployment

**None.** No environment variables, secrets, packages, migrations, workers, scheduling, container changes or deployment settings are introduced. The existing API response is expanded additively; clients consuming `Promotion` objects should be informed of `last_verified_at`.

### Environment variables

None.

### Runtime/deployment changes

None.

---

## Observability and operations

- Keep existing `check_purchase_completed`, `eligibility_http_check_completed` and structured failure categories/request IDs; no second telemetry system.
- Source/provenance contract failures continue to be recorded as safe `data_integrity` failures with stable error codes; preserve normal client-facing 500 behaviour for invalid published evidence.
- Do not log purchase values, source URLs or timestamps at high cardinality. Do not treat stale-looking timestamps as live monitoring failures: no freshness threshold exists in this task.
- Health/readiness behaviour, Sentry sanitisation and classification counts remain unchanged.

---

## Failure, consistency, and recovery

| Scenario | Required outcome |
| --- | --- |
| Primary or claim source missing, ambiguous, unverified or malformed | Existing published-data failure; safe 500 for HTTP; no partial response and no mutation. |
| More recent claim/supporting verification than primary | `last_verified_at` still equals the validated primary's `verified_at`; other timestamps stay attached to their source roles. |
| Supporting/terms source has `verified_at: null` | Preserve `null` in `sources[]`; do not infer or copy official-primary verification to that record. |
| Malformed projection or missing candidate details | Existing consistency/data error, not `NOT_ELIGIBLE` or silent omission. |
| Ambiguous purchase identity or zero candidates | Distinct successful non-promotion outcome with existing reason/explanation; no fabricated source or time. |
| Concurrent publication/source updates during a check | Existing read-only repeatable-read snapshot gives a coherent result; later check may reflect a newer committed snapshot. |
| Repeated identical check | Identical fields and order for the same evaluation date/data; no writes. |
| API serialization fails | Preserve safe 500 and ensure the database snapshot closes; never return incomplete JSON with a 200 status. |

No recovery worker, retry policy or new persisted pending state is required.

---

## Acceptance criteria

### Behaviour

- [ ] Every returned `promotions[]` item has exact `promotion_id`, `promotion_variant_id`, names and existing lifecycle status.
- [ ] Every matched item has `eligibility.classification`, non-empty structured `eligibility.reasons`, complete ordered `eligibility.rule_evaluations` and ordered deterministic `explanation`.
- [ ] All configured rule statuses (`satisfied`, `not_satisfied`, `unknown`) and their reason codes survive application-to-HTTP mapping without a lost non-decisive result.
- [ ] All five existing eligibility classifications are exercised, with **no change** to canonical classification or claim-window precedence.
- [ ] Every matched item has curated `provenance.official_source_url`, `provenance.claim_url`, original timestamps and ordered role-specific `sources[]`.
- [ ] Every matched API `Promotion` includes required, non-null aware `last_verified_at`, **equal as an instant** to `provenance.verified_at` from the unique PRIMARY source.
- [ ] A CLAIM/SUPPORTING/TERMS source with a later `verified_at` does not change primary `last_verified_at`.
- [ ] Unverified supporting sources retain `verified_at: null`; source roles/URLs are not inferred, rewritten or dropped.
- [ ] Multiple matching variants each independently satisfy every explainability guarantee.
- [ ] Resolved no-match and unresolved identity retain distinct existing outcomes/reasons and do not claim nonexistent matched evidence.
- [ ] Human-readable descriptions do not invent restrictions, monetary guarantees, live validation or precise per-rule citations.

### Data and consistency

- [ ] Invalid published primary/claim provenance or incomplete matched projections cannot produce a successful partial response.
- [ ] Active/expired published filtering and candidate order remain unchanged; unpublished/archived records are not exposed.
- [ ] Application result remains immutable, session-detached and deterministic across identical checks.
- [ ] Real PostgreSQL snapshot tests show no writes and no mixed old/new source/result state.
- [ ] No migration or duplicate verification timestamp column is introduced.

### API compatibility

- [ ] Existing endpoint, request fields, outcome union, success/error statuses and current response fields retain meanings and nullability.
- [ ] OpenAPI models and representative full response examples include required `last_verified_at` with `date-time` semantics for matched promotions.
- [ ] Serialization preserves RFC 3339 offset-aware instants and structured enum values; no `datetime.now()` in mapping.
- [ ] Existing downstream consumers of `provenance.verified_at` continue to work.

### Security

- [ ] Invalid evidence yields existing safe problem details without internal exceptions/PII; no source is guessed.
- [ ] No network calls, LLM calls, credentials, extra data storage or authentication bypass is introduced.

### Operations and code quality

- [ ] Existing safe structured logging/Sentry behaviour and resource bounds remain intact.
- [ ] No unnecessary refactor, new parallel explanation layer, dependency or infrastructure change.
- [ ] Targeted unit, FastAPI contract, PostgreSQL integration and broader required checks pass (or unavailable commands and risks are reported precisely).

---

## Tests to add or update

### Unit tests

**`backend/tests/unit/test_purchase_check.py`**

- Assert the complete matched result includes identity, **all** rule evaluations, decisive reason codes, ordered explanation, original provenance and timestamp; assert no required evidence disappears for a negative/uncertain classification.
- Assert application `last_verified_at` (if accessor added) equals `result.provenance.verified_at` and is aware, while the result stays frozen/detached.
- Use different explicit aware datetimes for primary, claim and supporting sources (including a *newer* claim/supporting time); assert the primary's timestamp is authoritative for the summary field.
- Keep unknown/absent claim-window and multi-variant ordering regressions. Test primary source invalid/unverified errors rather than fallback/default behaviour.

**`backend/tests/unit/test_eligibility_api.py`**

- Verify the required new field is present for every matched promotion, unchanged old `provenance.verified_at` and correct RFC 3339 serialization (including offset-aware timestamps).
- Parametrize all five classifications with populated reasons and rule evaluations, including non-decisive satisfied rules plus decisive failing/unknown rules.
- Assert mismatched record roles cannot affect `last_verified_at` and supporting `verified_at: null` stays `null`.
- Assert resolved no-match/unresolved responses contain no bogus promotion/verification fields; existing request validation/errors remain the same.
- Assert the generated OpenAPI schema makes `last_verified_at` **required** on `Promotion` and typed `string`/`date-time`; validate complete examples against the response schema.

### PostgreSQL integration tests

**`backend/tests/integration/test_check_purchase.py`** and **`backend/tests/integration/test_eligibility_api.py`**

- With seeded active and expired variants, assert identity, structured reasons, all configured rule evaluations, primary source URL and `last_verified_at` are coherent after the session closes.
- Seed distinct primary vs claim/supporting verification instants and test that the API timestamp is from primary, not latest-of-all. Preserve per-source values.
- Verify the existing repeatable-read/read-only snapshot, candidate ordering, safe failure for missing official evidence and no new INSERT/UPDATE/DELETE/COMMIT operations.
- Reuse existing Testcontainers/PostgreSQL setup; no new migrations expected.

### API/application tests

- Existing FastAPI tests must continue to cover `200` resolved/unresolved/no-match, validation (`413/415/422`), corrupted published data (`500`), persistence availability (`503`) and safe payloads.
- Ensure API only serializes existing application results; a transport unit test should detect any duplicate application rule-classification path.

### MCP contract tests

**N/A.** No MCP adapter is present in the inspected main branch. If one is added independently before PR 26 implementation, preserve the shared application semantics and add contract parity only as needed; do not create an MCP server in this PR.

### External-boundary tests

**N/A.** No external fetch/model provider is used. Fixed source fixtures and timestamps only; no live brand websites.

---

## Verification commands

Run from `backend/`. These commands are grounded in the current `backend/README.md` and `backend/pyproject.toml`:

```bash
# Dependency sync (if required)
uv sync --locked --extra dev

# Formatting
uv run ruff format --check .

# Lint
uv run ruff check .

# Targeted pure application + API tests
uv run pytest tests/unit/test_purchase_check.py tests/unit/test_eligibility_api.py

# Real PostgreSQL tests (requires Docker / Testcontainers)
uv run pytest tests/integration/test_check_purchase.py tests/integration/test_eligibility_api.py

# Broader backend suite
uv run pytest
```

No mypy/pyright task is currently configured in `pyproject.toml`; do **not** invent or claim a passing type-check command. No migration verification command is needed when no schema changes are made. If implementation unexpectedly modifies persistence, revisit that decision and verify Alembic upgrades against real PostgreSQL.

If a command cannot run, state the exact command, reason, alternative checks actually performed and remaining risk. Do not claim a command passed without running it or weaken tests merely to obtain green results.

---

## Completion report

When implementation is complete, report:

### Changed

Summarise the per-promotion explainability guarantee, `last_verified_at` derivation and the modules/contract changes.

### Database and migrations

`None` expected. State actual deviations if any.

### API/MCP contracts

Document the additive `Promotion.last_verified_at` response field; existing v1 fields and errors unchanged. MCP: `None` expected.

### Tests and verification

List test additions/updates, exact verification commands **actually run**, and results; distinguish passed, failed and unavailable.

### External configuration

`None` expected.

### Deviations

State any departures from this spec and why, or `None`.

### Remaining risks or follow-up

Explicitly note that source verification is a recorded timestamp, **not** automatic freshness assurance, manufacturer acceptance, immutable source-version evidence or rule-level citations. Report other remaining issues, or `None` if fully complete within this task's scope.
