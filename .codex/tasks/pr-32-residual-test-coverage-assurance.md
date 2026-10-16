# PR 32 — Residual Test Coverage & Defect-Detection Assurance

## Repository state

**Expected branch:**  
`pr32-residual-test-coverage-assurance`

**Base branch:**  
`main` (reconfirm the latest main commit before implementation)

**Dependencies:**

- PR #30 — Five-manufacturer MVP acceptance suite.
- PR #31 — Test coverage audit, minimum-wait claim-window correction, migration `0008_fixed_claim_min_wait`, and branch-coverage diagnostics. **PR #31 was merged on 16 October 2026.**
- Existing Python 3.13, `uv`, pytest, pytest-cov, Ruff, SQLAlchemy, Alembic, PostgreSQL/Testcontainers, FastAPI and MCP infrastructure.
- No new migration, production feature, or live model/manufacturer integration is authorised by this specification.
- **Review governance prerequisite:** PR #31's audit still describes its expanded production/migration scope as awaiting formal maintainer approval. Record a clear approval or outstanding decision separately; a merge alone is not evidence that this explicit scope-decision requirement was documented.

### Read first

- Root and nearest scoped `AGENTS.md`, `.codex/tasks/TEMPLATE.md`.
- `.codex/tasks/pr-31-test-coverage-audit-regression-hardening.md` and `backend/tests/COVERAGE_AUDIT.md`. **Do not repeat the PR #31 audit as new work.**
- `.codex/tasks/pr-30-mvp-end-to-end-acceptance-suite.md` if present; otherwise the actual PR #30 diff and current acceptance tests.
- `backend/tests/fixtures/promotions/README.md` and the five pinned manufacturer manifests with their reviewed clause maps.
- `backend/tests/acceptance/cases.py`, `backend/tests/unit/test_mvp_acceptance_cases.py`, `backend/tests/integration/test_mvp_end_to_end_acceptance.py`.
- `backend/app/application/purchase_check.py`, `purchase_check_details.py`, `promotion_authoring.py`, `promotions.py`.
- `backend/app/domain/eligibility_rules.py`, `claim_windows.py`, `promotion_validation.py`.
- `backend/app/db/repositories/promotions.py`, `backend/migrations/versions/0008_fixed_claim_min_wait.py`.
- `.github/workflows/backend.yml`, `backend/pyproject.toml`, and the most relevant existing API/MCP and PostgreSQL tests.

### Primary change area

An **evidence-based, narrowly targeted follow-up to PR #31**: investigate residual high-risk false-positive/false-negative eligibility paths, independently verify existing test oracles, and add only regression tests demonstrated to catch realistic defects. Explicitly separate uncovered tests from unsupported production capabilities, unverified third-party facts, and deployment/data migration risks.

### Canonical implementation examples

- `backend/tests/COVERAGE_AUDIT.md` — existing inventory, prior mutation results, measured coverage and known limitations.
- `backend/tests/integration/test_mvp_end_to_end_acceptance.py` — real PostgreSQL-backed canonical check, REST and MCP journeys.
- `backend/tests/integration/test_check_purchase.py`, `test_eligibility_api.py`, `test_mcp_check_purchase.py` — independent contract and snapshot tests.
- `backend/tests/integration/test_promotion_publication.py`, `test_postgres_migrations.py` — publication, database invariants and migration safety.
- `backend/tests/unit/test_claim_windows.py`, `test_purchase_check.py`, `test_eligibility_rules.py`, `test_promotion_validation.py` — pure/business and application tests.

### Relevant symbols

`CheckPurchaseRequest`, `check_purchase`, `_evaluate_candidate`, `PurchaseEligibilityFacts`, `PromotionEligibilityRules`, `PurchasePriceRule`, `PurchaseChannelRule`, `ConditionRule`, `CountryRule` (confirm current symbol names), `FixedClaimWindow`, `evaluate_fixed_claim_window`, `classify_eligibility`, `validate_definition`, `validate_promotion_for_publication`, `SqlAlchemyPromotionRepository.load_check_purchase_candidates`, `_check_details`, `purchase_check_snapshot`, REST `POST /api/v1/eligibility/check`, MCP `check_purchase` and supporting tools.

