# PR31 coverage and defect-detection audit

Audit date: 2026-10-15. The initial audit exposed two P0 claim-readiness failures.
The subsequent request to fix CI adds the structured minimum-wait rule, migration
and regression coverage described below. Certification remains limited to the
represented rules; legacy omitted waits require verified remediation.

## Reproducibility and scope

The implementation branch is `pr31-test-coverage-audit-regression-hardening`.
Its starting commit is `a2bbc4b` (merge of PR30 into the branch created from main).
The necessary PR30 acceptance suite was absent on main alone; the merge is an explicit
prerequisite adjustment, not a test-only diff. The implementation does not claim PR30
production changes as new coverage work. Latest remote PR numbering was not independently
verified; the attached specification is the authority for this work's scope.

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
coverage threshold was added. Local Docker image smoke was not run by this audit.

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
explicitly represented in the structured claim definition.

Migration `0008_fixed_claim_min_wait` adds the field and check constraint without
backfilling source rules. Deploy the migration and updated application before
publishing wait-bearing data; older application versions ignore the rule. Identify
legacy omitted waits through source review and correct or withdraw affected offers.
Downgrade refuses while wait-bearing rows exist, preserving the condition until
operators explicitly plan safe data remediation. No external issue was created;
PR31-P0 is this audit's local tracking reference. The initial testing-only scope
expanded in response to the user's request to fix CI.

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
