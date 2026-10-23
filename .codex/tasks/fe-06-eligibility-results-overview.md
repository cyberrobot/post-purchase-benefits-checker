# FE-06 — Eligibility Results Overview

## Repository state

**Expected branch:**  
`fe-06-eligibility-results-overview`

**Base branch:**  
`main` — confirm current branch, HEAD, FE-05 merge status and any intervening changes before implementation.

**Dependencies:**

- FE-01 / PR #33: Next.js App Router, TypeScript, React, Tailwind, Jest and Playwright foundation.
- FE-02 / PR #34: shared design tokens, layout, responsive primitives and accessibility conventions.
- FE-03 / PR #35: typed `checkPurchase` API, response Zod schemas, `ApiError`, TanStack Query mutation, `QueryProvider` and same-origin proxy.
- FE-04 / PR #36: shared purchase input form used on `/`.
- FE-05 / PR #39: dedicated `/check` route, field validation, explicit request submission, pending/errors and per-classification *textual* response feedback. **FE-06 extends this rather than adding a second checker.**
- Backend eligibility HTTP API, source provenance and explainability contracts: `POST /api/v1/eligibility/check` and its `resolved` / `unresolved_identity` response variants.
- **Visual reference:** supplied 22 October 2026 screenshot of a purchase summary followed by status-coded promotion cards, filters and a Cards / Rule Matrix switch. This is visual guidance and sample content, **not** trusted offer data.

### Read first

- `.codex/tasks/TEMPLATE.md`, `AGENTS.md`, any newly introduced frontend-scoped `AGENTS.md` and `frontend/README.md`.
- `.codex/tasks/fe-02-design-system-application-layout.md`, `fe-03-api-client-configuration.md`, `fe-04-purchase-input-form.md` and `fe-05-purchase-check-integration.md`.
- `frontend/src/app/{layout,page,check/page,globals.css}`; `frontend/src/components/providers/QueryProvider.tsx`; shared Card, Badge, Button, ButtonLink and Container primitives.
- `frontend/src/features/eligibility/components/{PurchaseInputForm,purchaseForm}.ts[x]` and mutation hook.
- `frontend/src/lib/api/{eligibility.contract,eligibility,promotion.fixture,fixtures,errors}.ts`; same-origin route handler.
- `backend/app/api/schemas/eligibility.py` and relevant application/domain result types **to establish the actual wire semantics**, not to modify the backend.
- `frontend/e2e/{purchase-check,purchase-input,support-upstream.mjs,support-layout.ts}` and `frontend/package.json`.
- The supplied image: assess layout, hierarchy, typography, grouping, badges, filters, cards and actions. Do not copy illustrative Samsung/Currys/promotion values into application code.

### Primary change area

New public Next.js route `/results` and a narrowly scoped frontend results feature. An explicit successful FE-05 purchase check moves to the results route, showing the **submitted purchase details**, the backend's outcome, and **every returned promotion variant** in a legible, filterable overview. Existing request and eligibility logic stays authoritative.

### Canonical implementation examples

- `PurchaseInputForm` owns the explicit submit, local validation, synchronous in-flight guard, revision protection and existing error state.
- `useCheckPurchaseMutation` and `checkPurchase` own **the only** mutation/fetch to the existing same-origin API.
- `checkPurchaseResponseSchema` defines the already-validated `CheckPurchaseResponse`, including classification, reasons, benefits, requirements, claim windows and provenance.
- `/check/page.tsx` owns one server-rendered `main#main-content`, `tabIndex={-1}` and one `h1`; preserve this convention for `/results`.
- `Card`, `Badge`, `ButtonLink`, `globals.css` and `support-layout.ts` provide design/accessibility patterns.
- `frontend/e2e/support-upstream.mjs` supplies deterministic `POPULATED`, `MIXED`, unresolved, no-match, malformed and failed-upstream scenarios. Its mixed fixture contains **six variant matches across five distinct promotion IDs**: do not accidentally deduplicate variants.

### Relevant symbols