### Expected change surface

- `backend/tests/COVERAGE_AUDIT.md` — **append a dated PR32 follow-up** with identified/ruled-out gaps, not a rewrite of PR31 evidence.
- A small number of **existing** test modules under `backend/tests/unit/` and `backend/tests/integration/`, extended only after checking equivalent parametrised coverage.
- Optionally a small test-only, independently authored oracle file under `backend/tests/acceptance/` if inline constants would otherwise become unclear. Do not create a new test framework.
- An optional, short `backend/tests/RELEASE_ASSURANCE_GAPS.md` **only if** a stand-alone release-blocker inventory is materially clearer than extending the existing audit.
- Documentation clarifications limited to proving the precise boundary between *configured rule matches* and *verified manufacturer claim entitlement*.

### Excluded areas

- Adding missing runtime eligibility fields/rules, changing `ELIGIBLE` semantics, changing public REST/MCP schemas, scraping or signing into manufacturer sites, live LLM evaluations, AI extraction/ingestion, authentication, UI work, and unrelated refactors.
- Production database migrations, automatic backfilling, source-content crawling, runtime policy engines, or new deployment mechanisms.
- Blanket line/branch coverage thresholds, testing for its own sake, duplicating PR31 mutants/cases, broad snapshots and tests whose expected values come from the production function being exercised.
- Quietly “fixing” a P0/P1 feature or data-integrity defect in this test-focused PR. **Report and scope a separate remediation PR instead**, unless the maintainer explicitly amends this specification before merging.

### Unknowns Codex must verify

1. Current default branch, latest PR number, actual test collection and CI results after PR31 merged. Reserve #32 only if still free.
2. Which residual branches in the post-PR31 full-suite coverage are genuinely risk-bearing. PR31 reported **2,414 passed; 571/620 branches = 92.0968%**. This is a historical measured result, **not** a fresh run or an automatic target.
3. Which alleged gaps are already covered by existing parametrised unit, PostgreSQL, REST or MCP tests. Treat PR31's seven proven mutant kills plus the subsequent wait-rule fault trial as *existing evidence*, not new PR32 kills.
4. Whether each reference's recorded manufacturer restrictions are implemented, only displayed as limitations, or absent from all validated structured inputs. Do not infer rules from a marketing summary.
5. Whether producer/consumer compatibility, publish-time validation and runtime data projection correctly preserve `claim_min_wait_days` in all supported deployment states.
6. Whether reliable, archived/pinned official-terms evidence sufficient for an independent assertion is actually available in the repo. A URL and an internal manifest are not immutable official-source bytes.
7. Whether generated coverage artifacts can be examined without adding a second expensive CI test run; do not claim missing branches solely from percentages.

---

## Objective

Produce a reproducible, evidence-backed assessment of **remaining meaningful test coverage gaps after PR31**, and implement a **small set of new or strengthened regressions only where a concrete, material failure mode is not already detected**.

For each finding, demonstrate: (1) the business impact of the potential defect; (2) the actual code boundary; (3) the current assertion or missing assertion; (4) an independently justified expected result; (5) a focused test that observes the result through the narrowest *credible* boundary; and (6) if practical, a temporary defect mutation that makes that test fail **for the intended reason**.

Where analysis shows missing *product functionality* rather than missing test coverage, record an explicit release limitation/blocker and a separate proposed implementation scope. **Do not make an unsupported positive eligibility claim pass by weakening a test, rewriting manufacturer facts, or documenting it as certified.**

Completion must not be defined as achieving a higher test count or a higher global coverage percentage. A defensible conclusion that a suspected gap is already covered is a valid audit outcome.

---

## Architecture and invariants

