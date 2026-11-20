# FE-10 — Claim Preparation Guide

## Repository state

**Expected branch:**  
`fe-10-claim-preparation-guide` (create from the current `main` after checking for concurrent changes)

**Base branch:**  
`main`

**Dependencies:**

- FE-01–05: Next.js App Router, React/TypeScript, Tailwind, shared UI, typed API, server-side upstream origin configuration, and purchase checker.
- FE-06/07: `/results` cards and five backend-owned eligibility classifications. FE-10 must not silently alter or re-evaluate any classification.
- FE-08 / merged PR #44: recorded reward and claim-window presentation helpers; reuse the terminology rather than introducing competing calculations.
- FE-09 / merged PR #45: public `/promotions/[slug]`, canonical `manufacturer-slug--promotion-slug`, published-only GET projection, strict `promotionDetailsSchema`, `getPromotionDetails`, and one-to-many variants/requirements. **This is the source of truth for FE-10.**
- Backend's existing read-only `GET /api/v1/promotions/{manufacturer_slug}/{promotion_slug}`. **No new backend capability is expected.**

### Read first

- `.codex/tasks/TEMPLATE.md`; root `AGENTS.md`; any scoped `AGENTS.md` present when implementation begins.
- `.codex/tasks/{fe-06-eligibility-results-overview,fe-07-eligibility-status-explanations,fe-08-rewards-claim-windows,fe-09-promotion-details}.md`.
- `frontend/src/app/promotions/[slug]/{page,page.test,error,not-found}.tsx` (where present).
- `frontend/src/features/promotions/details/{PromotionDetailsView,PromotionDetailsView.test,VariantHashFocus}.tsx`.
- `frontend/src/lib/api/{promotion-details.contract,promotion-details.server,promotion-details.fixture,promotion-slug,eligibility.contract,errors,http,config}.ts`.
- `frontend/src/features/eligibility/results/{ResultsOverview,ResultsOverview.test,ClaimWindowSummary,presentation}.t[sx]`.
- `frontend/src/components/ui/{ButtonLink,Card,Container}.tsx`, `frontend/e2e/{promotion-details.e2e.ts,purchase-results.e2e.ts,support-upstream.mjs,support-layout.ts}`, `frontend/package.json`, `frontend/playwright.config.ts`, `frontend/README.md`.

### Primary change area

An accessible, directly navigable public **claim-preparation** page at `/promotions/[slug]/claim` for an individual **published promotion variant**. It presents the verified, recorded claim requirements as a user-controlled checklist and provides a safe link to the official provider's claim site. It does **not** collect evidence, establish personal eligibility, or submit a claim.

### Canonical implementation examples

- `PromotionDetailsView.tsx` already displays each variant separately, including its `requirements` by stable `requirement_id`, optional descriptions and requirement-type labels. Extract/reuse its labels rather than introducing an inconsistent mapping.
- `PromotionDetailsView.tsx` already links to `promotion.provenance.claim_url` and official terms; match its external-link conventions and disclaimers.
- `getPromotionDetails(publicSlug)` is a server-only, `cache: 'no-store'`, bounded read that rejects malformed slugs, inconsistent API data and unsafe URLs, and returns `null` for an unpublished/unknown record. Reuse it unchanged.
- `promotionDetailsSchema` validates manufacturer-qualified public slugs, published variants, UUIDs, requirements, official source URLs and the verified claim source. Do not parse or scrape the claim website.
- `frontend/src/app/promotions/[slug]/page.tsx` and its error/not-found states establish the Server Component route conventions and safe, recoverable load behaviour.
- `frontend/e2e/promotion-details.e2e.ts` and `support-upstream.mjs` establish deterministic direct-route, navigation, accessibility and error fixtures.

### Relevant symbols

`PromotionDetails`, `PromotionDetails['variants'][number]`, `promotionDetailsSchema`, `getPromotionDetails`, `parsePublicSlug`, `PromotionDetailsView`, `VariantDetails`, `recordedTerms`, `requirement_id`, `requirement_type`, `provenance.claim_url`, `provenance.official_source_url`, `sources[].role`, `VariantHashFocus`, `ButtonLink`, `Card`, `Container`, `ApiError`, `calendarDate`, `timestamp`, `getApiOrigin`.

