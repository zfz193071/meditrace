# Reproducible failures and limitations

All observations below come from the checked-in **development-only offline reports**, not a real model. The source corpus and provisional annotations were not edited. Per-case `metrics.differences` retain the exact tuples in each report JSON. Future operator label changes must invalidate the prior packet hash and require new results.

## 1. Lost temporal context — simple baseline, dev-06

Expected: directly opposing medication statements share an explicit date and produce a C06 statement_difference item.

Observed: the baseline has no temporal extraction. Both dates are dropped; one expected finding is missed. See [baseline report](reports/2026-10-22-baseline-dev/report.json), row `dev-06`, `missing_findings`.

Impact: a clarification task can be missed. Handling: inspect the two source statements and their dates. The Fake pipeline's scripted dates allow the production checklist to detect this item. This is a difference between two deterministic inputs, not evidence that an LLM is more accurate.

## 2. Historical template treated as current — baseline and Fake, dev-08

Expected: the source says “Historical template, not current allergy status” before a second allergy line. That line should not become the current patient's unknown allergy assertion.

Observed: the prefix reader includes that line and creates one extra C07 unknown finding. Its citation is physically correct, but the surrounding section changes its meaning. [Fake report](reports/2026-10-22-fake-dev/report.json), row `dev-08`, shows the unmatched allergy fact and extra finding; the [replay report](reports/2026-10-22-replay-dev/report.json) reproduces them.

Impact: unnecessary clarification work. Handling: retain the failure, show source context to the reviewer and keep human support verification pending. Exact lexical quote verification is not semantic support. No model self-grading or invented human feedback was used.

## 3. Unreadable scanned input — deterministic rejection, dev-10

Expected: the entire packet is blocked when one supplied source page cannot be read, instead of silently skipping it and creating “missing” findings.

Observed: the production parser returns PDF_UNREADABLE_PAGE. It remains one rejected packet out of ten, has no successful fact gold, and is not counted as an extraction success.

Impact: no automatic review for this material. Handling: provide supported text material or review manually. This is an intentional scope limit, not a model failure or a measured success on scanned referrals.

## 4. Provisional annotation/contract disagreements — Fake, dev-03 and dev-06

Observed: the extractor requires explicit report dates to remain in temporal context, while dev-03's report annotation has no temporal context. A specific “not taking” medication assertion is marked explicitly_none by the lexical validator, while dev-06's provisional label is stated. Both remain FP/FN fact mismatches in the report.

Impact: interpreting every annotation mismatch as fabricated clinical content would overstate the evidence. Handling: an actual operator must decide the intended annotation/contract semantics, then version any correction. This work did not silently change gold, rewrite the production validator or ignore these mismatches.

## Separate fault-injection checks

`test_evaluation.py` deliberately fabricates a citation and verifies MODEL_INVALID_OUTPUT rejection; it also injects an interrupted remainder and checks that missed facts stay in denominators and replay preserves the failure. These are **automated fault injections**, not observed provider incidents. Real calls with omitted, zero, negative, NaN or positive caps all fail closed before output creation. None of these tests constitutes validation of a real evaluation ledger or actual spending recovery.
