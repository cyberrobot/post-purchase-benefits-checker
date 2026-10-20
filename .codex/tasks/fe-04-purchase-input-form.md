# FE-04 — Purchase Input Form

## Repository state

**Expected branch:**  
`fe-04-purchase-input-form`

**Base branch:**  
`main` (refresh HEAD and check outstanding PRs immediately before implementation).

**Dependencies:**

- FE-01 / PR #33: `frontend/` Next.js 16 App Router foundation with React 19, TypeScript, Tailwind CSS v4, pnpm, Jest and frontend CI.
- FE-02 / PR #34: layout, design tokens, form-compatible `Button`, `Card`, `Container` and accessibility/browser testing conventions.
- FE-03 / PR #35: Zod wire contracts, same-origin `/api/eligibility/check` route, `checkPurchase`, `ApiError`, `QueryProvider`, `useCheckPurchaseMutation` and deterministic Playwright fake upstream. These files were present on the inspected `main` branch.
- Backend PR #18: authoritative FastAPI `POST /api/v1/eligibility/check` contract. Backend eligibility rules and identity matching remain authoritative.
- **Visual reference:** user attachment `Screenshot 2026-10-19 at 17.43.03.png` (BenefitScout desktop hero with centred introduction and compact purchase search/CTA).

### Read first

- `.codex/tasks/TEMPLATE.md`; repository `AGENTS.md` and any newer frontend-scoped `AGENTS.md` (none found when inspected). Root guidance describes backend invariants, which remain binding at the boundary.
- `.codex/tasks/fe-02-design-system-application-layout.md`, `.codex/tasks/fe-03-api-client-configuration.md`, `frontend/README.md` and the attached image.
- `frontend/src/app/page.tsx`, `page.test.tsx`, `layout.tsx`, `globals.css`; `frontend/src/components/layout/*` and `frontend/src/components/ui/{Button,Card,Container}.tsx`.
- `frontend/src/lib/api/{eligibility.contract,eligibility,errors}.ts`, `frontend/src/features/eligibility/api/useCheckPurchaseMutation.ts`, `frontend/src/components/providers/QueryProvider.tsx`.
- `frontend/e2e/{shell,api-client}.e2e.ts`, `frontend/e2e/support-upstream.mjs`, `frontend/playwright.config.ts`, `frontend/scripts/smoke.mjs`, `.github/workflows/frontend.yml`, and `frontend/package.json`.
- `backend/app/api/schemas/eligibility.py`, `backend/app/domain/identity_normalisation.py`, `backend/app/domain/purchase_values.py` and `backend/app/api/eligibility.py` to verify the live request boundary without recreating it.

### Primary change area

A **reusable, accessible frontend purchase-entry form** comprising manufacturer, model, retailer and purchase date, rendered as the principal interaction on `/`. It validates input and explicitly invokes the existing FE-03 mutation. It shows a **minimal, truthful outcome/status message** only; detailed results and claim actions belong to a separate PR.

### Canonical implementation examples

- `frontend/src/app/page.tsx`: current synchronous Server Component, direct-child `<main id="main-content" tabIndex={-1}>` and exactly one `h1`.
- `frontend/src/app/layout.tsx`: root server layout with skip link, header, `QueryProvider`, and footer; the provider adds no wrapper DOM.
- `frontend/src/components/ui/{Button,Card,Container}.tsx` and `frontend/src/app/globals.css`: existing Tailwind v4 palette, spacing, control, focus and responsive patterns.
- `frontend/src/lib/api/eligibility.contract.ts`: `purchaseRequestSchema`, `calendarDateSchema`, `PurchaseRequest`, and `CheckPurchaseResponse`.
- `frontend/src/features/eligibility/api/useCheckPurchaseMutation.ts`: existing explicit, non-retrying mutation.
- `frontend/src/lib/api/errors.ts`: error kinds and safe request ID/retry-after fields.
- `frontend/e2e/shell.e2e.ts` and `frontend/e2e/api-client.e2e.ts`: production Chromium, accessibility and fake upstream patterns.
- There is **no** existing purchase-input component, manufacturer/retailer options API, or result page. Do not invent one.

