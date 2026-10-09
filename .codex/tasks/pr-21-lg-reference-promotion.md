# PR 21 — LG Reference Promotion

## Repository state

**Expected branch:**  
`pr21-lg-reference-promotion`

**Base branch:**  
`main`

**Dependencies:**

- PRs 3–7: promotion graph, lifecycle/history, source provenance, canonical manufacturer, product and retailer identity.
- PRs 9–15: promotion candidate matching, typed eligibility rules/classification, fixed claim windows, requirements and fixed GBP cashback rewards.
- PRs 17–18: canonical `check_purchase` and the read-only eligibility HTTP API.
- PR 19: validated candidate promotion format and persisted publication gate.
- **PR 20 (merged 9 October 2026):** reviewed Samsung reference data, offline constructor, publication/expiration replay and end-to-end PostgreSQL regression tests.
- Existing Python 3.13, `uv`, SQLAlchemy, Alembic, pytest, Ruff and PostgreSQL/Testcontainers tooling.
- **Number verification (9 October 2026):** GitHub PR #20 is merged into `main`; PR **#21** is the next implementation PR number. Verify the number remains available immediately before creating the implementation PR.

### Read first

- Root `AGENTS.md` and any nearer scoped guidance introduced before implementation.
- `.codex/tasks/TEMPLATE.md` and `.codex/tasks/pr-20-samsung-reference-promotion.md`.
- `.codex/tasks/pr-12-fixed-claim-windows.md`, `.codex/tasks/pr-15-reward-calculation.md`, `.codex/tasks/pr-17-check-purchase-eligibility-service.md`, `.codex/tasks/pr-19-promotion-authoring-validation-format.md`.
- `backend/tests/fixtures/promotions/README.md`, `backend/tests/samsung_reference.py`, `backend/tests/unit/test_samsung_reference_promotion.py`, and `backend/tests/integration/test_samsung_reference_promotion.py`.
- `backend/README.md` and the canonical application/domain/repository code listed below.

### Primary change area

**A curated, evidence-backed historical LG cashback promotion, test-only reference construction/publication and deterministic eligibility regression coverage.** This is one deliberately bounded campaign reference, not a general promotion ingestion service or a full LG promotion catalogue.

### Canonical implementation examples

- `backend/tests/samsung_reference.py` — semantic manifest validation, unambiguous identity reuse, atomic construction, `CandidatePromotionV1` preflight, lifecycle replay.
- `backend/tests/fixtures/promotions/samsung-summer-wallet-cashback-2026.json` — versioned reviewed facts, official evidence map and limitations.
- `backend/tests/integration/test_samsung_reference_promotion.py` — Testcontainer-backed lifecycle, persistence, snapshot, API and negative-case tests.
- `backend/tests/unit/test_samsung_reference_promotion.py` — source facts, boundary math and domain-only condition checks.
- `backend/app/application/promotion_authoring.py`, `backend/app/domain/promotion_validation.py`, `backend/app/application/promotions.py` — authoritative candidate and publication boundaries.
- `backend/app/db/repositories/promotions.py`, `backend/app/application/purchase_check.py`, `backend/app/domain/claim_windows.py`, `backend/app/domain/rewards.py` — canonical persisted read, classification, claim deadline and reward calculation.
- `backend/app/db/models/core.py`, `backend/app/db/models/identity.py` — existing ORM graph/identity constraints.

### Relevant symbols

```text
CandidatePromotionV1, parse_candidate_promotion, validate_candidate_promotion
PromotionValidationSnapshot, validate_promotion_for_publication
PromotionStatus, change_promotion_status, promotion_transaction
Manufacturer, Product, Retailer, Promotion, PromotionVariant
PromotionVariantProduct, Benefit, BenefitReward, Requirement, Source, PromotionSource
IdentityResolver, SqlAlchemyIdentityRepository, MatchStatus
SourceRole, SourceType, PromotionSourceRecord, PublishedProvenance
CheckPurchaseRequest, check_purchase, purchase_check_snapshot
FixedClaimWindow, evaluate_fixed_claim_window
EligibilityClassification, EligibilityReasonCode, PurchaseConditionRule
NoMatchReason.NO_MATCHING_PUBLISHED_PROMOTIONS
uk_evaluation_date, POST /api/v1/eligibility/check
```

### Expected change surface

```text
.codex/tasks/pr-21-lg-reference-promotion.md                          # this specification
backend/tests/fixtures/promotions/lg-g5-cashback-2025.json            # NEW, reviewed source facts
backend/tests/fixtures/promotions/README.md                           # extend with distinct LG evidence/coverage
backend/tests/lg_reference.py                                         # NEW, test-only constructor; mirror Samsung pattern
backend/tests/unit/test_lg_reference_promotion.py                     # NEW, manifest and deterministic domain checks
backend/tests/integration/test_lg_reference_promotion.py              # NEW, actual PostgreSQL regression
backend/README.md                                                     # short reference-test pointer if useful
```

