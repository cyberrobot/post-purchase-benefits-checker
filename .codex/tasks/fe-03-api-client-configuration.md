# FE-03 — API Client & Configuration

## Repository state

**Expected branch:**  
`fe-03-api-client-configuration`

**Base branch:**  
`main` (recheck current HEAD, open PRs, and applicable instructions before implementation).

**Dependencies:**

- FE-01 / PR #33: standalone `frontend/` Next.js App Router foundation, React 19, strict TypeScript, pnpm, Jest/RTL, build and smoke checks.
- FE-02 / PR #34: Tailwind CSS v4 design primitives, accessible shell, `RootLayout`, and Chromium/Playwright browser checks. FE-02's files are present in the inspected default-branch tree.
- Backend PR #18 and later explainability work: existing, authoritative `POST /api/v1/eligibility/check` FastAPI contract and structured problem responses.
- **No** requirement to run or alter the backend, PostgreSQL, MCP server, promotion sources, or manufacturer data during normal frontend CI. Fake upstream HTTP responses may be used for frontend integration tests.

### Read first

- `.codex/tasks/TEMPLATE.md`, repository `AGENTS.md`, and any newly introduced frontend-scoped `AGENTS.md` (verify scope; the root instructions are backend-focused).
- `.codex/tasks/fe-02-design-system-application-layout.md` and `frontend/README.md`.
- `frontend/package.json`, `frontend/pnpm-lock.yaml`, `frontend/next.config.ts`, `frontend/tsconfig.json`, `frontend/jest.config.ts`, `frontend/playwright.config.ts`.
- `frontend/src/app/layout.tsx`, `frontend/src/app/page.tsx`, existing shell components/tests, `frontend/e2e/shell.e2e.ts`, `frontend/scripts/smoke.mjs` and `.github/workflows/frontend.yml`.
- `backend/app/api/eligibility.py`, `backend/app/api/schemas/eligibility.py`, `backend/app/main.py`, `backend/tests/unit/test_eligibility_api.py`, and `backend/tests/integration/test_eligibility_api.py`.

### Primary change area

Frontend-only API transport foundation: a typed eligibility client, server-only upstream configuration, a narrowly scoped same-origin Next.js bridge, stable safe error handling, and a TanStack Query provider / opt-in purchase-check mutation. This task **does not build the purchase checker UI**.

### Canonical implementation examples

- `frontend/src/app/layout.tsx`: server root layout; preserve its server boundary and HTML/landmark structure.
- `frontend/src/app/page.tsx`: honest application placeholder; preserve no-network initial rendering.
- `frontend/src/components/layout/*`, `frontend/src/components/ui/*`: existing presentation conventions; avoid introducing duplicate state/UI foundations.
- `frontend/jest.config.ts` and `frontend/e2e/shell.e2e.ts`: existing test technologies and production browser test approach.
- `backend/app/api/schemas/eligibility.py`: **canonical** on-wire request, success union, enums, nested promotion projection, and problem schema.
- `backend/app/api/eligibility.py`: backend URL, body/media limits, headers, error codes/statuses, read-only semantics, and correlation ID behaviour.
- `backend/tests/integration/test_eligibility_api.py`: positive, unresolved and no-match reference behaviour backed by real PostgreSQL on the backend side.
- No API client, TanStack Query provider, shared HTTP error mapper, frontend authentication integration, or frontend API proxy currently exists.

### Relevant symbols

- `RootLayout`, `Home`, `QueryClient`, `QueryClientProvider`, `useMutation`, `fetch`, `Request`, `Response`, `AbortSignal`.
- FastAPI `PurchaseRequest`, `CheckResponse`, `ResolvedResponse`, `UnresolvedResponse`, `Promotion`, `Problem`, `EligibilityRoute`, `eligibility_check`.
- `POST /api/v1/eligibility/check`, response header `X-Request-ID` and content types `application/json` / `application/problem+json`.

### Expected change surface

Paths are suggested, not obligatory; adapt the exact names to the repository if needed:

```text
frontend/package.json
frontend/pnpm-lock.yaml
frontend/.env.example
frontend/README.md
frontend/src/app/layout.tsx
frontend/src/app/api/eligibility/check/route.ts
frontend/src/components/providers/QueryProvider.tsx
frontend/src/lib/api/config.ts                    # server-only upstream config
frontend/src/lib/api/errors.ts                    # safe, stable discriminated errors
frontend/src/lib/api/http.ts                      # fetch transport, decoding, timeout
frontend/src/lib/api/eligibility.contract.ts      # request/response/problem schemas and types
frontend/src/lib/api/eligibility.ts               # typed endpoint function
frontend/src/features/eligibility/api/useCheckPurchaseMutation.ts
frontend/src/**/*.test.ts(x)                      # targeted contract, transport, proxy and hook tests
frontend/e2e/api-client.e2e.ts                    # real-browser same-origin transport test
frontend/e2e/support/*                            # controlled fake HTTP upstream, if needed
frontend/playwright.config.ts                    # only if required for safe test-fixture orchestration
.github/workflows/frontend.yml                   # only if fixture wiring requires a workflow change
```

