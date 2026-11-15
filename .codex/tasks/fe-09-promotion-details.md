# FE-09 — Promotion Details

## Repository state

**Expected branch:**  
`fe-09-promotion-details` (create from the current `main` after verifying the working tree and open PRs)

**Base branch:**  
`main`

**Dependencies:**

- FE-01–05: Next.js App Router, React, TypeScript, Tailwind v4, typed API conventions, server-side API origin configuration and purchase-check form.
- FE-06/07: `/results`, session-only purchase-check snapshot, promotion-variant cards, five backend eligibility classifications, accessible explanations and official source links.
- FE-08 / merged PR #44: `RewardDetails`, `ClaimWindowSummary`, and shared date/GBP display helpers; **do not regress or duplicate them**.
- Published backend data: `Promotion`, `PromotionVariant`, associated products/retailer/benefits/rewards/requirements/sources; `PublishedPromotionDetails`, `get_published_details`, and `SqlAlchemyPromotionRepository.load_published_variant`.
- **Missing prerequisite to implement within this vertical slice, or as an explicitly linked prerequisite PR:** a public, read-only REST projection for complete published promotion details. The existing backend supports an individual variant lookup through the application/MCP boundary but **does not expose a promotion-by-slug REST endpoint**. A functional refreshable public page must not be implemented using static fixtures or a purchase-check session as its source of truth.

### Read first

- `.codex/tasks/TEMPLATE.md`, repository `AGENTS.md`, and any applicable scoped `AGENTS.md` found at implementation time.
- `.codex/tasks/{fe-06-eligibility-results-overview,fe-07-eligibility-status-explanations,fe-08-rewards-claim-windows}.md` and `frontend/README.md`.
- `frontend/src/app/{layout.tsx,results/page.tsx,check/page.tsx}`; `frontend/src/features/eligibility/results/{ResultsOverview,EligibilityExplanation,RewardDetails,ClaimWindowSummary,presentation}.tsx` / `.ts` and colocated tests.
- `frontend/src/features/eligibility/session/PurchaseCheckSession.tsx`; `frontend/src/lib/api/{eligibility.contract,eligibility,config,http,errors}.ts`; existing route bridge `frontend/src/app/api/eligibility/check/route.ts`.
- `frontend/e2e/{purchase-results.e2e.ts,support-upstream.mjs,support-layout.ts}`; frontend test/build configuration and shared UI primitives.
- `backend/app/main.py`, `backend/app/api/{eligibility.py,schemas/eligibility.py}`, `backend/app/application/{promotion_details,purchase_check_details,purchase_check}.py`, `backend/app/db/{models/core.py,repositories/promotions.py}`, `backend/app/mcp/schemas.py`.
- `backend/app/domain/{claim_windows,rewards,requirements,promotion_provenance,promotion_lifecycle,eligibility_rules}.py`; `backend/tests/integration/test_mcp_supporting_tools.py` and relevant PostgreSQL fixtures.

### Primary change area

A new **public, directly accessible** Next.js details route `/promotions/[slug]` showing the complete **recorded, published** promotion and its variants: benefits/reward definitions, qualifying products and retailers, purchase and claim-period rules, claim requirements, official source evidence and claim destinations. Provide a narrowly scoped, server-consumable backend projection if a suitable published REST endpoint is still absent.

### Canonical implementation examples

- `ResultsOverview.tsx` already presents per-variant information and has an inline disclosure labelled “View Full Promotion Details”. FE-09 adds a **separate working route**, with a clear link from each card; keep useful quick details without conflating an accordion with route navigation.
- `RewardDetails.tsx` presents **purchase-specific calculated amounts**; static published reward definitions are different and must get a separate type/presenter, while reusing typography/benefit-category conventions.
- `ClaimWindowSummary.tsx` presents **purchase-specific evaluated** dates and status; FE-09 presents fixed/relative **configured** windows without calculating individual opening dates or classifying today’s claim status.
- `eligibility.contract.ts` describes the **purchase-check response**, not a public promotion-details contract. Add a distinct typed, validated details DTO; do not falsify `eligibility.classification` or reuse a check-result schema for static promotion data.
- `get_published_details` validates publication visibility and source provenance for one variant. Reuse this validated projection and published-only query boundary rather than constructing another business rule engine in FastAPI or React.
- `backend/app/db/models/core.py` enforces `(manufacturer_id, slug)` uniqueness on `promotions`, while each promotion has zero or more `promotion_variants` identified separately. Do not treat the bare promotion slug as globally unique.

### Relevant symbols

