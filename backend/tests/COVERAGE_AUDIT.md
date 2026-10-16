# PR31 coverage and defect-detection audit

Audit date: 2026-10-15. The initial audit exposed two P0 claim-readiness failures.
The subsequent request to fix CI adds the structured minimum-wait rule, migration
and regression coverage described below. Maintainer scope approval remains
**pending**. Verification covers only the
represented waiting-period rule and campaign bounds; it does not certify full
manufacturer eligibility or production publication approval. Legacy omitted waits
require verified remediation.

## Reproducibility and scope

The implementation branch is `pr31-test-coverage-audit-regression-hardening`.
Its starting commit is `a2bbc4b` (merge of PR30 into the branch created from main).
The necessary PR30 acceptance suite was absent on main alone; the merge is an explicit
prerequisite adjustment, not a test-only diff. The implementation does not claim PR30
production changes as new coverage work. The original specification remains the
scope baseline. Its appended proposed
amendment requires maintainer approval; the request to fix CI did not establish
that approval.

The dev extra and lock now include pytest-cov 7.1.0 and coverage 7.16.2; those versions
were present in the Python 3.13.16 test environment. `uv lock --check --offline` passed.
`uv sync --locked --extra dev` passed during the CI correction. Initial collection
found **2387 tests**: 1686 unit, 701 integration. The initial audit
strengthened existing assertions; the CI correction adds focused wait-rule and
migration cases. Docker access required sandbox escalation locally.

Before changing test assertions, this command passed 1686 unit tests in 6.11s:

```sh
uv run pytest tests/unit --cov=app --cov-branch --cov-report=term-missing --cov-report=json:/private/tmp/pr31-before.json
```

This is a **unit-only baseline**, not whole-backend coverage: 2314/2550 statements
(90.7451%), 513/608 branches (84.375%), combined coverage 89.5187%.
The terminal's rounded 90% is combined coverage, not branch coverage.
95 branches were missing, including 54 in `db/repositories/promotions.py` because
unit tests do not replace PostgreSQL integration coverage. Other missing branches:
`purchase_check_details.py` 7, `promotion_authoring.py` 6, `promotions.py` 6,
`promotion_validation.py` 6, MCP server 4, promotion details 3, identity repository 2,
MCP schemas 2, and single branches in identity matching, API schemas, configuration,
DB engine and local access. Missing lines/branches are diagnostics, not automatically
verified business gaps. This unit-only baseline is retained as a focused diagnostic;
the comparable complete-suite baseline follows below.

For a comparable full-suite baseline, the unmodified PR30 tree was archived to
`/private/tmp/pr31-pr30-baseline` and run with the same Python 3.13.16 environment,
PostgreSQL Testcontainers, and coverage command. It passed **2387 tests** in 76.82s:
2474/2550 statements (97.0196%), 560/608 branches (92.1053%), and 96.0735% combined.
The initial PR31 audit run measured the same coverage counts and percentages while
exposing two failures. The corrected implementation's final measurements appear below.
Coverage percentages measure execution, not business correctness.

CI instruments its existing single complete pytest run with `--cov=app --cov-branch`,
`term-missing`, XML and HTML reports. `actions/upload-artifact` runs even on failure;
reports contain paths and execution counts, not captured requests or environment values.
The existing Docker build/migration/health smoke step remains present. No global
coverage threshold was added. Local Docker image smoke was deferred during the
initial audit; the later
correction-phase execution is recorded below.

## Invariant inventory

Paths are relative to `backend/app`; test IDs are relative to `backend/tests`.
A suite citation covers its existing parametrisation, not a new test claim.
“Existing” means assertions inspected; run evidence is listed below. It does not
mean every cited integration suite was executed during the focused audit.