The `QueryProvider` should render **no extra DOM wrapper**, so each public page's `<main>` remains a direct child of `<body>`.

### Excluded areas

- Production homepage, checker form/results, search, saved purchases, accounts, login/session management, profile UI, claiming flows, notifications or new navigation destinations.
- Backend route changes, CORS middleware, REST/MCP schemas, deterministic eligibility rules, migrations, promotion publication, data loading or backend observability.
- Calling MCP from the web frontend; the browser uses the existing REST API.
- AI-generated eligibility decisions, speculative promotion records, arbitrary benefit statuses, or mock data shown to visitors as real.
- Generic transparent HTTP forwarding, user-configurable upstream URLs, arbitrary proxy paths, speculative GET APIs, Axios/Redux or another data-fetching library alongside TanStack Query.
- Client-side storage/persistence of purchase details, query cache persistence, devtools shipped to production, analytics capture of purchase payloads, or an authentication framework.

### Unknowns Codex must verify

1. Current branch state, recent frontend merges, existence of scoped guidance, and any newly added API/config layer.
2. Current FastAPI OpenAPI and schema fields, error response media types and exact status/error codes. Do not treat a `200 unresolved_identity` as a transport failure.
3. Whether the backend has added browser CORS or frontend authentication since this specification was written. The inspected backend did not configure CORS in `backend/app/main.py`; this spec deliberately does **not** depend on changing it.
4. Whether serverless/runtime deployment settings require a different way of providing the API origin. The selected design reads the origin **at request time**, not solely during `next build`.
5. Current Playwright server orchestration and the ability to run a deterministic local fake upstream without clashing with ports 3100/3101.
6. Compatibility of the **latest appropriate pinned** TanStack Query and runtime-validation packages with React 19, Next.js 16 and Jest. Update the pnpm lockfile; do not rely on floating dependency versions.
7. Whether backend publication/verification semantics or response enum values have expanded; mirror actual wire contracts rather than designing new eligibility outcomes.

---

## Objective

Ship a production-suitable, reusable frontend integration layer so future BenefitScout features can submit structured purchase details to the existing FastAPI eligibility endpoint, receive validated typed outcomes, and handle expected failures consistently without implementing eligibility logic in the browser.

After FE-03:

- Callers can invoke `checkPurchase(input, { signal? })` and receive a `Promise<CheckPurchaseResponse>` using the backend's existing wire contract.
- The browser calls only the **same-origin** `POST /api/eligibility/check`. A small Next.js Route Handler forwards that one operation to the configured backend `POST /api/v1/eligibility/check`. The backend origin is never included in browser bundles.
- Server-side configuration is validated and missing/bad configuration fails with a safe, predictable response **when the API route is invoked**. The existing homepage still builds and renders without a running backend or API origin.
- HTTP, network, timeout, user cancellation, invalid response and safe problem-details failures have one typed error contract.
- `QueryClientProvider` is available to client components without converting `RootLayout` or the public homepage into Client Components. A purchase-check mutation exists for a future form, but it is not invoked by default.
- Type and runtime contract tests, unit tests, proxy tests and **real Chromium transport coverage** prevent real regressions.

**Definition of done:** all acceptance criteria below pass; an unconfigured/dead backend does not break normal startup or the root page; the new transport can be exercised end-to-end against a deterministic fake upstream; and there is no new public checking UI or backend business logic.

---

## Architecture and invariants

