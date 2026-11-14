# FE-08 — Rewards & Claim Windows

## Repository state

**Expected branch:**  
`fe-08-rewards-claim-windows` (create from current `main` after checking branch/PR state)

**Base branch:**  
`main`

**Dependencies:**

- FE-01–05: Next.js App Router, typed purchase-check response, purchase form, one-shot mutation, and in-memory response handoff.
- FE-06: `/results`, `ResultsOverview`, promotion cards, five-status filters, Rule Matrix, safe official links and browser acceptance tests.
- FE-07: existing `EligibilityExplanation` / `explainPromotion`, which show authoritative status, rule evidence and claim timing. **Extend/consolidate; do not introduce another results page or contradictory claim details.**
- Backend published promotion, reward and claim-window projection contracts. FE-08 is frontend-only.

### Read first

- `.codex/tasks/TEMPLATE.md`, repository `AGENTS.md`, and any new scoped `AGENTS.md`.
- `.codex/tasks/{fe-03-api-client-configuration,fe-05-purchase-check-integration,fe-06-eligibility-results-overview,fe-07-eligibility-status-explanations}.md`.
- `frontend/src/app/results/{page,page.test}.tsx`.
- `frontend/src/features/eligibility/results/{ResultsOverview,ResultsOverview.test,EligibilityExplanation,explanations,explanations.test,presentation,presentation.test}.t[sx]`.
- `frontend/src/features/eligibility/session/PurchaseCheckSession.tsx` and `frontend/src/lib/api/{eligibility.contract,promotion.fixture,fixtures}.ts`.
- `frontend/e2e/{purchase-results.e2e.ts,support-upstream.mjs,support-layout.ts}`, `frontend/package.json`, `frontend/playwright.config.ts`, and `frontend/README.md`.
- Backend, **for interpretation only**: `backend/app/api/schemas/eligibility.py`, `backend/app/domain/{benefits,rewards,claim_windows,eligibility_result}.py`, `backend/app/application/{purchase_check,purchase_check_details}.py`.

### Primary change area

The `/results` presentation of **each matching promotion variant's** recorded benefit(s), cashback value or unavailable-value explanation, and claim-period opening/deadline dates, with plain-English next-step context.

### Canonical implementation examples

- `ResultsOverview.tsx` already renders benefit names, returned cashback values, missing-value explanations, an upcoming-only “Claim Window Guide”, and full-details disclosure (requirements, sources and official claim link).
- `EligibilityExplanation.tsx` already shows `claim_window_status`, `opens_on`, `deadline_on` and `evaluation_date`; FE-08 must centralise that presentation rather than leaving duplicated independent date displays.
- `presentation.ts` already has `gbp`, `calendarDate`, five classification labels, counts and filters; extend with small pure presenters instead of adding reward/eligibility logic.
- `eligibility.contract.ts` is the canonical Zod wire schema. `PurchaseCheckSession` holds the exact `{submittedPurchase,response}` snapshot in memory; `/results` performs no check or fetch on render.
- The backend calculates fixed/percentage/product-specific monetary rewards using `Decimal`, and evaluates fixed/relative/minimum-wait claim windows as inclusive calendar dates. FE-08 displays the projected result; it must not reproduce these calculations.

### Relevant symbols

`ResultsPage`, `ResultsOverview`, `PromotionCard`, `RuleMatrix`, `EligibilityExplanation`, `explainPromotion`, `calendarDate`, `gbp`, `Promotion`, `CheckPurchaseResponse`, `promotionSchema`, `usePurchaseCheckSession`, `BenefitType`, `RewardUnavailableReason`, `ClaimWindowStatus`, `ClaimWindowEvaluation`, `calculate_reward`, `POST /api/eligibility/check` (frontend bridge), `POST /api/v1/eligibility/check` (backend).

### Expected change surface