### Relevant symbols

`Home`, `RootLayout`, `Button`, `Card`, `Container`, `useCheckPurchaseMutation`, `PurchaseRequest`, `purchaseRequestSchema`, `calendarDateSchema`, `CheckPurchaseResponse`, `ApiError`, `QueryProvider`, `checkPurchase`, `POST /api/eligibility/check`, `PurchaseRequest` (FastAPI model), `resolved`, `unresolved_identity`, and `no_matching_published_promotions`.

### Expected change surface

Suggested locations; preserve repository conventions if simpler equivalents exist:

```text
.codex/tasks/fe-04-purchase-input-form.md           # this specification
frontend/src/features/eligibility/components/PurchaseInputForm.tsx
frontend/src/features/eligibility/components/PurchaseInputForm.test.tsx
frontend/src/features/eligibility/components/purchaseForm.ts       # optional pure draft/validation mapping
frontend/src/features/eligibility/components/purchaseForm.test.ts  # when pure module introduced
frontend/src/app/page.tsx                            # limited landing integration, not full homepage
frontend/src/app/page.test.tsx
frontend/e2e/purchase-input.e2e.ts                    # real rendered UI and same-origin network
frontend/e2e/shell.e2e.ts                            # intentionally update placeholder assertions
frontend/e2e/support-upstream.mjs                     # accept absent optional purchase_price
frontend/scripts/smoke.mjs                           # change if placeholder text is asserted
frontend/README.md                                   # how to use/run and known limitations
```

Use existing UI primitives and scoped Tailwind utilities. Add an input primitive only if it materially improves reuse; a new form framework, date picker, global store or styling system is not required.

### Excluded areas

- Full homepage marketing design, additional landing sections, campaigns, popular-check links, promotion carousels, brand directory, autocomplete/suggestions, retailer catalogues and search APIs.
- Dedicated results listing/cards, classifications/claim-steps UI, claim URLs, source verification presentation, saved purchases, purchase-history persistence, and user accounts/authentication.
- Purchase-price field or speculative required eligibility fields: this PR ships **exactly four** inputs. Price is optional on the backend and is **omitted**, not fabricated.
- Backend, database, REST/MCP contract, eligibility, ingestion, normalization, provenance or infrastructure changes.
- New API clients, new proxy routes, direct browser access to backend hosts or manufacturer websites; no AI-based eligibility, fake success or campaign figures.
- A site-wide navigation redesign or links to unimplemented routes. No automatic checks on page load, background polling, debounced API calls or retry-on-reconnect.

### Unknowns Codex must verify

1. FE-03 remains merged or accessible on the chosen base branch, and the FE-03 API/hook/error schemas are unchanged.
2. Current homepage and shell tests still assert development placeholder text; update those intentionally rather than deleting assertions or globally weakening test coverage.
3. Whether the header currently contains only the home wordmark. Do not publish `/check`, `/promotions`, `/brands` or `/faq` unless implemented; an in-page `#purchase-checker` link is permissible if actually useful.
4. The browser-test fake upstream currently rejects requests unless `purchase.purchase_price === '799.99'`, whereas the real backend marks price **optional**. Update only this test double to accept **both omitted/null and valid configured price**, preserving existing FE-03 test behaviour.
5. The backend's `brand`, `model`, `retailer`, date and optional money wire validation; frontend must not narrow the business contract accidentally (e.g., by applying an unsupported date range or whitelist).
6. Tailwind v4 tokens, focus behaviour, response/correlation-ID handling, viewport matrices and CI commands in the latest repo.
7. Whether the design reference image/logo is committed/licensed for application use. It is a **visual reference** only; do not embed the screenshot or assume a logo asset exists.

---

## Objective

