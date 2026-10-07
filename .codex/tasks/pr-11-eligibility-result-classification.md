# PR 11 — Eligibility Result Classification

## Repository state

**Expected branch:**  
`pr11-eligibility-result-classification`

**Base branch:**  
`main`

**Dependencies:**

- PR 3 — Core Promotion Schema: merged.
- PR 4 — Promotion Lifecycle & History: merged.
- PR 5 — Benefit Model: merged.
- PR 6 — Promotion Source Provenance: merged.
- PR 7 — Product & Retailer Normalisation: merged.
- PR 8 — Purchase Input Contract: merged.
- PR 9 — Promotion Candidate Matching: merged.
- PR 10 — Core Eligibility Rules: merged.
- Existing Python 3.13 domain/application boundaries and pytest/Ruff tooling.
- No new database, migration, transport, provider, AI, queue, worker, cache, or infrastructure dependency.

### Read first

Before making changes, read:

- `AGENTS.md`
- `.codex/tasks/TEMPLATE.md`
- `.codex/tasks/pr-9-promotion-candidate-matching.md`
- `.codex/tasks/pr-10-core-eligibility-rules.md`
- `backend/README.md`
- `backend/app/domain/eligibility_rules.py`
- `backend/app/domain/promotion_lifecycle.py`
- `backend/app/application/purchase_check.py`
- `backend/app/application/promotion_candidate_matching.py`
- `backend/tests/unit/test_eligibility_rules.py`
- `backend/pyproject.toml`

If a more narrowly scoped `AGENTS.md` exists on the implementation branch, read and follow it.

### Primary change area

Pure deterministic domain result classification.

PR 10 produces per-rule outcomes:

```text
satisfied
not_satisfied
unknown
```

PR 11 composes those outcomes into one eligibility result for one promotion variant:

```text
ELIGIBLE
POTENTIALLY_ELIGIBLE
NOT_ELIGIBLE
CLAIM_NOT_YET_OPEN
EXPIRED
```

Conceptually:

```text
PR 10 rule evaluations
        +
claim-window state
        ↓
deterministic eligibility classification
        +
explicit machine-readable reasons
```

This PR does not calculate claim-window dates.

### Canonical implementation examples

Treat these as the preferred implementation references:

- `backend/app/domain/eligibility_rules.py`
  - immutable domain values;
  - `RuleStatus`;
  - `RuleEvaluation`;
  - stable `RuleReasonCode`;
  - deterministic evaluation order;
  - no persistence, network, application, or transport dependencies.
- `backend/app/domain/promotion_lifecycle.py`
  - stable `StrEnum` domain values;
  - deterministic state semantics.
- `backend/tests/unit/test_eligibility_rules.py`
  - dense table-driven domain tests;
  - stable enum-contract assertions;
  - explicit boundary behaviour.

Do not introduce:

- a general-purpose rules engine;
- a rules DSL;
- expression evaluation;
- dynamic rule loading;
- AI/LLM eligibility decisions;
- application orchestration;
- transport schemas.

### Relevant symbols

Inspect at minimum:

- `RuleKind`
- `RuleStatus`
- `RuleReasonCode`
- `RuleEvaluation`
- `PromotionEligibilityRules`
- `evaluate_eligibility_rules`
- `PurchaseEligibilityFacts`
- `PromotionStatus`
- `PromotionCandidate`
- `PromotionCandidateSet`

### Expected change surface

Expected changes should remain focused in:

```text
backend/app/domain/
backend/tests/unit/
backend/README.md
```

Likely additions:

```text
backend/app/domain/eligibility_result.py
backend/tests/unit/test_eligibility_result.py
```

A small update to `backend/app/domain/__init__.py` is acceptable if existing repository conventions require exports there.

No persistence or application orchestration change is expected.

### Excluded areas

Do not implement:

- fixed claim-window calculation;
- relative claim deadlines;
- delayed claim windows;
- claim dates derived from purchase date;
- evaluation against the current system clock;
- promotion requirements;
- requirement satisfaction;
- reward calculation;
- cashback amount calculation;
- warranty duration calculation;
- free-gift calculation;
- canonical `check_purchase` orchestration;
- promotion candidate aggregation;
- winner/best-promotion selection;
- promotion precedence;
- identity resolution;
- changes to promotion candidate matching;
- changes to `CheckPurchaseRequest`;
- new eligibility-rule types;
- persistence of rules;
- persistence of eligibility results;
- new database tables or columns;
- Alembic migrations;
- REST routes;
- FastAPI schemas;
- MCP tools;
- OpenAPI changes;
- publication validation;
- scraping;
- external provider calls;
- AI/LLM evaluation;
- frontend behaviour.

In particular, do not infer result `EXPIRED` directly from:

```python
PromotionStatus.EXPIRED
```

Promotion lifecycle expiry means a promotion is historical published data.

Eligibility-result `EXPIRED` means the relevant claim opportunity is no longer open.

These concepts must remain separate.

### Unknowns Codex must verify

Before implementation verify:

- PR 10 remains the canonical source of rule-level eligibility outcomes;
- `RuleStatus` still contains exactly:
  - `satisfied`;
  - `not_satisfied`;
  - `unknown`;
- `RuleEvaluation` still contains:
  - `kind`;
  - `status`;
  - `reason_code`;
- rule evaluations still preserve deterministic ordering;
- no final eligibility classification contract has appeared;
- no claim-window domain model or evaluator has appeared;
- no existing claim timing enum already represents open/not-yet-open/expired;
- `PromotionStatus.EXPIRED` remains lifecycle/history state only;
- current lint, format, and test commands still match `backend/README.md` and `backend/pyproject.toml`.

Do not create parallel concepts when the repository already contains an equivalent implementation.

---

## Objective

After PR 11, the backend must contain a pure deterministic domain classifier capable of converting PR 10 rule evaluations and a supplied claim-window state into one final eligibility classification for one promotion variant.

The supported classifications are exactly:

```text
ELIGIBLE
POTENTIALLY_ELIGIBLE
NOT_ELIGIBLE
CLAIM_NOT_YET_OPEN
EXPIRED
```

The classifier must provide explicit machine-readable reasons explaining why the classification was selected.

It must preserve the distinction between:

```text
known failed rule
→ NOT_ELIGIBLE

missing information required by a valid rule
→ POTENTIALLY_ELIGIBLE

all rules satisfied, claim can currently be made
→ ELIGIBLE

all rules satisfied, claim period starts later
→ CLAIM_NOT_YET_OPEN

all rules satisfied, claim period has ended
→ EXPIRED
```

Classification must:

- be deterministic;
- consume existing `RuleEvaluation` values rather than reevaluating eligibility rules;
- preserve PR 10 rule reason codes;
- use a typed claim-window state;
- perform no claim-date arithmetic;
- perform no database access;
- perform no network access;
- perform no LLM call;
- use no system clock;
- expose stable classification values;
- expose stable machine-readable reasons;
- remain independent of FastAPI and MCP;
- classify one promotion variant at a time.

This PR is complete when every classification and precedence combination is covered by deterministic unit tests.

---

## Architecture and invariants

Preserve the dependency direction:

```text
future REST / MCP
        ↓
future check_purchase application service
        ↓
candidate matching / promotion orchestration
        ↓
rule evaluation + claim-window evaluation
        ↓
eligibility result classification
```

PR 11 belongs in the domain layer.

### Core invariants

1. Final classification is deterministic.
2. An LLM never decides a classification.
3. Classification performs no database or network access.
4. The classifier consumes completed rule evaluations; it does not reevaluate rules.
5. Existing PR 10 reason codes remain authoritative for rule outcomes.
6. A known failed rule must never become `POTENTIALLY_ELIGIBLE`.
7. Missing information must never become `NOT_ELIGIBLE`.
8. Claim timing must not hide a known failed eligibility rule.
9. Claim timing must not hide unresolved eligibility information.
10. `PromotionStatus.EXPIRED` must not directly produce eligibility result `EXPIRED`.
11. Claim-window calculation is outside this PR.
12. Classification must not read today's date or the current clock.
13. Result and reason ordering must be deterministic.
14. Every result must contain at least one explicit reason.
15. Classification is per promotion variant; this PR does not aggregate multiple promotions.
16. Empty configured eligibility rules are valid: no configured rule means no eligibility restriction.
17. Do not create a second representation of PR 10 rule statuses.
18. Do not invent display prose as the business contract.