`PurchaseInputForm`, `Draft`, `requestFromDraft`, `validatePurchase`, `completion`, `failure`, `useCheckPurchaseMutation`, `PurchaseRequest`, `CheckPurchaseResponse`, `checkPurchaseResponseSchema`, `promotionSchema`, `Promotion`, `ApiError`, `QueryProvider`, `RootLayout`, `CheckPurchasePage`, `Home`, `Card`, `Badge`, `ButtonLink`, `POST /api/eligibility/check`, `POST /api/v1/eligibility/check`.

### Expected change surface

```text
.codex/tasks/fe-06-eligibility-results-overview.md     # this specification
frontend/src/app/results/page.tsx                    # new server route wrapper
frontend/src/app/results/page.test.tsx               # new route tests
frontend/src/app/layout.tsx                          # install minimal session provider
frontend/src/features/eligibility/session/*          # transient check-result handoff
frontend/src/features/eligibility/results/*          # presentation, selectors, components/tests
frontend/src/features/eligibility/components/PurchaseInputForm.tsx
frontend/src/features/eligibility/components/PurchaseInputForm.test.tsx
frontend/src/app/{page,check/page}.test.tsx          # preserve/shared-form regression
frontend/src/lib/api/promotion.fixture.ts            # fixtures only if warranted
frontend/e2e/purchase-results.e2e.ts                 # new browser acceptance tests
frontend/e2e/purchase-check.e2e.ts                   # update expected post-submit navigation
frontend/e2e/support-upstream.mjs                     # extend valid fixture cases when needed
frontend/scripts/smoke.mjs                           # /results smoke/empty state if appropriate
frontend/README.md                                   # documented nonpersistent results behaviour
```

Paths are guidance. Keep a small PR and explain any additional edits.

### Excluded areas

- **No** changes to the backend, database, schema, seeds, migrations, ingestion, source verification, REST/MCP contracts or deterministic eligibility engine.
- **No** authentication, saved-check history, browser/server persistence, deep-linkable results, new GET results endpoint or user tracking.
- **No** screenshot-only `purchase channel`, product catalogue/display-name lookup, invoice ID or imaginary price. The existing request contains `brand`, `model`, `retailer`, `purchase_date`, and optional `purchase_price` only.
- **No** client-calculated eligibility, claim opening/expiry, rule evaluation, cashback percentage, eligibility confidence, official retail authorisation or claimed/paid/approved state.
- **No** live claim submission, receipt upload, automatic checklist preparation, saved checklist, outbound manufacturer scraping or AI summarisation.
- **No** nonfunctional CTA to a future `/promotion/:id`, `/claim`, or unsupported endpoint. The screenshot's **Prepare Claim Checklist** and **View Full Promotion Details** actions require real functionality; use truthful in-card read-only requirements/details for FE-06 and defer a dedicated workflow to a later PR.
- No new global state library or duplicate form/client; no weakening of FE-03/04/05 tests.

### Unknowns Codex must verify

1. Exact HEAD and merge status of FE-05, current `/check` submit success logic, and whether another PR added a results route/session store.
2. Whether any frontend-scoped `AGENTS.md` appeared since the review.
3. Actual shape/order of backend promotion variants and possible null/empty benefit, requirements, explanations and claim-window fields.
4. Existing React/Next client navigation patterns, provider lifetime across App Router route transitions, and test mocks for `useRouter`.
5. Existing runtime URL validation, external-link safety patterns, time/date formatting and responsive tokens.
6. Whether a previously defined follow-up PR already owns rule-matrix and claim-detail features; if so, defer those views instead of overlapping the PR, and do not show inert toggles.

---

## Objective

After a deliberate purchase check on `/` or `/check` succeeds with **HTTP 200 and a schema-valid domain response**, the visitor reaches `/results`, where they can:

- Confirm the **exact submitted purchase details** and backend **evaluation date**.
- Review all returned matching promotion **variants**, including status, names, benefits, explanation, applicable claim-window dates, verification provenance and official links **only to the extent provided by the backend**.
- See accurate counts for all five classifications, filter by status, and expand recorded requirement / rule details without changing eligibility.
- Return to `/check` to edit the original values and explicitly run another check.
- Understand the difference between an unresolved product/retailer identity, zero **published** matching promotions, eligible/potentially eligible/upcoming/expired/not-eligible results and a failed service call.

