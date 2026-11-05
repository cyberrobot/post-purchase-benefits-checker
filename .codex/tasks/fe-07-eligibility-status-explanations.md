# FE-07 — Eligibility Status & Explanations

## Repository state

**Expected branch:**  
`fe-07-eligibility-status-explanations` (create from the current `main` after checking the existing working tree and open PRs)

**Base branch:**  
`main`

**Dependencies:**

- FE-01/02/03/04: Next.js 16 App Router, React 19, TypeScript, Tailwind v4, shared UI components, purchase-input form and typed API client.
- FE-05 / PR #39: explicit purchase check, validation, mutation lifecycle and error handling.
- FE-06: **already present on `main`** as `/results`, `ResultsOverview`, status filters, rule matrix, session-only check-result handoff and browser tests. FE-07 extends this working implementation; it must not create a second results page.
- Backend eligibility classification and explainability contracts: `backend/app/domain/{eligibility_result,eligibility_rules}.py`, `backend/app/application/purchase_check.py` and `backend/app/api/schemas/eligibility.py`.
- Shared frontend response validation: `frontend/src/lib/api/eligibility.contract.ts`.

### Read first

- `.codex/tasks/TEMPLATE.md`, repository `AGENTS.md`, any applicable scoped `AGENTS.md` that exists at implementation time, and `frontend/README.md`.
- `.codex/tasks/{fe-03-api-client-configuration,fe-04-purchase-input-form,fe-05-purchase-check-integration,fe-06-eligibility-results-overview}.md`.
- `frontend/src/app/results/{page,page.test}.tsx` and `frontend/src/features/eligibility/results/{ResultsOverview,ResultsOverview.test,presentation,presentation.test}.t[sx]`.
- `frontend/src/features/eligibility/session/PurchaseCheckSession.tsx` and `frontend/src/features/eligibility/components/{PurchaseInputForm,purchaseForm}.t[sx]`.
- `frontend/src/lib/api/{eligibility.contract,promotion.fixture,fixtures}.ts`; `frontend/e2e/{purchase-results.e2e.ts,support-upstream.mjs,support-layout.ts}`.
- `frontend/package.json`, `frontend/playwright.config.ts`, shared UI components and `frontend/src/app/globals.css`.
- Backend `RuleReasonCode`, `EligibilityReasonCode`, `RuleStatus`, `EligibilityClassification`, `classify_eligibility`, `_explanations`, and the HTTP response schema **for interpretation only**, not backend changes.

### Primary change area

Frontend `/results` presentation: trustworthy, prominent *per-promotion-variant* explanations of **why** the backend returned one of its five classification values, with a distinction between failed conditions, insufficient information, satisfied checks and claim-submission requirements.

### Canonical implementation examples

- `ResultsOverview.tsx` already renders the purchase summary, cards, five-status filters, a Cards/Rule Matrix switch, rule-evaluation details, claim-window information, provenance and safe official links.
- `presentation.ts` already defines the five status labels, descriptions, accents, counts, selectors and date/money formatting. Extend its types or add a small pure explanation presenter rather than duplicate mappings in JSX.
- `PurchaseCheckSession` already carries the exact submitted purchase and validated response as a transient immutable snapshot. **Do not replace or persist it.**
- `eligibility.contract.ts` is the canonical Zod representation of the backend response. It contains five exact classifications; `eligibility.reasons`, `eligibility.rule_evaluations` and nullable `claim_window_status`; nullable `claim_window`; and separate `requirements` and `explanation` arrays.
- Backend `classify_eligibility` gives **failed rules precedence over unknown rules, and unknown rules precedence over claim timing**. It returns *decision reasons* plus the complete set of rule evaluations.
- Existing Jest/RTL and Playwright results suites already verify navigation, variants, filtering, responsive layout, accessibility and single-submit behaviour. Extend these rather than replacing them with snapshots.

### Relevant symbols

`ResultsPage`, `ResultsOverview`, `PromotionCard`, `RuleDetails`, `RuleMatrix`, `criterionLabel`, `statuses`, `counts`, `selectPromotions`, `Promotion`, `Classification`, `PurchaseCheckSessionProvider`, `usePurchaseCheckSession`, `CheckPurchaseResponse`, `promotionSchema`, `checkPurchaseResponseSchema`, `EligibilityClassification`, `EligibilityReasonCode`, `RuleReasonCode`, `RuleStatus`, `classify_eligibility`, `POST /api/eligibility/check` and `POST /api/v1/eligibility/check`.