```text
.codex/tasks/fe-08-rewards-claim-windows.md            # this task
frontend/src/features/eligibility/results/ResultsOverview.tsx
frontend/src/features/eligibility/results/ResultsOverview.test.tsx
frontend/src/features/eligibility/results/EligibilityExplanation.tsx
frontend/src/features/eligibility/results/explanations.ts       # if consolidating timing copy
frontend/src/features/eligibility/results/explanations.test.ts
frontend/src/features/eligibility/results/presentation.ts
frontend/src/features/eligibility/results/presentation.test.ts
frontend/src/features/eligibility/results/RewardDetails.tsx     # optional focused component
frontend/src/features/eligibility/results/ClaimWindowSummary.tsx # optional focused component
frontend/src/features/eligibility/results/rewards.ts            # optional pure presenter
frontend/src/features/eligibility/results/rewards.test.ts
frontend/e2e/purchase-results.e2e.ts
frontend/e2e/support-upstream.mjs                    # only if deterministic cases needed
frontend/src/lib/api/promotion.fixture.ts            # only for realistic fixtures
frontend/README.md                                   # concise behaviour documentation
```

The file list is guidance. Explain any additional changes. Avoid inflating the existing large `ResultsOverview.tsx` if small typed presenters/components improve clarity.

### Excluded areas

- No backend domain, reward calculations, claim-window evaluation, promotion ingestion/publication, persistence, migrations, REST or MCP changes.
- No new purchase check on `/results`, reward calculations in React, wall-clock countdown, automatic refresh or date-derived claim classification.
- No authentication, saved results, claim submission, document upload, payment approval/tracking, alerts, reminders, notification delivery or customer support functionality.
- No invented warranty duration/coverage, free-gift model/value, cashback percentage, cap, total benefit value, or claim instructions parsed from free text.
- No FE-09 `/promotions/[slug]` route, broad redesign, new form fields, second state store, or changes to existing eligibility precedence, session lifecycle or filters.
- Do not turn a listed claim requirement into a failed rule or pretend a claim was submitted/approved.

### Unknowns Codex must verify

1. Current `main` HEAD, open FE-07/08/09 PRs and relevant changes before implementation.
2. Backend response and current Zod contract agree for benefit fields, missing-value reason enums and nullable claim timing; confirm any drift, do not invent fields.
3. Whether `EligibilityExplanation`, existing Claim Window Guide and full-details disclosure duplicate date/status content, and which component should own a single canonical presentation.
4. Whether variant/benefit IDs and accessible names remain unique for multiple benefits or duplicate promotion IDs.
5. Existing backend fixtures for fixed, relative, minimum-wait claim windows and fixed, percentage, product-specific rewards; only consume their response projection.
6. Safe outbound link validation and existing semantic UI patterns.
7. Toolchain pinning: at review time `frontend/.node-version` is `24.22.0`; `frontend/package.json` and the lockfile specify **pnpm 12.16.1**, but `frontend/README.md` still instructs **10.34.7**. Verify actual configuration, report drift separately; do not migrate the toolchain as part of FE-08.

---

## Objective

After a successful purchase check, the `/results` page must let a visitor understand, **for each returned promotion variant**:

1. **What benefits are recorded:** cashback, an extended warranty, free gifts, or several independent benefits.
2. **How much cashback is recorded** if the backend returned a GBP value; otherwise why the amount is unavailable and whether adding the supported optional purchase price may allow a new calculation on a new check.
3. **When the claim period opens and ends**, using backend-recorded dates and the response's evaluation date, never today's clock or client-side reconstruction.
4. **How claim timing and eligibility differ**, especially for expired, not-yet-open, potentially eligible and ineligible results.
5. **Where to review recorded requirements and official terms**, without implying that the app submits or approves claims.

**Done:** A promotion card exposes the typed benefit(s), value/unavailable explanation, and claim-window timing without requiring the user to expand technical rules or full details. The existing FE-07 explanation, five statuses, filters, Rule Matrix, official links and session/error/empty states remain accurate and functional.

### UX and content intent

Maintain FE-02 visual tokens and the FE-06/07 card design. Recommended hierarchy:

1. Promotion/variant title, recorded eligibility badge and source-verification context.
2. **Benefits**: each independent type, name, optional description and recorded monetary amount if present.
3. **Claim period**: clearly labelled opening/deadline dates, recorded timing state and "as evaluated on [date]" qualifier.
4. **Why this result?**: FE-07 decisive reasons, unknown facts and rule evidence.
5. Official promotion terms, official claim site and optional detailed requirements, using existing accessible controls.

