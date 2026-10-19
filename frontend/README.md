# BenefitScout frontend

A standalone Next.js App Router application with React, strict TypeScript and Tailwind CSS v4.
The public `/` route is a temporary application foundation. Purchase checking is not available yet.

## Prerequisites and setup

Use Node.js **24.22.0** (Node 24 LTS, also pinned in `.node-version`) and **pnpm 10.34.7**.
Select that Node version with your version manager, then install the pinned package manager:

```bash
npm install --global pnpm@10.34.7
node --version
pnpm --version
cd frontend
pnpm install --frozen-lockfile
pnpm dev
```

Open <http://localhost:3000>. No backend, environment variables, secrets, database or remote fonts
are required. The `engines` declaration and `.npmrc` reject incompatible toolchain versions.

## Commands

Run from `frontend/`:

| Command             | Purpose                                                                                  |
| ------------------- | ---------------------------------------------------------------------------------------- |
| `pnpm dev`          | Next.js development server                                                               |
| `pnpm format:check` | Check frontend and frontend workflow formatting with the root `.prettierrc`              |
| `pnpm format`       | Format that same file set                                                                |
| `pnpm lint`         | Next.js and TypeScript ESLint checks, no warnings allowed                                |
| `pnpm typecheck`    | Generate route types, then run strict TypeScript checks                                  |
| `pnpm test`         | Offline Jest and React Testing Library tests, once in CI mode                            |
| `pnpm test:watch`   | Interactive Jest watch mode                                                              |
| `pnpm build`        | Compile the production app and Tailwind styles                                           |
| `pnpm start`        | Serve the production build on port 3000                                                  |
| `pnpm smoke`        | Start the production build on loopback port 3100, poll `/`, verify HTML, stop the server |

Production verification:

```bash
pnpm build
pnpm smoke
# Or serve the build interactively:
pnpm start
```

The smoke command requires port 3100 to be free. It checks HTTP 200, the main landmark, heading,
language and metadata, and reports server logs on failure. It bounds readiness and terminates its
server even when assertions fail. To check presentation, open the production app at mobile and
desktop widths: the heading should be large and semibold, with a padded, centred content column
and no horizontal overflow. Component tests cover the accessible heading and honest placeholder copy.

## Layout and boundaries

- `src/app/layout.tsx`: server root layout, English language, metadata and global CSS.
- `src/app/page.tsx`: synchronous Server Component for `/`, with colocated `page.test.tsx`.
- `src/app/globals.css`: Tailwind v4 import and system font foundation.
- `scripts/smoke.mjs`: production HTTP verification used locally and by frontend CI.
- Configuration files at this directory's root: TypeScript, ESLint, Jest and PostCSS.

The frontend workflow independently checks frozen installation, formatting, lint, types, tests,
production build and HTTP smoke. Generated Next.js types/output, coverage, dependencies and local
environment files are ignored; the single committed pnpm lockfile controls dependency resolution.
Prettier discovers the shared repository configuration and excludes generated files using the local
`.prettierignore`.

Future integration must deliberately consume the existing backend
`POST /api/v1/eligibility/check` REST contract. The backend owns deterministic eligibility using
published promotion data. This app currently performs no API calls and adds no handlers, auth,
persistence or eligibility logic. Any future `NEXT_PUBLIC_*` values are included in browser bundles
and must never contain secrets.

Real homepage UX, the purchase checker, backend integration, authentication and hosting belong to
later frontend changes.

## Interface foundation (FE-02)

`RootLayout` owns the header, footer and skip link. Each public page must own exactly one
`<main id="main-content" tabIndex={-1}>` and one `h1`. The header intentionally publishes only the
home wordmark today. `SiteHeader` accepts a typed `navigation` list; supply only implemented
paths or existing anchors. With items configured, desktop links and a native mobile `details`
disclosure are provided. Its small client boundary adds Escape/focus restoration and closes on
selection; native disclosure and links remain usable without JavaScript.

The system font stack is deliberate: no approved local Inter asset or redistribution licence was
available. No font network request or build download is introduced. The wordmark is styled text
pending an approved logo. The palette follows the reference warm page, white cards, navy, violet
and amber. The success foreground uses the specified darker green. No campaign content from the
references is shipped.

