# PR 20 — Samsung Reference Promotion

## Repository state

**Expected branch:**  
`pr20-samsung-reference-promotion`

**Base branch:**  
`main`

**Dependencies:**

- PR 3–7: promotion graph, lifecycle, source provenance, canonical manufacturer/product/retailer identity.
- PR 9–15: published candidate matching, eligibility classification, relative claim windows, requirements and cashback reward calculation.
- PR 17–18: canonical `check_purchase` operation and read-only HTTP API.
- PR 19: strict candidate format and authoritative publication validation.
- PostgreSQL/Testcontainers and existing SQLAlchemy, Alembic, `uv`, pytest and Ruff tooling.
- **Number verification (9 October 2026):** PR #19, *Validate candidate promotions before publication*, is merged into `main`; there is no `pr20` branch in the repository at the time of review. Recheck before opening the implementation PR.

### Read first

- `AGENTS.md` and any narrower guidance introduced before implementation.
- `.codex/tasks/TEMPLATE.md`, `.codex/tasks/pr-6-promotion-source-provenance.md`, `.codex/tasks/pr-7-product-retailer-normalisation.md`.
- `.codex/tasks/pr-9-promotion-candidate-matching.md`, `.codex/tasks/pr-13-relative-delayed-claim-windows.md`, `.codex/tasks/pr-15-reward-calculation.md`.
- `.codex/tasks/pr-17-check-purchase-eligibility-service.md`, `.codex/tasks/pr-18-eligibility-http-api.md`, `.codex/tasks/pr-19-promotion-authoring-validation-format.md`.
- `backend/README.md`; relevant implementation/tests named below.

### Primary change area

**Evidence-backed reference promotion data, opt-in loading/publication and a complete PostgreSQL purchase-check regression.** This is a small curated reference case, **not** a general manufacturer-ingestion feature.

### Canonical implementation examples

- `backend/app/application/promotion_authoring.py` — `CandidatePromotionV1`, `parse_candidate_promotion`, `validate_candidate_promotion`.
- `backend/app/domain/promotion_validation.py` — publication completeness rules.
- `backend/app/application/promotions.py` — `change_promotion_status`, transactional lifecycle transitions.
- `backend/app/db/repositories/promotions.py` — `SqlAlchemyPromotionRepository`, `promotion_transaction`, `purchase_check_snapshot`.
- `backend/app/db/models/core.py`, `backend/app/db/models/identity.py` — existing ORM tables and identity records.
- `backend/app/application/purchase_check.py`, `backend/app/domain/claim_windows.py` — canonical eligibility and inclusive relative windows.
- `backend/tests/integration/test_check_purchase.py`, `test_promotion_publication.py`, `test_eligibility_api.py` — database and transport fixtures.

### Relevant symbols

```text
CandidatePromotionV1, parse_candidate_promotion, validate_candidate_promotion
PromotionValidationSnapshot, validate_promotion_for_publication
PromotionStatus, change_promotion_status, promotion_transaction
Manufacturer, Product, Retailer, Promotion, PromotionVariant, PromotionVariantProduct
Benefit, BenefitReward, Requirement, Source, PromotionSource
SourceRole, SourceType, PromotionSourceRecord, PublishedProvenance
CheckPurchaseRequest, check_purchase, purchase_check_snapshot
RelativeClaimWindow, EligibilityClassification, EligibilityReasonCode
NoMatchReason.NO_MATCHING_PUBLISHED_PROMOTIONS
```

### Expected change surface

```text
backend/tests/fixtures/promotions/samsung-summer-wallet-cashback-2026.json  # NEW: reviewed, machine-readable reference facts
backend/tests/fixtures/promotions/README.md                                 # NEW or focused existing docs: evidence mapping and bounded coverage
backend/tests/integration/test_samsung_reference_promotion.py                # NEW: persisted real-promotion end-to-end checks
backend/tests/unit/test_samsung_reference_promotion.py                       # NEW if pure fixture/validation tests warrant a separate file
backend/scripts/load_samsung_reference_promotion.py                          # NEW, only if an opt-in loader is implemented
backend/README.md                                                            # narrow local reference-data instructions
```

Use the existing ORM and lifecycle service. Put reusable fixture construction in a narrowly scoped test helper if needed. No new migration is expected. Codex may adjust paths after inspecting repository conventions, but must explain deviations.