- Both REST and MCP call the same canonical deterministic application check. Their agreement **alone** does not establish correctness; both must also satisfy independent expected business facts.
- Only active/expired **published** promotion data can drive runtime results. Review/unverified candidate data must remain invisible.
- Source/provenance retention proves which evidence was recorded, **not** that all real manufacturer restrictions have been modelled.
- `ELIGIBLE` is a classification under the **configured** rules; it must never be tested or presented as proof that the manufacturer has approved a claim when price, condition, country, purchase channel, account, age, prior-claim or other restrictions remain unverified.
- `claim_min_wait_days` must survive authoring, publication, persistence, repository projection, canonical checking and both transports when the referenced promotion actually stores it. No old code path may silently omit an applicable wait.
- Calendar dates are inclusive at supported endpoints; independently pinned purchase-relative waits take precedence over a wider campaign opening. No live clock or external network is needed for tests.
- Missing/ambiguous facts must not silently become an unconditional eligible or ineligible verdict. Errors caused by corrupt published data must not yield partial successful offers.
- PostgreSQL-dependent constraints, migration, transaction and projection behaviour must be tested on real PostgreSQL, never a mock or SQLite substitute.
- Independent oracles use literal reviewed calendar/GBP values or evidence-clause references **not dynamically derived from the response or the same implementation helpers**.

---

## API and contract changes

**None.** Existing REST and MCP schemas and error contracts remain unchanged.

Contract assertions added under this PR must include exact status/classification, reason codes, opening/deadline, amount/currency where applicable, source/verification identity, and safe failure shape—not merely HTTP `200`, schema validation or REST/MCP parity.

If an analysis finding appears to require adding country, condition, purchase channel, purchase-price restriction or new eligibility status to the public contract, **do not implement it here**: document a separate design decision and the customer impact.

---

## Domain and application behaviour

### Risk-ranked investigations (validate before adding tests)

| Risk / priority | Basis in reviewed post-PR31 code | Test question and required outcome |
| --- | --- | --- |
| **P0 conditional — unmodelled exclusions represented as fully eligible** | `domain/eligibility_rules.py` supports condition, channel, country and purchase-price rules, while `CheckPurchaseRequest` and `_evaluate_candidate` currently build runtime checks from manufacturer/product/retailer/purchase date (with price used for reward calculations). Manufacturer fixtures document further age, residency, returns, prior-claim and marketplace restrictions. | For each reviewed official term, label it **enforced**, **informational requirement**, **unsupported** or **not established**. Identify cases where a published reference could be interpreted as unconditional claim entitlement. Record a blocker when a source-backed material exclusion cannot be evaluated; do not fake end-to-end coverage for unavailable inputs. |
| **P1 — existing terms can disagree with configured wait** | Migration 0008 retains existing nullable `promotions.claim_min_wait_days` values without backfilling; PR31 explicitly warns that legacy published source-backed waits may have been omitted. | Determine whether existing tests detect a source-reviewed wait that is absent/wrong in persisted published data. A historical NULL-preservation migration test is not proof of correct eligibility. Add a **test-data consistency oracle** where sufficient independent evidence exists; otherwise record a release data-audit requirement. Never invent a global manufacturer wait. |
| **P1 — write-to-read regression in wait projection** | `FixedClaimWindow.minimum_days_after_purchase` is carried via DB `claim_min_wait_days`, `_check_details`, `check_purchase` and transports. PR31 added domain/fixture/migration coverage. | Review exact post-PR31 tests for protection at the real PostgreSQL-to-REST/MCP boundary, particularly field loss or default-to-NULL. Add only a distinct missing end-to-end assertion, using an independent synthetic calendar, if not already covered. |
| **P1 — test oracle mirrors the fixture** | `test_mvp_acceptance_cases.py` compares CASES to manifest; acceptance `offer()` obtains requirements/URLs/timestamps from manifest. Some date/amount constants are independently written. | Distinguish **projection fidelity** (fixture → result) from **business-rule fidelity** (official terms → expected outcome). Add a compact documented evidence-to-test mapping for the five narrow references; strengthen only business-significant assertions currently relying on the source under test. |
| **P1 — incorrect product or reward at the database boundary** | Candidate matching uses an actual `PromotionVariantProduct.product_id` filter, and application reward assembly uses the canonical identity; PR31 proved a retailer-filter mutation, not a distinct product-filter mutation. | Check whether removing the product join filter, or changing the per-product reward mapping, is caught by a truly independent PostgreSQL/REST oracle; if already caught, record evidence instead of adding a duplicate. |
| **P2 — misleading test claim about AI** | Scripted ChatGPT journeys call deterministic MCP tools but do not run a live model. | Keep the scripted claim-grounding coverage; report natural-language extraction and model prose faithfulness as **unverified**. Do not convert this into live-model CI work. |