### Expected change surface

```text
.codex/tasks/fe-10-claim-preparation-guide.md                # this specification
frontend/src/app/promotions/[slug]/claim/page.tsx           # server-rendered claim guide
frontend/src/app/promotions/[slug]/claim/page.test.tsx      # resolution and route states
frontend/src/app/promotions/[slug]/claim/error.tsx          # optional scoped retry boundary
frontend/src/app/promotions/[slug]/claim/not-found.tsx      # optional, if required by routing
frontend/src/features/promotions/claim/ClaimPreparationGuide.tsx
frontend/src/features/promotions/claim/ClaimChecklist.tsx  # client-only checklist state
frontend/src/features/promotions/claim/ClaimChecklist.test.tsx
frontend/src/features/promotions/claim/requirements.ts     # optional shared pure presentation mapping
frontend/src/features/promotions/claim/requirements.test.ts
frontend/src/features/promotions/details/PromotionDetailsView.tsx
frontend/src/features/promotions/details/PromotionDetailsView.test.tsx
frontend/e2e/promotion-claim.e2e.ts
frontend/e2e/promotion-details.e2e.ts                       # extend cross-route journey
frontend/e2e/support-upstream.mjs                           # only if test variants are missing
frontend/README.md                                        # concise route/limitations note
```

If adding an entry point on `/results` is small and does not obscure eligibility messaging, extend `ResultsOverview.tsx` and its tests; the route must already be fully reachable from FE-09 without it. File paths are guidance, not permission for an unrelated refactor. Do not create duplicate definitions of requirement names or official-link validation.

### Excluded areas

- No backend API, MCP, database schema, migration, ingestion, publication or eligibility-rule change.
- No claim submission, upload/storage of receipts, invoice scans, serial numbers, IMEIs, personal details or claim status; no form posting to the provider.
- No user accounts, persistence, localStorage/sessionStorage, cookies, analytics containing checklist/evidence details, reminders, notifications or automated follow-up.
- No automatic eligibility determination, personalised claim-window calculation, claim deadline countdown, claim acceptance, reward approval or payout estimation.
- No AI-generated evidence, inferred requirements from benefit descriptions, live official-site scraping or invented registration instructions.
- No new promotion listing route, global redesign, package migration or unrelated FE-08/09 refactor.

### Unknowns Codex must verify

1. Current `main`, pending PRs, scoped guidance and any changes to FE-09 after PR #45 was merged.
2. Whether the claim route already exists; do not duplicate it.
3. Whether all seven published requirement types (`receipt`, `serial_number`, `registration`, `invoice`, `barcode`, `imei`, `installation_evidence`) retain their current meanings and optional descriptions in the live DTO.
4. Whether any published variant can have zero requirements (the existing strict Zod schema allows this), and how the parent guide should explain the empty state.
5. Whether actual published projection and fixture preserve unique IDs for requirements inside a variant; confirm no cross-variant assumption is being made.
6. Whether an existing shared official-link component/requirements label presenter has landed since inspection; reuse it if available.
7. The actual App Router `params`/`searchParams` types, existing route error boundaries, and accessibility baseline.
8. Current toolchain pins: at inspection `frontend/package.json` specified Node 24.x, pnpm 12.16.1, Next 16.4.2; verify `.node-version`, lockfile and CI before running commands, as old README instructions may differ.

---

## Objective

A visitor can open `/promotions/<manufacturer-slug>--<promotion-slug>/claim` directly, choose the correct published variant when necessary, and use a practical checklist to prepare the **recorded** claim evidence/actions. They can review official terms and open the **verified official claim destination** themselves. The guide works in a fresh tab without a purchase-check session.

**Definition of done:** the correct variant's original requirements appear as keyboard-accessible checkboxes; checking/unchecking updates a truthful progress summary; navigation or reload cannot expose a different variant's checklist as if it applied; the recorded official claim link works safely; unknown, unpublished and malformed promotions never render a successful guide; existing detail/results screens continue to work.

### Design intent and UX description

**Within five seconds**, the visitor should understand which promotion and variant they are preparing for, what evidence is recorded as necessary, and where the official claim starts.