### Excluded areas

- No production auto-seeding, startup DB writes, autonomous scraping, live claim submission, source crawling, LLM/AI extraction, background jobs, admin editor or general-purpose data importer.
- No new or changed public request/response schema, MCP tool, frontend, authentication, payment or claim-processing behaviour.
- No new generic rule DSL or unsupported purchase-condition, participant-age, company/household-cap, SIM-status, marketplace-seller or country field silently inferred from free text.
- No change to the existing five-field purchase request; no code path that bypasses publication validation to make the fixture `active`.
- Do not represent the *entire* Samsung campaign as exhaustively catalogued. This PR explicitly covers one SKU and one confirmed retailer.

### Unknowns Codex must verify

1. Whether the PR 19 candidate JSON parser is a read/validate contract only (currently yes), with no public candidate graph writer. Do not assume a candidate document is automatically persisted.
2. Whether the canonical Samsung, Buds4 Pro, and Samsung.com rows already exist; reuse unambiguous identities and aliases rather than duplicate them.
3. Exact identity-model and retailer-SKU association conventions for `SM-R640`.
4. Whether source roles are constrained to exactly one verified `primary` and one verified `claim` (currently yes) and duplicate source links are rejected.
5. The lifecycle supports `review → active → expired`; already `expired` historical publications participate in purchase matching.
6. Existing candidate filtering removes outside-purchase-date, wrong-retailer and wrong-SKU rows *before* detailed rule classification; such cases produce **no matching promotion**, not `NOT_ELIGIBLE`.
7. The current purchase input cannot attest to new/unused condition, claimant age, territory, account status, prior claims, household limits or third-party seller status. Requirements text is not an executable eligibility rule.
8. Current backend verification commands and target tests still exist when implementation begins.

---

## Objective

Add a **reproducible, source-backed Samsung promotion reference** that can be constructed from reviewed local data, pass the existing publication gate, be evaluated through the actual database-backed `check_purchase` flow, and demonstrate real £50 cashback, inclusive purchase-date boundaries and the correct 30-day claim deadline.

Use the real **Samsung Summer Wallet Cashback Promotion (UK), 3–23 June 2026**, but restrict the reference graph to the verified **Samsung Galaxy Buds4 Pro (`SM-R640`) purchased directly from Samsung.com**. The full campaign included other Samsung products/retailers; do not call this restricted seed a complete catalogue. Preserve official terms, evidence references and explicit limitations. As of 9 October 2026 the offer is historical, so a voluntarily loaded instance must finish in lifecycle status `expired`, not appear as currently active.

Success requires deterministic eligible, excluded/no-match, expired and boundary-date checks with **no live network calls**. A successful reference test is evidence that the engine processes these published facts correctly, **not** a claim that every Samsung participation restriction can be evaluated from the existing public request.

---

## Architecture and invariants

```text
Official Samsung PDF / newsroom (human-reviewed evidence)
  -> local curated facts + evidence map (version controlled)
  -> controlled reference-data/graph constructor (test fixture; optional explicit loader)
  -> persisted review graph -> existing publication-validation gate
  -> active -> expired (historical campaign)
  -> PostgreSQL repeatable-read snapshot -> check_purchase -> unchanged API mapper
```

- Keep real promotion data **separate from** fake identities used solely for negative tests.
- Published graph must contain **exactly one** reference promotion and a single bounded variant, product, verified retailer, fixed GBP cashback benefit and required source links. Avoid claiming all variants or retailers are represented.
- The official **purchase period** is different from the **per-purchase claim window**. Do not substitute a single fixed 22 July deadline for all purchase dates.
- Use relative window **`start_offset_days = 0` and `end_offset_days = 29`**, inclusive. Samsung states claims are due within 30 days of purchase and expressly identifies **22 July 2026** as the final deadline for a **23 June** purchase. Counting the purchase date as day 1 makes day 30 exactly `purchase_date + 29 days`.
- Real published evidence must be linked to a source role, URL and truthful UTC-aware retrieved/verified timestamps. A note in a fixture is not by itself persisted provenance.
- Retain full source/reference records when promotion lifecycle becomes `expired`; never delete historical data to simulate expiry.
- Test the **existing** application path. Never hard-code an alternative Samsung eligibility branch or mock the domain/database under the main PostgreSQL regression.
- The phrase `ELIGIBLE` means **all currently configured rules match and the claim window is open**, not manufacturer approval of a submitted claim. Unmodelled official conditions must be exposed as known limitations, never asserted as satisfied.