Avoid a second "Claim Window Guide" once the same information is visible; either consolidate it into the shared claim panel or remove redundant content. Benefit values are promotional data, **not** earned money, approved claims or guaranteed payouts. The panel must communicate category/status in text rather than colour or icons alone.

### Benefit presentation matrix

| `benefit_type` | Display requirement | Must not infer |
| --- | --- | --- |
| `cashback`, `cashback_reward_gbp` non-null | Prominent **recorded** "£X cashback" or equivalent and optional name/description | Reward formula, purchase approval, payment or claim acceptance |
| `cashback`, null amount, `purchase_price_required_for_reward` | "Cashback amount not available yet" and backend `reward_unavailable_explanation` if provided (else safe fallback). Offer **Edit purchase details** only if the original optional purchase price was omitted. | £0, "not eligible", automatic recalculation or guaranteed recovery |
| `cashback`, null amount, `reward_not_configured` | "Cashback amount not available for this promotion" plus explanation/official terms. | Implying entry of price would resolve an unconfigured amount |
| `cashback`, null amount, null reason | "Cashback amount not supplied". | Numeric placeholder or fabricated reason |
| `extended_warranty` | Explicit **Extended warranty** type, backend `name`, optional plain-text `description`. | Any cover duration, policy start/end, registration or warranty approval |
| `free_gift` | Explicit **Free gift** type, backend `name`, optional plain-text `description`. | Item SKU, retail value, stock, shipping or entitlement |

Rules:

- Iterate **all** `benefits` in backend order; use `benefit_id` keys. Preserve all promotion variants by `promotion_variant_id`; never merge benefits or calculate a cross-promotion total.
- Include category labels even when benefit names are vague or empty. If `name` is blank, use category as fallback. Omit null descriptions, and render all supplied strings as escaped text.
- Monetary amounts arrive as decimal **strings**, not numbers. Keep the existing string-based `gbp` helper or extend it without `Number`, `parseFloat` or JS floating-point arithmetic. Respect the backend's recorded precision rather than silently rounding; do not invent a consistent pennies contract without verifying backend formatting.
- Do not show `reward_unavailable_reason` as raw snake_case or treat unavailable amounts as zero.
- A missing value does not determine the separate eligibility `classification`.
- If the benefit array is empty, show **No benefit details supplied**; do not invent fallback cashback or gift.

### Claim-period presentation matrix

Source fields: `promotion.eligibility.claim_window_status`, optional `promotion.claim_window.{status,opens_on,deadline_on}`, and parent `response.evaluation_date`.

| Reported timing | UI copy and behaviour |
| --- | --- |
| `open` | **Claim period was open when checked**, plus recorded dates if present. Not "Open now" or "Claim now". |
| `not_yet_open` | **Claim period had not opened when checked**, plus opening/deadline dates if present. No live countdown. |
| `expired` | **Claim period had ended when checked**, with recorded deadline if present; card remains visible. |
| `null`/unspecified | **Claim timing not supplied**, with actual dates only if present; no inferred status. |
| `claim_window === null` | **Opening and deadline dates not supplied**; no synthetic dates. |

- Use the explicit labels **Claim period opens** and **Claim deadline**, `<time dateTime="YYYY-MM-DD">`, and existing `calendarDate`. These are **calendar dates**; do not convert them through midnight UTC or browser timezone.
- The backend evaluates fixed/relative/minimum-wait windows with **inclusive opening and deadline days**. The UI must not derive them from the purchase date or recalculate eligibility on boundary days.
- Show **As evaluated on [response.evaluation_date]** and avoid wording about current claimability; no `Date.now()`, timers, "expires in N days", "today" or source-verification-as-purchase-verification claims.
- `eligibility.claim_window_status` is the recorded timing indicator. `claim_window.status` is supporting projected data and must not silently override it. If fields conflict, do not invent a corrected status; report the inconsistent fixture/response for backend follow-up.
- Claim timing is distinct from `promotion.promotion_status` and from `eligibility.classification`. For example, a `NOT_ELIGIBLE` result may still have an `open` claim window; do not suggest this makes the purchase claimable.
- Keep claim dates accessible for expired, upcoming, ineligible and potentially eligible results, not just positive cards.