`Promotion`, `PromotionVariant`, `Product`, `Manufacturer`, `Retailer`, `Benefit`, `BenefitReward`, `Requirement`, `PromotionSource`, `PublishedPromotionDetails`, `PublishedLookup`, `get_published_details`, `LookupNotFound`, `PublishedPromotionDataError`, `SqlAlchemyPromotionRepository`, `purchase_check_snapshot`, `FixedClaimWindow`, `RelativeClaimWindow`, `FixedAmountReward`, `PercentageReward`, `ProductSpecificReward`, `PublishedProvenance`, `validate_publication_provenance`, `ResultsOverview`, `PromotionCard`, `RewardDetails`, `ClaimWindowSummary`, `ButtonLink`, `Container`, `Card`, `getApiOrigin`, `readBounded`, `withDeadline`, `problemSchema`.

### Expected change surface

```text
.codex/tasks/fe-09-promotion-details.md                   # this specification
frontend/src/app/promotions/[slug]/page.tsx              # server-rendered public route
frontend/src/app/promotions/[slug]/page.test.tsx         # route and state tests
frontend/src/app/promotions/[slug]/loading.tsx           # optional accessible loading state
frontend/src/app/promotions/[slug]/error.tsx             # safe recoverable failure state
frontend/src/app/promotions/[slug]/not-found.tsx         # optional scoped 404
frontend/src/features/promotions/details/*              # UI, pure formatting, tests
frontend/src/lib/api/promotion-details.contract.ts       # new Zod public details schema
frontend/src/lib/api/promotion-details.server.ts         # server-only bounded GET client
frontend/src/features/eligibility/results/ResultsOverview.tsx
frontend/src/features/eligibility/results/ResultsOverview.test.tsx
frontend/e2e/promotion-details.e2e.ts                    # new browser journey tests
frontend/e2e/purchase-results.e2e.ts                    # card-to-details navigation
frontend/e2e/support-upstream.mjs                       # deterministic GET fixture support
frontend/README.md                                     # route and scope guidance

# Minimal enabling public data read if not supplied by a prerequisite backend PR:
backend/app/api/promotions.py
backend/app/api/schemas/promotions.py
backend/app/main.py
backend/app/application/promotion_details.py            # extend read composition, if needed
backend/app/db/repositories/promotions.py                 # published group lookup + names
backend/tests/unit/test_promotion_details_api.py        # or existing appropriate unit suite
backend/tests/integration/test_promotion_details_api.py
```

Paths are guidance, not a licence for broad refactoring. Keep the backend addition **read-only**; if product/retailer display-name projection can be added within the existing application/repository boundary, prefer that over a second data-access architecture. Explain changed paths beyond this list.

### Excluded areas

- No new eligibility check triggered by visiting the details page. No personalised classification, rule evaluation, reward calculation, claim-submission confirmation, payment status or automatic countdown.
- No authentication, accounts, saved promotions, purchase history, claims handling, evidence upload, notifications, email, scraping, AI-generated terms, content authoring or publisher UI.
- No changes to promotion publication rules, status transitions, reward computation, claim-window algorithms, existing purchase-check response shape, MCP tool contracts or stored business semantics.
- No new database schema, slug migration, slug rewriting, seeding changes, or fabricated global slug uniqueness. If an essential persistence change is discovered, report it as a separate prerequisite instead of silently modifying the schema.
- No new listing route `/promotions` until its own feature is specified; breadcrumbs/navigation must not link to an unimplemented page.
- Do not make frontend-only placeholder content appear to be published data when the public read endpoint is unavailable.

### Unknowns Codex must verify

1. Current `main`, FE-08 merge status, existing FE-09 branches/PRs and any newer route, API or scoped instructions. Review against current files, not remembered line numbers.
2. Whether a suitable public published-promotion read endpoint has been added since this spec was drafted. If so, prefer it and reconcile the proposed response contract rather than creating a duplicate.
3. Actual manufacturer/product/retailer identity and display-name loading patterns, including published-only filtering and the behaviour of missing/removed linked product data.
4. Exact reward types, required fields and whether the projection supports all product-specific values for public display without calculating a personal payout.
5. Behaviour of all recorded claim-window forms, including fixed minimum wait and relative offsets; confirm inclusive day semantics and constraints in domain code.
6. Whether default Next.js fetch caching and request-scoped rendering might accidentally show outdated publication state; establish the intended no-store policy.
7. Established API problem-details status/error mappings and correlation IDs; preserve them when adding the endpoint and server client.
8. Package/toolchain pinning: at review `frontend/.node-version` is `24.22.0`, and `frontend/package.json` expects **pnpm 12.16.1**; older README instructions mention pnpm 10.34.7. Use the checked-in manifest/lockfile rather than following stale README commands.

---

## Objective

A visitor opening `/promotions/[slug]` directly, refreshing it or following a results-card link can inspect the **same recorded promotion** without having a purchase-check session. The page must explain:

1. Who is offering the promotion, its recorded publication state and available qualifying-purchase dates.
2. Which variants, products/models and retailers are covered by the published structured data.
3. Which cashback, extended-warranty and free-gift benefits are recorded, including the type and limitations of any stored reward definition.
4. How the recorded **claim rules** work (fixed dates, relative offsets and minimum wait) and which claim documents/actions are listed, without inventing personal eligibility or deadlines.
5. Where the official source, terms and claim site can be opened, with evidence roles and verification timestamps.

**Definition of done:** a real published promotion with several variants renders all above data through a server-fetched, Zod-validated read-only contract. A deep link works in a fresh tab; nonpublished/unknown records are excluded; purchase-check results and existing UI remain correct.

### Design intent and UX hierarchy

- **Within five seconds**, show promotion name, manufacturer, recorded state, benefit categories and clear official-terms action. Prioritise useful information above decoration.
- **Top:** optional valid breadcrumb `Home > [Promotion]` (no unimplemented promotions index), one `h1`, manufacturer, status label **“Recorded as active”** or **“Recorded as expired”**, short statement that these are published promotion terms rather than confirmation of an individual's entitlement.
- **Summary:** benefit categories, qualifying purchase-period range when supplied, claim-window **definition** and evidence “Last official source verified [timestamp]”. Do **not** call a claim window “open now”.
- **Main:** labelled sections “Who qualifies”, “Benefits”, “Claim period”, “What you need to claim”, “Official sources and terms”. Render **each published variant separately** if its products/retailer/benefits/requirements differ; don't merge variants or repeat a promotion-level source list under every card.
- **Desktop:** readable primary detail column and a compact secondary panel for official terms, recorded claim link and source verification. **Mobile:** one natural stacked reading order with primary action near the top; no horizontal scroll at 320 px.
- **Actions:** “Check my purchase” links to `/check`; “Read official terms” links to the validated primary source; “Visit official claim site” to the validated claim source with a caveat that the official provider controls eligibility, dates and claim acceptance.
- Use semantic headings, descriptive labels, accessible lists and native links; text and icons must convey meaning without relying on colour. Reuse FE-02 tokens and UI primitives.

### Route identity and linking

The database's constraint is `UNIQUE(manufacturer_id, slug)`, **not** globally unique `slug`. Keep the single-segment route by defining the public slug as:

```text
/promotions/<manufacturer-slug>--<promotion-slug>
```

The double hyphen is an unambiguous delimiter because each stored component matches `^[a-z0-9]+(-[a-z0-9]+)*$`, which cannot contain `--` internally. This is a **derived URL key only**: do not change persisted slugs or invent a different global uniqueness constraint.

- Parse the canonical key strictly and case-sensitively; reject malformed encodings, empty components, invalid characters, unexpected additional delimiters and excessively long segments with 404. Resolve by both database slugs, not by text search or `promotion_name`.
- Construct links from **backend-returned canonical public slug**. Purchase-check results currently have promotion/variant UUIDs but **not** slugs; add a **minimal, backward-compatible optional link identifier** to the purchase-check REST response only if required, with matching Zod validation and contract tests. Prefer a stable supported lookup mapping if it can avoid changing the check response without an extra request per card. Never derive slugs from display names or issue an N+1 lookup.
- All variants of a promotion share the canonical URL. For a link from a specific result card, append `#variant-<promotion_variant_id>` to focus/scroll to the corresponding variant section. Use a real ID on the page and ensure keyboard/focus navigation behaves sensibly. Do **not** expose submitted purchase data in the URL.
- The route must continue to work with no `/results` snapshot, after reload and in a new tab. An optional session-aware “Back to results” link is supplementary; always provide an unconditional check/home path.

---

## Architecture and invariants

1. **Public source of truth:** only structured, validated, **published** backend promotion data. The detail route must not reconstruct a promotion by querying the user's last check or scraping an external site.
2. **Stable identity:** a promotion is identified by manufacturer slug + promotion slug, and a variant by UUID. No deduplication of distinct published variants.
3. **No decision from static details:** `promotion.status` means publication lifecycle, not whether a given purchase is eligible or whether a claim is currently open. Only `POST /api/v1/eligibility/check` can return a purchase-specific classification.
4. **Presentation-only formatting:** React may label configured rules and format dates/currency; it must not apply new eligibility precedence, evaluate windows, infer qualifying purchases, or compute percentage cashback from a price.
5. **Evidence is passive:** official source records are retrieved from curated published data. Source HTML/PDF is **not** downloaded, executed or automatically interpreted by this page.
6. **Minimal read interface:** backend REST uses application services/domain types and SQLAlchemy repositories. It does not create a second eligibility engine or parallel MCP-only business logic.
7. **Server rendering:** the App Router page is a Server Component; it fetches on the Next server through existing `BENEFITSCOUT_API_ORIGIN` validation. No browser-exposed origin, public secret or direct database access from Next. Small client components only for optional disclosures and contextual navigation.
8. **Consistent visibility:** only `active` and `expired` records which satisfy existing publication evidence validation are visible. `discovered`, `extracted`, `review`, `archived`, missing and corrupt records must never render as successful public pages.
9. **No stale personal data:** the page does not read/write the transient purchase-check session to obtain its content, and does not cache personalised results.
10. **Safe fallback:** absent/unconfigured optional fields have truthful, explicit copy; malformed authoritative data fails visibly rather than silently inventing terms.

