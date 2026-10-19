# FE-02 — Design System & Application Layout

## Repository state

**Expected branch:**  
`fe-02-design-system-application-layout`

**Base branch:**  
`main` (recheck the current HEAD immediately before implementation)

**Dependencies:**

- FE-01 / merged PR #33 — Next.js 16 App Router foundation (React 19, strict TypeScript, Tailwind CSS v4, Jest/React Testing Library, pnpm and frontend CI).
- Five visual references attached to the FE-02 request, described under **Design reference and visual language** below. The images are design direction, **not** authoritative data or production UI copy.
- No backend availability, account system, promotion-feed integration, database migration, new API, or FE homepage implementation is required.

### Read first

- `.codex/tasks/TEMPLATE.md`; `AGENTS.md` and any newly added frontend-scoped `AGENTS.md` (none was present in the inspected `main` tree).
- `frontend/README.md`, `frontend/package.json`, `frontend/tsconfig.json`, `frontend/src/app/layout.tsx`, `frontend/src/app/page.tsx`, `frontend/src/app/globals.css`, `frontend/src/app/page.test.tsx`.
- `frontend/jest.config.ts`, `frontend/jest.setup.ts`, `frontend/scripts/smoke.mjs`, `.github/workflows/frontend.yml` and shared `.prettierrc`.
- Actual current code and tests on the base branch. FE-01 is the starting point; do not assume a subsequent homepage PR has merged.

### Primary change area

Frontend-only **visual foundation and shared application shell**: design tokens, self-hosted typography, reusable presentational primitives, accessible site header/footer, navigation behaviour, and responsive layout conventions. This is a foundation for subsequent homepage, checker, results and FAQ PRs—not their implementation.

### Canonical implementation examples

- `frontend/src/app/layout.tsx`: existing server root layout, `lang="en-GB"`, metadata and global CSS.
- `frontend/src/app/globals.css`: existing Tailwind CSS v4 entry point (`@import 'tailwindcss'`).
- `frontend/src/app/page.tsx`: existing deliberately limited public-page placeholder.
- `frontend/src/app/page.test.tsx`: existing React Testing Library test for the exact honest placeholder message.
- `frontend/scripts/smoke.mjs`: existing production SSR smoke contract (HTTP 200, title, description, a `<main>`, an `<h1>` and placeholder copy).
- There is **no** existing design-system component precedent; create one coherent convention rather than introduce multiple competing component libraries.

### Relevant symbols

`RootLayout`, `metadata`, `Home`, global CSS variables / Tailwind v4 theme tokens, React component props, Next.js `Link` for internal navigation, and the current Jest/RTL test and smoke contracts. Verify the actual implementation before changing imports or introducing browser-only behaviour.

### Expected change surface

Guidance, not an exact file mandate:

```text
frontend/src/app/globals.css
frontend/src/app/layout.tsx
frontend/src/app/page.tsx                       # minimal shell integration only
frontend/src/components/layout/SiteHeader.tsx
frontend/src/components/layout/SiteFooter.tsx
frontend/src/components/layout/SiteNavigation.tsx  # client component only if needed
frontend/src/components/ui/Button.tsx
frontend/src/components/ui/ButtonLink.tsx
frontend/src/components/ui/Card.tsx
frontend/src/components/ui/Badge.tsx
frontend/src/components/ui/Container.tsx
frontend/src/components/ui/SectionHeading.tsx
frontend/src/components/ui/AccordionItem.tsx    # native details/summary preferred
frontend/src/components/**/**/*.test.tsx        # colocated, focused tests
frontend/src/app/page.test.tsx                  # preserve and extend semantics
frontend/src/fonts/ or frontend/public/fonts/  # licensed, locally hosted font if used
frontend/README.md                              # document design and component usage
frontend/scripts/smoke.mjs                     # change only if a verified contract requires it
```

Prefer named imports through concrete files over an unnecessary, circular all-components barrel. Component splits may differ when justified by simpler code.

### Excluded areas