**Done:** A successful check navigates once to a responsive, accessible, truthful `/results` UI with no additional network call, no fabricated campaign data, no purchase details persisted or encoded in URLs, and robust direct-entry/refresh recovery. `/` and `/check` stay functional.

### Visual and content intent

- Match screenshot's **hierarchy**, not exact pixels: broad rounded summary surface on a light tinted page; purchase identity and metadata first; a compact results/status overview and filter control; generous separation; white outlined promotion cards with strong heading, prominent real reward content, readable explanation and right-side contextual actions on desktop.
- Use FE-02 warm-white/navy/violet tokens and existing rounded corners; preserve accessible semantic contrast. Classification accents should be unmistakable with **labels plus icons/text**, never colour alone. Mobile cards stack without horizontal clipping.
- Screenshot's `Samsung OLED S90D 65" 4K Smart TV`, Currys, `£1499`, channel `ONLINE`, promotional titles and `£150` are **examples only**. With today's API, a header must use a safe representation like **Brand · Model** from the *submitted request*, not a made-up catalogue description.
- Prefer **Purchase details checked** over **Checked purchase verification**: the system checked eligibility against recorded rules; it did **not** authenticate the receipt, prove a payment or approve a claim.
- Label dates honestly: **Purchase date** from input, **Evaluated on** from `evaluation_date`, **Source last verified** from `last_verified_at` / `provenance.verified_at`. These are different events.
- Render purchase price **only when the user supplied it**; there is no purchase channel or invoice date in the existing contract.
- An `ELIGIBLE` result is **eligible under recorded rules**, not a guaranteed accepted/paid claim. Use stronger **Claim period open** wording only if `eligibility.claim_window_status === 'open'` is present; never infer it from the current clock.

---

## Architecture and invariants

1. **One request path:** `PurchaseInputForm` → `useCheckPurchaseMutation` → `checkPurchase` → `/api/eligibility/check` → existing Next proxy → FastAPI. FE-06 never makes a second check or uses an eager query.
2. **Transient route handoff:** introduce a small, typed client-only `PurchaseCheckSessionProvider` (name flexible) under the current root `QueryProvider` / App Router layout, carrying an immutable `{ submittedPurchase: PurchaseRequest; response: CheckPurchaseResponse }` snapshot plus an editable draft if needed. Its only purpose is same-tab route navigation. Do **not** use React Query caches as persistent results storage.
3. **No persistence:** no URL query string/route param, browser `history.state`, `localStorage`, `sessionStorage`, IndexedDB, cookies, global server singleton, API cache, server action or analytics payload storing purchase data. State is cleared by a full reload; this is an explicit MVP limitation.
4. **Submission ownership:** FE-05 maintains the in-flight guard, revision number and abort/unmount safety. On a valid response *from the latest unedited submission*, atomically publish the matching `{input,response}` snapshot to session and then navigate using Next's `router.push('/results')`. Do not navigate on errors or from stale responses. Retain one intentional POST per submit; never refetch during navigation.
5. **Snapshot integrity:** purchase summary always corresponds to the **same input** that produced the response. If the user returns to edit any field, the old result becomes invalid immediately; a history-forward `/results` visit must not display stale eligibility against changed values. Keep the editable draft for prefill as needed, but clear the old response.
6. **Page boundary:** `frontend/src/app/results/page.tsx` remains a Server Component owning direct-child `<main id="main-content" tabIndex={-1}>` and exactly one `h1`, with a narrowly scoped client results body. The root layout, header/footer and skip-link remain intact; there must not be multiple nested main landmarks.
7. **Direct entry:** navigating directly to `/results`, hard refreshing or opening it in another tab shows a friendly **No results in this tab** state and a `/check` CTA; it must not fetch, guess a check, restore a purchase, crash or redirect in a hydration loop.
8. **Determinism:** frontend may format/select/sort response data for presentation only; backend classification, rule outcomes, claim dates, reward values and source evidence remain authoritative. Never infer a claim decision.
9. **Safe content:** validate once at the existing API boundary; render backend text as escaped plain text. Never use HTML injection, arbitrary links or remote content as executable instructions.

