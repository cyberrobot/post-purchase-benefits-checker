# PR 18 — Eligibility HTTP API

## Repository state

**Expected branch:**  
`pr18-eligibility-http-api`

**Base branch:**  
`main`

**Dependencies:**

- PR 8 — `CheckPurchaseRequest` application input contract.
- PR 7 and PR 9 — canonical identity resolution and published candidate matching.
- PR 10–15 — eligibility rules/classification, fixed/relative claim windows, requirements, and rewards.
- **PR 17 (merged)** — `check_purchase`, `CheckPurchaseResult`, `UnresolvedPurchaseIdentity`, and `purchase_check_snapshot` with a coherent read-only PostgreSQL snapshot.
- Existing FastAPI application factory, Pydantic, PostgreSQL/SQLAlchemy, structured logging/Sentry, pytest/httpx, and PostgreSQL Testcontainers.
- No schema migration, LLM, MCP, frontend, or third-party network dependency.

### Read first

- `AGENTS.md` and any nearer-scoped `AGENTS.md` present at implementation time.
- `.codex/tasks/TEMPLATE.md` and `.codex/tasks/pr-17-check-purchase-eligibility-service.md`.
- `backend/README.md`, `backend/pyproject.toml`, `backend/.env.example`.
- Existing implementation and tests listed below; verify current `main` before editing.

### Primary change area

**REST API / transport adapter.** Introduce a stable public, versioned, JSON HTTP contract over the existing transport-independent purchase-check application service. No eligibility calculations belong to the route.

### Canonical implementation examples

- `backend/app/main.py::create_app` — application factory, `app.state.session_factory`, lifecycle and safe unexpected-error handler.
- `backend/app/api/health.py` — current FastAPI router pattern (only existing route: `GET /health`).
- `backend/app/application/purchase_check.py::{CheckPurchaseRequest, check_purchase}` — canonical validated input and orchestration.
- `backend/app/application/promotion_candidate_matching.py::{ResolvedPurchaseIdentity, UnresolvedPurchaseIdentity}` — resolved/unresolved result distinction.
- `backend/app/application/purchase_check_details.py::{CheckPurchaseResult, CheckPurchasePromotionResult, CheckPurchaseBenefit, PublishedPromotionDataError}` — immutable result and domain-data failure types.
- `backend/app/db/repositories/promotions.py::purchase_check_snapshot` — fresh dedicated session, read-only repeatable-read snapshot, rollback on exit.
- `backend/app/core/config.py::Settings` and `backend/app/core/logging.py` — configuration and telemetry conventions.
- `backend/tests/unit/test_health.py` — FastAPI `TestClient`, application-factory injection, and existing unexpected-error expectations.
- `backend/tests/unit/test_purchase_check.py` and `backend/tests/integration/test_check_purchase.py` — canonical service fixtures and PostgreSQL behaviour.

### Relevant symbols

```text
create_app, app.state.session_factory, health_router
Settings, configure_logging, initialise_sentry
CheckPurchaseRequest, check_purchase
CheckPurchaseResult, CheckPurchasePromotionResult, CheckPurchaseBenefit
UnresolvedPurchaseIdentity, ResolvedPurchaseIdentity
CheckPurchaseRepository, PublishedPromotionDataError, PublishedDataErrorCode
IdentityPersistenceError, PromotionPersistenceError
purchase_check_snapshot
EligibilityResult, EligibilityReason, RuleEvaluation
EligibilityClassification, ClaimWindowStatus, ClaimWindowEvaluation
BenefitType, RequirementType, RewardUnavailableReason, NoMatchReason
PublishedProvenance, PromotionSourceRecord, SourceRole, SourceType
normalise_text, normalise_identifier, validate_purchase_date, validate_purchase_price
```

### Expected change surface

```text
backend/app/api/eligibility.py                 # new APIRouter, orchestration adapter
backend/app/api/schemas/eligibility.py         # new explicit request/response/problem schemas
backend/app/api/schemas/__init__.py            # if package required
backend/app/main.py                            # route registration and scoped exception integration
backend/app/core/config.py                     # optional explicit CORS origin allowlist
backend/.env.example                           # only if configuration is added
backend/tests/unit/test_eligibility_api.py     # contract, parsing, error and wiring tests
backend/tests/integration/test_eligibility_api.py # real PostgreSQL end-to-end API tests
backend/README.md                              # public contract, samples, limits
```

A different narrow file layout is acceptable if it follows the current repository. Do **not** bypass the application factory or construct a second service implementation.

### Excluded areas