- Building the screenshot's full marketing homepage, FAQ page/content, benefits selector/tabs, interactive checker, result page, promotional carousel, real-time countdown, search flow or claim-document checklist.
- New `/check`, `/promotions`, `/faq`, account, policy or other routes solely to make header links appear functional.
- REST/MCP changes, manufacturer data, backend eligibility computations, data ingestion, email alerts, payments, manufacturer sign-in and authentication.
- Invented promotion statistics, source verification, “live” eligibility results, prices, payment methods or eligibility classifications.
- New UI framework, Storybook, visual regression service, global state manager, API client, analytics provider or animation dependency without a separately approved need.
- Refactoring FE-01 toolchain, CI or backend packages unrelated to the layout work.

### Unknowns Codex must verify

1. The latest `main` files and merged/open frontend PRs; whether a page/header/design-system file appeared since this specification was drafted.
2. Whether the approved BenefitScout logo or licensed font files are actually available in the repository. **None appeared in the inspected FE-01 tree.** Do not invent a replacement image or assume assets in the chat are mounted in the implementation environment.
3. Whether any usable navigation destinations currently exist beyond `/`. Only publish links whose destinations exist.
4. Whether the FE-01 production smoke and homepage placeholder assertions depend on exact metadata and copy; preserve them unless an intentional, justified update is covered in the same PR.
5. The simplest Tailwind v4-compatible way to expose tokens through global CSS (`@theme` / CSS variables) in the pinned toolchain; do not bring in a Tailwind v3 config pattern.
6. The font's actual redistribution licence, source and self-hosting/build compatibility. The build must succeed without a network font download.

---

## Objective

Deliver a coherent, reusable, accessible BenefitScout interface foundation that visually follows the five references **without shipping an incomplete or misleading homepage**.

After FE-02:

- Every public page can share an accessible site header, footer, skip link, stable content width and responsive spacing through the Next.js root layout.
- Feature PRs can use documented typography, palette, spacing, border, shadow and focus tokens instead of hardcoded, inconsistent values.
- Buttons, links, cards, badges, section headings, disclosure items and layout containers have small, typed interfaces, keyboard-friendly semantics and predictable responsive behaviour.
- The existing `/` placeholder still renders, still clearly says purchase checking is unavailable, and still passes the existing production smoke checks.
- Navigation never advertises unimplemented routes, and the UI does not claim to have checked a promotion.

**Definition of done:** the foundational shell and primitives are implemented, used in the real `/` route at least where relevant, tested for observable behaviour, reviewed at the required viewport widths, and all existing frontend CI commands pass.

---

## Architecture and invariants

- Keep `frontend/` a standalone **Next.js App Router** application, **not Vite**. Use the existing React, strict TypeScript and Tailwind CSS v4 setup.
- Keep `src/app/layout.tsx` as a Server Component. Render `<SiteHeader />`, a skip link, `{children}` and `<SiteFooter />` there. A page owns its **single** `<main id="main-content">` and its page-specific `<h1>`; do not create nested or duplicate `<main>` landmarks in the shell.
- Most primitives should be Server Component-compatible, semantic and dependency-free. Put `'use client'` only on truly interactive boundaries (the mobile navigation disclosure if required); do not convert the entire layout or page into a client component.
- Prefer styling native HTML elements to recreating their accessibility behaviour. Use a real `<button>` for actions, a real link for navigation, and `<details><summary>` for basic disclosure.
- Centralise tokens. Components must not scatter hardcoded hex values and arbitrary one-off spacing/box-shadow rules.
- No layout primitive owns business state. In particular, `Badge` is a visual primitive—not an eligibility classifier; claim status comes later from backend data and explicit frontend mapping.
- Maintain the backend's deterministic eligibility boundary. These components do not call APIs, interpret promotions or fabricate claim windows.
- Avoid nonfunctional affordances: no dead links, disabled-looking active navigation, fake form submission or persuasive promises about capabilities not yet launched.

### Design reference and visual language

Treat the uploaded images as stylistic examples, identified by their original filenames:

| Attachment | Design cues to implement in FE-02 | Leave for a later feature PR |
| --- | --- | --- |
| `Screenshot 2026-10-16 at 15.06.09(1).png` | Warm page background; confident dark headings; violet eyebrows; dominant amber feature card; pill labels; subtle outlined white cards; compact dark CTA buttons. | Full hero, “60 seconds” promise, £150 reward, dates, “LIVE” result, deadline or any campaign fact. |
| `Screenshot 2026-10-16 at 15.06.14(1).png` | Clear section-heading hierarchy, three-card responsive grid pattern, icon-tile treatment, soft shadows and fine dividers. | “260+ campaigns”, “1,800+ SKUs”, definitive result promise and complete content section. |
| `Screenshot 2026-10-16 at 15.06.21(1).png` | Contrasting dark navy section surface, elevated navy panel, indigo/violet interactive accent, strong white text. | Benefits tabbed selector, trade-in logic, cashback ranges or manufacturer-authorisation badges. |
| `Screenshot 2026-10-16 at 15.06.38(1).png` | Editorial two-column desktop composition, comfortable text measure, generous whitespace, aligned CTA. | Photography, page narrative, “68%” statistic, product count or payment policy assertions. |
| `Screenshot 2026-10-16 at 15.06.43(1).png` | Rounded white FAQ disclosure cards, thin borders, high-contrast headings, restrained purple active indication. | Full FAQ route, FAQ copy and unsupported manufacturer claims. |

**Visual character:** premium but approachable UK consumer product. It should feel precise and trustworthy, **not** like a financial dashboard. Use generous whitespace, clean alignment, strong typographic hierarchy, calm UI chrome and a limited number of meaningful accent colours. The purchase-checker will be the later homepage's focal interaction—not a decorative illustration.

**Reference fidelity:** implement the shared design language rather than pixel-copying desktop screenshots. The source images include large desktop compositions but no validated mobile or navigation design; use the responsive and accessibility requirements below as the authority there.

### Design tokens

The following values are **starting design tokens sampled or inferred from the supplied references**, not claims about an existing production design system. Fine-tune within the same palette only when a contrast measurement or implementation test demonstrates a need; document any material deviation.

| Purpose | Proposed token | Value / constraint |
| --- | --- | --- |
| Warm application background | `--color-page` | `#FAF9F6` |
| Default card | `--color-surface` | `#FFFFFF` |
| Subtle inset / neutral panel | `--color-surface-muted` | `#F7F8FA` |
| Primary text | `--color-ink` | `#10182F` |
| Secondary body text | `--color-ink-muted` | `#536581` |
| Deep navy section | `--color-navy` | `#0B1329` |
| Dark elevated panel | `--color-navy-panel` | `#1C274E` |
| Primary violet accent | `--color-brand` | `#5046E6` |
| Amber feature highlight | `--color-highlight` | `#ECB73E` |
| Positive text on pale surface | `--color-success` | `#007A52` (chosen dark enough for normal-text contrast) |
| Positive tint | `--color-success-subtle` | `#ECFDF5` |
| Default border | `--color-border` | `#DEE6F0` |
| White on dark/brand | `--color-on-dark` | `#FFFFFF` |

- Implement semantic **CSS custom properties** in `globals.css`, exposing Tailwind v4-compatible utility tokens with `@theme`/`@theme inline` as appropriate. Semantic names are mandatory; avoid feature-specific token names such as `--samsung-reward-green`.
- Do not rely on colour alone to communicate a result: badges include text and future result components must include reason/context.
- Verify **WCAG 2.2 AA** normal text contrast **≥ 4.5:1**, large text / necessary graphical objects **≥ 3:1**, and visible keyboard focus. Do not put small white text on the amber surface; use dark navy on amber. Green-on-pale uses the darker `#007A52` foreground rather than the brighter green in the reference.
- Limit purple to calls to action, interactive states, eyebrows and small emphasis. Limit amber to high-salience feature surfaces and occasional highlights, not every control.
- Define consistent spacing based on a 4px or 8px rhythm. Representative values: `4, 8, 12, 16, 24, 32, 48, 64, 96px`; prefer semantic utilities over individually invented values.
- Representative corner radii: 12px small control, 16px pill/card interior, 24–32px feature cards; full pill for badges. Borders should be subtle; shadows should be low-elevation and unobtrusive. Avoid heavy neumorphism.
- Responsive content max-width: approximately **1200–1280px**, with optional narrower prose measure of **65–75 characters**. Horizontal gutters: **16px mobile**, **24–32px tablet**, **40px or more desktop** where space permits.
- Support light mode as the shipped baseline. **Do not accidentally inherit an OS-driven dark mode** without designed equivalent tokens. The intentionally navy benefits surface is a component/section theme, not a whole-site automatic dark theme.

