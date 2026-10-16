# PR 31 — Test Coverage Audit & Defect-Detecting Regression Hardening

## Repository state

**Expected branch:**  
`pr31-test-coverage-audit-regression-hardening`

**Base branch:**  
`main`

**Dependencies:**

- PR 10–15 — eligibility evaluation, classification, claim windows, requirements and rewards.
- PR 17–19 — canonical purchase checking, REST API and promotion authoring/publication validation.
- PR 20–25 — Samsung, LG, Hisense, Hotpoint and Sony reference promotions.
- PR 26–30 — explainability, MCP tools, scripted ChatGPT integration and five-manufacturer acceptance suite.
- Existing Python 3.13 / `uv`, `pytest`, SQLAlchemy, Alembic, PostgreSQL Testcontainers, Ruff and GitHub Actions setup.
- At specification creation, PR #30 was the newest observed PR. Recheck numbering and the base branch before implementation.

### Read first

- `AGENTS.md`, any nearer scoped guidance, and `.codex/tasks/TEMPLATE.md`.
- `.codex/tasks/pr-17-check-purchase-eligibility-service.md`, `pr-18-eligibility-http-api.md`, `pr-19-promotion-authoring-validation-format.md` and the latest applicable MCP/acceptance specifications.
- `backend/pyproject.toml`, `backend/uv.lock`, `backend/README.md`, `backend/tests/conftest.py`, `.github/workflows/backend.yml`.
- `backend/tests/acceptance/cases.py`, `backend/tests/chatgpt/flow.py`, `backend/tests/integration/test_mvp_end_to_end_acceptance.py`.
- Directly relevant domain, application, repository, API and MCP code and tests listed below.

### Primary change area

Backend test quality, targeted regression tests, evidence-backed test coverage inventory and CI diagnostics. **This is not a broad refactor or a PR to maximise a line-coverage percentage.**

### Canonical implementation examples

- `backend/tests/unit/test_eligibility_rules.py`, `test_claim_windows.py`, `test_eligibility_result.py`, `test_purchase_check.py`.
- `backend/tests/integration/test_promotion_publication.py`, `test_check_purchase.py`, `test_eligibility_api.py`, `test_mcp_check_purchase.py`.
- `backend/tests/integration/test_mvp_end_to_end_acceptance.py` and `backend/tests/acceptance/cases.py`.
- `backend/tests/integration/test_postgres_migrations.py` and `backend/tests/conftest.py` for real database behaviour.

### Relevant symbols

- `CheckPurchaseRequest`, `check_purchase`, `_evaluate_candidate` in `app.application.purchase_check`.
- `match_promotion_candidates`, `IdentityResolver`, `SqlAlchemyPromotionRepository.find_promotion_candidates`, `load_check_purchase_candidates`, `purchase_check_snapshot`.
- `evaluate_eligibility_rules`, `classify_eligibility`, `evaluate_fixed_claim_window`, `evaluate_relative_claim_window`.
- `validate_definition`, `validate_promotion_for_publication`, `change_promotion_status`, source provenance validation.
- `PurchaseRequest`, `CheckResponse`, `eligibility_check`, `PurchaseMCPServer`, supporting MCP tools and `ScriptedConversation`.

### Expected change surface

- `backend/tests/**`: audit findings, targeted new tests and strengthening **existing** assertions; avoid duplicate equivalent tests.
- `backend/tests/COVERAGE_AUDIT.md`: durable coverage map, independently verified gaps, severity, known limitations, test IDs and disposition.
- `backend/pyproject.toml`, `backend/uv.lock`: minimal test-only coverage tooling, if justified and compatible with repository conventions.
- `.github/workflows/backend.yml`: collect branch coverage from the existing complete test run and publish a diagnostic artifact; preserve current PostgreSQL and Docker smoke tests.
- **Only if a high-priority test exposes a focused defect:** the smallest owning domain/application/persistence module needed to make the business invariant true, with that production change explicitly reported. Otherwise raise a separately scoped blocking fix; do not hide the failed test.