| Invariant | Production path | Existing test IDs | Boundary exercised (unit / PostgreSQL / REST / MCP / scripted) | Oracle | Missing/weak assertion | Severity | Proposed/new test ID | Outcome | Issue/PR |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Inclusive opening/deadline, leap day, year boundary, offset overflow | domain/claim_windows.py | unit/test_claim_windows.py::test_inclusive_window_and_retained_dates; ::test_relative_calendar_arithmetic; ::test_relative_calendar_overflow | unit; PostgreSQL window suites | Explicit calendar constants, no production calculator for expected dates | Already covered; avoid duplicate cases | P1 | Existing tests retained | Passing; opening/deadline mutations killed | PR31 |
| Failed rules outrank unknown and timing; absent window uncertain | domain/eligibility_result.py; domain/eligibility_rules.py | unit/test_eligibility_result.py::test_every_rule_status_combination_and_claim_state; ::test_unspecified_window_preserves_failure_unknown_precedence; unit/test_purchase_check.py::test_absent_window_is_uncertain | unit/application fake port | Contract decision precedence and fixed enum values | Existing dense matrix, no missing combination established | P1 | Existing tests retained | Passing; unknown mutation killed | PR31 |
| Classification remains correct while preserving distinct verification times | application/purchase_check.py; application/purchase_check_details.py | unit/test_purchase_check.py::test_primary_verification_and_complete_evidence_survive_claim_classification | unit/application fake port | Separately authored 2024-02-28, leap-day opening and 2024-04-01 outcomes | Existing test only checked nonempty reasons | P1 | Same test strengthened: exact classification and reason pair | 3 passing; premature-ready mutation killed | PR31 |
| Hotpoint 30-day and Sony 35-day wait must prevent premature readiness | domain/claim_windows.py; application/purchase_check.py | integration/test_mvp_end_to_end_acceptance.py::TestMVPAcceptance::test_mvp_unsupported_claim_delays_are_not_release_approved (replaced) | PostgreSQL / REST / MCP | Reviewed official-term evidence and manually pinned calendar examples below | Previously asserted unsafe ELIGIBLE as observed behaviour | P0 | ::test_mvp_individual_wait_prevents_premature_claim_readiness | Initial two failures corrected by structured wait rule; final verification below | PR31-P0 correction below; no external issue |
| Correct product/manufacturer/retailer; unlinked product is never wildcard; groups do not broaden retailer scope | application/promotion_candidate_matching.py; application/identity_matching.py; db/repositories/identity_matching.py; db/repositories/promotions.py | integration/test_promotion_candidate_matching.py::test_exact_applicability; ::test_real_model_or_sku_resolution; unit/test_product_retailer_matching.py::test_combined_candidates | unit / PostgreSQL | Explicit isolated DB associations and expected empty/matched candidates | Already covered, including wrong product, missing product, SKU conflict | P1 | Existing tests retained | Passing; retailer-removal mutation killed | PR31 |
| Unicode aliases/collisions remain scoped and ambiguous; variants ordered separately | domain/identity_normalisation.py; db/models/identity.py | unit/test_identity_normalisation.py; integration/test_product_retailer_normalisation.py; integration/test_promotion_candidate_matching.py::test_all_variants_and_stable_order | unit / PostgreSQL | Authored aliases, UUID ordering and association graph | No additional unique gap confirmed | P1 | None | Existing coverage; not a new end-to-end guarantee | PR31 |
| Fixed/product rewards, GBP zero, exact percentages, missing price and wrong mapping; noncash has no fabricated amount | domain/rewards.py; domain/benefits.py; application/purchase_check_details.py | unit/test_rewards.py::test_percentage_calculation; unit/test_purchase_check.py::test_cashback_reward_independent_of_eligibility; ::test_missing_product_specific_mapping_is_data_error; ::test_non_cash_preserved_without_value | unit; existing REST/PostgreSQL reward tests | Literal Decimal expected values and GBP contract | Existing extensive parametrisation; no duplicate matrix added | P1 | None | Unit baseline passing | PR31 |
| Evidence requirements survive and are claim steps, not satisfied purchaser facts | domain/requirements.py; application/purchase_check_details.py | unit/test_requirements.py; unit/test_purchase_check.py::test_complete_result_immutable_detached_and_deterministic; integration/test_mvp_end_to_end_acceptance.py::offer | unit / PostgreSQL / REST / MCP | Typed requirement contracts; pinned descriptions | Some acceptance assertions compare manifest to output: projection checks only | P1 | None | Coverage exists; receipt/registration completion is unsupported | PR31 |
| Only active/expired published offers visible; archived/review excluded; historical claim period independent | domain/promotion_lifecycle.py; application/promotions.py; db/repositories/promotions.py | integration/test_promotion_candidate_matching.py::test_only_published_states; integration/test_mvp_end_to_end_acceptance.py::test_mvp_historical_published_promotions_remain_available | PostgreSQL / REST / MCP | Explicit DB statuses and independently selected claim dates | Already covered | P1 | None | Filtering passing; review-admission mutation killed | PR31 |
| Publication validates full graph/provenance; changed graph cannot reuse approval; retry/concurrent activation consistent | domain/promotion_validation.py; domain/promotion_provenance.py; application/promotion_authoring.py; application/promotions.py; db/models/core.py | integration/test_promotion_publication.py::test_preflight_snapshot_cannot_approve_changed_graph; ::test_concurrent_activation_has_one_change; ::test_source_verification_correction_allows_retry; unit/test_promotion_provenance.py::test_invalid_urls | unit / PostgreSQL | Constructed invalid graph, real constraints and source role contract | Extensive existing publication tests; no unproven new concurrency gap claimed | P1 | None | Unit provenance passing; invalid URL mutation killed; complete initial run covered publication | PR31 |
| Inconsistent published data never yields partial success; repeatable read and rollback | application/purchase_check.py; db/repositories/promotions.py; db/session.py; db/engine.py | integration/test_check_purchase.py::test_snapshot_does_not_mix_concurrent_changes; integration/test_eligibility_api.py::test_http_invalid_published_data_never_partial_success | PostgreSQL / REST | Concurrent committed edits, explicit invalid projection and safe error contract | Existing tests use real database; unit fakes do not prove isolation | P1 | None | Existing coverage; complete initial run passing | PR31 |
| REST strict dates/prices/size, safe problem details/request IDs, uncertainty vs no match | api/eligibility.py; api/schemas/eligibility.py | unit/test_eligibility_api.py::test_invalid_purchase_never_starts_snapshot; ::test_chunked_body_without_content_length_is_bounded; ::test_safe_failure_and_snapshot_closure; integration/test_eligibility_api.py::test_http_zero_missing_price_unresolved_and_no_match | unit / REST / PostgreSQL | Fixed schema/errors and explicit negative identities | Already covered; parity alone insufficient | P1 | None | Unit baseline passing | PR31 |
| MCP schema/safe errors, read-only association scoping and unpublished gate | mcp/server.py; mcp/schemas.py; mcp/local_access.py; application/promotion_details.py | integration/test_mcp_supporting_tools.py::test_wrong_benefit_source_links_and_empty_requirements; ::test_nonpublished_gate_before_graph_materialization; ::test_invalid_arguments_do_not_checkout_connections | MCP / PostgreSQL | Deliberately unrelated IDs and denied database operations | Existing meaningful denied-action tests | P1 | None | Existing coverage; complete initial run passing | PR31 |
| Cancellation/timeout/disconnect restores pool and DB baseline | mcp/server.py; db/repositories/promotions.py | integration/test_mcp_check_purchase.py::test_cancelled_call_releases_postgres_snapshot; ::test_mcp_transaction_timeout_restores_baseline_on_reused_connection; integration/test_mcp_supporting_tools.py::test_lookup_mounted_disconnect_closes_snapshot | MCP / PostgreSQL | Checked-out count zero; reused connection baseline; no further SQL | Already covered; no arbitrary-sleep test added | P1 | None | Existing coverage; complete initial run passing | PR31 |
| Configuration, diagnostics, health and schema remain safe/stable | core/config.py; core/logging.py; core/sentry.py; main.py; api/health.py; db/models/core.py; db/models/identity.py; db/base.py | unit/test_config.py; unit/test_sentry.py; unit/test_health.py; integration/test_postgres_migrations.py; integration/test_core_promotion_schema.py; integration/test_session_isolation.py | unit / PostgreSQL | Safe allowlists, explicit migration/schema/transaction constraints | Nullable minimum-wait column added in migration 0008; existing constraints preserved | P2 | None | Unit baseline passing; migration 0008 preservation/constraint/downgrade tests added | PR31 |
| Scripted conversation grounding is deterministic only | tests/chatgpt/flow.py (test harness); mcp/server.py | unit/test_chatgpt_tool_flow.py; integration/test_chatgpt_mcp_flow.py | scripted / MCP / PostgreSQL | Authored tool calls and whitelisted claim facts | **No real LLM extraction or prose faithfulness verified** | P2 | None | Explicit unsupported guarantee | PR31 |