### Typography

- Use one cohesive sans-serif family resembling the references: **Inter** as the proposed primary font, with system-ui fallback. If adopted, self-host a legally redistributable variable WOFF2 asset (with licence information) through `next/font/local` or equivalent; **do not use build-time remote font fetches, CDN stylesheets, or private font binaries**. If the approved file cannot be obtained, document and ship a deliberate system-font fallback pending a separate approved font change.
- Use a compact type scale, defined through reusable classes/tokens rather than per-page magic numbers. Representative desktop sizes: display `clamp(2.5rem, 4vw, 3.5rem)`; section title `clamp(2rem, 3vw, 3rem)`; card title `1.25–1.5rem`; body `1rem–1.125rem`; eyebrow / small metadata `0.8125–0.875rem`.
- Keep headlines tightly but legibly tracked (`-0.02em` to `-0.035em`) with line-height about `1.1–1.2`; body line-height about `1.5–1.65`. Do not use all-caps body paragraphs. Eyebrows may be uppercase with increased tracking.
- Respect semantic heading levels. The **page** provides exactly one `<h1>`; section heading component must support explicit `<h2>` or `<h3>` as appropriate rather than blindly inserting an `<h1>`.
- At **200% text zoom**, long labels must wrap and remain readable. Never rely on fixed-height text containers or truncate essential copy.

### Reusable component contracts

Build only components that the screenshot language or application shell needs now. Keep each public prop surface small and explicitly typed.

| Component | Required contract and behaviour |
| --- | --- |
| `Container` | Constrains width, centres content, manages responsive inline gutters; optional narrow/wide variant. Should not force a semantic `<main>`. |
| `Button` | Real `<button>` with `variant: 'primary' \| 'secondary' \| 'ghost'`, size as needed, native disabled/`type`/ARIA props and visible focus. Default `type="button"` unless caller specifies otherwise. Disabled state must not look clickable. |
| `ButtonLink` | Separate link-styled-as-button component, uses Next `Link` for internal hrefs and native anchor for allowed external destinations; never uses `onClick` navigation on a button. Reuse Button variant styles without making DOM semantics ambiguous. |
| `Card` | Noninteractive surface container with `default`, `subtle` and optional `dark` treatment; no implicit click handler or misleading hover state. Supports native children and `className`. |
| `Badge` | Text-bearing pill with restrained `neutral`, `accent`, `success` (and only if actually needed, `warning`) appearances. Not hardwired to promotion data and not an eligibility decision. |
| `SectionHeading` | Optional uppercase eyebrow, semantic heading text, optional concise supporting copy, normal/centred alignment. Accept explicit level (`h2`/`h3`) and optional id for actual anchors. |
| `AccordionItem` | Reusable FAQ-like disclosure based on native `<details>` and `<summary>`, with a visible state icon and no JavaScript dependency unless justified. Keyboard and screen reader usable in both states; support long copy and constrained widths. |

Include a simple **reusable icon treatment** (inline decorative SVG with `aria-hidden="true"` or an accessible text-bearing equivalent) where components need it. Do not add a general-purpose icon abstraction or a large icon package for one arrow/chevron.

**Styling conventions:** prefer shared variant maps/utilities that are simple to read; don't introduce a generic class-name-merging framework for a handful of components unless a real Tailwind override conflict requires it. Do not use arbitrary `dangerouslySetInnerHTML` for labels/FAQ text. Content remains caller-provided.

### Header, navigation, footer and shell

**Header**