### Expected change surface

```text
.codex/tasks/fe-07-eligibility-status-explanations.md  # this task
frontend/src/features/eligibility/results/presentation.ts
frontend/src/features/eligibility/results/presentation.test.ts
frontend/src/features/eligibility/results/ResultsOverview.tsx
frontend/src/features/eligibility/results/ResultsOverview.test.tsx
frontend/src/features/eligibility/results/explanations.ts        # optional focused pure mapper
frontend/src/features/eligibility/results/explanations.test.ts   # if extracted
frontend/src/features/eligibility/results/EligibilityExplanation.tsx  # optional focused UI
frontend/e2e/purchase-results.e2e.ts
frontend/e2e/support-upstream.mjs                     # only if valid status fixtures need extending
frontend/src/lib/api/promotion.fixture.ts             # only for deterministic fixtures
frontend/README.md                                    # concise user-facing explanation semantics
```

Paths are guidance, not an invitation to rewrite unrelated UI. `ResultsOverview.tsx` is already a large component; a small, separately tested explanation mapper/component is reasonable if it improves readability. Avoid a general-purpose rules engine.

### Excluded areas

- No changes to backend application/domain decisions, rule precedence, published promotion data, REST/MCP schemas, database, migrations, seeding, source retrieval or AI extraction.
- No new API request, client-side eligibility evaluation, background refresh, current-date inference, reward calculation or recheck on `/results`.
- No authentication, saved results, cookies, local/session storage, browser-history payload, query-string purchase details or deep linking.
- No new form fields for channel, condition or country. The current form accepts brand, model, retailer, purchase date and optional GBP price only.
- No promotion ranking, deduplication of distinct variants, aggregate purchase eligibility judgement, claim approval/payment inference or claim submission workflow.
- No redesign of the purchase-check form, results navigation/session lifecycle, benefit rendering, safe external links, filters or surrounding site layout except where explanation clarity/accessibility genuinely requires a small adjustment.
- Do not present claim-submission requirements (`receipt`, `serial_number`, `registration` etc.) as failed eligibility conditions; the backend supplies **requirements**, not their completion statuses.

### Unknowns Codex must verify

1. Current `main` HEAD, pending FE-06 follow-up PRs and whether any newer explanation component exists.
2. Whether there is a new frontend-scoped `AGENTS.md` and whether any frontend package versions or scripts changed; at review time `frontend/package.json` and the introductory `frontend/README.md` disagree about the pinned pnpm version, so **verify the manifest and lockfile rather than copying the README version**. Do not fix toolchain drift in FE-07 unless it blocks verification, and report it separately.
3. The complete current `RuleReasonCode` / `EligibilityReasonCode` enum list and any newly introduced wire fields or invariants.
4. Whether backend explanation strings are always present and whether `claim_window` can be null while `claim_window_status` is non-null (the typed contract allows this).
5. Which existing `ResultsOverview` tests rely on exact labels, heading counts or raw `words(reason_code)` output, so these can be meaningfully updated rather than suppressed.
6. Existing colour tokens, keyboard patterns, real status fixtures and whether the Rule Matrix should use the same readable reason labels as the cards.

---

## Objective

After a purchase check succeeds and navigates to `/results`, a visitor can immediately understand, **for each returned promotion variant**:

1. The exact **backend-reported** eligibility status and its practical meaning.
2. **Why that status was returned**, using stable reason codes and the supplied rule evaluations rather than frontend guesses.
3. Which recorded eligibility **conditions failed**, which facts **could not be assessed**, and which checks **passed**, clearly separated.
4. Whether claim-window timing is open, not yet open, expired or unspecified **at `evaluation_date`**, including actual recorded dates when supplied.
5. What action is reasonable next: review the terms, edit and recheck a supported missing input, or wait for a recorded future opening date. Never imply that submitting evidence fixes a known failed rule or guarantees a claim.

**Done:** All five classifications are intelligible without opening raw debug details. A decisive reason is visible within each card, and fuller recorded evidence remains accessible; the same truth is expressed in Cards and Rule Matrix views. Multiple variants retain their own independent statuses and reasons. No new check request, persistence or backend decision logic is added.

### UX and content intent

Use the existing FE-02 visual system and FE-06 card design. Within each promotion card, maintain this information hierarchy:

1. Promotion title/variant, **status badge with text** and recorded benefit(s).
2. A brief, visible **“Why this result?”** statement and the decisive reason(s), written in plain British English.
3. Clearly labelled grouped evidence as applicable: **Conditions not met**, **Information we couldn't assess**, **Recorded checks passed**, and **Claim period**. Put actionable or decisive information first; leave long satisfied-rule inventories collapsible.
4. Supplemental recorded explanation text, official source/provenance and claim requirements inside the already functional details interface.

Do not force a new wizard, icons-only status, modal, opaque acronym, or a second competing “full details” disclosure. A short status heading must not be the only reason shown. A person should be able to understand *what was checked and what remains unknown* without interpreting `purchase_date_before_start`.

### Five status presentations

| Backend classification | Public status label | Primary explanation and safe guidance |
| --- | --- | --- |
| `ELIGIBLE` | **Eligible** | “This purchase meets the recorded eligibility rules.” If claim window is `open`, say the recorded claim period is open. “This is not an approved or paid claim.” Encourage checking official terms/requirements. |
| `POTENTIALLY_ELIGIBLE` | **Potentially eligible** | Explain **which** rule facts are `unknown` and/or that claim timing is unspecified. Do not automatically say “provide more purchase details”: all rules may be satisfied but `claim_window_status` may be `null`. |
| `NOT_ELIGIBLE` | **Not eligible** | Show **every decisive `not_satisfied` rule** in stable order. Say “Does not meet one or more recorded eligibility conditions.” If other rules are unknown, keep them in a separate non-decisive group; no suggestion that completing those alone will reverse a known failure. |
| `CLAIM_NOT_YET_OPEN` | **Claim not yet open** | “The recorded eligibility rules are met, but the claim period has not opened at the evaluation date.” Show the backend opening date **only if** present; do not use a countdown. |
| `EXPIRED` | **Claim period expired** | “The recorded claim deadline has passed at the evaluation date.” Show the actual recorded deadline if supplied. Do not say the product was ineligible or that the promotion lifecycle record is archived. |

`POTENTIALLY_ELIGIBLE` is not a system error. `EXPIRED` refers to **claim-window evaluation**, not a direct mapping from `promotion_status === 'expired'`. Neither a missing claim window nor missing data constitutes a definite negative rule outcome.

---

## Architecture and invariants

1. **Backend remains authoritative.** Render `promotion.eligibility.classification` exactly as reported. The frontend does not rerun `classify_eligibility`, recompute statuses from rule evaluations, inspect promotion lifecycle to override a status, or calculate claim dates from the current time.
2. **One canonical typed input.** A pure display function accepts the already Zod-validated `Promotion` and optionally the parent `evaluation_date`/submitted request for contextual guidance. It produces strings and grouped rule-display items, not a new eligibility decision.
3. **Decision reason vs evidence.** `eligibility.reasons` reports the backend's *decisive explanation*; `rule_evaluations` contains **all** recorded checks, including checks that did not determine classification. Preserve this distinction when prioritising visible content.
4. **Precedence belongs to backend.** Failed condition(s) take priority over unknowns; unknowns take priority over claim timing; the UI must not reorder causal significance. If fixture data are inconsistent, continue showing the reported classification and accurately labelled received evidence rather than silently “correcting” the decision client-side.
5. **No accidental deduplication.** Preserve backend order for reasons and rule evaluations, including repeated rule kinds if valid, and preserve all promotion variants by `promotion_variant_id`. Never dedupe on `promotion_id` or reason string alone.
6. **Claim timing is orthogonal to rule evidence.** `claim_window_status` and optional `claim_window` are reported values. A null claim status means “not supplied”, **not** “open”, “expired”, or “failed”. A present future opening date is a *claim* opening date, not the purchase eligibility period start.
7. **Requirements are not unmet conditions.** Requirements list what may be needed to make a claim. Without a recorded requirement-completion result, do not mark them with failure icons or assert the user lacks a receipt/serial number.
8. **Snapshot integrity.** Continue reading only the existing immutable same-tab `{submittedPurchase,response}` snapshot. Editing a field invalidates it; reload/direct entry shows the existing empty state. No side effects on result render.
9. **Safe copy.** All backend prose, promotional names, descriptions and source titles remain escaped text; no `dangerouslySetInnerHTML`, remote HTML/Markdown rendering or arbitrary URL transformations.
10. **British-English presentation.** Plain, non-accusatory language; avoid guaranteed cashback, approval or “verified purchase” claims. `evaluation_date`, purchase date, source verification and claim deadlines remain separate facts.