---

## API and contract changes

**None** to REST, MCP or `CheckPurchaseRequest`. The existing read-only `POST /api/v1/eligibility/check` remains the sole HTTP check path and must call `check_purchase`.

The reviewed **local reference manifest** must be human-readable JSON with bounded, versioned keys documenting, at minimum:

```json
{
  "reference_version": 1,
  "campaign": "Samsung Summer Wallet Cashback Promotion 2026 (UK)",
  "promotion_slug": "samsung-summer-wallet-cashback-2026-buds4-pro-samsung-com-reference",
  "coverage": "Samsung Galaxy Buds4 Pro SM-R640 purchased at Samsung.com only; not the full campaign",
  "manufacturer": "Samsung",
  "product": { "name": "Galaxy Buds4 Pro", "model_or_sku": "SM-R640" },
  "retailer": "Samsung.com",
  "purchase_start_date": "2026-06-03",
  "purchase_end_date": "2026-06-23",
  "claim_window": {
    "type": "relative",
    "start_offset_days": 0,
    "end_offset_days": 29
  },
  "benefit": { "type": "cashback", "reward": { "type": "fixed_amount", "amount_gbp": "50.00" } },
  "official_terms_url": "https://api.my-samsung.com/UploadImages/terms/TermsConditionsLegal_91665.pdf",
  "samsung_newsroom_url": "https://news.samsung.com/uk/samsung-electronics-uk-launches-summer-cashback-promotion-offering-up-to-300-cashback-on-selected-galaxy-devices",
  "claim_url": "https://samsungoffers.claims/walletcashback2026"
}
```

This is a **reference-data manifest**, *not* an alternative persisted candidate schema. When implementing loader/fixture construction, resolve canonical database UUIDs first and use PR 19's `CandidatePromotionV1` as the candidate-validation contract where appropriate. Do not modify PR 19's schema to accept free-text identities. Additional manifest keys may record source clauses, evidence-check status and explicit limitations. Do not commit generated UUIDs as authoritative reference identities.

The optional loader is an **operator-invoked internal tool only**. It accepts an explicit database target via existing configuration, offers a no-write inspection/dry-run mode, and must never be wired to API startup or migrations. Its CLI flags are implementation details, not public API.

---

## Domain and application behaviour

### 1. Confirmed historical campaign facts

| Fact | Approved value | Official evidence |
|---|---|---|
| Campaign | Samsung Summer Wallet Cashback Promotion 2026 (UK) | PDF p. 1 heading |
| Promoter | Samsung Electronics (UK) Limited | PDF p. 1, clause 1 |
| Purchase starts | 2026-06-03 | PDF p. 1, clause 2 |
| Purchase ends | 2026-06-23 | PDF p. 1, clause 2 |
| Included model/SKU | Galaxy Buds4 Pro / `SM-R640` | PDF p. 2, Table 1 |
| Benefit | Cashback **GBP 50.00** | PDF p. 2, Table 1 |
| Participating retailer in this reference | Samsung.com | PDF p. 3, Table 2 |
| Product condition | New; not second-hand, refurbished or ex-display | PDF pp. 1–2, clause 7 |
| Claim instructions | Proof of purchase and other specified details; serial number or IMEI where requested | PDF p. 4, clause 11 |
| Relative claim deadline | Within 30 days, **purchase day included**; inclusive | PDF p. 4, clause 12 |
| Absolute end of the last purchase's claim period | 2026-07-22 at 23:59 BST | PDF p. 4, clause 12 |
| Claim URL | `https://samsungoffers.claims/walletcashback2026` | PDF pp. 1 and 4 |
| Participant restrictions | Territory, age/company, resellers, other Samsung claims, per-household/company caps | PDF pp. 1, 4, clauses 3–6 and 13 |

Official sources:

1. **Authoritative Samsung terms PDF:** <https://api.my-samsung.com/UploadImages/terms/TermsConditionsLegal_91665.pdf> (6 pages, UK promotion terms).
2. **Corroborating Samsung Newsroom post (15 June 2026):** <https://news.samsung.com/uk/samsung-electronics-uk-launches-summer-cashback-promotion-offering-up-to-300-cashback-on-selected-galaxy-devices> (lists Galaxy Buds4 Pro cashback as £50 and campaign dates).
3. **Samsung-designated claim destination:** <https://samsungoffers.claims/walletcashback2026>. The claim URL is evidenced by the official terms; it may be closed or block automated access in October 2026. **Do not assert current claim-page accessibility.**

As-of evidence review: **9 October 2026**. During implementation, recheck the official documents for amendments or corrections. Keep the observed verification timestamps accurate; never fabricate a retrieval time or a successful HTTP visit. If an official document cannot be checked, do not promote unverified revised facts.

### 2. Product, retailer, benefit and requirements

- Use manufacturer `Samsung`, a canonical product resolved by `SM-R640`, and only a **Samsung.com**-scoped variant (`retailer_id` is non-null). The official Table 2 permits more retailers, but they are intentionally out of this PR's reference scope. **Never** use `retailer_id = null` for this restricted variant.
- Link only this product to this reference variant. A differently named Buds model or a different SKU must not be accidentally resolved to `SM-R640`.
- Add one `cashback` benefit with `FixedAmountReward(Decimal("50.00"))`; do not use an unspecified amount or guess reward from promotional prose.
- Add `receipt` requirement with proof-of-purchase instructions; add `serial_number` as an **as-requested** requirement, not a claim that all devices necessarily need one. Samsung account / wallet steps and participant restrictions belong in verified instructions/limitations if not otherwise representable.
- Avoid making the full-campaign original title imply exhaustive support; store the reference's bounded scope in the name, description or documented metadata available to maintainers. The original campaign name and official reference remain discoverable.
- Do not infer eligibility from claimant age, residency, product condition, seller identity, prior claim or account registration: the existing five-field API cannot evaluate those. Preserve their source-backed limitations; do **not** mislabel them as passed deterministic rules. Do not silently present the offer as unconditional cashback in consumer copy.

### 3. Publication and lifecycle

- Construct the persisted graph in `review`, following existing canonical identity and source handling.
- Assign the actual verified PDF to `primary`, verified claim destination to `claim`, and Newsroom to `supporting` (and the same or another evidence resource to `terms` only if identity/link constraints permit). Source objects may not be duplicated in `promotion_sources` with different roles if that violates existing uniqueness; do not work around the validator.
- Publication must run `change_promotion_status(..., ACTIVE)` with the established PR 19 persisted-graph validation, never direct SQL that sets `status='active'`.
- Because the claim deadline has passed, transition the verified published record to `EXPIRED` through the existing lifecycle operation before offering it as completed loaded reference data.
- A fixture can construct the same graph in an isolated Testcontainer and then test its historical behaviour. **Never seed this reference on app startup or deploy it to production automatically.**
- If a mid-process failure occurs, a retry must recognise the stable campaign slug and existing graph, reconcile verified state, and finish at `expired` (or fail with a clearly reported incomplete state). Do not leave duplicate graph rows or silently mutate already published evidence.
- If existing rows with the same canonical identity/slug materially disagree with reviewed facts, fail safely and report the conflict; no destructive replacement of live/historical records.

### 4. Precise expected eligibility semantics

Use `CheckPurchaseRequest(brand="Samsung", model="SM-R640", retailer="Samsung.com", purchase_date=<date>)` with an injected `evaluation_date` and the real PostgreSQL snapshot. The result must contain one matching reference promotion for in-scope inputs; historical `PromotionStatus.EXPIRED` does **not** itself force the computed claim classification to `EXPIRED`.