`src/app/globals.css` exposes semantic Tailwind v4 `@theme` tokens for colours, typography,
spacing, radii and shadows. Use utilities directly in JSX: `text-display` / `text-section` with
`font-bold leading-[1.15] tracking-tight`, `text-body text-ink-muted`, and
`text-small font-bold tracking-widest text-brand uppercase`. Ordinary component appearance uses
small typed variant maps and utilities, including responsive `md:` / `lg:` variants.
For example, compose cards with `grid gap-6 md:grid-cols-2 lg:grid-cols-3`, editorial sections
with `grid items-center gap-8 md:grid-cols-2`, and section spacing with `py-16 lg:py-24`.
Use `bg-navy text-on-dark` or `bg-highlight text-ink` for contrasting sections and explicitly
choose readable descendant text colours. Put dark text on amber; badges do not decide eligibility.
Decorative icon tiles can use `inline-grid place-items-center rounded-control bg-surface-muted
p-3 text-brand`.

The shell body is a flex column with `min-h-svh`. Every public page's main must be a **direct
child of body**: the global `body > main { flex: 1 }` convention gives all short pages footer
space automatically. Pages own their main and H1; do not wrap main in a route-level div.
Long content expands naturally and the footer stays in document flow.

Retained global CSS exceptions are the explicit light colour scheme, direct-child main growth,
universal focus ring with white separation, heading/paragraph wrapping, tap highlight reset,
Safari's native disclosure marker selector, and the reduced-motion preference reset. These are
cross-component/browser conventions rather than a parallel component stylesheet.

Import primitives directly from `src/components/ui/`:

- `Container`: `width="wide"` (default) or `"narrow"`, native div props; no landmark ownership.
- `Button`: native button props, default `type="button"`, `primary` (navy), `secondary` (violet)
  or `ghost` (outlined) variant. Native `disabled` prevents action.
- `ButtonLink`: the same variants, internal paths/anchors via Next Link, HTTP(S) external anchors,
  safe new-tab relationship attributes. Labels remain caller-provided.
- `Card`: `default`, `subtle` or `dark` div surface, children and native div props; no built-in action.
- `Badge`: `neutral`, `accent` or `success` text-bearing span; caller supplies its meaning.
- `SectionHeading`: explicit `level="h2"` or `"h3"`, optional `id`, `eyebrow`, `description`,
  `align="normal"` or `"center"`; heading text as children. Use `tone="dark"` on standalone
  `bg-navy` or `bg-navy-panel` sections for amber eyebrows and white headings/supporting copy.
  The default `tone="light"` preserves light-surface colours and automatically adapts inside
  `Card variant="dark"`; a dark card does not require an explicit tone.
- `AccordionItem`: native details/summary, `title`, children, optional `open` and `className`.
  Native Enter/Space behaviour is preserved, with a decorative chevron that indicates open state.

For example, future sections can compose `SectionHeading`, a `grid gap-6 md:grid-cols-2 lg:grid-cols-3` div, and three `Card`
children inside a `Container`. The real homepage, checker, FAQ, benefit selector, eligibility
mapping, manufacturer data and additional navigation destinations remain separate feature work.

Contrast calculations for the shipped foreground/background pairs (WCAG relative luminance):
muted/page 5.62:1, muted/subtle 5.57:1, violet/subtle 5.88:1, white/violet 6.25:1,
green/pale-green 5.10:1, navy/amber 9.56:1, white/navy-panel 14.49:1 and amber/navy-panel
7.87:1. Borders are decorative; outlined controls use violet rather than the pale divider token.
`SiteFooter` accepts optional typed `links` and renders the current year plus the manufacturer
eligibility/claims disclaimer.

## Production browser acceptance tests

Install the Chromium version selected by the Playwright lockfile, build once, then run the suite:

```bash
pnpm install --frozen-lockfile
pnpm exec playwright install chromium
pnpm build
pnpm test:e2e
```

