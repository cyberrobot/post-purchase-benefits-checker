# FE-05 — Purchase Check Integration

## Repository state

**Expected branch:**  
`fe-05-purchase-check-integration`

**Base branch:**  
`main` (verify current HEAD and outstanding PRs before starting implementation).

**Dependencies:**

- FE-01 / PR #33: Next.js 16 App Router, React 19, TypeScript, Tailwind v4, pnpm, Jest and CI.
- FE-02 / PR #34: layout, semantic tokens, Button/Card/Container, accessible navigation and Playwright conventions.
- FE-03 / PR #35: `checkPurchase`, Zod wire schemas, `ApiError`, `useCheckPurchaseMutation`, QueryProvider and existing same-origin `/api/eligibility/check` route.
- FE-04 / PR #36: **Already implemented** four-field `PurchaseInputForm` on `/` with form validation, explicit API submission, pending-state guard, minimal response messages and tests. Extend; do not duplicate.
- Backend PR #18 and explainability: authoritative FastAPI `POST /api/v1/eligibility/check` and structured deterministic eligibility outcomes.
- **Visual reference:** attached `Screenshot 2026-10-20 at 11.50.14.png`. Important: the purple **Find My Benefits** CTA in the image is shown **on hover**, not in its default state.

### Read first

- `.codex/tasks/TEMPLATE.md`, `AGENTS.md`, and any new frontend-scoped `AGENTS.md` (none was found at review time).
- `.codex/tasks/fe-02-design-system-application-layout.md`, `.codex/tasks/fe-03-api-client-configuration.md`, `.codex/tasks/fe-04-purchase-input-form.md`, and `frontend/README.md`.
- `frontend/src/app/{page,layout,globals.css}`, `frontend/src/components/ui/{Button,buttonStyles,Card,Container}.*`, and existing site layout components.
- `frontend/src/features/eligibility/components/PurchaseInputForm.tsx` and its tests.
- `frontend/src/features/eligibility/api/useCheckPurchaseMutation.ts`, `frontend/src/lib/api/{eligibility.contract,eligibility,errors,http,config}.ts`, and `frontend/src/app/api/eligibility/check/route.ts`.
- `backend/app/api/schemas/eligibility.py`, `backend/app/api/eligibility.py`, and relevant backend tests solely to verify contracts.
- `frontend/e2e/{purchase-input,api-client,shell}.e2e.ts`, `frontend/e2e/support-upstream.mjs`, `frontend/playwright.config.ts`, `frontend/package.json`, and frontend CI.
- The supplied image as UX reference; it is not a production asset.

### Primary change area

A dedicated `/check` page reusing the existing purchase form and FE-03 mutation, with screenshot-informed field states and responsive layout, optional **supported** purchase price, loading/error interaction and classification-aware summaries of the real backend response. The existing `/` checker must keep working.

### Canonical implementation examples

- `PurchaseInputForm`: currently uses `purchaseRequestSchema.safeParse`, `validatePurchase`, a synchronous `inFlight` ref, local pending state, field-error descriptions, first-invalid focus and safe `completion`/`failure` summaries.
- `useCheckPurchaseMutation`: explicit TanStack mutation with `retry: false`, `networkMode: 'always'`; never introduce an eager query.
- `checkPurchase`: typed fetch to `/api/eligibility/check`; Next route handler forwards to FastAPI using server-only `BENEFITSCOUT_API_ORIGIN`.
- `eligibility.contract.ts`: authoritative frontend runtime request/response schemas; backend Pydantic request/response is ultimate source of wire truth.
- `frontend/src/app/page.tsx`: existing Server Component and one `main` / one `h1` convention.
- `frontend/src/components/ui/buttonStyles.ts`: primary button defaults to navy/ink, secondary is violet; currently hover underlines only.
- `frontend/e2e/support-upstream.mjs`: controlled fake HTTPS backend with no-match, unresolved model, populated, rate-limited and unavailable cases.

### Relevant symbols