1. **Next.js App Router remains the framework.** Keep `RootLayout` a Server Component. Add a minimal `'use client'` `QueryProvider` around `{children}`; the provider must not create an HTML element. Preserve FE-02's `body > main`, skip link, header, footer and metadata conventions.
2. **Same-origin public boundary.** Browser `fetch` targets `/api/eligibility/check`. The Route Handler owns forwarding to a single, server-configured backend host and a hardcoded `/api/v1/eligibility/check` path. The caller must not supply a URL, path, hostname, protocol or headers to influence the destination.
3. **REST is authoritative.** The frontend only sends backend-supported fields, parses the documented response, preserves explanation/provenance, and presents no inferred eligibility. `resolved` with no promotions, `unresolved_identity`, and promotions with any of the five eligibility classifications remain distinct **successful** domain outcomes.
4. **Typed and runtime-checked boundaries.** Use one coherent schema/type definition strategy (recommended: Zod schemas with inferred TypeScript types) based on the actual FastAPI wire models. Do not cast untrusted `response.json()` directly to a trusted type. Validate required fields and discriminants, while handling harmless additional response properties compatibly. Keep schemas in a transport-only module reusable outside React.
5. **No automatic purchase checks.** Provide a reusable TanStack Query mutation, not an eager `useQuery` of an empty/placeholder purchase. No request runs from initial render, focus, reconnect, hydration or provider setup. Disable retries for purchase mutations and do not persist results to browser storage.
6. **No new business state.** The API layer must not relabel missing information as `NOT_ELIGIBLE`, calculate claim dates/rewards, substitute an expired/potential status, infer source validity, or silently turn backend failures into an empty promotions array.
7. **No frontend credentials.** This PR does not introduce manufacturer or BenefitScout login. Never forward incoming cookies, browser `Authorization` headers or unrelated request headers to the backend. Future authentication requires a separate reviewed design.
8. **Testability and deterministic behaviour.** Network dependencies are injected/mocked in unit tests; integrated browser testing uses a controlled local upstream server, not external brands or a live database.

### Transport layout and dependency direction

```text
Future checker client component
  -> useCheckPurchaseMutation()          # TanStack Query, user-triggered
  -> checkPurchase(payload, {signal})    # typed client, runtime response validation
  -> HTTP POST /api/eligibility/check     # browser: same origin
  -> Next.js Route Handler               # server: constrained bridge
  -> BENEFITSCOUT_API_ORIGIN + /api/v1/eligibility/check
  -> existing FastAPI eligibility adapter and application/domain layers
```

The module containing `BENEFITSCOUT_API_ORIGIN` must use `server-only` protection (or an equivalent enforceable Next.js server-only boundary) and must never be imported by a Client Component. Transport code must not import `backend/` Python modules at runtime.

---

## API and contract changes

### 1. Browser-facing same-origin bridge: `POST /api/eligibility/check`

- **Purpose:** expose one existing backend eligibility operation to same-origin frontend code without requiring CORS changes or exposing the upstream origin.
- **Request:** `Content-Type: application/json` and JSON body matching `PurchaseRequest`:

  | Field | Wire type | Required | Rules |
  | --- | --- | --- | --- |
  | `brand` | string | yes | Existing backend text validation and max 255 characters. |
  | `model` | string | yes | Existing backend model validation and max 255 characters. |
  | `retailer` | string | yes | Existing backend text validation and max 255 characters. |
  | `purchase_date` | `YYYY-MM-DD` string | yes | Valid calendar date, not a JS `Date` timestamp. |
  | `purchase_price` | GBP decimal **string** or `null` | no | If supplied, match backend money pattern; never serialize a float. |

- The bridge passes the JSON body and a controlled `Content-Type` header through to FastAPI, with the backend ultimately validating the business input. Do not implement an alternative eligibility validator that disagrees with Pydantic. The typed caller should reject obviously malformed values before sending, using the shared contract schema.
- Apply the backend's **8192-byte body limit** at the bridge (bounded streaming read, not an unbounded `text()` followed by a length check); reject oversize requests and unsupported content types predictably.
- The upstream URL and path are fixed in server code/configuration. Support exactly `POST`; Next handles other methods as method-not-allowed. Do not add open redirects, path parameters or a generic forwarding route.
- **200 success:** forward a valid JSON response that conforms to backend `CheckResponse`. Expected discriminants:
  - `outcome: "resolved"`: `evaluation_date`, `resolved_identity`, `promotions`, `no_match_reason`, `explanation`.
  - `outcome: "unresolved_identity"`: `evaluation_date`, `unresolved_identity` (`field`, `status`, `candidate_ids`), `explanation`.