---

## API and contract changes

**None.** FE-06 consumes the existing typed `CheckPurchaseResponse` and makes no schema, endpoint, authentication, HTTP error or MCP changes.

### Supported input and summary mapping

| Source | Display | Rule |
| --- | --- | --- |
| Submitted `brand` + `model` | Purchase title | Display text as supplied; do not invent a richer catalogue name |
| Submitted `retailer` | Retailer | Do not assert it is an authorised promotion retailer independently |
| Submitted `purchase_date` | Purchase date | Calendar-only `YYYY-MM-DD`; format for `en-GB` without timezone shifting |
| Submitted `purchase_price` | Paid amount, optional | Only when present; GBP decimal string, no binary-float reinterpretation |
| Response `evaluation_date` | Eligibility evaluated | Calendar date, distinct from both purchase date and source verification |
| Response `resolved_identity` | Internal resolution only | Do not expose raw UUIDs as product names |
| Purchase channel, invoice number, approval state | N/A | Unsupported; never display fabricated values |

### Domain outcome mapping

| Backend outcome | UI |
| --- | --- |
| `unresolved_identity` / `not_found` | Could not identify the specific `brand`, `model` or `retailer`; advise correction; **not** “ineligible” |
| `unresolved_identity` / `ambiguous` | Multiple matches; advise greater specificity; don't display UUID candidate IDs |
| `resolved` and empty `promotions` with `no_matching_published_promotions` | No matching **published** promotions were found for these details; do not claim none exist anywhere |
| `resolved` with non-empty `promotions` | Show every returned promotion **variant**; do not claim a single universal purchase status |
| Malformed/unknown/inconsistent response | Existing client contract error on `/check`, not a successful results page |
| Transport 429, 502, 503, timeout, etc. | Existing FE-05 failure UX on `/check`, with safe retry guidance and preserved input |

### Classification mapping and filters

Use the **exact** `promotion.eligibility.classification` to determine status; it is separate from `promotion.promotion_status` (publication lifecycle) and `eligibility.claim_window_status` (claim timing).

| Classification | Accessible badge/filter | Meaning |
| --- | --- | --- |
| `ELIGIBLE` | Eligible | Meets recorded eligibility rules; not claim approval |
| `POTENTIALLY_ELIGIBLE` | Potentially eligible | More evidence/conditions may be unknown; “Action needed” only if real next steps are present |
| `CLAIM_NOT_YET_OPEN` | Upcoming claim period | Claim period has not opened at the recorded evaluation date |
| `EXPIRED` | Claim period expired | Claim window has ended; do not suppress the card |
| `NOT_ELIGIBLE` | Not eligible | At least one recorded rule is not met; show reason when provided |

- Status counts and `All (N)` use **returned `promotions` array entries** (variant matches), including all negative/historical results; do not deduplicate by `promotion_id`. Use `promotion_variant_id` as stable card identity. If the same promotion appears under two variants, display both with distinguishing `variant_name` if supplied.
- Preserve backend order within each grouping or apply a documented stable status priority (`ELIGIBLE`, `POTENTIALLY_ELIGIBLE`, `CLAIM_NOT_YET_OPEN`, `EXPIRED`, `NOT_ELIGIBLE`) with original response index as tie-breaker. Filtering must never mutate the actual response or falsely update counts.
- Show **All** and five status filters, using short translated labels and zero counts as appropriate; design may wrap horizontally at small widths. If grouping statuses into **Other**, document exactly which classifications it contains and make the total reconcile with `All`.
- Optional **Cards / Rule Matrix** switch from reference may be implemented as two client-side views of the **same** validated data, with no new fetch. The matrix shows actual `rule_evaluations` (`kind`, `status`, `reason_code`) per variant; missing evaluations must display **Not supplied**, not green ticks. If keeping a small PR requires deferring it, **hide the switch entirely** rather than render a dead control; record follow-up.

### Promotion-card field mapping