---

## Architecture and invariants

1. **Backend authority:** `calculate_reward` owns monetary computation and `evaluate_fixed_claim_window` / `evaluate_relative_claim_window` own inclusive claim timing. The frontend renders their projection only.
2. **Canonical typed source:** consume the existing Zod-validated `Promotion`, parent `evaluation_date`, and submitted purchase data; no alternative API types or parallel status rules.
3. **Pure display mapping:** optional small helpers `presentBenefit` and `presentClaimPeriod` return text and fields, not new eligibility status or calculated money/dates.
4. **FE-07 parity:** preserve `explainPromotion`'s classification/reason precedence, and centralise claim-date presentation used alongside `EligibilityExplanation`; no duplicated hard-coded date algorithms.
5. **Session integrity:** continue to render only the existing in-memory `{submittedPurchase,response}` snapshot. No network calls, local/session storage or URL payloads on results render.
6. **Per-variant identity:** keys/labels by `promotion_variant_id` and `benefit_id`, never dedupe on shared `promotion_id`.
7. **Orthogonal concerns:** a reward value, absent reward, claim window or requirement cannot change the reported backend classification.
8. **Safe content:** text escaping and existing validated URLs; no remote HTML/Markdown execution or `dangerouslySetInnerHTML`.
9. **Accessibility:** semantic dates/lists, visible categories, labelled disclosure state, keyboard operability, no clipping at 320px or 200% text zoom.
10. **Minimal surface:** no new state library, clock library, endpoint, global store or backend dependency.

### Illustrative pure presenter (not a wire contract)

```ts
type BenefitDisplay = {
  key: string; // benefit_id
  category: 'Cashback' | 'Extended warranty' | 'Free gift';
  title: string;
  amountLabel: string | null;
  description: string | null;
  unavailableExplanation: string | null;
  canRecheckWithPurchasePrice: boolean;
};

type ClaimPeriodDisplay = {
  timingLabel: string;
  evaluatedOn: string;
  opensOn: string | null; // validated YYYY-MM-DD or null
  deadlineOn: string | null;
};
```

Only set `canRecheckWithPurchasePrice` when the backend says purchase price is required **and** the submitted optional price was absent. If the backend still reports it missing after a supplied price, faithfully show the explanation and report inconsistent data rather than promising a fix.

---

## API and contract changes

**None.** FE-08 consumes the existing successful check snapshot. Do not modify REST/MCP endpoints, HTTP status/errors, Next proxy, OpenAPI or Zod fields just for presentation.

### Existing wire fields to consume

| Field | Purpose |
| --- | --- |
| `response.outcome`, `evaluation_date` | Resolved promotions only; fixed historical evaluation anchor |
| `promotions[].promotion_id`, `promotion_variant_id` | Keep per-variant identity and stable order |
| `promotions[].benefits[].benefit_id`, `benefit_type`, `name`, `description` | Typed benefit presentation |
| `promotions[].benefits[].cashback_reward_gbp` | Nullable, backend-calculated decimal-string GBP |
| `promotions[].benefits[].reward_unavailable_reason`, `reward_unavailable_explanation` | Nullable reason/description of missing cashback value |
| `promotions[].eligibility.classification` | Authority for FE-07 eligibility badge/explanations |
| `promotions[].eligibility.claim_window_status` | Nullable evaluated claim status |
| `promotions[].claim_window` | Nullable `{status,opens_on,deadline_on}`; no calculated dates |
| `promotions[].requirements[]` | Existing read-only claim requirements, not completion data |
| `promotions[].provenance.official_source_url`, `claim_url` | Existing official external links only |
| `promotions[].last_verified_at` | Recorded primary-source verification, not purchase verification |

**Not in the contract:** warranty duration/coverage, gift value/SKU, cashback percentage/reward rule, claim confirmation, payout status. Do not manufacture these from `name` or `description`.