1. **Context header:** a valid link back to the exact `/promotions/[slug]` page; promotion name, manufacturer and heading **Prepare your claim**; a brief explanation: “Use this checklist to prepare the requirements recorded for this promotion. The official provider confirms eligibility and handles your claim.”
2. **Variant identity:** show variant name or code and any recorded retailer/product context needed to distinguish variants. For multiple variants, show a compact accessible variant chooser **before** the checklist; never automatically merge all variants.
3. **Evidence and actions checklist:** an ordered-in-source list of checkboxes with human-readable requirement type and the recorded description. Intro: “Tick each item when you have it ready or have completed the action.” Include a clear progress statement, for example “2 of 4 items marked ready.”
4. **Official next step:** an always-visible “Open official claim site” link with “opens in a new tab” text and a statement that the external provider controls eligibility, submission, deadlines and acceptance. Do not relabel it “Submit claim”.
5. **Terms and timing context:** a secondary “Read official terms” link, last-verified timestamp, and concise recorded claim-window *definition* (fixed dates/relative days/minimum wait), reusing FE-09 copy/presenter when appropriate. Do not suggest a personal deadline or that the window is presently open.
6. **Navigation:** “Back to promotion details” returns to the same canonical slug, optionally `#variant-<uuid>`; “Check my purchase” points to `/check` if a neutral extra action is useful.

Use existing FE-02 tokens, responsive cards, readable spacing, one `h1`, semantic sections, native controls, visible keyboard focus and text-based meaning. Mobile is a single-column reading order; desktop may separate checklist from official next steps. Do not put decorative elements above the useful checklist.

### Route and variant selection

Canonical route:

```text
/promotions/<manufacturer-slug>--<promotion-slug>/claim
/promotions/<manufacturer-slug>--<promotion-slug>/claim?variant=<promotion_variant_id>
```

- The server must call the existing `getPromotionDetails(slug)` exactly once per route render. Use `params: Promise<{ slug: string }>` and `searchParams` per the checked-in Next version. The public slug is already validated by the FE-09 client; do not invent a second parser.
- A `variant` query parameter, if present, must be exactly one valid UUID from **the returned published promotion's** `variants` array. Invalid, repeated or unknown values must produce an explicit non-success state (prefer a 404), **never** silently fall back to another variant. The query parameter is an identifier only, not a requirement definition or URL.
- With **one variant** and no query parameter, select it automatically. With **multiple variants** and no query parameter, present a chooser and **do not show any checklist as implicitly applicable** until one variant is selected.
- Variant chooser items must link to the same canonical route with `?variant=<id>`, have unique descriptive accessible names (variant label/code and, when necessary, retailer/model), and expose the selected choice in text/semantics. Do not rely on colour alone.
- FE-09's `VariantDetails` should offer a “Prepare claim checklist” link for **each variant** using that variant's ID; a results-card shortcut is optional, but if present must use the response's typed `public_slug` and `promotion_variant_id` (never display names). Use internal Next.js links, never arbitrary user-provided hrefs.
- No purchase details, personal data, serial numbers or receipt data may appear in query parameters, hashes, server logs or browser persistence.
- A fresh-tab load, back/forward navigation and refresh must resolve the same public records; users must not need `/results` or the in-memory purchase-check session.

---

## Architecture and invariants

1. **Published-only source:** `getPromotionDetails` and `promotionDetailsSchema` own the read contract; unpublished/malformed records are not usable. Do not fetch the backend directly from a Client Component.
2. **Variant isolation:** selected `promotion_variant_id` determines exactly one `variants[].requirements[]`; preserve source order and `requirement_id` identity. Do not deduplicate by `requirement_type` or merge across variants.
3. **Recorded rather than inferred requirements:** the seven allowed types and optional `description` are the only checklist inputs. Do not treat benefit descriptions, product metadata or external page text as extra requirements.
4. **Checklist as local UI state:** checkbox truth means **visitor marked ready**, not “evidence validated” or “claim completed”. State lives in a small Client Component, scoped to the selected variant's identity. No writes, persistence, analytics events or network requests when an item is checked.
5. **No implicit unlock:** the official claim link remains usable regardless of checklist completion; the guide does not disable a legitimate official destination based on self-reported ticks.
6. **Authority over timing/status:** publication `status` is not personal eligibility; configured `claim_window` is not a calculated or live claim window. No client clock, countdown, date arithmetic or eligibility rules.
7. **Official destination only:** render exactly `promotion.provenance.claim_url` from the strict FE-09 DTO; `sources` and `provenance` consistency is already validated. No redirect endpoint, pasted link, inferred host or fallback to unverified data.
8. **No sensitive data handling:** do not ask the user to enter receipt numbers, IMEIs, card details, home address or other evidence content into the checker.
9. **Readable failure:** missing, withdrawn, corrupt or temporarily unavailable data must not appear to be a complete checklist or a working provider link.
10. **Minimal client surface:** server handles published details and selected variant; client handles checkboxes only. Reuse FE-09 tests, presenters, semantic links and responsive design.

