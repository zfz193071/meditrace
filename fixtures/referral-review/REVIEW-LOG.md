# Fixture review record

Date: 2026-10-20. Reviewer for the checks below: coding agent, not a human operator or clinical expert. The corpus is provisionally frozen as `synthetic-referral@1`; per-packet hashes are in `freeze.json` and `operator-review-template.json`.

## Completed engineering checks

- All 30 packets checked for schema, referential integrity, source/PDF text read-back, hashes, page-local offsets, declared coverage and split membership.
- 187 authored facts, 189 spans and 20 findings remain traceable to sources; existence of the spans is not claimed as a semantic-accuracy score.
- Six test packets have empty finding sets; seven input-rejection packets have no successful ReviewResult.
- Repeated generation matched the checked assets byte-for-byte, including encrypted and oversized fixtures.
- All 41 renderable source PDF pages rendered through PDFium 5.14.0. The coding agent inspected four contact sheets plus full-size dev-01, dev-03 follow-up and test-05 Unicode pages: no observed clipping, overlaps, missing accented/µ glyphs or broken page numbering. The deliberately corrupt file was excluded; the encrypted rejection fixture was opened only for visual QA with its known synthetic password.
- Public sources/results match exactly the three selected development packets. All initial/final review states validate. The “after” state does not silently resolve missing information.

## Operator approval

**Pending for all 30 packets.** No human review or clinical expert validation has occurred during this implementation. The pending template contains no reviewer identity or approval date. Follow [ANNOTATION](ANNOTATION.md) to perform and record the required review.

Agent-generated labels and engineering checks do not satisfy the specification's human-authored/reviewed ground-truth gate. MT-03 cannot be closed based solely on these checks; do not publish model performance claims from this corpus before that gate is met.