Users can enter the **manufacturer (brand), exact product model/SKU, retailer and purchase date** in a clean, responsive form, submit the purchase on demand, and see meaningful validation, progress, failure and minimal factual completion feedback based on a genuine FE-03 API response.

After FE-04:

- The first viewport of `/` focuses on the purchase form, without a large decorative illustration; on mobile the fields and CTA remain easy to use.
- The four fields are visibly labelled, keyboard-accessible, and map to the exact existing backend property names.
- Invalid or incomplete input never reaches the network. A valid submission makes one same-origin request via `useCheckPurchaseMutation`.
- While pending, the form communicates progress and prevents duplicate submits. Users retain their input on errors and can correct/resubmit.
- An unresolved identity, resolved response with no matching promotions, and resolved response containing promotion records are distinguishable. **No return value is represented as confirmed cashback, eligibility or a claimable benefit in this PR.**
- A missing/unavailable backend produces an honest, recoverable error—not a fake empty result or simulated success.

**Definition of done:** a real visitor can fill and submit the form; validation and UI behaviour have focused RTL coverage; actual browser submission to the existing same-origin bridge is covered against deterministic fake upstream; mobile/reflow/accessibility regressions are checked; existing FE-01–03 behaviour and CI remain intact.

### Design reference and UX intent

The reference screenshot shows a spacious white header, a soft violet/warm page, centrally aligned dark/violet hero typography, a rounded white horizontal search treatment, a dark navy “Find My Benefits” button and subtle auxiliary links. Preserve this **visual hierarchy**, not its single-input interaction or unsupported campaign claims.

- Use a concise one-`h1` hero such as **“Find benefits from a purchase”**, with supporting text that explains the four facts needed. No guarantee of benefits or savings.
- Centre a rounded white card beneath the introduction. Keep the form visible near the top of the page on desktop; avoid excessive whitespace pushing the CTA below the fold.
- Desktop (when usable): two-column labelled inputs, with a clear full-width or right-aligned navy submit button. Narrow screens: one column and full-width submit button, minimum comfortable tap targets, no horizontal overflow.
- Field order (visual **and** keyboard): **Manufacturer → Model → Retailer → Purchase date → Find My Benefits**. Do not rely on placeholders as labels.
- Labels/assistance: `Manufacturer` (“e.g. Samsung”); `Model number` (“Find the exact model/SKU on the product or receipt”); `Retailer` (“Where did you buy it?”); `Purchase date` (native date input; UK-friendly presentation). Keep real model/SKU characters intact.
- Follow FE-02's navy, violet, warm-white palette, `text-*` and `rounded-*` tokens, modest borders/shadows, responsive `md:`/`lg:` utilities and highly visible keyboard focus. Avoid hardcoded colours, custom illustration assets or new CSS theme architecture.
- A compact *single search box* as seen in the screenshot is **not sufficient** for backend eligibility; it may not replace the four required fields. Do not show “popular checks” with specific promotion values unless actual authoritative data and links exist—there is no such data API in FE-04.
- Any homepage headline/copy change must be verified in both component and production-browser tests, and metadata should not claim the feature is unavailable once it functions.

---

## Architecture and invariants