- Within `resolved.promotions[]`, preserve documented identity, `promotion_status`, `eligibility.classification`, `reasons`, `rule_evaluations`, `claim_window`, `benefits`, `requirements`, `last_verified_at`, `provenance`, `sources`, and `explanation` fields. Preserve nullable fields rather than fabricating absent values.
- Supported classifications: `ELIGIBLE`, `POTENTIALLY_ELIGIBLE`, `NOT_ELIGIBLE`, `CLAIM_NOT_YET_OPEN`, `EXPIRED`. Their semantics are entirely backend-defined.
- **Error responses:** preserve backend non-2xx `application/problem+json` format (`type`, `title`, `status`, `detail`, `code`, `request_id`) when safely parseable, including 413/415/422/429/500/503. The backend may produce gateway `429` with `Retry-After`. Preserve a safe `X-Request-ID` and bounded `Retry-After` header when present; never reflect unsafe headers.
- **Bridge-owned failures:** report safe RFC 9457-compatible problems (e.g. `503 api_not_configured` for absent/invalid origin, `504 upstream_timeout` for timeout, `502 upstream_unavailable` for connection failure or invalid upstream reply). Use a server-generated correlation/request ID where no valid upstream ID exists. Do not leak upstream hostname, network error text, credentials, tracebacks or exception payloads.
- **Idempotency:** backend purchase check is read-only; the bridge adds no persistence. Do not add blind automatic replay/retries even though the HTTP operation is logically read-only.
- **Backward compatibility:** do not alter the backend contract or reinterpret its status/outcome fields. Any public bridge-specific error codes are frontend-boundary details, not new eligibility decisions.

### 2. Typed frontend API: `checkPurchase`

- Export exact request and response types plus `checkPurchase(input: PurchaseRequest, options?: { signal?: AbortSignal }): Promise<CheckPurchaseResponse>` from a stable frontend module.
- Validate outgoing data (required strings, date, decimal string, allowed keys) and success/error responses at runtime; do not parse monetary strings into JS `number` or UTC-convert purchase dates.
- Support caller `AbortSignal` plus a finite request deadline (recommend **10 seconds** for the browser request; select/document one fixed default). Abort immediately if already aborted. Distinguish explicit cancellation from timeout.
- Send `Accept: application/json, application/problem+json`, `Content-Type: application/json`, and `cache: 'no-store'`. Do not send bearer tokens, record payloads in logs, or attach query parameters containing purchase data.
- The typed transport must preserve domain success with `200` whether zero, one or many promotions are returned; use distinct discriminants instead of a fake `eligible: boolean`.
- Return a predictable error shape (see below). All app callers should branch on typed error `kind`, not substrings of browser exception messages.

### 3. Error contract

Use an exported discriminated, safe error type/class with at least:

| Kind | Trigger | Safe caller behaviour |
| --- | --- | --- |
| `validation` | Invalid local input or upstream 413/415/422 | Display generic field/request guidance; preserve backend `code` and status if available. |
| `rate_limited` | HTTP 429 | Display retry guidance, optionally exposing parsed `retryAfterSeconds`; **no automatic retry**. |
| `unavailable` | 502/503 or network/offline failure | Offer manual retry; no empty-success fallback. |
| `timeout` | Deadline elapsed / HTTP 504 | Offer manual retry; no silent background loop. |
| `cancelled` | User/React abort | Quiet cancellation; do not present it as an eligibility result. |
| `server` | Other 5xx | Safe generic error; keep correlation ID. |
| `contract` | Unparseable JSON, wrong content type or malformed successful response | Explicit contract error; do not render or trust partial data. |

Attach known-safe `status`, `code`, `requestId` and optional `retryAfterSeconds` as appropriate, without reflecting raw server HTML or internal error strings. Unexpected HTTP 4xx should remain an error (not a domain classification). Parsing failures must not be mistaken for `unresolved_identity`.

### 4. TanStack Query integration

- Install a pinned, React-19-compatible `@tanstack/react-query`. Add the minimal client `QueryClientProvider` and a `get/createQueryClient` factory avoiding process-wide shared mutable state across SSR requests. Keep `RootLayout` server-rendered.
- Provide a typed `useCheckPurchaseMutation()` hook for future form usage. It invokes `checkPurchase` **only on explicit `mutate`/`mutateAsync`**; no request fires merely because the component renders or regains focus.
- Choose and document conservative global defaults: no automatic retry for mutations, no persistent query cache, no refetch-on-window-focus for this product's initial UI, and no speculative background purchase checks. Be explicit about mutation cancellation limitations: an `AbortSignal` may be passed to the standalone client; **do not claim that TanStack Query automatically cancels mutations**. If cancellation is exposed by the hook, explicitly own and clean up the `AbortController`.
- Do not retain raw purchase inputs beyond normal transient mutation lifecycle, write them to local/session storage, or add React Query Devtools in production. `reset()` or equivalent should allow the future UI to clear result/error state.
- Do not add unused query hooks for endpoints that do not exist. Future promotion listing/search queries belong in later PRs.

---

## Domain and application behaviour