| Purchase date | Evaluation date | Expected result | Check |
|---|---|---|---|
| 2026-06-03 | 2026-06-03 | `ELIGIBLE` | First purchase day; claim opens same day; £50 |
| 2026-06-03 | 2026-07-02 | `ELIGIBLE` | Inclusive **day 30**; deadline 2 July |
| 2026-06-03 | 2026-07-03 | `EXPIRED` | First day after day-30 deadline |
| 2026-06-23 | 2026-06-23 | `ELIGIBLE` | Last purchase day included |
| 2026-06-23 | 2026-07-22 | `ELIGIBLE` | Final campaign claim deadline included |
| 2026-06-23 | 2026-07-23 | `EXPIRED` | First day after final claim deadline |
| 2026-06-23 | 2026-10-09 | `EXPIRED` | Historical query remains available |
| 2026-06-02 | 2026-06-03 | **No matching published promotion** | Outside purchase window (one day early) |
| 2026-06-24 | 2026-06-24 | **No matching published promotion** | Outside purchase window (one day late) |
| 2026-06-15 | 2026-06-15 | **No matching published promotion** | Known excluded test retailer or known unlinked test SKU |

**Important existing behaviour:** For dates outside the promotion purchase period, wrong retailer and wrong SKU, `find_promotion_candidates` filters out the reference **before** detailed rule evaluation. Assert a resolved `CheckPurchaseResult` with empty `promotions` and `no_matching_published_promotions`, **not** `NOT_ELIGIBLE`. For unknown brand/model/retailer strings the existing response may be `unresolved_identity`; seed a separate *known* nonqualifying test identity for negative tests so this distinction is explicit. Do not change core matching solely to force a `NOT_ELIGIBLE` result.

For matched cases assert claim `opens_on`, `deadline_on`, the precise `Decimal("50.00")` benefit, source/claim links, requirements and stable reason codes: `all_configured_rules_satisfied` + `claim_window_open` or `claim_window_expired` as appropriate. Inject dates; never depend on system time.

---

## Persistence, transactions, and migrations

**No database migration or schema change expected.** Use existing `manufacturers`, `products`, `retailers`, `promotions`, `promotion_variants`, `promotion_variant_products`, `benefits`, `benefit_rewards`, `requirements`, `sources`, `promotion_sources` and identity/alias tables if already appropriate.

- Resolve existing canonical identities and normalised lookup keys before inserting. Add only genuinely missing entries; respect database uniqueness/foreign-key constraints and no cross-manufacturer product linking.
- Give the reference promotion a stable, distinct slug. A second identical load must not duplicate the promotion, product, retailer, variant, benefit, reward, requirements, sources or links.
- Perform reference-data/graph creation atomically. Separate lifecycle publication must respect the service's own commit/rollback boundaries. On retry detect whether the record is `review`, `active`, `expired` or conflicting; do not attempt `expired → active`.
- `Source.retrieved_at` and `Source.verified_at` must be real timezone-aware timestamps of reviewed evidence (verification after retrieval) and must describe **what** was reviewed; they are **not** the promotion purchase dates. An inaccessible historical claim page does not make the official PDF's documented destination imaginary, but record any access limitation in the evidence map.
- Preserve historical graph, published provenance, and sources across `active → expired`. Do not delete or rewrite historical rows.
- Verify PostgreSQL uniqueness, matching and read-path behaviour through Testcontainers; do not replace with SQLite or mocks.

---

## External services and network access

**No runtime or test network dependencies added.** Samsung sites are evidence references to be manually verified, not live test fixtures. The reviewed manifest and tests must be runnable offline, with fixed local facts.

A future separate source-ingestion PR may implement bounded, SSRF-safe source retrieval with timeouts, retries and snapshots. This PR must not add a network client, HTTP scraper or source-access-on-check behaviour. Normal test execution must never request the Samsung PDF or claim portal. Changes to an official campaign page must not make deterministic CI flaky.

---

## Security and privacy

- No consumer details or claim records are collected. Do not load real receipts, claimant emails, serial numbers, bank details, account credentials or PII into fixtures.
- Treat official-source text and the reference manifest as data, never executable rules or code. Validate manifest fields and source URLs with established types/constraints.
- No trusted network fetches, arbitrary file imports, user-controlled paths, write HTTP endpoints or new auth boundary.
- Optional loading into a non-test database must require an explicit operator action and must not default to a production connection. Do not create privileged bulk-update paths or production auto-seeding.
- Manufacturer submission and eligibility approval remain Samsung's decisions. Visible descriptions must not guarantee payout, waive unmodelled participation restrictions, or describe a historical promotion as currently claimable.

---

## Configuration and deployment