1. **Next.js Server Component page, Client Component form.** Keep `RootLayout` and `Home` server-rendered. Mount a narrowly scoped `'use client'` `PurchaseInputForm` in the existing direct-child `<main>`. The provider must not add wrapper DOM. Preserve `lang="en-GB"`, the skip link, one `h1`, and semantic `<header>/<main>/<footer>`.
2. **Single data path.** `PurchaseInputForm` → `useCheckPurchaseMutation()` → `checkPurchase()` → `POST /api/eligibility/check` → existing Next bridge → FastAPI. Do not create fetch helpers or duplicate validation/transport stacks.
3. **Backend authority.** UI input validation checks wire shape and provides feedback; it does not decide eligibility, match brands/models, infer retailer qualification, calculate claim windows/rewards, or invent offer status.
4. **One request per intentional valid submission.** No API call on mount, type, blur, focus/reconnect, page hydration or input prefill; submit only from native `<form onSubmit>` handling.
5. **No persistent user data.** Purchase values, responses and errors remain in transient component/mutation state; no localStorage, sessionStorage, cookies, URL query serialization, third-party analytics or speculative history saving.
6. **The four-field feature contract is the source of truth.** Expose manufacturer to the user, send `brand` on the wire. `purchase_date` is a calendar-date `YYYY-MM-DD` string, never a JavaScript timestamp. Omit `purchase_price` completely; never send an assumed `0`.
7. **Truthful feedback.** A domain success is distinct from an HTTP success-with-no-offers, an unresolved identity and an infrastructure error. Do not call returned candidate records “eligible benefits”. A detailed results surface is a follow-up feature, not a justification for blank feedback.
8. **Predictable state.** Pending submission disables subsequent submissions; keep submitted values stable until the promise settles (disable field edits while pending, or implement an equally well-tested stale-response guard). Editing after a settled request clears old completion/error messaging so it cannot be mistaken for the new draft.

---

## API and contract changes

**No new or changed backend, MCP or HTTP API.** The frontend consumes the existing contract:

```ts
// Existing PurchaseRequest on the wire — purchase_price intentionally omitted.
{
  brand: string;           // visibly labelled Manufacturer
  model: string;           // exact user-provided product model / SKU
  retailer: string;        // retailer name supplied by buyer
  purchase_date: string;   // valid YYYY-MM-DD calendar date
}
```

- Only `brand`, `model`, `retailer`, `purchase_date` are submitted. Do not submit UI-only draft/error properties. Follow `purchaseRequestSchema` (strict object, max 255 characters for identity text, no blank/whitespace-only values, valid Gregorian date). Backend identity matching handles normalisation; do not case-fold, rewrite punctuation, remove model whitespace internally, select canonical IDs, or trim characters within models in the UI.
- Keep optional price omitted, not `''`, `0`, NaN or guessed data. Missing purchase price may prevent a precise percentage/amount reward calculation; FE-04 makes no final reward-value promise.
- Native `<input type="date">` may display according to the browser/OS locale, but the *value sent* is the raw browser `YYYY-MM-DD` calendar-date string. Do not use `new Date(date).toISOString()` (UTC shifting risk) or `Date.parse` for transport.
- Use existing `purchaseRequestSchema.safeParse` as the final submission guard (or a form schema derived from the same contract). Present field-specific messages before any request. The API client also re-validates before sending.
- Do **not** arbitrarily reject historical or future calendar dates as a new eligibility/business rule: the current backend contract accepts calendar dates without an upper/lower purchase-date bound. If product requirements later add a date policy, specify that in a separate approved contract/product change.
- Success discriminant handling uses `CheckPurchaseResponse`:
  - `unresolved_identity`: show an actionable explanation naming the unresolved `brand`/`model`/`retailer`; for ambiguous and not-found statuses, invite correction. Do not expose internal candidate UUIDs.
  - `resolved` with `promotions.length === 0`: state no matching **published promotion** was found for these details; not “your purchase is ineligible everywhere”.
  - `resolved` with records: state the check returned **N promotion record(s) requiring eligibility review**; do not label all as claimable, show calculated sums, count “benefits you qualify for”, or render a partial results dashboard. Add a short note that detailed results are not yet shown.
- `ApiError.kind` (`validation`, `rate_limited`, `unavailable`, `timeout`, `cancelled`, `server`, `contract`) maps to plain safe text. For 422, invite review without claiming to know which field failed if server only supplies a generic problem. For 429, indicate wait/retry when `retryAfterSeconds` is available; for 502/503/504, say the checker is unavailable and keep entered values; for malformed results, report a service problem, **never** “no promotions”. Optional safe request ID may be shown for support.
- Do not show raw exception messages, backend hostnames, unvalidated HTML or source URLs. Existing HTTP status codes, RFC 9457-style problem payloads, correlation header, timeouts and retry policy are unchanged.
- Auth: none introduced. Preserve FE-03's no-cookie/no-authorization proxy boundary. No pagination/filter/sort or mutating side effects; purchase checks are read-only despite the POST transport.