Additional narrow changes are permitted if existing conventions genuinely require them; explain deviations. **No migration, runtime application module, or externally visible contract change is expected.** Do not duplicate all Samsung helper code if a *small, demonstrably safe* existing shared test utility suffices, but avoid a broad reference-ingestion framework/refactor in this PR.

### Excluded areas

- No automatic startup seeding, production deployment of historical data, scheduled ingestion, live source crawling, claims submission, payments, bank account collection, LLM extraction, admin UI or generic publisher/importer.
- No REST/MCP route, input/output schema, authentication, customer record, frontend or background job changes.
- No migration, generalized claim-window DSL, new eligibility-rule type, production special-case for LG, or silent override of the publication gate.
- Do not call this reference a complete set of all OLED G5 eligible models; this PR intentionally covers **one** confirmed product at **one** confirmed retailer.
- No live LG requests during CI, purchase checks, or application startup.

### Unknowns Codex must verify

1. PR #20 is merged and its test-only helper/fixtures are available on the selected base commit. Confirm no parallel PR #21 or later spec now exists.
2. Whether canonical LG, `LG.com/UK` or `OLED55G54LW.AEK` identities/aliases already exist; resolve/reuse only unambiguous matches.
3. Exact `Product.model_number` and alias semantics, including **preservation of `.AEK`**. Never collapse to the generic OLED G5 family.
4. Whether PR 19's candidate preflight remains non-authoritative and whether `review → active` publication still validates persisted source and product links.
5. Whether the existing fixed claim window is inclusive at both endpoints; `claim_start_date` and `claim_end_date` are distinct from purchase dates and from the 30-day **validation** delay.
6. Whether an expired but previously published promotion is still matched and checked for an injected historical evaluation date (currently yes).
7. Whether known mismatching model/retailer/purchase date results in **no matching published promotion**, rather than `NOT_ELIGIBLE` (currently yes), and whether unknown identities yield an unresolved-identity result.
8. Exact test fixture/session cleanup and source reuse behavior; avoid deleting pre-existing manufacturer, product, retailer or sources shared with other references.
9. Whether schema source links require distinct `primary` and `claim` source IDs (currently yes); a claim destination evidenced by the official LG terms is **not** necessarily an independently reachable claim site.

---

## Objective

Add one **real, reproducible LG cashback reference** for the **LG OLED G5 Cashback Promotion (UK), 21 May–24 June 2025**, restricted to an **LG OLED55G54LW.AEK purchased directly from LG.com/UK**. The authoritative LG terms specify **GBP 150.00 cashback** and an inclusive **19 August 2025 claim-submission deadline**. Claim submission is allowed on/after the qualifying purchase; **LG's 30-day delay is a processing/validation delay, not a 30-day wait before a consumer may submit a claim**.

Produce a reviewed offline JSON manifest with documented source evidence and limitations; build a single valid persisted reference graph through existing identity/publication/lifecycle boundaries; and regression-test the **real** PostgreSQL-backed `check_purchase` use case plus existing HTTP adapter for valid purchases, exclusions/no matches, historical expiry and exact purchase/claim boundary dates.

The finished historical record is `expired` (as of 9 October 2026), but remains queryable. No test should depend on live LG pages, current system time or application startup writes. The result confirms the engine handles documented structured facts; it does **not** guarantee LG would accept any particular claimant's submission.

---

## Architecture and invariants

```text
LG Electronics UK official T&Cs (human-reviewed; source of truth)
  → versioned local reference manifest + reviewed clause map
  → test-only constructor using canonical identities and existing ORM
  → PR 19 candidate preflight (not authoritative)
  → persisted review graph → existing publication gate
  → active → expired (historical reference)
  → PostgreSQL repeatable-read snapshot
  → canonical check_purchase → unchanged HTTP serializer
```