**No new environment variables, services, jobs, Docker/image behaviour or deployment changes.** Use existing `DATABASE_URL` only for an explicitly invoked local/staging loader; normal server startup is read-only with respect to reference data. Do not add a new deployment dependency or schedule.

---

## Observability and operations

- Reuse existing logging patterns. Any optional loader reports deterministic operation (`created`, `already_present`, `expired`, `conflict`, `failed`) and safe promotion identity/slug, not personal information.
- If verification or publication fails, report specific validation issue codes or safe persistence error category; never log raw DB URLs, credentials or stack traces in consumer output.
- No new telemetry stack, dashboards, health endpoints or background monitors.

---

## Failure, consistency, and recovery

- **Missing/ambiguous canonical identity:** fail or require explicit curation; never invent a best-guess match.
- **Invalid/contradictory source evidence:** leave unpublished; report mismatch and preserve any review draft for correction.
- **Publication validation rejection:** no `active` state and no silent bypass; reuse `PromotionPublicationError` diagnostics.
- **Duplicate load:** no new rows, no reward duplication, no provenance loss.
- **Partial load/DB exception:** rollback graph transaction; test retries and transaction boundaries.
- **Failure between active and expired transitions:** report an incomplete historical-load state and safely reconcile on retry; an `active` historical promotion must not be described as a current claimable offer.
- **Official claim site closed/unavailable:** no CI impact and no false reachability statement. Retain official claim URL as historical evidence.
- **Ambiguous/out-of-scope purchase:** no false definite `NOT_ELIGIBLE` or guaranteed `ELIGIBLE`; preserve existing unresolved/no-match semantics and explicit unmodelled restrictions.

---

## Acceptance criteria

### Behaviour

- [ ] The repository contains **one real, bounded Samsung reference promotion** matching the official 2026 campaign, its `SM-R640` SKU, Samsung.com retailer, exact £50 cashback and evidenced dates.
- [ ] `start_offset_days=0`, `end_offset_days=29` correctly interpret Samsung's 30-day deadline including the purchase day.
- [ ] Source manifest records primary Samsung terms, corroborating Samsung Newsroom, claim URL, reviewed clauses and source-check date; persisted graph exposes verified primary/claim provenance.
- [ ] Existing PR 19 publication validation approves the complete persisted graph; intentionally missing or altered verified evidence blocks publication.
- [ ] Published historical reference is retained as `expired`; historical purchases still evaluate through existing candidate, rule, reward and claim-window code.
- [ ] All eligible, excluded/no-match, expired and exact boundary-date cases in the table above pass with a fixed evaluation date; separate domain-only coverage explicitly demonstrates `NOT_ELIGIBLE` for a refurbished product without claiming that v1 HTTP checks this field.
- [ ] Consumer-facing/maintainer documentation states that the reference is a **subset**, not all campaign products/retailers, and that participant/condition constraints cannot all be proven from v1 input.

### Data and consistency

- [ ] No new schema or migrations; all records comply with current PostgreSQL constraints.
- [ ] Loader/replay is idempotent; conflicting existing records reject safely and have no unexpected side effects.
- [ ] Source, claim link, cashback and historical graph survive expiration.
- [ ] No startup auto-seed or production publication side effect.

### Security

- [ ] No private consumer data, claim submissions or sensitive user evidence in test fixtures, output or logs.
- [ ] No live remote calls required to run CI.
- [ ] No validation/publication shortcuts, arbitrary SQL injection or inferred unsupported conditions.

### Operations

- [ ] Optional loader provides dry-run and clear safe success/conflict/retry diagnostics.
- [ ] Existing health and API error responses stay unchanged.

### Code quality

- [ ] Focused PR: no generic ingestion framework, unnecessary dependency, transport rewrite or unrelated refactor.
- [ ] Ruff and relevant unit, integration and full backend tests pass; no unrun check is reported as passed.

---

## Tests to add or update

### Unit tests

`backend/tests/unit/test_samsung_reference_promotion.py` (or a coherent nearby test):

