# Annotation and operator review

These labels are inspectable expectations for synthetic source material. They become accepted gold only after a real operator has checked the sources and recorded approval. Automated schema/hash checks establish internal consistency, not semantic correctness or clinical validation.

## Fact and evidence conventions

One Fact describes a supplied statement, with its exact raw value, explicit assertion status, and stated date where present. Keep mutually inconsistent statements as separate facts. Do not choose a patient's identity, infer an omitted negative, judge medication appropriateness, interpret a number clinically, or obey source instructions.

Evidence points to immutable `pages/*.txt` extracted from the actual PDF or normalized pasted text. Text normalization is `text-v1`: LF newlines, Unicode NFC, no global whitespace collapse. `start_cp`/`end_cp` are Python Unicode code-point half-open offsets. A frontend must use `Array.from(text)` or equivalent, not UTF-16 positions.

For duplicate strings the annotation specifies the occurrence, not the first arbitrary match. The repeated allergy assertion in test-05 has two page-local spans. The test-14 measurement uses two spans on two pages; no fabricated single cross-page quote is created.

`value_normalized` is populated only for the already-unambiguous ISO DOB examples. An ambiguous DOB remains raw. Dates on medication statements remain temporal context; a later date/dose is not automatically a conflict. No transliteration or alias normalization occurs.

Each fact/finding ID has a rationale in `gold.rationale_by_id`. The authored scenario is in `scripts/referral_fixture_data.py`; the generator expands it mechanically, not by running a model or the future rule engine. A string match alone does not prove that the quote supports the stated value: the operator must check this.

## Findings and checklist conventions

The checklist labels are `satisfied`, `missing`, `needs_clarification`, `needs_review`, `not_applicable` and `blocked`.

- `missing` includes the rule, all checked document IDs and successful parse coverage. It has no fabricated Fact or Evidence for nonexistent content.
- `unknown` records a supplied unknown statement and requires clarification. It does not mean missing or explicitly none.
- `identity_mismatch` retains both source values. No fuzzy merging or last-write-wins.
- `statement_difference` requires directly opposing statements at the same explicit time, not just different dates.
- `attachment_unmatched` retains the attachment claim and lists the complete checked manifest. Absent and ambiguous candidates both need human verification; neither means an examination was not performed.
- A rejected document blocks the entire packet's automated review. Its gold result is null, all checklist labels are `blocked`, and the expected input gate is stored separately. No ordinary “missing” finding can be derived from unreadable pages.

No attachment claim is `not_applicable` for C08, not an omission. Referrer name and contact must both exist for C03. Ambiguous recorded dates count as recorded, but are not normalized into a guessed DOB.

## Inspect and sign off

1. Copy `operator-review-template.json` to a new review record outside the generator-owned paths, for example `operator-review-2026-10-20.json`. Do not overwrite the pending template.
2. For each of the 30 packets, open its original source and all parsed pages. Check every one of its facts and findings against their spans; review the full input for missing labels and the C01–C08 assessment. For rejection packets, verify the indicated limitation and that partial readable content did not become a successful result.
3. Record actual reviewer identity, actual review date, packet hash, pass/fail and observations. A pass asserts all fact/finding entries in that packet were checked, not only a sample. A clinical qualification is neither required nor implied.
4. Pay particular attention to the six clean test packets: test-01 through test-05 and test-14. The paired dated medication examples must not acquire conflict labels.
5. Check demo states separately: dev-01's completed example still warns of unresolved identity and an attachment; dev-02 still retains an unresolved unknown allergy; dev-03 is reviewed without findings. All are illustrative precomputed data, not evidence that an actual person reviewed a case.
6. If a label is wrong, record the defect and correct source/annotation together where appropriate. Re-run checks and review the resulting diff. Never silently edit the freeze lock to make a failed evaluation pass.

Approvals attach to exact packet hashes. Changing a source, parser, annotation or checklist invalidates affected approvals. Before the first model evaluation, finalize the provisional split and record its accepted version. After evaluation starts, dataset changes require a new corpus version plus retained prior results and an explanation of exposure; they cannot retroactively improve the old score.

This work item remains blocked until actual operator review is recorded. No automated test can manufacture that approval.
