# Technical interview draft

Use this as a rehearsal guide, not as a claim that you personally implemented or independently reviewed every component. Read the linked code, run the examples and replace any statement you cannot defend. The current implementation was produced with AI coding assistance.

## 90-second project introduction

> MediTrace explores a narrow document-review task: helping someone check a referral packet before handing it on. It highlights missing information and conflicting details, links each extracted fact to its source, and leaves the final decision with the reviewer.
>
> The demo uses fictional, precomputed material. In the identity example, two documents contain different dates of birth. Both quotes remain visible. A reviewer can keep the issue unresolved, add a reason and export a handoff that still carries the identity warning. Updating the source revision makes the old result read-only.
>
> The stack is Next.js and TypeScript with a FastAPI backend. The public demo uses an isolated in-memory adapter while sharing the workspace's evidence and review components. Backend code covers source revisions, ownership checks, bounded parsing, idempotent operations and model-cost reservations. Isolated PostgreSQL concurrency checks have CI evidence; full production and provider acceptance remain separate.
>
> The evaluation is deliberately transparent. A scripted Fake pipeline and replay are measured against provisional synthetic annotations. One example has a physically valid citation that comes from a historical template, so the citation does not establish current clinical meaning. That failure is retained in the report.
>
> This is an AI-assisted portfolio prototype, not a clinical product. My discussion would focus on the parts I have personally reviewed and can explain, and on what still requires real-provider testing and user validation.

Timing is a rehearsal target; no claim is made about the speaker's English fluency or delivery speed.

## Architecture walkthrough — approximately 7 minutes

| Time | Explain and demonstrate | Evidence |
| --- | --- | --- |
| 0:00–0:45 | Define the user/task, synthetic scope and human decision boundary. Avoid diagnosis or clinical effectiveness claims. | [Product](../referral-review/PRODUCT.md), [demo UI](../../src/frontend/components/referral/DemoWorkspace.tsx) |
| 0:45–1:45 | Trace a file through bounded parsing, normalized pages and a source revision. Explain why an unreadable page blocks automatic review of the packet. | [Parser](../../src/backend/referral_review/documents/parser.py), [parser tests](../../src/backend/tests/referral_review/test_parser.py) |
| 1:45–2:45 | Follow a fact to document/page/code-point offsets/hash. Distinguish lexical verification from semantic support; show the historical-template failure. | [Text rules](../../src/backend/referral_review/documents/text_rules.py), [extraction validation](../../src/backend/referral_review/extraction/service.py), [failures](../../evals/referral-review/FAILURES.md) |
| 2:45–3:45 | Explain immutable source revisions, stale runs, separate reviewer decisions and frozen handoffs. Demonstrate prepared revision replacement. | [Packet service](../../src/backend/referral_review/packets/service.py), [review service](../../src/backend/referral_review/reviews/service.py), [review tests](../../src/backend/tests/referral_review/test_reviews.py) |
| 3:45–4:45 | Explain explicit dispatch, idempotency, reservations and unknown cost. A timeout is not proof that the provider did no work. | [Run service](../../src/backend/referral_review/runs/service.py), [usage service](../../src/backend/referral_review/usage/service.py), [run tests](../../src/backend/tests/referral_review/test_runs.py) |
| 4:45–5:30 | Trace authentication and ownership rather than trusting client-supplied IDs. Demo isolation does not validate private-workspace security. | [Identity service](../../src/backend/referral_review/identity/service.py), [identity tests](../../src/backend/tests/referral_review/test_identity.py), [packet tests](../../src/backend/tests/referral_review/test_packets.py) |
| 5:30–6:30 | Show the shared transport boundary, offline recorder and replay. Explain why failure cases stay in denominators and why Fake costs are null. | [Review transport](../../src/frontend/components/referral/ReviewTransport.tsx), [evaluation runner](../../evals/referral-review/referral_eval/runner.py), [metrics tests](../../src/backend/tests/referral_review/test_evaluation.py) |
| 6:30–7:00 | State the unresolved acceptance gates and next experiment: reviewed labels and a budgeted real evaluation after accounting integration. | [MT-20 evidence](../referral-review/MT-20-EVIDENCE.md), [release gates](../referral-review/QUALITY-AND-RELEASE.md) |

