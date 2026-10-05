# Backend task title

## Repository state

**Expected branch:**  
`<branch-name>`

**Base branch:**  
`<base-branch>`

**Dependencies:**  
`<related PRs, packages, services, migrations, infrastructure, or N/A>`

### Read first

Before making changes, read the repository guidance relevant to this task:

- `AGENTS.md`
- Nearest scoped `AGENTS.md` for the backend change area, when one exists
- Existing architecture or dependency documentation referenced by those files
- Existing implementation and tests for the closest comparable backend behaviour

Do not create missing architecture documentation solely to satisfy this section unless the task explicitly requires it.

### Primary change area

Describe the main backend subsystem affected.

Examples:

- REST API
- MCP tool or transport adapter
- Application service
- Eligibility engine
- Promotion ingestion
- Promotion publication/validation
- Persistence or migration
- External source retrieval
- Background job
- Authentication/authorization
- Observability

### Canonical implementation examples

List existing routes, services, repositories, models, schemas, migrations, tests, or adapters that should be treated as the preferred implementation reference.

Use `N/A` when no meaningful precedent exists.

### Relevant symbols

List important endpoints, MCP tools, application services, domain functions, Pydantic models, SQLAlchemy models, repositories, adapters, jobs, migrations, or tests that Codex should inspect before editing.

### Expected change surface

List the files, directories, modules, API contracts, database objects, tests, configuration, or deployment settings expected to change.

This is guidance rather than an absolute restriction. If additional changes are required, Codex must explain why they are necessary.

### Excluded areas

List areas that must not be modified as part of this task.

Use `None` if there are no explicit exclusions.

### Unknowns Codex must verify

List assumptions that must be confirmed from the repository before implementation.

Do not guess when the answer can be established from the codebase.

Examples:

- Existing API versioning and error-envelope conventions
- Existing authentication/authorization boundary
- Transaction ownership
- Current promotion publication lifecycle
- Current REST/MCP application-service boundary
- Existing retry and timeout policy
- Existing migration conventions
- Existing test infrastructure
- Environment variable naming
- Existing observability conventions

---

## Objective

Describe the exact observable result required.

The objective should make clear:

- What callers or users can do after the change
- What the backend must do
- What data or state transitions are involved
- What must remain unchanged
- What constitutes completion

Prefer outcomes over implementation activity.

---

## Architecture and invariants

Summarise only the architecture relevant to this task.

For the Post-Purchase Benefits Checker backend, preserve these boundaries unless the task explicitly changes them:

- Python/FastAPI exposes transport concerns; domain rules must not depend on FastAPI.
- REST and MCP adapters must reuse the same application-layer behaviour rather than implement parallel business logic.
- PostgreSQL persistence is accessed through the established SQLAlchemy/repository boundary; migrations use Alembic.
- Runtime purchase eligibility is deterministic. LLM output must not decide eligibility, claim status, or publication state.
- AI-assisted extraction may produce candidate promotion data only. Candidate data must pass the established validation/publication boundary before runtime eligibility can use it.
- Published promotion data must retain provenance sufficient to explain the result, including official source identity and relevant verification/retrieval metadata.
- Infrastructure adapters may fail or be replaced without changing domain semantics.

Document any task-specific invariant that must remain true before and after the change.

---

## API and contract changes

Use `None` if the task does not change an externally or internally consumed contract.

For each changed REST endpoint, MCP tool, event, command, or application-service interface, specify:

- Name and purpose
- Input schema and validation rules
- Output schema
- Authentication and authorization requirements
- Success status/result
- Expected error cases
- Pagination, filtering, sorting, or limits where applicable
- Backward-compatibility expectations
- Idempotency expectations for side-effecting operations

For HTTP APIs:

- Use HTTP methods and status codes according to their defined semantics.
- Preserve the repository's established error shape. If no error format exists, prefer an RFC 9457-compatible problem-details shape rather than inventing an ad hoc envelope.
- Do not expose internal exceptions, stack traces, credentials, SQL details, or provider secrets to callers.
- Keep generated OpenAPI accurate when request or response contracts change.