- Changes to domain classification, rule evaluation, candidate matching, reward arithmetic, claim timing, source validation, or the `CheckPurchaseRequest` application fields.
- Database models, SQL migrations, seed data, ingestion, publication, source fetching, background processing, caches, queues, or new external services.
- MCP tools, ChatGPT-specific request shapes, OAuth/account systems, saved purchases, evidence uploads, receipt OCR, claim submission, or frontend work.
- Price-threshold, country, channel, or condition eligibility **input or persistence**, which PR 17 does not currently support.
- User-supplied evaluation dates, offer ranking/aggregation, invented eligibility classifications, and inferred requirements satisfaction.
- Introducing a separate rate-limit database/Redis cluster or a new observability framework solely for this route.

### Unknowns Codex must verify

1. `GET /health` is still the only registered HTTP route; there is no established `/api/v1` versioning or public problem-details format to preserve.
2. The service still accepts only `brand`, `model`, `retailer`, `purchase_date`, and optional `purchase_price`. Check normalisation limits and exact `Decimal` validation rather than duplicating them differently.
3. `check_purchase` still returns `CheckPurchaseResult | UnresolvedPurchaseIdentity` and expects an explicit `evaluation_date`, `identity_resolver`, and `promotion_repository`.
4. `purchase_check_snapshot` still requires a **fresh** session factory (not a request-owned active session), sets PostgreSQL repeatable-read/read-only isolation, and rolls back and closes the transaction.
5. Existing typed result fields, reason/status enum values, source metadata and nullable values match the current code; update schema examples to actual types if code evolved.
6. `IdentityPersistenceError`, `PromotionPersistenceError`, and `PublishedPromotionDataError` remain the safe failure categories.
7. Whether an API gateway/reverse proxy already enforces body-size, request-rate and timeout limits. Do not claim these protections exist without verification.
8. Whether a dedicated CORS configuration already exists. Do not add a second or overly permissive middleware.
9. Current pytest/Ruff/Docker commands and the app-factory test seams remain as documented.

---

## Objective

Clients can submit a structured purchase via **`POST /api/v1/eligibility/check`** and receive a documented JSON result describing either (a) unresolved identity or (b) all matching published promotion variants with classification, reasons, claim timing, benefits/rewards, claim requirements, verification evidence and deterministic explanations.

The endpoint must call the **existing** `check_purchase` application operation **once** with a single server-chosen UK calendar evaluation date and the existing read-only PostgreSQL snapshot. It must expose no ChatGPT-specific abstraction and require no frontend to exist. Invalid input and infrastructure/data-integrity faults must produce stable, safe HTTP errors rather than false ineligibility. It must not write to the database or invoke an LLM or network source.

Completion means independent HTTP clients can use the documented v1 endpoint and generated OpenAPI, with tested deterministic mappings, failure behaviour and a real PostgreSQL end-to-end path.

---

## Architecture and invariants

```text
HTTP JSON / FastAPI + explicit Pydantic v1 wire schemas
  -> parse/validate and map to CheckPurchaseRequest
  -> request-scoped server evaluation date (Europe/London)
  -> purchase_check_snapshot(app.state.session_factory)
       -> check_purchase(..., identity_resolver=..., promotion_repository=...)
  -> explicit immutable-result -> response-schema mapping
  -> JSON (dates/timestamps/UUIDs/GBP decimals encoded deterministically)
```

- The router owns HTTP status, parsing, serializer, documentation and safe error mapping only. It **never** re-evaluates rules, chooses an offer, fixes source data, or reinterprets claim deadlines.
- Domain/application code must not import FastAPI/Pydantic/HTTP objects; do not expose ORM objects, sessions, Python exceptions or reprs in JSON.
- Use the `create_app`/`app.state.session_factory` wiring. Do **not** inject `get_session()` from `backend/app/db/session.py` into `purchase_check_snapshot`: that operation requires a fresh dedicated session and owns rollback/closure.
- Current query semantics include published `active` and previously published `expired`, but not `archived`; lifecycle expiry does **not** automatically mean the claim window expired.
- A syntactically valid unknown or ambiguous brand/retailer/model is a **successful unresolved lookup**, not HTTP 422 and not `NOT_ELIGIBLE`.
- `CheckPurchaseResult` with `promotions=[]` is also a successful, distinct no-match outcome; it must not be labelled `NOT_ELIGIBLE`.
- All promotion variants returned by PR 17, including separately matching variants, must be preserved in their existing deterministic order; no pagination, silent truncation or offer ranking in v1.
- The API is deterministic with respect to validated purchase, fixed evaluation date and one coherent published data snapshot. The HTTP layer chooses the date once; no implicit clock lookup in the domain operation.

---

## API and contract changes

### Endpoint