### Suggested small presentation boundary

Define a pure helper along these lines; naming can follow the repository style:

```ts
export type ExplanationGroup = {
  heading: string;
  items: Array<{ key: string; text: string }>;
};

export type EligibilityExplanationView = {
  statusLabel: string;
  summary: string;
  decisive: ExplanationGroup[];
  additionalEvidence: ExplanationGroup[];
  claimTiming: string | null;
  nextStep: string | null;
};

export function explainPromotion(
  promotion: Promotion,
  context: { evaluationDate: string; submittedPurchase: PurchaseRequest },
): EligibilityExplanationView;
```

This is an **illustrative UI-only interface**, not a backend or network contract. Make the helper deterministic and unit-testable. Do not store another copy of the raw result in derived state. Treat backend `promotion.explanation` as supplemental recorded explanation, while stable codes control the primary structured “why” presentation.

---

## API and contract changes

**None.** FE-07 is a consumer of the existing `CheckPurchaseResponse` from the successful FE-05 mutation; it changes no request/response fields, HTTP status codes, Next proxy, auth contract or MCP tool.

### Existing wire fields to consume

| Path | Meaning / UI use |
| --- | --- |
| `response.outcome` | `resolved` vs `unresolved_identity`; latter is **not** one of five statuses. |
| `response.evaluation_date` | Authoritative evaluation calendar date for claim-timing language. |
| `response.promotions[]` | One display result **per returned promotion variant**. |
| `promotion.eligibility.classification` | Exact backend five-state status, never frontend-derived. |
| `promotion.eligibility.reasons[]` | Ordered *decision reason* code plus nullable `rule_kind`; use to explain **why**. |
| `promotion.eligibility.rule_evaluations[]` | Ordered `(kind, status, reason_code)` for passed, failed or unknown evidence. |
| `promotion.eligibility.claim_window_status` | `open`, `not_yet_open`, `expired` or `null`. |
| `promotion.claim_window` | Nullable `{status,opens_on,deadline_on}`; show dates only if present. |
| `promotion.explanation[]` | Optional backend prose, displayed as safely escaped supplementary text, not a substitute for mapped reasons. |
| `promotion.requirements[]` | Claim-submission requirements, not eligibility failures. |
| `promotion.provenance` / `sources` | Existing official source and last-verification references; keep current link validation and disclosure. |

The existing Zod enums are exhaustive. If backend introduces new reason values, do **not** silently accept unvalidated wire data or coerce them to another eligibility outcome. Keep `eligibility.contract.ts` unchanged in FE-07 unless implementation uncovers an actual backend/frontend drift, in which case document the drift and add matching contract tests before any necessary minimal fix.

### Required display mappings

Create an explicit, exhaustively covered mapping for the existing codes. Representative rule messages:

| Machine-readable code | Plain-language copy |
| --- | --- |
| `retailer_mismatch` | “The retailer does not match this promotion's recorded retailer conditions.” |
| `product_mismatch` | “The product model does not match this promotion's recorded product conditions.” |
| `manufacturer_mismatch` | “The manufacturer does not match this promotion's recorded manufacturer conditions.” |
| `purchase_date_before_start` | “The purchase date is before the recorded qualifying purchase period.” |
| `purchase_date_after_end` | “The purchase date is after the recorded qualifying purchase period.” |
| `purchase_price_below_minimum` | “The purchase price is below the recorded minimum.” |
| `purchase_price_above_maximum` | “The purchase price is above the recorded maximum.” |
| `purchase_channel_mismatch`, `condition_mismatch`, `country_mismatch` | Refer to the corresponding recorded restriction, without inventing required permitted values. |
| `purchase_price_unknown` | “The purchase price could not be assessed against this promotion's rules.” |
| `purchase_channel_unknown`, `condition_unknown`, `country_unknown` | Explicitly identify the unevaluated fact, without offering a field that does not exist. |
| `*_match`, `purchase_date_match`, `purchase_price_match` | Concise positive recorded-check descriptions for an optional “Checks passed” section. |
| `all_configured_rules_satisfied` | “All recorded eligibility conditions were satisfied.” |
| `claim_window_open` | “The recorded claim period is open at the evaluation date.” |
| `claim_window_not_yet_open` | “The claim period has not opened at the evaluation date.” |
| `claim_window_expired` | “The recorded claim period has ended at the evaluation date.” |
| `claim_window_unspecified` | “The claim period could not be determined from the recorded information.” |