---

## API and contract changes

**None.** Reuse the existing read-only `GET /api/v1/promotions/{manufacturer_slug}/{promotion_slug}` via the Next server's `getPromotionDetails` client and the strict `PromotionDetails` Zod type. No new HTTP methods, Next proxy routes, REST/MCP schemas, OpenAPI updates, authentication or backend mutation.

### Existing fields used

| Existing field | FE-10 usage |
| --- | --- |
| `promotion.public_slug` | Canonical page identity and internal links |
| `promotion.name`, `manufacturer.name`, `status` | Heading/context, recorded publication state only |
| `variants[].promotion_variant_id`, `code`, `name` | Explicit variant selection and checklist state isolation |
| `variants[].retailer`, `products[]` | Disambiguation of variant choice |
| `variants[].requirements[].requirement_id` | Unique checkbox ID and React key |
| `variants[].requirements[].requirement_type`, `description` | Recorded checklist label and optional safe plain-text explanation |
| `promotion.claim_window` | Configured timing explanation, not personalised calculation |
| `promotion.provenance.claim_url` | Verified official external claim destination |
| `promotion.provenance.official_source_url`, `last_verified_at` | Terms link and provenance label |

Request and response: unchanged. Public GET and no cookies/credentials; preserve existing no-store caching, bounded response size, timeout and error/problem mapping. A failed published details read must not be replaced with static fixtures or stale browser state.

---

## Domain and application behaviour

### Checklist item presentation

- Map current published values to visible labels: `receipt` → **Receipt**; `serial_number` → **Serial number**; `registration` → **Registration**; `invoice` → **Invoice**; `barcode` → **Barcode**; `imei` → **IMEI**; `installation_evidence` → **Installation evidence**. Reuse/extract the FE-09 mapping.
- Render each returned requirement as its **own** checkbox even when types repeat; track checked items by `requirement_id`, not index or type. Show the recorded description as escaped text; never execute HTML/Markdown from a source.
- Treat `registration` and similar steps as recorded **actions**, not necessarily a document file. The guide is an “Evidence and actions” checklist, not an upload form.
- Initial checked count is `0`. Clicking/keyboard toggling one checkbox changes only that item and updates `X of N items marked ready`. Unchecking reverses the count. Ticks must never modify source requirements or the server payload.
- A selected-variant change must never transfer checked items from the previous variant. Key the client checklist by the variant UUID or explicitly reset on selection change. Reload may reset all ticks; tell the user the checklist is not saved if that might otherwise surprise them.
- When all available items are ticked, say **All recorded items marked ready**, *not* “Eligible”, “Claim approved”, “Claim submitted” or “Guaranteed”. Do not call a zero-item checklist complete.
- If requirements are empty, show **No claim requirements are recorded for this variant. Review the official terms before proceeding.** Suppress `0 of 0` readiness/completion UI, but retain the verified official link and terms.
- If a variant selector is visible but no variant is selected, show a neutral instruction **Choose a promotion variant to see its requirements**, not a combined or empty checklist.

### Timing, publication and links