---

## API and contract changes

**A new public read contract is required unless a compatible endpoint has already landed.** The following describes the expected behaviour; final Python/Pydantic and Zod field names must be kept in exact parity. Avoid reusing the **purchase-check** `Promotion` schema since it includes evaluated eligibility, purchase-specific benefit amounts and `claim_window` status.

### Backend endpoint

- **Name/method:** `GET /api/v1/promotions/{manufacturer_slug}/{promotion_slug}`.
- **Purpose:** retrieve all validated, published variants and stable, static details of one promotion.
- **Input:** two canonical URL slug path parameters, lowercase ASCII, each `^[a-z0-9]+(-[a-z0-9]+)*$`, bounded by database field limits; no request body; no purchase details.
- **Auth:** public read access; no cookies or user identity required. No mutations, idempotent and safe to retry within bounded read policy.
- **200:** JSON with exactly one resolved published promotion, all published variants, and source provenance.
- **404:** unknown/malformed/nonpublished/archived promotion. Do not leak draft existence.
- **503:** database/infrastructure temporarily unavailable; **500:** corrupt published projection/invariant. Use established `application/problem+json` shape and `X-Request-ID` where supported, without stack traces or SQL messages.
- **Caching:** `Cache-Control: no-store` initially so withdrawal/publication updates are not hidden behind a stale site or Next cache. No listing, pagination or filtering for this single-promotion endpoint. Sorting of variants, products, benefits, requirements and sources must be deterministic.

### Minimum read DTO (illustrative types; implement strictly in Pydantic and Zod)

```ts
type PromotionDetails = {
  promotion_id: string;            // UUID
  public_slug: string;             // <manufacturer-slug>--<promotion-slug>
  name: string;
  status: 'active' | 'expired';
  manufacturer: { id: string; name: string; slug: string };
  purchase_window: { starts_on: string | null; ends_on: string | null };
  claim_window:
    | { kind: 'fixed'; opens_on: string; deadline_on: string; minimum_days_after_purchase: number | null }
    | { kind: 'relative'; opens_after_purchase_days: number; deadline_after_purchase_days: number }
    | null;
  variants: Array<{
    promotion_variant_id: string;
    code: string;
    name: string | null;
    retailer: { id: string; name: string } | null;  // null = no stored retailer restriction
    products: Array<{ id: string; name: string; model_number: string | null }>;
    benefits: Array<{
      benefit_id: string;
      benefit_type: 'cashback' | 'extended_warranty' | 'free_gift';
      name: string;
      description: string | null;
      reward:
        | { kind: 'fixed_amount'; amount_gbp: string }
        | { kind: 'percentage'; percentage: string }
        | { kind: 'product_specific'; values: Array<{ product_id: string; amount_gbp: string }> }
        | null;
    }>;
    requirements: Array<{
      requirement_id: string;
      requirement_type: 'receipt' | 'serial_number' | 'registration' | 'invoice' | 'barcode' | 'imei' | 'installation_evidence';
      description: string | null;
    }>;
  }>;
  provenance: {
    official_source_url: string;
    claim_url: string;
    last_verified_at: string;     // timezone-aware timestamp
  };
  sources: Array<{
    source_id: string;
    role: 'primary' | 'terms' | 'claim' | 'supporting';
    url: string;
    source_type: 'web_page' | 'pdf' | 'other';
    retrieved_at: string;        // timezone-aware timestamp
    verified_at: string | null;  // timezone-aware or null
  }>;
};
```

DTO rules:

- Derive display names through verified ORM relationships; do not hand-copy marketing examples. Never expose raw ORM objects, unpublished rows, internal audit fields, unknown product IDs as names or unpublished source material.
- Keep **all** benefit rows and requirements per variant, and all source roles at promotion level; don't collapse by benefit type or retailer.
- Use exact decimal strings for GBP/percentages and canonical `YYYY-MM-DD` for calendar dates. Validate URL scheme, host, credentials and unsafe characters against existing source-URL conventions. Render strings as text.
- Do not include `eligibility.classification`, `rule_evaluations`, purchase-specific `cashback_reward_gbp`, `claim_window.status`, user-supplied purchase fields, customer data or claim-completion state in this public read DTO.
- Reuse `get_published_details` / equivalent validated projection to enforce public visibility and provenance **before** serialising. Any group read must enforce the same invariant for each published variant; do not leak a hidden variant through a parent join.
- If the existing purchase-check response must gain `public_slug` for card linking, add it **additively** with a correctly constrained schema and preserve all existing fields and result semantics. Document this change with updated backend OpenAPI and FE contract tests. Do not add a new per-card fetch.