Empty `__init__.py` modules have no business invariant. ORM package exports and db/base
are exercised through schema/migration suites. No fetching, ingestion, queues or model
provider boundary exists in this scope: new external-failure tests are **not applicable**.

## P0 reproduction and correction: PR31-P0

Pinned evidence was reviewed from repository manifests, not fetched live or inferred
from a runtime result. Hotpoint's reviewed Wren clause 8(c) / FAQ at
`https://promo.hotpoint.co.uk/terms-and-conditions` and `https://promo.hotpoint.co.uk/faqs/`
record a 30-day wait. Sony's reviewed terms section 8 at
`https://campaign.odw.sony-europe.com/redemption/terms/UK_TV_Autumn_Terms_and_Conditions_2026.pdf`
record 35 days. The Hotpoint and Sony fixture `evidence.clause_map.minimum_wait`
identifies those sections, with review times 2026-10-12 and 2026-10-13 respectively.
These are pinned review observations, not immutable source bytes or fresh verification.

The replacement test independently pins:

| Brand | Purchase | Evaluation | Earliest individual opening | Expected | Before correction |
| --- | --- | --- | --- | --- | --- |
| Hotpoint | 2026-06-12 | 2026-06-13 | 2026-07-12 | CLAIM_NOT_YET_OPEN | ELIGIBLE |
| Sony | 2026-10-27 | 2026-11-04 | 2026-12-01 | CLAIM_NOT_YET_OPEN | ELIGIBLE |

Both evaluations lie in the broad fixed campaign window. Before correction, the first
assert failed with `ELIGIBLE != CLAIM_NOT_YET_OPEN`. The tests retain the required
reason `claim_window_not_yet_open` and independently pinned individual opening.
The journey checks application/REST/MCP parity before the independent assertion.
Run:

```sh
uv run pytest tests/integration/test_mvp_end_to_end_acceptance.py -k individual_wait -q
```

Initial result: **2 failed, 48 deselected**, 5.05s. The correction keeps these safety
assertions and adds `FixedClaimWindow.minimum_days_after_purchase` and nullable
`promotions.claim_min_wait_days`. Opening is the later of the fixed opening and the
individual wait; the fixed deadline is preserved. Publication rejects empty or
overflowing claim intervals for allowed purchases. Existing rows retain NULL, and
relative claim windows keep their previous meaning. The authoring format accepts
the optional minimum wait on fixed windows; REST/MCP request and response schemas
are unchanged. Reference source observations remain pinned, with the current wait
explicitly represented in the structured claim definition. `claim_delay_limitation`
is the original evidence-capture observation; its historical `unmodelled` and false
publication/runtime-authority flags are not current publication gates. The acceptance
test compares the historical wait with the current structured wait and independently
asserts response classification, reason and opening. Its recorded verification
covers only the represented waiting-period rule.

Migration `0008_fixed_claim_min_wait` adds the field and check constraint without
backfilling source rules. Apply the migration and deploy **all** application
instances supporting the new
evaluator and publication logic **before** publishing any wait-bearing data. An old
binary ignoring the field is unsafe. Audit existing published promotions to identify
legacy omitted waits through source review and correct or withdraw affected offers.
Downgrade refuses while wait-bearing rows exist, preserving the condition until
operators explicitly plan safe data remediation. No external issue was created;
PR31-P0 is this audit's local tracking reference. The implementation exceeds the
original testing-only scope; **maintainer scope
approval remains pending**. The expanded surface proposed for review comprises
optional fixed-window `minimum_days_after_purchase`, nullable persisted
`claim_min_wait_days`, migration `0008`, publication validation, shared runtime
evaluation, authoring format, test-fixture updates and focused tests. Existing rows
retain `NULL`; no inferred or manufacturer-wide backfill occurs. If strict test-only
scope is desired, move the production rule/migration to a separately reviewed
dependent PR; this is an option requiring explicit instruction, not an approved
or performed split.