---

## API and contract changes

No public REST or MCP contract changes.

This PR introduces domain contracts only.

### `EligibilityClassification`

Introduce a stable classification enum equivalent to:

```python
class EligibilityClassification(StrEnum):
    ELIGIBLE = "ELIGIBLE"
    POTENTIALLY_ELIGIBLE = "POTENTIALLY_ELIGIBLE"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    CLAIM_NOT_YET_OPEN = "CLAIM_NOT_YET_OPEN"
    EXPIRED = "EXPIRED"
```

These values are part of the eligibility-result contract and must remain stable.

Do not collapse:

```text
POTENTIALLY_ELIGIBLE
NOT_ELIGIBLE
```

into one state.

Do not introduce fallback states such as:

```text
UNKNOWN
ERROR
MAYBE
UNAVAILABLE
```

Infrastructure/system failures are not eligibility classifications.

### Claim-window state input

Introduce the minimal typed state needed by the classifier, equivalent to:

```python
class ClaimWindowStatus(StrEnum):
    OPEN = "open"
    NOT_YET_OPEN = "not_yet_open"
    EXPIRED = "expired"
```

This enum represents the already-determined temporal state supplied to the classifier.

PR 11 must not determine this value from dates.

Future claim-window work may calculate:

```text
claim window definition
+
purchase date
+
evaluation date
        ↓
ClaimWindowStatus
```

PR 11 consumes only the resulting state.

Do not add:

- start date;
- end date;
- duration;
- offset;
- purchase-date arithmetic;
- current-date arithmetic

to the classifier merely to manufacture the status.

### Eligibility reasons

Every result must expose explicit machine-readable reasons.

Rule-driven reasons must preserve the existing PR 10 `RuleReasonCode`.

Classification-specific reason codes may be introduced for claim/result state, for example:

```python
class EligibilityReasonCode(StrEnum):
    ALL_CONFIGURED_RULES_SATISFIED = "all_configured_rules_satisfied"
    CLAIM_WINDOW_OPEN = "claim_window_open"
    CLAIM_WINDOW_NOT_YET_OPEN = "claim_window_not_yet_open"
    CLAIM_WINDOW_EXPIRED = "claim_window_expired"
```

Exact names may follow repository conventions, but their meanings must be stable and unambiguous.

Do not replace machine-readable reason codes with human prose.

A later presentation/API layer may map reason codes to user-facing descriptions.

### Result contract

Provide one immutable domain result equivalent to:

```python
@dataclass(frozen=True, slots=True)
class EligibilityResult:
    classification: EligibilityClassification
    reasons: tuple[EligibilityReason, ...]
    rule_evaluations: tuple[RuleEvaluation, ...]
    claim_window_status: ClaimWindowStatus
```

An equivalent shape is acceptable if it preserves all required semantics.

Requirements:

- immutable;
- no ORM objects;
- no FastAPI/Pydantic transport dependency;
- no raw purchase payload;
- deterministic reason order;
- original rule evaluations preserved;
- at least one explicit reason;
- no mutable collections.

`EligibilityReason` should distinguish rule reasons from classification/claim reasons without duplicating the entire PR 10 reason-code vocabulary.

A reasonable shape is:

```python
@dataclass(frozen=True, slots=True)
class EligibilityReason:
    code: RuleReasonCode | EligibilityReasonCode
    rule_kind: RuleKind | None = None
```

For rule reasons, `rule_kind` identifies the rule that produced the reason.

For classification/claim reasons, `rule_kind` is `None`.