`PurchaseInputForm`, `validatePurchase`, `Home`, `RootLayout`, `Button`, `buttonStyles`, `checkPurchase`, `useCheckPurchaseMutation`, `purchaseRequestSchema`, `calendarDateSchema`, `PurchaseRequest`, `CheckPurchaseResponse`, `checkPurchaseResponseSchema`, `ApiError`, `ApiErrorKind`, `CLIENT_TIMEOUT_MS`, `POST /api/eligibility/check`, `POST /api/v1/eligibility/check`.

### Expected change surface

Paths are guidance, not a requirement for gratuitous files:

```text
.codex/tasks/fe-05-purchase-check-integration.md
frontend/src/app/check/page.tsx
frontend/src/app/check/page.test.tsx
frontend/src/app/page.tsx                         # minimal changes only
frontend/src/app/page.test.tsx
frontend/src/features/eligibility/components/PurchaseInputForm.tsx
frontend/src/features/eligibility/components/PurchaseInputForm.test.tsx
frontend/src/features/eligibility/components/*    # optional pure response-summary helpers/tests
frontend/src/components/ui/buttonStyles.ts        # only if a shared CTA hover rule is appropriate
frontend/e2e/purchase-check.e2e.ts
frontend/e2e/purchase-input.e2e.ts                 # retain regression coverage
frontend/e2e/support-upstream.mjs                  # extend real wire-format fixtures
frontend/e2e/shell.e2e.ts
frontend/scripts/smoke.mjs                        # route coverage, if useful
frontend/README.md
```

### Excluded areas

- Backend, persistence, seed data, migrations, MCP, REST/OpenAPI contract changes, eligibility business rules, reference lookup/search APIs or new upstream transport.
- Hardcoded manufacturer or retailer identity/authorisation catalogues. The image depicts dropdowns, but the reviewed frontend has **no real options API**. Preserve honest free-text inputs until that feature exists.
- Purchase **channel** and **condition** fields: the current backend request supports neither. Do not display inert controls or send unsupported properties.
- Full results page, individual promotion cards, claim links/workflows, extended source/provenance detail, registration/authentication, saved purchases, receipt upload or marketing redesign.
- New form libraries, global stores, duplicate API clients, client-side eligibility, automatically retried requests, analytics containing purchase data or browser persistence.

### Unknowns Codex must verify

1. Current branch/merge state, latest FE-04 implementation, frontend-scoped guidance, and whether a `/check` route was introduced since review; at review time `/check` did not exist and `/` contained the checker.
2. Whether `PurchaseRequest` still contains only `brand`, `model`, `retailer`, `purchase_date` and nullable optional `purchase_price`.
3. Whether any supported manufacturer/retailer options API or optional channel/condition wire fields were added. Do **not** guess.
4. Any FE-04 homepage, field-label or browser assertions that must be deliberately updated rather than deleted.
5. Date policy: current backend/Zod wire schema accepts all real ISO calendar dates, including future dates; the screenshot says purchase date is **up to today**. Implement that as an explicit **frontend product UX restriction**, not a change to shared API validation, unless current product requirements contradict it.
6. Existing design tokens and browser accessibility conventions, especially current primary button default/hover appearance.
7. Whether `BENEFITSCOUT_API_ORIGIN` is configured in the target environment. Lack of a backend is an error state, not no matching promotions.

---

## Objective

Users can visit `/check`, enter or correct manufacturer/brand, model/SKU, retailer and purchase date, optionally provide a GBP purchase price, receive actionable validation feedback, explicitly submit a single purchase check, follow its loading state and distinguish every supported backend response and error state **without invented offers or eligibility logic**.

FE-04 already does basic validation, posting, pending and minimal response messaging. FE-05 must produce **observable additional functionality**: a canonical `/check` route, better screenshot-informed presentation and accessibility, optional supported price entry, classification-aware response summaries, robust stale-response handling, and expanded production-browser acceptance tests. Keep the root-page checker useful through shared code (it may continue rendering the same component and link to `/check`; do not create separate implementations).

**Done:** a genuine request from `/check` traverses the existing typed mutation and same-origin proxy, returning truthful result feedback or recoverable errors. No account is required; no backend/DB changes; all existing frontend CI and browser coverage remain valid.