Implement and test **every enum member actually exported by the repository**, not just these examples. Do not expose underscore-separated codes as the primary copy. Exact phrasing may be adjusted for consistency with FE-02 style, provided it does not introduce unsupported claims. Avoid labels like “Retailer not authorised” when only a mismatch is known.

---

## Domain and application behaviour

### Results with multiple variants

Render each variant's own status, decisive reasons, evidence and claim period. `ELIGIBLE` on variant A does not make variant B eligible. Maintain counts and filters for all five classifications, preserve FE-06 backend order, and do not merge two variants of the same promotion.

### Decisive conditions and secondary evidence

- For `NOT_ELIGIBLE`, display **all** `not_satisfied` decision reasons in original order, under **Conditions not met**. If an `unknown` evaluation also exists, show it separately as **Information we couldn't assess** and label it **not the reason for this decision** when needed. Do not say “add missing details to qualify” while a known failure remains.
- For `POTENTIALLY_ELIGIBLE`, show unknown rule reason(s) under **Information we couldn't assess**, in the server-provided order. If the only uncertainty is `claim_window_unspecified`, explain missing claim timing rather than incorrectly alleging a missing price, retailer or receipt.
- For `ELIGIBLE`, use the `all_configured_rules_satisfied` / `claim_window_open` reasons when present; optionally collapse the passed-rule checklist. Do not mark any claim requirement “complete”.
- For `CLAIM_NOT_YET_OPEN` and `EXPIRED`, show the relevant claim-timing reason as decisive. The presence of a future/expired claim window does not make a purchase rule “failed”.
- If `eligibility.reasons` is empty despite a valid parsed payload, show a neutral “Detailed reasons were not supplied” explanation and the **actual** available rule evaluations. Never synthesize definitive conditions or a new status.
- If `rule_evaluations` is empty, do not call it a failed evaluation; say “No individual rule checks were supplied.” If the backend says `all_configured_rules_satisfied`, explain that summary without pretending to have per-rule evidence.
- Preserve multiple failures and multiple unknowns; render each independently and readably. Do not stop at the first reason or dedupe by rule kind.
- A `satisfied` rule is a passed **recorded check**, not verification of the physical purchase or receipt.

### Dates, claim windows and unspecified data

- Always explain claim timing **as evaluated on the response's `evaluation_date`**, not the visitor's current date or browser timezone.
- Display `opens_on` and `deadline_on` if, and only if, `claim_window` is supplied; use the existing calendar-only `en-GB` formatter, not `new Date('YYYY-MM-DD')` in local time.
- When `claim_window` is null, a status-specific sentence may still be shown from the backend classification/reason; **never fabricate a date**.
- If `claim_window_status` is null, say “Claim period not supplied”/“Claim timing could not be determined”; do not treat that as a failure or assume it is open.
- `promotion_status === 'expired'` must not change claim-period wording. A historical published promotion can still be checked against a previous purchase.
- Do not calculate days until open/deadline or present “still open today” without a fresh authoritative check.

### Next-step guidance (no invented functionality)

- Known input correction: offer the **existing** “Edit purchase details” link, retaining prior draft values and requiring a new deliberate submission.
- If a `purchase_price_unknown` reason is present **and no price was submitted**, explain that the optional purchase price can be added on `/check` and the purchase checked again. If a price was supplied, do not imply it was omitted.
- For unknown `purchase_channel`, `condition`, or `country`, the current checker has **no corresponding field**. Tell visitors those facts were not assessed and refer them to the official promotion terms; do not show nonfunctional inputs or suggest the checker can resolve them.
- For a future claim period, show “Claim period starts on [recorded date]” if supplied; do not create reminders or suggest immediate claim submission.
- For a closed claim period, explain the recorded deadline; do not promise extensions or backdated eligibility.
- For eligible results, direct people to the existing official terms/claim site and claim-requirement details, without implying a claim will be accepted.
- If no actionable guidance can be grounded in the fields returned, omit that action rather than inventing one.

### Unresolved identity, zero matches and service failures

Preserve FE-06/FE-05 behaviour **unchanged**:

- `unresolved_identity/not_found` or `ambiguous` displays targeted brand/model/retailer correction, no five-state badge and no leaked candidate UUIDs.
- `resolved` with `promotions: []` remains **no matching published promotions**, not a sixth eligibility classification.
- Transport/contract errors remain on `/check` using the FE-05 error boundary; do not navigate to a results page showing “not eligible” for 429/502/503, timeouts or malformed JSON.
- Direct `/results`, full reload or another tab still has no stored snapshot; no automatic request is made.