### Frontend server read

- `getPromotionDetails(publicSlug)` parses the two components, validates the canonical key and calls the backend GET from a **server-only** module using `getApiOrigin()`; no same-origin browser bridge is needed for this SSR page.
- Use established bounded timeout/response size and safe error handling (`withDeadline`, `readBounded`, response media type and problem envelope validation). No redirects, no credentials, no unbounded retry, no arbitrary user-supplied URL or hostname.
- Zod-validate all successful responses, including IDs, dates, reward discriminants, source URLs, source timestamp nullability and variant completeness. Validate response `public_slug` equals the requested canonical identity.
- Map 404 to Next.js `notFound()`; map missing origin, 5xx, timeout or invalid schema to an accessible recoverable error (not a fabricated 404 or empty promotion). Preserve safe correlation ID where available.
- Ensure page content and metadata do not trigger duplicate upstream fetches (request-scoped memoisation if metadata reads the same data). No static export or persistent Next fetch cache for these public records.

---

## Domain and application behaviour

### Published detail lookup

1. Request one canonical promotion by **both** manufacturer and promotion slugs. The lookup returns nothing for missing/draft/review/archived records and never calls `check_purchase`.
2. Resolve all published promotion variants in a coherent read-only database snapshot. Materialise variant-specific eligible product names/model numbers, retailer restriction, benefits/reward definitions and requirements. Validate sources once for the promotion; preserve role, verification and retrieval times.
3. Read static purchase and claim-window definitions exactly as stored. Do not evaluate claim status using server time or generate a per-user deadline.
4. Sort variants by stable variant code then UUID; products by model/name then UUID; benefits/requirements by ID; sources by role then source ID. Use stable IDs as React keys, not array positions.
5. Publish no partial success: if one required variant association is invalid or provenance is inconsistent, fail closed through a safe 500 rather than omit the invalid part and imply an incomplete promotion is authoritative.

### Eligibility-rules presentation

| Recorded data | Required UI explanation |
| --- | --- |
| Manufacturer | Name the manufacturer responsible for the promotion. |
| Products per variant | List each qualifying model/product supplied by the backend. Do not imply that similarly named products qualify. |
| Retailer per variant | If present, “Qualifying retailer: [name]”; if null, “No retailer restriction recorded”, not “All shops definitely accepted”. |
| Purchase start/end | Display actual bounds as **Qualifying purchase dates**. A null bound is “not specified”; don't fabricate a date. |
| Additional condition, country, channel or price rules | Display **only if** represented by validated published fields and supported in the DTO. The current persisted projection does not expose a comprehensive rule set for these; never manufacture rules by reading prose or interpreting purchase-check reason codes. |
| Missing rule information | “Only recorded conditions are shown here. Check the official terms for the full requirements.” |

A visitor must not see “Eligible”, “Not eligible”, “Claim period open”, or “You qualify” based on the detail read. Offer `/check` to obtain a **separate explicit** purchase-specific decision.

### Benefit/reward presentation

- Show all benefits (`cashback`, `extended_warranty`, `free_gift`) and their exact published names/descriptions. Use a category label even if the name is vague.
- Cashback: fixed amount displays the recorded GBP amount; percentage displays “X% cashback (subject to qualifying purchase price)”; product-specific amounts pair each value with its **actual associated product**. Do not compute a monetary result on this page or sum mixed benefits.
- Reward `null`: “Cashback amount not recorded” if a cashback reward is absent; do not display £0. Other benefit types must not acquire monetary values or invented warranty duration/gift value.
- If the source record has no description, render a neutral absence state, not AI-written offer copy.

### Claim-period presentation

- **Fixed:** show recorded start and deadline, plus “At least N days after purchase” when a minimum wait is configured. The earliest date for a particular purchase could be later than the fixed start; do not label the fixed start as a guaranteed claimant opening date.
- **Relative:** show “Opens N calendar days after purchase” and “Deadline N calendar days after purchase”; these are **offsets**, not absolute dates. Clarify that individual dates depend on the purchase date.
- **Null:** “Claim timing not recorded. Check the official terms”; no countdown, fabricated date or inferred current window status.
- Purchase-date rules and claim-submission rules remain distinct. Preserve inclusive domain-day semantics in explanatory copy; do not perform the date computation client-side.

### Claim requirements and official sources