Other end-to-end limitations: the five-field CheckPurchaseRequest has no country,
purchase channel or product-condition facts, and the purchase-check projection builds
manufacturer/product/retailer/date rules only. Domain tests of those additional rule
forms do not prove runtime enforcement. Age, residency, marketplace seller, returns,
prior claims and receipt/account completion remain unverified. Source review does not
certify those unsupported restrictions; real model interpretation remains untested.

## Isolated defect-detection trials

These seven trials were performed against the initial audit implementation before
the minimum-wait correction; their descriptions refer to that source version.
Each trial copied backend into a fresh `/private/tmp/pr31-mutants-*` temporary directory,
excluding the venv/caches. Tests used the existing Python environment, with the venv bin
on PATH for Alembic. PostgreSQL trials created disposable Testcontainers, not the normal
development database. Source was restored in `finally`, SHA-256 hashes of original
source modules matched before/after, and the temporary directory was removed on exit.
No mutation switches or source edits were committed. The first PostgreSQL attempt failed
in setup because Alembic was missing from PATH; it **does not count**. Corrected reruns
below all failed at intended observable assertions, with pytest exit code 1.

Run each listed focused pytest ID with `-q --tb=short` against that isolated change.
The mutation descriptions give exact one-line replacements for reproduction.

| Trial / temporary mutation | Exact focused test ID (under tests/) | Actual failure / result | Intended reason |
| --- | --- | --- | --- |
| `domain/claim_windows.py`: `< window.start_date` → `<= window.start_date` | unit/test_claim_windows.py::test_inclusive_window_and_retained_dates[as_of1-open] | `assert result == ClaimWindowEvaluation(status, START, END)`; NOT_YET_OPEN != OPEN; 1 failed, 4 passed | Opening day must be included |
| Same module: `> window.end_date` → `>= window.end_date` | unit/test_claim_windows.py::test_inclusive_window_and_retained_dates[as_of3-open] | Same assertion; EXPIRED != OPEN; 1 failed, 4 passed | Deadline day must be included |
| `domain/eligibility_result.py`: UNKNOWN maps to ELIGIBLE instead of POTENTIALLY_ELIGIBLE | unit/test_eligibility_result.py::test_every_rule_status_combination_and_claim_state | `assert result.classification is expected_classification`; ELIGIBLE != POTENTIALLY_ELIGIBLE; 21 failed, 60 passed | Missing facts cannot certify eligibility |
| `db/repositories/promotions.py`: `PromotionVariant.retailer_id == retailer_id` → `True` | integration/test_promotion_candidate_matching.py::test_exact_applicability[changes3-False] | `assert query(...) == ((candidate,) if matched else ())`; candidate tuple != (); 1 failed, 4 passed | Wrong retailer must not match |
| Same module: add `PromotionStatus.REVIEW` to ACTIVE/historical filter | integration/test_promotion_candidate_matching.py::test_only_published_states[review] | `assert query(...) == ...`; review candidate tuple != (); 1 failed, 5 passed | Nonpublished promotion cannot leak |
| `domain/promotion_provenance.py`: `if not is_valid_source_url(source.url):` → `if False:` | unit/test_promotion_provenance.py::test_invalid_urls | `pytest.raises(PromotionProvenanceError)` DID NOT RAISE; 26 failed | Invalid primary/claim evidence cannot pass publication validation |
| `domain/eligibility_result.py`: NOT_YET_OPEN mapping changed to ELIGIBLE | unit/test_purchase_check.py::test_primary_verification_and_complete_evidence_survive_claim_classification[evaluation1-CLAIM_NOT_YET_OPEN-claim_window_not_yet_open] | `assert offer.eligibility.classification.value == classification`; ELIGIBLE != CLAIM_NOT_YET_OPEN; 1 failed, 2 passed | Strengthened application assertion detects premature readiness while preserving provenance |

There are seven distinct faults (two different calendar endpoints). Required publication
provenance evidence is demonstrated at the real domain validator, not a mocked response;
retailer and lifecycle filters are demonstrated against PostgreSQL. The tests are not
new progress merely because they killed faults: six trials corroborate existing coverage.

Initial audit checks, before the CI correction:

- `uv run pytest tests/unit/test_claim_windows.py tests/unit/test_eligibility_result.py tests/unit/test_purchase_check.py -q`: **347 passed**.
- `uv run pytest tests/integration/test_promotion_candidate_matching.py tests/unit/test_promotion_provenance.py -q`: **97 passed**, real PostgreSQL.
- `uv run ruff check .` and `uv run ruff format --check .`: passed after implementation.
- Full command `uv run pytest --cov=app --cov-branch --cov-report=term-missing --cov-report=xml:coverage.xml --cov-report=html:htmlcov -q`: **2385 passed, 2 failed** in 73.08s. This historical run exposed the two P0 Hotpoint/Sony safety regressions before correction. Coverage after the complete run: 2474/2550 statements (97.0196% line coverage), 560/608 branches (92.1053% branch coverage), 96.0735% combined; this matches the full PR30 baseline exactly.
- `uv lock --check --offline`: passed; 67 packages resolved consistently with the committed lock.
- Locked sync and Docker smoke were deferred in the initial audit; their completed correction-phase results follow below.
- No supported mypy configuration/command: **N/A, not run**.

The initial unmutated P0 failures are recorded above as defect evidence. Final
correction validation is recorded separately from those historical measurements.

## CI correction verification

New focused oracles cover the later individual opening, the campaign opening when
the wait already elapsed, inclusive opening/deadline dates, invalid wait types and
bounds, calendar overflow, empty intersections, strict authoring and publication
validation. The independent P0 dates above remain literal expectations. Migration
tests verify existing rows retain NULL, old values remain unchanged, invalid waits
are rejected by PostgreSQL, and downgrade cannot discard a stored wait. Reference
replay fingerprints now include the wait; changed and removed waits are rejected
without replacing the saved graph.