1. Input has a specified brand, model, retailer and purchase date; `purchase_price` is optional. Passing omission is different from inventing `"0"`, and value `"0.00"` is valid and must be preserved.
2. Backend identity ambiguity is an HTTP **200** `unresolved_identity` with its own explanation and candidate IDs. Do not throw, synthesize a `NOT_ELIGIBLE` result, or substitute a `no_match_reason`.
3. A resolved result with `promotions: []` and `no_match_reason: "no_matching_published_promotions"` is a valid resolved outcome, **not** an API/network error.
4. Each promotion's eligibility, claim-window status, source URLs, verification timestamp and explanation are passed through without alteration. Null `claim_window` is not automatically `expired` or `open`. Do not derive a new classification from claim timestamps.
5. Fetch failures do not change cached or displayed statuses to a fabricated positive/negative result. After a user-initiated retry, only the next successful response supplies eligibility.
6. Time-sensitive results may change as published data and London-local evaluation date change. FE-03 does not cache purchase-check responses as reusable durable eligibility assertions; mutation retries occur only when explicitly requested by the user.
7. Treat backend JSON as untrusted. Validate relevant nested fields rather than validating only `outcome`. Keep response schemas maintainable and document how to update them when the backend's OpenAPI changes.

### Eligibility-specific rules

No new rules are allowed. The frontend must reproduce the existing transport semantics exactly; all manufacturer, retailer, date, price, claim-window, reward and provenance logic stays in FastAPI/application/domain modules. The frontend should not call an LLM to classify a purchase.

### Ingestion/publication rules

`N/A` — existing backend publication and provenance boundaries are unchanged.

---

## Persistence, transactions, and migrations

`None`. No PostgreSQL/Alembic changes. No Next.js/edge KV, browser local storage, IndexedDB or persisted Query cache. Purchase checking remains a read-only backend operation.

---

## External services and network access

### Browser -> Next.js

- Fixed relative path: `/api/eligibility/check`, method POST, same origin.
- Browser `fetch` must have a bounded deadline, support explicit abort, not cache responses and not retry automatically.
- Avoid assuming a cross-origin FastAPI deployment is directly browser-accessible.

### Next.js -> FastAPI

- Only configured origin from `BENEFITSCOUT_API_ORIGIN`, fixed suffix `/api/v1/eligibility/check`.
- Use Node.js runtime for the Route Handler (`runtime = 'nodejs'` if needed), a bounded upstream timeout (recommend **8 seconds**, shorter than the browser deadline), no automatic retry, `cache: 'no-store'` and no response caching by Next.js.
- Forward only the validated/bounded request bytes and whitelisted headers. Do not forward browser cookies, authorization, arbitrary proxy headers or user-provided hostnames. Limit request size at the earliest feasible boundary.
- Forward allowlisted upstream `Content-Type`, `X-Request-ID`, and safe `Retry-After` when relevant; do not blindly copy `Set-Cookie`, `Location`, CORS or hop-by-hop headers.
- For non-JSON/invalid upstream responses, produce a safe bridge-owned error; never forward a traceback or HTML error document verbatim.
- Tests use fake `fetch` for route units and a local HTTP fixture for real end-to-end browser transport; the test suite must run without PostgreSQL or live manufacturer services.

---

## Security and privacy

- `BENEFITSCOUT_API_ORIGIN` is server-only. No `NEXT_PUBLIC_BACKEND_URL` or exposed production host/config object. **No frontend secrets** or backend credentials are introduced.
- Validate the server origin using the URL parser: allow only `http:`/`https:`, require an explicit hostname, disallow embedded username/password, non-root path, query and fragment. For production, require HTTPS; local plain HTTP may be used for local development/test. Reject invalid config safely rather than sending traffic to an arbitrary origin. The route must not accept destination input from users.
- The bridge is **not** an open proxy and must not forward untrusted headers or cookies. Hardcode the permitted upstream route and method.
- Enforce JSON media type, bounded body size, bounded outbound timeouts and safe response parsing. Do not log brand/model/retailer/purchase date/price, entire response bodies, customer identifiers, tokens or arbitrary query parameters.
- Only return known-safe error details and correlation IDs; never expose env contents, upstream error messages, internal network addresses or stack traces.
- The backend currently exposes a read-only public check. Do **not** invent client-side authorization as security. Account integration and any future authenticated operations need a separate reviewed task.
- `application/problem+json` is machine-readable error data, not automatically safe display copy; caller UI must choose human-readable, non-sensitive messages.
- Tests must cover oversized bodies, invalid content types, unexpected headers, missing configuration, hostile origin formats, network failures and malformed upstream responses.

---

## Configuration and deployment

### Environment variables