### Visual intent and interaction reference

- Desktop two-column grid: row 1 **Manufacturer / Brand** and **Product model or SKU**; row 2 **Retailer** and **Purchase date**. On narrow screens, one column in the identical reading/tab order.
- Use persistent visible labels, required markers, spacious rounded controls and reserved helper/error space. Do not rely on placeholders for accessible names.
- An invalid model/SKU should show a contrasting border and adjacent readable error (as in reference), with `aria-invalid` / `aria-describedby` and focus on the first invalid field after submission.
- The green `Valid` labels in the reference must **not** imply a manufacturer, retailer or model was recognised by the backend. If local validity markers are added, show them only after user interaction, and label them **Format valid** or equivalent. A local syntactically valid brand can still be `unresolved_identity`.
- Do **not** fake screenshot dropdowns: manufacturer and retailer are free text until backed by a trusted search/catalogue endpoint. Do not restrict users to Samsung or Currys.
- The **Find My Benefits** CTA defaults to **navy/ink** (the existing primary style). Its **hover** state is **violet/purple**. Keep a highly visible keyboard focus ring and appropriate disabled/busy appearance; do not make purple the resting style or make hover the only feedback.
- On desktop, place the CTA right-aligned after the optional section. On mobile, full-width CTA with a comfortable touch target.
- Use a disclosure such as **Add optional purchase price**. It may expose the supported `purchase_price` field, but must not say **price, channel & condition** or collect unsupported properties.
- Supporting copy can state **No account required** and **Checked against published promotion data**, but must not imply guaranteed cashback, current claimability or official verification beyond the backend response.
- Reuse FE-02 Tailwind tokens, warm-white/card/navy/violet palette, spacing and reduced-motion behaviour. Screenshot is guidance, not a demand for pixel-copying.

---

## Architecture and invariants

1. **Single network path:** `PurchaseInputForm` -> `useCheckPurchaseMutation` -> `checkPurchase` -> same-origin `POST /api/eligibility/check` -> Next route handler -> FastAPI. No second mutation, client or direct browser/backend call.
2. **Server/Client boundaries:** `frontend/src/app/check/page.tsx` remains a Server Component, with direct-child `<main id="main-content" tabIndex={-1}>`, exactly one `h1`, and a narrowly scoped client form. Root layout remains server-rendered, with skip link, QueryProvider (no DOM wrapper), header and footer.
3. **Wire validation:** use existing `purchaseRequestSchema`, `PurchaseRequest` and error types; keep backend authoritative. Additional **form-only** date-to-today policy must not modify or silently narrow the shared REST/Zod contract.
4. **Determinism:** the frontend does not decide eligibility, match identities, evaluate retailer restrictions, calculate claim windows or invent reward values. All classifications come from backend response objects.
5. **One intentional submit:** no fetch on load, typing, blur, focus, navigation prefetch or reconnect; preserve the synchronous in-flight guard and non-retrying mutation.
6. **Ephemeral values:** keep draft, responses and errors in component/mutation state. Do not put purchase details in URLs, localStorage, sessionStorage, cookies, telemetry or a persisted query cache.
7. **No stale assertions:** editing a field clears its previous result/error synchronously; pending state blocks duplicate submissions; after route unmount no late response should appear.
8. **Exact request keys:** send the four required backend keys, plus `purchase_price` *only when supplied and valid*. Never send a fabricated `0`, condition/channel, JS Date/timestamp or normalization that changes SKU meaning.
9. **Errors aren't results:** 503, 502, malformed 200, timeouts and 429 never render as `no_matching_published_promotions`.

---

## API and contract changes

**None.** Reuse existing FastAPI/Next/Zod wire contracts. FE-05 does not add an API, response classification, auth contract or MCP tool.

### Request mapping