- Show recorded `active`/`expired` publication state as such, while reminding the visitor this does not establish whether *their purchase* qualifies.
- A fixed claim-window display may show `opens_on`, `deadline_on` and `minimum_days_after_purchase` as FE-09 already does. A relative window may show the recorded number of calendar days after purchase. A null window must say timing is not recorded. Do not derive date boundaries from today's date or ask for new purchase data to compute dates here.
- Place the official claim link near checklist completion/progress **and keep it visible when some items remain unchecked**; it is a voluntary external navigation, not a form submission. Preserve `target="_blank" rel="noopener noreferrer"` and a clearly spoken new-tab cue.
- “Read official terms” points to the validated `official_source_url`. The user may leave to the provider and return without receiving any confirmation within this app.
- Safe text and URL rendering must use the existing FE-09 schema. If a claim URL violates that contract, fail the page read through the established safe error boundary; never print or navigate to the unsafe value.

### Failure and navigation cases

| Case | Required UI |
| --- | --- |
| Valid single-variant promotion, no `variant` | Correct checklist and official links |
| Valid multi-variant promotion, no `variant` | Explicit chooser; no combined checklist |
| Valid `variant` belonging to returned promotion | Exactly that variant's requirements, unique context and links |
| Invalid, repeated or unknown `variant` | Non-success response, no misleading fallback or official action |
| Unknown/malformed/nonpublished promotion | Existing public 404 semantics |
| Backend outage/timeout/invalid DTO/unsafe URL | Recoverable safe error state, no stale checklist/provider action |
| Empty `requirements` | Clear no-requirements-recorded explanation and official terms |
| Page refresh or fresh tab | Published content available, previous ticks not claimed as saved |
| Checklist changed | No API POST, cookie/local storage or persistence write |

---

## Persistence, transactions, and migrations

**None.** No SQLAlchemy/Alembic changes and no new tables, persisted claims, saved checklists or browser storage. No PostgreSQL integration tests or migration verification are necessary for this frontend-only work. The existing backend published projection remains authoritative and is already covered by FE-09 tests.

---

## External services and network access

- **Existing server read only:** `getPromotionDetails` fetches the existing API using validated server-side origin, no-store caching, bounded body and timeout; preserve its retry/error policy rather than adding another client.
- **Official external navigation:** the browser opens `provenance.claim_url` and `provenance.official_source_url` only following an explicit link activation. This is not an application-service request; do not prefetch/scrape the external provider, retry its claims or assume its availability.
- **Tests:** verify `href` and `rel` without making a live request to a manufacturer. Use current deterministic FE-09 upstream fixture and mocked server client for route unit tests.

---

## Security and privacy

- FE-10 is a **public informational** route and must not require authentication. It must not expose unpublished promotions or rely on a visitor's purchase-check session.
- Trust only the strict published API DTO, including URL scheme and source/provenance coherence. Do not use `dangerouslySetInnerHTML`, execute source text, accept arbitrary query-driven official destinations, or construct external URLs from user text.
- Validate the `variant` identifier against the returned publication, not just UUID syntax; guard duplicate query parameters and accidental fallback to a different variant.
- Use accessible native checkbox labels and safe IDs derived from validated UUIDs. Avoid UI that asks visitors to type, upload, paste or otherwise expose sensitive evidence.
- No personal data, evidence details or checked-item state in server logs, analytics, query parameters, cookies, network requests or browser storage.
- Preserve privacy-sensitive distinction between “marked ready” and “provider verified”; do not imply the site has checked a receipt, application or identity.
- External links must include `noopener noreferrer`; keep the provider's site responsible for its own security, claim processes and privacy notices.

---

## Configuration and deployment

**None.** Reuse the existing `BENEFITSCOUT_API_ORIGIN` on the Next server and the current backend rollout. No new environment variables, secrets, workers, cron, database connections, Docker changes or auth configuration are expected. Verify existing frontend CI/build and public route operation before completion.

---

## Observability and operations

- Preserve FE-09's safe `promotion_details_read_failed` logging/error classification (or its current equivalent) for upstream failures. Do not log private checklist state, full URLs with query credentials, purchase data or evidence.
- New success/checkbox interactions need no analytics or telemetry system. If a route-specific error event is justified, use a low-cardinality constant and preserve the existing request ID and error kind, without PII.
- Backend health/readiness and claim-provider availability are not controlled by FE-10; do not introduce live official-site health checks.

---

## Failure, consistency, and recovery