### Cards and Rule Matrix parity

Both existing views must communicate the same backend classifications and meaningful reason labels. A user who switches to Rule Matrix can still identify the failed or unknown reason for each variant without deciphering raw enum strings. No extra request or change in filter count may result from switching views. Full supplementary details can remain in cards only, as long as the matrix preserves status and decisive reason visibility and does not contradict the cards.

---

## Persistence, transactions, and migrations

**None.** No database, migration, persistence, cache or server state changes. All display data is derived synchronously from the transient session snapshot. No transaction or reconciliation behaviour is needed.

---

## External services and network access

**No new external dependency or request.** Preserve the one explicit POST to the existing check endpoint on `/` or `/check`; `/results` does not fetch. Existing outbound official-source links remain passive, URL-validated and protected with `rel="noopener noreferrer"`, with no embedded requests or automatic navigation.

---

## Security and privacy

- Do not persist submitted purchase fields, outcome, user details or evidence in URLs, browser storage, cookies, telemetry or new logs.
- Render backend explanation text and promotion names as React text nodes; never inject HTML or trust source content as code.
- Do not display resolved identity/candidate UUIDs as meaningful user-facing names or reveal internal infrastructure errors.
- Continue using validated official URLs from the established contract and safe external-link attributes; no URLs constructed from free-form reason text.
- Avoid “claim approved”, “receipt verified”, “guaranteed cashback”, “authorised retailer” or other unsupported assurances.
- Preserve accessibility for status meaning without relying on colour, animation, punctuation or icon glyph alone.

---

## Configuration and deployment

**None.** No new environment variables, packages, routes, middleware, build targets, Docker images, hosted services, feature flags or authentication configuration.

### Environment variables

None.

### Runtime/deployment changes

None. Follow the actual pinned Node/pnpm information in `frontend/package.json` and lockfile when installing or verifying; record existing README drift separately if encountered.

---

## Observability and operations

No new telemetry infrastructure. Existing error and request-correlation behaviours remain unchanged. The results presentation may use local component state for disclosure/view controls, but must not log raw purchase inputs, explanations or official URLs. Service errors must remain distinct from domain classifications. Accessibility and deterministic browser tests are the operational assurance for FE-07.

---

## Failure, consistency, and recovery

| Scenario | Required behaviour |
| --- | --- |
| Incomplete `reasons` or `rule_evaluations` | Explain missing **detail**, not an invented negative rule; keep the backend classification. |
| `claim_window: null` and unknown or populated `claim_window_status` | Show only authoritative classification/timing; no fabricated dates. |
| A definite failure and one or more unknown checks | Failure remains visibly decisive; unknowns are separate supporting context. |
| Multiple failures / unknowns | All relevant items visible in stable backend order; no accidental deduplication. |
| Misleading/malicious explanation string | Escaped display only; stable typed decision reasons remain primary. |
| Revisit old URL after editing or failed recheck | Existing snapshot invalidation/empty state remains; no stale benefits. |
| Unresolved identity or no-match response | Existing outcome-specific UI remains; no fabricated eligibility badge. |
| Network/contract failure | Existing `/check` safe error and manual retry; do not navigate to `/results`. |
| Variant filter or view switch | No fetch, no data loss, identical independent backend classifications. |
| Unexpected semantic contradiction in a test fixture | Never recompute classification or conceal received rule outcomes; choose neutral wording for unavailable details and report contract inconsistency separately if found in real API data. |

---

## Acceptance criteria

### Behaviour

