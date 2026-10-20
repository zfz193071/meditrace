# Synthetic referral fixtures

This corpus supports offline development of the Referral Review Copilot. It contains 30 fictional packets: 10 development cases, 20 held-out test cases, and three public demonstrations copied only from development cases. It is not a clinical benchmark.

The annotations are **provisional, coding-agent-authored expectations awaiting operator review**. They are not outputs graded by the model under evaluation and are not human- or clinician-validated gold. Review procedure and current status: [ANNOTATION](ANNOTATION.md), [REVIEW-LOG](REVIEW-LOG.md).

## Contents

- `checklist.json`: machine-readable `outpatient-referral-demo@1`, C01–C08. No clinical thresholds.
- `manifest.json`: split, parser/generator versions and SHA-256 hashes for all generated files.
- `dev/` and `test/`: packet metadata, original text/PDF sources, parsed pages and provisional gold.
- `public/dev-01`, `public/dev-02`, `public/dev-03`: self-contained source files, precomputed `run.json`, and illustrative before/after review states. No API or model execution.
- `fixture.schema.json`: strict schemas that reuse MT-01's canonical Fact, Evidence, Finding and ReviewResult.
- `freeze.json`: independently checked checklist/test hashes; regeneration never updates this lock.
- `operator-review-template.json`: packet-hash-bound sign-off template; all entries genuinely remain pending.
- [LICENSE](LICENSE.txt) and [font license](BITSTREAM-VERA-LICENSE.txt): synthetic material reuse and embedded font terms.

There are 47 source documents, 187 provisional facts, 189 page-local evidence spans and 20 expected findings. Seven packets intentionally block automated review and have **no successful gold result**. Six test packets have no findings, exceeding the required five clean negatives.

Nineteen PDF files are present including four public copies; 15 are distinct source files. Corrupt/encrypted/scan/mixed/oversized/page-limit files are intentional rejection fixtures. Only ordinary text PDFs are expected to be accepted. No original source contains a real patient's identity, working contact, hospital logo or licensed clinical document; identifiers are explicitly synthetic and contacts use `example.invalid`.

## Reproduce and verify

From the repository root:

```bash
src/backend/venv/bin/uv sync --project src/backend --frozen --cache-dir .uv-cache
src/backend/.venv/bin/python scripts/referral_fixtures.py --check
src/backend/.venv/bin/python -m pytest -q src/backend/tests/referral_review/test_fixtures.py
src/backend/.venv/bin/python scripts/referral_fixture_render.py
```

`--check` regenerates into an automatically cleaned temporary directory, then compares bytes. It does not rewrite the checked corpus, call a provider, read `.env`, connect to a database, or start a service. `--write` regenerates assets; inspect the diff before accepting changes. To inspect an alternative build without overwriting the corpus, use `--write --output-root /absolute/temporary/directory`.

The PDF renderer writes only to ignored `.scratch/referral-pdf-qa/`. It uses project-local PDFium when system Poppler is unavailable. These preview images are disposable QA artifacts, not corpus inputs. ReportLab's invariant metadata, pinned dependencies, UUIDv5 IDs and fixed timestamps make the original files repeatable. Timestamps describe fixtures, not actual model or human activity.

## Public and held-out boundaries

Only the three `public/` directories are eligible for later MT-16 bundling. The entire fixture directory and authoring scripts are currently excluded from Vercel deployment, and no frontend loader has been added. MT-16 must explicitly copy/allowlist the public subset, never import the corpus generator.

The test files are visible to repository readers; “held-out” does not mean secret. They are excluded from public examples and must not be copied into development prompts, few-shot examples, tuning, or a public client bundle. The generator includes test authorship and therefore is itself a test asset. If developers inspect test errors and tune against them, report the exposure; do not continue to claim an unseen test result.

## Coverage

| Cases | Deliberate scenario |
| --- | --- |
| dev-01, test-08, test-09 | DOB/name disagreement; both sides retained |
| dev-01, test-10 | Missing attachment versus ambiguous attachment candidates |
| dev-02, dev-04, dev-05, test-01, test-02, test-07, test-11 | Listed/none/unknown/missing states |
| dev-03, test-03, dev-06, test-12 | Dated medication changes versus directly opposing same-date statements |
| dev-07, test-06, test-13 | Missing identity, sender/contact, destination or reason |
| dev-08, test-04, test-05, test-14 | Astral code points, ambiguous dates, duplicate quotes, Unicode units and cross-page evidence |
| dev-09, test-13 | Hostile instructions are source text, not facts or executable actions |
| dev-10, test-15 through test-20 | Scanned, corrupt, mixed, encrypted, >2 MiB and >25-page PDFs |

The corpus uses a compact, deliberately regular template. It verifies known semantics and failure boundaries; it does not establish accuracy on diverse real-world referrals. Production parsing isolation, resource limits, rules and actual model evaluation remain MT-06/08/09/20 responsibilities.