| Property | Contract |
| --- | --- |
| Method / path | `POST /api/v1/eligibility/check` |
| Request content type | `application/json` (`charset=utf-8` permitted) |
| Success | `200 OK`, `application/json` |
| Errors | RFC 9457-compatible `application/problem+json` for this new endpoint |
| Authentication | **Public read-only v1**: no customer session or API secret required. Abuse controls below are mandatory before exposing it publicly. |
| Idempotency | Safe to retry; POST is used for structured query inputs, but it performs no business writes. No idempotency key. |
| Pagination | None; preserves the complete canonical result order. No sorting/filter query parameters. |
| Compatibility | `/api/v1` and documented schema/enum/field names are stable; breaking changes require `/api/v2`. Additive optional fields must not change existing meanings. |

### Request wire contract

```json
{
  "brand": "Example Brand",
  "model": "MODEL-123",
  "retailer": "Example Retailer",
  "purchase_date": "2026-10-01",
  "purchase_price": "799.99"
}
```

- `brand`, `model`, `retailer`: required JSON **strings**, original spelling preserved; no trimming/canonicalisation for the application value. Validate using the existing PR 7 normalisers: no empty/blank, unsupported control characters, or more than 255 characters before **or after** normalisation. `model` may be a model number or SKU.
- `purchase_date`: required strict ISO full calendar date string `YYYY-MM-DD`; reject timestamp, timezone suffix, number, boolean, `datetime`, impossible date, and ambiguous locale formats. No restriction to past purchases: the core application contract does not enforce one.
- `purchase_price`: optional `null` or a **JSON string**, representing an exact non-negative GBP `Decimal` with at most 2 decimal places. Reject JSON numbers/floats/booleans, negative, NaN/Infinity, exponent notation, commas, currency symbols and silent rounding. A simple bounded wire form such as `^(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,2})?$` is acceptable; document any API-only numeric-length bound. `"0"` and `"0.00"` remain valid and distinct from missing/null.
- Do not add a `currency` field: v1 prices and calculated cashback are **GBP only**. Do not accept `evaluation_date` from callers.
- Unknown keys rejected (`extra="forbid"`), required fields may not be `null`, strict JSON object only. Avoid coercion from numeric strings for identity fields.
- JSON body must be bounded (target **8 KiB**) without relying only on `Content-Length`; if an upstream proxy provides this guarantee, verify and document it. Preserve standard HTTP error semantics when bodies are oversized.
- Map a validated transport request into the **existing** `CheckPurchaseRequest` so the domain validators remain authoritative. Where transport validation is narrower (e.g., lexical JSON price form), document that it is an explicit wire-format policy, not a new eligibility rule.

### Successful response: discriminated union

Use a required top-level `outcome` discriminator. The generated OpenAPI must show the two mutually exclusive response shapes rather than an opaque `dict` or serialized dataclass tree.

**Resolved purchase**, including no matching published promotions:

```json
{
  "outcome": "resolved",
  "evaluation_date": "2026-10-08",
  "resolved_identity": {
    "manufacturer_id": "11111111-1111-4111-8111-111111111111",
    "retailer_id": "22222222-2222-4222-8222-222222222222",
    "product_id": "33333333-3333-4333-8333-333333333333"
  },
  "promotions": [
    {
      "promotion_id": "44444444-4444-4444-8444-444444444444",
      "promotion_variant_id": "55555555-5555-4555-8555-555555555555",
      "promotion_name": "Example Cashback",
      "variant_name": null,
      "promotion_status": "active",
      "eligibility": {
        "classification": "ELIGIBLE",
        "reasons": [
          {"code": "all_configured_rules_satisfied", "rule_kind": null},
          {"code": "claim_window_open", "rule_kind": null}
        ],
        "rule_evaluations": [
          {"kind": "manufacturer", "status": "satisfied", "reason_code": "manufacturer_match"},
          {"kind": "product", "status": "satisfied", "reason_code": "product_match"}
        ],
        "claim_window_status": "open"
      },
      "claim_window": {
        "status": "open",
        "opens_on": "2026-10-01",
        "deadline_on": "2026-10-31"
      },
      "benefits": [
        {
          "benefit_id": "66666666-6666-4666-8666-666666666666",
          "benefit_type": "cashback",
          "name": "Cashback",
          "description": null,
          "cashback_reward_gbp": "80.00",
          "reward_unavailable_reason": null,
          "reward_unavailable_explanation": null
        }
      ],
      "requirements": [
        {"requirement_type": "receipt", "description": "Upload your receipt."}
      ],
      "provenance": {
        "official_source_url": "https://example.org/promotion",
        "source_type": "web_page",
        "retrieved_at": "2026-10-01T10:00:00Z",
        "verified_at": "2026-10-02T10:00:00Z",
        "claim_url": "https://example.org/claim"
      },
      "sources": [
        {
          "source_id": "77777777-7777-4777-8777-777777777777",
          "role": "primary",
          "url": "https://example.org/promotion",
          "source_type": "web_page",
          "retrieved_at": "2026-10-01T10:00:00Z",
          "verified_at": "2026-10-02T10:00:00Z"
        },
        {
          "source_id": "88888888-8888-4888-8888-888888888888",
          "role": "claim",
          "url": "https://example.org/claim",
          "source_type": "web_page",
          "retrieved_at": "2026-10-01T10:00:00Z",
          "verified_at": "2026-10-02T10:00:00Z"
        }
      ],
      "explanation": [
        "The recorded eligibility rules match this purchase.",
        "The claim window is open."
      ]
    }
  ],
  "no_match_reason": null,
  "explanation": []
}
```

