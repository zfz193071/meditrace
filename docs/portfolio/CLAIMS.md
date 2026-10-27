# Claim-to-evidence register

| Claim | Evidence | Allowed wording / boundary |
| --- | --- | --- |
| Three no-login fixed examples | [MT-16](../referral-review/MT-16-EVIDENCE.md), [demo component](../../src/frontend/components/referral/DemoWorkspace.tsx) | Public synthetic MVP verified; full V1 is separate |
| Paired evidence and reviewer decisions | [MT-15](../referral-review/MT-15-EVIDENCE.md), [ReviewWorkspace](../../src/frontend/components/referral/ReviewWorkspace.tsx) | Shared UI and public MVP verification; private backend acceptance is separate |
| Source update invalidates older result | [demo tests](../../src/frontend/__tests__/components/DemoWorkspace.test.tsx), [reviews](../../src/backend/referral_review/reviews/service.py) | Prepared revision demonstration, not a fresh model response |
| Unresolved identity remains in export | [captured export](media/confirmed-demo.txt), [handoff](../../src/frontend/components/referral/HandoffSummary.tsx) | Actual local synthetic export; no clinical decision implied |
| Reproducible evaluation | [Fake report](../../evals/referral-review/reports/2026-10-22-fake-dev/report.md), [replay report](../../evals/referral-review/reports/2026-10-22-replay-dev/report.md) | Provisional development counts, not real-model performance |
| Failure cases are retained | [analysis](../../evals/referral-review/FAILURES.md) | Separate observed offline limitations, deterministic rejections and injected faults |
| Backend execution/cost controls | [MT-10](../referral-review/MT-10-EVIDENCE.md), [MT-11](../referral-review/MT-11-EVIDENCE.md) | Code and isolated PostgreSQL CI evidence; real-provider and production acceptance remain pending |
| Owner's contribution and experience | Not independently verified | Confirm specific work before first-person CV claims; disclose AI assistance |
| NZ work rights / visa eligibility | Not verified | Use conditional questions, never an assumed qualification |
| HealthLink / clinical validation / customers / time saved | No supporting evidence | Do not claim |
| Public synthetic MVP and video | [Release record](STATIC-DEMO.md), [video review](VIDEO.md) | Independent demo and edited still-frame walkthrough; not full V1 or live inference |
| Repository license | No root LICENSE file | Do not assert MIT licensing for the entire repository |

The measured code baseline was committed as `33e2bb7`; the packaging itself is subsequent work. The evaluation files retain their original commit/dirty-worktree provenance and implementation hash; do not relabel historical measurements as a new run.