| Displayed field | Wire key | Rule |
| --- | --- | --- |
| Manufacturer / Brand | `brand` | Required, valid identity text, editable free text |
| Product model or SKU | `model` | Required, retain exact meaningful SKU punctuation/case |
| Retailer | `retailer` | Required, editable free text; never assert authorisation from input alone |
| Purchase date | `purchase_date` | Required, `YYYY-MM-DD` wire calendar date; no JS timezone conversion |
| Optional purchase price (GBP) | `purchase_price` | Optional decimal string such as `799.99`; omit entirely if blank |
| Purchase channel / condition | N/A | Unsupported: do not send or silently ignore user input |

Validate date with the shared calendar schema, plus screenshot-driven **no future purchase date** as a UI rule using today's `Europe/London` date, not UTC. Leap years and midnight boundaries need tests. This policy must be documented so it does not silently change shared contract semantics. Optional money uses a decimal string, never binary float or a guessed currency conversion. Preserve backend-supported regex and max length; reject ambiguous thousands/currency formatting rather than guessing.

### Response mapping

`200 OK` always contains an explicitly typed domain response, not a generic Boolean success:

| Backend result | Frontend summary / action |
| --- | --- |
| `unresolved_identity`, `status: not_found` | Could not identify the named `brand`, `model` or `retailer`; prompt correction; **not** ineligibility |
| `unresolved_identity`, `status: ambiguous` | Multiple identities match; ask for a more specific field; do not expose candidate UUIDs as names |
| `resolved`, empty `promotions`, `no_match_reason: no_matching_published_promotions` | No matching **published** promotions found for these details; do not state the purchase is definitively ineligible everywhere |
| `resolved`, nonempty `promotions` | Count/group each real promotion by its reported classification; no blanket “eligible benefits found” |
| `ELIGIBLE` | Meets **recorded** eligibility rules; not an approved/paid claim |
| `POTENTIALLY_ELIGIBLE` | May qualify; more evidence/information could be required |
| `NOT_ELIGIBLE` | Does not meet recorded rules |
| `CLAIM_NOT_YET_OPEN` | Claim period has not opened, without fabricating an opening date |
| `EXPIRED` | Claim period has expired, without fabricating deadlines |

Some responses contain multiple promotions of *different* classifications; counts must be correct and none can be omitted because it is less favourable. Do not invent a top-ranked winning promotion. Claim-window status and rule eligibility classification are distinct. Show short factual summaries in FE-05; detailed promotion cards, claims, benefits, source panels and URLs belong to a later result-page feature. Server-provided explanation text, if used, must be displayed as escaped plain text, not HTML.

### Error mapping

Preserve current `ApiError` kinds and the existing RFC-compatible problem-details boundary:

- `validation` / 413, 415, 422: actionable correction, without guessing a particular field not identified by the server.
- `rate_limited` / 429: safe text for bounded valid `Retry-After` or generic wait advice; **no automatic retry**.
- `timeout` / 408, 504, `cancelled`: incomplete check; retain values and offer explicit retry.
- `unavailable` / 502, 503 and `server` / 5xx: checker/service problem, **not** no matches; manual retry.
- `contract`: unexpected content type, invalid JSON, invalid 200 schema, unsafe upstream data: safe generic failure; never render partial records.
- Include a validated `requestId` as a user-facing support reference where present, not raw exception/HTTP bodies, backend hostname, SQL, stack trace or unsafe `detail`.

---

## Domain and application behaviour

### Validation and interaction state machine

Implement/test **pristine**, **editing**, **invalid**, **submitting**, **unresolved identity**, **no published match**, **classified results**, and **transport failure**.