Example IDs/URLs/terms above are **illustrative, not fixtures**. The actual endpoint must serialize values from PR 17 without inventing extra rule evaluations, claim dates, sources or reward amounts.

**Unresolved identity**:

```json
{
  "outcome": "unresolved_identity",
  "evaluation_date": "2026-10-08",
  "unresolved_identity": {
    "field": "model",
    "status": "ambiguous",
    "candidate_ids": ["33333333-3333-4333-8333-333333333333"]
  },
  "explanation": ["The product model matches more than one product. Enter a more specific model number or SKU."]
}
```

For unresolved outcomes, do not populate `promotions` or `resolved_identity`; these exist only in the `resolved` schema. Keep `candidate_ids` in the established deterministic order, and do not fabricate display labels for them. The `unresolved_identity.explanation` source is the existing deterministic `UnresolvedPurchaseIdentity.explanation` property.

For **resolved no-match**, return `200`, `promotions: []`, `no_match_reason: "no_matching_published_promotions"`, the resolved UUIDs, and the existing application explanation. Do not return `404`, `NOT_ELIGIBLE`, or an empty unresolved response.

### Typed field and serialization rules

- `classification` is **exactly one of** `ELIGIBLE`, `POTENTIALLY_ELIGIBLE`, `NOT_ELIGIBLE`, `CLAIM_NOT_YET_OPEN`, `EXPIRED` — case preserved.
- Each eligibility reason has stable `code` and nullable `rule_kind`; every rule evaluation has `kind`, `status` and `reason_code`. Include complete arrays in application order, including non-decisive evaluations.
- `claim_window` is `null` when PR 17 has no configured window; in that case `claim_window_status` is `null`. Otherwise preserve `status`, `opens_on`, `deadline_on` from the canonical window evaluation.
- Benefits have `benefit_id`, `benefit_type`, `name`, nullable `description`, nullable `cashback_reward_gbp`, nullable `reward_unavailable_reason` and nullable `reward_unavailable_explanation`. For free gifts/warranties, reward money is `null`; do not suggest a value. For missing percentage-price inputs preserve the specific unavailable reason without changing eligibility.
- Requirements have the current `requirement_type` and nullable `description`. PR 17 does **not** expose requirement IDs in its result, so do not synthesize them.
- `provenance` reflects validated publication primary/claim records, including exact official and claim URLs, source type, retrieved/verified timestamps. `sources` reflects **all** PR 17 source records, with role/type/URL/time metadata. Supporting/terms sources may have `verified_at: null`; do not represent them as officially verified by inference.
- UUIDs are canonical hyphenated strings; dates are ISO full dates; aware datetimes are RFC 3339 strings including offset (UTC may use `Z`). Preserve instants. GBP amounts are **decimal strings**, with no float conversion or rounding in HTTP serialization; `"80.00"` is valid, including trailing pence when present in the Decimal.
- Preserve existing candidate order and within-result benefits/requirements/source ordering; no sorting in the HTTP adapter. Use explicitly defined Pydantic response models and mapping functions, with `null` rather than disappearing fields where the documented resolved schema declares a nullable property.
- Reason/status/benefit/source values are explicit string enums in OpenAPI. Keep semantic fields independent of changeable English descriptions.

### Evaluation date

- Determine `evaluation_date` **once** per accepted check using the **`Europe/London` calendar date**, independent of server system timezone and DST (e.g., `datetime.now(ZoneInfo("Europe/London")).date()`).
- Pass this concrete `date` into `check_purchase`; return the same date at top level in either success outcome.
- Make the clock injectable/overridable in tests without modifying the application-layer signature or reading wall time in deterministic tests.
- Do not accept client-provided evaluation date in v1 and do not confuse purchase date with current claim-evaluation date.

### Error response contract