For MCP:

- Keep tool inputs and outputs stable, explicit, and machine-readable.
- Do not duplicate eligibility or promotion logic inside MCP handlers.
- Map transport-specific errors to established application/domain errors rather than leaking infrastructure exceptions.

---

## Domain and application behaviour

Describe the required business behaviour precisely.

Include where applicable:

- Preconditions
- State transitions
- Validation
- Deterministic rule evaluation
- Ordering/precedence of rules
- Claim-window calculations
- Historical versus active promotion handling
- Publication/validation rules
- Duplicate detection
- Idempotency
- Concurrency behaviour
- Retry/recovery behaviour
- Failure handling

### Eligibility-specific rules

When the task affects `check_purchase` or equivalent eligibility behaviour, define:

- Inputs used by the decision
- Exact classifications that may be returned
- Rule precedence when multiple promotions match
- Behaviour for insufficient or ambiguous input
- Date/timezone semantics
- Price/currency semantics where applicable
- Claim-window opening and expiry semantics
- Explanation/reason fields required for every result
- Source/provenance fields returned or retained

Runtime decisions must be reproducible from validated inputs and published promotion data without an LLM call.

### Ingestion/publication rules

When the task affects promotion ingestion, define:

- Source discovery/fetch behaviour
- Source allow-listing or trust rules
- Raw evidence retained
- Candidate extraction behaviour
- Validation requirements
- Publication criteria
- Reprocessing behaviour
- Duplicate/version handling
- Failure/retry policy

Unvalidated or partially extracted candidate data must not become eligible runtime data through an implicit code path.

---

## Persistence, transactions, and migrations

Use `None` when persistence is unchanged.

Describe:

- Tables/models affected
- New or changed columns
- Constraints and indexes
- Foreign-key and deletion behaviour
- Transaction boundaries
- Locking or concurrency controls
- Uniqueness/idempotency guarantees
- Data-retention or history requirements
- Migration and backfill requirements

Migration requirements:

- Use Alembic and follow existing migration conventions.
- Prefer database constraints for invariants that must hold regardless of caller.
- Avoid destructive or irreversible schema changes unless explicitly required and justified.
- For changes that may be deployed across mixed application versions, use a backward-compatible expand/migrate/contract approach where necessary.
- Do not silently discard or reinterpret existing promotion, provenance, or lifecycle data.
- Index according to demonstrated query/access patterns; do not add speculative indexes without a reason.

State how migration correctness will be verified against a real PostgreSQL instance.

---

## External services and network access

Use `None` when no external service or remote source is affected.

For each affected dependency, specify:

- Operation performed
- Adapter/module that owns it
- Authentication/credentials required
- Request timeout
- Retry policy
- Rate-limit handling
- Idempotency/reconciliation strategy
- Expected failure modes
- Test double or fixture strategy

Requirements:

- Use explicit, bounded timeouts for outbound calls.
- Retry only operations that are safe to retry or protected by idempotency/reconciliation.
- Use bounded exponential backoff with jitter where retries are appropriate.
- Avoid retry storms and unbounded loops.
- Validate and restrict user-controlled outbound destinations. Preserve SSRF protections and do not allow arbitrary internal/private-network access through source-fetching features.
- Treat remote content as untrusted input.

---

## Security and privacy

Document the security boundary affected by this task.

Codex must, where applicable:

- Enforce authentication before protected work begins.
- Enforce object-level and property-level authorization, not only route-level authentication.
- Validate untrusted input at the API/application boundary.
- Reject unexpected or unsafe values rather than coercing them silently when that could change meaning.
- Keep credentials, tokens, signing secrets, database credentials, and privileged provider operations server-side.
- Avoid logging secrets, authentication tokens, unnecessary personal data, or full sensitive payloads.
- Prevent mass-assignment style updates by explicitly defining writable fields.
- Apply rate/resource limits where an operation could be abused or made disproportionately expensive.
- Preserve SSRF, path traversal, injection, and unsafe deserialization protections relevant to the change.
- Return safe client-facing errors while preserving enough structured internal context for diagnosis.