- Consistent light/neutral header visually connected to the reference palette; constrained content aligned with `Container` and visually separated from the page when helpful.
- An accessible **BenefitScout** wordmark linking to `/`. If no approved logo file is present, use styled text; do not generate a speculative brand image.
- Support a typed optional navigation list. Populate it only with **implemented, reachable** paths or existing on-page anchors. At FE-02 baseline, the brand/home link may be the only available destination; do not add fake `/check`, `/promotions`, `/faq`, sign-in or legal links.
- No permanently visible “Check now” CTA until the associated action actually works. Future homepage work may inject a real primary CTA without modifying the component's architecture.
- At desktop widths display present nav items inline. At mobile widths, if more than the brand link is actually configured, use a keyboard-operated menu/disclosure that sets `aria-expanded`, has a correct `aria-controls` target, exposes items only when open, closes on an item activation and Escape, and restores appropriate focus. A disclosure is **not** a modal: do not fake a focus trap; avoid background-scroll manipulation unless the interaction genuinely requires it.
- Ensure a responsive header does not overlap content, lose the brand, create an inaccessible off-canvas menu or introduce sideways scrolling.

**Shell and page landmark**

- Render a visible-on-focus **“Skip to main content”** link before the header. It must target the actual `<main id="main-content">` on every public page.
- Use a flex/column or grid min-height page wrapper so short pages have the footer at the bottom without `position: fixed`; avoid sticky/fixed UI obscuring focus targets.
- Keep per-page `<main>`/`<h1>` ownership as stated above. `RootLayout` should not duplicate the existing home page's main landmark.
- Maintain `<html lang="en-GB">` and existing title/description metadata unless a later homepage copy change is explicitly in scope.

**Footer**

- Consistent neutral footer: BenefitScout wordmark, short accurate service description, copyright/year rendered without stale hardcoded dates, and optional working links passed as data.
- Include a concise, non-alarming **independence/authority disclaimer** such as “Promotion eligibility and claims are determined by the manufacturer; always check the official terms.” Do not assert that manufacturer status is verified or that every promotion has an official claim link.
- Do **not** render dummy Privacy/Terms, social, account or regulatory links if pages do not exist. Structure should make adding approved legal/navigation links later easy.
- Footer contrast, wrapping, tap targets and responsive reflow must meet the same accessibility requirements as the header.

### Responsive and interaction behaviour

- Mobile-first layout; minimum supported width **320px**, with deliberate checks at **360/375px**, **768px**, **1024px**, **1280/1440px** and **200% zoom**.
- Page shell and cards must not overflow horizontally or require horizontal scrolling at those widths, excluding intentionally scrollable future specialised components.
- Card groups should compose as **one column mobile**, two columns when width/content allows, and up to three columns desktop. Do **not** force a three-column grid at tablet widths simply because the reference has three desktop cards.
- Editorial two-column layouts should stack with text and media in logical reading order on narrow screens. FE-02 supplies grid/spacing patterns, not the specific editorial section.
- Use `prefers-reduced-motion` to minimise transitions. Hover is supplemental, never the only state cue; keyboard `:focus-visible` is obvious on light and dark surfaces.
- Interactive targets should generally be at least **44 × 44 CSS px**. Respect text wrapping and safe-area padding where appropriate.
- Prefer simple CSS layout; avoid layout calculations requiring JavaScript or viewport-dependent server rendering that can cause hydration mismatches.

---

## API and contract changes

**No REST, MCP or backend contracts change.** FE-02 introduces only **internal TypeScript presentational component prop contracts** described above. Their props should use native HTML attribute types where appropriate.

- No new request/response schemas, fetches, HTTP handlers, authentication flows or app-state persistence.
- No eligibility engine or source-provenance data is evaluated by the UI.
- Future links to manufacturer sites must be sourced from verified backend results, not arbitrary static demo URLs. There are no such external claim links in this PR.
- All new components should export predictable, documented interfaces; avoid exporting APIs that imply unsupported business functionality.

---

## Domain and application behaviour

FE-02 is a presentation concern; its only application behaviour is compositional and navigational:

1. The server renders the site shell, skip link, site identity, page main content and footer consistently.
2. `Button` performs only the native action passed by its caller; `ButtonLink` navigates to a real destination; neither silently submits a form.
3. Optional mobile navigation opens and closes based on user interaction, with accurate ARIA state and no hidden keyboard-reachable links.
4. Disclosure content in `AccordionItem` is operable without pointer input; use native semantics.
5. The existing home route remains a truthful coming-soon foundation page. It must not show **“eligible”**, **“verified”**, **“live”**, cashback amounts, deadline countdowns, campaign counts or other unsubstantiated claims copied from the references.
6. Future business data such as `ELIGIBLE`, `POTENTIALLY_ELIGIBLE`, `NOT_ELIGIBLE`, `CLAIM_NOT_YET_OPEN` and `EXPIRED` is explicitly **out of scope**; FE-02 badge appearances are not a mapping for those domain values.

### Eligibility-specific rules

**N/A.** No purchase information is accepted and no runtime eligibility calculation or result classification is performed.

### Ingestion/publication rules

**N/A.** No promotion ingestion, publication, source verification or history change.

---

## Persistence, transactions, and migrations

**None.** No backend migration, local storage, cookie, database table or persisted client state. Mobile nav/disclosure state, if implemented, is ephemeral in the browser.

---

## External services and network access

**None required.** No API integrations, analytics, remote image API, font CDN or manufacturer request. Build-time and test-time font loading must not require network access. Any font source used to prepare locally bundled assets must be legal to redistribute and documented in the codebase.

---

## Security and privacy

- Do not handle purchase details, receipts, serial numbers, personal information, account data or authentication tokens in this PR.
- New components render textual children safely as React content; no HTML injection escape hatches.
- External links, when later introduced, must have explicit destinations and safe `rel="noopener noreferrer"` when using `target="_blank"`; do not fabricate links in the design shell.
- SVG icons must be local, inert and accessibility-labelled appropriately; no remote scripts or inline executable code.
- Accessibility and honest messaging are product-safety requirements: visually attractive example data must **not** be rendered as an actual customer's financial entitlement.

---

## Configuration and deployment

### Environment variables

**None added or changed.** Do not add `NEXT_PUBLIC_*` flags, API URLs or secrets to support a static design system.

### Runtime/deployment changes

- Preserve Node **24.22.0**, pnpm **10.34.7**, Next.js **16.4.2**, React **19.3.1**, Tailwind **4.3.3** and existing frontend scripts unless current main intentionally differs.
- Keep the existing frontend GitHub Actions workflow and frozen lockfile policy. If bundling a licensed local font, include required font files and licences in the frontend source tree; verify they work in an offline production build.
- No new Docker service, hosting resources, runtime process, new route handler or backend startup dependency.
- A small font dependency/asset change is permissible only if justified and documented; keep the total client JS and CSS impact modest.

---

## Observability and operations

- Keep `/` available with existing metadata, SSR HTML and production smoke contract; no metrics provider or analytics installation.
- CSS or client-component errors should not prevent the server-rendered main content, header or footer from appearing.
- No user tracking, PII logging or custom telemetry is appropriate for this foundation PR.
- Browser console should have no React hydration mismatch, missing-key or accessibility-related warnings during ordinary navigation/disclosure interaction.

---

## Failure, consistency, and recovery

- **Missing approved logo:** render an accessible text-only brand mark; do not leave a broken image.
- **Font unavailable or licensing unclear:** ship documented system-font fallback and raise a scoped design-fidelity deviation; do not add a remote font dependency or silently commit unlicensed assets.
- **No extra routes exist:** hide nonfunctional navigation entries and primary CTA; do not link to 404s or placeholder `#` anchors.
- **JavaScript disabled or delayed:** server-rendered shell, content, links and native FAQ disclosure remain usable; if mobile menu navigation is interactive, preserve a usable fallback for any published destinations or document/test a no-JS approach.
- **Long strings, narrow screen or text zoom:** allow wrapping and vertical expansion; do not hide or clip critical actions/labels.
- **Reduced-motion or keyboard use:** controls are distinguishable without animation/hover and focus is visible.
- **Theme overrides:** do not apply an accidental dark-mode background that breaks light-surface component contrast.

---