Relevant added/extended IDs:

- `unit/test_claim_windows.py::test_fixed_campaign_wait_uses_purchase_and_preserves_absolute_deadline`
- `unit/test_claim_windows.py::test_fixed_campaign_opening_still_applies_after_individual_wait`
- `unit/test_claim_windows.py::test_fixed_wait_rejects_invalid_offsets`
- `unit/test_claim_windows.py::test_fixed_campaign_wait_rejects_overflow_and_empty_intersection`
- `unit/test_promotion_authoring.py::test_fixed_window_wait_round_trips_as_typed_candidate_data`
- `unit/test_promotion_authoring.py::test_fixed_window_wait_rejects_untrusted_invalid_types_and_bounds`
- `unit/test_promotion_validation.py::test_publication_rejects_fixed_wait_without_a_nonempty_supported_intersection`
- `unit/test_promotion_validation.py::test_publication_accepts_fixed_wait_with_qualifying_purchase_bounds`
- `integration/test_postgres_migrations.py::test_fixed_min_wait_migration_preserves_rows_and_refuses_unsafe_rollback`
- Hotpoint/Sony `integration/test_*_reference_promotion.py::test_replay_rejects_changed_graph_without_replacement`

An additional controlled fault injection changed the domain evaluator's
`if window.minimum_days_after_purchase is not None:` to `if False:`. The focused
`test_mvp_individual_wait_prevents_premature_claim_readiness` run failed both cases
at `ELIGIBLE != CLAIM_NOT_YET_OPEN` (**2 failed, 48 deselected**, 5.29s). This trial
used a temporary source edit inside `try/finally`, preserving the original full
text in memory and restoring it before further validation. The restored P0 run
passed **2 tests** (158 unrelated cases deselected), 5.04s. There is no retained
mutation switch. The final Docker image and restored checkout have identical
aggregate app/migration source SHA-256 hashes.

- Focused implementation suites: **449 passed** in 36.47s.
- Fingerprint repair: **18 PostgreSQL replay/conflict tests passed** in 4.89s.
- Fixed-window unit suite after the campaign-opening oracle: **117 passed**.
- `uv sync --locked --extra dev`: passed (67 packages resolved, 63 checked).
- The existing workflow's Docker build, Alembic upgrade through 0008 and live
  `/health` smoke script: passed locally using disposable containers/network.
- Final complete command `uv run pytest --cov=app --cov-branch --cov-report=term-missing --cov-report=xml:coverage.xml --cov-report=html:htmlcov --cov-report=json:/private/tmp/pr31-ci-final.json -q`: **2414 passed**, 6 existing SQLAlchemy test warnings, 76.25s. No skips or expected failures conceal the P0 cases.
- Final coverage: 2500/2577 statements (97.0120%), 571/620 branches (92.0968%), 96.0588% combined. The PR30 baseline was 2474/2550 statements and 560/608 branches; the production rule added paths, so the denominator changed. This diagnostic does not set a release threshold.
- Final Ruff check and format check: passed (122 files formatted); `git diff --check`: passed.
- Independent review found the reference replay fingerprint omission; one repair cycle corrected it and a fresh second reviewer returned PASS. Implementation/review used gpt-6.1-sol; focused repair used gpt-6-luna. No remote GitHub Actions run was triggered; these are local executions of the CI checks.

These checks demonstrate represented claim timing and persistence guarantees.
They do not certify unrepresented claimant restrictions or automatically repair
legacy published records whose source wait was omitted.

## PR32 residual assurance follow-up — 2026-10-16

### Baseline and decision record

This is a follow-up to the PR31 evidence above, not a rerun of its audit or mutant
count. The local `main` and `origin/main` were still PR30 (`46d19f0`); remote
refresh failed with DNS resolution errors. The PR32 branch therefore uses the
available PR31 tip `62ea8e2` as its prerequisite baseline. The specification reports
PR31 merged on 16 October; neither the latest remote main, current highest PR
number, availability of PR number 32 nor remote CI status was independently
confirmed. No PR number was reserved and no PR was created.

**Governance decision outstanding:** both the PR31 task amendment and original
sections of this audit explicitly say maintainer approval of the production and
migration expansion is pending. No separate approval evidence was available.
A reported merge is not recorded scope approval. Obtain and record that decision
before relying on the dependent release. PR32 changes no production code,
manifest, schema, migration, transport contract, configuration or CI workflow.

Inspection and the three new isolated fault trials below found existing tests
already detect the proposed wait-projection, product-filter and reward-value
faults. **No new or strengthened tests were necessary.** The conditional synthetic
2027 wait scenario and additional product matrix would duplicate demonstrated
protection. This conclusion does not certify unavailable manufacturer facts or
legacy production data. No normal tests were relaxed, skipped or marked xfail.

### Findings and dispositions

Test paths below are relative to `backend/tests`; owning code is relative to
`backend/app`. “Adequately tested” refers to the stated fault and boundary, not
complete manufacturer entitlement.