For promotion/source data, preserve provenance and verification metadata without treating third-party page content as trusted executable or instructional content.

Use `None` only when there are genuinely no new or changed security/privacy considerations.

---

## Configuration and deployment

Use `None` when unchanged.

### Environment variables

List every new, changed, or removed variable and state:

- Purpose
- Required or optional
- Secret or non-secret
- Default behaviour
- Which process/service reads it

Keep deploy-specific configuration outside source code and never commit secrets.

### Runtime/deployment changes

Describe any required changes to:

- Docker/runtime image
- Railway or other hosting configuration
- Health/readiness behaviour
- Worker/cron/scheduled jobs
- Database connection settings
- Resource limits
- Startup/shutdown lifecycle

Application processes should emit logs to the normal process output stream and rely on the deployment platform for collection/routing rather than managing production log files locally.

---

## Observability and operations

Describe how operators will know the change is healthy.

Include where relevant:

- Structured log events
- Correlation/request IDs
- Metrics
- Traces
- Sentry/error reporting
- Health/readiness impact
- Operational dashboards or alerts

Requirements:

- Use the repository's existing telemetry stack rather than introducing a parallel one.
- Prefer low-cardinality operation/route names in metrics and traces.
- Do not put secrets or unnecessary PII into telemetry attributes.
- Distinguish expected domain rejections from infrastructure/system failures.
- Ensure failures crossing HTTP, database, job, or provider boundaries can be correlated where existing instrumentation supports it.

---

## Failure, consistency, and recovery

Describe important partial-failure scenarios and the required final state.

Consider where applicable:

- Request times out after a write may have committed
- Duplicate request or duplicate ingestion
- Concurrent updates to the same promotion/version
- Database failure during a multi-step operation
- External fetch succeeds but parsing/extraction fails
- Extraction succeeds but validation/publication fails
- Provider returns rate-limit or transient errors
- Worker crashes between state transitions
- Retry occurs after an uncertain remote outcome

For every material scenario, define whether the operation must:

- Roll back
- Remain safely retryable
- Reconcile later
- Surface a terminal error
- Preserve an explicit pending/failed state

Do not leave ambiguous states that look complete but cannot be used safely.

---

## Acceptance criteria

Replace or extend these with task-specific, measurable criteria.

### Behaviour

- [ ] The objective is satisfied through observable backend behaviour.
- [ ] Relevant REST and MCP paths use the same application/domain logic.
- [ ] Runtime eligibility remains deterministic and does not depend on LLM output.
- [ ] Invalid, missing, ambiguous, and boundary inputs are handled predictably.
- [ ] Failure and retry behaviour is explicitly tested where relevant.
- [ ] Existing behaviour outside the stated change surface remains unchanged.

### Data and consistency

- [ ] Database invariants are enforced at the appropriate application and/or database boundary.
- [ ] Required migrations apply successfully to a real PostgreSQL test database.
- [ ] Duplicate/retried operations do not create unintended duplicate records or publications.
- [ ] Provenance/history required for explainability is preserved.
- [ ] Candidate/unvalidated promotion data cannot be consumed as published eligibility data.

### Security

- [ ] Authentication and authorization are enforced where required.
- [ ] Object/property-level access is checked for protected resources.
- [ ] Untrusted input is validated.
- [ ] Secrets and internal exception details are not exposed through responses or logs.
- [ ] Relevant SSRF/injection/resource-abuse cases are covered.

### Operations