## Acceptance criteria

### Behaviour

- [ ] The public `/` route displays a consistent shell: skip link, BenefitScout header, one `<main id="main-content">`, one page `<h1>` and footer.
- [ ] Existing homepage placeholder remains explicit that purchase checking is not available, with no fictional promotions or eligibility results.
- [ ] Brand link navigates to `/`; any additional visible navigation links resolve to actual implemented destinations.
- [ ] Desktop navigation layout and mobile disclosure work for injected real links; hamburger/toggle is not rendered pointlessly when there are no additional destinations.
- [ ] Mobile disclosure correctly reports and changes `aria-expanded`, closes on Escape and selection, and does not leave closed links in the keyboard tab order.
- [ ] `Button` uses native button semantics/type; `ButtonLink` uses link semantics; disabled controls are not actionable; card surfaces are not falsely interactive.
- [ ] `AccordionItem` opens/closes with mouse, Enter and Space and has meaningful summary/content relationships without duplicating content.
- [ ] Components accept real content and long text, not baked-in Samsung, LG or illustrative promotional facts.

### Visual design and responsiveness

- [ ] Design tokens are centralised and visibly reflect the warm neutral, navy, violet, amber and white-card language of all five references.
- [ ] Typography is consistent and has intentional heading/body scales; a local/licensed font or explicitly documented fallback builds offline.
- [ ] Container, section, card, button and badge styles are coherent on both light and intentionally dark surfaces.
- [ ] Mobile (**320/360/375**), tablet (**768**), desktop (**1024/1280/1440**) and **200% zoom** views show no unintended horizontal scrolling, overlapping navigation or clipped content.
- [ ] Future three-card layouts can collapse to 1/2/3 columns without forcing desktop proportions on phones.
- [ ] Focus states remain visible on violet, amber, navy and white surfaces; reduced-motion preference is honoured.

### Data and consistency

- [ ] No database, persisted state, runtime promotion data or business-rule semantics are added or changed.
- [ ] UI appearance and status badges cannot by themselves imply an authoritative eligibility determination.
- [ ] No unverified counts, dates, cashback amounts or live result labels from screenshots are installed as production content.

### Security and accessibility

- [ ] Landmark/heading hierarchy is valid; skip link targets main correctly; no duplicate `<main>`/page `<h1>`.
- [ ] Interactive components use semantic elements, accessible names, keyboard operation and target sizes appropriate for touch.
- [ ] Normal text meets **4.5:1** contrast and large text/essential non-text UI meets **3:1** in all shipped variants; check the actual implementation, not only the example palette.
- [ ] Text at 200% zoom and narrow viewports remains readable; no essential information is conveyed only by colour or motion.
- [ ] No unsafe HTML insertion, secrets, PII collection, bogus official links or unexpected remote requests.

### Operations

- [ ] Existing `pnpm build` and `pnpm smoke` run successfully with the actual resulting server-rendered page.
- [ ] No hydration warnings or missing asset requests in a normal browser session.
- [ ] No new environment variables or external services are required.

### Code quality

- [ ] Next.js server/client boundaries remain minimal; only genuinely interactive navigation needs a client boundary.
- [ ] Tailwind CSS v4 tokens are implemented according to the pinned version, not with v3-only configuration.
- [ ] Component props are typed and ergonomically minimal; tests verify **behaviour**, not snapshots of classes or incidental internal implementation.
- [ ] Shared styles are reused in the shell and placeholder; unused speculative abstractions or dependencies are not introduced.
- [ ] Formatting, lint, typecheck, focused tests, full frontend suite, production build and smoke pass.

---

## Tests to add or update

Prefer colocated RTL tests under `frontend/src/components/` and an update to the existing page test. File names below are examples of the expected test coverage, not a requirement to create one redundant file per component.

### Unit tests