- **Purchase promotion period:** 2025-05-21 through 2025-06-24, inclusive.
- **Claim submission window:** fixed `2025-05-21` through `2025-08-19`, inclusive **at calendar-date resolution**. The claimant may only submit **after their own purchase**; the fixed-window model alone cannot express that additional per-purchase relationship when an artificial evaluation date is earlier than the supplied purchase date. Use realistic evaluation dates (`evaluation_date >= purchase_date`) in purchase-check regressions; document the representational limit instead of inventing a constraint.
- **Claim processing/validation:** LG says it happens **after 30 calendar days from purchase**, which does **not** change the claim opening date or final submission deadline. Do not use `RelativeClaimWindow(start_offset_days=30, ...)`, and do not show `CLAIM_NOT_YET_OPEN` merely because 30 days have not elapsed since purchase.
- Fixed windows are inclusive by the current date-only domain contract. The official terms specify a final **23:59 GMT** submission cut-off; the current purchase-check contract cannot evaluate time of day or exact GMT/BST boundaries. Do not claim minute-level enforcement.
- Official source provenance must be persisted, with real observed UTC-aware retrieval/verification timestamps and a verified official terms URL. Never backfill guessed review times.
- Historical lifecycle (`expired`) and computed eligibility/claim classification are **different axes**: for an explicitly historical evaluation date while claims were open, the returned classification may be `ELIGIBLE` even though the stored promotion lifecycle is `expired` today.
- Use the same domain/application/database code as every other purchase check; **no LG-specific runtime branch** or publication shortcut.
- `ELIGIBLE` means recorded/representable conditions match while the submission window is open, not that age, residency, receipt authenticity, returns, prior claims or other external restrictions have been verified.

---

## API and contract changes

**No public REST, MCP or application-service API change.** Preserve `CheckPurchaseRequest` (`brand`, `model`, `retailer`, `purchase_date`, optional `purchase_price`) and existing `POST /api/v1/eligibility/check` payload/result shapes and error semantics. The reference fixture is test data, never an API endpoint.

Provide a versioned, validated local manifest of *reviewed* facts, e.g.:

```json
{
  "reference_version": 1,
  "campaign": "LG OLED G5 Cashback Promotion 2025 (UK)",
  "promotion_slug": "lg-g5-cashback-2025-oled55g54lw-lg-com-uk-reference",
  "coverage": "OLED55G54LW.AEK purchased directly from LG.com/UK only; not the full G5 campaign",
  "manufacturer": "LG",
  "product": {"name": "LG OLED G5 55-inch TV", "model_or_sku": "OLED55G54LW.AEK"},
  "retailer": "LG.com/UK",
  "purchase_start_date": "2025-05-21",
  "purchase_end_date": "2025-06-24",
  "claim_window": {
    "type": "fixed",
    "start_date": "2025-05-21",
    "end_date": "2025-08-19"
  },
  "benefit": {
    "type": "cashback",
    "reward": {"type": "fixed_amount", "amount_gbp": "150.00"}
  },
  "official_terms_url": "https://www.lg.com/uk/tncs/g5-cashback/",
  "claim_url": "https://www.lgcashback.com/g5"
}
```

This is a **human-curated reference-data contract, not a replacement for `CandidatePromotionV1`**. Extend the file with structured `evidence` (official section/clause anchors, `reviewed_on`, truthful source-specific verification notes and genuinely captured timestamps if available), `requirements` and `limitations` as in PR #20. Do **not** commit made-up UUIDs, fake retrieved/verified timestamps, an assertion that the closed historical claim portal is live, or source text masquerading as executable rules. Resolve UUID identities first, then validate a UUID-based PR 19 candidate document where appropriate. Use exactly documented schema keys and fail closed on semantic unreviewed changes; consider the existing reviewed SHA-256 approach.

**Scope limitation:** The official terms contain other qualifying G5 models and different payout amounts; the local reference and test assertions must not be described as representing all eligible models or retailers. A test of another model not included in the reference must be labelled **out of reference scope**, not asserted to be excluded from LG's whole promotion.

---

## Domain and application behaviour

### 1. Official LG facts and evidence mapping

**Primary authoritative source (reviewed 9 October 2026):** <https://www.lg.com/uk/tncs/g5-cashback/>. Review again during implementation for changes or corrections. Treat the official full terms as authoritative over summary/banner copy.

