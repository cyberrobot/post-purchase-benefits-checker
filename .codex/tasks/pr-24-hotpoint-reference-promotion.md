# PR 24 — Hotpoint Reference Promotion

## Repository state

**Expected branch:**  
`pr24-hotpoint-reference-promotion` (verify it is available before creating it)

**Base branch:**  
`main` (after PR #23; verify the current head and actual next PR number before creating a pull request)

**Dependencies:**  
Existing promotion schema/lifecycle/provenance/identity/rewards/claim windows (PRs #3–#15), `check_purchase` (PR #17), eligibility HTTP API (PR #18), candidate authoring/publication validation (PR #19), Samsung (PR #20), LG (PR #21), and the verified Hisense reference (PR #23). Python 3.13, FastAPI, SQLAlchemy 2, PostgreSQL/Testcontainers, Alembic, `uv`, pytest and Ruff. No new runtime dependency is expected.

### Read first

- Repository `AGENTS.md`; any applicable scoped instructions.
- `.codex/tasks/TEMPLATE.md` and `.codex/tasks/pr-20-samsung-reference-promotion.md`, `pr-21-lg-reference-promotion.md`, `pr-22-hisense-reference-promotion.md`.
- `backend/README.md`, `backend/tests/fixtures/promotions/README.md`.
- Existing reviewed fixtures and constructors, especially `backend/tests/hisense_reference.py`, `backend/tests/lg_reference.py`, their unit/integration tests, and the corresponding publication checks.
- Exact Wren subsection of Hotpoint's **official** 2026 campaign terms: <https://promo.hotpoint.co.uk/terms-and-conditions> (not the neighbouring participating-retailers or Hotpoint.co.uk-only subsections).
- Official claim page: <https://promo.hotpoint.co.uk/>; corroborating official FAQ: <https://promo.hotpoint.co.uk/faqs/>.

### Primary change area

**Promotion reference data and deterministic eligibility regression tests**, scoped to **one exact Hotpoint model bought directly from Wren**. This is a reviewed, test-only reference—not an importer, scraper, account integration or entire campaign catalogue.

### Canonical implementation examples

- `backend/tests/fixtures/promotions/hisense-autumn-cashback-2026-wf7i1248bbr.json`
- `backend/tests/hisense_reference.py` and `backend/tests/unit/test_hisense_reference_promotion.py`
- `backend/tests/integration/test_hisense_reference_promotion.py`
- `backend/tests/lg_reference.py`; `backend/tests/integration/test_lg_reference_promotion.py`
- `backend/app/application/promotion_authoring.py`, `backend/app/application/promotions.py`
- `backend/app/application/purchase_check.py`
- `backend/app/db/repositories/promotions.py`
- `backend/app/domain/claim_windows.py`, `backend/app/domain/eligibility_result.py`
- `backend/tests/integration/test_promotion_publication.py`, `backend/tests/integration/test_eligibility_api.py`

### Relevant symbols

`CheckPurchaseRequest`, `check_purchase`, `purchase_check_snapshot`, `IdentityResolver`, `SqlAlchemyIdentityRepository`, `parse_candidate_promotion`, `validate_candidate_promotion`, `change_promotion_status`, `PromotionStatus`, `FixedClaimWindow`, `evaluate_fixed_claim_window`, `ClaimWindowStatus`, `Manufacturer`, `Product`, `Retailer`, `Promotion`, `PromotionVariant`, `PromotionVariantProduct`, `Benefit`, `BenefitReward`, `Requirement`, `Source`, `PromotionSource`, and the existing FastAPI `uk_evaluation_date` test override.

### Expected change surface

1. **New:** `backend/tests/fixtures/promotions/hotpoint-wren-cashback-2026-h7ic16m6-uk.json`.
2. **New:** `backend/tests/hotpoint_reference.py` — test-only manifest reader, semantic pin, and atomic ORM fixture constructor.
3. **New:** `backend/tests/unit/test_hotpoint_reference_promotion.py`.
4. **New:** `backend/tests/integration/test_hotpoint_reference_promotion.py`.
5. **Update:** `backend/tests/fixtures/promotions/README.md` — source evidence ledger, claim-delay limitation and construction instructions.
6. **Optional small update:** `backend/README.md` to point to the reference and its tests.
7. **Spec:** `.codex/tasks/pr-24-hotpoint-reference-promotion.md` (this file).

Avoid copying entire helper modules mechanically if a narrow existing helper can be reused without expanding the refactor.

### Excluded areas

- No production seeding, scheduled ingestion, live page fetches in tests, retailer/manufacturer login, cashback claim submission, bank integration or handling genuine personal receipts.
- No broader Hotpoint campaign import; specifically **do not** include AO/Currys/other participating retailers or the Hotpoint.co.uk-only campaign.
- No changes to public REST/MCP schemas, transport handlers, promotion rules, shared lifecycle, identity matching or application eligibility logic merely to get assertions to pass.
- No database schema migration or new benefit/requirement enum in this PR.
- No silent alteration of Samsung, LG or Hisense reviewed data.
- **Do not claim complete historical claim-timing accuracy:** the existing backend cannot combine a purchase-relative opening with an absolute deadline; see the mandatory safety note below.

### Unknowns Codex must verify

1. Confirm that the official Wren terms still state **model `H7IC16M6 UK`, £75, Wren-only, purchases 5 May–12 June 2026, fixed claim period 4 June–4 December 2026, and a 30-day wait**. Check for amendments before pinning the fixture.
2. Confirm the current published-source validation contract: required `primary` and `claim` roles, verified timestamp rules, allowed source types, and whether the claim destination can be attested by the terms without directly fetching it.
3. Confirm canonical Wren retailer identity and exact Hotpoint model normalisation (`H7IC16M6 UK` with the internal space). Do not invent a manufacturer SKU without evidence.
4. Confirm the latest candidate schema and publication gate: one fixed **or** one relative claim window, not both; fail if an implementation implicitly merges them.
5. Confirm `check_purchase` excludes `review`, includes published `active`/`expired`, returns resolved no-match distinctly from unresolved identities, and provides stable reason codes, reward and provenance.
6. Confirm branch/PR numbering immediately before opening the actual PR. This spec assumes #24 from latest observed PR #23.

---

## Objective

Add **one real UK Hotpoint cashback reference** for the **Hotpoint MaxiSpace built-in dishwasher, model `H7IC16M6 UK`, purchased directly from Wren**, paying **exactly GBP 75.00** under Hotpoint's 2026 **Wren-specific** cashback terms.

Deliver an offline, source-backed fixture and test-only constructor that can be validated through the existing candidate preflight and **persisted** publication gate in isolated PostgreSQL tests. Exercise the actual `check_purchase` read snapshot and the existing HTTP endpoint for supported evaluation dates. Cover purchase date edges, £75 reward, claim closing date, requirements, provenance, identity/no-match handling, malformed evidence, rollback and replay.

**Important accuracy boundary:** Hotpoint requires a claim to be submitted no earlier than **30 days after each purchase**, in addition to fixed claim dates. PR #24 **must not** pretend that an ordinary fixed-window record enforces that purchase-relative wait. Scope integrated `ELIGIBLE` test expectations to evaluation dates where the wait has already elapsed; explicitly document the unsupported historical interval. This PR is **test-only**, and its fixture must not be production-published as a complete, general-purpose claim-eligibility rule until conjunctive claim windows are supported or a separate safe business rule is introduced.

## Architecture and invariants

- Maintain the existing pipeline: reviewed official terms → pinned fixture → test-only ORM graph in `review` → candidate preflight → existing persisted publication validation → real `check_purchase` through SQLAlchemy snapshot → FastAPI.
- No model-generated facts, runtime network call or Hotpoint-specific conditional in the core eligibility engine.
- Preserve a **single reference variant** (one exact model, Wren retailer, one cashback amount). Do not claim this covers Wren's other eligible products.
- Distinguish **promotion lifecycle** (`review`, `active`, `expired`) from **computed eligibility classification** (`ELIGIBLE`, `CLAIM_NOT_YET_OPEN`, `EXPIRED`, etc.).
- Use inclusive **UK calendar dates** for the reference. The exact 00:00/23:59 cutoff is a limitation of the current date-only request; do not claim sub-day enforcement.
- Price is not a prerequisite for the fixed £75 reward; never compute cashback as a percentage.
- Input contains brand, model, retailer, purchase date and optional price only. Consumer residence/age, purchase condition, Wren seller verification, product registration, receipts, serial, prior claims, returns and banking data are **not verified** by `check_purchase`.
- Reference helpers must be explicitly **test-only** and cannot be imported by production app startup or wired to public writes.
- Do not create a false active promotion from missing, tampered, stale or unreviewed terms evidence.

---

## API and contract changes

**None.**

- Preserve existing `POST /api/v1/eligibility/check` request, response, error and OpenAPI contracts.
- No new administrative or MCP endpoint.
- Test-only Python helper is not a public API. It accepts an existing SQLAlchemy test session, does not commit a caller-owned transaction, and may reject inconsistent state.
- HTTP regression tests use the existing application state and injected `uk_evaluation_date` override, not bespoke Hotpoint route logic.

---

## Domain and application behaviour

### 1. Authoritative bounded campaign facts

Source checked during specification drafting on **12 October 2026**; implementation must record its own actual retrieval and verification UTC timestamps rather than manufacture timestamps from this date.

| Fact | Exact reference value | Official Wren-term basis |
| --- | --- | --- |
| Campaign | **Hotpoint Cashback Promotion – Wren (2026)** | Heading of Wren subsection |
| Promoter | Hotpoint UK Appliances Limited | Wren subsection opening |
| Manufacturer | `Hotpoint` | Offer identity |
| Product | MaxiSpace built-in dishwasher, 60 cm | Wren clause 4 table |
| Exact model | **`H7IC16M6 UK`** | Wren clause 4, dishwasher row |
| Purchase retailer | **`Wren` only** | Wren clause 13 |
| Eligible purchase dates | **2026-05-05 to 2026-06-12 inclusive** | Wren clause 2 |
| Base claim interval | **2026-06-04 to 2026-12-04 inclusive** | Wren clause 3 |
| Individual earliest claim | **purchase date + 30 calendar days**, not earlier than 2026-06-04 | Wren clause 8(c), official FAQ |
| Cashback | `CASHBACK`, `fixed_amount`, **`"75.00"` GBP** | Wren clause 4 table |
| Registered warranty | Required | Wren clauses 6 and 8(b) |
| Evidence | Receipt, product model, serial number, warranty-registration confirmation | Wren clauses 5 and 8(c) |
| Claim site | `https://promo.hotpoint.co.uk/` | Wren clause 8(c) and official claim page |
| Territory/person | UK resident aged 18+; specified employee/professional exclusions | Wren clause 1 |
| Product exclusions | Graded, seconds, replacement and imperfect products | Wren clause 14 |
| Restrictions | One cashback claim per eligible appliance; cannot combine with another promoter offer unless allowed; returned product ineligible | Wren clauses 9, 15 and 20 |
| Claim payment | Bank transfer after validation; not proof of eligibility at purchase | Wren clause 16 |

**Primary official evidence:** <https://promo.hotpoint.co.uk/terms-and-conditions> — specifically heading **“HOTPOINT CASHBACK PROMOTION - WREN”**; the retailer-general and Hotpoint.co.uk-only subsections have **different** retailer scopes, rewards and/or deadlines and must not be used as interchangeable evidence.

**Claim destination:** <https://promo.hotpoint.co.uk/> — an official Hotpoint-controlled campaign site displaying the special **4 December 2026** deadline for Wren. Direct accessibility of a user-specific completed claim is neither required nor asserted.

**Corroboration:** <https://promo.hotpoint.co.uk/faqs/> — lists the Wren extended deadline and 30-day wait. It is **supporting evidence**, not a substitute for the Wren clauses.

Retain the Wren-section heading, fact-to-clause map, observation date, exact official URLs and any available content checksum/revision in fixture provenance. The specification does **not** assert an exact official HTML-byte hash or a live claim-portal submission.

### 2. Mandatory claim-window limitation and fail-safe handling

The legal/official submission interval for a qualifying purchase on date **P** is:

```text
earliest_allowed_claim_date = max(2026-06-04, P + 30 calendar days)
last_allowed_claim_date     = 2026-12-04
```

Examples:

| Purchase P | Last day still waiting | First claim day | Last claim day |
| --- | --- | --- | --- |
| 2026-05-05 | 2026-06-03 | 2026-06-04 | 2026-12-04 |
| 2026-06-12 | 2026-07-11 | 2026-07-12 | 2026-12-04 |

**Verified codebase limitation:** `CandidatePromotionV1` accepts `FixedWindow` **or** `RelativeWindow`. The current persisted `check_purchase` explicitly rejects simultaneous fixed and relative fields as `published_claim_window_invalid`. Neither approach independently expresses both the per-purchase delay and a single 4 December deadline.

**PR #24's permitted representation** is the honest, minimal **fixed base period** (`2026-06-04`–`2026-12-04`), plus a **prominent structured manifest limitation** recording `minimum_days_after_purchase: 30` as **unmodelled, nonauthoritative metadata**. This metadata is for evidence/testing/documentation only; it is **not** passed as an unrecognised extra key to the strict v1 candidate format, and it is **not** silently enforced by the application.

**Safe test/interpretation envelope:** for a particular purchase, a fixed-window `ELIGIBLE` result may be considered consistent with the official *claim timing* only if evaluation date is on or after `max(2026-06-04, purchase_date + 30 days)` and no later than `2026-12-04`. `CLAIM_NOT_YET_OPEN` before the 4 June global opening and `EXPIRED` after 4 December are also safe timing assertions. Do not make integrated `ELIGIBLE` assertions in the unsafe interval **4 June through 11 July 2026** for purchases whose individual waiting periods had not elapsed.

**Explicit risk and follow-up:** if this reference were used with arbitrary historical evaluation dates, the fixed-only engine could produce a **false-positive `ELIGIBLE`** while an individual 30-day waiting period remained. Thus **no production publication or general claim-now promises** in this PR. A future separate feature should add a validated *combined purchase-relative opening + fixed absolute deadline* rule with domain, candidate, persistence, query, HTTP and migration tests. Do not sneak that feature into this small reference PR.

### 3. Requirements, unknowns and classification

- Persist existing requirement types `receipt`, `serial_number`, `registration`; descriptions cite Wren clauses 5/6/8. Do not store account/sort-code fields in a fixture.
- Store proof/registration as **claim steps**, not as automatically satisfied user facts.
- Correct known identities and purchase date in range: exactly one reference candidate with fixed GBP 75.00 cashback; for safe evaluation dates, `ELIGIBLE` through 4 December, and computed `EXPIRED` beginning 5 December.
- Purchase dates **4 May** and **13 June**, or a separately inserted **known** excluded model/retailer: **resolved no matching published promotion**, not a fabricated `NOT_ELIGIBLE` offer.
- Unknown/unresolvable brand, retailer or model: retain `UnresolvedPurchaseIdentity` as the current service does, not a negative decision.
- Optional purchase price (including absent) does not change a fixed cashback amount.
- An expired **claim window** does not automatically change persisted `active` lifecycle state. Deliberate `active → expired` retains the full reference, and an injected historical date before the claim deadline can still evaluate `ELIGIBLE` when safely after the waiting period.
- Residency, age, graded products, prior claim, marketplace seller, return, payment and receipt quality cannot be inferred; surface restrictions in the benefit description/limitations, not invented rules.

### 4. Fixture, validation and publication

- Use a versioned local **JSON evidence manifest** similar to Hisense/LG, with immutable facts and explicit `reference_version`, `evidence_status`, provenance, clause map, claim-delay limitation, full exclusions and requirements.
- Pin a canonical JSON semantic SHA-256 over facts **including limitations and evidence**. Obtain and commit the actual digest only **after** reviewing the final fixture. Never pre-fill a guessed hash.
- Validate strict, correct source URLs, date order, exact model/cashback, Wren-specific table selection and reviewed-status gate; reject altered semantic content, malformed types, swapped retailer, changed reward or missing/forged evidence.
- Construct canonical Hotpoint/Wren/product identities with existing `IdentityResolver`. Preserve the model string from the primary terms; do not strip UK suffix or treat arbitrary lookalikes as identical.
- Construct `Promotion` in `review` with one Wren variant; attach one fixed claim window, one cashback reward, the three requirements, and verified `primary` and `claim` source roles. Claim URL may be attested *from the official terms*: label the observation honestly; do not misstate that a particular form or user claim was fetched.
- Check PR #19 candidate preflight; its expected unresolved-reference issue is not publication approval. Exercise `change_promotion_status(..., ACTIVE)` **inside the isolated integration database** and verify the **persisted** validation gate.
- Leave transaction/commit ownership to the caller; use a nested transaction or equivalent existing atomic fixture pattern. Reject caller sessions with unexpected pending changes before a nested begin that could flush them.
- Replays must return the same reference graph, never duplicate records or mutate lifecycle/provenance/reward. Detect conflicting existing graph and ambiguous identities, fail safely and roll back only fixture-owned writes. A retry after `expired` must **not** republish.
- Normal app startup and ordinary tests **must never seed** this reference into production.

---

## Persistence, transactions, and migrations

**No schema or Alembic migration.** Use existing manufacturer, product, retailer, promotion, variant, benefit/reward, requirement and source tables.

- Validate real PostgreSQL constraints and the current source role/link uniqueness requirements.
- Preserve `review → active → expired` history and all source/evidence relationships.
- No hardcoded authoritative database UUIDs; fixture identity is reconciled through existing canonical matching.
- Verify transaction rollback after construction/preflight or persisted publication validation failure; do not delete caller-owned shared identity rows during cleanup.
- An existing graph with the same slug but altered amount, dates, product, retailer, requirements or sources is a **conflict**, not a reason to update silently.
- Existing migrations remain unchanged. Integration tests use the project's **migrated** PostgreSQL Testcontainer.

---

## External services and network access

**No outbound call in implementation or tests.**

Hotpoint's official HTTPS URLs are **curated data**, not dynamic user-provided fetch targets. The only evidence-review network activity occurs **outside** deterministic test runs. No credentials, account session, browser automation, API timeout/retry policy or external provider is added.

Keep the source links in fixture data; CI/unit/integration tests never fetch Hotpoint pages. If an official page later changes, manual review must lead to an intentional new fixture version/digest, not a silent runtime refresh.

---

## Security and privacy

- No real claimant name, address, bank account/sort code, serial number, receipt image, email, session cookie or warranty registration credential in code, fixtures or test logs.
- Do not log arbitrary raw third-party HTML or instructions as executable content. Treat the retrieved terms as untrusted **data** until reviewed and pinned.
- The test-only constructor must not bypass candidate/persisted publication validation, and no FastAPI/admin write endpoint is introduced.
- No new access-control boundary is required. Public API behaviour and safe errors remain unchanged.
- Avoid overstating verified facts: validating a reference purchase does not prove customer entitlement or claim approval.

---

## Configuration and deployment

**None.** No environment variables, secrets, Docker/Railway changes, migration, background worker, scheduler, startup hook or health/readiness change.

No hidden production seeding. A future production import needs a separate verified rule-model decision on the combined claim window.

---

## Observability and operations

Existing request/eligibility diagnostics remain unchanged. Tests may report deterministic fixture construction/publication conflict reasons without exposing private data. No new metrics, traces, alerts or log dimensions are introduced.

Document that this is a single reference and the **claim-opening limitation** is a known, explicit issue, not an implementation-success claim.

---

## Failure, consistency, and recovery

- **Official evidence becomes inaccessible/amended:** keep reviewed fixture version pinned; do not silently refresh or claim later verification. Reject altered unreviewed content.
- **Manifest mismatch or invalid source metadata:** stop before write, or roll back the test-only graph.
- **Missing/unverified primary or claim source:** persisted promotion validation rejects `active`; no partial publication.
- **Duplicate fixture construction:** same IDs/graph, no extra links or benefits.
- **Conflicting canonical identity or edited existing graph:** deterministic exception, caller's existing rows untouched.
- **Error during nested fixture transaction:** rollback all fixture-owned side effects, preserve previously flushed unrelated caller rows.
- **Restart/replay after `review`, `active`, or `expired`:** allow safe resume only as current lifecycle rules permit; no expired-to-active resurrection.
- **Claim-window modelling conflict:** don't set simultaneous fixed and relative columns or bypass `published_claim_window_invalid`; don't introduce a false claim-now guarantee.

---

## Acceptance criteria

### Behaviour

- [ ] One official, narrowly scoped Hotpoint/Wren cashback reference is represented: **`H7IC16M6 UK` + Wren + £75.00 + purchases 5 May–12 June 2026**.
- [ ] Claim-page and Wren terms confirm the **4 December** deadline; no accidental use of the **26 July** deadline from other campaign subsections.
- [ ] Manifest records 30-day delayed opening **as an acknowledged unmodelled condition**, and docs explicitly prohibit treating fixed-only results as fully accurate for pre-wait historical dates.
- [ ] After the relevant waiting period has elapsed, real PostgreSQL snapshot checks classify the bounded matching purchase `ELIGIBLE` through 4 December and `EXPIRED` on 5 December, with exact £75 reward.
- [ ] Known wrong model/retailer and purchase dates outside 5 May–12 June produce **no-match**, not a spurious `NOT_ELIGIBLE`; unknown identities remain unresolved.
- [ ] Requirements include receipt, serial and registration; explanations/provenance are returned through unchanged `check_purchase` and HTTP contracts.
- [ ] No Hotpoint-specific runtime business logic, public route, production seed or network test dependency is introduced.

### Data and consistency

- [ ] Source URLs and observations are accurate; capture timestamps reflect **actual implementation verification** and the claim URL's precise basis.
- [ ] Pinned semantic digest rejects tampering; unverified/missing required sources cannot publish.
- [ ] Transaction ownership, rollback, identity ambiguity, conflicting graph, idempotency and replay are tested.
- [ ] Reference is published only in test DBs; source/reward/history persist across deliberate expiration.
- [ ] PostgreSQL migrations remain unchanged and the existing schema is exercised.

### Security

- [ ] No personal receipts, banking info, genuine serials or tokens are retained.
- [ ] No unvalidated or model-extracted content becomes published authority.
- [ ] Existing safe API errors and request validation stay intact.

### Operations and code quality

- [ ] CI is offline with respect to Hotpoint/Wren; regular app startup never loads the fixture.
- [ ] No unrelated refactors/new dependencies.
- [ ] Actual lint/format/test results are reported, without claiming unrun commands passed.
- [ ] Follow-up for **combined fixed deadline + purchase-relative opening** is clearly documented before any production promotion publication.

---

## Tests to add or update

### Unit tests

File: `backend/tests/unit/test_hotpoint_reference_promotion.py`.

1. Assert manifest exactness: campaign **Wren**, product **`H7IC16M6 UK`**, £75.00, purchase boundaries, 4 December claim deadline, required evidence and 30-day limitation.
2. Assert semantic pin catches model, retailer, amount, deadline, official URL, evidence-status, claim-delay metadata or requirements tampering; key order and formatting changes preserve digest.
3. Confirm fixed £75 reward with absent, low or high purchase price using the existing reward calculator (`Decimal`, never `float`).
4. Confirm `FixedClaimWindow(2026-06-04, 2026-12-04)` has inclusive base opening/deadline (3 June not open, 4 June open, 4 December open, 5 December expired).
5. Independently test the **official 30-day arithmetic as data evidence**: 5 May → 4 June and 12 June → 12 July. Name this a **limitation regression**, not an assertion that current `check_purchase` enforces the waiting period.
6. Where helpful, use existing pure domain `PurchaseConditionRule` for `NEW` vs graded/refurbished as **domain capability coverage only**; don't claim a corresponding v1 API input or persisted rule is present.
7. Ensure malformed/missing or contradictory source facts cannot be repaired silently.

### PostgreSQL integration tests

File: `backend/tests/integration/test_hotpoint_reference_promotion.py`, with the established migrated Testcontainers PostgreSQL setup.

| Purchase | Evaluation date | Wren exact-model expected | Notes |
| --- | --- | --- | --- |
| 2026-05-04 | 2026-10-12 | `NO_MATCH` | Day before eligible purchases |
| 2026-05-05 | 2026-06-03 | `CLAIM_NOT_YET_OPEN` | Global opening and personal wait not yet met |
| 2026-05-05 | 2026-06-04 | `ELIGIBLE` | Earliest purchase, precisely 30 days later |
| 2026-05-05 | 2026-10-12 | `ELIGIBLE` | Within valid supported envelope |
| 2026-06-12 | 2026-07-12 | `ELIGIBLE` | Last purchase, precisely 30 days later |
| 2026-06-12 | 2026-12-04 | `ELIGIBLE` | Final Wren claim day |
| 2026-06-12 | 2026-12-05 | `EXPIRED` | Day after Wren deadline |
| 2026-06-13 | 2026-10-12 | `NO_MATCH` | Day after purchases close |
| 2026-06-01 | 2026-10-12 | `NO_MATCH` | Separately inserted known *non-Wren* retailer |
| 2026-06-01 | 2026-10-12 | `NO_MATCH` | Separately inserted known unpromoted model |

All checks above must execute `purchase_check_snapshot` + **real** `check_purchase`; the expected `NO_MATCH` means resolved identity with `NoMatchReason.NO_MATCHING_PUBLISHED_PROMOTIONS`, not an invented eligibility enum.

**Do not add `ELIGIBLE` integration assertions on 2026-06-20 for a 2026-06-12 purchase:** that is exactly the known fixed-only false-positive window. Add a focused test/documentation assertion that the fixture **records and exposes the limitation**, and that it has not been silently presented as a fully enforced rule.

Additional integration coverage:

- Publish through `change_promotion_status(..., ACTIVE)` in isolated DB; confirm `review` candidates remain invisible before publication and missing primary/claim source blocks publication.
- Check one and only one variant, correct canonical manufacturer/model/retailer, exact decimal reward, claim-window fields, required evidence descriptions, Wren primary URL, claim destination, fixed dates and stable reason codes.
- Resolve a known wrong retailer/model separately; unknown identities return their current unresolved types.
- Constructor retry and replay at `review`, `active`, `expired`; preserve graph IDs, source metadata and lifecycle, including after explicit expiry.
- Failure injection during construction/preflight and during publication; verify rollback, no leaked identities and no changes to pre-existing caller rows.
- Optional concurrency check only if existing test pattern supports it without introducing a new framework.
- Verify a published `expired` historical reference still evaluates `ELIGIBLE` with an injected **2026-12-04** evaluation date, but `EXPIRED` on **2026-12-05**.

### API/application tests

Extend the new integration test file with `TestClient` using the existing `POST /api/v1/eligibility/check` and `uk_evaluation_date` override:

- Matching exact model/Wren purchase (`2026-05-05`) as of `2026-10-12`: one result, £75, expected reason codes, source and requirements.
- Same purchase as of `2026-12-05`: existing `EXPIRED` classification and same provenance.
- Known wrong retailer or out-of-purchase-period date: existing no-match shape, not a new error schema.
- No new request fields or claim-delay flag in the public contract; document the limitation in reference metadata/description instead.

### MCP contract tests

**N/A.** No MCP adapter is present or changed in this PR.

### External-boundary tests

No live HTTP or model-provider calls. Tests use the pinned terms evidence, and must fail if they attempt to reach Hotpoint. Docker/Testcontainers connectivity for PostgreSQL is the existing integration infrastructure, not manufacturer retrieval.

---

## Verification commands

From `backend/`, reflecting current `pyproject.toml` and existing test files:

```bash
uv sync --locked --extra dev
uv run ruff format --check .
uv run ruff check .
uv run pytest tests/unit/test_hotpoint_reference_promotion.py
uv run pytest tests/integration/test_hotpoint_reference_promotion.py
uv run pytest tests/integration/test_promotion_publication.py tests/integration/test_check_purchase.py
uv run pytest tests/integration/test_eligibility_api.py
uv run pytest
```

There is no configured mypy step in the current `backend/pyproject.toml`; **do not invent** a type-check command. No migration check is necessary because none is added, but the integration tests must run against the **migrated PostgreSQL** fixture. Docker must be available for Testcontainers.

If a check cannot run, record the exact command, blocker, alternative verification and outstanding risk. Never mark an unrun command as passed.

---

## Completion report

### Changed

List fixture, test-only construction, tests and evidence documentation. Summarise the exact **Wren-only** amount/dates and known delayed-opening limitation.

### Database and migrations

**None.** Note that the tests use existing tables and the migrated PostgreSQL fixture.

### API/MCP contracts

**None.** Existing HTTP endpoint exercised only.

### Tests and verification

List each new/updated test file, commands actually run and results. State clearly if PostgreSQL/Docker or full tests were not run.

### External configuration

**None.** No Hotpoint credentials or promotion import job required.

### Deviations

Explain any meaningful deviation from the source facts or this spec; never suppress conflicting official terms, schema limits or timing semantics.

### Remaining risks or follow-up

**Required known follow-up:** support claim submission windows with a **purchase-relative opening plus fixed absolute deadline** before publishing the Hotpoint reference as a generally accurate, production-visible promotion. The test-only fixed interval does not prove the 30-day wait for every historical purchase/evaluation pair. Actual warranty registration, receipts, purchase condition, claimant restrictions and Hotpoint's final claim decision remain outside the five-field request.