- [ ] Each promotion variant on `/results` shows its exact backend classification and a **visible human-readable “Why this result?” explanation** without expanding raw details.
- [ ] All five exact statuses are handled: `ELIGIBLE`, `POTENTIALLY_ELIGIBLE`, `NOT_ELIGIBLE`, `CLAIM_NOT_YET_OPEN`, `EXPIRED`.
- [ ] All current rule and classification reason codes have explicit, unit-tested plain-English mappings; default UI does not expose raw enum tokens as the primary explanation.
- [ ] `NOT_ELIGIBLE` shows **all recorded failed conditions**; unrelated unknowns are separate and never presented as the decisive failure.
- [ ] `POTENTIALLY_ELIGIBLE` distinguishes **unknown rule facts** from **unspecified claim timing**, including the case where all recorded rules passed but the claim window is null.
- [ ] `ELIGIBLE` states recorded-rule eligibility is not claim approval or payment.
- [ ] `CLAIM_NOT_YET_OPEN` and `EXPIRED` refer to **claim timing**, not failed purchase-eligibility rules or promotion lifecycle status.
- [ ] Claim opening/deadline dates appear only when the backend supplies them; wording consistently references `evaluation_date` and never browser “now”.
- [ ] Satisfied, failed and unknown rule evaluations can be understood without interpreting codes; backend ordering is preserved.
- [ ] Claim-submission requirements remain separate and are **never marked as unmet eligibility rules** without a specific backend outcome.
- [ ] Contextual next steps are truthful: optional price only when absent, no unsupported fields, no guaranteed claim outcome.
- [ ] Cards and Rule Matrix show consistent statuses and decisive reasons; existing status filters/counts remain correct.
- [ ] Six example variants across five statuses remain six visible, independent matches in All view; multiple variants of one promotion are not collapsed.
- [ ] Unresolved identity, no matching published promotions, direct navigation/reload empty state and FE-05 error states remain distinct.
- [ ] No extra network request, persistence or client classification logic is introduced.

### Data and consistency

- [ ] Existing Zod API contract and transient snapshot remain the source of truth; no backend schema/data/migration change.
- [ ] Reason and rule-evaluation order are deterministic, even with repeated kinds and mixed outcomes.
- [ ] Empty or null optional detail produces honest fallback copy, never a new inferred classification or date.
- [ ] Promotion source metadata, benefit amounts, purchase details and official URLs remain unchanged.

### Security

- [ ] Backend text is escaped; malicious HTML-like strings cannot execute.
- [ ] Purchase details do not leak into URL, storage, cookies, analytics or new logs.
- [ ] Official links retain URL validation and `noopener noreferrer`; no user-supplied reason is used to construct a URL.
- [ ] No internal UUID or unsupported claim guarantee appears in the explanation UI.

### Accessibility and UX

- [ ] Labels, not colour alone, communicate status and rule outcome; icons are decorative where redundant.
- [ ] Per-card explanation has clear semantic headings and labelled list groups; repeated cards remain distinguishable by title/variant.
- [ ] Disclosure controls work via keyboard, expose state appropriately, and do not trap focus.
- [ ] At 320px width, 200% text zoom and reduced-motion preference, explanations reflow with no lost content or horizontal page overflow.
- [ ] Existing WCAG 2.2 AA-oriented automated checks pass for representative statuses, filters and disclosures.

### Code quality

- [ ] Only presentation mapping and the narrowly required results UI/tests change.
- [ ] No parallel rules engine, second API client, new global state manager, or unrelated refactor.
- [ ] Existing FE-06 tests remain meaningful; adjust assertions to the new observable copy instead of weakening them.
- [ ] Formatting, ESLint, TypeScript, Jest, Playwright, production build and smoke checks pass or are reported with exact blockers.

---

## Tests to add or update

### Unit tests

Extend `frontend/src/features/eligibility/results/presentation.test.ts` or add `explanations.test.ts` for the pure mapping:

1. Exhaustively map every `RuleReasonCode` and `EligibilityReasonCode` to readable text; assert exact supported code coverage so future additions are not forgotten.
2. Table-test the five statuses with representative decisive codes, nullable claim timing, and no extra decision logic.
3. Definite failures with **two or more failed reasons**: preserve ordering and display all; a simultaneous unknown appears in a separate group, not as the reason for rejection.
4. Two unknown reasons plus satisfied checks: no false “not eligible”, no fabricated requirement or unavailable form field.
5. `POTENTIALLY_ELIGIBLE` with **all rules satisfied** and only `claim_window_unspecified`: claim-timing uncertainty correctly explained; no claim the customer omitted a receipt or purchase price.
6. Unknown purchase price with and without submitted `purchase_price`: guidance only suggests supplying price when actually absent; do not claim input missing when present.
7. All rules satisfied but `claim_window_status` open/not yet open/expired; use recorded dates if available and generic truthful copy when claim-window detail is null.
8. Empty `reasons`, empty `rule_evaluations`, null claim window, empty `explanation` and absent optional benefit detail: honest fallbacks and no exception.
9. Multiple variants with the same promotion ID but different variant IDs remain independently labelled and ordered.
10. Do not interpret `promotion_status: 'expired'` as `eligibility.classification: 'EXPIRED'`.
11. No `Date.now()` / browser-clock-dependent classification or claim-date inference in presentation helpers.