Do not convert reason enums into unvalidated arbitrary strings internally merely for convenience.

### Classification operation

Provide one pure operation equivalent to:

```python
classify_eligibility(
    rule_evaluations: tuple[RuleEvaluation, ...],
    claim_window_status: ClaimWindowStatus,
) -> EligibilityResult
```

Exact naming may follow repository conventions.

The operation must not accept:

- raw purchase data;
- ORM promotion objects;
- `PromotionStatus`;
- current date/time;
- database session;
- HTTP request;
- application service;
- LLM/provider client.

---

## Domain and application behaviour

### Classification precedence

Classification precedence is mandatory.

#### 1. Known failed rule

If one or more rule evaluations have:

```python
status == RuleStatus.NOT_SATISFIED
```

return:

```text
NOT_ELIGIBLE
```

This takes precedence over:

- `UNKNOWN` rule evaluations;
- claim window `OPEN`;
- claim window `NOT_YET_OPEN`;
- claim window `EXPIRED`.

A known disqualifying rule is sufficient to establish that the promotion is not applicable.

Reasons must identify every `NOT_SATISFIED` rule in deterministic input order.

Example:

```text
purchase_price_below_minimum
retailer_mismatch

→ NOT_ELIGIBLE
```

Do not stop at the first failed rule when multiple failed evaluations are already available.

### 2. Unknown rule information

If no rule is `NOT_SATISFIED`, but one or more rules have:

```python
status == RuleStatus.UNKNOWN
```

return:

```text
POTENTIALLY_ELIGIBLE
```

This takes precedence over claim-window state.

Examples:

```text
purchase price required
purchase price unavailable

→ POTENTIALLY_ELIGIBLE
```

```text
country required
country unavailable
claim window is currently open

→ POTENTIALLY_ELIGIBLE
```

```text
purchase channel unknown
claim window has expired

→ POTENTIALLY_ELIGIBLE
```

The classifier must not imply that the user definitely qualified for an expired claim when purchase eligibility itself remains unresolved.

Reasons must identify every `UNKNOWN` rule in deterministic input order.

### 3. Claim not yet open

When every configured rule is:

```text
satisfied
```

and:

```python
claim_window_status == ClaimWindowStatus.NOT_YET_OPEN
```

return:

```text
CLAIM_NOT_YET_OPEN
```

Include an explicit claim-window reason equivalent to:

```text
claim_window_not_yet_open
```

Do not calculate the opening date in PR 11.

### 4. Claim expired

When every configured rule is:

```text
satisfied
```

and:

```python
claim_window_status == ClaimWindowStatus.EXPIRED
```

return:

```text
EXPIRED
```

Include an explicit reason equivalent to:

```text
claim_window_expired
```

This result means:

```text
the purchase satisfies all currently evaluated eligibility rules,
but the supplied claim-window evaluation says the claim opportunity has ended
```

It must not mean:

```text
Promotion.status == expired
```

### 5. Eligible

When every configured rule is:

```text
satisfied
```

and:

```python
claim_window_status == ClaimWindowStatus.OPEN
```

return:

```text
ELIGIBLE
```

Reasons should make both facts explicit:

```text
all_configured_rules_satisfied
claim_window_open
```

### No configured rules

An empty rule-evaluation tuple is valid.

PR 10 defines absent rules as imposing no restriction.

Therefore:

```text
no configured rules
+
claim window open
→ ELIGIBLE
```

```text
no configured rules
+
claim window not yet open
→ CLAIM_NOT_YET_OPEN
```

```text
no configured rules
+
claim window expired
→ EXPIRED
```

Do not invent an `UNKNOWN` result merely because there were no configured rules.

### Mixed failure and unknown

Example:

```text
retailer_mismatch
purchase_price_unknown
```

must produce:

```text
NOT_ELIGIBLE
```

The definite retailer failure is enough to reject the promotion.

The returned result must still preserve the complete original rule-evaluation tuple so later explainability/debugging can see both outcomes.

Decision reasons should identify the failed rule or rules that caused `NOT_ELIGIBLE`.

