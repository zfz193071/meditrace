# Offline referral evaluation

Mode: **fake**; origin: **fake**; split: **dev**.

Provisional annotations. Not clinical validation or a real-model quality score.

Release status: **BLOCKED**. Commit: `0bfb26daef8a20fd707988a9bdcc8b18760d248d`.
Implementation SHA-256: `1c5de6adbc352b08aa997f8f7784a024e8150d61a76ade27e4f097e6a5450cdc`.

| Metric | Counts |
| --- | --- |
| Packets | 10 total; 9 succeeded; 1 rejected; 0 failed |
| Accepted facts | TP 71; FP 3; FN 2 |
| Findings (rule/kind/field) | TP 10; FP 1; FN 0 |
| Citation integrity | 74 / 74 accepted facts |
| Provisional annotated support agreement | 71 / 74 |
| Human-verified support, real tokens, cost, model latency | Not measured |

## Case results

| Case | Outcome | Error | Fact TP / FP / FN | Finding TP / FP / FN |
| --- | --- | --- | --- | --- |
| dev-01 | succeeded | — | 10 / 0 / 0 | 2 / 0 / 0 |
| dev-02 | succeeded | — | 8 / 0 / 0 | 1 / 0 / 0 |
| dev-03 | succeeded | — | 10 / 1 / 1 | 0 / 0 / 0 |
| dev-04 | succeeded | — | 7 / 0 / 0 | 1 / 0 / 0 |
| dev-05 | succeeded | — | 8 / 0 / 0 | 1 / 0 / 0 |
| dev-06 | succeeded | — | 8 / 1 / 1 | 1 / 0 / 0 |
| dev-07 | succeeded | — | 5 / 0 / 0 | 3 / 0 / 0 |
| dev-08 | succeeded | — | 8 / 1 / 0 | 0 / 1 / 0 |
| dev-09 | succeeded | — | 7 / 0 / 0 | 1 / 0 / 0 |
| dev-10 | rejected | PDF_UNREADABLE_PAGE | N/A — rejected input gold | N/A — rejected input gold |

Failed supported packets retain all gold false negatives. Rejected-input packets remain in total and rejection counts, not in successful fact denominators.

See report.json for per-field/per-kind counts, candidate diagnostics, negative packet and item false positives, versions, timing and cost provenance.

## Blockers

- Operator gold review pending
- No authorized real-model evaluation or independent evaluation ledger
- Frozen release gates and 20 real latency measurements not established