- **Title:** `promotion_name` and optional `variant_name`; never use screenshot title as fixture-driven production copy.
- **Benefit(s):** enumerate all `benefits` with `benefit_type`, `name`, optional description. Show `£X cashback` only when `cashback_reward_gbp` is non-null; use a decimal-string-safe GBP formatter, not float arithmetic. For null amounts, report appropriate `reward_unavailable_reason` / `reward_unavailable_explanation` when present. Never promise a numeric warranty duration, accessory or cashback value unless returned in named data.
- **Status/reasons:** show a succinct neutral phrase from the mapped classification plus backend-provided `explanation` when useful. Display raw explanation text escaped; reason code and `rule_evaluations` can be rendered in an expandable **Recorded rules** section with comprehensible labels. Do not invent passing rules or translate `unknown` to satisfied.
- **Claim window:** show `opens_on` / `deadline_on` **only when a `claim_window` exists**, with clear labels. Do not derive time windows, days remaining, or a deadline from the user's purchase date or current local time.
- **Requirements:** accessible collapsible **View claim requirements** uses only returned `requirements`, with optional descriptions; if empty, state that the response lists no requirements, not that no documents are needed.
- **Source:** label `last_verified_at` / `provenance.verified_at` **Source last verified**, not “Purchase verified”. Show real `official_source_url` as **Official promotion source / terms** and `claim_url` as **Open official claim site** only when a validated URL exists. The latter is an outbound link, **not** an application claim submission or assurance of claimability.
- **Lifecycle:** if shown, label `promotion_status` as a separate publication/lifecycle value; it must not override or silently conflate the returned eligibility classification.
- The screenshot's **Prepare Claim Checklist** CTA is out of scope. Do not create an inert button. A read-only requirements disclosure is appropriate for FE-06; a prepared checklist or dedicated detail route needs a separate scoped task.

---

## Domain and application behaviour

### Successful-check navigation sequence

1. User visits `/` or `/check` and enters supported fields; no check runs on mount or field changes.
2. FE-05 locally validates and explicitly issues **one** POST. It displays the existing pending state, guards duplicate clicks/Enter and retains input on failure.
3. On schema-valid `200`, while still mounted and if the submission revision matches the current form revision, publish `{submittedPurchase,response}` once and navigate to `/results`. This applies to `resolved` (with or without matches) and `unresolved_identity` responses so all domain outcomes have a coherent destination.
4. `/results` reads the session snapshot only. It performs **zero** requests on mount, route change, filter switch, Cards/Matrix switch, disclosure expansion or browser history navigation.
5. **Edit purchase details** returns to `/check` with the submitted values prefilled through in-memory state, not URL fields. Editing immediately invalidates the previous result and no new check occurs until explicit submit.
6. New successful check **replaces** the previous snapshot; malformed/failed check never overwrites it with fabricated data or navigates to success.
7. If the user reloads `/results`, closes the tab or opens the link elsewhere, display the defined empty/restart state; do not silently resubmit.

### Results view states

- **No in-memory snapshot:** accessible empty state with “Start a purchase check” link; no sample promotions.
- **Unresolved identity:** purchase summary plus correction guidance for the actual field/status. No promotion cards, no invented eligibility; preserve ability to edit.
- **Resolved, zero promotions:** calm empty state, truthful *published* no-match wording, purchase context and edit CTA.
- **Resolved, one promotion:** one legible card and exact status/count.
- **Resolved, multiple/mixed:** all variants, correct count and filters; including `NOT_ELIGIBLE`, `EXPIRED` and same-promotion multiple variants.
- **Filter with zero matches:** say “No results in this category”; retain overall count and allow All reset.
- **Long/partial details:** wrap long names/links/reasons safely; render nulls gracefully; source and date copy must remain distinct.
- **Loading and transport failure:** occur on the checker before navigation, not simulated on a no-network results page. If future results fetching is added, specify separate loading/error behaviour in its own task.

### Eligibility-specific rules

**Presentation only.** Eligibility logic, order of backend rules, claim-window status, source verification and reward calculation are unchanged. Use literal backend enum values as discriminants; do not recompute status using today's date, a heuristic based on purchase date, `promotion_status`, returned reward amount or a guessed claim portal state. A visible positive badge never means an accepted or paid claim.