### Excluded areas

- New product features, UI/frontend code, authentication, promotion discovery, source scraping, live AI/model calls, manufacturer sign-in and generic test frameworks.
- Unrelated refactoring, schema or API/MCP changes to improve coverage numbers.
- Synthetic rules that misrepresent manufacturer terms, stale/generic test snapshots and live manufacturer sites in CI.

### Unknowns Codex must verify

1. The precise base commit, latest PR number, changed files and actual test collection before editing.
2. Actual branch/line coverage and currently unexercised failure paths; **do not invent percentages**.
3. Whether tests currently cover each claimed behaviour through a real application boundary or only a pure-function test, fixture self-check, fake repository or scripted conversation.
4. Which published reference rules are fully representable and verified; distinguish recorded limitations from valid production behaviour.
5. Whether the runtime can express combined fixed claim dates and per-purchase minimum waiting periods; current evidence indicates it cannot for the reviewed Hotpoint/Sony slices.
6. Current Python test tools and their compatible versions, Docker availability and how CI stores artifacts.
7. Whether a purported gap is already exercised by an existing parametrised test; extend existing coverage rather than duplicating it.

---

## Objective

Deliver an evidence-based review of the backend's test coverage and a **small, prioritised set of regression tests** that catch realistic defects affecting whether a customer is told about a claimable benefit, its amount, timing, eligibility explanation and source.

Completion requires:

1. A reproducible mapping from important business invariants and failure modes to production functions, existing tests, uncovered paths, risk and independently established expectations.
2. Targeted tests for the highest-risk *verified* gaps, using explicit expected classifications, reason codes, dates, amounts, source identities, response errors and database state—not merely “the endpoint returned 200” or “REST equals MCP”.
3. Demonstration that the tests actually fail when a handful of realistic defects are introduced in an **isolated, temporary** validation run, and pass on the corrected implementation.
4. A coverage report for diagnostic purposes, **not** a vanity global threshold.
5. Honest treatment of product limitations. In particular, no certification of premature claim eligibility on the Hotpoint/Sony cases.

**Do not claim an audit found no defects merely because all existing tests pass.** Distinguish test gaps, product bugs, unsupported features and unverifiable business rules.

---

## Architecture and invariants

Preserve all existing architectural boundaries:

- REST and MCP both call the canonical application purchase-check operation; neither calculates eligibility independently.
- Domain eligibility remains deterministic from validated purchase input, published promotion data and an explicit evaluation date.
- Candidate/unpublished data never leaks into authoritative runtime checks.
- PostgreSQL-specific integrity, isolation, transactions and lifecycle changes are verified against real PostgreSQL, not SQLite.
- Published sources, verification timestamps, rewards, claim requirements and historical promotion state remain preserved and explainable.
- Expected domain negatives (`NOT_ELIGIBLE`, `EXPIRED`, unresolved identity and no match) must remain distinct from invalid source data and infrastructure errors.
- Test expectations must not be derived solely from the same helper, production calculator, ORM projection or runtime output under test.

### Quality standard for every added test

Every new test must document, through its name/arrange/assertions or audit row:

- **Defect hypothesis:** what realistic regression would this catch?
- **Independent oracle:** where does the expected answer come from (pinned official terms, a separately authored calendar/GBP example, contract invariant or explicitly constructed database state)?
- **Observable assertion:** exact result and reasons plus meaningful side effects/no side effects where applicable.
- **Failure proof:** a fault or mutation that causes this test to fail for the intended reason.

Avoid mock-only service tests that reproduce mocked outputs, tautological assertions, blanket golden snapshots, asserts based on values just read from the result, test order dependencies, arbitrary sleeps and broad skips/xfails. Use shared fixtures for setup, not as the sole authority for assertions.

---

## API and contract changes

