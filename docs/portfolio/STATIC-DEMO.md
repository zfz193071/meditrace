# Standalone portfolio build

This implements the public-demo packaging step of the [current four-package MVP scope](../referral-review/README.md). It does not deploy the full V1 application.

From the repository root, after installing the locked frontend dependencies:

```sh
pnpm --dir src/frontend build:portfolio
```

The command prints a new `artifacts/portfolio/build-*/site` directory and writes a sibling `verification.json`. Only publish the `site` directory to an independent static host at its domain root, with directory index support and HTTPS. Browser evidence verification uses Web Crypto, which requires a secure context. This artifact needs no Node server, API, database, account, payment configuration or model key.

The build stages an explicit allowlist of routes: `/`, `/demo/`, `/project/`, `/evaluation/`, plus Next's error page. It copies no `.env` or root deployment configuration, clears service environment variables, and replaces workspace navigation with architecture links. Shared review components and existing synthetic fixtures are reused. The full application's build and routes remain available separately.

Verification checks the exported HTML route allowlist and every root-relative HTML link/script/style reference. CI builds and verifies the same artifact. This is build evidence, not browser interaction or public deployment evidence. Shared frontend API helpers can exist in bundles; the demo supplies its local transport rather than a live backend.

Remaining MVP acceptance: independently publish this artifact, verify the actual HTTPS URL and missing private/API paths, walk through the three cases (evidence, decisions, confirmation, export, reset), check keyboard and narrow-screen use, and finalize the README/Discord/video links. Do not publish through the root full-service deployment config or replace the existing production service with this artifact.

## Verification — 2026-10-27

- `pnpm --dir src/frontend build:portfolio`: passed, including TypeScript and exported route/link/asset checks. Local artifact: `artifacts/portfolio/build-r51fs01c/site` (ignored build output).
- `NEXT_PUBLIC_PORTFOLIO_ONLY=true pnpm --dir src/frontend test --runInBand __tests__/components/DemoWorkspace.test.tsx`: 4/4 passed. Covers identity evidence, decisions, confirmed handoff, copying, reset, prepared-revision recovery and the complete case; each test asserts no fetch calls or browser-storage writes.
- `pnpm --dir src/frontend lint`: passed with two existing unused-variable warnings in legacy files.
- No server startup, browser AI action, real model call or deployment. Public HTTPS, responsive layout and keyboard acceptance remain pending.