### Ingestion/publication rules

**N/A.** Only data already returned by the existing check response is rendered. No ingestion or publication side effects.

---

## Persistence, transactions, and migrations

**None.** No PostgreSQL or Alembic work, server sessions, saved history, cookies or browser persistence. The ephemeral React context is not a durable database or browser store. Reloading loses the result by design; the empty state makes this transparent. Unit/browser tests must prove no client- or server-side storage and no new write calls.

---

## External services and network access

- **No new endpoint.** Reuse the existing typed client/proxy/backend check, existing timeout, response-size limit, no-store transport semantics and manual retry policy.
- No new API call from `/results`; all card actions are local display controls or safe links to **validated backend-provided** official URLs.
- External links use `target="_blank"` with `rel="noopener noreferrer"` and clear off-site wording. Preserve the frontend schema's validated HTTP(S) URL policy; never interpolate untrusted input into a guessed campaign/claim URL or fetch user-provided destinations.
- Existing `support-upstream.mjs` is the deterministic test boundary; no production manufacturer calls, live offers or network dependency in unit/E2E tests.

---

## Security and privacy

- Results and request snapshot remain in client memory **only** for this tab's current mounted app. Do not put them in URLs, storage, logs, analytics, persisted TanStack caches, React Server Component props, server state or error monitoring attributes.
- Keep the check unauthenticated as currently designed. Do not introduce identity sharing or permanent records.
- Render backend explanation, benefit name/description, source strings and identifiers as escaped React text, not HTML/Markdown/JS execution. Never render UUIDs as user-facing labels or candidate identities.
- Only validated URLs may be clickable. Do not synthesize source/claim links; use existing validation and outbound link hardening.
- Show status meaning via text and icon/pattern in addition to colour; satisfy WCAG AA contrast, keyboard navigation, visible focus and accessible selected-filter state.
- Preserve semantic card headings (under one `h1`), correctly associated labels/controls, button focus, useful announcements on filter/view changes, and reduced-motion preferences. No role-only decorative controls or hidden essential content.
- No promo details from fixture data in production components; tests should detect accidentally shipping screenshot campaign data.

---

## Configuration and deployment

### Environment variables

**None new or changed.** Existing server-only `BENEFITSCOUT_API_ORIGIN` is required for live submission but **not** for `/results` to render its no-session state. Do not introduce `NEXT_PUBLIC_*` backend URLs or secrets.

### Runtime/deployment changes

One public App Router page and a small client context under the existing root provider. No middleware, new service, worker, auth, database connection, API route or backend deployment unit. Preserve pinned pnpm/Next/React versions and frontend CI.

---

## Observability and operations

- Maintain the FE-05 distinction between domain outcomes and API errors. Results sessions are established **only** from validated success responses.
- Preserve existing request-ID handling for errors on `/check`; don't expose raw problem body/internal exception or purchase payload in logs.
- No new telemetry vendor, PII tracing or event beacon. If existing metrics are available, count result-state categories without purchase values or source URLs.
- A 502/503, rate limit or invalid schema must never create a fake “no matching promotions” results session.

---

## Failure, consistency, and recovery

| Scenario | Required behaviour |
| --- | --- |
| Validation fails | Stay on checker, focus invalid field, zero network, no results navigation |
| Pending double-click / Enter | One request, one handoff, one transition |
| Network/503/429/timeout | Stay on checker; safe existing `ApiError` feedback, preserve draft, manual retry only |
| Malformed/unsafe 200 | Contract error on checker; never mount partially parsed offers |
| Identity unresolved | Show field-specific correction on results; no false ineligibility |
| Resolved, no promotions | Show published no-match, not universal absence of offers |
| Multiple variants of same promotion | Render/count each returned variant using variant ID |
| Null reward/claim window/requirements | No invented money, dates or paperwork; render truthful fallback |
| User edits after success | Invalidate old response immediately; prior `/results` entry cannot display stale data |
| Old request completes after edit or unmount | Ignore stale response and do not navigate or overwrite snapshot |
| Hard refresh/direct `/results` | Informative empty state, edit/start CTA, zero check API calls |
| Rapid filtering or view toggle | Pure local derived state; stable counts; no fetch |