---

## Domain and application behaviour

### Form data, validation and interaction

- All four fields start empty; no invented defaults (especially no current purchase date, brand or retailer). Labels remain visible even when values are entered.
- Text inputs are free-text because the repository currently exposes **no supported brand/retailer/model lookup endpoint**. Make this explicit in help text rather than mimicking an autocomplete with fake values.
- Use native semantic labels (`htmlFor`/`id`) and `name`, sensible autocomplete only where genuinely appropriate, and `type="date"` for date. Avoid `autoFocus` stealing focus from the skip link/header.
- Mark each field required. Validation must reject an empty/whitespace-only manufacturer, model and retailer; identity text >255 characters; invalid date including impossible leap dates; disallowed control characters as defined by the existing wire schema. Prefer precise, calm messages (for example, “Enter the retailer name”).
- Prevent native validation popups from undermining consistent accessible error presentation (`noValidate` if using custom validation); do not suppress validation itself. Validate on submit and, once touched/attempted, update invalid/error state when corrected without showing disruptive errors on initial load.
- Render error text adjacent to each affected field, associate via `aria-describedby`, set `aria-invalid` only for invalid fields, and focus the first invalid field on failed submit. Include a succinct form error summary if it improves accessibility without redundant announcements.
- Date semantics: use the browser date control's `value` as a string; no timezone adjustment. Keep consistent `en-GB` page language. Unit test leap-day valid and invalid cases; do not use a moving wall clock in validation.
- Submit CTA **“Find My Benefits”** or **“Check My Purchase”** (choose one consistent final label); button must be `type="submit"` because the existing reusable `Button` defaults to `type="button"`.
- Pending: set an accurate label such as “Checking…” and an accessible non-visual/polite status, disable duplicate submit and either lock field edits until settled or guard against stale results. Do not spin indefinitely; FE-03 applies its existing deadlines.
- Settle: preserve entered text; show one response area with appropriate `role="status"` for successful domain messages or `role="alert"` for failures; avoid `alert` + duplicated live region. Make feedback keyboard/screen-reader discoverable and move focus deliberately when warranted, without unexpected focus theft from field correction.
- Resubmit: corrected entries clear outdated response/error state and allow one new explicit attempt; no silent retries, automatic reruns or background calls. Do not leak previous request's success after input changes.

### Eligibility-specific rules

- **Owned entirely by backend.** FE-04 passes only the four user-supplied values. `resolved` vs `unresolved_identity` and the `promotions` list are authoritative output, not classifications inferred by the form.
- The five promotion eligibility classifications, claim windows, reward calculations, actual date eligibility, explanation codes and source provenance are **not** interpreted into user-facing claimability by FE-04; those belong to results UX work.
- Calendar-date precision remains date-only, and no client-side LLM, manufacturer account or promotion rule lookup may affect submission.

### Ingestion/publication rules

Not applicable. The frontend cannot publish, validate or retrieve promotion source data; the existing backend continues to use validated published promotions.

---

## Persistence, transactions, and migrations

**None.** No frontend storage, database writes, user-session state, migrations, backfills or server-side purchase history. A purchase check is an explicit read-only operation over the existing backend even though it uses HTTP POST.

---

## External services and network access

- Only the existing `POST /api/eligibility/check` same-origin browser request is used, via `useCheckPurchaseMutation` and `checkPurchase`. FE-03's server bridge alone contacts the configured FastAPI origin.
- Timeouts, response/body size limits, no-automatic-retry policy, forwarding rules, TLS policy, safe errors and correlation are inherited unchanged from FE-03.
- Missing `BENEFITSCOUT_API_ORIGIN` or unavailable upstream must produce a visible, recoverable error after a deliberate submission; **homepage rendering must not require any backend or environment variable**.
- Real-browser tests use a deterministic local fake upstream. IMPORTANT: its current `purchase_price === '799.99'` expectation is a **fixture limitation**, not the real backend contract. Extend the fixture to accept the valid four-field request (price absent), while retaining FE-03 tests that send `'799.99'` and their existing security/response checks.
- No manufacturer login, retailer networking, arbitrary user URLs, CORS changes, third-party fetches or provider credentials.