| ID | Invariant/source clause | Customer failure/impact | Owning code | Existing test ID and boundary | Evidence/oracle | Gap category | Severity | New or strengthened test ID | Defect proof | Disposition/blocker |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PR32-01 | Hotpoint Wren 8(c); Sony §8: individual wait survives read projection | Premature claim-now advice | db/repositories/promotions.py::_check_details; application/purchase_check.py::_evaluate_candidate | integration/test_mvp_end_to_end_acceptance.py::TestMVPAcceptance::test_mvp_individual_wait_prevents_premature_claim_readiness; PostgreSQL → canonical operation → REST/MCP | Literal 30/35 days and 2026-07-12/2026-12-01 openings; independent reviewed observations, not fresh source bytes | adequately tested | P1 | None | M32-1: dropping persisted wait fails both existing cases | No duplicate synthetic test; source and legacy-row caveats remain |
| PR32-02 | Exact linked product only | Wrong product receives an offer | db/repositories/promotions.py::find_promotion_candidates | integration/test_promotion_candidate_matching.py::test_exact_applicability[changes1-False]; real PostgreSQL query | Independently constructed different product association; expected empty tuple | adequately tested | P1 | None | M32-2: removing product predicate yields forbidden candidate | No new test needed; application also rejects inconsistent candidate details |
| PR32-03 | Exact GBP reward projected from product mapping | Incorrect cashback advice | db/repositories/promotions.py::_check_details | integration/test_eligibility_api.py::test_http_real_snapshot_complete_projection_and_no_writes; PostgreSQL/REST; integration/test_check_purchase.py::test_complete_snapshot_materialised_no_writes; application | Literal expected amounts 100, 20.00, 42; synthetic persisted product-specific amount 42 | adequately tested | P1 | None | M32-3: product reward +1 fails literal REST oracle | Existing tests detect this concrete projection fault; not a claim of exhaustive cross-product mapping verification |
| PR32-04 | Recorded wait must match actual source-backed published data | Legacy NULL or wrong wait permits premature readiness | migrations/versions/0008_fixed_claim_min_wait.py; application/purchase_check.py | integration/test_postgres_migrations.py::test_fixed_min_wait_migration_preserves_rows_and_refuses_unsafe_rollback; PostgreSQL; existing reference replay tests | Migration preserves NULL deliberately; current fixture consistency is not evidence about deployed rows | migration/deployment risk | P1 | None | Inspection: optional NULL has no wait; no production dataset available | Release data audit required; correct or withdraw affected published rows with provenance; never infer brand-wide waits |
| PR32-05 | Reviewed official terms must justify configured facts | Internally consistent fixtures can still misstate entitlement | tests/acceptance/cases.py; integration/test_mvp_end_to_end_acceptance.py::offer | unit/test_mvp_acceptance_cases.py::test_pinned_acceptance_identity_reward_and_requirements; fixture consistency; acceptance offer; projection fidelity | Five reference clause maps and README review ledger; semantic hashes pin local JSON, not official bytes | unverified manufacturer/source fact | P1 | None | No fresh source-byte proof available; comparisons to manifest are not independent verification | Retain projection assertions; archive reviewed official versions before source-level certification; mapping below |
| PR32-06 | Samsung clause 7; LG Eligibility §4/General §27: new product | Refurbished purchase may still match configured public rules | domain/eligibility_rules.py::PurchaseConditionRule; application/purchase_check.py::_evaluate_candidate | unit/test_samsung_reference_promotion.py::test_new_only_domain_rule_is_separate_from_public_five_field_request; unit/test_lg_reference_promotion.py::test_new_only_domain_rule_is_separate_from_public_five_field_request; pure domain | Explicit REFURBISHED → NOT_ELIGIBLE/condition_mismatch, missing → POTENTIALLY_ELIGIBLE/condition_unknown | unsupported product capability | P0 conditional on claim-entitlement presentation | None | Domain pair exists; public CheckPurchaseRequest has no condition and configured rules omit it | All five references not release-certified as unconditional manufacturer entitlement; separate purchase-fact/persisted-rule/transport design required |
| PR32-07 | Claimant, country, seller/channel, prior claims, returns, account and evidence terms | Advice to excluded claimant or invalid seller/returned purchase | application/purchase_check.py::CheckPurchaseRequest/_evaluate_candidate; domain/eligibility_rules.py | Five reference domain/acceptance tests; current five-field contract inspected | Detailed per-brand ledger below; domain support for some typed rules does not establish runtime projection | unsupported product capability | P0 conditional on entitlement presentation | None | No transport facts or runtime configured rules for these exclusions | Separate supported-fact/uncertainty and publication policy scope; require review before general claim-entitlement advice |
| PR32-08 | All runtime instances must preserve wait-bearing data | Mixed old/new binaries ignore a newly stored wait | migration 0008; application/promotion_authoring.py; db/repositories/promotions.py | unit/test_promotion_authoring.py::test_fixed_window_wait_round_trips_as_typed_candidate_data; publication/migration/reference suites | Strict typed authoring → publication → persisted field → projection reviewed; old binary lacks evaluator | migration/deployment risk | P1 | None | M32-1 corroborates projection only; no deployed fleet observed | Apply 0008 and deploy all supporting consumers before enabling wait data; record fleet/version and legacy-data audit externally |
| PR32-09 | Corrupt publication must never partially succeed; evidence retained | Partial or misleading successful offers; unsafe error details | application/purchase_check.py; application/purchase_check_details.py; api/eligibility.py; mcp/server.py | integration/test_mvp_end_to_end_acceptance.py::test_mvp_corrupt_published_data_fails_safely; integration/test_eligibility_api.py::test_http_invalid_published_data_never_partial_success | Actual deleted claim-source link, exact published_data_invalid and no MCP structured success, pool cleanup | adequately tested | P1 | None | Existing tests inspected; no distinct new adversarial path established | No duplicate source/error test; provenance is traceability, not full terms enforcement |
| PR32-10 | Scripted conversation is deterministic tool assurance | Mistaking scripted grounding for faithful live language interpretation | tests/chatgpt/flow.py; mcp/server.py | unit/test_chatgpt_tool_flow.py; integration/test_chatgpt_mcp_flow.py | Authored tool calls and expected structured facts | unsupported product capability | P2 | None | No live model invoked | Natural-language extraction and generated prose faithfulness unverified; no live CI evaluation added |
| PR32-11 | No retrieval/ingestion boundary changed | No new external failure path to cover | N/A | N/A | No network/model ingestion implemented in this scope | not applicable | N/A | None | Inspection | No live manufacturer/model calls or new external-boundary tests |