- Render each actual stored requirement (`receipt`, `invoice`, `serial_number`, `barcode`, `imei`, `registration`, `installation_evidence`) with description if present. These are things **required to submit a claim**, not evaluated eligibility conditions and not a completion checklist.
- An empty list means **“No claim requirements recorded here; check the official terms”**, not “Nothing required”. Do not add upload fields or working claim-submission controls.
- Render source links with roles (“Official promotion source”, “Terms”, “Claim site”, “Supporting source”), source type, retrieved and verified timestamps. Show “Verification not recorded” if optional supporting-source verification is null.
- Use provenance-selected official/claim URLs from the validated projection; include `target="_blank" rel="noopener noreferrer"` and accessible new-tab cues. Never auto-open a claim site or suggest an open/guaranteed claim just because the link exists.

### Navigation, empty and failure behaviour

- `/results` promotion card contains a working internal link “View promotion page” or “View full promotion details” to the correct canonical URL and variant anchor. If preserving the existing disclosure, rename it clearly to “Show quick details” and retain its behaviour; do not leave two ambiguous controls with the same name.
- Direct URL/reload/new tab: the page fetches independently of React client session. Browser back still returns to `/results` when available, without re-running eligibility; do not persist old results to make navigation work.
- Missing/hidden/malformed slug: semantic 404 with a `Check my purchase`/Home path. Backend unavailable/config absent/timeout: safe retry state, not a misleading promotion or false 404. Invalid backend schema: fail closed, log safe diagnostic code, no partial HTML claiming success.
- Long content, optional null descriptions, duplicate display titles, many variants, and source URLs must wrap without breaking layout. No `dangerouslySetInnerHTML` or rendering third-party HTML/Markdown.

### Eligibility-specific rules

**No new runtime eligibility decision.** The FE-09 page shows recorded static qualifying conditions only. `POST /api/v1/eligibility/check` remains the sole source for the five purchase-specific classifications, rule precedence and evaluated claim windows. An FE-09 implementation must not duplicate `classify_eligibility`, `calculate_reward` or claim-window evaluators.

### Ingestion/publication rules

**No changes.** The new read path must honour existing publication validation, only consume published data, preserve source evidence and never make extracted/review-stage records visible through a new public endpoint.

---

## Persistence, transactions, and migrations

**No schema or Alembic migration is expected.** Existing `(manufacturer_id, slug)` promotion uniqueness and variant associations support the proposed canonical URL.

- Implement the read through SQLAlchemy repository boundaries and a **single coherent read-only PostgreSQL snapshot**; favour the established repeatable-read, no-autoflush/no-commit approach where applicable.
- Ensure a multi-variant read cannot mix rows across a concurrent publication/change; release sessions and rollback on success/failure.
- Do not add speculative indexes. Verify the existing unique composite promotion index handles slug lookup and existing association indexes handle variants.
- Verify with a real PostgreSQL Testcontainers integration test, including two manufacturers with the **same** stored promotion slug.
- If a persistent-data change proves essential, document it separately and use normal migration review; do not sneak it into FE-09.

---

## External services and network access

- **Next -> backend:** one bounded server-to-server GET, using already configured `BENEFITSCOUT_API_ORIGIN`. In production the established HTTPS rule applies; development loopback HTTP is allowed under current configuration.
- **Browser -> official providers:** explicit user-clicked passive anchor links only; no tracking claims, source fetching or URL proxying.
- Do not introduce new provider keys, third-party frontend dependencies, unauthenticated remote scraping, cookies, browser-local URL injection, or extra client API round trips.
- Network failures must be recoverable. Avoid automatic multiple retries at both Next and Python layers.

---

## Security and privacy

- Publication gating must happen at the backend read boundary before exposing the associated graph. An unpublished/archived record cannot be guessed through promotion or variant identifiers.
- Validate user-controlled slug parameters **before database access**; cap length, reject invalid format and never interpolate them into SQL/text queries. Bind parameters through SQLAlchemy.
- Validate all returned data at the server and treat names, descriptions, and source URLs as untrusted data for rendering. Text only; no unsafe HTML, image hotlinks, executable rich content or scriptable URL schemes.
- Reuse established source-link policy; reject embedded credentials, whitespace/control characters, invalid hosts/protocols. Official links are *recorded*, not real-time-vetted provider guarantees.
- Keep `BENEFITSCOUT_API_ORIGIN` server-side. Do not include purchase details, user identity, receipts, session payload or origin secrets in query strings, metadata, logs or analytics.
- Use structured low-cardinality route labels and correlation IDs where available; no raw provider response dumps or personal information.

---

## Configuration and deployment

### Environment variables

No new variables. Reuse existing server-only `BENEFITSCOUT_API_ORIGIN`, honouring its existing URL validation and local-vs-production restrictions. The `/promotions/[slug]` route requires a running backend; the frontend build and other routes must not require a live connection merely to compile.

### Runtime/deployment changes

- Backend deployment must expose the read-only promotions REST endpoint before traffic to the new detail links; coordinate feature rollout or deploy atomically.
- No new scheduler, worker, Docker image, auth provider, database credential, storage service or static-export conversion.
- If the backend is unconfigured or unavailable, render a truthful accessible failure. Do not compile a static catalogue of promotions at build time.