| Fact | Exact reviewed value | Official LG evidence |
| --- | --- | --- |
| Campaign | LG's Cashback Promotion on LG OLED G5 TVs | Terms heading and summary |
| Promoter | LG Electronics U.K. Ltd | Summary and promoter address |
| Eligible participant | UK resident, at least 18; exclusions for associated persons | Full terms: Eligibility §1 |
| GBP banking | GBP bank account with details matching the claim form | Eligibility §2; Cashback Claim §13 |
| Purchase dates | **21 May–24 June 2025** inclusive | Summary; Eligibility §4 |
| Store scope | **LG.com/UK** only in the listed retailer table | Eligibility §§3–4; Participating Retailers §22 |
| UK model/SKU | **`OLED55G54LW.AEK`** | Qualifying Products table |
| Cashback for this SKU | **GBP 150.00** | Qualifying Products table, `OLED55G54LW.AEK` row |
| Product condition | Genuine, new UK variant; second-hand/refurbished/reconditioned excluded | Eligibility §4; General Conditions §27 |
| Submission opens | After purchase; registration can happen on purchase day | Eligibility §4; Cashback Claim §12 |
| Last submission | **19 August 2025 at 23:59 GMT**, inclusive date | Eligibility §§4, 6, 9 |
| Claim form | `https://www.lgcashback.com/g5` (**destination cited by LG terms, not independently checked**) | Eligibility §§4, 6; Cashback Claim §12 |
| Evidence required | Readable serial number plus full receipt or online order confirmation | Eligibility §§6–7 |
| Validation delay | LG processes/validates after **30 calendar days from purchase** | Eligibility §§4, 6; Cashback Claim §12 |
| Bulk/returns restrictions | More than 10 qualifying items excluded; cancellation/return invalidates claims | Eligibility §§10, 18–20 |

**Additional caution:** The LG page contains other model lists outside the G5 reward table. Only the explicit **G5 Qualifying Products reward table** authorizes this SKU and **£150** for this particular cashback reference. Do not treat unrelated LG product tables or present-day promotions as evidence for the reference reward.

The official terms name `www.lgcashback.com/g5`; the canonical `https://` URL above is the expected claim destination to preserve and resolve as an externally linked source. **Do not claim direct reachability, live claim acceptance or successful form verification** without actually verifying it. The historical deadline is past.

### 2. Product, retailer, cashback and requirements

- Manufacturer: **LG**; resolve canonical LG/LG Electronics aliases where unambiguous rather than introducing a second manufacturer.
- Product: one exact UK variant `OLED55G54LW.AEK`; preserve `.AEK` throughout matching and fixture assertions. A shortened `OLED55G54LW` or marketing-family string is not automatically equivalent to the verified variant unless a previously reviewed, unambiguous alias is explicitly established.
- Retailer: canonical **LG.com/UK**. This reference variant must have a **non-null `retailer_id`**. Known unrelated stores must not match the reference; marketplace/third-party seller information is not available in the current public request.
- Benefits: exactly one `cashback` with `FixedAmountReward(Decimal("150.00"))`, independent of optional purchase price. Never treat `£150` as a percentage and never use floating point.
- Requirements: typed `receipt` (receipt/order confirmation) and `serial_number` (readable serial number). Bank details/identity information needed on LG's own form belongs in verified claim instructions, **not** PII-filled tests or an invented built-in requirement enum.
- Place the scope, historical status and unsupported real-world participation checks in safe display descriptions/manifest `limitations`, not in fabricated rules or guaranteed-payout claims.
- No condition, country, age, bank-account, purchase-volume, returned-item or third-party-seller evaluation is claimed from the existing five-field v1 purchase input. The requirements list is advice about evidence, not proof of submission or satisfaction.

### 3. Manifest, publication and lifecycle

1. Record the official terms URL, section-level evidence anchors, `reviewed_on = 2026-10-09`, and explicit notes about portal accessibility. At implementation record **real** timezone-aware retrieval/verification timestamps for source records; don't synthesize them from this spec's review date.
2. Parse and validate the local reviewed facts before constructing ORM rows. Reject malformed dates, unrecognized/changed model, unreviewed amount changes, missing or altered official URL, omitted evidence, unknown fields and unapproved modifications. Use a reviewed semantic digest or equivalently strict versioned-facts check, without silently normalizing contradictory data.
3. Resolve LG, exact product and LG.com/UK identities using the existing matching repository; reject ambiguity, conflicts or wrong-manufacturer product links. Construct one uniquely slugged promotion graph in `review` in the caller-controlled transaction.
4. Link exactly one primary source (LG official terms page, `web_page`), one distinct claim source (LG-designated portal, `web_page`) and optional *genuinely corroborating* sources only if actually verified. Do not link the same `Source` UUID twice under different roles; follow uniqueness rules. A claim URL sourced from primary terms is a documented destination, not proof the portal was visited.
5. Use PR 19's candidate preflight as a validation step, but publish **only through** the established persisted `change_promotion_status(..., ACTIVE)` validation gate. No direct mutation to `active`.
6. Complete by transitioning `ACTIVE → EXPIRED` using the existing lifecycle service. Never serve this 2025 promotion as a newly current offer on 9 October 2026, and never change existing published history merely to replay the fixture.
7. On replay, compare the full graph (facts, amounts, condition limitations, sources, URLs, timestamps, roles, requirements and dates) with the reviewed reference. Return the same object and reconcile `review`/`active` safely to `expired`; already `expired` is a no-op. On conflicting graph or invalid lifecycle, fail without silently replacing data.
8. Use a **test-only constructor** as in PR #20; no CLI loader is required and no production seed is authorised by this spec. If an operator loader is later proposed, require a separately reviewed scope and production safety gate.