---

## Acceptance criteria

### Behaviour and UX

- [ ] `/results` exists with one server-owned `main#main-content`, `tabIndex={-1}`, one clear `h1` and shared site header/footer/skip-link semantics.
- [ ] An explicit successful check from **both** `/` and `/check` navigates once to `/results` with the validated response **and exactly matching submitted request**; no second POST or new GET.
- [ ] Both unresolved and resolved-empty success responses get truthful, actionable pages; network/API errors stay on `/check` and never become no-match results.
- [ ] Purchase header shows submitted brand, model, retailer and purchase date; purchase price only if provided; evaluation date clearly labelled. No fabricated invoice date, product catalogue title or purchase channel.
- [ ] All five classifications and counts reconcile with total **variant matches**; `NOT_ELIGIBLE`/`EXPIRED` are not erased; two variants of one promotion remain separate.
- [ ] Every promotion card uses real name, optional variant, all benefits, recorded eligibility explanation, verification timestamp and available claim dates. Missing fields are rendered honestly.
- [ ] Cashback amounts use backend decimal strings without calculating a new reward, rounding based on float arithmetic or claiming a guaranteed payout.
- [ ] Filter controls are functional, keyboard operable, clearly selected, and preserve accurate counts. Empty filtered categories have a clear reset route.
- [ ] Read-only requirements and recorded-rule details are functional disclosures when present. Any Cards/Rule Matrix switch is fully functional or omitted; no dead screenshot CTA.
- [ ] Source and claim links come exclusively from validated backend-provided URLs, clearly open externally, and never submit a claim in-app.
- [ ] **Edit purchase details** opens `/check` with original fields prefilled; changing a value invalidates the old response; no implicit submit, navigation prefetch or stale result.
- [ ] Direct visits, refreshes, other tabs and expired client context show **No results in this tab** with a working `/check` CTA, not fake content or a fetch.
- [ ] Responsive screenshot-informed treatment at 320–1440px and 200% zoom; mobile cards/buttons reflow without clipped controls or sideways scroll; keyboard, screen-reader and reduced-motion use are supported.

### Data and consistency

- [ ] Existing `PurchaseRequest` and `CheckPurchaseResponse` schemas remain unchanged and authoritative; no duplicate eligibility implementation.
- [ ] Backend `eligibility.classification`, `claim_window_status`, `promotion_status`, benefit amounts, reasons, claim dates and source verification are displayed as separate data dimensions without client recomputation.
- [ ] No client- or server-side storage, URL purchase data or stateful backend additions; every results view is tied to an immutable single submission snapshot.
- [ ] No fake Samsung/Currys/`£150` promotions embedded in production UI or hardcoded status counts.

### Security

- [ ] All untrusted strings are escaped, URLs validated, external links hardened, and candidate IDs/internal exceptions omitted.
- [ ] No data leaks into URLs, storage, cookies, console logs, telemetry or hydration payloads.
- [ ] Axe AA, keyboard-only, accessible announcements, focus management, text alternatives for coloured badges and semantic heading/landmark tests pass.

### Operations and quality

- [ ] Existing FE-03/04/05 request timeouts, error contracts, no-retry policy and pending/stale-response safeguards remain intact.
- [ ] Focused unit/route/component/browser suites and wider frontend format, lint, typecheck, unit, build, smoke and Playwright checks pass.
- [ ] No unrelated dependencies, backend changes or loss of existing browser coverage.

---

## Tests to add or update

### Unit tests

