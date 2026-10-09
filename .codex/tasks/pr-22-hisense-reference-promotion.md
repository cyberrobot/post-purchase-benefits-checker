# PR 22 — Hisense Reference Promotion

## Repository state

**Expected branch:**  
`pr22-hisense-reference-promotion`

**Base branch:**  
`main` (after merged PR #21; verify the current head before starting)

**Dependencies:**  
PR #3–#15 (promotion schema, lifecycle, benefits, provenance, normalisation, eligibility, claim windows, requirements and rewards); PR #17 (`check_purchase`); PR #18 (eligibility HTTP API); PR #19 (candidate authoring/publication validation); PR #20 (Samsung reference); PR #21 (LG reference). Python 3.13, SQLAlchemy, Alembic, PostgreSQL/Testcontainers, `uv`, pytest, Ruff.

### Read first

- `AGENTS.md` and any newly introduced scoped `AGENTS.md`.
- `.codex/tasks/TEMPLATE.md`, `.codex/tasks/pr-20-samsung-reference-promotion.md`, `.codex/tasks/pr-21-lg-reference-promotion.md`.
- `backend/README.md` and `backend/tests/fixtures/promotions/README.md`.
- The published-authority boundary and existing comparable test-only constructors; the present codebase, not this spec, determines names and call signatures.

### Primary change area

**Promotion reference data, validation/publication, and deterministic eligibility regression tests.** This is a *single verified reference*, **not** a general Hisense scraper or a whole-campaign importer.

### Canonical implementation examples

- `backend/tests/fixtures/promotions/samsung-summer-wallet-cashback-2026.json`
- `backend/tests/fixtures/promotions/lg-g5-cashback-2025.json`
- `backend/tests/samsung_reference.py`, `backend/tests/lg_reference.py`
- `backend/tests/unit/test_lg_reference_promotion.py`
- `backend/tests/integration/test_lg_reference_promotion.py`
- `backend/tests/integration/test_samsung_reference_promotion.py`
- `backend/app/application/purchase_check.py`, `backend/app/application/promotion_authoring.py`, `backend/app/application/promotions.py`
- `backend/app/domain/claim_windows.py`, `backend/app/domain/eligibility_result.py`, `backend/app/domain/eligibility_rules.py`
- `backend/tests/integration/test_promotion_publication.py`, `backend/tests/integration/test_eligibility_api.py`

### Relevant symbols

- `CheckPurchaseRequest`, `check_purchase`, `purchase_check_snapshot`, `IdentityResolver`, `SqlAlchemyIdentityRepository`.
- `parse_candidate_promotion`, `validate_candidate_promotion`, `change_promotion_status`.
- `FixedClaimWindow`, `evaluate_fixed_claim_window`, `PurchaseConditionRule`, `PurchaseCondition`, `PromotionStatus`.
- `Manufacturer`, `Product`, `Retailer`, `Promotion`, `PromotionVariant`, `PromotionVariantProduct`, `Benefit`, `BenefitReward`, `Requirement`, `Source`, `PromotionSource`.
- `POST /api/v1/eligibility/check` and its existing `uk_evaluation_date` test override; verify the latest code before using.

### Expected change surface

1. **New:** `.codex/tasks/pr-22-hisense-reference-promotion.md` (this specification).
2. **New:** `backend/tests/fixtures/promotions/hisense-autumn-cashback-2026-wf7i1248bbr.json`.
3. **New:** `backend/tests/hisense_reference.py` (offline, test-only reviewed-reference constructor; no production import).
4. **New:** `backend/tests/unit/test_hisense_reference_promotion.py`.
5. **New:** `backend/tests/integration/test_hisense_reference_promotion.py`.
6. **Update:** `backend/tests/fixtures/promotions/README.md` with evidence ledger and limitations.
7. **Update only if useful:** `backend/README.md` with concise reference/testing documentation.

If a reusable test helper is warranted to remove repeated Samsung/LG mechanics, explain its benefit and keep the refactor small; do not expand the task into a generic import pipeline.

### Excluded areas

- No production seeding, startup/CI import, public promotion-write API, browser automation, manufacturer-account login, crawling, LLM extraction or scheduling.
- No database schema migration, new benefit/requirement enums, eligibility algorithm rewrite or public request/response changes.
- Do not edit Samsung/LG reviewed fixtures or silently publish other Hisense products, retailers or offers.
- Do not auto-expire promotions from the read-only purchase-check path.

### Unknowns Codex must verify

1. **Critical evidence gate:** the **full, current official Autumn 2026 terms** including Annex 1 (participating retailers), Annex 2 (qualifying model and amount), exclusions, claim requirements and amended-term dates. The campaign's terms endpoint presented a bot/JavaScript verification challenge when inspected on **9 October 2026**; search snippets are **not** sufficient publication verification. **Do not activate authoritative data without a real review of the complete applicable terms, using an accessible official copy or official retailer-hosted complete terms.** If inaccessible, retain a clearly unverified `review` candidate and report the blocker; never manufacture provenance or make the CI fixture masquerade as published authority.
2. Confirm `Currys` is permitted for **this autumn campaign**, not merely earlier Hisense campaigns. A Currys product offer and indexed terms indicate participation, but do not replace the full Annex 1 verification. Verify whether any product/retailer restrictions override the global annex.
3. Confirm `WF7I1248BBR` is an exact listed model and **GBP 100.00** is the Autumn 2026 amount in authoritative Annex 2. **Do not import the GBP 150 reward from the *different* Hisense A-Rated Appliances promotion of May–June 2026.**
4. Confirm the campaign's **claim opening 27 November 2026** (not 27 October; one Currys snippet uses a conflicting early start), last claim date 24 December 2026 and the product's relevant **purchase** period 9 September–27 October 2026. Reconcile conflicts against authoritative full terms and official Hisense campaign page before pinning facts.
5. Confirm receipt, model, serial number, purchase evidence, claimant restrictions, returns/ex-display, retailer-owned-store and any household/duplicate claim limits directly from the official Autumn 2026 terms. Do **not** copy unrelated 2025/early-2026 terms as facts.
6. Check existing identity rows/aliases, candidate preflight limitations, verified-source-role requirements, lifecycle transitions, tests' `evaluation_date` injection, transaction ownership, and the precise serialization of benefit and provenance fields.

---

## Objective

Represent **one authentic, evidence-verified Hisense Autumn Cashback 2026 promotion** as an exact-model, exact-retailer UK reference for **Hisense `WF7I1248BBR` washing machine purchased directly from Currys**, eligible for **fixed GBP 100 cashback**, subject to final verification of the official Autumn 2026 terms. The example is deliberately one slice of a wider campaign.

After implementation, a reviewed fixture can be constructed deterministically in the isolated PostgreSQL test database, checked through the existing persisted publication gate, and queried through the real `check_purchase` and existing HTTP route. Regression tests must prove purchase eligibility boundaries, delayed **fixed-date** claim opening, inclusive deadline and eventual expiration, exact benefit amount, provenance, filtering, identity behaviour, rollback and safe replay.

**Release constraint:** This specification does not authorise shipping an unverified promotion as `active`. The source audit and validation gate in this document are mandatory exit conditions; fail closed if they cannot be met.

## Architecture and invariants

- Follow established separation: pure domain eligibility and claim dates → application `check_purchase` → existing SQLAlchemy/PostgreSQL snapshot → FastAPI adapter. No Hisense-specific branch in business logic.
- Offline human-reviewed source facts → strict, pinned versioned fixture → test-only ORM construction in `review` → PR #19 candidate preflight → **persisted** `change_promotion_status(..., ACTIVE)` publication validation. Candidate preflight by itself is not permission to publish.
- `active` and `expired` are **persisted lifecycle states**, whereas `CLAIM_NOT_YET_OPEN`, `ELIGIBLE` and `EXPIRED` are **calculated eligibility classifications at an injected date**. They are not interchangeable.
- Use a **fixed** claim window 2026-11-27 through 2026-12-24 inclusive, regardless of whether the customer purchased in September or October. **Do not model a relative 30-day-after-purchase claim window.**
- Tests must not access Hisense or Currys sites. Publication verification is performed during human evidence review and recorded truthfully; normal tests consume locally pinned observations.
- Current v1 purchase request has **brand, model, retailer, purchase date and optional price only**. Never claim the service checked customer identity, region, age, purchase condition, third-party marketplace seller, serial, proof submission, prior claims or payment details.
- Do not treat a match to the bounded reference as a guarantee of Hisense claim acceptance.

## API and contract changes

**None.** No new API/MCP endpoint, schema, public field, status code, config parameter or FastAPI transport logic. The existing `POST /api/v1/eligibility/check` returns results from the same application service as the integration tests. The constructor is test-only and not a public app interface.

## Domain and application behaviour

### 1. Campaign facts and evidence status as inspected 9 October 2026

| Field | Proposed exact value | Evidence and verification requirement |
| --- | --- | --- |
| Campaign | Hisense Autumn Cashback 2026 Promotion (UK) | Official claim-site terms title; confirm final applicable version |
| Promoter | Hisense UK Limited | Confirm from applicable Autumn 2026 terms |
| Bounded model | `WF7I1248BBR` washing machine | Hisense UK campaign's qualifying-products table |
| Bounded retailer | `Currys`, purchase directly from Currys' own store/site | Currys product page plus **must verify Autumn 2026 Annex 1** |
| Purchase interval, inclusive | **2026-09-09 → 2026-10-27** | Hisense UK campaign page; verify relevant product class in T&Cs |
| Claim interval, inclusive | **2026-11-27 → 2026-12-24** | Hisense UK campaign page; verify terms and disregard conflicting snippet |
| Benefit | `CASHBACK`, `fixed_amount`, **`"100.00"` GBP** | Hisense UK row for `WF7I1248BBR`; confirm Annex 2 |
| Claim destination | `https://autumncashback2026.hisensepromotions.co.uk/` | Hisense UK campaign page names this destination; site opening/claim acceptance not independently established |
| Requirements | Receipt/proof of purchase and valid product serial number, **only after full-term verification** | Hisense's campaign page explicitly says to retain proof; consult Autumn 2026 terms to confirm serial/detail requirements |
| Limits/exclusions | Record full terms' actual age/residency, consumer-only, new-product, returns, household and retailer/seller limitations | **Not yet fully verified**; do not invent or silently copy earlier campaigns |

**Official evidence URLs to preserve and review:**

1. **Hisense UK manufacturer campaign page:** <https://uk.hisense.com/promotions-giveaways/energy-efficiency-cashback> — accessible and inspected on 9 October 2026; shows `WF7I1248BBR` and £100, purchase window and claim window. The page title uses “Energy Efficiency Cashback Promotion” despite autumn campaign content; preserve actual page title and distinguish it from other campaigns.
2. **Full Hisense Autumn 2026 terms (publication prerequisite):** <https://autumncashback2026.hisensepromotions.co.uk/en_gb/terms-and-conditions-promotion/?country_promotion=2> — indexed with relevant annexes, but a bot challenge prevented complete direct reading at the time of drafting. A successful human review or independently accessible exact official terms copy is required before marking as verified.
3. **Hisense-designated claim portal:** <https://autumncashback2026.hisensepromotions.co.uk/> — destination confirmed by the manufacturer page; availability when claims open is not guaranteed.
4. **Corroborating retailer listing:** <https://www.currys.co.uk/products/hisense-kitchenfit-7i-series-wf7i1248bbr-wifienabled-12-kg-1400-spin-washing-machine-black-10304682.html> — Currys advertises the product under the autumn cashback campaign, but a promotional snippet conflicts on claim opening. The official manufacturer/terms dates take precedence after checking.
5. **Explicit exclusion from this reference:** <https://energycashback.hisensepromotions.co.uk/en_gb/land-qualifyingproducts> — an earlier, different May–June 2026 campaign listed the **same model at £150**. This is evidence for a cross-campaign regression, **not** the source for the Autumn £100 amount.

**Evidence provenance:** Record actual UTC-aware `retrieved_at` and `verified_at` instants *when each authoritative page is successfully reviewed*, exact official URL, role, page/version/title, applicable section or annex, `reviewed_on` and a concise review outcome. A successful search-result snippet or the drafting timestamp is **not** equivalent to direct full-term verification. A claim destination found within the manufacturer page is evidence of the URL, not evidence that the destination accepts claims today. Never claim a source was visited or verified when only its link was found.

### 2. Bounded product, benefit and requirements

- Candidate manifest: `reference_version: 1`, descriptive campaign, unique slug such as `hisense-autumn-cashback-2026-wf7i1248bbr-currys-reference`, single `Hisense` manufacturer, exact model `WF7I1248BBR`, and retailer `Currys`. The model must remain exact; do not introduce unverified shortened SKU aliases.
- Single retailer-specific variant linked to exactly one canonical product. Other qualifying Hisense models/participating retailers are outside this reference; absence from the reference **does not prove campaign-wide ineligibility**.
- One cashback benefit and one fixed `Decimal("100.00")` GBP reward; optional purchase price is not required and does not change the amount. No conditional/basket reward or unstated minimum price.
- Persist verified requirement types from existing enum only, normally `receipt` and `serial_number` **if confirmed** by the campaign terms. No invented `account`, `bank_details`, or extra type.
- Store claim advice and *unverified-by-v1* restrictions as clear, non-executable descriptions/limitations. Do not falsely encode condition/age/seller checks into the persisted v1 eligibility outcome.
- Before publication, independently reconcile manufacturer primary evidence, terms/annexes and retailer corroboration. If product, amount, retailer or dates conflict, **stop** and request a new documented evidence decision; do not choose the more favourable reward automatically.

### 3. Construction, publication and lifecycle

1. Parse a locally reviewed manifest; strictly reject missing/extra fields, malformed dates, reversed windows, changed SKU, amount, retailer, URLs, unreviewed source metadata and unsafe URL schemes. Pin all semantic facts/evidence/limitations with a reviewed SHA-256 digest or equally strict versioned-facts check; formatting/key ordering alone must not invalidate the file. Update the pin **only after renewed evidence review**.
2. Resolve existing Hisense, Currys and exact product identities through canonical identity matching. Reuse unambiguous identities/aliases, preserve product↔manufacturer ownership and reject ambiguous or conflicting associations. Do not globally declare `WF7I1248BBR` unique across manufacturers without the matching repository's established rules.
3. In a **caller-owned transaction and savepoint**, build exactly one graph in `review`: one `Promotion`, one retailer-specific `PromotionVariant`, single product, `CASHBACK` benefit/reward, verified requirements and provenance sources. Ensure pending unrelated caller state is not flushed or rolled back accidentally; mirror the defensive LG constructor.
4. Primary source: **verified exact Autumn 2026 terms**, once reviewed (`web_page` or verified official PDF). Supporting source: accessible Hisense campaign page; retailer page optionally corroborates direct Currys promotion. Claim source: separately identified Hisense-designated claim destination. Do not reuse a source UUID for multiple link roles; follow composite-key constraints. Never mark primary terms verified from the inaccessible challenge page.
5. Run PR #19 parsed candidate preflight. Then use only the **persisted** publication gate for `review → active`; do not set `status=active` directly. If terms cannot be verified, preflight/publication **must fail closed**, with no active object visible to purchase checks.
6. Unlike the historical Samsung/LG references, this promotion is **currently within its purchase period as of 9 October 2026**. Once fully verified, keep its published lifecycle `active` in live-period tests. Never auto-expire solely because claim submission has not opened yet. Test explicit eventual `active → expired` via the existing lifecycle service separately; do **not** conflate it with `check_purchase` returning computed `EXPIRED` on 25 December.
7. On repeated construction, compare *all* reviewed graph facts (identity, date windows, variant links, benefit, requirements, limitations, source URLs/roles/titles and provenance timestamps). Exact match returns existing object and preserves lifecycle. Conflict rejects without replacement, duplicate rows or reactivation. A test-only helper may provide an explicit promotion-finish operation only using supported lifecycle transitions, never by direct state assignment.
8. No production seed or automatic backfill, and no real customer claim submission.

### 4. Deterministic eligibility regression matrix

Create the fully reviewed/published test graph; use `CheckPurchaseRequest(brand="Hisense", model="WF7I1248BBR", retailer="Currys", purchase_date=<purchase>)`, `purchase_price=None` except where noted, the migrated PostgreSQL `purchase_check_snapshot`, and an **explicit injected** `evaluation_date`. For matched cases, initially keep persisted promotion lifecycle `active`. Assert exactly one reference promotion result.

| Purchase date | Evaluation date | Expected computed classification | Regression intent |
| --- | --- | --- | --- |
| 2026-09-09 | 2026-09-09 | `CLAIM_NOT_YET_OPEN` | First valid purchase; wait until fixed claim opening |
| 2026-09-09 | 2026-10-09 | `CLAIM_NOT_YET_OPEN` | Current date; do not offer premature claiming |
| 2026-10-27 | 2026-10-27 | `CLAIM_NOT_YET_OPEN` | Final valid purchase date inclusive |
| 2026-10-27 | 2026-11-26 | `CLAIM_NOT_YET_OPEN` | Day before fixed claim opening |
| 2026-09-09 | 2026-11-27 | `ELIGIBLE` | Opening day inclusive; independent of purchase date |
| 2026-10-27 | 2026-11-27 | `ELIGIBLE` | Late purchase shares same fixed opening |
| 2026-10-27 | 2026-12-23 | `ELIGIBLE` | Day before claim deadline |
| 2026-10-27 | 2026-12-24 | `ELIGIBLE` | Last claim day inclusive |
| 2026-09-09 | 2026-12-25 | `EXPIRED` | First calendar day after claim deadline |
| 2026-10-27 | 2027-01-01 | `EXPIRED` | Historical query still finds configured promotion |
| 2026-09-08 | 2026-09-09 | **No matching published promotion** | Purchase one day too early |
| 2026-10-28 | 2026-10-28 | **No matching published promotion** | Purchase one day too late |
| 2026-10-01 | 2026-11-27 | **No matching published promotion** | Known unlinked, separately seeded fake product or clearly unrelated known test retailer |

For matching rows assert `claim_window.opens_on == 2026-11-27`, `deadline_on == 2026-12-24`, `GBP Decimal("100.00")` with or without purchase price, fixed claim window, active lifecycle, reason-code precedence and exact source/claim URLs. For `CLAIM_NOT_YET_OPEN`, assert `all_configured_rules_satisfied` and `claim_window_not_yet_open` (check the exact enum value in code), with opening date and explanatory copy. For `ELIGIBLE` use `claim_window_open`; for `EXPIRED` use `claim_window_expired`. Confirm requirements and caveats are available as stored metadata rather than falsely evaluated.

**Important matching distinction:** a known different model/retailer and purchases outside the offer dates are filtered by candidate matching, returning empty promotions and `no_match_reason="no_matching_published_promotions"`—**not** an item classified `NOT_ELIGIBLE`. Truly unknown identities follow the existing `UnresolvedPurchaseIdentity` path. Create synthetic known non-matches rather than claiming that all other actual Hisense products are disqualified.

**Fixed-window unit boundaries:** `FixedClaimWindow(2026-11-27, 2026-12-24)` evaluated on **26 November** → `NOT_YET_OPEN`; **27 November** and **24 December** → `OPEN`; **25 December** → `EXPIRED`. Do not make service assertions with `evaluation_date` before the user's future purchase date.

**Ineligible semantics:** after verifying a new-only condition in *this* campaign's terms, use a separate pure-domain test for `PurchaseConditionRule({PurchaseCondition.NEW})`: `REFURBISHED` → `NOT_ELIGIBLE` (`condition_mismatch`); unknown → `POTENTIALLY_ELIGIBLE` (`condition_unknown`). This must **not** be asserted as a condition checked by the five-field v1 request. If full terms do not substantiate a new-only rule, omit this test rather than invent campaign-specific constraints.

**Cross-promotion regression:** ensure the same model's earlier, *separate* 2026 A-Rated campaign at £150 does not contaminate the Autumn £100 reward, period or references. Test identity reuse and promotion-variant isolation without importing the earlier campaign unless a separate reviewed fixture is genuinely required. Assert no accidental combined/duplicate reward.

**Lifecycle test:** after explicit `active → expired` on a test-only graph, historical evaluation **inside** claim dates can still return computed `ELIGIBLE` even though `promotion_status=expired`; an evaluation **after** 24 December returns `EXPIRED`. Reading/querying never changes the persisted lifecycle state.

## Persistence, transactions, and migrations

**No schema migration, index, Alembic revision or production backfill.** Reuse `manufacturers`, `products`, `retailers`, `promotions`, `promotion_variants`, `promotion_variant_products`, `benefits`, `benefit_rewards`, `requirements`, `sources`, `promotion_sources` and existing identity/alias records as appropriate.

- A stable, unique Hisense/Autumn/2026/model/Currys slug prevents collisions with historical Hisense campaigns and wider future imports.
- Persist fixed `claim_start_date=2026-11-27` and `claim_end_date=2026-12-24` with both relative offsets **null**; purchase dates are independent and inclusive.
- Store exact fixed GBP amount; do not use float or percentage calculation.
- Use genuinely observed timezone-aware UTC retrieval/verification timestamps and meaningful source titles/roles; preserve provenance and claim URL through lifecycle changes and replay.
- Graph construction in a caller-controlled nested transaction/savepoint is atomic; failure leaves no partly published reference. Repeat operations cannot duplicate identities, promotions or source links, even after safe retries.
- Ensure existing shared identities/sources are never removed during test fixture cleanup. Test constraints, rollback and preservation against the **migrated real PostgreSQL** container, not SQLite.
- Do not commit the reference to a production database as part of this PR.

## External services and network access

**Runtime/test external services: None.** Hisense and Currys websites are human-reviewed **evidence sources**, not runtime or CI dependencies. No live HTTP fetch, credentials, bot bypass, login, retries, browser tool, scheduled source monitor, or new outbound network integration is required. Do not implement scraping or silently fall back from challenged official terms to guessed data.

Before finalising the immutable fixture, a maintainer must resolve the full-term access/evidence gap, verify Annex 1/2 and record what was actually seen, with observation timestamps. If inaccessible, the task remains blocked for authoritative publication; an offline unverified review candidate is the maximum acceptable partial implementation.

## Security and privacy

- Persist only promotion facts/evidence URLs, source metadata, requirement **types** and generic claim instructions. **No customer receipts, serial numbers, names, contact data, passwords, bank details or claim session tokens** in fixtures/tests/logs.
- Treat source pages and local JSON as untrusted data; accept only reviewed HTTPS URLs and strictly bounded facts. No `eval`, executable extracted conditions, unsafe serialization, arbitrary URL fetching or SSRF exposure.
- Reject bad product-manufacturer mappings, retailer aliases, unverified sources or conflicting published graph edits; never bypass the publication gate.
- Keep `POST /api/v1/eligibility/check` unchanged and its existing read-only/public safety properties intact. Explanations must not promise reward approval or certify unaudited personal eligibility.

## Configuration and deployment

**None.** No environment variables, feature flags, jobs, service credentials, Docker/Railway settings or startup loading. The only new data is an offline test fixture plus its tests; promotion publication to a deployed environment would be a **separate** explicit, reviewed operational action.

## Observability and operations

Existing `check_purchase` structured diagnostic events and source provenance are sufficient. Do not introduce per-Hisense metrics or customer-identity logs. Domain no-match/not-yet-open/expired outcomes are normal results, not server errors. Report publication validation failure using existing structured issues and no partial live state. No changes to health/readiness endpoints.

## Failure, consistency, and recovery

| Scenario | Required behaviour |
| --- | --- |
| Full Autumn 2026 terms cannot be verified | Fail closed; no validated `active` published reference; record precise blocker |
| Official/retailer facts disagree | Do not guess or silently prefer cashback value; stop, document discrepancy and update only after authoritative review |
| Invalid manifest or changed semantic pin | Reject before graph publication, with no state change |
| Ambiguous/reused identity with wrong manufacturer | Reject without creating duplicate or corrupted product links |
| Constructor fails after partial flush or preflight | Roll back only the owned savepoint/transaction; caller's unrelated state safe |
| Persisted publication validation rejects source/graph | Remain non-active; do not set status directly |
| Replay with unchanged graph already `active` | Return existing record without changing timestamps/amounts/status |
| Replay with changed graph or incompatible status | Reject; no overwrite, auto-reactivation, or unintended deletion |
| Claim-window passes while database status remains `active` | Computed `EXPIRED`; read-only evaluation does not mutate state |
| Explicit retirement of verified promotion | Existing lifecycle service performs transition, historical data still queryable |
| Network inaccessible in tests | No effect: tests use pinned local evidence only |

## Acceptance criteria

### Behaviour

- [ ] One **actually verified** Hisense Autumn 2026/Currys/`WF7I1248BBR` £100 reference is represented; no other retailer/model is falsely treated as catalogued.
- [ ] Official current terms including Annex 1/2 and retailer-specific restrictions have been directly reviewed; any conflicting dates or amounts are reconciled and recorded. **If not, publication is blocked and the task is not marked complete.**
- [ ] The purchase interval and delayed fixed claim window are inclusive with correct result classifications at every matrix boundary.
- [ ] No false `NOT_ELIGIBLE` result for candidate-filtered exclusions; unknown identities remain distinct.
- [ ] Optional purchase price never changes the GBP 100 fixed reward; no earlier £150 campaign bleed-through.
- [ ] Existing public API and domain/application separation remain unchanged; no LLM/network runtime dependency.

### Data and consistency

- [ ] Reviewed semantic fixture pin prevents unaudited edits and carries truthful source URLs, timestamps, terms anchors and limitations.
- [ ] Constructor/preflight/persisted publication gate handles idempotent replay, safe failure, rollback and conflicting data.
- [ ] Source provenance and claim destination survive explicit `active → expired` lifecycle change, without record deletion.
- [ ] Real migrated PostgreSQL/Testcontainers checks pass; no schema migration needed.

### Security

- [ ] Invalid/unverified promotion data never enters authoritative active eligibility results.
- [ ] Only evidence/claim instructions, not customer PII or secrets, are stored.
- [ ] Existing validation, HTTPS source safety and HTTP boundary are preserved.

### Operations

- [ ] No startup seed, production write, external HTTP call or background task is introduced.
- [ ] Expected no-match and time-window classifications have existing safe diagnostic behaviour.

### Code quality

- [ ] PR is focused, follows `AGENTS.md`, reuses existing constructors/patterns, has no unrelated refactor or dependency.
- [ ] All targeted tests plus relevant Samsung/LG/publication/HTTP regressions pass; formatting/lint pass; unrun checks are reported honestly.

## Tests to add or update

### Unit tests

**`backend/tests/unit/test_hisense_reference_promotion.py`**

1. Exact pinned campaign identity, `WF7I1248BBR` spelling, Currys retailer scope, fixed claim dates, GBP `"100.00"` decimal string, source URLs, review observations and verified terms anchors.
2. Manifest rejects missing/extra/changed properties, mixed campaign facts (£150 earlier promo), changed retailer/model, corrupted semantic digest, invalid/unsafe URLs, non-decimal amount, wrong claim-window type and inverted dates. JSON whitespace and key order are digest-neutral.
3. Pure `FixedClaimWindow` opening/day-before/last-day/day-after boundaries.
4. Deterministic reward calculation with and without purchase price, no float/rounding surprises.
5. If confirmed by Autumn terms: pure-domain `NEW` versus `REFURBISHED`/unknown condition outcome, **separate from public API**.
6. Assert no reliance on wall clock or live Hisense endpoints in validation/eligibility tests.

### PostgreSQL integration tests

**`backend/tests/integration/test_hisense_reference_promotion.py`**

1. Construct graph in `review` with canonical identities, approved reviewed sources, one variant, exact benefit, typed requirements and candidate preflight; publish through persisted `change_promotion_status(..., ACTIVE)`.
2. Run the **real** `purchase_check_snapshot` + `check_purchase` through all rows of the matrix with injected evaluation dates; assert classification, reason codes/order, exact reward, claim dates, explanations, requirements and sources.
3. Test known excluded synthetic retailer/product versus unknown identity/no match; do not invent false official campaign exclusions.
4. Assert `CLAIM_NOT_YET_OPEN` on 9 October 2026 while promotion is `active`, `ELIGIBLE` on opening/deadline days and `EXPIRED` after the deadline without read-side mutation.
5. Test explicit lifecycle transition to `expired`, then re-query historically to show computed `ELIGIBLE` for a 2026 open-claim date, with historical provenance still attached.
6. Reject missing/unverified primary/claim source, invalid manufacturer link or other publication invalidity, and assert no active publication.
7. Assert repeat construction/finish, graph fingerprints, idempotency, rollback after mid-construction and preflight exceptions, replay after retirement, no duplicate records and safe identity/source cleanup.
8. Regression for the distinct earlier £150 campaign and same SKU: Autumn amount/dates remain £100/2026-09-09..10-27; source/reward graph not cross-linked.
9. Assert read-only, reproducible snapshot and no provider fetch or AI call.

### API/application tests

Inside the new integration file or focused existing tests, call the **unchanged** `POST /api/v1/eligibility/check` backed by the actual persisted reference, with injected `uk_evaluation_date` according to existing test wiring. Verify:

- Purchase `2026-10-27`, evaluation `2026-11-26`: HTTP 200, `CLAIM_NOT_YET_OPEN`, correct opening/date/claim link.
- Same purchase, evaluation `2026-11-27`: HTTP 200, `ELIGIBLE`, fixed GBP 100, requirements, source links and active lifecycle.
- Evaluation `2026-12-25`: `EXPIRED` computed without deleting or changing promotion status.
- Out-of-window purchase / known wrong test retailer: empty `promotions` and existing no-match reason.
- Existing JSON error/validation/OpenAPI contracts unchanged; no new Hisense route.

### MCP contract tests

**N/A.** No MCP tool or MCP contract change.

### External-boundary tests

No new outbound client is added. Normal tests must never fetch Hisense/Currys pages or make any real claim request. Where helpful, assert accidental remote calls fail; leave Testcontainers Docker traffic untouched. **Human review of official T&Cs is a non-CI acceptance activity and must not be simulated with a mock that claims a source was visited.**

## Verification commands

From `backend/`; confirm against `pyproject.toml` and README at implementation time:

```bash
uv sync --locked --extra dev
uv run ruff format --check .
uv run ruff check .
uv run pytest tests/unit/test_hisense_reference_promotion.py
uv run pytest tests/integration/test_hisense_reference_promotion.py
uv run pytest tests/unit/test_samsung_reference_promotion.py tests/integration/test_samsung_reference_promotion.py
uv run pytest tests/unit/test_lg_reference_promotion.py tests/integration/test_lg_reference_promotion.py
uv run pytest tests/integration/test_check_purchase.py tests/integration/test_promotion_publication.py
uv run pytest tests/integration/test_eligibility_api.py
uv run pytest
```

The **new Hisense test paths are implementation deliverables**, not presently existing runnable commands. PostgreSQL integration tests require Docker/Testcontainers. The inspected `backend/pyproject.toml` configures Ruff and pytest but no mypy invocation; do not invent an unconfigured type-check command. No Alembic migration is required. If checks cannot run, report exact commands, blockers, alternative checks and remaining risk. Do not weaken tests to get green.

## Completion report

### Changed

List reviewed Hisense manifest, precise model/retailer scope, test-only constructor, real publication/eligibility regression coverage and evidence documentation.

### Database and migrations

`None` for migrations; describe isolated test graph, active/expired lifecycle cases, exact fixed window/reward and preserved provenance.

### API/MCP contracts

`None`; identify the existing HTTP route exercised in tests.

### Tests and verification

List added test paths, commands actually run and outcomes. Explicitly distinguish source verification from automated test execution.

### External configuration

`None` for new config. Record any **manual terms review** and whether authoritative publication was allowed or blocked.

### Deviations

Describe deviations from one-model/one-retailer scope, changed evidence, mismatched official dates/amount or other required design change; otherwise `None`.

### Remaining risks or follow-up

State any outstanding official terms access, eligibility dimensions unsupported by the v1 purchase input, manufacturer validation discretion, future reward/source changes, or need for a separately reviewed production deployment. Never mark blocked verification as complete.