## Technical follow-up questions

1. **Why not just summarize the packet?** A summary alone cannot show whether a stated attachment is present or preserve both sides of an identity discrepancy. The checklist produces explicit review items, while citations support inspection. The [checklist service](../../src/backend/referral_review/checklist/service.py) is deterministic; no clinical decision is delegated to it.
2. **What does a valid citation prove?** It proves a quote can be located on an immutable normalized page using offsets and hash. It does not prove relevance or current meaning. [dev-08's failure](../../evals/referral-review/FAILURES.md#2-historical-template-treated-as-current--baseline-and-fake-dev-08) demonstrates the distinction.
3. **Why code points rather than JavaScript indexes?** Astral characters occupy two UTF-16 units. Python and frontend evidence slicing must agree on Unicode code points. The [frontend helper](../../src/frontend/lib/referral-api/evidence.ts) and [parser tests](../../src/backend/tests/referral_review/test_parser.py) cover this boundary.
4. **What happens after a source changes?** The new revision gets an independent run. Old results remain inspectable but cannot receive new decisions; corrections do not silently carry forward. See [reviews](../../src/backend/referral_review/reviews/service.py) and [demo tests](../../src/frontend/__tests__/components/DemoWorkspace.test.tsx).
5. **Does idempotency guarantee one provider charge?** No universal exactly-once claim is made. The run state machine prevents repeat dispatch through its guarded path, but a provider timeout can leave the outcome unknown. Reservations remain conservative until reconciliation. [Runs](../../src/backend/referral_review/runs/service.py) and [usage tests](../../src/backend/tests/referral_review/test_usage.py) support the design; isolated PostgreSQL CI is recorded; real-provider and production acceptance remain pending.
6. **Why is the demo not the authenticated backend?** An isolated local adapter makes the review task inspectable without account or provider setup. It shares UI/contracts but is not evidence of backend authorization, durable storage or billing. See [adapter](../../src/frontend/lib/referral-api/demo.ts) and [shared UI](../../src/frontend/components/referral/ReviewWorkspace.tsx).
7. **How can evaluation be misleading?** Removing failed packets improves apparent recall, treating Fake token constants as costs fabricates measurements, and equating a quote match with semantic support overclaims quality. The [metrics](../../evals/referral-review/referral_eval/metrics.py) keep denominators and null measurements explicit.
8. **Why isn't the real evaluation command enabled?** The independent evaluation ledger and global reservation controls are implemented, but the real runner, authorized budget and reviewed annotations remain incomplete. A cost-cap argument alone is not authorization. The [runner](../../evals/referral-review/referral_eval/runner.py) rejects real mode, including programmatic entry; this is a remaining implementation task, not completed budget validation.
9. **How would this integrate with a hospital or HealthLink?** That integration has not been implemented or validated. First establish the actual workflow, permission boundaries, data contracts and clinical ownership with users; the current prototype only accepts synthetic documents. Do not claim New Zealand workflow compatibility.
10. **What would you change after these results?** First have an operator review annotation/contract disagreements and historical-context handling. Then finish the real-runner integration and obtain authorization for real evaluation. Do not silently alter gold or tune on frozen-test errors while calling the result unseen. [Failure analysis](../../evals/referral-review/FAILURES.md) records the current evidence.

## AI-assisted development and individual ownership

Verified repository facts: an AI coding assistant produced implementation, tests and documents under user direction and repository rules; automated regression and offline browser evidence are recorded. There is no verified record here that the owner independently reviewed every line, authored all algorithms or performed clinical validation.

Before using first-person contribution claims, record the specific files you reviewed, explain a design alternative, reproduce a failure and explain its fix, and distinguish a test you executed yourself from one run by the assistant. Useful review exercises are the dev-08 semantic failure, stale-review rejection, unknown-cost retention and replay provenance checks. Their existence is verified; completing these personal exercises is **pending**, not asserted.

Suggested disclosure after personal review: “I used an AI coding assistant for implementation and test drafting. I personally reviewed [specific modules], reproduced [specific cases], and made [specific verified decisions]. Remaining gaps are [current acceptance items].” Do not remove the placeholders until true.