| Variable | Read by | Required | Secret | Default / failure behaviour |
| --- | --- | --- | --- | --- |
| `BENEFITSCOUT_API_ORIGIN` | Next.js server Route Handler only | Required **for live purchase checks**, not for building/rendering `/` | No, but server-only | No implicit production default. Missing/invalid at invocation returns a safe 503 problem. Development example: `http://127.0.0.1:8000`. |

- Add `frontend/.env.example` with documentation only (no live credentials). Keep `.env*` ignored except `.env.example` using the existing `.gitignore` rules.
- Validate at request time or in a lazily invoked server-only config getter; no module-import throw that prevents `pnpm build`, smoke or the public homepage from working without backend configuration.
- Do not use `NEXT_PUBLIC_*` for the backend origin, and do not rely on build-time-only `rewrites` expansion for a runtime-configured backend. Deployment must provide the origin to the **Next.js server runtime**.
- Do not modify backend `DATABASE_URL`, MCP environment, Railway service secrets, authentication or backend CORS settings.

### Runtime/deployment changes

- Next.js must have server runtime support for the Route Handler; this architecture is **not** compatible with purely static export without a redesign.
- Update README with: local backend startup prerequisites if exercising live checks; server env setup; expected behaviour without env; how to call the check endpoint manually; no-browser-CORS explanation; safe failure/timeout diagnostics; and limitations of the still-placeholder homepage.
- `pnpm build`, `pnpm smoke`, homepage unit tests and FE-02 browser shell tests must continue to pass **without** `BENEFITSCOUT_API_ORIGIN`.
- Add only necessary npm package/runtime changes to the checked-in lockfile; avoid changing Node 24, pnpm 10.34.7, Next.js, React or unrelated dependency versions.

---

## Observability and operations

- Preserve backend `X-Request-ID` on successful and problem responses when valid; generate a safe bridge request ID if upstream has none. Surface it on typed client errors for support correlation.
- Server-side bridge logs may record operation name, status, elapsed time, sanitized error kind and request ID; **never** record purchase payload contents or a full upstream response.
- Client errors should be actionable (`validation`, `rate_limited`, `unavailable`, `timeout`, `cancelled`, `server`, `contract`) without unfiltered exception messages or noise from expected cancellations.
- Reuse existing deployment logging infrastructure; do not add Sentry SDK, analytics or a second metrics stack for this foundational PR.
- Do not change backend health checks. If a lightweight future status indication is desired, keep it out of this PR: the new client route must not make `/` dependent on backend uptime.

---

## Failure, consistency, and recovery

| Scenario | Required behaviour |
| --- | --- |
| No configured API origin / invalid origin | Browser receives a safe, structured 503 from bridge. `/` still works and production build remains independent. |
| Backend unreachable, DNS/connect/TLS error | Stable unavailable/502 error, no hostname/body leakage, no automatic retry. |
| Backend slow / deadline exceeded | Bounded abort and safe 504/timeout classification; no hanging request. |
| User cancels browser request | Abort is distinguishable from timeout; no manufactured eligibility result. |
| FastAPI returns 422 with a problem body | Preserve safe code/status/request ID; present validation category, no success payload. |
| Gateway/backend returns 429 with `Retry-After` | Preserve safe retry hint, do not automatically replay personal purchase data. |
| Backend returns HTTP 200 `unresolved_identity` | Resolve normally as domain success; consumer can inspect `outcome`. |
| Backend returns HTTP 200 resolved with zero promotions | Resolve normally with `no_match_reason`; not treated as a network failure. |
| Upstream returns HTML/empty/malformed JSON or violates contract | Fail closed as `contract`/safe 502; never cast or display untrusted partial object as valid eligibility. |
| Request is repeated intentionally | Independent read-only checks; no frontend persistence or fabricated deduplication. |
| Initial render, focus or reconnection | No purchase-check request until explicit mutation. |
| Query provider rerender/SSR hydration | Stable client instance, no additional wrapper element, no cross-request singleton data leakage. |

---

## Acceptance criteria

### Behaviour

- [ ] `checkPurchase` accepts the actual backend purchase contract and returns the exact discriminated `resolved` / `unresolved_identity` success union.
- [ ] Purchase price is a decimal **string** (`"0.00"` accepted), purchase date is a date-only string, omitted price stays omitted, and unsupported fields are rejected by typed/request validation.
- [ ] Every documented promotion property needed for later results/explainability is preserved and validated, including nullable fields and provenance.
- [ ] A `200` unresolved identity and a `200` zero-promotion result are **not** treated as HTTP errors.
- [ ] Browser traffic uses only the same-origin endpoint; the backend origin is not embedded in browser JavaScript.
- [ ] Root layout remains a Server Component; the root page remains an honest placeholder and makes no backend request.
- [ ] A client component can use `useCheckPurchaseMutation()` on explicit submission, with typed success/error states and no automatic background replay.
- [ ] Request cancellation and timeout are distinct, documented and testable.