1. **Initial:** empty draft; visible required labels; no premature red errors, green `Valid`, result message or network request.
2. **Invalid submit:** stop the native submit, set field errors, commit descriptions, focus the first invalid field, announce error and make zero requests.
3. **After attempted validation:** update/clear field errors as user corrects them; use field labels/helper/error IDs, `aria-invalid` and readable message. Editing clears old check response and transport failure.
4. **Dates:** accept real calendar dates including leap days; reject impossible dates and dates after today's UK date at the UI; serialize raw `YYYY-MM-DD` calendar date. Do not change `calendarDateSchema` or backend date parsing.
5. **Price:** collapsed by default; if empty, omit; if present, validate GBP decimal format; never use `Number`, floats or a synthetic default for wire money.
6. **Valid submit:** snapshot validated values once, guard rapid clicks/Enter events synchronously, announce **Checking your purchase…**, disable fields/CTA while pending and maintain visible non-jumpy progress.
7. **Success:** render the discriminated backend result accurately, including distinct identity correction vs genuine no published match vs per-classification counts. Preserve all draft values.
8. **Failure:** render a visible `role=alert` recoverable message, re-enable controls, preserve draft and allow **manual** retry only.
9. **New edit/check:** clear stale results as soon as values change; prevent old response being presented under the corrected details; no API call until explicit resubmit.
10. **Focus/tab order:** manufacturer -> model -> retailer -> date -> optional disclosure (+ price only when open) -> submit; no icon-only controls, traps or nested forms.

### Eligibility-specific rules

Only backend classifications, `evaluation_date`, reasons, rule evaluations, claim-window data and provenance are authoritative. Do not transform `unresolved_identity` into `NOT_ELIGIBLE`, infer eligibility from the product/retailer name, calculate current claimability or use machine-generated claims. Show dates, prices, source freshness or reward figures only when explicitly available in a response. Detailed explainability UI is out of scope.

### Ingestion/publication rules

**N/A.** FE-05 neither seeds reference entities nor ingests/promotes source material. Published promotion data is only accessed through the existing check response.

---

## Persistence, transactions, and migrations

**None.** No PostgreSQL schema changes, migration, cookie/session state, saved history or browser storage. Frontend browser tests run against the established deterministic HTTP fake upstream, not a new database fixture.

---

## External services and network access

- Reuse only existing browser -> same-origin Next proxy -> configured FastAPI route.
- Preserve `frontend/src/lib/api/http.ts` bounds: **10-second client timeout** and **8-second upstream timeout** when inspected, bounded response sizes, schema/media-type validation, no-store, and cancellation. Recheck current values before implementation.
- Respect `retry: false` and existing non-replaying mutation. Never add nested retry loops.
- No external manufacturer URLs, image services, login providers or AI calls.
- In CI use existing `frontend/e2e/support-upstream.mjs` over the production Next app; test service-down, 429, invalid response and proper success domain outcomes deterministically. Do not depend on live manufacturer sites.

---

## Security and privacy

- No account/auth addition. Browser only sends strictly supported typed fields to a fixed same-origin route.
- Render untrusted response strings with React escaping; no `dangerouslySetInnerHTML`, unsafe dynamic links or evaluation of remote rules.
- Do not leak raw backend origin, secrets, stack trace, SQL, unsafe error detail, identity candidate IDs or purchase data into logs/telemetry/URLs.
- Display only validated opaque request IDs for diagnostics.
- `Valid` is **local format validity**, not official product/retailer recognition. In particular do not assert “Authorised UK retailer” until backend evidence/API supports that claim.
- Provide persistent labels, accessible descriptions, role=status/alert, visible focus, error semantics beyond colours, keyboard access, reduced-motion and responsive reflow.

---

## Configuration and deployment

### Environment variables

**None new.** Keep existing **server-only** `BENEFITSCOUT_API_ORIGIN` and existing config validation. It is required for live checks, but should not be required to render or build `/check`. Do not add `NEXT_PUBLIC_*` secrets or exposed backend addresses.

### Runtime/deployment changes

Add a public Next.js App Router `/check` page. Preserve `/` and header/skip-link conventions; do not introduce middleware, auth, workers, queue, database connection or another deployment unit. Keep pinned Node.js/pnpm/framework versions and existing CI.

---

## Observability and operations

- Clear client UX distinction: pending vs domain no-match vs unresolved vs classified vs transport failure.
- Preserve X-Request-ID handling across the proxy; optionally surface safe ID on failure for support.
- Use existing operational diagnostics without adding purchase-payload logging, new telemetry stack or a mandatory analytics SDK.
- A backend 503 (e.g. API unavailable or unconfigured) must be a recoverable service error, never a synthetic empty list or success.
- Do not claim promotion/source freshness without explicit response evidence.