- The guide is read-only; no partial backend write or distributed consistency concern exists.
- If a published promotion disappears or is withdrawn before a fresh page load, show 404; never use a previously cached checklist to preserve access to it.
- If upstream fetch fails, times out or returns invalid/unsafe data, show the established retry/error state. Retry should re-read the authoritative published data; do not surface static fixture content in production.
- If a visitor changes variants, ensure the new checklist starts with no inherited marks. If they reload or close the tab, no saved-progress guarantee exists.
- If official terms change after source verification, present the recorded `last_verified_at` and tell visitors to verify the provider's current terms; never imply live source verification.
- If an external provider returns an error after navigation, it remains their workflow; FE-10 cannot track or reconcile the outcome and must not fake submission success.

---

## Acceptance criteria

### Behaviour

- [ ] `/promotions/[slug]/claim` loads a real published promotion in a fresh tab, directly and after refresh, with no `/results` session and no extra purchase-check POST.
- [ ] Promotion details include a working per-variant “Prepare claim checklist” link with the correct canonical `public_slug` and `promotion_variant_id`.
- [ ] Single-variant routes work without a query; multi-variant routes without `variant` present a chooser and no ambiguous checklist.
- [ ] Valid `?variant=<uuid>` shows **only** the selected variant's requirements, in recorded order, with readable labels/descriptions and unique IDs.
- [ ] Invalid/unknown/repeated `variant` never falls back silently to another checklist or shows a misleading official action.
- [ ] Each checkbox works by mouse, touch and keyboard; count updates on check and uncheck; duplicates of the same requirement type remain independent.
- [ ] Changing variant does not carry ticks across; reload does not claim saved progress.
- [ ] Zero requirements yields an explicit truthful empty state, not “ready” or `0 of 0 complete`.
- [ ] The official claim action is visible regardless of progress and leads to the validated `provenance.claim_url`; terms link leads to `official_source_url`, with accessible new-tab explanation.
- [ ] Active/expired publication, configured timing and checklist progress are never represented as personal eligibility, claim submission or approval.
- [ ] FE-08/09 details and five-status results presentation remain unchanged apart from intentional links.

### Data and consistency

- [ ] All requirement items originate from the FE-09 validated published DTO; there is no inferred evidence or combined variant list.
- [ ] No new schema, API, backend mutation, local storage, user account or evidence persistence is introduced.
- [ ] Authored source descriptions are escaped text; malformed published data cannot render a successful claim guide.

### Security and accessibility

- [ ] Unknown/nonpublished/malformed promotions map to 404; infrastructure/contract failures present a safe retry state.
- [ ] Unsafe URLs, non-HTTP(S) destinations and unverified claim-source mismatches are rejected by the existing contract.
- [ ] Native label/checkbox association, visible focus, variant chooser accessibility, meaningful live progress and external-link text meet keyboard and screen-reader expectations.
- [ ] WCAG A/AA automated audit has no violations on selected, unselected, empty and error states; manual focus/order/reflow tests pass at 320px and 200% text scaling.
- [ ] No PII/evidence entered, stored, transmitted or logged by FE-10.

### Operations and code quality

- [ ] No new external dependency, direct client-side backend fetch or unbounded network operation.
- [ ] The code follows current App Router Server/Client Component boundaries, FE-09 types, shared components and official-link convention.
- [ ] Targeted tests, lint, formatting, typecheck, full frontend tests, build, smoke and applicable Playwright suite pass; report unavailable checks transparently.

---

## Tests to add or update

### Unit tests

`frontend/src/features/promotions/claim/ClaimChecklist.test.tsx` and optional `requirements.test.ts`:

- All seven types have readable labels, exactly as existing FE-09 labels; preserve optional descriptions and order.
- Duplicate requirement types with distinct IDs create separate controls and count correctly.
- Initially zero checked; mouse and keyboard toggling advances/reverses progress; all checked yields **marked ready**, never **eligible/claimed**.
- Empty requirements shows official-terms guidance and **not** a completion message.
- Switching component key/variant resets state and does not leak ticks; no localStorage/sessionStorage/cookie writes.
- Official claim/terms anchors have validated fixture destinations, `target="_blank"` and `rel="noopener noreferrer"`, independent of checklist status.
- No dynamic date derivation, claim status or backend-owned eligibility computation.