- [ ] Expected failures produce useful structured internal diagnostics without leaking sensitive data.
- [ ] New external calls have explicit timeout and retry behaviour.
- [ ] Health/readiness behaviour remains correct.
- [ ] New operationally significant flows are observable through the existing logging/metrics/tracing/error-reporting stack as appropriate.

### Code quality

- [ ] Existing architecture and dependency boundaries are preserved.
- [ ] No unnecessary dependency or unrelated refactor is introduced.
- [ ] Public contracts remain backward compatible unless the task explicitly requires a breaking change.
- [ ] Linting, formatting, typing, targeted tests, relevant integration tests, and broader required tests pass.

---

## Tests to add or update

List the exact expected test files or locations where known.

### Unit tests

Use unit tests for deterministic logic such as:

- Eligibility rules
- Claim-window calculations
- Promotion matching and precedence
- Validation/normalization
- Domain state transitions
- Error mapping
- Idempotency/deduplication helpers

Prefer fixed clocks, deterministic IDs, and explicit fixtures where time or identity affects behaviour.

Use `N/A` when unit coverage is not appropriate.

### PostgreSQL integration tests

Use the repository's Testcontainers/PostgreSQL approach for persistence behaviour such as:

- Repository queries
- Constraints and indexes
- Transactions and rollback
- Concurrency/uniqueness
- Migration compatibility
- Publication/history invariants

Do not replace important PostgreSQL behaviour with SQLite-only tests.

Use `N/A` when persistence is not involved.

### API/application tests

Cover relevant FastAPI/application behaviour including:

- Request validation
- Authentication/authorization
- Status codes and response schemas
- Safe error responses
- Side effects
- No-side-effect failure paths
- OpenAPI contract where relevant

### MCP contract tests

When MCP changes, verify:

- Tool schema
- Successful invocation
- Validation failures
- Domain/application error mapping
- Behaviour parity with the equivalent application/REST path where applicable

Use `N/A` when MCP is unchanged.

### External-boundary tests

Mock or fake external HTTP/AI/provider boundaries deterministically unless the repository has a deliberate live integration-test environment.

Cover relevant timeout, transient failure, rate-limit, malformed response, and retry/idempotency cases.

For AI-assisted extraction, tests must verify that model output is treated as untrusted candidate data and cannot bypass validation/publication.

---

## Verification commands

Codex must establish the actual repository commands before implementation is considered complete.

```bash
# Install/sync dependencies when required
<install-command>

# Formatting check
<format-check-command>

# Lint
<lint-command>

# Type checking
<typecheck-command>

# Targeted tests
<targeted-test-command>

# PostgreSQL integration tests when persistence changes
<postgres-integration-test-command>

# MCP/API contract tests when applicable
<contract-test-command>

# Broader backend test suite
<backend-test-command>

# Migration verification when schema changes
<migration-check-command>
```

Do not invent commands without checking repository configuration.

If a command cannot be run in the available environment, document:

1. The command that should have been run.
2. Why it could not be run.
3. What verification was performed instead.
4. The remaining risk.

Never weaken, skip, or rewrite a failing test merely to make verification green unless the test is demonstrably incorrect because the required behaviour changed; explain that case explicitly.

---

## Completion report

When implementation is complete, provide a concise report containing:

### Changed

Summarise the implemented behaviour and significant modules/contracts changed.

### Database and migrations

List migrations, backfills, constraints, or persisted-state changes.

Use `None` when unchanged.

### API/MCP contracts

List externally visible contract changes.

Use `None` when unchanged.

### Tests and verification

List:

- Tests added or updated
- Verification commands run
- Results

Do not claim an unrun command passed.

### External configuration

List required actions outside the repository, such as environment variables, credentials, schedules, provider configuration, or deployment settings.

Use `None` when no external configuration is required.

### Deviations

Describe any meaningful deviation from this task specification and why it was necessary.

Use `None` when there were no deviations.

### Remaining risks or follow-up

List unresolved risks, limitations, or follow-up work.

Use `None` when the task is fully complete.