Ubuntu CI uses `pnpm exec playwright install --with-deps chromium` to install system libraries too.
`pnpm test` remains Jest only. Browser specs use `e2e/*.e2e.ts`; Playwright starts one production
Next.js server on loopback port **3101**, which must be free. The HTTP smoke server uses 3100.
The Chromium suite has two workers, one retry in CI and none locally. Failures save screenshots
and first-retry traces in `test-results/`; `playwright-report/` contains the HTML report. Both are
ignored by Git and uploaded by frontend CI on failure. Open a local report with
`pnpm exec playwright show-report`.

The suite checks the actual `/` shell, truthful development copy, semantic landmarks, working home
navigation, keyboard skip navigation and visible focus, footer flow, local asset loading and
browser runtime errors. It measures document and critical text bounds at 320, 360, 375, 768, 1024,
1280 and 1440 CSS pixels. Separate 640/320 CSS-width cases with 200% root text size stress wrapping;
these are **reflow and text-size proxies, not native browser zoom**. An axe scan uses its supported
WCAG 2.0/2.1/2.2 A/AA tags and fails on every returned violation. Axe does not certify all WCAG
criteria, and the root scan does not audit unrendered dark cards or dark section headings.

Outstanding manual checks are **native 200% browser zoom** and screen-reader inspection. The live
root has no navigation menu or footer links; live-browser menu interactions become applicable when
implemented destinations are supplied. Existing RTL tests cover injected menu Escape/focus behaviour and dark tone mappings. No test route or component harness is introduced.
Long-label stress remains outstanding manual shared-component coverage rather than a claim about the root.
Reduced-motion coverage confirms the current static shell has no active animations or transitions;
it does not exercise an animated component. Firefox and WebKit are possible future extensions.

## Eligibility API foundation

Set `BENEFITSCOUT_API_ORIGIN` on the **Next.js server runtime** when enabling live
checks (for example `http://127.0.0.1:8000` for a separately running local backend;
see the backend README for its PostgreSQL/configuration/startup prerequisites).
Production accepts only HTTPS origins. Local loopback HTTP origins are accepted
outside production for development. Credentials,
paths beyond `/`, query strings and fragments are rejected. No `NEXT_PUBLIC_*`
variable is used. Next.js server hosting is required; static export cannot serve
the bridge. Build and homepage rendering require no API configuration.

The browser sends `POST /api/eligibility/check`; the server forwards only to
`/api/v1/eligibility/check` on the configured origin, so browser CORS configuration
is unnecessary. A manual request against the frontend is:

```sh
curl -i http://localhost:3000/api/eligibility/check \
  -H 'Content-Type: application/json' \
  -d '{"brand":"Example","model":"SKU-1","retailer":"Shop","purchase_date":"2026-10-01","purchase_price":"799.99"}'
```

`checkPurchase` validates wire data, preserves decimal/date strings and distinguishes
resolved/no-match and unresolved identity successes. Callers handle `ApiError.kind`
for validation, rate limiting, availability, timeout, cancellation, server and
contract failures. Messages are safe generic copy; use the correlation request ID
for support. Missing/invalid configuration returns `503 api_not_configured`,
connection/invalid upstream replies return `502 upstream_unavailable`, and the
8 second upstream deadline returns `504 upstream_timeout`. The browser deadline
is 10 seconds. Request bodies are limited to 8192 bytes; responses to 1 MiB.
There are no automatic retries. Cookies/authorization are never forwarded.

The provider creates an isolated QueryClient with no focus/reconnect refetch,
no retries or persistence. `useCheckPurchaseMutation` runs only on explicit
mutation. Mutation data is transient (zero cache retention after it becomes
inactive); components should call `reset` when done. TanStack does not automatically
cancel mutations. Standalone `checkPurchase` accepts a caller AbortSignal.
The homepage remains a placeholder; checkout/results and accessible error UI are
future work. Backend REST/MCP and database contracts are unchanged.

`pnpm test:e2e` manages a deterministic upstream fixture on loopback port 3102 and
the production Next.js server on 3101, supplying the origin only at runtime.
Playwright terminates both processes, including on failure. The transport browser
test traverses the real route for resolved, unresolved, rate limited and broken
connection responses. Ordinary smoke checks use 3100 without an origin.