### Component tests

Extend `ResultsOverview.test.tsx`:

- Verify a visible “Why this result?” statement for each of the five classifications, with meaningful per-variant reasons and correct badges.
- Assert distinct group headings/list items for failed, unknown and passed checks; include a known failure plus an unknown and test that it does not tell the visitor the unknown fact is the cause of `NOT_ELIGIBLE`.
- Verify claim-submission requirements stay in **Claim requirements**, without a failure marker or asserted completion state.
- Confirm `ELIGIBLE` disclaimer and the no-date fallback for upcoming/expired/null claim windows.
- Confirm potential eligibility from unspecified claim timing alone, with correct guidance.
- Verify same mapped reason wording in cards and the Rule Matrix; filtering and disclosure interactions still work.
- Preserve existing tests for malicious names/HTML strings, official links, large values, accessible headings, zero matches, unresolved identity and session-empty state.
- Avoid snapshot-only or class-name-only assertions where visible semantics can be tested.

### Browser / end-to-end tests

Extend `frontend/e2e/purchase-results.e2e.ts` using deterministic mocked upstream fixtures:

- From `/check`, one explicit POST produces `/results`; check each of five statuses and at least one visible decisive explanation in a **mixed multi-variant** response. Switch Cards ⇄ Rule Matrix and filter every category; no new API request.
- `NOT_ELIGIBLE`: prove a failed condition is named as the deciding reason and an additional unknown is not mistaken for the cause.
- `POTENTIALLY_ELIGIBLE`: cover both a real unknown rule and an unspecified claim window with otherwise satisfied rules (extend `support-upstream.mjs` minimally if needed).
- `CLAIM_NOT_YET_OPEN` and `EXPIRED`: dates must match the fixture's `evaluation_date`, `opens_on` and `deadline_on`; no fabricated date or browser-current-time wording.
- Keyboard-only interaction for reason details; axe accessibility checks after filters/disclosures.
- Responsive coverage reusing existing 320/360/375px, 200% text and `expectReflow` helpers rather than creating a redundant full matrix of tests.
- Preserve direct-entry/reload/no-session, edit-and-invalidate, service-error and no-extra-request scenarios.

### PostgreSQL integration tests

N/A — no persistence changes.

### API/application tests

No new backend tests. Preserve frontend Zod contract tests and the FE-05 request/error integration tests. Run the existing suites because FE-07 consumes validated response shapes.

### MCP contract tests

N/A — MCP unchanged.

### External-boundary tests

Existing deterministic upstream fixture covers the sole REST boundary. No live manufacturer website, AI provider or additional external service test is required.

---

## Verification commands

Use the commands defined in the **current** `frontend/package.json`, from `frontend/`. At review time these scripts exist:

```bash
# Select Node and package-manager versions matching package.json and the lockfile.
node --version
pnpm --version
pnpm install --frozen-lockfile

# Focused unit/component regression, update paths to actual files created.
pnpm exec jest --runInBand --runTestsByPath \
  src/features/eligibility/results/presentation.test.ts \
  src/features/eligibility/results/ResultsOverview.test.tsx

# Standard frontend checks.
pnpm format:check
pnpm lint
pnpm typecheck
pnpm test
pnpm build
pnpm smoke

# Targeted and broader browser acceptance (Playwright setup per existing config).
pnpm exec playwright test e2e/purchase-results.e2e.ts
pnpm test:e2e
```

If a helper is extracted, include its test file in the focused Jest run. Do not assert these commands passed without actually running them. If CI is queued/hanging, report that separately from local test results and do not approve a PR solely because checks have not returned.

For any command that cannot run, record the exact command, reason, verification performed instead and remaining risk. Do not weaken failing assertions to obtain a green run; distinguish genuine changes to expected copy from regressions.

---

## Completion report

When FE-07 is implemented, report:

### Changed

The explanation mapping/component and precise `/results` behaviour changed, with paths.

### Database and migrations

None.

### API/MCP contracts

None unless actual verified drift required a minimal contract correction; specify that deviation.

### Tests and verification

List the exact unit/component/browser tests added or updated, all commands **actually run**, and pass/fail results.

### External configuration

None.

### Deviations

Any changes outside this narrow frontend explanation scope, with justification; otherwise None.

### Remaining risks or follow-up

List unresolved accessibility, data-contract, optional-fact or CI issues; otherwise None.
