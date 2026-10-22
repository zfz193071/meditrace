# Role-specific project material — drafts

These are project-based statements, not verified employment history. Confirm your own contribution before putting them on a CV. Do not add years of experience, production customers, a clinical accuracy score, work rights or measured business impact without evidence.

## AI application engineer

**Short project description**

MediTrace is a synthetic-data referral-review prototype that combines structured extraction contracts, source-anchored evidence, a deterministic checklist and human-confirmed handoffs. Its current public examples are precomputed; offline baseline/Fake/replay reports expose failures and measurement limits. Real-provider quality and final infrastructure acceptance remain pending.

**Candidate project bullets — use after reviewing the implementation**

- Developed an AI-assisted document-review prototype with typed extraction boundaries, exact source anchoring and a human decision layer; demonstrated with fictional referral packets.
- Added an offline evaluation workflow with per-case TP/FP/FN, separate citation-integrity/support counters, negative-case false positives and replay provenance; retained historical-context and annotation-disagreement cases in the report.
- Implemented backend execution and usage-control paths for guarded dispatch, idempotent operations and conservative unknown-cost handling; explicitly tracked outstanding PostgreSQL and real-provider acceptance.

Evidence: [extraction](../../src/backend/referral_review/extraction/service.py), [evaluation](../../evals/referral-review/README.md), [run/usage evidence](../referral-review/MT-11-EVIDENCE.md). The word “developed” describes a project contribution and should be qualified with the AI-assisted workflow and your personally verified role.

## Full-stack engineer

**Short project description**

MediTrace is a Next.js/React/TypeScript and FastAPI portfolio prototype for checking referral documents. It includes an English landing page, a no-login local demo, a shared evidence/review UI, version-aware human decisions and handoff export. The authenticated backend has separate configuration and acceptance requirements.

**Candidate project bullets — use after reviewing the implementation**

- Built an English, responsive referral-review interface with shared production/demo contracts and components, including paired source quotes, reviewer decisions and confirmed handoff export.
- Separated a visitor-isolated in-memory demo adapter from the authenticated API transport; covered reset, stale results, version conflicts and unresolved-identity export behavior with automated tests.
- Documented inspectable development-only evaluation counts and failure explanations alongside implementation/version provenance, without presenting synthetic scores as clinical validation or real-model performance.

Evidence: [demo and workspace tests](../../src/frontend/__tests__/components/DemoWorkspace.test.tsx), [MT-15](../referral-review/MT-15-EVIDENCE.md), [MT-16](../referral-review/MT-16-EVIDENCE.md), [MT-20](../referral-review/MT-20-EVIDENCE.md).

## Shared boundaries

This is not a production clinical system. It has no validated HealthLink/hospital integration, no demonstrated fit to New Zealand clinical workflow, and no verified users or time-saving outcome.

Personal details to fill only after confirmation: current location, employment history, role ownership, English interview capability, availability, New Zealand work rights and whether employer visa support is needed.