---

## Security and privacy

- Reuse the strict existing request schema; validate before mutation while preserving the backend as ultimate authority. Render all user-provided text as React text content; do not use `dangerouslySetInnerHTML`.
- No secrets in browser bundles or source. Do not forward cookies or authorization credentials; leave FE-03's allow-listed server origin and path unchanged.
- Never record purchase fields or returned promotion/source details in logging, analytics, query strings, storage or diagnostic error messages. Keep request IDs and low-cardinality error kinds only if diagnostics are needed.
- Do not interpolate user values into outbound URLs. The form always uses the fixed same-origin client.
- Defend against double clicks, empty/oversized strings and unexpected response shape through the existing frontend transport. No speculative auth or identity assumptions.

---

## Configuration and deployment

**No new variables or runtime services.** FE-03's existing `BENEFITSCOUT_API_ORIGIN` remains **server-only** and optional for build/page rendering, but necessary to complete a live check. No `NEXT_PUBLIC_*` API origin, manufacturer credentials or feature flags.

- Build still succeeds without a live backend. The form is visible regardless; a submission with no configured backend displays the correct availability error.
- Keep current frontend GitHub Actions, Next.js runtime, browser test ports, Node/pnpm pinning and deployment assumptions; modify fixture wiring only if truly required and document why.
- Update `frontend/README.md` and, if page copy changes a deliberate contract, metadata and production smoke assertions. Do not silently delete existing checks.

---

## Observability and operations

- Visual pending state, accurate success-domain state and safe recoverable error state are required. Distinguish validation (no request), unresolved identity (successful response), no matching promotions (successful response), and upstream/system failure.
- When useful for support, render `ApiError.requestId` as **request ID only**, never raw backend exception detail. No client analytics, extra error-reporting SDK, field-value telemetry or new metrics stack.
- Production browser tests must fail on console errors, uncaught page errors and unexpected network submission behaviour. Reuse existing Playwright reports and screenshots rather than adding an observability vendor.
- Backend health/readiness and domain instrumentation are unchanged.

---

## Failure, consistency, and recovery

| Scenario | Required user-visible and internal behaviour |
| --- | --- |
| One or more fields missing/invalid | Inline messages, focus first invalid field, **zero** network requests. |
| Multiple rapid submit clicks | Only one in-flight request and no double completion notification. |
| Timeout / network error / 502 / 503 / 504 | Truthful unavailable/timeout message, preserve values, manual retry possible. Never convert to no matching promotions. |
| 422 validation error | Generic safe correction advice; preserve fields. Do not invent a server field-level error mapping. |
| 429 rate limit | Show a safe wait/retry message; use bounded retry-after information if available; no automatic retry. |
| `unresolved_identity` success | Identify the unresolved field and distinguish not-found vs ambiguous in user guidance; not an HTTP failure or ineligible decision. |
| `resolved` with zero promotion records | State no matching *published* promotions for these details; not global proof of non-eligibility. |
| `resolved` with one/many records, including ineligible ones | Acknowledge number of records, not number of benefits the user can claim; no invented rewards. |
| Form changed after a previous result | Clear stale result/status; the previous check must never look like it applies to edited values. |
| Missing upstream configuration | Page and form still render; explicit submit receives recoverable unavailable response. |
| Unexpected reply / malformed contract | Show service-problem error, not false successful state; no sensitive payload shown. |

---

## Acceptance criteria

### Behaviour and UX