---

## Domain and application behaviour

### Successful result flow

1. User explicitly submits supported purchase fields via FE-05. The response is validated once, handed off in memory and navigates to `/results`.
2. Cards render every recorded benefit, unavailable-value explanation, and claim-period dates/status for the **exact returned variant**, independent of eligibility status.
3. The FE-07 “Why this result?” section continues to show decisive/unknown/passed rules without duplicating an alternative claim panel or competing deadline copy.
4. The existing **Edit purchase details** link returns to `/check`. Adding a missing purchase price invalidates the old snapshot and requires an explicit new check; no results-page retry or auto-calculation.
5. Full promotion details retain requirements, official sources, verification metadata and external claim link. All labels must avoid promising claim acceptance.
6. Keep Rule Matrix focused on recorded rule evidence, but make per-variant rewards/claim timing available consistently (a compact summary in each row or a clear accessible route back to Cards); it must not show contradictory claim dates.
7. Filters, Cards/Matrix switch and disclosures do not issue additional API requests or change the underlying snapshot.

### Status × reward × claim guidance

- `ELIGIBLE` + `open`: record benefit and claim dates, link to official terms/claim site; this is **not** an approved or paid claim.
- `ELIGIBLE` + unknown timing: preserve positive eligibility classification while stating that claim timing is unspecified; **not** "open now".
- `POTENTIALLY_ELIGIBLE`: show recorded benefit and unknown rule facts; missing cashback amount alone is not decisive.
- `CLAIM_NOT_YET_OPEN`: show recorded opening date if supplied; never present a live "claim now" CTA.
- `EXPIRED`: show recorded deadline and benefits for reference; do not hide the promotion.
- `NOT_ELIGIBLE`: show advertised benefit in context but put failed-condition explanation first for actionability; no suggestion it is claimable.
- Any status with `claim_window === null`: show timing separately (if supplied), and state dates were not provided.
- Any status with no benefits: honest empty benefits message.

### Important edge cases

- Multiple benefits with same type and multiple variants with one `promotion_id`: show all in backend order; no double counting/aggregation.
- Null cashback reasons: separate price-required, unconfigured and unspecified explanations; never substitute £0.
- A submitted price plus a backend price-required reason: show received reason without automatic retry or guessing.
- Claim window with missing dates or inconsistent statuses: display only validated supplied facts; record the inconsistency as follow-up, never client-side reclassify.
- An old `evaluation_date` must not be turned into a current availability claim.
- Unknown/unresolved brand/product/retailer, zero published matches, empty filtered results, missing same-tab snapshot, transport failure and malformed API response: preserve existing FE-05/06 states.

### Eligibility-specific rules

**Presentation only.** The frontend must not recalculate `classification` from benefits, promotion lifecycle, rules or date comparison. FE-07 reason precedence stays untouched.

### Ingestion/publication rules

**N/A.** Use only the already validated response from published promotion data.

---

## Persistence, transactions, and migrations

**None.** No database, session/local storage, cookies, URL/query data, saved results or migrations.

---

## External services and network access

**No new external calls.** Retain official promotion source/claim links and existing validated URL scheme, safe attributes and accessible labels. No page fetching, polling or claim submission.

---

## Security and privacy

- Treat all backend descriptions, titles, explanations and source titles as untrusted text; React escapes them. Do not render third-party markup or parse claim instructions as executable content.
- Do not disclose raw product/manufacturer/retailer identity UUIDs or copy purchase details into URLs, storage or analytics.
- Keep existing validated official URLs and `target="_blank" rel="noopener noreferrer"`, with the new-tab accessibility cue.
- No client credentials, secrets, PII logs or new security boundary.
- No claims of reward approval, paid cashback, purchase verification, gift fulfilment or warranty registration without contract evidence.

---

## Configuration and deployment

### Environment variables

**None.** No new or changed environment variables.

### Runtime/deployment changes

**None.** Continue existing Next.js/React/Tailwind and GitHub Actions pipeline. Handle pnpm documentation drift separately rather than changing CI/toolchain as part of this feature.

---

## Observability and operations