### PostgreSQL integration tests

**N/A** — persistence is unchanged; keep FE-09 backend read projection tests intact.

### API/application tests

`frontend/src/app/promotions/[slug]/claim/page.test.tsx`:

- Direct single-variant, multi-variant chooser, valid selected variant and correct one-call `getPromotionDetails` integration.
- Invalid, repeated, malformed or unknown variant query; unknown/nonpublished public slug; malformed canonical slug.
- Simulated `ApiError('unavailable')`, timeout, contract failure: expected scoped or parent recoverable error boundary, no external claim action in an error state.
- No purchase session access or new POST; route URLs contain only canonical slug and variant ID.
- Test returned data comes from the mocked existing validated reader; do not mock a second invented contract.

Existing backend REST/MCP and OpenAPI contracts: **no changes**; no new backend tests required unless the implementation uncovers and separately scopes an actual defect.

### MCP contract tests

**N/A** — MCP remains unchanged.

### External-boundary and browser tests

`frontend/e2e/promotion-claim.e2e.ts`, with updates to `promotion-details.e2e.ts` and deterministic `support-upstream.mjs` where needed:

- `/results` → FE-09 detail variant → FE-10 selected checklist; route contains the correct UUID. Check details → claim navigation even without an existing results session.
- Direct fresh-tab route, reload, back/forward and multi-variant selection (including an unselected chooser).
- Recorded receipt/other evidence/actions, independent same-type entries, count changes, unchecking, all-ready copy and zero-requirements variant.
- Claim and official-terms anchors: correct `href`, new-tab attributes, no actual external manufacturer request or simulated successful submission.
- Invalid/missing/nonpublished slugs, unknown/repeated variants, 503, malformed upstream payload and unsafe URL produce safe 404/error UI.
- 320, 360, 375, 768, 1024, 1280 and 1440px reflow; 200% text; keyboard tab/space activation; axe WCAG A/AA on populated and error views.
- Assert no browser console errors, horizontal overflow, phantom submission requests, disabled-only claim navigation or dependency on today's date.

Use fixed fixtures; no live manufacturer websites, accounts or AI services in automated tests. Tests must prove behavioural outcomes, not merely that components rendered.

---

## Verification commands

Verify the currently checked-in runtime and lockfile first. At inspection, `frontend/package.json` specifies Node 24.x and `pnpm@12.16.1`. Run from `frontend/`:

```bash
pnpm install --frozen-lockfile

# Targeted tests (adjust the exact paths if colocated files differ)
pnpm exec jest src/app/promotions/'[slug]'/claim src/features/promotions/claim --runInBand
pnpm exec playwright test e2e/promotion-claim.e2e.ts e2e/promotion-details.e2e.ts

# Required frontend checks
pnpm format:check
pnpm lint
pnpm typecheck
pnpm test
pnpm build
pnpm smoke
pnpm test:e2e
```

Install Playwright's Chromium with `pnpm exec playwright install chromium` if required by the environment. These commands are based on the observed package scripts; verify against the actual runner/CI before treating them as final. **This is a specification, not an implementation report: no tests have been executed for FE-10.**

If a check cannot be run, document (1) intended command, (2) blocker, (3) alternative verification, and (4) remaining risk. Do not weaken meaningful tests or mark queued/hung CI checks as passed.

---

## Completion report

When FE-10 is implemented, report:

### Changed

Routes, variant-selection behaviour, checklist component, official links and navigation changes with exact paths.

### Database and migrations

`None` expected.

### API/MCP contracts

`None` expected; confirm the existing published details read remains unchanged.

### Tests and verification

Exact targeted/unit/browser/accessibility checks **actually run**, failures, workarounds, skipped tests and CI status.

### External configuration

`None` expected beyond existing FE-09 `BENEFITSCOUT_API_ORIGIN`.

### Deviations

Any approved departure from a per-variant checklist, stateless progress, validated claim destination or existing public read contract, with rationale.

### Remaining risks or follow-up

Record incomplete official terms, unsupported requirement types, provider-site changes, or UX limitations for a separate task. The application neither holds submitted evidence nor confirms claim acceptance.