**None intended.** Strengthen testing of current contracts:

- REST `POST /api/v1/eligibility/check`: strict request validation, exact machine-readable outcomes, safe `application/problem+json` failures and request IDs.
- MCP `check_purchase`, `get_benefit`, `get_claim_requirements`, `get_promotion_source`: schema, structured content, stable safe error codes, scoping and read-only semantics.
- On equivalent inputs, REST and MCP must agree **and** separately satisfy the independent business oracle. Parity alone cannot certify correctness if both share a bug.
- No change to public input/output, error format, authorization or status semantics under this PR unless a specific exposed defect requires a separately reviewed fix.

---

## Domain and application behaviour

### Initial findings to investigate and verify

| Priority | Observation from current code/tests | Required audit action |
| --- | --- | --- |
| **P0: unsafe claim readiness** | [`test_mvp_unsupported_claim_delays_are_not_release_approved`](https://github.com/cyberrobot/post-purchase-benefits-checker/blob/main/backend/tests/integration/test_mvp_end_to_end_acceptance.py#L529-L577) explicitly observes `ELIGIBLE` while a 30-day Hotpoint or 35-day Sony post-purchase waiting period is unmodelled. | Prove the false-positive boundary through independent source-backed date expectations. It must be a release blocker until accurately represented or safely prevented from being presented as currently claimable. Do **not** redefine the incorrect output as a passing business oracle. |
| **P1: no test-effectiveness diagnostics** | [`backend/pyproject.toml`](https://github.com/cyberrobot/post-purchase-benefits-checker/blob/main/backend/pyproject.toml) and [CI](https://github.com/cyberrobot/post-purchase-benefits-checker/blob/main/.github/workflows/backend.yml) run pytest/Ruff but do not presently measure branch coverage or deliberate defect detection. | Establish factual coverage baseline and verify tests fail for meaningful mutations. No arbitrary global coverage target. |
| **P1: source rule fidelity** | [`cases.py`](https://github.com/cyberrobot/post-purchase-benefits-checker/blob/main/backend/tests/acceptance/cases.py) pins five narrow manufacturer cases; some assertions also compare fixtures to manifests. | For high-risk dates, retailer restrictions, rewards and claim delays, verify expected results against manually pinned, reviewed evidence rather than copying implementation or manifest transformations. |
| **P2: simulated AI boundary** | [`ScriptedConversation`](https://github.com/cyberrobot/post-purchase-benefits-checker/blob/main/backend/tests/chatgpt/flow.py#L1-L4) expressly is not a model client. | Keep deterministic MCP contract coverage; document that natural-language extraction/model response faithfulness is **not** verified by these offline tests. Do not falsely claim a live ChatGPT E2E guarantee. |
| **P2: end-to-end support boundaries** | Domain evaluators can model channel, condition and country restrictions, but the five-field `CheckPurchaseRequest` and current persisted purchase-check projection do not use all those fact types. | Map **domain-only** vs **runtime-supported** behaviour accurately; do not claim unimplemented fields or rules are covered end-to-end. Escalate when official promotion terms require unsupported restrictions. |

These are initial **code-review observations**, not measured coverage statistics. The implementation audit must corroborate or revise them from the latest code and tests.

### Required adversarial scenario inventory

Inspect existing assertions first. Fill only gaps that remain:

1. **Claim time, dates and precedence:** inclusive opening/deadline, day before/after, leap day, year boundary, purchase exactly on promotion first/last day, relative offsets, overflow, combination of restrictive conditions, expired historical promotion with a still-open claim period, and mismatched/no claim window. `NOT_ELIGIBLE` must outrank claim timing where a genuine rule fails; unknown information must never turn into a definitive negative or false positive.
2. **Retailer/product identity:** correct manufacturer but wrong product or retailer; case/Unicode model aliases; retailer groups versus individual retailers; deliberate alias collision remains ambiguous; SKU points at a different product/manufacturer; unlinked product never implies wildcard matching; several applicable variants remain distinct, consistently ordered and independently explained.
3. **Rewards and requirements:** GBP zero, missing vs explicitly supplied price, exact `Decimal` percentages, fixed and product-specific values, wrong-product reward map, reward without eligible product mapping, no fabricated amount for free gift/extended warranty, evidence requirements retained without being treated as optional when present.
4. **Publication/history:** review/extracted/archived states never appear as active offers; a valid expired published offer remains searchable; incomplete or tampered sources fail closed; concurrent/retried publication cannot approve a changed graph or create inconsistent state; independent source verification dates and official/claim URLs are retained. Inspect existing comprehensive publication tests before extending.
5. **Transport and failure safety:** malformed date/price/oversized arguments, unknown identity vs resolved no match, transient PostgreSQL failure, inconsistent published graph, cancellation/timeout/disconnect, safe errors with no partial result, read-only rollback, connection-pool cleanup, and no diagnostic secret leakage.

### Known Hotpoint/Sony product gap — mandatory handling

Use source-verified independently pinned expectations (not fixture comments alone):

- **Hotpoint:** a purchase on `2026-06-12`, evaluated `2026-06-13`, is still within its 30-day post-purchase waiting period; earliest individually allowed claim date shown in the current acceptance test is `2026-07-12`.
- **Sony:** a purchase on `2026-10-27`, evaluated `2026-11-04`, is still within its 35-day waiting period; earliest individually allowed date shown there is `2026-12-01`.

The existing fixed promotion-wide claim interval alone is insufficient to make either case claim-ready. Specify and execute a test that would reject a premature unqualified `ELIGIBLE` verdict; expected safe representation must be based on the actual supported contract and independently verified terms. If the current model cannot express the combined rules, **record an actionable P0 release blocker**. Either implement the smallest correctly designed rule/model fix under a separately approved scope, or leave the coverage work explicitly **not release-certified**. Never keep the defective verdict green by asserting it is correct, silently skipping it or adding an unconditional xfail.

### Risk-based coverage audit method

Create `backend/tests/COVERAGE_AUDIT.md` with columns:

`Invariant | Production path | Existing test IDs | Boundary exercised (unit / PostgreSQL / REST / MCP / scripted) | Oracle | Missing/weak assertion | Severity | Proposed/new test ID | Outcome | Issue/PR`.

Inventory all important production modules at least once, then prioritize findings by potential user harm, data corruption, exploitability and likelihood rather than by raw uncovered lines. For each candidate gap inspect relevant parametrisation and negative cases, run it, and verify whether the behaviour is actually missing. State genuine non-applicable paths. Capture measured before/after branch coverage when tooling works, without inventing numbers.

### Defect-detection evidence

Validate at least **five distinct high-value, realistic** faults in an isolated copy/worktree or controlled temporary monkeypatch; **never commit mutation edits**:

- Changing an inclusive claim-opening or deadline comparison to exclusive.
- Collapsing unknown or not-yet-open into `ELIGIBLE` (or confusing unknown and ineligible).
- Removing retailer **or** product restriction from candidate matching.
- Admitting a non-published promotion into a runtime result.
- Accepting missing/invalid primary/claim provenance at publication or returning it as a successful purchase result.
- Other equivalent P0/P1 defects proven by the actual audit may substitute, with justification.

For each, record the mutation, expected kill test ID, actual failing assertion and whether it failed **for the intended reason**. A test that merely crashes during setup, fails due to the mutation harness or only notices a changed mock call does not count. All selected tests must pass without the mutation. Do not require an expensive global mutation-testing service or create persistent artificial mutation switches.

---

## Persistence, transactions, and migrations

**No schema change expected.** Current Alembic revisions and SQLAlchemy mappings are unchanged by the audit.

- Preserve existing PostgreSQL Testcontainers and migration tests; validate real constraints and locks only when the audit reveals a distinct weak assertion or material missing case.
- Use committed/rolled-back session fixtures deliberately; no test should rely on order or pre-existing data.
- For concurrency and cancellation cases, assert database/connection state and exact failure semantics, not only the occurrence of an exception.
- If correcting a revealed business defect requires a migration, stop the testing-only scope and document the blocking fix and its migration/test requirements separately; do not sneak a migration into this PR.

---

## External services and network access

**No new runtime external service.** Normal tests stay offline and deterministic:

- Reuse pinned reviewed official-term evidence already in the repository for test expectations; when it is insufficient, describe the evidence gap instead of inventing promotion rules.
- Do not issue requests to live manufacturer sites, use real AI tokens, or require a ChatGPT account in unit/integration CI.
- Maintain the scripted natural-language/MCP test boundary, clearly labelled as *scripted*, not a proof of real model interpretation.
- Test external failure behaviour only for boundaries actually implemented in the codebase.

---

## Security and privacy

- Exercise strict input rejection and error-shape boundaries for REST/MCP where gaps exist.
- Confirm runtime checks cannot fetch unpublished data or return evidence from an unrelated variant in supporting tools.
- Ensure failure messages/logs/coverage artifacts contain no credentials, SQL connection strings, complete purchase payloads or secrets.
- Do not weaken local-only MCP restrictions, cancellation controls or current source provenance gates to make tests pass.
- A security test must demonstrate the denied action, not just mock a guard as already denying it.

---

## Configuration and deployment

### Environment variables

**None expected.** Coverage and mutation checks must not require production configuration or new secrets.

### Runtime/deployment changes

- Add only compatible development coverage tooling (e.g. `pytest-cov`) if not already installed; update `backend/uv.lock` consistently.
- Update the existing `Backend` GitHub Actions workflow to generate **branch** coverage from its existing `uv run pytest` suite, with a human-readable missing-branches summary and a downloadable coverage artifact if supported.
- Do not add a second expensive full pytest run in the same CI job merely to produce coverage, and do not remove the current Docker image/migration/health smoke test.
- Treat coverage as a diagnostic baseline. Do not introduce a high universal coverage threshold that rewards trivial tests or forces out-of-scope refactoring. Target business assertions and mutation evidence are the acceptance gate.

---

## Observability and operations

- Tests report explicit scenario labels, business classifications, reason codes and safe IDs; no sensitive full-payload logging.
- Coverage artifacts are useful for pinpointing unexercised branches but are not presented as proof of behavioural correctness.
- The audit report clearly separates **passing**, **failing due to confirmed defect**, **unsupported/blocked**, **not yet tested** and **not applicable**.
- CI failure output must identify the responsible targeted test and expected outcome; avoid obscuring business failures behind bulk snapshots or excessive fixtures.

---

## Failure, consistency, and recovery

- A new regression test that exposes a real fault must first fail reproducibly, then pass only after the underlying fault is resolved. Preserve the test.
- If a necessary fix crosses scope (new claim-rule representation, data migration, manufacturer evidence), produce a separate blocking issue/PR with reproduction and release implications; do **not** record a clean certification.
- Ensure deliberate mutation trials cannot affect the checked-out branch, the normal test database, CI state or official fixture files after their run. Verify restoration.
- Preserve current rollback, connection and snapshot guarantees under expected database exceptions and MCP cancellations.
- Do not disable, skip or weaken failed existing tests to hide regressions.

---

## Acceptance criteria

### Behaviour

- [ ] The audit enumerates the critical purchase-check, eligibility, publication, provenance, historical, REST and MCP invariants, citing actual production paths and test IDs.
- [ ] Each proposed gap is confirmed against the real existing test suite; no duplicated assertions are counted as progress.
- [ ] New or strengthened high-priority tests use independent fixed expected values and assert classification **and** relevant reasons, windows, reward, evidence and side effects.
- [ ] Hotpoint/Sony premature-eligibility cases are independently documented and demonstrably detected; they are **not** certified as safe while the backend still incorrectly reports claim readiness.
- [ ] Actual runtime support boundaries are accurately documented (including unsupported channel/condition/country restrictions where verified).
- [ ] REST/MCP parity checks are paired with meaningful independent business assertions.

### Data and consistency

- [ ] Historical and unpublished promotion paths retain correct visibility; integrity failures never become successful results.
- [ ] Real PostgreSQL checks exercise any newly identified persistence failure, not SQLite or only mocks.
- [ ] Retried/failed/cancelled operations are proven read-only or rolled back as appropriate, without connection leakage.
- [ ] Pinned evidence and expected business facts are reviewed independently of fixture construction and runtime projections.

### Security

- [ ] Strict invalid input, safe failure responses and relevant association-scoping paths are audited; any newly uncovered high-risk path has a meaningful negative test.
- [ ] No live source/model dependencies or secrets are introduced into ordinary CI.

### Operations

- [ ] CI produces a reproducible branch-coverage report; baseline and relevant unexercised paths are recorded without an arbitrary global threshold.
- [ ] At least five different high-value, isolated realistic faults are demonstrably killed by appropriate tests and the unmodified suite passes.
- [ ] Known product defects and unsupported scenarios remain visible as explicit blockers, not hidden by expected-failure markers.

### Code quality

- [ ] Existing architecture and public REST/MCP schemas remain unchanged unless a focused defect fix is separately justified.
- [ ] Test fixture/data setup is deterministic, independent and cleaned up; assertions do not merely compare a value against itself or mirror the production algorithm.
- [ ] Ruff, targeted pytest, complete pytest and existing CI Docker smoke checks pass for any branch claimed complete; any inability to run checks is disclosed.
- [ ] The completion report distinguishes coverage measurement from test-effectiveness evidence and actual runtime/business guarantees.

---

## Tests to add or update

**Do not create every suggested file unconditionally.** Inspect existing coverage, extend the nearest established suite, and add a file only when it provides a clear separation of purpose.

### Unit tests

- `backend/tests/unit/test_claim_windows.py` and `test_eligibility_result.py`: strengthen independent date/precedence oracle where genuinely absent; require a boundary mutation to fail.
- `backend/tests/unit/test_purchase_check.py`: verify coupled eligibility/reward/provenance semantics and unknown versus failure outcomes without deriving expectations from the returned result.
- `backend/tests/unit/test_eligibility_rules.py` and `test_product_retailer_matching.py`: check any demonstrated unsupported/ambiguous identity, missing-fact and restrictive-rule regressions not already parametrised.
- Optional `backend/tests/unit/test_regression_oracles.py`: only for distinct, independently authored short business examples otherwise awkward to place.

### PostgreSQL integration tests

- `backend/tests/integration/test_promotion_candidate_matching.py`: live product/retailer scoping, ambiguous identity and nonpublished filtering, if not already defended by sufficiently specific tests.
- `backend/tests/integration/test_check_purchase.py`, `test_promotion_publication.py`, `test_promotion_source_provenance.py`: cross-table invariant, changed graph, snapshot and fail-closed behaviour for verified gaps only.
- `backend/tests/integration/test_mvp_end_to_end_acceptance.py`: independently pinned five-manufacturer claim-opening, purchase-boundary, reward, historical and retailer-restricted results. **Replace inappropriate acceptance of known unsafe early-claim behaviour with a demonstrable blocker/regression.**
- `backend/tests/integration/test_postgres_migrations.py`: only if a real untested migration/constraint regression is identified; no new migration is expected.

### API/application tests

- `backend/tests/integration/test_eligibility_api.py`: independent business oracles in addition to complete-response checking, plus targeted malformed/corrupt data failure paths where missing.
- `backend/tests/unit/test_eligibility_api.py`: preserve problem-detail contract and no unsafe disclosure; avoid duplicate exhaustive validation matrices already in acceptance tests.

### MCP contract tests

- `backend/tests/integration/test_mcp_check_purchase.py` and `test_mcp_supporting_tools.py`: ensure correct scoped structured responses and errors through real protocol and PostgreSQL; test exact expected claim facts independently of REST where missing.
- `backend/tests/integration/test_chatgpt_mcp_flow.py` and `backend/tests/chatgpt/flow.py`: retain deterministic scripted tool calls and grounding; clearly identify the limit: **not a live LLM natural-language test**. Add no fictitious model-success claims.

### External-boundary tests

**N/A for new integrations.** Existing tests must continue blocking unexpected outbound model/manufacturer traffic. Review timeout/cancellation tests at implemented MCP and database boundaries only if the audit finds gaps.

### Test-effectiveness proof

Produce a concise appendix in `backend/tests/COVERAGE_AUDIT.md` with at least five isolated mutation trials: mutation description, expected test identifier, actual failure and cleanup evidence. Run only targeted affected tests for each mutation; a full mutant matrix is not required.

---

## Verification commands

Run from `backend/` after confirming repository commands and compatible coverage tooling:

```bash
# Dependency sync (also updates tool installation from the committed lock)
uv sync --locked --extra dev

# Formatting / linting
uv run ruff format --check .
uv run ruff check .

# Focused suites; real PostgreSQL integration tests require Docker
uv run pytest tests/unit/test_claim_windows.py tests/unit/test_eligibility_result.py tests/unit/test_purchase_check.py
uv run pytest tests/integration/test_mvp_end_to_end_acceptance.py
uv run pytest tests/integration/test_promotion_publication.py tests/integration/test_check_purchase.py
uv run pytest tests/integration/test_eligibility_api.py tests/integration/test_mcp_check_purchase.py tests/integration/test_mcp_supporting_tools.py

# Whole backend suite and branch coverage (when compatible coverage tooling is added)
uv run pytest --cov=app --cov-branch --cov-report=term-missing --cov-report=xml:coverage.xml

# Migration integration tests (already part of the full suite)
uv run pytest tests/integration/test_postgres_migrations.py
```

- The repository currently has no configured mypy/typecheck command in `backend/pyproject.toml` or CI; report typecheck as **N/A, not run**, unless the base branch gains a supported command. Do not invent one.
- For mutation-effectiveness checks, document each temporary change and run its focused pytest ID; verify the test fails for the intended business reason and passes after restoring the change.
- Verify the existing `.github/workflows/backend.yml` image build, Alembic upgrade and live `/health` smoke test via CI when possible; do not state this passed locally if it did not run.
- If verification is blocked, report the exact command, blocker, alternate evidence and residual risk. Never claim an unrun command passed.

---

## Completion report

### Changed

Summarise the verified gaps, strengthened existing tests, new focused test files, audit documentation and any justified minimal production fix.

### Database and migrations

`None` unless a separately approved defect correction changes persistence; then explicitly list what changed and why it was unavoidable.

### API/MCP contracts

`None` expected. List any deliberately changed external behaviour explicitly.

### Tests and verification

Report:

- Total collected unit/integration tests (measured, not guessed), audited business areas and before/after branch coverage.
- Each new/changed test ID, its independent oracle and the exact defect it detects.
- At least five defect/mutation attempts, their focused fail/pass results and confirmation all temporary mutations were restored.
- Actual commands run, results, CI/Docker availability and failures.

### External configuration

`None` expected.

### Deviations

Describe any spec requirement not completed, changed scope, or feature fix deferred. `None` only when fully satisfied.

### Remaining risks or follow-up

Report P0/P1 bugs and unsupported source terms (especially any premature claim-ready response), what remains unverified by offline scripted AI tests, and the issue/PR blocking production release. `None` only if verified and resolved.