### 4. Exact expected eligibility regression matrix

Use `CheckPurchaseRequest(brand="LG", model="OLED55G54LW.AEK", retailer="LG.com/UK", purchase_date=<date>)`, defaulting optional purchase price to `None`, the **real** PostgreSQL snapshot, and an explicitly injected `evaluation_date`. The constructed/published reference's lifecycle state is `expired` for all table cases. Assert one reference result for matching rows.

| Purchase date | Evaluation date | Expected computed result | Reason |
| --- | --- | --- | --- |
| 2025-05-21 | 2025-05-21 | `ELIGIBLE` | First allowed purchase day; submission can begin immediately |
| 2025-05-21 | 2025-05-22 | `ELIGIBLE` | No erroneous 30-day claim-opening delay |
| 2025-06-24 | 2025-06-24 | `ELIGIBLE` | Last allowed purchase date; claim may be submitted at purchase |
| 2025-06-24 | 2025-08-18 | `ELIGIBLE` | Day before the fixed claim deadline |
| 2025-06-24 | 2025-08-19 | `ELIGIBLE` | Fixed claim-deadline **date inclusive** |
| 2025-06-24 | 2025-08-20 | `EXPIRED` | First calendar date after deadline |
| 2025-06-24 | 2026-10-09 | `EXPIRED` | Historical check today; published data still queryable |
| 2025-05-20 | 2025-05-21 | **No matching published promotion** | Purchase before the promotional period |
| 2025-06-25 | 2025-06-25 | **No matching published promotion** | Purchase after promotional period |
| 2025-06-01 | 2025-06-01 | **No matching published promotion** | Known unrelated test retailer or known unrelated test model |

For matched cases, assert `claim_window.opens_on == date(2025, 5, 21)` and `deadline_on == date(2025, 8, 19)` **regardless of whether the qualifying purchase was in May or June**; fixed cashback `Decimal("150.00")` without purchase price; `promotion_status == expired`; stable reason codes `all_configured_rules_satisfied` and `claim_window_open`/`claim_window_expired`; official source URL; claim URL; required receipt/serial; and explanatory text.

**Important distinction:** Purchase dates outside the period and **known** disallowed retailer/test model are filtered out during candidate matching, producing `CheckPurchaseResult(promotions=(), no_match_reason="no_matching_published_promotions")`—**not** a `NOT_ELIGIBLE` item. Unknown strings may produce `UnresolvedPurchaseIdentity`; seed separate artificial identities for known non-matches. If a different **legitimately participating LG G5** model is outside the single-SKU fixture, that is **out of reference coverage**, not definitive disqualification from LG's campaign.

**Ineligible semantics:** Add a separate *pure domain* check of LG's new-only condition: `PurchaseConditionRule({PurchaseCondition.NEW})` with `REFURBISHED` → `NOT_ELIGIBLE` (`condition_mismatch`), and unknown condition → `POTENTIALLY_ELIGIBLE` (`condition_unknown`). This **must not** be represented as a condition validated through the existing HTTP request or persisted LG reference when that request contains no condition field.

