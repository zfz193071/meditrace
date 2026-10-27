# Standalone portfolio build

**Public demo:** [meditrace-portfolio-mvp.vercel.app/demo/](https://meditrace-portfolio-mvp.vercel.app/demo/). Published and verified 2026-10-27; [release record](#public-release--2026-10-27).

This implements the public-demo packaging step of the [current four-package MVP scope](../referral-review/README.md). It does not deploy the full V1 application.

From the repository root, after installing the locked frontend dependencies:

```sh
pnpm --dir src/frontend build:portfolio
```

The command prints a new `artifacts/portfolio/build-*/site` directory and writes a sibling `verification.json`. Only publish the `site` directory to an independent static host at its domain root, with directory index support and HTTPS. Browser evidence verification uses Web Crypto, which requires a secure context. This artifact needs no Node server, API, database, account, payment configuration or model key.

The build stages an explicit allowlist of routes: `/`, `/demo/`, `/project/`, `/evaluation/`, plus Next's error page. It copies no `.env` or root deployment configuration, clears service environment variables, and replaces workspace navigation with architecture links. Shared review components and existing synthetic fixtures are reused. The full application's build and routes remain available separately.

Verification checks the exported HTML route allowlist and every root-relative HTML link/script/style reference. CI builds and verifies the same artifact. This is build evidence, not browser interaction or public deployment evidence. Shared frontend API helpers can exist in bundles; the demo supplies its local transport rather than a live backend.

Public deployment and core-flow verification are now recorded below. Remaining MVP work is final recruiting material and video review. Do not publish through the root full-service deployment config or replace the existing production service with this artifact.

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

This completed local core-flow checks for the MVP. The subsequent public checks are below. Full V1 and external-user acceptance are not implied.

## Public release — 2026-10-27

- Public origin: <https://meditrace-portfolio-mvp.vercel.app>. Deployed frontend source: [`3588c02`](https://github.com/zfz193071/meditrace/tree/3588c027ba06358501879cd1613bf806ebb16a61); its [CI](https://github.com/zfz193071/meditrace/actions/runs/40461135427) passed both jobs before release.
- Independent Vercel Hobby project: `meditrace-portfolio-mvp` / `prj_2B9S2xzHReAfVmDN8TXqO9w5scZ4`, scope `lucyzhus-projects`. Framework is `null`, environment-variable count is zero, and no Git repository is linked. The existing Services project, domain, database and environment were not modified.
- Deployment: `dpl_CVrbEriY4coMha1vMsmPy9sgCG2e`, READY, production alias assigned. Uploaded the previously verified `build-ytay_jnk` artifact as a static-only prebuilt bundle: 55 files, approximately 1.2 MB, no functions or source environment files. No rollback was needed.
- [27 unauthenticated HTTP checks](evidence/public-2026-10-27/http.json) passed: public pages, linked assets and report JSON match local artifact bytes; bare page paths redirect successfully; workspace/login/account/API/unknown paths return 404.
- [Live browser audit](evidence/public-2026-10-27/browser.json) passed: all three cases, keyboard review/confirmation/export/reset, three viewport widths and client navigation. All 91 observed requests were known resources on the MVP origin; no backend/model or external page requests occurred. [Evidence panel](evidence/public-2026-10-27/mobile-evidence.png) and [confirmed handoff](evidence/public-2026-10-27/mobile-confirmed.png) were visually inspected.

Print HTML and Blob text were inspected without an OS print dialog or a saved PDF. The absent favicon request is suppressed by the browser harness. This verifies the synthetic portfolio, not clinical use, real-model quality or full V1.

### Repeat this isolated release

```sh
pnpm --dir src/frontend build:portfolio
python3 scripts/portfolio_release.py prepare artifacts/portfolio/build-EXAMPLE/site
# Use the temporary directory printed by prepare; never the repository root.
vercel deploy --cwd /path/printed/by/prepare --prebuilt --prod --project meditrace-portfolio-mvp --scope lucyzhus-projects --yes
python3 scripts/portfolio_release.py verify artifacts/portfolio/build-EXAMPLE/site
# With a dedicated headless Chrome on port 9468:
node scripts/portfolio_browser_qa.cjs artifacts/portfolio/build-EXAMPLE/site 9468 --live
```

The release helper follows Vercel's [Build Output API](https://vercel.com/docs/build-output-api/configuration), stages only static files outside the checkout, declares the four page routes and a real 404 fallback, and performs no deployment itself. Public verification is pinned to this independent origin. Live browser mode permits only GET requests for files present in the supplied artifact; other page requests are blocked.