- [ ] `/` renders an accessible, reusable four-field purchase form using the reference screenshot's compact elevated-card/centred-CTA visual direction without copying unimplemented marketing content.
- [ ] Manufacturer, model, retailer and purchase date are visibly labelled, required and correctly ordered in DOM/tab order.
- [ ] Four fields generate `brand`, `model`, `retailer`, `purchase_date` using the FE-03 client; `purchase_price` is absent, never zero or fabricated.
- [ ] Blank/invalid text, overlength inputs, unsupported controls, invalid/nonexistent dates and empty fields are rejected before any network traffic; valid historical calendar dates are accepted.
- [ ] Valid explicit submit makes one POST via existing mutation, with pending and duplicate-submit protection; no automatic call occurs on render/typing/focus/reconnect.
- [ ] All success-domain variants (unresolved, resolved no-match, resolved records) are distinctly and truthfully acknowledged; the UI never labels promotion records as claimable solely because they were returned.
- [ ] Validation, API errors, timeout, rate limit and missing backend configuration are explained safely and permit correction/manual retry without losing user-entered details.
- [ ] Editing settled results clears stale status; no old response appears to validate a new draft.
- [ ] Form works with keyboard and assistive technologies, displays field-associated errors and announces progress/outcomes appropriately.
- [ ] At 320–1440px and large text the labels, inputs, CTA and messages remain readable and unclipped; the initial desktop viewport gives the checker visual priority.

### Data and consistency

- [ ] No backend schema, eligibility logic, production promotion data, ingestion or migrations are changed.
- [ ] Existing FE-03 wire types/Zod contract, error mapping and same-origin proxy are reused, not cloned or bypassed.
- [ ] Date remains ISO calendar-date string, without timezone conversion; model/SKU is not rewritten.
- [ ] No local persistence, manufactured defaults, sample rewards, real-brand promotional claims or static sample suggestions are shipped.

### Security and accessibility

- [ ] User input is rendered safely, and invalid input cannot trigger a request.
- [ ] No secrets, provider auth, browser cookies or unchecked outbound URLs are introduced.
- [ ] Focus-visible, field error association, status/alert announcement, no unexpected focus theft and no horizontal overflow are tested.
- [ ] Rendered form passes axe A/AA checks; manual screen-reader and native-zoom checks are documented as outstanding if not performed.

### Operations and code quality

- [ ] The real production-build Playwright flow exercises the **rendered form**, not only an `evaluate(fetch(...))` shortcut.
- [ ] The test upstream supports missing optional purchase price while FE-03's existing valid-price integration tests continue to pass.
- [ ] Existing page, layout, smoke, proxy, contract, CI and browser tests continue to assert meaningful behaviour; update intentionally obsolete placeholder assertions rather than removing coverage.
- [ ] No new form library or duplicate API stack is introduced without documented necessity.
- [ ] Format, lint, types, Jest, build, smoke and browser acceptance pass; any unexecuted commands and residual risks are reported.

---

## Tests to add or update

### Unit tests

- Focused pure helpers, if introduced, for mapping `{manufacturer,model,retailer,purchaseDate}` to the exact `PurchaseRequest` without price; Zod validity and calendar-date boundaries (e.g. valid leap day `2024-02-29`, invalid `2026-02-29`, non-date and malformed dates).
- RTL test `PurchaseInputForm.test.tsx` with a mocked `useCheckPurchaseMutation` or endpoint: labels, descriptions and field order; default empty state; empty/whitespace/overlong text; date validity; first-invalid-field focus and `aria-invalid`/described-by error; proper `type="submit"` button.
- Assert one exact request for valid entries and **zero** for invalid inputs and on mount/re-render/typing; assert `purchase_price` not sent, no timezone shift, no automatic retry, and no double-submit while pending.
- Mock each successful domain outcome and `ApiError.kind`; assert correct words/announcements, retained fields, manual retry and stale-status reset on change. Test a populated promotion classified `NOT_ELIGIBLE` to prove the form does not claim eligibility.
- Update `page.test.tsx` to cover the new heading/main and actual form/entry; preserve shell and skip-link semantics. No snapshots as a substitute for behavioural tests.