---

## Observability and operations

- Record safe operation identifiers, HTTP status, duration, request/correlation ID and error category for the new backend GET. Do not log full URLs with untrusted inputs or source contents.
- Distinguish 404 nonpublished/not-found (expected) from schema/data-integrity failure, upstream timeout and persistence outage (operational).
- Reuse the project's current logging/Sentry conventions rather than adding a separate telemetry stack. No new health endpoint or high-cardinality per-slug metric labels.

---

## Failure, consistency, and recovery

| Scenario | Required behaviour |
| --- | --- |
| Invalid composite slug or non-existent record | 404, no promotion data rendered, useful navigation. |
| Draft/review/archived promotion | Same public 404 behaviour; no unpublished identity leakage. |
| Multiple manufacturers share stored promotion slug | Canonical URL resolves **only** the requested manufacturer. |
| Several variants share the promotion | All published variants render, stable keys/anchors, no accidental deduplication. |
| Backend origin missing or GET times out | Safe recoverable unavailable state; no fallback to stale `/results` data. |
| Corrupt published relationships or evidence | Fail closed with safe server error, no partial public claims. |
| Source link has unsafe URL syntax | Reject invalid contract/fail closed; never render a clickable unsafe link. |
| Promotion status changes between requests | Next request reflects backend state (`no-store`); expired still public, unpublished no longer public. |
| User reloads or shares URL | Same published details load without session, check call or purchase data. |
| Relative/minimum-wait claim window | Accurate static rule only; no invented absolute personalised deadline. |

---

## Acceptance criteria

### Behaviour

- [ ] A valid published promotion has a functioning, refreshable `/promotions/[slug]` page with one `main#main-content`, one `h1` and full recorded title/manufacturer/status.
- [ ] Same stored promotion slug under two manufacturers resolves to distinct pages by canonical composite public slug.
- [ ] All published variants are shown separately with eligible products/model labels and optional retailer restriction; results link selects its variant by stable hash anchor.
- [ ] Every stored benefit and reward definition renders faithfully; no calculated personal payout or invented warranty/gift information.
- [ ] Fixed, relative, minimum-wait and unspecified claim windows are explained correctly **without** live status or client calculations.
- [ ] All claim requirements and official sources/terms/claim URLs are visible with provenance timestamps; empty requirements are not described as “none required”.
- [ ] “Check my purchase” works; visiting the page never calls the check endpoint.
- [ ] Existing FE-06/07/08 results filters, explanation semantics, benefits, claim-window summaries and quick details continue to work.
- [ ] Missing/hidden/error states are accessible and truthful; the route works on direct load, refresh and fresh tab.

### Data and consistency

- [ ] Every public detail is backed by a real published projection; no fixtures, invented rules or display-name-generated slugs in production.
- [ ] No unpublished/archived promotion or invalid association is exposed; corrupted data fails closed.
- [ ] No schema migration or publication state change. No `POST /eligibility/check` response semantic regression.
- [ ] Source roles, official URLs, timestamps, variant IDs, required fields, nullable fields and decimal strings match backend and Zod contracts.

### Security

- [ ] Slugs and response URLs are validated, external links use secure new-tab attributes, and all third-party content is escaped as text.
- [ ] No source scraping, SSRF via slug/URL, client-exposed backend origin, session leakage or private purchase data in URLs/metadata.
- [ ] Error responses/logs reveal no SQL, stack traces, secrets or unpublished promotion information.

### Operations

- [ ] Missing backend config and upstream failure produce recoverable error UI, not 404 or fake details.
- [ ] New read endpoint uses bounded read handling, safe problem responses, request IDs and existing observability.
- [ ] Public GET is read-only, deterministic in ordering and reflects publication changes on subsequent requests.

### Code quality

- [ ] Uses existing Next.js, Tailwind, Zod, accessibility conventions and backend application/repository architecture without a new state library or eligibility engine.
- [ ] Types and schema changes are covered by tests; frontend and backend lint/format/type/test/build commands pass.
- [ ] Manual mobile/desktop and keyboard checks completed; no horizontal overflow at 320 px or 200% text size.

---

## Tests to add or update

### Unit tests

- `frontend/src/lib/api/promotion-details.contract.test.ts`: valid multiple-variant DTO; rejected invalid slugs/URLs/decimals/timestamps/statuses; nullable source verification; strict reward discriminants.
- `frontend/src/features/promotions/details/*.test.ts[x]`: static presenter for all benefit categories and reward kinds, supported claim windows/requirements, no invented statuses; labels/links/semantic headings/empty copy.
- `frontend/src/app/promotions/[slug]/page.test.tsx`: valid page, missing/hidden, schema error and unavailable server case, direct route independent of session, no duplicate data fetch where metadata applies.
- `frontend/src/features/eligibility/results/ResultsOverview.test.tsx`: every card has correct canonical link, stable variant anchor; disclosure label distinguished from page link.
- Backend targeted unit tests for strict slug parsing, published-only lookup, DTO mapping and REST error boundary. Use deterministic UUIDs/dates and no live network.

