# BE — Database Seeding & Reference Data Loader

## Repository state

**Expected branch:** `feature/be-database-seeding-reference-data-loader`

**Base branch:** `main` (refresh before implementation; FE-04 / PR #36 was merged when reviewed).

**Dependencies:** Existing PostgreSQL/SQLAlchemy/Alembic schema; canonical identity matching (PR #7); promotion authoring and lifecycle/publication services; Samsung (#20), LG (#21), Hisense (#22), Hotpoint (#24), Sony (#25) reference work; explainability (#26); REST/MCP eligibility and five-manufacturer acceptance tests (#18, #27–30). Python 3.13, uv, Docker and PostgreSQL 16.

### Read first

- `AGENTS.md`, any nearer backend-scoped `AGENTS.md`, and `.codex/tasks/TEMPLATE.md`.
- `backend/README.md`, `backend/.env.example`, `backend/pyproject.toml`, `backend/tests/conftest.py`.
- `backend/app/db/models/{core,identity}.py`, `backend/app/db/repositories/{identity_matching,promotions}.py` and `backend/app/db/session.py`.
- `backend/app/domain/{identity_normalisation,promotion_lifecycle}.py` and `backend/app/application/{identity_matching,promotion_candidate_matching,promotion_authoring,promotions,purchase_check}.py`.
- `backend/app/api/eligibility.py`; existing promotion transaction factory and Alembic migrations.
- `backend/tests/fixtures/promotions/README.md` and the five reviewed JSON manifests; `backend/tests/{samsung,lg,hisense,hotpoint,sony}_reference.py`, `backend/tests/reference_helpers.py` and their associated unit/integration tests.

### Primary change area

An **explicit, operator-invoked reference-data loader**: validated versioned offline data, application-layer planning and orchestration, SQLAlchemy writes, CLI, operational documentation and real PostgreSQL integration tests. Keep catalogue seeding and promotion staging separate.

### Canonical implementation examples

- Identity: `Manufacturer`, `Retailer`, `Product`, alias/SKU ORM models; `SqlAlchemyIdentityRepository`, `IdentityResolver`, `normalise_text`, `normalise_identifier` and `MatchStatus`.
- Promotion: `SqlAlchemyPromotionRepository`, `promotion_transaction`, `change_promotion_status`, `PromotionPublicationError`, `PromotionStatus` and `parse_candidate_promotion` / `validate_candidate_promotion`.
- Reviewed manifest hash checks, evidence mapping, exact graph comparison and idempotent replay in the five **test-only** reference constructors. Their logic may guide extraction into production-owned modules; `app` must never import `tests` at runtime.
- Transaction-isolated, migrated PostgreSQL 16 Testcontainers fixtures in `backend/tests/conftest.py`.

### Relevant symbols

`Manufacturer`, `Retailer`, `Product`, `ManufacturerAlias`, `RetailerAlias`, `ProductModelAlias`, `RetailerProductSku`, `Promotion`, `PromotionVariant`, `Source`, `IdentityResolver`, `MatchStatus`, `SqlAlchemyIdentityRepository`, `SqlAlchemyPromotionRepository`, `promotion_transaction`, `change_promotion_status`, `PromotionStatus`, `parse_candidate_promotion`, `validate_candidate_promotion`, `purchase_check_snapshot`, `check_purchase`, `Settings.app_env`.

### Expected change surface

Suggested paths, not evidence that these modules already exist:

```text
.codex/tasks/be-database-seeding-reference-data-loader.md
backend/app/application/reference_data_import.py
backend/app/db/repositories/reference_data_import.py
backend/app/cli/seed_reference_data.py
backend/data/reference/                         # one versioned reviewed data pack
backend/tests/fixtures/promotions/              # reuse/repoint references without fact drift
backend/tests/{reference_helpers,*_reference}.py # shared safe logic where appropriate
backend/tests/unit/test_reference_data_import.py
backend/tests/integration/test_reference_data_import.py
backend/tests/integration/test_reference_data_eligibility.py
backend/README.md
```

Keep implementation focused. If another file is required, explain why.

### Excluded areas

- Public REST/MCP write endpoints, frontend controls, authentication, accounts and saved purchases.
- Crawling, live site/account access, manufacturer logins, AI extraction or inferred catalogue expansion.
- Automatic seeding on FastAPI startup, Docker startup, Alembic migration, deployment or user requests.
- Invented SKUs, retailers, claim rules, offer values or unsupported products outside reviewed references.
- Automatic promotion publication, expiration, source re-verification, lifecycle bypass or historical reactivation.
- Changes to eligibility, claim-window, reward calculations, results contracts or broad schema redesign.
- Destructive resets, truncation, force-overwrites and production database writes in this PR.

### Unknowns Codex must verify

1. Latest `main`, nearest scoped instructions, Alembic head and exact transaction-factory path.
2. Which five constructors only stage review graphs and which publish/expire *inside tests*; do not treat any test as a production loader.
3. Pinned semantic digests, manifest versions, verified observations and manufacturer/model/dealer mappings for each reference.
4. Canonical `Currys` versus reviewed Sony dealer alias `Currys - UK`; exact normalisation/collision behaviour.
5. Sony/Hotpoint legacy `claim_delay_limitation` flags versus subsequently implemented minimum-day fixed claim windows; never silently rewrite legacy evidence or approve publication.
6. Existing CLI packaging, environment config, session ownership, DB uniqueness and locking conventions.
7. Current tests for ambiguous identity, rollback, replay, conflicting graphs, publication rejection and end-to-end eligibility.
8. Whether all five references can be staged without unsupported graph facts; any mismatch must be identified explicitly.
9. Need for any schema change (not expected); do not invent a migration for seed data.

---

## Objective

Provide an **offline, repeatable, explicit** operator workflow to populate a fresh **migrated development/test PostgreSQL database** with the narrowly reviewed MVP reference catalogue. An optional, independently requested operation may stage the corresponding existing reference promotions in **non-published `review` state**.

After completion:

- `manufacturers`, `retailers` and `products` become usable without running pytest or manually inserting SQL.
- The catalogue contains the five evidenced manufacturers and *only* their reviewed exact reference models:

| Manufacturer | Exact reference model | Evidenced retailer |
| --- | --- | --- |
| Samsung | `SM-R640` | `Samsung.com` |
| LG | `OLED55G54LW.AEK` | `LG.com/UK` |
| Hisense | `WF7I1248BBR` | `Currys` |
| Hotpoint | `H7IC16M6 UK` | `Wren` |
| Sony | `K55XR75M2B` | canonical `Currys` with curated `Currys - UK` alias |

- Default invocation is **dry-run**. `--apply` changes the catalogue. `--apply --stage-promotions` may additionally persist the five reviewed promotion graphs as review-only, subject to strict evidence compatibility; it never publishes them.
- Identical retries change **no** business rows, IDs, timestamps or promotion status. Ambiguous/conflicting canonical identities or manifest evidence fail safely without partial commit.
- After catalogue seeding, the user's `Samsung / Blah / Currys / 2026-10-19` request returns HTTP 200 `unresolved_identity` for **model**, not for brand. A valid known model and retailer with no published match returns HTTP 200 `resolved`, `promotions: []` and `no_match_reason: no_matching_published_promotions`.
- Operators can see what was created/reused, reproduce a local bootstrap and distinguish missing catalogue from PostgreSQL being unavailable.

**Definition of done:** A fresh migrated PostgreSQL instance can be planned, populated and checked through a documented command, rerun without changes and rejected atomically on conflicts; staged promotion records are not observable as published matches; real integration/API tests demonstrate these properties.

---

## Architecture and invariants

1. **CLI → application use case → repository → PostgreSQL.** CLI handles only approved dataset selection, environment gating, modes and output. Application logic owns plan, ordering and conflict policy; SQLAlchemy adapter owns transactions and persistence. Domain and API do not depend on the loader.
2. **Catalogue ≠ promotion.** Known product identity must resolve with no corresponding promotion. A reference-only seed creates zero offers.
3. **Publication is authoritative.** REST and MCP continue using existing deterministic published-only purchase-check logic; a review row must never become active/expired merely because a loader ran.
4. **No side effects during boot or dry-run.** No startup hook, migrations-as-seeds, implicit test setup on the operator DB or direct SQL initialization.
5. **Reviewed, bounded facts only.** Preserve manufacturer/model/dealer strings, provenance dates and coverage limits. A seed does not claim the entire UK market is supported.
6. **One canonical owner.** Reuse compatible persisted UUIDs where unambiguous; never merge or re-parent identities or aliases silently.
7. **No silent updates.** Changed model, slug, ownership, source verification or promotion fingerprint is a conflict, not an implicit update.
8. **Lifecycle preservation.** Existing `review`, `active`, `expired` and `archived` graphs are checked for exact compatibility without reset, overwrite or reactivation.
9. **No runtime test dependency.** Do not import constructors in `backend/tests` from the backend app; extract shared deterministic pieces into appropriate application/repository modules while keeping existing regression coverage.
10. **No external calls or personal data.** No receipt, serial-number, order-history, login, LLM or remote source retrieval handling.

---

## API and contract changes

**No REST, MCP, OpenAPI or eligibility contracts change.** Add an internal operator-only CLI with this proposed interface (not yet implemented):

```bash
uv run python -m app.cli.seed_reference_data --dataset mvp-reviewed-v1 --plan
uv run python -m app.cli.seed_reference_data --dataset mvp-reviewed-v1 --apply
uv run python -m app.cli.seed_reference_data --dataset mvp-reviewed-v1 --apply --stage-promotions
```

- `--plan` is implicit/default and read-only; writes require `--apply`. `--stage-promotions` requires `--apply`.
- Use a finite allowlist of bundled dataset IDs only. Reject arbitrary local paths, URLs, globs and user-controlled SQL.
- Reject `APP_ENV=production`, even with `--apply`. For development/test, display only a *redacted* target hostname, port and DB name before applying.
- Summarise dataset ID/version/semantic hash, mode, per-entity created/reused/no-op counts and errors. Report staged promotions distinctly from published promotions.
- Stable exit codes: `0` for plan, successful apply or no-op; nonzero for input/conflict and service/database failure. Document exact values.
- No `--publish`, `--force`, `--reset`, `--truncate` or destructive switches in this task. Promotion publication requires an independently authorised workflow using the existing gate.

---

## Domain and application behaviour

### Dataset and catalogue rules

- Create one **first-class versioned reviewed data source**, derived solely from existing examined reference evidence. Avoid independently editable test and production copies: move/repoint manifests where feasible, or reference one canonical shared pack. Existing digest checks must remain meaningful.
- Strictly validate `dataset_id`, `schema_version`, field types, lengths, model identifiers, retailer aliases, normalized uniqueness, manufacturer ownership, evidence reference and **semantic SHA-256**. No automatic hash updating; material changes require review and version/digest amendment.
- Load canonical manufacturers and retailers, reviewed retailer aliases, then manufacturer-owned products. `Currys - UK` must resolve to **the same Currys ID**. Do not create a separate retailer for Sony and do not infer marketplace seller equivalence.
- Use `normalise_text` for manufacturers/retailers and `normalise_identifier` for models/SKUs; preserve exact raw display strings and punctuation (`.AEK`, spacing in `H7IC16M6 UK`). Never strip meaningful internal characters or shorten UK variants.
- Match first using canonical IDs and existing resolver semantics, then compare persisted factual identity/ownership. Reuse compatible rows, reject conflicting name/slug/model/alias/owner or ambiguous matches. Never silently rewrite pre-existing canonical data.
- Create `ProductModelAlias` or `RetailerProductSku` only with explicit reviewed evidence. A participating retailer is not evidence for a retailer-specific SKU.
- Do not load synthetic negative-test identities or fake products added only to make tests pass.

### Optional reviewed promotion staging

- Stage only the five narrow existing reviewed manifests, as full promotion graphs in `review`. Their test-only helper designs are examples; application code must not call `tests` helpers directly.
- Preserve exact campaign/variant relationships, dates, benefits/reward definitions, requirements, source roles/types/URLs, verification/retrieval timestamps and documented limitations.
- Preflight via existing candidate validation where possible. Candidate preflight is **not** persisted publication approval; no status transition to `active`/`expired` is part of this loader.
- Sony/Hotpoint manifest legacy flags such as `production_publication_permitted: false` and `authoritative_runtime_rule: false` are historical evidence. Compare them to current minimum-wait rule support and document any inconsistency for review; never silently flip a flag or bypass the current persisted publication gate.
- Historical Samsung/LG references stay historical in meaning; do not assert current portal availability or automatically publish/expire them.
- Replays compare the complete persisted graph and source evidence by stable manufacturer + promotion slug/variant identity. Same facts reuse IDs and leave status/timestamps untouched; changed facts reject. Do not create duplicate `Source` observations with identical evidence.
- A later authorised publication operation must explicitly invoke `change_promotion_status` with fresh evidence review. Loader staging must not claim atomic publication with the separate lifecycle transaction or briefly activate historical campaigns.
- If any reference lacks valid review-stage graph data, **reject the optional stage atomically** and report the precise blocker. Catalogue-only mode must still work independently.

### Eligibility-specific rules

Do not change eligibility decisions. Verify existing responses:

- Empty catalogue: `Samsung` → unresolved `brand`.
- Seeded Samsung/Currys and unknown `Blah` → unresolved `model` with `not_found`.
- Seeded exact model and retailer with no **published** applicable promotion → `resolved`, empty promotions and `no_matching_published_promotions`.
- Staged `review` promotions remain excluded.
- A test-only explicitly published graph, transitioned via the real publication service, is subsequently returned according to existing date, retailer, model and claim-window rules. No invented classifications.

### Ingestion/publication rules

No network ingestion. Manifests remain untrusted until schema and pin validation. Existing provenance, review/publication validation, lifecycle locking and published-data explainability remain authoritative. No AI or CLI shortcut to publication.

---

## Persistence, transactions, and migrations

**Affected existing tables:** `manufacturers`, `retailers`, `products`, `manufacturer_aliases`, `retailer_aliases`, optionally `product_model_aliases` and `retailer_product_skus`; if staging promotions, existing `promotions`, `promotion_variants`, product/benefit/requirement/source associations and reward tables.

**Expected schema change:** None. Reference data belongs in explicit operator commands, not schema migrations. Add an Alembic migration only if investigation demonstrates a necessary invariant absent from existing constraints; justify and test it separately.

- Validate the selected full dataset and derive a complete proposed plan before any writes.
- Use **one operator-owned transaction** per apply run covering catalogue and optional stage. Any validation, SQL or graph conflict rolls back all changes from that run. No per-row autocommits.
- Use a bounded PostgreSQL transaction-scoped advisory lock per dataset/target (or an existing equivalent) to serialise concurrent imports; re-read canonical keys within that lock. Keep unique/FK constraints authoritative.
- Handle `IntegrityError` as a safe conflict and leave the transaction rolled back. Never blindly retry as a new identity.
- Dry-run must perform no DML or durable database mutations and must not report speculative generated UUIDs as actual.
- No-op replays preserve all row IDs, `created_at`, `updated_at`, graph fingerprints and lifecycle statuses.
- No delete/truncate, source rewriting, mutable published graph edits, manual `active` status insertion or automatic data expiry.
- Test against a fresh migrated PostgreSQL 16 instance **and** one with existing unrelated reference/promotion data. Database connections and advisory locks must be closed cleanly after errors.

---

## External services and network access

**None.** The loader reads only approved local reviewed manifests and the configured PostgreSQL database. It must not fetch source URLs or connect to AI systems, manufacturer accounts or external services. Any future online reference ingestion is separate and will require explicit timeout, rate limiting, provenance and SSRF controls.

---

## Security and privacy

- Privileged local/deployment-operator-only command; no unauthenticated REST/MCP endpoint or browser invocation.
- Reject production environment writes. Read connection credentials through the existing `Settings`/`DATABASE_URL` path. Mask username/password and query secrets in output, logging and exceptions.
- Strict schema/field/hash validation. Allowlisted bundled dataset identifiers; no arbitrary path traversal, injected SQL, executable rule definitions, unsafe deserialization or remote content execution.
- Bound file size, nesting depth, entity count and runtime for the finite dataset. Evidence URLs are inert strings, not fetch targets.
- No shoppers' purchases, accounts, tokens, receipts, private serials or personally identifying data.
- Safe operator error classifications without raw SQL, credentials, stack traces or full third-party source content.

---

## Configuration and deployment

### Environment variables

Reuse existing settings only:

| Variable | Required | Process | Behaviour |
| --- | --- | --- | --- |
| `APP_ENV` | No | Loader | `development` or `test` allowed; `production` rejected |
| `DATABASE_URL` | Yes | Loader | PostgreSQL connection; keep secret and redact output |
| `LOG_LEVEL` | No | Loader | Existing structured logging level |

No `NEXT_PUBLIC_*` settings and no new secret/config variable expected.

### Runtime/deployment changes

- Run manually **after** `uv run alembic upgrade head` and after verifying the intended database. Document host-versus-Docker PostgreSQL port differences; current development Compose may expose `5434:5432`, but `DATABASE_URL` is authoritative.
- Bundle reviewed data-pack files in the backend package/image if operator commands must run there; never execute them automatically during container/build/startup/CI deployment.
- Leave FastAPI health/readiness and startup unchanged. Current `/health` does not query PostgreSQL, so it must not be described as database readiness.
- Production data publication/curation needs a separate authenticated, auditable operator workflow and approval.

---

## Observability and operations

Emit structured `reference_seed_plan`, `reference_seed_completed`, `reference_seed_noop`, `reference_seed_rejected` and `reference_seed_failed` events (or equivalent existing naming) with dataset ID, version/hash, mode, entity counts, duration and safe error category. Avoid high-cardinality source bodies and credentials.

Distinguish malformed data, identity ambiguity, ownership conflict, evidence/fingerprint drift, migration mismatch, unavailable database and completed no-op. Never label `review` records as `published` or dry-run as completed writes.

Document SQL count checks and HTTP purchase-check smoke requests. Logs to standard process output; no new metrics or log service required.

---

## Failure, consistency, and recovery

| Scenario | Required result |
| --- | --- |
| Fresh migrated empty DB | Plan shows approved records; explicit apply creates the catalogue |
| Identical second run | Successful no-op without timestamp, UUID or status changes |
| Ambiguous manufacturer/alias/model or conflicting persisted owner | Fail closed; no guessed merge or partial insert |
| Manifest digest mismatch / missing facts | Reject before writes, do not recalculate an approval digest |
| SQL error midway through catalogue or review staging | Roll back the whole dataset run |
| Two simultaneous operator invocations | Serialise/reconcile or fail with clear conflict, never duplicate |
| DB stopped, missing migration or wrong port | Nonzero operational error, not `unresolved_identity` |
| Existing active/expired promotion | Compare; never rewrite, reactivate or retire during load |
| Reference with unsupported publication evidence | Do not publish; optional stage either safely retains review or rejects |
| Process interruption with uncertain commit | Re-run reconciles the stored canonical facts without duplicate effects |
| Backend restart | Does not implicitly seed, refresh or publish |

---

## Acceptance criteria

### Behaviour

- [ ] Default is true dry-run, explicit `--apply` is required for writes.
- [ ] Catalogue-only import includes exactly the five reviewed manufacturers, five exact product models and evidenced retailers/aliases, but **zero promotions**.
- [ ] Opt-in reviewed-promotion staging produces only `review` records; unsupported/stale manifests cause a safe rejection rather than partial publication.
- [ ] Same import repeated is a true database no-op.
- [ ] Original `Samsung / Blah / Currys` purchase moves from unresolved brand to unresolved **model** after catalogue seed.
- [ ] Known seeded purchase with no published match returns resolved empty result.
- [ ] REST/MCP and deterministic eligibility contracts remain unchanged.

### Data and consistency

- [ ] No invented model variants, alias ownership, retailers, SKUs, rewards or campaign expansion.
- [ ] Real reviewed manifest digests, source evidence, graph fingerprints, provenance and historical limitations are preserved.
- [ ] Compatible existing identities are reused and incompatible/ambiguous entries rejected.
- [ ] Partial and concurrent failures preserve atomicity; unique constraints remain effective.
- [ ] All existing published/historical graphs and lifecycle statuses stay unchanged.
- [ ] Correctness verified against real migrated PostgreSQL, not SQLite-only tests.

### Security

- [ ] Loader refuses production and never runs automatically or through public transports.
- [ ] Manifests, dataset identifiers and source URL strings are bounded and validated.
- [ ] No database credentials or purchase/source-sensitive content leak to output or logs.

### Operations

- [ ] README provides plan/apply/stage instructions, target-DB checks, expected counts, smoke examples and publication caveats.
- [ ] Validation failures, conflicts, infrastructure errors and no-op runs have distinguishable exits/logs.
- [ ] Missing/unavailable PostgreSQL produces an actionable operator failure.

### Code quality

- [ ] No runtime import from `tests`, duplicate eligibility engine or bypass of publication services.
- [ ] Existing reference fixture tests remain valid; no tests weakened to get a green run.
- [ ] Formatting, lint, focused tests, PostgreSQL integration and full backend tests pass or are reported unrun accurately.

---

## Tests to add or update

### Unit tests

`backend/tests/unit/test_reference_data_import.py`:

- Strict version/schema/hash validation, approved five-manufacturer/retailer/model mapping and evidence coverage.
- Unicode name normalization, model punctuation, `Currys - UK` alias ownership, unsupported SKU/alias rejection.
- Preflight plan determinism, dry-run vs `--apply`, `--stage-promotions` preconditions, stable conflict/report classifications.
- Malformed, oversized, unknown-field or unapproved dataset/manifest rejection; production refusal and credential redaction.
- No runtime reliance on test helpers or network fetches.

### PostgreSQL integration tests

`backend/tests/integration/test_reference_data_import.py`:

- Migrated clean PostgreSQL 16 Testcontainer: plan is read-only, apply creates expected rows; second apply retains counts, IDs, all timestamps and statuses.
- Pre-existing compatible records reused; colliding aliases, duplicate normalized model identities or manufacturer mismatch rejected atomically.
- Forced mid-run exception/constraint error rolls back the entire run; corrected retry succeeds.
- Concurrent applies serialize/reconcile, no duplicate product or source observation rows.
- Promotion stage retains complete reviewed source/reward/rule graph strictly in `review`, never published; existing `active`/`expired` records stay unchanged.
- Unrelated pre-existing application data is preserved.

### API/application tests

`backend/tests/integration/test_reference_data_eligibility.py`:

- Before seed: Samsung unresolved brand; after seed: Samsung/Currys/Blah unresolved model.
- Known model and retailer with no published offer resolves with no match; review-only promotions remain excluded.
- Through the real persisted publication gate in **test setup only**, one reviewed valid promotion can become published and match according to stored rules; historical matching remains correct.
- A stopped/missing database still causes safe persistence failure (503) rather than a fabricated no-match response.
- Use actual FastAPI route and application use case, not a mocked identity resolver.

### MCP contract tests

No new MCP tool. Re-run a relevant existing purchase-check MCP regression against the seeded test database and verify parity with REST, particularly review-only exclusion.

### External-boundary tests

No external HTTP/AI calls. Assert all reference loading is offline and URLs from manifests are inert evidence, not fetched.

---

## Verification commands

From `backend/`, after checking the updated repository. **The seed command/new tests below are required implementation deliverables, not currently available commands.**

```bash
uv sync --locked --extra dev
uv run ruff format --check .
uv run ruff check .
uv run pytest tests/unit/test_reference_data_import.py
uv run pytest tests/integration/test_reference_data_import.py
uv run pytest tests/integration/test_reference_data_eligibility.py
uv run pytest
uv run alembic current
uv run alembic upgrade head

# Against an explicitly selected local development/test database:
uv run python -m app.cli.seed_reference_data --dataset mvp-reviewed-v1 --plan
uv run python -m app.cli.seed_reference_data --dataset mvp-reviewed-v1 --apply
uv run python -m app.cli.seed_reference_data --dataset mvp-reviewed-v1 --apply --stage-promotions
uv run python -m app.cli.seed_reference_data --dataset mvp-reviewed-v1 --plan
```

Also run existing five-reference promotion tests, publication and purchase-check integration tests and relevant MCP acceptance tests. No dedicated type-checking command is configured in the reviewed `backend/pyproject.toml`: if refreshed repository tooling supports type checking, run it; otherwise state the gap instead of claiming `compileall` is a type checker. If Docker/DB are unavailable, list exactly what was not run, why, what was verified instead and remaining risk. Do not weaken a meaningful failing test.

---

## Completion report

### Changed

Summarise CLI, application/repository modules, reviewed data pack, tests and documentation; report exact imported identity counts and staged graphs.

### Database and migrations

Expected migration: **None**. Report any justified change, transaction/locking details, zero-change replay and FK/constraint verification.

### API/MCP contracts

Expected change: **None**. Confirm existing transport schemas and eligibility outcomes remain stable.

### Tests and verification

Record every command actually executed and its result, including dry-run, initial apply, repeat apply, conflicts, concurrent runs, rollback and real REST/MCP paths.

### External configuration

State operator DB target (redacted), `APP_ENV`, `DATABASE_URL` setup and explicit manual commands; no new secrets expected.

### Deviations

Explain any revised source manifest, legacy evidence limitation, missing fixture, newly required migration or changed dataset scope. Otherwise `None`.

### Remaining risks or follow-up

State clearly that **a populated catalogue is not a published promotions database**. Staged review graphs are intentionally invisible to purchase results. Production publication/curation, freshness, historical activation safety and any broader product catalogue are separate work.