1. **Header / link semantics:** brand link has name and `/` href; no dead links when optional navigation is empty; real supplied items appear with correct destinations.
2. **Mobile navigation:** with real injected items, a disclosure reports closed/open state, toggles with keyboard, closes on Escape and selection, and hides links from keyboard navigation when closed. Test relevant focus restoration rather than brittle implementation-specific DOM structure.
3. **Button / ButtonLink:** native types, variants, `disabled`, event handling, labels, internal href, keyboard semantics; no unwanted form submission from a default `Button`.
4. **AccordionItem:** native disclosure state, Enter/Space activation, visible answer when expanded, appropriate summary semantics and noninteraction of hidden answer when collapsed.
5. **Container / SectionHeading / Card / Badge:** meaningful semantic output (correct heading level and text, no implicit button/card click, badge includes textual label). Avoid tests that merely assert a CSS class string.
6. **Page integration:** exactly one `main`, exactly one `h1`, skip target, header/footer landmarks, existing placeholder copy, no fake live results.
7. **Accessibility regression:** if an existing accessible audit helper is available, use it for representative primitives; otherwise rely on semantic RTL tests and document a browser accessibility review. Do not add a heavy test stack solely to raise a passing test count.

### PostgreSQL integration tests

**N/A.** No backend or data changes.

### API/application tests

**Frontend page integration only.** Use the current Jest/RTL setup for `RootLayout`/page composition where practical; preserve or deliberately update `frontend/src/app/page.test.tsx` and the SSR assertions in `scripts/smoke.mjs` without weakening their intent.

### MCP contract tests

**N/A.** No tool or transport changes.

### External-boundary tests

**N/A.** No external services. Confirm no font/CDN/network dependency is introduced. Manual browser verification must cover the specified viewport, zoom, keyboard, reduced-motion and focus cases; attach screenshots or a concise checklist to the implementation PR when possible.

---

## Verification commands

Run the actual commands shipped by FE-01 from `frontend/` and retain meaningful output in the implementation summary:

```bash
# Select the pinned Node 24.22.0 and pnpm 10.34.7 first.
cd frontend
pnpm install --frozen-lockfile

# Style and static checks
pnpm format:check
pnpm lint
pnpm typecheck

# Focused component/page tests (use existing Jest via pnpm)
pnpm exec jest --ci --runInBand src/components src/app/page.test.tsx

# Complete existing frontend suite and production checks
pnpm test
pnpm build
pnpm smoke
```

If targeted Jest matching does not apply to the created test tree, use appropriate actual file paths; do not silently skip the coverage. Run a real browser visual/keyboard check at the sizes listed above because jsdom cannot validate layout overflow, focus visibility or responsive reflow.

**No** PostgreSQL, Alembic, backend pytest, REST or MCP test commands are required because their files and contracts are unchanged.

If a verification command cannot run, report its exact invocation, why, alternative evidence collected and the remaining risk. Do not describe a manual visual inspection as an automated visual regression test.

---

## Completion report

When FE-02 implementation is complete, report:

### Changed

- Actual design tokens/typography, shell and components implemented.
- Which reference patterns are supported and which are intentionally deferred.

### Database and migrations

`None` expected.

### API/MCP contracts

`None` expected; list any internal component prop interfaces worth documenting.

### Tests and verification

- Test files and meaningful behaviours covered.
- Exact formatting, lint, type, test, build and smoke commands **actually run** with pass/fail results.
- Viewports and accessibility interactions **actually checked** in a browser.

### External configuration

`None` expected; identify any locally bundled font asset/licence if introduced.

### Deviations

- State `None` or explain approved changes from this spec, especially font fallback, token adjustments or new dependencies.

### Remaining risks or follow-up

- Explicitly list deferred homepage, checker, FAQ, benefit selector, real eligibility/status mapping, real links and authoritative manufacturer-promotion data. Do not imply those features shipped with FE-02.

---

## Scope guardrail for reviewers

**Approve FE-02 on the quality of its visual foundation and app shell, not its resemblance to a complete homepage.** The attached screenshots are attractive but contain statements that require independent business evidence (for example, £340m unclaimed, 68% missed claims, 260+ campaigns, 1,400+/1,800+ SKUs, an active Samsung reward and “22 days left”). Those statements are **not acceptance criteria, seeded test data, design tokens, or authorised marketing copy** in this PR. Implementing any of them as a live consumer claim requires a later data-backed feature and content review.