- No new telemetry or logging of full purchase/check payloads.
- Existing API failures stay in the purchase-check form; `/results` is a read-only snapshot view.
- Test that benefit/date/disclosure/filter/view interactions create **zero** additional `/api/` requests.
- If verified wire inconsistencies exist, report the relevant field values, reproduction and follow-up instead of silently repairing domain decisions in the browser.

---

## Failure, consistency, and recovery

- **No snapshot, reload, direct URL or new tab:** existing “No results in this tab” state, no fabricated rewards.
- **Unresolved identity or no published matches:** retain existing correction/empty state.
- **Null amounts/dates:** explicit “not supplied” copy, not £0, "open", or "ineligible".
- **Malformed response:** existing schema/error boundary handles it; do not bypass validation for a partially fabricated results page.
- **Edit/recheck:** old snapshot invalidates on change; a replacement appears only after explicit successful check.
- **Stale evaluation timestamp:** qualify status with the historical evaluation date rather than a live availability claim.
- **Contradictory backend fields:** do not recompute status or reward; document risk and regression fixture.

---

## Acceptance criteria

### Behaviour

- [ ] `/results` renders every benefit for each variant, with distinct Cashback / Extended warranty / Free gift categories, recorded names and optional descriptions.
- [ ] Non-null cashback shows the exact backend GBP value; null cashback has accurate distinct explanations for price required, reward not configured and no reason, never £0 by default.
- [ ] Warranty and gift display only actual returned details, never fabricated durations/values/stock.
- [ ] Opening and deadline dates show with labels, semantic `<time>`, clear evaluation-date context and no duplicative claim guide/details.
- [ ] All claim timing states `open`, `not_yet_open`, `expired`, null, and null window dates are represented honestly.
- [ ] Classification and FE-07 rule explanations remain authoritative and independent of benefit value and claim-window state.
- [ ] Eligible, potentially eligible, upcoming, expired and ineligible variants retain all their recorded rewards and dates.
- [ ] Existing claim requirements, official source and claim links remain usable with safe, accurate copy; no fake claim action.
- [ ] All variants and benefit entries remain independently visible; no aggregation, deduplication or reordered results.
- [ ] Existing filters, Cards/Rule Matrix, disclosure, edit, direct-entry, no-match, unresolved and failed-check behaviours remain intact.

### Data and consistency

- [ ] No client-side reward/eligibility/claim calculation, live clock, countdown or date derivation.
- [ ] GBP decimal strings are formatted without binary-floating-point conversion or precision loss.
- [ ] Display fields come only from the validated response; nulls do not become false/zero.
- [ ] No API, MCP, database, migration, persistence or configuration changes.

### Security

- [ ] All untrusted text is escaped; no unsafe HTML or link handling.
- [ ] External links retain accessible text and secure new-tab attributes.
- [ ] No purchase details leak via URL, storage or telemetry.

### Accessibility and UX

- [ ] Benefit type and timing state are conveyed in text, not colour alone.
- [ ] Correct headings, benefit list semantics, `<time>` values, visible focus, keyboard disclosures and ARIA expansion state.
- [ ] No horizontal overflow or content clipping at 320/360/375/768/1024/1280px, including long descriptions, 200% text zoom and reduced-motion.
- [ ] Axe accessibility regression tests pass in Cards, expanded details and Rule Matrix.
- [ ] A user can understand benefits and claim dates without opening raw technical rule details.

### Code quality

- [ ] One canonical claim-date presenter, no duplicated backend business logic.
- [ ] Pure mappers/component boundaries are meaningfully tested, no unrelated dependency/refactor.
- [ ] Format, lint, typecheck, tests, build, smoke and browser verification pass, or exact blockers are recorded.
- [ ] Do not claim queued or hung CI is green.

---

## Tests to add or update

### Unit tests

Add to `frontend/src/features/eligibility/results/{presentation.test.ts,rewards.test.ts}` (or nearest presenter test):