For failures introduced by this endpoint, use RFC 9457-compatible `application/problem+json` with `type`, `title`, `status`, `detail`, and a stable extension `code`. Include `request_id` if server request correlation is available. Never echo raw rejected values, SQL details, Python exception strings, stack traces, source secrets, or internal table names.

| Status | `code` | When |
| --- | --- | --- |
| `413` | `request_too_large` | Request body exceeds documented 8 KiB bound. |
| `415` | `unsupported_media_type` | Unsupported request content type. |
| `422` | `invalid_purchase_request` | Malformed JSON, missing/extra fields, wrong JSON types, invalid identity/date/GBP price; optionally include bounded field/error-code metadata, never raw input. |
| `429` | `rate_limited` | Public edge/gateway rate limit; return `Retry-After` where available. |
| `500` | `published_data_invalid` | Published projection/provenance/reward consistency error; never transform into `NOT_ELIGIBLE` or silently omit affected results. |
| `503` | `eligibility_unavailable` | PostgreSQL/session/repository availability failure, including `IdentityPersistenceError` or `PromotionPersistenceError`; no eligibility result fabricated. |
| `500` | `internal_server_error` | Unexpected error not already covered; safe generic details and internal exception logging. |

Example:

```json
{
  "type": "about:blank",
  "title": "Invalid purchase request",
  "status": 422,
  "detail": "Provide valid purchase fields and try again.",
  "code": "invalid_purchase_request"
}
```

Use a stable problem `type` URI if one exists in the repository; otherwise `about:blank` is acceptable. Schema should document 200, 413, 415, 422, 429, 500 and 503. If implementing 413/429 at a gateway, coordinate its error shape where configurable rather than pretending FastAPI generated those responses. Custom scoped FastAPI validation handlers may be needed to make `RequestValidationError` match the new problem format; **preserve existing `/health` and its existing generic unexpected-error contract**.

---

## Domain and application behaviour

1. Validate the JSON wire request strictly, then create `CheckPurchaseRequest` using the same brand/model/retailer strings, Python `date`, and exact `Decimal | None`. Domain constructor errors caused by untrusted input should map to `422`, never `500`.
2. Capture the request's UK evaluation date once; enter `purchase_check_snapshot(app.state.session_factory)` using a **new** dedicated session, then call `check_purchase` **exactly once** with the resolver and repository yielded by that context manager.
3. On `UnresolvedPurchaseIdentity`, return the discriminator, known field, `not_found`/`ambiguous` status, original candidate UUIDs and existing explanation. This is `200`, not 404/422; do not run promotion detail lookups after unresolved resolution (as enforced by PR 17).
4. On `CheckPurchaseResult`, return all matching variants, with the exact five classification values from the domain. Do not compare raw strings, recompute claim dates, recalculate cashback, infer price/channel/country/condition restrictions, or reorder/select variants.
5. Eligibility precedence remains that of PR 11/17: known failed rule → `NOT_ELIGIBLE`; unknown rule → `POTENTIALLY_ELIGIBLE`; missing window → `POTENTIALLY_ELIGIBLE`; then opening/expiration/open state. Eligibility is not a guarantee that a manufacturer accepts a claim.
6. Dates are inclusive **as evaluated by the service**, not by the route. Promotion lifecycle `expired` and claim-window `expired` remain distinct. `no_matching_published_promotions` remains a successful resolved result, not evidence of negative eligibility.
7. Requirements are claim instructions, not confirmation that evidence has been supplied. URLs are passive result data, never fetched by this endpoint. Sources are returned with original role and verification status.
8. Entire request is read-only: no database commits, writes, saved-purchase records, analytics write, claim submission or external API calls. Repeated identical calls with fixed snapshot/date return equivalent JSON aside from request telemetry.

### Eligibility-specific rules

Inputs used: existing `brand`, `model`, `retailer`, `purchase_date`, optional GBP `purchase_price`, server-selected evaluation date, and stored published promotion data. No new rule dimensions or input fields. Preserve all original reasons and rule evaluations. Timezone applies to choosing **today**, not to converting the caller's purchase calendar date. Use the same canonical `check_purchase` output for every client.

### Ingestion/publication rules

Not changed. PR 17's validated published `active` and `expired` records participate; raw, discovered, extracted, review and archived records do not become runtime results through the API.

---

## Persistence, transactions, and migrations

**No schema changes or Alembic migrations.**