### PostgreSQL integration tests

- `backend/tests/integration/test_promotion_details_api.py`: actual FastAPI GET backed by PostgreSQL/Testcontainers with two manufacturers sharing slug; multiple variants/products/retailers, benefits and product-specific reward values, requirements and full provenance.
- Assert 200 JSON/OpenAPI agreement, 404 for missing/draft/review/archived, no publication leakage, corrupt source/association fails closed, stable ordering, snapshot/session cleanup and no mutation.
- Test fixed, relative, fixed minimum-wait and absent claim definitions from the database, preserving raw configuration (not evaluated dates).

### API/application tests

- Backend FastAPI request/response tests for 200/404/500/503, malformed slug, safe problem envelope, request ID, expected Content-Type and no-store headers.
- Frontend server fetch tests for valid GET, JSON media type validation, bounded body, timeout, redirect refusal, problem schema/error mapping and malformed response handling. Verify `getApiOrigin` protects server destination.
- If purchase-check response adds `public_slug`, update both backend HTTP response tests and `frontend/src/lib/api/eligibility.contract.test.ts`; add backward-compatibility regression covering other purchase-check fields.

### MCP contract tests

**No MCP contract change.** Existing lookup contract tests must continue passing; avoid introducing any REST/MCP divergence in publication visibility or provenance. Add parity evidence if the new read adapter reuses or extends a shared application query.

### External-boundary tests

- `frontend/e2e/promotion-details.e2e.ts`, production Next.js and a deterministic fake read-only upstream: navigate from `/results` to details; direct load, reload and fresh tab without session; verify zero additional purchase-check POSTs.
- Test multiple variants, identical stored promotion slugs under different manufacturers, links to official primary/claim/terms sources, purchase and claim date semantics, missing rule/requirement copy, nonpublished 404, backend unavailable, invalid upstream JSON and unsafe URL handling.
- Check 320/360/375/768/1024/1280/1440 px layout, 200% root text reflow, keyboard skip link/focus and axe WCAG A/AA on a populated page (and error state). Assert no console/page errors and no dead controls.
- Do not contact live manufacturer websites or rely on today's date, live upstream service, or a real AI model in ordinary automated tests.

---

## Verification commands

Run from the indicated directory, with Node.js 24.22.0 and the **manifest-pinned pnpm 12.16.1**; verify versions against the current lockfile first.

```bash
# frontend/
pnpm install --frozen-lockfile
pnpm format:check
pnpm lint
pnpm typecheck
pnpm test
pnpm build
pnpm smoke
pnpm exec playwright install chromium
pnpm test:e2e

# backend/ (when the public read endpoint is added in this work)
uv sync --locked --extra dev
uv run ruff check .
uv run ruff format --check .
uv run pytest tests/unit/test_promotion_details_api.py
uv run pytest tests/integration/test_promotion_details_api.py
uv run pytest tests/integration/test_mcp_supporting_tools.py
uv run pytest

# Real PostgreSQL integration requires the repository's configured Docker/Testcontainers setup.
# No Alembic change expected; verify current upgrade path only if backend data access was changed:
uv run alembic upgrade head
```

Replace targeted test filenames if the implementation integrates tests into established modules; do not silently omit their scenarios. Commands above are drawn from the current manifest/README; if they change, verify and record the correct commands. If a command cannot run, report the exact command, blocker, alternative verification and remaining risk. Do not weaken tests or mistake a queued/hung CI job for a pass.

---

## Completion report

When implemented, report:

### Changed

- The public route, components, working links, canonical slug handling, and public read data projection; state if the enabling backend endpoint was delivered in a separate PR.

### Database and migrations

- `None` expected. If otherwise, identify the approved follow-up and verification results.

### API/MCP contracts

- The new published promotion GET and exact response shape. State whether an additive `public_slug` change was necessary to results responses; confirm MCP is unchanged.

### Tests and verification

- New/updated unit, integration, browser and accessibility tests; commands **actually run**, pass/fail/skipped status and any CI limitations.

### External configuration

- `None` expected beyond existing `BENEFITSCOUT_API_ORIGIN` and backend rollout ordering.

### Deviations

- Explain any approved deviation from manufacturer-qualified canonical routing, contract shape or minimum enabling backend read; don't conceal unsupported scope.

### Remaining risks or follow-up

- Record any unresolved full-terms fields not yet represented structurally, pending authoring capabilities, or manual accessibility checks; never claim the page provides legal completeness or approves eligibility.
