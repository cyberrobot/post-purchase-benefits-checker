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