### PostgreSQL integration tests

**N/A.** No persistence or backend change. Do not introduce PostgreSQL/Testcontainers into frontend CI.

### API/application tests

- Existing FE-03 `eligibility.contract.test.ts` and route/client tests remain the source of API contract truth; no parallel API schema is created.
- If any form adapter is introduced, assert it calls the existing mutation with the exact supported keys and maps only existing backend outcomes.
- Verify no need to change OpenAPI, backend validation, REST endpoint or MCP contract.

### MCP contract tests

**N/A.** The browser uses the existing REST client, never MCP directly.

### External-boundary and browser acceptance tests

- Add `frontend/e2e/purchase-input.e2e.ts`, launched by existing Playwright production Next.js server and controlled HTTPS upstream fixture. Tests **fill real page controls and click the real CTA**; do not rely solely on `page.evaluate` to simulate the UI.
- Use fixture model cases to verify resolved/no-match, a populated-but-not-assumed-eligible result, unresolved model, 429, upstream-unavailable, and correction/manual retry. Assert `POST /api/eligibility/check` occurs once per valid explicit submission, and no request occurs on page load or invalid form submission.
- Modify `frontend/e2e/support-upstream.mjs` so omitted/null `purchase_price` is accepted as the real contract allows, but an unexpected price value or incorrect request structure still fails. Preserve FE-03's `'799.99'` test cases and existing handling of unsafe source data, rate limits and offline upstream.
- Include one browser path that exercises server response validation/error boundaries rather than bypassing the proxy. Do not depend on live brands or campaigns.
- Recheck viewport widths `320, 360, 375, 768, 1024, 1280, 1440` and CSS root-text-size 200% at `320`/`640`; assert no clipped label/control/CTA/status, horizontal scroll, overlap or broken tab focus. Run axe with the repository's WCAG A/AA tags against the **rendered interactive form**, including an invalid/error state.
- Update existing `shell.e2e.ts` whose assertions explicitly prohibit a form and expect placeholder copy. **Replace** these checks with equally strict real-form assertions; preserve header/footer, skip link, focus, reflow and production-console checks. Update smoke only where truly tied to old placeholder copy.
- Manual follow-up: native browser 200% zoom; VoiceOver/NVDA label/error/status readout; date picker behaviour in UK browser locale.

---

## Verification commands

Run from repository root unless indicated. Establish that scripts are unchanged immediately before implementation.

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

In Linux CI, existing workflow uses `pnpm exec playwright install --with-deps chromium`. If new tests require supplementary fixture setup, prefer the already configured `frontend/playwright.config.ts` server orchestration; do not introduce an untracked local service or external dependency.

If any command cannot be run, report **the exact command**, environment/blocker, alternative verification and remaining risk. Do not weaken tests to make them pass. Browser tests are required, not optional just because Jest passes.

---

## Completion report

When implementing this spec, report:

### Changed

The four-field form, homepage integration, validation/pending/response UI, documentation and deliberate test modifications.

### Database and migrations

`None`.

### API/MCP contracts

`None` — existing FE-03 frontend client and FastAPI contract reused, `purchase_price` omitted by this form.

### Tests and verification

List actual unit, RTL, same-origin browser, reflow, accessibility, and production smoke tests added/updated, the commands executed and their outcomes. Do not claim unrun tests passed.

### External configuration

No new configuration. Remind deployers that live checks require the pre-existing server-side `BENEFITSCOUT_API_ORIGIN`; page/build do not.

### Deviations

Identify changes beyond the expected surface or agreed UX and explain why they were necessary. Use `None` otherwise.

### Remaining risks or follow-up

Detailed eligibility/results and claim guidance, optional purchase price, real lookup/autocomplete, full homepage content, account/saved-purchase flows and any manual native-zoom/screen-reader testing not completed belong to future work. Report other open risks explicitly.