- Add `frontend/src/features/eligibility/results/*.test.ts[x]`: classify and count six variants/five promotion IDs; each enum, zero status count, stable sorting, filters, row keys; no cross-over of `promotion_status` and `claim_window_status`.
- Test exact label/text for each classification including ambiguous/not-found identity and no published match. Ensure `ELIGIBLE` is not “claim approved” and unspecified claim window is not “claim open”.
- Test missing/nullable benefit amount, multiple benefits, non-cashback reward, `reward_unavailable_reason`, real date formatting (calendar vs UTC timestamp), oversized text, missing/empty requirements and explanations; assert never output guessed `£150`, dates or documents.
- Test session provider snapshot set/replace/invalidate; client navigation only after non-stale validated completion; editing/returning/back/forward does not restore old response; no session persistence or implicit network requests.
- Preserve and update `PurchaseInputForm.test.tsx` tests for loading, error, request payload, first-invalid focus, in-flight guard, no retry and stale-resolution suppression.

### PostgreSQL integration tests

**N/A** — no data or persistence changes.

### API/application tests

- No new API. Preserve `eligibility.contract.test.ts`, `eligibility.test.ts` and Next proxy `route.test.ts` unchanged except fixture improvements.
- Add `/results/page.test.tsx` for Server Component landmarks and the direct-entry empty state without `BENEFITSCOUT_API_ORIGIN`.

### MCP contract tests

**N/A** — MCP unchanged.

### External-boundary and browser tests

Add `frontend/e2e/purchase-results.e2e.ts` using the existing production Next app + deterministic fake HTTPS backend:

1. `/` → successful check → `/results`: exact submitted summary, expected response date, one POST, no results request; repeat from `/check`.
2. `POPULATED`: real cashback amount/benefit/requirements, verified source date, official HTTPS URLs, honest positive status; expand details by keyboard.
3. `MIXED`: **six** variant cards, **five** distinct promotion IDs, every classification, status counts/filters, `NOT_ELIGIBLE` and `EXPIRED` retained, no invented rewards/terms; test any matrix view is built from real evaluations.
4. `UNKNOWN` and `AMBIGUOUS`: field-specific prompts, no UUID leakage, back to prefilled `/check`, corrected submission yields a new result.
5. No-match: zero published result state; not a network-error message, with working edit CTA.
6. 429, 502, 503, timeout, unsafe/malformed body: remain on checker and retain draft; no success route or partial results.
7. Direct `/results`, full reload, new tab: no snapshot and no API requests; working start link.
8. Editing a previously checked purchase invalidates the old snapshot; browser Forward/back must not show a stale eligibility result; success after resubmission replaces it.
9. All external links have correct target/rel, valid provenance only; no `javascript:`/credential-bearing URLs, HTML injection or direct backend origin exposed.
10. 320/360/375/768/1024/1280/1440px reflow and 200% zoom; Axe WCAG 2/2.1/2.2 A/AA in resolved, unresolved, empty and filtered states; keyboard focus/disclosures, meaningful label vs colour-only distinction, no console/page errors.

Use true fixture-driven **wire response objects**. Avoid screenshots as fake data sources and avoid live manufacturer sites in CI. Any manual Safari / screen reader gaps must be disclosed in the completion report.

---

## Verification commands

Commands verified against `frontend/package.json` (execute from project root unless shown):

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

Tests must include targeted new results unit/component suites and the amended FE-05 browser checks; retain existing full frontend suite. If implementation cannot run a command, record exact command, blocker, alternative verification and remaining risk; never claim unrun checks passed or weaken failing assertions merely to obtain green CI.

---

## Completion report

On implementation completion, provide:

### Changed

List `/results` route, ephemeral check-session handoff, purchase summary, cards, filters, real requirement/rule disclosures, and FE-05 form navigation changes.

### Database and migrations

`None`.

### API/MCP contracts

`None` — reused typed existing check response.

### Tests and verification

List tests added/updated, each actual command executed and results, including accessibility/responsive/browser checks. Separate observed results from not-run checks.

### External configuration

`None` new; the existing server-only backend API origin is still needed for real checks.

### Deviations

Describe any scope changes (notably if rule matrix is deferred or the session mechanism differs), with rationale, or `None`.

### Remaining risks or follow-up

Document deliberate ephemeral-only results (refresh loses data), any deferred dedicated promotion-detail/claim-checklist workflow, screenshot-only unsupported channel/catalogue fields, and unverified real browser/screen-reader combinations. Do not imply saved results or official claim submission now exists.