- Use `purchase_check_snapshot` with a fresh app-owned `sessionmaker` session, covering identity, candidate query and detail hydration in one **read-only repeatable-read PostgreSQL transaction**.
- Snapshot context owns rollback/close even when mapping, application or transport processing fails. Never `commit`, reuse `get_session`, flush pending writes, or hold the transaction open for network calls.
- Result DTOs must be fully materialised before leaving the snapshot; response mapping must not cause lazy ORM access.
- Existing deterministic repository ordering, publication scope and provenance are preserved. No new tables, writes, locks, indexes or historical reconstruction.
- Verify transaction/rollback semantics in existing PostgreSQL integration tests and a new HTTP-to-PostgreSQL test using the current migration head; no new migration test is expected.

---

## External services and network access

**None.** Source URLs and claim URLs are passive JSON strings. Do not call manufacturers, ChatGPT/LLMs, search, OCR, payments, email, or other providers; do not add retry logic for deterministic validation failures. PostgreSQL is the existing internal persistence dependency and its failures are surfaced as safe `503` responses.

---

## Security and privacy

- This first checker is **public, unauthenticated and read-only**; it handles product/purchase fields, not saved personal accounts or claims. Do not implement an insecure browser-embedded API secret. Restrict the database principal to read privileges for this path when deployment supports it.
- Bound request body to 8 KiB, validate JSON types/unknown fields, and rely on shared domain normalisers to reject bad Unicode/identity inputs. No arbitrary source URL, SQL query, file upload or executable user text is accepted.
- **Before production exposure**, configure/verify edge rate limiting and request timeout protection for `POST /api/v1/eligibility/check`; suggested initial policy: **60 requests/minute/IP with a modest burst** and `429`/`Retry-After`, tuned with real traffic. If no suitable gateway exists, document that production publication is **blocked pending a separate rate-limit/control PR** instead of shipping an ineffective per-process in-memory limiter. This requirement is explicit and verifiable, not a claim that the current repository already has controls.
- Use narrow CORS origin allowlisting only for known client origins. CORS is not authentication; reject wildcard production origins and do not enable cross-origin credentials. Browser same-origin clients must work without CORS configuration.
- Never return full exceptions, traces, SQL/connection information, operational hostnames, config, credentials, tokens or unpublished promotion data. Do not log raw brand/model/retailer strings, purchase prices, receipts or full request/response bodies.
- Do not trust source descriptions as executable instructions or turn returned source URLs into server-side fetches. Retain precise source role and verification data rather than implying all sources are official.
- Avoid propagating caller-controlled request-ID values unchecked into logs/headers; generate a safe request ID or validate any existing middleware policy.

---

## Configuration and deployment

### Environment variables

- `API_CORS_ALLOWED_ORIGINS` (**optional**, non-secret): exact allowed browser origins for v1 if a separate-origin UI is later deployed. Default: **empty list / no cross-origin browser access**. Owned by the FastAPI settings/middleware boundary; documented in `.env.example` and README if implemented. Use Pydantic Settings' supported collection parsing; no hard-coded frontend hostname and no wildcard production setting.
- `DATABASE_URL`, `APP_ENV`, `LOG_LEVEL`, `SENTRY_DSN`: unchanged.
- **No API key** and **no model-provider key** required for this endpoint.

### Runtime/deployment changes

- Register the router in `create_app` and keep existing `/health`, app lifespan and error logging working unchanged.
- Do not add a second engine/session factory or load the DB at import time beyond the existing bootstrap.
- Document that the deployment ingress must enforce the body/rate/time limits above if not enforced within FastAPI; specify clearly which layer implements which control. Return 413 for oversized bodies even when `Content-Length` is absent.
- Expose OpenAPI schema at the existing FastAPI `/openapi.json` endpoint. Keep logs on process stdout. No worker, migration, Docker image dependency or hosting-provider configuration required in source solely for this API.

---

## Observability and operations

- Reuse structlog/Sentry already wired by `create_app`; do not add another telemetry stack.
- Include a generated request/correlation ID in API diagnostics and returned error responses where supported. Prefer an `X-Request-ID` response header if a request-ID pattern is adopted.
- Log low-cardinality `eligibility_http_check_completed`/`eligibility_http_check_failed` with status, `outcome`, classification counts, request ID and safe duration/candidate-count metrics; avoid duplicate verbose logging already performed by `check_purchase`.
- Distinguish expected `resolved`/`unresolved_identity`/no-match responses and 422 validation from data-integrity/system failures. Do not send expected user errors to Sentry as incidents.
- Use path templates, not arbitrary identifiers or user input, as metric labels. Keep the `/health` process-only contract unchanged.

---

## Failure, consistency, and recovery