### Evidence-to-test mapping and limits

No official terms PDF/HTML bytes are committed under `tests/fixtures/promotions`.
Hisense records the SHA-256 of a prior user attachment, but those attachment bytes
are not present there for independent replay. Samsung/LG/Hotpoint/Sony record
review observations and URLs rather than immutable official bytes. PR32 inspected
all five manifests and the README clause ledger; it did not reopen remote sources
or certify that their contents are currently unchanged. The independent literal
calendar/GBP expectations below independently exercise the implementation, while
their manufacturer authority remains the earlier recorded review observations.

| Narrow reference | Independently authored acceptance facts and clause attribution | Runtime enforcement | Informational requirements / unsupported restrictions / facts not established |
| --- | --- | --- | --- |
| Samsung SM-R640, Samsung.com | GBP 50, Table 1 p2; retailer Table 2 p3; purchase 3–23 June 2026 §§1–2; clause 12 inclusive offsets 0..29 gives purchase 15 June → 14 July | Manufacturer/product/retailer/purchase dates, relative claim dates, fixed reward | Clause 11 receipt/serial are instructions; clause 7 new-only and §§3–6/13 territory, age/company, reseller, prior claims/caps and account/Wallet steps unsupported. Portal accessibility/claim acceptance not established |
| LG OLED55G54LW.AEK, LG.com/UK | GBP 150 exact SKU reward row; Eligibility §§3–4/retailers §22; claim deadline 19 August 2025 §§4/6/9, Cashback Claim §12 | Manufacturer/product/retailer/purchase dates, fixed 21 May–19 August window, reward; 30-day validation delay is not an opening wait | §§6–7 receipt/serial informational; new UK condition, residency/age, bank account, bulk/returns/prior claims unsupported. Individual submission-after-purchase and exact 23:59 GMT cutoff unsupported; portal availability not established |
| Hisense WF7I1248BBR, Currys | GBP 100 Annex 2; Currys Annex 1/§3.2; purchases 9 September–27 October 2026 §3.1; claims 27 November–24 December §3.5 | Manufacturer/product/canonical retailer/purchase dates/fixed claim dates/reward | §§3.6/5.2/5.3/5.5 receipt/serial informational; §§3.7/4.1–4.8 consumer, age/residency, employee, condition, returns, direct seller/marketplace, combination and household cap unsupported. Portal not accessed; archived PDF hash alone is not replayed source bytes |
| Hotpoint H7IC16M6 UK, Wren | GBP 75 clause 4; Wren clause 13; purchase 5 May–12 June clauses 2–3; fixed 4 June–4 December plus 30 days clause 8(c)/FAQ; 12 June → 12 July | Manufacturer/product/retailer/dates/reward and structured wait 30 | Clauses 5/6/8 receipt/serial/warranty registration informational; clauses 1/9/14/15/20 claimant, condition, claims/combination/returns unsupported; seller identity beyond canonical Wren unsupported; payment/bank evidence not established |
| Sony K55XR75M2B, Currys - UK | GBP 150 §6 row; dealer PDF p3/§11; purchase 30 September–27 October §§5–6; 35 days §8 and fixed 31 December deadline §10; 27 October → 1 December | Manufacturer/product/retailer alias/dates/reward and structured wait 35 | §9 receipt and serial photo alternatives informational; §§2–3/7/11–13 owner/age/new condition/returns/account/seller/prior claims unsupported; exact CET cutoff unsupported; no claim submitted or accepted |

Acceptance `offer()` compares requirement descriptions, source URLs and timestamps
to each manifest: these are **projection fidelity** assertions. Semantic digest
checks protect against accidental local edits but can be deliberately updated with
a wrong fact; they do not independently validate official restrictions. Literal
amounts/dates in CASES and the two wait cases are **business expectation** oracles
within the recorded review scope. No new immutable-source business oracle was
invented where independent bytes were absent. Existing reference construction and
replay tests already reject changed or removed structured waits.

Concrete unsupported pair: Samsung clause 7 is recorded as new-only. The existing
pure-domain test rejects REFURBISHED and marks missing condition unknown. The
same public request for SM-R640/Samsung.com, purchased and evaluated 2026-06-15,
cannot express refurbished condition and its persisted configured rule set can
return ELIGIBLE. That is a configured-rule match, not certified claim entitlement.
This is a capability/release decision, not a regression to “fix” by a passing
transport test. Local follow-up scopes PR32-06/07 require supported purchase facts,
persisted typed constraints, projection, shared evaluation, REST/MCP design and
source-backed publication review; no external issues/PRs were created.

For PR32-04/08, source-audit every existing published wait-bearing promotion,
record source version and expected wait, compare the actual persisted column,
then correct/version or withdraw mismatches in a separate remediation. A synthetic
NULL row proves code semantics, not that a real production record is wrong. No
production dataset or deployment inventory was accessed, so actual affected rows
and mixed-version exposure remain unknown. All five references remain **not
release-certified for unconditional manufacturer claim entitlement** until material
unrepresented exclusions and evidence limitations have an explicit release decision.

### New isolated defect-detection evidence