### Required audit method

1. Extract actual measured full-suite branch/line coverage once after PR31, if the environment permits, and compare **relevant branch locations** against the PR31 report. Do not infer semantic gaps from the number of uncovered lines.
2. Read existing tests **before writing any new cases**; identify an observable fault that survives existing tests.
3. Create a dated **PR32 findings section** in `backend/tests/COVERAGE_AUDIT.md`. Required columns:

   `ID | Invariant/source clause | Customer failure/impact | Owning code | Existing test ID and boundary | Evidence/oracle | Gap category | Severity | New or strengthened test ID | Defect proof | Disposition/blocker`.

4. Classify every finding as: **missing meaningful test**, **adequately tested**, **unsupported product capability**, **unverified manufacturer/source fact**, **migration/deployment risk**, or **not applicable**.
5. Rank by incorrect customer advice, lost/incorrect cashback, failure to claim before a deadline, unsafe publication, data corruption and exploitable error/resource boundaries. Ignore easy-to-cover lines without material risk.
6. Confirm at least one independent expectation for each newly asserted business rule. Preserve exact source-clause attribution and what the evidence **does not** establish.
7. Implement no more than **3–5 distinct, highest-value scenarios** unless new findings justify a separately approved expansion. Existing parametrisation should be extended rather than cloned.
8. For each new scenario, record the defect hypothesis, independent oracle, exact observable assertion, applicable boundary, test ID and proof of sensitivity. If no genuinely new gaps are found, document that conclusion with inspection evidence; **do not add filler tests**.

### Focused scenario candidates (conditional, not an automatic test backlog)

**A. Persistence-to-consumer wait preservation.** If not already proven, construct a small independent, synthetic published promotion with fixed campaign bounds `2027-01-01..2027-03-31`, a `14`-calendar-day post-purchase wait, and purchase `2027-01-10`. Assert `CLAIM_NOT_YET_OPEN` and `opens_on=2027-01-24` on `2027-01-23`; `ELIGIBLE` on `2027-01-24`; and expiration after `2027-03-31`. Repeat the relevant result through canonical application, REST and MCP on the **same real persisted graph**. The test must detect losing or zeroing the persisted wait in `_check_details` even when domain-only tests remain green. Use a test-only reviewed/synthetic fixture, not a fictional manufacturer's official promotion.

**B. Evidence-versus-configured rule mismatch.** Where a fixture has a separately reviewed and explicitly identified waiting-period clause, test that the authored and persisted canonical promotion rule retains the pinned value. A test that only compares two fields inside the same mutable fixture is insufficient. For any published legacy row whose recorded source requires a nonzero wait but the structured rule is NULL, flag a **release data-integrity defect**: an unqualified runtime `ELIGIBLE` cannot be certified simply because code handles NULL as an absent optional wait. Do not silently backfill unknown data or add a runtime source-parser in PR32.

**C. Product and variant scoping.** After checking existing negative tests, use a real PostgreSQL graph with two different products/variants and a separately authored literal expected offer count/identity. Assert no cross-product/variant leakage through the canonical operation and at least one transport. Add only if existing coverage does not already fail when the product filter is removed.

**D. Material unrepresentable restriction.** For one reviewed source-backed example (e.g., source terms requiring a new/unused product or purchase from a specific channel), document a paired case showing that the pure domain rule rejects/marks unknown appropriately **but the five-field transport cannot supply/enforce it**. This is an **evidence-backed gap demonstration**, not a passing end-to-end test claiming runtime enforcement. File a separate feature/release-blocker scope if such a rule is necessary before trustworthy customer-facing eligibility advice.

**E. Error and source integrity.** Only if inspection reveals a distinct missing path, verify that a specifically tampered published graph or cross-promotion association produces no partial successful offer and an exact safe problem/MCP error, with DB/session cleanup. Do not repeat the provenance/connection-cleanup suites from PR31 without a new adversarial case.