- Table-driven typed benefits: three types, multiple benefits, blank names, optional descriptions, empty array, long strings.
- Exact GBP decimal-string rendering: `10`, `10.00`, large amounts and retained decimal precision; no `Number`/`parseFloat` rounding.
- Null cashback with `purchase_price_required_for_reward`, `reward_not_configured`, no reason, present/absent purchase price, and no false £0.
- Claim timing `open` / `not_yet_open` / `expired` / null with supplied or null window dates; backend-projected inclusive boundary cases for fixed, relative and minimum-wait windows.
- No timezone or wall-clock dependence for calendar dates and evaluation context.
- Variant and benefit identity/order, no aggregation or invented fallback fields.

### Component tests

Extend `frontend/src/features/eligibility/results/ResultsOverview.test.tsx`, `explanations.test.ts` and any new focused component tests:

- All three benefit types render visibly and independently, with recorded descriptions and truthful unknown values.
- Opening/deadline dates and historical evaluation context are visible; duplicate claim panels removed/consolidated.
- Status/reward separation, e.g. `NOT_ELIGIBLE` variant with £150 recorded cashback and `open` claim window.
- Price-required reward with omitted vs supplied price and correct existing edit link.
- Multiple variants sharing `promotion_id`, all five classifications, filters and Cards/Rule Matrix consistency.
- Null/empty benefits, dates, rules, requirements; unresolved identity and no-matches unchanged.
- Untrusted hostile-looking text safely escaped and wrapped; links remain safe; disclosures keyboard accessible.
- Prefer behavioural assertions to snapshots or testing implementation-private state.

### Browser / end-to-end tests

Extend `frontend/e2e/purchase-results.e2e.ts` and deterministic `support-upstream.mjs` when appropriate:

- Explicit `/check` → `/results` with cashback fixed amount, price-required missing amount, warranty and gift, backed by schema-valid fixture responses.
- Open, upcoming, expired and unspecified claim periods, recorded dates and conditional action wording.
- Cards/Matrix/filter/disclosure switches issue no extra check request; edit/recheck explicitly replaces snapshot.
- External links, keyboard interaction, 320px responsive reflow, 200% zoom, reduced motion and axe checks.
- No live manufacturers, live claim site navigation, sleep-based timing or client clock dependence.

### PostgreSQL integration tests

**N/A.** No persistence.

### API/application tests

**No new backend API tests.** Existing frontend response-contract tests continue to pass. Update fixtures only if supported by actual backend fields.

### MCP contract tests

**N/A.** No MCP changes.

### External-boundary tests

**No new network code.** Preserve existing safe-link and one-request-per-check browser regression coverage.

---

## Verification commands

Use the **actual current** versions from `frontend/package.json`, `.node-version` and `pnpm-lock.yaml`. At specification review: Node `24.22.0`, pnpm `12.16.1`; `frontend/README.md` contains stale pnpm `10.34.7` guidance, which must be reported rather than copied blindly.

```bash
cd frontend
node --version
pnpm --version
pnpm install --frozen-lockfile

# Focused unit/component regression; include rewards.test.ts if created.
pnpm exec jest --runInBand --runTestsByPath \
  src/features/eligibility/results/presentation.test.ts \
  src/features/eligibility/results/explanations.test.ts \
  src/features/eligibility/results/ResultsOverview.test.tsx

pnpm format:check
pnpm lint
pnpm typecheck
pnpm test
pnpm build
pnpm smoke

pnpm exec playwright test e2e/purchase-results.e2e.ts
pnpm test:e2e
```

For any check not run, report the exact command, failure/blocker, verified alternative and remaining risk. Do not modify assertions only to silence real regressions. An unavailable/queued CI job is not a pass.

---

## Completion report

### Changed

List changed reward/date UI files, pure presenters, components and user-visible copy.

### Database and migrations

None.

### API/MCP contracts

None, unless real separately verified contract drift demanded a justified correction.

### Tests and verification

List tests added/updated and the commands **actually run** with outcomes; include mobile and a11y coverage and no-extra-request evidence.

### External configuration

None.

### Deviations

Explain any out-of-scope changes, or None.

### Remaining risks or follow-up

Record backend data inconsistencies, unsupported warranty/gift detail, source freshness, toolchain/README version mismatch and pending CI if relevant; otherwise None.