### Data and consistency

- [ ] No server or browser data persistence, cache persistence, database migration or business-state changes are added.
- [ ] No eligibility, reward, claim-window, source-status or manufacturer rules are implemented or overridden in the frontend.
- [ ] The current backend schema and sample responses have regression fixtures to expose drift.

### Security

- [ ] Runtime-only server environment configuration rejects invalid origins and does not leak values or break public build when unset.
- [ ] Bridge has a fixed path/method, JSON-only media type, bounded body, whitelisted headers, explicit timeout and no cookie/auth forwarding.
- [ ] Non-JSON upstream errors, credentials, internal hostnames, traces and full purchase payloads never leak to the browser or logs.
- [ ] No generic proxy, arbitrary URL fetching, new account/auth machinery or browser storage of purchase payloads.

### Operations

- [ ] Structured failure categories and request correlation are consistently available to future UI.
- [ ] Backend unavailable/not configured does not break homepage SSR, production build, production smoke or shell browser tests.
- [ ] Timeout, rate limit, 4xx/5xx, invalid JSON/contract and connection failure paths are deterministically covered.

### Code quality

- [ ] A single typed fetch/contract/error approach is used (not ad hoc endpoint implementations).
- [ ] Dependencies are pinned via the existing pnpm lockfile; no conflicting state/fetching library is introduced.
- [ ] `pnpm format:check`, `pnpm lint`, `pnpm typecheck`, `pnpm test`, `pnpm build`, `pnpm smoke` and `pnpm test:e2e` pass.
- [ ] New browser transport tests run against the real production Next.js server and a controlled upstream; unit tests alone are insufficient.
- [ ] README and `.env.example` explain setup and the boundary without suggesting the checker UI has already shipped.

---

## Tests to add or update

### Unit tests

Use colocated Jest/RTL tests, with stable mocked clocks/fetches and no real upstream:

1. **Contract tests** (`src/lib/api/eligibility.contract.test.ts`): valid full resolved promotion with sources, claim window, nullable reward fields, reason/rule evaluations and timestamps; resolved no-match; unresolved identity; missing/incorrect discriminator; missing required nested field; wrong enum; malformed dates/prices; `"0.00"` and omitted price; schema compatibility with harmless additive fields. Derive fixtures from `backend/app/api/schemas/eligibility.py` and `backend/tests/.../test_eligibility_api.py` rather than inventing an incompatible mock envelope.
2. **HTTP/error tests** (`src/lib/api/http.test.ts` or endpoint-specific tests): correct POST URL, body and headers; 200 successful parse; 413/415/422 problem; 429 `Retry-After`; 500/503; unexpected 4xx; network failure; timeout; explicit `AbortError`; invalid JSON; wrong content type; malformed 200 schema; error retains safe request ID; no automatic retries; no request/response logging of sensitive payloads.
3. **Server config tests** (`src/lib/api/config.test.ts` in server-compatible Jest context): valid local HTTP / production HTTPS origins; unset origin; invalid protocol, username/password, query, fragment, non-root path, production HTTP. Verify no top-level dependency on configuration during homepage imports/build.
4. **TanStack Query tests** (`src/components/providers/QueryProvider.test.tsx`, `src/features/eligibility/api/useCheckPurchaseMutation.test.tsx`): provider preserves child markup and client context; no request on mount, rerender or fake focus/reconnect; explicit mutation performs one call; success discriminants remain exact; errors propagate; deliberate second invocation works; `reset` clears state; no automatic retries. Do not claim a mutation is automatically abortable without explicit hook logic.

### PostgreSQL integration tests

`N/A` — backend persistence and migrations are unchanged. Backend's existing tests provide authoritative data-boundary evidence.

### API/application tests

- **Route Handler unit tests** (`src/app/api/eligibility/check/route.test.ts`): mocked upstream asserts fixed backend path and method, controlled forwarded JSON/headers, bounded inbound body, successful body/header preservation, upstream RFC 9457 problems, fake `429`, timeout, connection error, invalid/non-JSON/HTML response, missing/bad env, safe correlation ID, and no forwarding of incoming cookie/authorization/host headers. Test the handler directly without needing PostgreSQL.
- Explicitly test that upstream failures do not return a `200` with empty promotions and that no request with unbounded body or user-controlled URL is sent.
- If an implementation chooses a helper separate from the Route Handler, test both helper contract and real handler invocation to catch integration wiring errors.