### Defect-detection proof

For **each new or strengthened high-priority test**, run an isolated one-line/one-site realistic fault or controlled fixture corruption against its relevant target; record the failed assertion and restored passing result. Aim to demonstrate **at least three distinct high-value post-PR31 risk hypotheses** across candidate tests and existing tests, but **do not fabricate tests or mutation kills** to meet a number. Explicitly mark a hypothesis already detected by the old suite as *no new test needed*.

Prioritise new faults that PR31 did not already test, such as:

- Dropping or replacing persisted `claim_min_wait_days` during SQLAlchemy projection (distinct from altering the pure calendar evaluator).
- Removing the **product** restriction in candidate SQL (PR31 already mutated the retailer filter).
- Mapping a product-specific benefit to the wrong resolved product or return value through the real persisted graph.

Mutations must occur only in an isolated temporary checkout or disposable controlled fixture, never in committed source. Setup failures, mocks failing for their own configuration and infrastructure failures do **not** count as mutation kills. Restore the source and demonstrate the original targeted tests pass. If a mutation is already detected by an existing test, say so and do not add a redundant one.

### Decision rules for discovered defects

- **Test gap with correct behaviour:** add the smallest meaningful regression.
- **Genuine P0/P1 production defect:** retain independent failing evidence; document a blocking remediation issue/spec and its owning layer. Do not suppress, xfail, alter expected manufacturer facts, or expand this PR into a feature/migration without explicit amendment.
- **Unsupported source requirement:** mark the reference or specific eligibility conclusion **not release-certified** where it matters; identify the missing input/rule contract and a separate implementation plan.
- **Unverifiable evidence:** record the clause/source-verification gap; do not claim official-term correctness.
- **Already tested:** link the exact test ID and fault-detection evidence; no duplicate test.

---

## Persistence, transactions, and migrations

**No schema or migration changes.** `0008_fixed_claim_min_wait` is already present; do not modify it in this PR.

Use the existing Testcontainers fixture and migrated PostgreSQL schema for any persisted rule and projection cases. Validate in one transaction/snapshot where appropriate; the test database must be isolated and fully cleaned up. Assert database state or non-mutation where the business property requires it.

The migration's NULL default and unsafe downgrade refusal are already exercised. Do **not** repeat those assertions as if they prove migration rollout safety or retroactively reconstruct omitted official-term waits. Flag any mixed-version deployment or published legacy data remediation as an operational release prerequisite beyond the test-only scope.

---

## External services and network access

**No new services or outbound requests.** Use recorded manufacturer evidence and offline fixtures. If independent official bytes/clauses are unavailable, identify that limitation and the manual review needed; do not silently substitute an assertion copied from the application output.

Normal pytest/CI must make no live manufacturer request, no login attempt, and no real LLM call. The existing simulated MCP conversation harness remains an **offline scripted consumer**, not live ChatGPT assurance.

---

## Security and privacy

- Preserve existing input bounds, local MCP protections, safe structured error contracts and publication/source gates.
- Any error-path test must verify no SQL details, passwords, local absolute paths, raw source payloads or sensitive purchase contents leak through HTTP/MCP responses or logs.
- Test candidate/review publication boundaries using real data, not a mocked guard that was configured to reject.
- Do not introduce secrets, consumer details or complete manufacturer terms into coverage artifacts.
- Avoid production writes to third-party accounts/services.

---

## Configuration and deployment

### Environment variables

**None.** No new secrets, CI external credentials, manufacturer accounts or toggles.

### Runtime/deployment changes

**None.** Keep the current CI single full-suite pytest run with branch coverage and coverage artifact from PR31. Avoid new global fail-under thresholds, another parallel full-suite run, expensive blanket mutation-testing services or altered Docker smoke behaviour.

**Release precondition, not an implementation in PR32:** separately confirm the post-0008 rollout order and audit any already-published source-backed waiting periods that were omitted. Old application versions that ignore the wait are unsafe for newly wait-bearing data.

---

## Observability and operations

