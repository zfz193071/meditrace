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

## Browser verification without a local server

With a dedicated headless Chrome already running on an isolated DevTools port:

```sh
node scripts/portfolio_browser_qa.cjs artifacts/portfolio/build-EXAMPLE/site 9468
```

The script opens a background tab and fulfills its requests from the actual exported files at a synthetic HTTPS origin. Unexpected requests are blocked. It checks responsive layouts at 1440, 1024 and 390px; uses Tab/Enter and native input events for the three-case review flow; inspects exported Blob text and print HTML; and checks client navigation. Screenshots and `audit.json` are saved beside the artifact under `browser-qa`. Failure diagnostics go to `failure.json`.

This does not start a Next/FastAPI service, call AI, use another session's browser profile, or test a public TLS connection. Copy may use the documented download fallback if clipboard access is unavailable. Print verification does not open the operating system print dialog. The script closes only its own tab; the operator manages the dedicated Chrome process.

## Verification — 2026-10-27

- `pnpm --dir src/frontend build:portfolio`: passed, including TypeScript and exported route/link/asset checks. Local artifact: `artifacts/portfolio/build-r51fs01c/site` (ignored build output).
- `NEXT_PUBLIC_PORTFOLIO_ONLY=true pnpm --dir src/frontend test --runInBand __tests__/components/DemoWorkspace.test.tsx`: 4/4 passed. Covers identity evidence, decisions, confirmed handoff, copying, reset, prepared-revision recovery and the complete case; each test asserts no fetch calls or browser-storage writes.
- `pnpm --dir src/frontend lint`: passed with two existing unused-variable warnings in legacy files.
- No server startup, browser AI action, real model call or deployment. Public HTTPS acceptance remains pending; the subsequent local browser checks are recorded below.

## Core-flow acceptance — 2026-10-27

The actual static artifact `build-ytay_jnk` passed the browser script in Chrome 156 after the [keyboard-focus fix](../../BUGFIX-DEMO-KEYBOARD-FOCUS.md). [Machine-readable audit](evidence/mvp-2026-10-27/audit.json), [mobile evidence panel](evidence/mvp-2026-10-27/mobile-evidence.png), [mobile confirmed handoff](evidence/mvp-2026-10-27/mobile-confirmed.png).

- Three viewport widths passed horizontal-overflow checks. All four public pages were also checked at 390px; evidence and confirmed-handoff screenshots were visually inspected.
- Keyboard-only interaction passed all three cases, source-revision invalidation, decisions, confirmation, copy/download/print controls, reset and refresh. Text and print HTML retain the identity warning; the clean case and prepared revision can be confirmed.
- Homepage → demo → architecture client navigation passed. All 93 page resource requests were served locally, with no unexpected/private/backend requests or runtime exceptions. Browser storage remained empty after the flow.
- Related component tests: 19 passed. Static build/TypeScript/link checks and targeted lint passed. The preceding `e6689f3` [CI run](https://github.com/zfz193071/meditrace/actions/runs/40459418342) completed successfully in both jobs; this link is evidence for that preceding commit, not the new focus fix.

This completes local core-flow checks for the MVP. Public HTTPS deployment and smoke verification, final recruiting links/copy, and video review remain. Full V1 and external-user acceptance are not implied.