| Scenario | Required final state |
| --- | --- |
| Missing/incorrect fields, invalid date or money string | `422` problem JSON; domain work and database calls not started. |
| Malformed JSON, wrong content type or oversized body | `422`, `415`, or `413` problem JSON as applicable; no check is performed. |
| Unknown/ambiguous identity | `200`, `outcome=unresolved_identity`; do not claim non-eligibility or return a server error. |
| Resolved identity with no published candidates | `200`, `outcome=resolved`, `promotions=[]`, explicit no-match reason. |
| Published data inconsistent/missing mandatory verified provenance | `500` `published_data_invalid`; no partial `200`, no promotion omission and no guessed answer. |
| PostgreSQL read/snapshot unavailable or fails part-way | `503` `eligibility_unavailable`, rollback/close, safe logs; caller can retry. |
| Unexpected adapter/serialization exception | `500` generic problem response; log internally with request ID, never leak details. |
| Concurrent promotion update while checking | One consistent PR 17 repeatable-read result or safe error; never mix versions within a response. |
| Retried identical request | No write or duplicate business effect; same output for the same date and dataset. |
| Rate limit reached (configured gateway) | `429` and bounded retry guidance; no database work where limit is enforced ahead of app. |

There is no persistent operation state to reconcile. Partial-success HTTP bodies must not be returned after a failed eligibility computation.

---

## Acceptance criteria

### Behaviour

- [ ] `POST /api/v1/eligibility/check` accepts the documented valid JSON and returns `200` with a typed, documented discriminated response.
- [ ] The route creates **exactly one** canonical `CheckPurchaseRequest` and calls **exactly one** `check_purchase` through the existing `purchase_check_snapshot`; no parallel rule implementation.
- [ ] Both unresolved (not found/ambiguous) and resolved no-match outcomes are `200` and retain distinct machine-readable structures.
- [ ] All matching variants, exact five classification values, all rule evaluations/reasons, inclusive claim-window dates, claim requirements, benefits/reward reasons, sources and provenance are preserved without inferred data.
- [ ] Purchase calendar date and evaluation date are distinct; evaluation date is derived once from the `Europe/London` timezone and injected in tests.
- [ ] Repeated checks perform no writes; existing `GET /health` behaviour is unchanged.

### Data and consistency

- [ ] One fresh dedicated read-only repeatable-read PostgreSQL snapshot covers the full check; rollback and close occur on success/failure.
- [ ] No migration, schema, promotion lifecycle, source data, publication rules or existing application-service contract is changed.
- [ ] Only already-published eligible candidate states are returned; historical `expired` state is not confused with claim-window expiry.
- [ ] No false `NOT_ELIGIBLE` is manufactured from unknown/no-match/missing-window outcomes.

### API compatibility

- [ ] OpenAPI contains exact request model, both discriminated `200` response models, enumerations, examples and 413/415/422/429/500/503 responses.
- [ ] GBP values are decimal **strings** (no float), calendar dates are strict ISO dates, and UUIDs/aware source timestamps serialize correctly.
- [ ] Extra fields and unsafe Pydantic coercions are rejected; validation/problem responses contain no raw input or internals.
- [ ] Field names, enum spellings, outcome discriminator and null-vs-absent rules match this v1 specification.

### Security

- [ ] No API/client secret is embedded in browser-facing code; no account/claim data or unvalidated promotions are exposed.
- [ ] Request size and JSON media type are enforced; non-JSON, oversized, malformed and adversarial Unicode/price bodies have contract tests.
- [ ] Production edge rate limiting and request timeout policy are verified and documented before public exposure; otherwise production exposure is explicitly blocked as a follow-up.
- [ ] CORS defaults to no cross-origin allowance and accepts only explicitly configured origins if implemented.
- [ ] No raw purchase details, secrets, stack traces, SQL strings or response bodies are logged or returned.

### Operations and code quality

- [ ] Expected user outcomes are not logged as system faults; persistence/published-data faults are distinguishable internally and mapped to safe errors externally.
- [ ] Existing application factory, Sentry, logging, database lifecycle and `/health` tests still pass.
- [ ] No new data store, external provider, LLM call, frontend dependency or unrelated refactor is added.
- [ ] Targeted API/unit/PostgreSQL integration tests, full backend pytest, Ruff lint/format and relevant Docker checks pass (or any inability to run is reported precisely).

---

## Tests to add or update

### Unit tests

`backend/tests/unit/test_eligibility_api.py` (or equivalent focussed transport contract tests):