- Preserve the existing `check_purchase_completed` and structured failure categories; do not add noisy telemetry just to count tests.
- The updated coverage audit must distinguish *verified passed*, *currently failing*, *could not run*, *source not reviewed*, and *unsupported business behaviour*.
- Preserve accurate CI provenance: local results are not the same as CI results, and previous PR31 branch percentages are not current PR32 measurements.
- For release-blocking issues, record the precise affected promotion/condition, example purchase/evaluation inputs, incorrect observable result, source evidence and explicit release impact, without storing customer PII.

---

## Failure, consistency, and recovery

- On corrupt published state, the canonical check must not return a partly successful promotion list. Test this only for a newly identified material path; existing broad corrupted-source cases already exist.
- On test interruption/failure, rollback disposable PostgreSQL changes and restore every mutation. No shared state, order dependence, persistent test-runner changes or arbitrary sleeps.
- A test dependent on missing official evidence is **not green by default**; classify it as blocked/unverified and describe what evidence is required.
- A feature gap that permits misleading customer advice must remain visible as a separate product-release decision; do not hide it under "unit-tested" status.
- No changes to retry/concurrency semantics are part of this task.

---

## Acceptance criteria

### Behaviour

- [ ] A dated PR32 audit inventories **post-PR31 residual risks**, not a relabelled copy of PR31's coverage analysis.
- [ ] Every new or strengthened test states a realistic customer-facing defect, independent expected result, exact assertion, and the boundary it exercises.
- [ ] Cases are first checked against all existing parametrised tests to avoid duplication.
- [ ] The combined fixed campaign/minimum-wait invariant is protected across persistence and consumers **if that specific end-to-end hole is proven to exist**; otherwise the existing test IDs are recorded.
- [ ] Product, retailer, variant, source and reward scope are checked for newly found cross-boundary risks only; no blanket matrix is added.
- [ ] No customer-facing result is asserted fully claim-approved solely because the service's subset of configured rules matched.

### Data and consistency

- [ ] Official-source assertions are classified as independent evidence, manifest consistency, or projection checks; those evidence levels are not conflated.
- [ ] Every identified legacy nullable-wait or unsupported restriction risk receives a disposition and release impact.
- [ ] All new DB-dependent assertions use real migrated PostgreSQL and leave no persistent rows/transactions behind.
- [ ] No schema, backfill or public API change is introduced under this test-only scope.

### Security

- [ ] Publication invisibility, malformed data and safe error handling remain intact.
- [ ] No secrets, tokens or private data enter fixtures, logs or CI reports.
- [ ] Any new denial test exercises a real boundary, not a preprogrammed mock denial.

### Operations

- [ ] Historical PR31 coverage measurements are distinguished from current PR32 run results.
- [ ] The existing branch-coverage CI workflow stays intact; no arbitrary global percentage gate is added.
- [ ] Any P0/P1 defect is reported with reproducible evidence and remains visible until separately resolved/approved.

### Code quality

- [ ] Only a small number of distinct high-value tests is added, or the audit justifies why none was needed.
- [ ] New tests catch their stated defect in a controlled fault trial, where practical; failures are not merely setup failures.
- [ ] Temporary mutation edits are fully restored.
- [ ] Ruff, focused tests, full backend suite and relevant real PostgreSQL integration tests pass unless an explicitly reported production blocker prevents this.
- [ ] No tests are skipped, xfailed, relaxed or rewritten just to make results green.

---

## Tests to add or update

### Unit tests

**Conditional based on confirmed gaps**, not a mandatory new-test count:

- `backend/tests/unit/test_mvp_acceptance_cases.py` — strengthen independent evidence/oracle assertions where existing comparisons are solely against the mutable manifest, with narrowly pinned facts and clause attribution.
- `backend/tests/unit/test_claim_windows.py` and `test_purchase_check.py` — extend existing date and classification assertions only if a distinct untested minimum-wait/campaign precedence path is verified.
- `backend/tests/unit/test_promotion_validation.py` — add only an uncovered supported-rule publication failure; unsupported source restrictions must not be portrayed as implemented enforcement.

### PostgreSQL integration tests

