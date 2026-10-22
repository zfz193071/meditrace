#!/usr/bin/env python3
"""Publish aggregate development counts only; never bundle corpus, recordings or test sources."""
import argparse
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REPORTS=ROOT/'evals/referral-review/reports'

def summary():
    reports=[]
    for mode in ('baseline','fake','replay'):
        directory=REPORTS/f'2026-10-22-{mode}-dev'
        report=json.loads((directory/'report.json').read_text())
        if report['split']!='dev' or report['release_status']!='BLOCKED': raise ValueError('Expected provisional development report')
        reports.append(dict(provider=report['provider'],origin=report['origin'],summary=report['summary'],
            versions=report['versions'],commit=report['commit'],working_tree_dirty=report['working_tree_dirty'],
            created_at=report['created_at'],corpus_sha256=report['corpus_sha256'],
            recording_sha256=report['recording_sha256'],offline_gates=report['offline_gates']))
    if reports[1]['summary']!=reports[2]['summary']: raise ValueError('Replay drift')
    return dict(schema_version='public-evaluation-v1',release_status='BLOCKED',split='dev',
        annotation_status='provisional_operator_review_pending',reports=reports,
        real_model_metrics=None,real_cost_usd=None,real_latency_p95_ms=None,human_verified_support=None,
        limitations=[
            dict(id='temporal-context',case='dev-06',mode='baseline',category='Observed offline baseline limitation',
                 expected='Keep the date context and flag directly opposing medication statements at the same date.',
                 actual='The simple baseline drops temporal context and misses one C06 statement_difference finding.',
                 impact='The reviewer could miss a clarification task.',handling='Inspect both source statements; the Fake validation + checklist path retains dates and detects this item. This is not a real-model comparison.'),
            dict(id='historical-template',case='dev-08',mode='baseline / fake / replay',category='Observed offline context limitation',
                 expected='Do not treat a historical template as current allergy status.',
                 actual='The line reader selects an Unknown statement under a historical-template heading, producing one extra C07 unknown finding.',
                 impact='A reviewer gets an unnecessary clarification task despite an intact source quote.',handling='Read the surrounding source. Keep this failure in the report; lexical citation checks do not establish semantic support.'),
            dict(id='scan',case='dev-10',mode='all offline paths',category='Deterministic unsupported-input rejection',
                 expected='Reject the packet when a scanned page cannot be read.',actual='PDF_UNREADABLE_PAGE; no successful result is produced.',
                 impact='The packet cannot receive an automated check.',handling='Supply supported text material or use manual review. Count the rejected packet in the total; do not report it as an extraction success.'),
            dict(id='annotation-alignment',case='dev-03 / dev-06',mode='fake / replay',category='Provisional annotation disagreement',
                 expected='Fact status and temporal context match the exact annotation tuple.',actual='Report date context and a specific negated medication assertion differ from provisional labels.',
                 impact='Two fact mismatches remain counted; they are not automatically classified as invented clinical facts.',handling='An operator must review the label and contract alignment. No gold or threshold was changed to improve the score.')])

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    path=ROOT/'src/frontend/public/evaluation/offline-summary.json'
    text=json.dumps(summary(),ensure_ascii=False,indent=2)+'\n'
    if args.check:
        if path.read_text()!=text: raise SystemExit('Evaluation display drift')
    else:
        path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
    print('Public evaluation summary matches development reports; no raw corpus or recording bundled.')
if __name__=='__main__': main()