- Strict valid request parsing, omission/null/zero and decimal precision; reject JSON numeric money, float/exponent/negative, invalid date/timestamp, blank/control/oversized identity, booleans, extra fields, arrays and unknown keys.
- `CheckPurchaseRequest` receives unchanged raw strings, a Python calendar date and an exact Decimal. Rejected requests never enter the service/snapshot.
- Patch/inject the fixed `Europe/London` evaluation date, including a UK DST/UTC date-boundary case; verify the same date is used by check and response.
- Adapter calls exactly one `check_purchase` and uses the fresh snapshot port, preserving closure even if service/serializer fails.
- Explicit resolved/unresolved discriminated serialization; no-match; multiple promotions and stable ordering; all five classifications; null claim window; missing percentage reward price; free gift/warranty no numeric amount; full reason/evaluation/source/provenance fields; source `verified_at=null` when allowed.
- Decimal output remains string with exact scale (e.g., `"12.50"`, never `12.5`); UUID/date/RFC3339 serialization; response OpenAPI schemas and example validation.
- Stable status/problem shape for malformed/oversized/wrong-media requests, domain validation, `PublishedPromotionDataError`, persistence failures and unexpected exceptions; errors have no internal messages or raw input.
- Optional exact-origin CORS allow/disallow and no wildcard/credential leakage if CORS configuration is added.
- Existing `backend/tests/unit/test_health.py` remains green; unrelated generic exception handling is unchanged.

### PostgreSQL integration tests

`backend/tests/integration/test_eligibility_api.py` using `postgres_container` and the **actual migrated PostgreSQL** fixture (no SQLite):

- Seed a published `active` variant with a verified primary+claim source, matching canonical brand/model/retailer, claim window, requirements and cashback; call the HTTP endpoint and verify fully projected JSON from the real repository/snapshot.
- Include `expired` published promotion with still-open claim window; confirm the distinction.
- Verify unresolved identities, resolved no-match, multiple variants, stable order and exact zero/percentage GBP handling where fixture size permits.
- Verify read-only behaviour and rollback/transaction closure; if safe/inexpensive, exercise coherent snapshot under a concurrent published-data change.
- Verify published-data integrity or storage failures never create a false successful eligibility result.

### API/application tests

- `TestClient(create_app(...))` uses existing injected settings/engine factory. Use dependency overrides or a narrow app-factory seam to inject date/service test doubles without monkeypatching domain logic.
- Assert OpenAPI `POST` path, tagged/versioned models and declared status codes. A standalone non-browser HTTP client must need only a JSON body.
- Ensure no accidental network/AI calls or DB writes on the request path.

### MCP contract tests

**N/A.** MCP is not added or changed. Future MCP must call PR 17's service and can use these transport-level fixtures for behavioural parity.

### External-boundary tests

**N/A** for outbound sources/model providers. For production gateway limits, verify integration or configuration outside this repository and record the result as a deployment prerequisite.

---

## Verification commands

Run from `backend/` with Docker available for PostgreSQL tests:

```bash
# Dependency sync (when needed)
uv sync --locked --extra dev

# Formatting check
uv run ruff format --check .

# Lint
uv run ruff check .

# Typing: no mypy/pyright task is defined in current pyproject.toml.
# Verify current repository configuration; do not invent a command.

# Targeted HTTP/API tests
uv run pytest tests/unit/test_eligibility_api.py

# Real PostgreSQL API integration tests
uv run pytest tests/integration/test_eligibility_api.py

# Existing domain/application regressions
uv run pytest tests/unit/test_purchase_check.py tests/integration/test_check_purchase.py

# Broader suite
uv run pytest

# Docker build/smoke when API packaging or startup changes
# docker build -t benefits-checker-api .
```

**Migration verification:** no new migration. Existing integration tests exercise the current migration head; use `uv run alembic upgrade head` only when preparing a real PostgreSQL test environment (the established Testcontainers fixture already applies migrations). The CI workflow may already perform the Docker build and smoke checks; verify that rather than assuming it.

If a command is unavailable, report the command, why it could not run, what was checked instead, and the remaining risk. Never claim an unrun test passed.

---

## Completion report

When implementation is finished, report:

### Changed

List route, schema/adapter, app registration, date injection, CORS/error handling (if changed), and README/OpenAPI updates.

### Database and migrations

`None` expected. Confirm snapshot read-only lifecycle and that schema remains unchanged.

### API/MCP contracts

`POST /api/v1/eligibility/check` with the v1 JSON request, discriminated success responses and problem-details errors. **MCP: None.**

### Tests and verification

List test files, exact commands actually run and results, including PostgreSQL/Docker where relevant.

### External configuration

List any exact-origin CORS values introduced, and **explicitly identify the production gateway rate/body/timeout control** or the blocking follow-up if absent. No client API secret.

### Deviations

State deviations from v1 schema, error mapping, repository wiring or security assumptions, with reason. Otherwise `None`.

### Remaining risks or follow-up

State unresolved production exposure requirements, quotas, public API compatibility/versioning risks, future CORS/frontend integration or MCP parity. Otherwise `None`.