- `backend/tests/integration/test_mvp_end_to_end_acceptance.py` **or** `test_check_purchase.py` — add a real persisted, synthetic non-manufacturer minimum-wait end-to-end example **only if not already covered**. Test exact `2027-01-23`/`2027-01-24` boundary, not-yet-open reason and window, later inclusive campaign deadline, and no partial/cross-variant leakage.
- `backend/tests/integration/test_promotion_candidate_matching.py` — inspect the current product-scope tests and demonstrate whether they kill a removed product filter; extend only if the fault survives.
- `backend/tests/integration/test_postgres_migrations.py` — **normally no change**: PR31 already tests NULL preservation and safe downgrade. Do not duplicate a migration test to simulate evidence completeness.

### API/application tests

- When one new business invariant is added, assert exact corresponding classification/reason/amount/evidence at the application boundary and at least one external adapter; both REST/MCP where material and feasible.
- Existing REST problem-details checks remain authoritative for transport errors; do not create a new contract.

### MCP contract tests

- No schema changes. Where an end-to-end scenario truly adds a new invariant, verify MCP structured content reflects the independent expected result rather than just matching REST.
- Do not repeat already proven supporting-tool scoping/cancellation tests unless a distinct new cross-promotion fault is found.

### External-boundary tests

**N/A.** No live manufacturer or model calls. Document the absence of a live natural-language model evaluation as an assurance limit, not an automatically failing unit test.

---

## Verification commands

Run from `backend/`, after checking that the installed dependencies, Docker availability and current file names match the repository:

```bash
uv sync --locked --extra dev
uv run ruff check .
uv run ruff format --check .

# Focused risk areas; select the genuinely changed subsets first
uv run pytest tests/unit/test_mvp_acceptance_cases.py tests/unit/test_claim_windows.py tests/unit/test_purchase_check.py -q
uv run pytest tests/integration/test_mvp_end_to_end_acceptance.py tests/integration/test_check_purchase.py -q
uv run pytest tests/integration/test_promotion_candidate_matching.py tests/integration/test_promotion_publication.py -q
uv run pytest tests/integration/test_eligibility_api.py tests/integration/test_mcp_check_purchase.py -q

# Diagnostic branch coverage from a SINGLE complete suite
uv run pytest --cov=app --cov-branch --cov-report=term-missing --cov-report=xml:coverage.xml -q

# Migration regression only if migration interactions were touched
uv run pytest tests/integration/test_postgres_migrations.py -q
```

`backend/pyproject.toml` does not currently configure a mypy/typecheck command: report **N/A**, unless the checked branch adds one. PostgreSQL integration tests require Docker. For each mutation, run its **focused test ID** against an isolated temporary edit, then rerun after restoration; do not perform a full-suite run for every mutation.

Document for every unrun command: exact command, blocker, replacement evidence and remaining risk. Do not claim that any command in this specification has already run as part of PR32.

---

## Completion report

### Changed

Summarise the verified residual coverage gaps, audit classification/dispositions, independent-oracle improvements, and the exact added/extended test IDs. State how they differ from PR31 work.

### Database and migrations

**None expected.** If a defect requires persistence changes, report it as a separate blocking remediation scope; do not include an unapproved migration.

### API/MCP contracts

**None expected.** Any need for new purchase facts or rules must be documented as a separate feature/specification.

### Tests and verification

Include before/after observed test counts and branch coverage **only when measured**; test IDs, independent sources/expected values, targeted mutation descriptions, actual intended failures, restored passes, PostgreSQL/CI outcomes, and unrun checks. Explicitly distinguish *newly found defect*, *newly added test*, and *pre-existing test already able to catch it*.

### External configuration

**None expected.** Record any unresolved production data audit or deployment-compatibility prerequisite separately.

### Deviations

Any change to the test-only scope requires documented maintainer approval **before** merge. Do not assume PR31's merged but explicitly unapproved amendment creates blanket permission for future production changes.

### Remaining risks or follow-up

List unsupported manufacturer restrictions, missing source-verification evidence, legacy publication data with omitted waits, mixed-version rollout exposure, and the separate issue/PR for each material defect. If one is release-blocking, mark the relevant promotion/claim result **not release-certified** until resolved. Only write `None` when this is genuinely supported by review evidence.