### MCP contract tests

`N/A` — no MCP change. Browser must not call `/mcp`.

### External-boundary and browser tests

- **Real Chromium test** (`frontend/e2e/api-client.e2e.ts`): start existing production Next.js test server and a deterministic local HTTP upstream fixture using unique/managed ports. Configure the server with `BENEFITSCOUT_API_ORIGIN` at **runtime**. From a real browser document on `/`, use `fetch('/api/eligibility/check', {method:'POST', ...})` and assert the upstream receives the correct request and the browser receives the expected status/body/header. This exercises actual browser origin policy, Next.js routing and server transport without inventing a feature UI.
- Cover at least **one** successful `resolved` response, **one** successful `unresolved_identity` response, and **one** backend problem (such as 422 or 429). Include a separate genuine upstream-unavailable path when feasible. Do not obtain these responses from `page.route()` alone; the browser request should traverse the real Next.js Route Handler to the fake upstream.
- Keep the existing shell/browser accessibility and responsive tests intact, and run them together with the new transport test. Test fixtures must not require Internet access, database credentials, or a live brand API.
- If Playwright's production server is already configured, extend the existing setup without adding a globally running process or leaking mock-only behaviour into production routes. Ensure ports are released on failure; CI diagnostics remain available.

---

## Verification commands

Run from the repository root unless otherwise noted; these commands are present in the inspected `frontend/package.json` / workflow:

```bash
# Use Node 24.22.0 and pnpm 10.34.7 according to frontend/.node-version/package.json.
cd frontend
pnpm install --frozen-lockfile

# Formatting, static checks and targeted tests
pnpm format:check
pnpm lint
pnpm typecheck
pnpm exec jest --ci --runInBand src/lib/api src/features/eligibility/api src/components/providers src/app/api/eligibility/check

# Full unit coverage and production behaviour
pnpm test
pnpm build
pnpm smoke

# Full production Chromium suite, including FE-03's real transport test
pnpm exec playwright install chromium
pnpm test:e2e
```

The new Jest directories must match the actual files created; adjust the targeted command if paths differ. FE-02 browser tests use the existing Playwright config / production server on loopback port 3101; the separate smoke service uses 3100. If the fake upstream fixture requires new orchestration, document its port allocation and start/stop behaviour, and ensure it does not accidentally require a production backend env value for ordinary smoke checks.

**No** backend pytest, PostgreSQL Testcontainers, Alembic or MCP commands are required for the frontend-only change. Do not claim tests passed until they have actually run. When a test cannot run, record the exact command, blocker, alternative validation and remaining risk; never suppress failures merely to make CI green.

---

## Completion report

Upon implementation, provide:

### Changed

List the typed client, schemas, error handling, server bridge, server-only config, TanStack Query provider/hook, docs and any test wiring actually added.

### Database and migrations

`None` expected.

### API/MCP contracts

- New **frontend-facing** `POST /api/eligibility/check`, with its mapped upstream route and error envelope.
- New TypeScript client and error contracts.
- **No** backend REST or MCP contract change expected.

### Tests and verification

Report exact new/updated tests, shell/browser acceptance evidence, and the actual pass/fail results of each command. Explicitly state whether the Chromium test reached the fake upstream through the real Route Handler.

### External configuration

Document the `BENEFITSCOUT_API_ORIGIN` runtime value required for live checks, permitted protocols and local setup; no new secrets or `NEXT_PUBLIC_*` variables expected.

### Deviations

State `None`, or explain any justified change to the bridge design, runtime schema strategy, timeout policy, or browser fixture arrangement. Do not silently replace server-only bridging with cross-origin browser fetch or pretend an absent backend CORS policy is harmless.

### Remaining risks or follow-up

- Actual checkout form/results UX, accessible error presentation and manual retry belong to the next FE feature PR.
- Real deployment origin, gateway limits/rate limiting and auth may require separate infrastructure/security review.
- OpenAPI/response schema drift must be checked when backend contracts evolve; no new eligibility semantics are authorised here.
- No promotion listing/search endpoint or account system is added by this task.

---

## Scope guardrail for reviewers

**Approve FE-03 for reliable, secure integration boundaries—not for a working purchase-checking interface.** The homepage must continue to say checking is unavailable until a later feature PR provides a real user-facing flow. A successful `200` unresolved identity or no-match result must never be rendered as a network error or rewritten into an eligibility verdict. Tests that merely mock a client function without exercising the production Next.js bridge and its browser origin behaviour are not sufficient.