---

## Failure, consistency, and recovery

- **Validation fails:** zero calls, first invalid field focused, values preserved.
- **Duplicate submit:** one in-flight request and one final result, no queued duplicates.
- **Slow request:** progress remains visible; bounded timeout eventually becomes recoverable error.
- **Offline / invalid API config / 503:** failure message and manual retry; no “no matches” substitute.
- **200 unresolved:** correction guidance based on real unresolved field/status.
- **200 no published match:** truthful information with no inference of universal ineligibility.
- **200 mixed results:** count actual classification groups, without erasing negative/expired records.
- **Malformed 200:** contract error, no untrusted partial render.
- **Editing after result:** immediately clear old result/error; no new fetch until submit.
- **Route change/unmount:** no persistent state, result replay or background retry.

---

## Acceptance criteria

### Behaviour and UX

- [ ] `/check` exists and renders one server-owned `main`, one `h1` and shared real purchase form; it can initially load without backend configuration.
- [ ] `/` remains useful, calls the same mutation/proxy, and has no divergent duplicated form logic.
- [ ] Screenshot-informed responsive two-column layout, required labels, error styles, optional disclosure and right-aligned CTA on desktop; one-column/no overflow on mobile.
- [ ] CTA defaults **navy**, hovers **violet**, has visible keyboard focus and distinct pending/disabled states. Purple in screenshot is correctly understood as hover.
- [ ] No fake manufacturer/retailer dropdowns or claims of identity/retailer authorisation from client-side checks.
- [ ] Blank, whitespace, excessive/control-character model/text, invalid/impossible/future date and invalid optional price all produce accessible actionable errors.
- [ ] Invalid requests make zero network calls; one valid explicit submission makes exactly one same-origin POST using the existing client.
- [ ] Optional price is omitted when blank, sent as supported GBP decimal string when filled; no channel/condition payload properties.
- [ ] All domain outcome types and all five promotion classifications get distinct truthful summaries, even when classifications are mixed.
- [ ] Pending controls prevent duplicate actions; progress announced; values retained on error; edits remove stale feedback; manual retry works.
- [ ] No request on mount, blur, typing, reconnect, hydration or route prefetch.

### Data and consistency

- [ ] No backend/schema/migration/persistence changes; same source of frontend wire schemas.
- [ ] No client eligibility, rewards, claim window calculations, fake offer totals or stored purchases.
- [ ] No API failure becomes a no-match domain result.

### Security

- [ ] Only supported validated purchase fields sent; no credentials or backend origin in browser bundles.
- [ ] Untrusted server strings, candidate IDs, unsafe URLs and internal errors never leak into rendered HTML as trusted content.
- [ ] Error descriptions, focus, live announcements, contrast, no-colour-only validation, keyboard and zoom/reflow requirements hold.

### Operations

- [ ] Existing typed API/proxy timeouts, request IDs and no-retry policy preserved.
- [ ] Frontend formatting, lint, types, unit, build, smoke and Playwright suites pass with meaningful assertions.

### Code quality

- [ ] New functionality extends FE-04, not a second form/client.
- [ ] No unnecessary dependency or unrelated design/backend rewrite.
- [ ] No tests removed or relaxed solely to make CI green.

---

## Tests to add or update

### Unit tests

- Extend `PurchaseInputForm.test.tsx` and a pure response-summary test module if introduced. Cover pristine state; required/whitespace/max length/control-character checks; valid punctuation in SKU; impossible dates/leap day/UK midnight/future date; optional price omitted vs valid/invalid.
- Assert invalid submission is zero network calls, first-invalid focus after error DOM commit, `aria-invalid` and `aria-describedby`, no premature green validity marker, keyboard-accessible disclosure.
- Verify exact four-field request and optional fifth `purchase_price`, no new fields, no date timezone shift or numeric rounding, one request on rapid repeated submit.
- Mock `resolved` empty, all three unresolved fields with `not_found`/`ambiguous`, every promotion classification and mixed-classification counts, including `NOT_ELIGIBLE` and `EXPIRED` records that are **not** promised as eligible cashback.
- Mock all `ApiErrorKind` values, safe/unsafe/missing request ID, rate-limit advice, retained values, manual retries and stale-status clearing. 502/503/contract invalid must not return no-match text.
- Keep FE-04 and FE-03 tests intact except deliberately updated copy/states.