### Multiple unknowns

Example:

```text
purchase_channel_unknown
purchase_price_unknown
country_unknown
```

must produce:

```text
POTENTIALLY_ELIGIBLE
```

All unknown decision reasons must be retained in deterministic evaluation order.

### Reason ordering

Reasons must have deterministic ordering.

For rule-driven results, preserve PR 10 evaluation order.

Do not:

- sort reason codes alphabetically;
- depend on set iteration;
- depend on object identity;
- depend on database ordering.

Classification-specific reasons should follow one fixed documented order.

### Input validation

The classifier must require canonical domain values.

Invalid values must fail explicitly rather than being coerced.

Examples that must not silently work:

```python
classify_eligibility(..., "open")
classify_eligibility(..., "expired")
```

when a `ClaimWindowStatus` value is required.

Likewise, entries in `rule_evaluations` must be actual `RuleEvaluation` values.

Wrong types should raise `TypeError` consistently with the existing domain style.

Malformed domain input is a programming/data-contract error, not:

```text
POTENTIALLY_ELIGIBLE
```

### Promotion lifecycle separation

The classifier must not accept `PromotionStatus` as claim timing.

These are separate axes:

```text
PromotionStatus.EXPIRED
→ historical published promotion record

ClaimWindowStatus.EXPIRED
→ user's claim opportunity is no longer open
```

An expired historical promotion may still be relevant to a purchase made during its purchase eligibility period.

Candidate matching intentionally retains historical published promotions.

Therefore no direct mapping such as:

```python
PromotionStatus.EXPIRED
    -> EligibilityClassification.EXPIRED
```

is permitted.

### Application orchestration

None in PR 11.

Do not yet modify `match_promotion_candidates(...)` to automatically classify candidates.

Do not implement the full:

```text
CheckPurchaseRequest
→ candidates
→ facts
→ rules
→ classifications
```

pipeline.

That belongs to later purchase-check orchestration once structured promotion rules and claim windows can be loaded/evaluated end to end.

---

## Persistence, transactions, and migrations

None.

PR 11 must not add:

- tables;
- columns;
- enums in PostgreSQL;
- migrations;
- persisted eligibility results;
- persisted claim-window data.

Result classification is derived deterministic domain behaviour.

No transaction is required.

If persistence becomes necessary, stop and explain why the PR must expand before adding schema changes.

---

## External services and network access

None.

Classification must perform no:

- HTTP requests;
- AI/model requests;
- product lookups;
- source fetching;
- cache access;
- provider calls.

---

## Security and privacy

No new external security boundary is introduced.

Requirements:

- do not place raw receipt/customer/payment data into eligibility reasons;
- do not place arbitrary exception text into result reasons;
- use stable predefined reason codes;
- do not expose infrastructure failures as eligibility classifications;
- do not invoke dynamic code or user-controlled expressions.

The result object should contain only the minimum domain information required to explain classification.

---

## Configuration and deployment

None.

### Environment variables

None.

### Runtime/deployment changes

None.

No changes are required to:

- Docker;
- Railway;
- startup;
- shutdown;
- health/readiness;
- worker processes;
- schedules;
- database configuration.

---

## Observability and operations

No new telemetry infrastructure is required.

This is pure deterministic domain behaviour.

Do not add logging inside the domain classifier merely to make classification observable.

Future application/transport orchestration may log low-cardinality values such as:

```text
classification
reason_code
promotion_id
```

through the repository's existing observability boundary.

Domain unit tests are the primary operational verification for PR 11.

---

## Failure, consistency, and recovery

There are no writes or partial persistence states.

Expected failures are programming/domain-contract failures such as:

- non-`RuleEvaluation` input;
- invalid claim-window state type;
- malformed result/reason construction.

These must fail immediately.

They must not be converted into:

```text
NOT_ELIGIBLE
POTENTIALLY_ELIGIBLE
EXPIRED
```

Infrastructure failures are outside the classifier and must remain distinguishable from eligibility outcomes.

The operation is naturally idempotent:

```text
same rule evaluations
+
same claim-window status
→ equivalent EligibilityResult
```

---

## Acceptance criteria

### Behaviour

- [ ] `EligibilityClassification` defines exactly:
  - `ELIGIBLE`;
  - `POTENTIALLY_ELIGIBLE`;
  - `NOT_ELIGIBLE`;
  - `CLAIM_NOT_YET_OPEN`;
  - `EXPIRED`.
- [ ] Classification consumes PR 10 `RuleEvaluation` values rather than reevaluating rules.
- [ ] Any `NOT_SATISFIED` rule produces `NOT_ELIGIBLE`.
- [ ] A known failure takes precedence over unknown rule information.
- [ ] `UNKNOWN` without any known failure produces `POTENTIALLY_ELIGIBLE`.
- [ ] Unknown eligibility takes precedence over claim-window state.
- [ ] All rules satisfied + claim window open produces `ELIGIBLE`.
- [ ] All rules satisfied + claim window not yet open produces `CLAIM_NOT_YET_OPEN`.
- [ ] All rules satisfied + claim window expired produces `EXPIRED`.
- [ ] Empty rule evaluations are treated as no configured eligibility restriction.
- [ ] Every result has explicit machine-readable reasons.
- [ ] Existing PR 10 rule reason codes are preserved.
- [ ] Complete rule evaluations remain available on the result for explainability.
- [ ] Reason order is deterministic.
- [ ] Classification performs no claim-window date calculation.
- [ ] Classification does not depend on the current date/time.
- [ ] `PromotionStatus.EXPIRED` is never automatically mapped to result `EXPIRED`.
- [ ] Runtime classification remains deterministic and performs no LLM call.
- [ ] Existing behaviour outside the stated change surface remains unchanged.

### Data and consistency

- [ ] No schema or migration change is introduced.
- [ ] No eligibility result is persisted.
- [ ] No claim-window definition is persisted.
- [ ] Existing promotion history and provenance remain unchanged.
- [ ] Candidate/unvalidated promotion data behaviour remains unchanged.

### Security

- [ ] Reasons contain stable domain codes rather than arbitrary user/provider text.
- [ ] Raw sensitive purchase payloads are not embedded in result reasons.
- [ ] Infrastructure exceptions are not represented as eligibility states.

### Operations

- [ ] No new external calls or background processing are introduced.
- [ ] Health/readiness behaviour remains unchanged.
- [ ] No new configuration is required.

### Code quality

- [ ] Domain dependency boundaries are preserved.
- [ ] Result classification is implemented as focused pure Python domain logic.
- [ ] Existing `RuleStatus` and `RuleEvaluation` contracts are reused.
- [ ] No unnecessary dependency or unrelated refactor is introduced.
- [ ] No rules DSL/general-purpose engine is introduced.
- [ ] Ruff lint and format checks pass.
- [ ] Targeted tests pass.
- [ ] The broader backend test suite passes.

---

## Tests to add or update

### Unit tests

Add focused coverage in:

```text
backend/tests/unit/test_eligibility_result.py
```

Cover at minimum:

#### Stable contracts

Verify exact `EligibilityClassification` values.

Verify exact `ClaimWindowStatus` values.

Verify result/reason values are immutable if dataclasses are used.

#### Eligible

```text
all rules satisfied + OPEN
→ ELIGIBLE
```

Include:

- several satisfied rules;
- one satisfied rule;
- zero configured rules.

Verify explicit eligible reasons.

#### Potentially eligible

```text
one UNKNOWN + no failures
→ POTENTIALLY_ELIGIBLE
```

Cover:

- one unknown;
- several unknowns;
- satisfied + unknown mix;
- unknown + claim OPEN;
- unknown + claim NOT_YET_OPEN;
- unknown + claim EXPIRED.

Verify all unknown rule reason codes are preserved in stable order.

#### Not eligible

```text
one NOT_SATISFIED
→ NOT_ELIGIBLE
```

Cover:

- one failed rule;
- several failed rules;
- satisfied + failed mix;
- failed + unknown mix;
- failed + claim OPEN;
- failed + claim NOT_YET_OPEN;
- failed + claim EXPIRED.

Verify known failure takes precedence.

Verify all failed reason codes are included in stable rule order.

#### Claim not yet open

```text
all configured rules satisfied
+
NOT_YET_OPEN
→ CLAIM_NOT_YET_OPEN
```

Verify the claim reason is explicit.

Verify no current-date calculation occurs.

#### Expired

```text
all configured rules satisfied
+
ClaimWindowStatus.EXPIRED
→ EXPIRED
```

Verify explicit `claim_window_expired` reason.

Add a regression-style assertion making clear that:

```text
PromotionStatus.EXPIRED
```

is not accepted as claim-window status and does not itself determine the eligibility result.

#### Empty rule set

Cover all three claim-window states:

```text
() + OPEN
→ ELIGIBLE

() + NOT_YET_OPEN
→ CLAIM_NOT_YET_OPEN

() + EXPIRED
→ EXPIRED
```

#### Invalid inputs

Reject:

- list/string/`None` in place of the rule-evaluation tuple where inappropriate;
- non-`RuleEvaluation` tuple members;
- string `"open"` instead of canonical `ClaimWindowStatus.OPEN`;
- `PromotionStatus.EXPIRED` instead of claim-window status.

Do not convert invalid inputs into eligibility results.

#### Determinism

Calling classification repeatedly with equivalent inputs must return equivalent immutable results.

Changing unrelated iteration/set order must not change reason ordering.

### PostgreSQL integration tests

N/A.

No persistence behaviour changes.

### API/application tests

N/A.

No application service or public transport contract changes.

### MCP contract tests

N/A.

### External-boundary tests

N/A.

No external boundary is introduced.

---

## Verification commands

Run from `backend/`.

```bash
# Install/sync dependencies when required
uv sync --locked --extra dev

# Formatting check
uv run ruff format --check .

# Lint
uv run ruff check .

# Type checking
# N/A — no configured type-check command currently exists in backend/pyproject.toml.

# Targeted tests
uv run pytest tests/unit/test_eligibility_result.py

# Eligibility regression tests
uv run pytest tests/unit/test_eligibility_rules.py tests/unit/test_eligibility_result.py

# PostgreSQL integration tests
# N/A — persistence is unchanged.

# MCP/API contract tests
# N/A — public contracts are unchanged.

# Broader backend test suite
uv run pytest

# Migration verification
# N/A — no migration is introduced.
```

Do not invent a mypy or equivalent command unless repository configuration has changed and such a command now exists.

If any required command cannot run, document:

1. the exact command;
2. why it could not run;
3. what was verified instead;
4. the remaining risk.

Never weaken an existing PR 10 eligibility test merely to make PR 11 pass.

---

## Completion report

When implementation is complete, provide a concise report containing:

### Changed

Summarise:

- final eligibility classification domain contract;
- claim-window status seam;
- classification precedence;
- reason/explainability contract;
- tests added.

### Database and migrations

None.

### API/MCP contracts

None.

### Tests and verification

List:

- `test_eligibility_result.py`;
- any existing tests updated;
- exact verification commands run;
- actual results.

Do not claim an unrun command passed.

### External configuration

None.

### Deviations

Describe any meaningful deviation from this specification and why it was necessary.

Use `None` when there were no deviations.

### Remaining risks or follow-up

Expected later work includes:

- fixed claim-window definitions and calculation;
- relative/delayed claim-window calculation;
- promotion requirements;
- requirement evaluation;
- mapping persisted promotion data into typed eligibility rules;
- canonical purchase-check orchestration;
- evaluating all matched promotion candidates;
- multi-promotion result behaviour/precedence;
- reward calculation;
- REST/MCP transport contracts;
- user-facing explanation mapping.

Do not implement those concerns as part of PR 11.

List only additional unresolved PR 11 issues beyond those deliberately deferred areas.

Use `None` when PR 11 itself is complete.