- Parse/validate reference facts (correct date strings, SKU, fixed amount as exact decimal-string, source URLs, scope) with no wall-clock dependency.
- Assert day-count conversion: 3 June → 2 July, 23 June → 22 July; `+1` day is expired. Check opening and ending inclusivity.
- Reject malformed dates, wrong benefit type/value, missing evidence and unexpected changes to the curated manifest rather than silently repairing them.
- **Explicit ineligible classification test:** using Samsung's official **new-only** condition as a *direct domain-level* `PurchaseConditionRule({PurchaseCondition.NEW})`, evaluate a `REFURBISHED` product as `NOT_ELIGIBLE` (`condition_mismatch`) and a missing condition as `POTENTIALLY_ELIGIBLE` (`condition_unknown`). This verifies existing pure domain semantics only; it **must not** imply that the v1 persisted promotion or public `check_purchase` already enforces condition.
- Do not fake `NOT_ELIGIBLE` from an out-of-window candidate-filtered purchase.

### PostgreSQL integration tests

`backend/tests/integration/test_samsung_reference_promotion.py`:

1. Construct one real promotion graph and canonical identities through established SQLAlchemy boundary, status `review`; verify a valid PR 19 publication attempt and transition to `expired`.
2. Run **actual** `purchase_check_snapshot` + `check_purchase` against the migrated Testcontainer for every scenario in the table. Assert classification, no-match reason, correct £50 reward, exact claim boundaries, explanations, requirements and source/claim URL fields.
3. Use a separate persisted **known** excluded retailer and known non-promoted test product for the negative paths; preserve `no_match` vs `unresolved_identity` semantics.
4. Test duplicate load/run (including safe retry after already expired), uniqueness and no altered provenance/history.
5. Test rejection when primary/claim verification is missing or a product link points at another manufacturer; assert no invalid `active` publication.
6. Demonstrate that historical `expired` status still yields an `ELIGIBLE` classification for an **explicit historical evaluation date inside the claim window**, but `EXPIRED` when the evaluation date is after the deadline.
7. Check no additional runtime HTTP request/LLM call is introduced; do not mock DB behaviour under the critical integration path.

### API/application tests

If the fixture is reachable through existing test app setup without introducing a second seed mechanism, add an end-to-end assertion through `POST /api/v1/eligibility/check` for at least one matching purchase using injected/frozen evaluation date and one no-match case. Preserve current response discriminators and `application/json`/problem-details semantics. Do not add a special Samsung route or change API output to satisfy the fixture.

### MCP contract tests

**N/A** — no MCP adapter is present/changed by this PR.

### External-boundary tests

**N/A** — no external network boundary is added. Verify by test design that the official URLs are treated as stored evidence, not fetched during runtime checks or CI.

---

## Verification commands

From `backend/` using existing repository commands:

```bash
uv sync --locked --extra dev
uv run ruff format --check .
uv run ruff check .
uv run pytest tests/unit/test_samsung_reference_promotion.py
uv run pytest tests/integration/test_samsung_reference_promotion.py
uv run pytest tests/integration/test_check_purchase.py tests/integration/test_promotion_publication.py
uv run pytest tests/integration/test_eligibility_api.py
uv run pytest
```

New focused test files are expected **implementation outputs**, not present before the PR. Docker is required for PostgreSQL Testcontainers. There is no configured type-check command in the inspected `backend/pyproject.toml`; do not invent one. There is no migration check because no migration is expected. If a check cannot execute, report which command, why, substitute verification and remaining risk. Do not weaken tests for green CI.

---

## Completion report

### Changed

Summarise reference manifest/evidence, canonical identities, bounded product/retailer variant, reward/requirements, optional loading mechanism and lifecycle handling.

### Database and migrations

List inserted reference records and lifecycle status; say **No schema migration** unless an unexpected change is justified.

### API/MCP contracts

**None** unless scope explicitly changes and that deviation is approved.

### Tests and verification

List each new/updated test and the exact commands run with outcomes. Distinguish real PostgreSQL results from unit-only results.

### External configuration

**None**, except explicit operator action if a local/staging reference loader is provided. Never claim a production promotion has been loaded unless separately performed and verified.

### Deviations

Identify factual differences discovered in updated official terms, schema/identity gaps and any justifiable scope changes.

### Remaining risks or follow-up

Explicitly record that campaign coverage is one SKU/retailer, that some Samsung terms cannot yet be checked from v1 inputs, that the claim portal is a historical URL and may no longer accept submissions, and that future broader campaign coverage is a separate reviewed-data change. Do not overstate customer eligibility or live availability.