Each trial copied `backend/` to its own disposable `/private/tmp/pr32-*` directory,
excluding the venv/cache/coverage artifacts. The existing Python 3.13 environment
and its bin PATH supplied pytest and Alembic. Exactly one site in the temporary
`app/db/repositories/promotions.py` changed; no working-tree production source was
edited. Each temporary source was restored to its original text, its focused test
rerun, and its directory removed. Disposable real PostgreSQL Testcontainers were
used throughout. These are new PR32 fault trials against **pre-existing tests**,
not newly added tests or new production defects and not PR31's earlier mutants.

| Trial | One-site replacement | Focused existing test ID | Intended observed failure | Restored result |
| --- | --- | --- | --- | --- |
| M32-1 | `_check_details`: `claim_min_wait_days=promotion.claim_min_wait_days` → `claim_min_wait_days=None` | integration/test_mvp_end_to_end_acceptance.py::TestMVPAcceptance::test_mvp_individual_wait_prevents_premature_claim_readiness | Both literal Hotpoint/Sony assertions fail: ELIGIBLE != CLAIM_NOT_YET_OPEN (2 failed, 5.49s); assertion names 12 July / 1 December openings | 2 passed, 5.05s |
| M32-2 | Candidate SQL `PromotionVariantProduct.product_id == product_id` → `True` | integration/test_promotion_candidate_matching.py::test_exact_applicability | `[changes1-False]`: nonempty PromotionCandidate tuple != (); 1 failed, 4 passed, 2.87s | 5 passed, 3.85s |
| M32-3 | `_check_details`: `ProductRewardValue(value.product_id, value.amount)` → `ProductRewardValue(value.product_id, value.amount + 1)` | integration/test_eligibility_api.py::test_http_real_snapshot_complete_projection_and_no_writes | Exact REST amount set {'100','20.00','43'} != {'100','20.00','42'}; 1 failed, 4.21s | 1 passed, 4.31s |

Reproduce each with the stated single-site edit in an isolated backend copy and
`python -m pytest <focused ID> -q --tb=short`, using the existing venv and migrated
PostgreSQL fixtures, then restore and repeat. M32-1 is projection loss, distinct
from PR31's pure evaluator bypass; M32-2 targets product rather than retailer;
M32-3 targets persisted reward value rather than pure reward arithmetic. Setup
errors are not counted as kills. Logs were inspected for these exact assertions.

### PR32 verification status

- `UV_CACHE_DIR=/private/tmp/uv-pr32 uv sync --locked --extra dev`: **could not complete**; locked resolution found 67 packages but editable build could not fetch setuptools==75.8.2 from PyPI because DNS resolution failed. Replacement evidence uses the existing venv with `uv run --no-sync`; fresh install reproducibility remains unverified.
- `UV_CACHE_DIR=/private/tmp/uv-pr32 uv run --no-sync pytest tests/integration/test_mvp_end_to_end_acceptance.py -k individual_wait -q`: sandbox attempt had **2 setup errors**, Docker socket PermissionError; this is not a product failure or mutant kill. With authorised Docker access and `--tb=short`, **2 passed, 48 deselected**, 5.57s.
- Isolated focused commands and restored results: table above. No full-suite run occurred during implementation.
- `UV_CACHE_DIR=/private/tmp/uv-pr32 uv run --no-sync ruff check .` and `uv run --no-sync ruff format --check .`: **passed**, 122 files already formatted; `git diff --check`: **passed**.
- mypy: **N/A**, no configured command. Migration-specific command `uv run pytest tests/integration/test_postgres_migrations.py -q` was not separately run during implementation because no migration interaction changed; the full suite remains the authoritative broader check.
- Docker image build/startup smoke not rerun: packaging, runtime and CI are unchanged. No live manufacturer/model requests, external accounts, production writes, commits, pushes or PR creation occurred.

### Final independent review and full-suite measurement

- Fresh reviewer: **PASS**, no actionable findings. No repair cycle was needed.
- From `backend/`, `UV_CACHE_DIR=/private/tmp/uv-pr32 uv run --no-sync pytest --cov=app --cov-branch --cov-report=term-missing --cov-report=xml:coverage.xml -q`: **2414 passed**, 6 SQLAlchemy warnings, 84.53s. No tests failed or were skipped.
- This PR32 run measured 2500/2577 statements (97.0120%) and 571/620 branches (92.0968%; 49 missing arcs, 47 partial branches), with 96.0588% combined coverage. Comparing the generated JSON to the preserved PR31 final report `/private/tmp/pr31-ci-final.json` found **the exact same missing-branch arc set**; no branch was newly missed or newly covered. The result is fresh PR32 evidence, despite matching the historical PR31 values.
- Risk review of the relevant locations found all branches covered in `application/purchase_check.py`, `domain/claim_windows.py`, and `domain/eligibility_rules.py`. Remaining partial arcs are in defensive validation/malformed-data branches across schema and domain constructors, authoring/publication validation, repository reward/source shape checks, and operational guards. Existing tests cover the customer-significant boundaries in those areas, including whole-check rejection of invalid published details, no partial REST/MCP success for corrupted source graphs, publication rejection/retry for malformed claim windows and reward mappings, and real persisted wait/product/reward projections. No additional residual business gap was established from the uncovered arcs. The missing locations and exact arc set are unchanged from PR31; percentages were not used as a test target.
- Local Ruff lint and format checks passed (122 files already formatted); `git diff --check` passed. mypy is N/A (no configured command). Migration tests were exercised by the full suite; Docker image/startup smoke was not rerun because packaging, runtime and CI were unchanged. No remote CI run was performed.
- The independently identified deployment/data audit prerequisites, unsupported customer facts, unavailable immutable source bytes, and pending PR31 maintainer scope decision remain unresolved; coverage does not clear them.