**Fixed opening semantics:** Unit-test `FixedClaimWindow(2025-05-21, 2025-08-19)` at **2025-05-20** → `NOT_YET_OPEN`, **2025-05-21** → `OPEN`, **2025-08-19** → `OPEN`, **2025-08-20** → `EXPIRED`. Do not simulate a valid purchase on May 21 and evaluate it May 20 through the purchase service (that would be a future-dated purchase, not evidence of a consumer's claim status).

---

## Persistence, transactions, and migrations

**No schema migration or data backfill.** Reuse the existing `manufacturers`, `products`, `retailers`, `promotions`, `promotion_variants`, `promotion_variant_products`, `benefits`, `benefit_rewards`, `requirements`, `sources`, `promotion_sources` and alias tables as appropriate.

- Use a stable unique LG reference slug, never a Samsung slug or a generic global `lg-g5` identifier likely to collide with broader future campaigns.
- Resolve before inserting; avoid duplicate LG manufacturer and retailer rows, preserve `OLED55G54LW.AEK` canonical precision, and reject ambiguous identity matches.
- Persist fixed `claim_start_date = 2025-05-21` and `claim_end_date = 2025-08-19` with **both relative offsets null**. Persist purchase date boundaries independently.
- Persist a single fixed GBP reward, typed requirements and distinct primary/claim sources with meaningful titles. `retrieved_at` and `verified_at` must be genuine UTC-aware instants, with `verified_at >= retrieved_at` and provenance surviving the transition to `expired`.
- Construction must be atomic within the caller's transaction/savepoint and must not accidentally flush/rollback a caller's unrelated pending changes. Reuse PR 20's defensive pattern unless a clearly safer narrow implementation is justified.
- Repeated build/finish operations must not duplicate graph rows, payment-like effects or source references; a conflicting existing graph fails safely rather than overwriting or reactivating it.
- Verify PostgreSQL constraints and rollback using migrated Testcontainers. No SQLite stand-in for the integration checks. Keep test cleanup scoped only to rows owned by the fixture; never delete reused reference/identity rows belonging to other tests.

---

## External services and network access

**No runtime, import-time or CI network access to LG is required or permitted.** The authoritative LG terms and designated claim URL are **stored evidence links**, not remote test dependencies. CI must use local deterministic facts. Do not introduce an `httpx` or browser source fetch in `check_purchase`, fixtures, publication tests or API startup.

External evidence referenced:

- Primary: <https://www.lg.com/uk/tncs/g5-cashback/> — official LG UK 2025 G5 campaign terms, read/reviewed **9 October 2026**.
- Claim destination: <https://www.lgcashback.com/g5> — explicitly named in official LG terms. Current portal reachability and claim acceptance **not established**; do not assume the historical form is still accessible.

If LG has amended the official terms between this spec and implementation, a maintainer must review the differences and update manifest/spec evidence consciously before publication; never silently import changed pages or pin a guessed timestamp. No network adapter, credentials, retry/timeout policy or remote fetch job is introduced here.

---

## Security and privacy

- Do not store customer receipts, serial numbers, identities, addresses, bank details, purchase histories or live claim forms in reference fixtures. Requirements are types/instructions only.
- Validate local manifest facts and URLs as untrusted data even when curated. No executable rules, `eval`, untrusted deserialization, arbitrary fetches or new public write capability.
- Preserve the established publication guard and source verification checks. Candidate preflight does not confer publish authority.
- Do not assert that a v1 match verifies UK residency, age ≥18, GBP bank account, condition, prior claims, product returns, bulk-purchase cap or seller details. These are LG-side restrictions not present in the five-field request.
- Do not expose stored source metadata as a claim that the claim portal was visited. Do not display a 2025 historical offer as currently claimable.
- No changed authentication/authorization boundary; all test-only graph writes occur in an explicit isolated test database.

---

## Configuration and deployment

**None.** No new or changed environment variables, dependencies, service settings, Docker images, Railway configuration, startup writes, migrations, cron tasks or production seed. Use existing `DATABASE_URL` only through test fixtures backed by the disposable PostgreSQL Testcontainer. The LG reference must not be loaded into a live deployment by mere application startup.

---

## Observability and operations

- Reuse existing structured logs and safe publication error diagnostics; no new telemetry stack.
- For test-only replay, surface deterministic created/reused/expired/conflict behavior through assertions rather than production metrics.
- Distinguish expected reference conflicts/validation rejections from database failures. No personal data, raw credentials or potentially sensitive vendor payloads in logs.
- No health, readiness, Sentry, HTTP error-envelope or operational alert changes.

---

## Failure, consistency, and recovery

- **Manifest drift / unsupported fact:** reject on malformed or unreviewed data (especially altered SKU, cashback amount, retailer, dates, URL or requirements); do not repair silently. Re-review evidence and version/pin deliberately.
- **Identity ambiguity:** fail closed with a clear non-sensitive diagnostic; never alias two conflicting LG models or manufacturer families automatically.
- **No/invalid primary or claim verification:** publication validation blocks `ACTIVE`; preserve `review` or roll back as transaction boundaries dictate.
- **Wrong-manufacturer product link or incomplete cashback graph:** PR 19 persisted validation blocks publication, with no partial `active` state.
- **Duplicate replay:** compare all relevant data and return existing record unchanged; no duplicate identities, sources, variants or rewards.
- **Concurrent or partial write:** retain existing unique constraints/transaction behavior; roll back and surface conflicts rather than overwrite; if publication succeeded but expiry failed, retry `ACTIVE → EXPIRED` safely.
- **Already expired:** no transition back to `ACTIVE`, source mutation or historical deletion.
- **Claim page unavailable:** does not fail offline tests or alter historical facts; report the claim URL as LG-designated historical destination, not a verified live form.
- **Unrepresentable eligibility conditions or time-of-day cutoff:** document precisely and avoid false certainty. Do not rewrite the public request or fixed window semantics in this PR.

---

## Acceptance criteria

### Behaviour

- [ ] Exactly **one** bounded real LG G5 reference promotion exists in version-controlled test fixtures, for UK model **`OLED55G54LW.AEK`**, **LG.com/UK**, qualifying purchases **21 May–24 June 2025** and **GBP 150.00** cashback.
- [ ] Fixed inclusive claim dates **21 May–19 August 2025** are persisted. No erroneous claim-opening delay of 30 days is introduced; LG's 30 days is correctly described as **validation delay**.
- [ ] Official LG terms and the officially designated claim URL are traceable through the manifest, clause map and persisted primary/claim provenance; claim portal accessibility is not falsely asserted.
- [ ] The reviewed graph passes the authoritative PR 19 persisted publication gate; missing/unverified evidence or invalid manufacturer/product association cannot activate it.
- [ ] Published historical promotion is `expired` as of 9 October 2026, preserved and queryable; injected historical dates can still produce computed `ELIGIBLE`, followed by `EXPIRED` after claim closure.
- [ ] Every expected case in the regression matrix passes through the canonical purchase-check service, with fixed date boundaries, precise GBP reward, sources, requirements, stable explanations and correct no-match behavior.
- [ ] Out-of-reference models are not mislabeled as ineligible for LG's **full** campaign; missing identity, unknown condition and unmodelled claimant checks are not silently assumed passed.

### Data and consistency

- [ ] No schema migration; all rows satisfy existing PostgreSQL uniqueness, references and publication constraints.
- [ ] Existing unambiguous LG/product/retailer aliases are reused. Identity conflicts and incorrect suffix normalization are rejected.
- [ ] Construction and replay are idempotent and atomic; failed creation/publication causes no invalid published or partial graph.
- [ ] Expiring the reference preserves original reward, evidence/URLs, timestamps, requirements and queryable historical state.

### Security

- [ ] Fixtures contain no real consumer receipts, bank information, serial numbers or other PII.
- [ ] No live vendor calls in normal tests, runtime checks or startup, and no new production admin/write route or automatic seed.
- [ ] No validation bypass, unsafe manifest deserialization, hallucinated checks or claim-approval guarantees.

### Operations

- [ ] Existing logging/health/API errors remain unchanged; failures are diagnostically explicit without leaking sensitive data.
- [ ] Test execution is deterministic with frozen evaluation dates and isolated PostgreSQL fixtures.

### Code quality

- [ ] Focused PR with clear LG-vs-Samsung fixture separation and no generic ingestion framework or unrelated refactors.
- [ ] No new external API or MCP contracts. Existing response schemas and source/reward ordering stay backward compatible.
- [ ] Formatter, lint, targeted, PostgreSQL integration and overall backend tests pass; unrun checks are recorded as such.

---

## Tests to add or update

### Unit tests

`backend/tests/unit/test_lg_reference_promotion.py`:

1. Assert exact reviewed values, model suffix, `LG.com/UK`, fixed claim window, £150 decimal-string amount, URLs, clause anchors and bounded scope.
2. Reject malformed purchase/claim dates, reversed windows, wrong model/retailer, changed fixed amount, floats instead of decimal-string money, unsupported benefit type, missing primary URL/evidence, unsafe URL schemes, unapproved extra properties and changed reviewed manifest hash/content.
3. Verify `FixedClaimWindow` inclusivity: **20 May** not yet open, **21 May** open, **19 August** open, **20 August** expired. Assert `opens_on`/`deadline_on` values exactly.
4. Verify that **30 calendar days** is metadata/instructions for **LG processing/validation** and does not alter eligibility's fixed claim opening. Avoid encoding a fake delayed window in the domain.
5. Domain-only `PurchaseConditionRule({PurchaseCondition.NEW})`: `REFURBISHED` → `NOT_ELIGIBLE` + `condition_mismatch`; unknown → `POTENTIALLY_ELIGIBLE` + `condition_unknown`. Explicitly separate this from what the persisted v1 purchase route enforces.
6. Preserve deterministic serialization and semantic fixture pin behavior, independent of JSON key order/whitespace or system clock.

### PostgreSQL integration tests

`backend/tests/integration/test_lg_reference_promotion.py`:

1. Build the actual ORM graph in `review` using canonical identity resolver, PR 19 candidate preflight and primary/claim source provenance. Call the **existing** lifecycle service for `review → active → expired` and assert persisted fixed dates, reward and source fields.
2. Run the actual `purchase_check_snapshot` + `check_purchase` path against migrated PostgreSQL for **all cases** in the matrix. Assert classification, reason ordering, `no_match_reason`, fixed claim window dates, exact £150 benefit independent of purchase-price input, requirements, full model identity and sources.
3. Seed a clearly synthetic **known excluded retailer** and **known unlinked test model** separately from real campaign facts; assert candidate-filtered no match rather than `NOT_ELIGIBLE`. Assert unknown model/retailer results have existing unresolved-identity semantics.
4. Confirm an expired lifecycle record can produce computed `ELIGIBLE` for a 2025 date while the fixed claim period was open, but `EXPIRED` on 20 August 2025 and on 9 October 2026.
5. Assert valid publication requires primary/claim verified sources and valid product manufacturer; missing verification/bad association is rejected with current structured validation issues, without active publication.
6. Test repeat graph construction and `finish_reference` from `review`, `active`, `expired`; compare persisted graph fingerprints and row counts for idempotency, provenance preservation and no unexpected updates.
7. Test transaction rollback on simulated constructor/preflight failure; conflict with a pre-existing same-slug promotion; ambiguous or mismatched existing identity; and cleanup that does not remove reused shared rows.
8. Confirm the read path is reproducible/read-only and makes no LG HTTP calls. Do not mock the PostgreSQL repository in the critical end-to-end tests.

### API/application tests

In `backend/tests/integration/test_lg_reference_promotion.py` or a focused existing API test:

- Call the **existing** `POST /api/v1/eligibility/check` using the real persisted reference, with `uk_evaluation_date` overridden to **2025-08-19** and request for purchase **2025-06-24**; assert HTTP 200 JSON, `promotion_status="expired"`, computed `eligibility.classification="ELIGIBLE"`, `cashback_reward_gbp="150.00"`, claim end date, source links and requirement fields.
- Re-evaluate at **2025-08-20** → computed `EXPIRED`, and submit a known excluded retailer or out-of-purchase-range purchase → empty promotions/`no_matching_published_promotions`. Do not add a special LG HTTP route or alter API request schema.
- Preserve existing status/error/validation cases unchanged. Do not assert time-of-day enforcement absent from date-only API.

### MCP contract tests

**N/A.** No MCP adapter or tool contract is created or changed.

### External-boundary tests

**N/A for new external calls.** Fixtures/tests never reach the LG terms or claim site. Where practical, test that a network client is not invoked by runtime purchase checking; don't interfere with Testcontainers' Docker infrastructure traffic.

---

## Verification commands

Run from `backend/` using the established `uv` and Ruff setup (Docker required for migrated PostgreSQL Testcontainers):

```bash
uv sync --locked --extra dev
uv run ruff format --check .
uv run ruff check .
uv run pytest tests/unit/test_lg_reference_promotion.py
uv run pytest tests/integration/test_lg_reference_promotion.py
uv run pytest tests/unit/test_samsung_reference_promotion.py tests/integration/test_samsung_reference_promotion.py
uv run pytest tests/integration/test_check_purchase.py tests/integration/test_promotion_publication.py
uv run pytest tests/integration/test_eligibility_api.py
uv run pytest
```

Focused LG test paths above are **expected new implementation outputs**, not commands that can pass before implementation. No type-check command is configured in the inspected `backend/pyproject.toml`; do not invent one. No Alembic migration verification is required because the schema is unchanged. If a command cannot run, report the command, reason, alternative evidence and remaining risk. Do not weaken failing assertions or silently skip PostgreSQL coverage.

---

## Completion report

### Changed

Summarise the LG reviewed manifest, bounded G5 SKU/retailer coverage, persisted reference graph construction, source evidence and fixed-window regression tests.

### Database and migrations

Report reference data/graph state in the test database, including `expired` lifecycle and preserved provenance. **No schema migration** unless an explicitly justified deviation was necessary.

### API/MCP contracts

**None.** The existing HTTP endpoint is only exercised by tests; no contract change is expected.

### Tests and verification

Name new/modified test files; list each exact command run and result, distinguishing pure unit vs real Testcontainers/PostgreSQL and API checks. Do not claim unrun tests passed.

### External configuration

**None.** No live LG credentials or operator data-loading step required. Do not claim the reference was deployed or made live.

### Deviations

Record any changes to official evidence, chosen exact model string, retailer alias, source availability, or established helper patterns and why they were required. Do not silently alter campaign facts.

### Remaining risks or follow-up

Record that this reference covers only `OLED55G54LW.AEK`/LG.com/UK, that LG's approval/age/condition/returns/GBP account/bulk restrictions are not all representable by the v1 purchase input, that `23:59 GMT` cannot be checked by the current date-only domain, and that the historical `lgcashback.com/g5` claim portal has not been independently confirmed live. A wider G5 catalogue or richer claimant/claim-time rules belongs in separate reviewed PRs.