### PostgreSQL integration tests

**N/A**; no database change.

### API/application tests

- Preserve existing Zod, HTTP-client and Next proxy contract tests. Verify `/check` is renderable without a configured API, and both routes use existing mutation.
- Do not change backend OpenAPI, Pydantic models or same-origin routing semantics.

### MCP contract tests

**N/A**; browser does not directly use MCP.

### External-boundary and browser acceptance tests

Create `frontend/e2e/purchase-check.e2e.ts` against current production Next + fake HTTPS upstream; update root-route tests without weakening their assertions:

1. `/check` loads, one main/h1, correct labels/tab order and **no network call** before CTA.
2. Missing model/SKU: red/contrasting error border, field-specific text, first-invalid focus, zero POST; correcting removes stale error.
3. Default primary navy CTA, **violet on hover**, visible keyboard focus and appropriate disabled/progress state. Assert actual computed style or meaningful visual behaviour, not text alone.
4. Enter valid model/SKU punctuation and exact date -> one proxy POST, exact expected JSON.
5. Optional GBP price is sent only when filled; no unsupported channel/condition keys.
6. Resolved/no-match and unresolved identity (`not_found`/`ambiguous`) cases; correction and resubmit.
7. Mixed results including `ELIGIBLE`, `POTENTIALLY_ELIGIBLE`, `NOT_ELIGIBLE`, `CLAIM_NOT_YET_OPEN`, `EXPIRED`; assert truthful exact counts and no invented claim approval.
8. 429 / Retry-After, 502/503/API unavailable, timeout, and invalid/unsafe 200 response; clear error and manual retry.
9. Double-click/Enter while pending -> one request. Editing after success clears stale result; no automatic retry on reconnect.
10. Axe A/AA checks on pristine, invalid, pending and result states with existing project tags. Check live region and keyboard controls.
11. Reflow at `320, 360, 375, 768, 1024, 1280, 1440` widths, 200% root text/zoom checks; no clipped field/button/status or horizontal overflow.
12. Existing `/` form stays operative; skip link works on both routes; no console/page errors outside intentionally simulated HTTP failures.

Use deterministic new fake-upstream fixture cases, not live campaigns or hardcoded production dropdown options. Record any native Safari date/VoiceOver/NVDA checks not executable in CI.

---

## Verification commands

Commands verified against current `frontend/package.json`:

```bash
cd frontend
pnpm install --frozen-lockfile
pnpm format:check
pnpm lint
pnpm typecheck
pnpm test
pnpm build
pnpm smoke
pnpm exec playwright install chromium
pnpm test:e2e
```

Use the existing CI Linux Chromium dependencies setup. If a command cannot run, report its exact invocation, blocker, alternate verification and remaining risk; do not claim unrun tests passed or weaken tests to mask regressions.

---

## Completion report

### Changed

Describe `/check`, shared form/state enhancements, supported optional price, classification summary mapping, hover/accessibility work, and limited root/documentation changes.

### Database and migrations

`None`.

### API/MCP contracts

`None` — existing typed/frontend and FastAPI contracts reused, including already optional `purchase_price`.

### Tests and verification

Report actual unit, UI, browser, accessibility, responsive, build/smoke and API-regression tests added/updated and commands/results; distinguish manual checks.

### External configuration

No new variables. Live service still requires pre-existing server-side `BENEFITSCOUT_API_ORIGIN`.

### Deviations

List any changes to scope/contract/date policy and justification; otherwise `None`.

### Remaining risks or follow-up

Trusted manufacturer/retailer lookup and dropdowns, backend-supported purchase channel/condition, full results/cards/claims/source evidence UI, history/auth, and incomplete manual browser/screen-reader checks belong to later tasks.
