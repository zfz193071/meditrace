#!/usr/bin/env python3
"""Build the public, offline demo only from public development material.

No frozen/private evaluation cases, provider calls or database access. The missing
report variant removes dev-01's intake note; revision two adds an authored report.
Findings are recomputed by the production deterministic checklist, not a model.
"""
import argparse
import base64
import copy
import hashlib
import json
from pathlib import Path
import sys
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src/backend'))
from referral_review.schemas import PacketDetailResponse, RevisionResponse, RunResponse, DocumentPageResponse, ReviewResult
from referral_review.checklist.contracts import ChecklistManifest
from referral_review.checklist.service import evaluate
from referral_review.extraction.contracts import Extraction

NOW = '2026-10-22T00:00:00Z'
def uid(key): return str(uuid5(NAMESPACE_URL, 'meditrace-public-demo:' + key))
def digest(value): return hashlib.sha256(value.encode()).hexdigest()

def variant(key, source, title, missing=False, prepared=False):
    directory = ROOT / 'fixtures/referral-review/public' / source
    original = json.loads((directory / 'documents.json').read_text())
    result = json.loads((directory / 'run.json').read_text())
    docs = copy.deepcopy(original['documents'][:1] if missing else original['documents'])
    pid, rid, runid = uid(key + ':packet'), uid(key + (':revision-2' if prepared else ':revision-1')), uid(key + (':run-2' if prepared else ':run-1'))
    pages, urls = [], {}
    for doc in docs:
        raw = (directory / doc['source_path']).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == doc['sha256']
        urls[doc['id']] = 'data:' + ('application/pdf' if doc['kind'] == 'pdf' else 'text/plain;charset=utf-8') + ';base64,' + base64.b64encode(raw).decode()
        for page in doc['pages']:
            text = (directory / page['text_path']).read_text()
            assert digest(text) == page['text_hash']
            pages.append(dict(document_id=doc['id'], page_number=page['number'], normalized_text=text, text_hash=digest(text), parse_quality='ready', parser_version='text-v1'))
    allowed = {d['id'] for d in docs}
    result['evidence'] = [e for e in result['evidence'] if e['document_id'] in allowed]
    eids = {e['id'] for e in result['evidence']}
    result['facts'] = [f for f in result['facts'] if set(f['evidence_ids']) <= eids]
    if prepared:
        text = 'SYNTHETIC - fictional training material, not clinical guidance\nSynthetic Echo Report A\nReport: Synthetic Echo Report A, dated 2026-10-01.'
        did, eid = uid(key + ':report'), uid(key + ':report-evidence')
        quote = 'Synthetic Echo Report A, dated 2026-10-01.'
        docs.append(dict(id=did, kind='text', title='Synthetic Echo Report A', sha256=digest(text), byte_size=len(text.encode()), pages=[{}]))
        pages.append(dict(document_id=did, page_number=1, normalized_text=text, text_hash=digest(text), parse_quality='ready', parser_version='text-v1'))
        urls[did] = 'data:text/plain;charset=utf-8;base64,' + base64.b64encode(text.encode()).decode()
        result['evidence'].append(dict(id=eid, document_id=did, page_number=1, start_cp=text.index(quote), end_cp=text.index(quote)+len(quote), quote=quote, text_hash=digest(text)))
        result['facts'].append(dict(id=uid(key+':report-fact'), field_key='report.description', value_raw=quote, value_normalized=None, assertion_status='stated', temporal_context='2026-10-01', evidence_ids=[eid]))
    manifest = ChecklistManifest(revision_id=rid, documents=[dict(id=d['id'], title=d['title'], kind=d['kind'], parse_status='ready', page_count=len(d['pages']), pages=[p for p in pages if p['document_id']==d['id']]) for d in docs])
    extraction = Extraction(revision_id=rid, mode='fake', model_requested='authored-public-fixture', model_reported=None, provider_request_id=None, usage=None, facts=result['facts'], evidence=result['evidence'])
    checked = evaluate(extraction, manifest)
    result.update(run_id=runid, revision_id=rid, findings=[f.model_dump(mode='json') for f in checked.findings])
    result = ReviewResult.model_validate(result).model_dump(mode='json')
    expected = [] if prepared or key == 'normal' else ['attachment_unmatched'] if missing else ['attachment_unmatched', 'identity_mismatch']
    assert sorted(f['kind'] for f in result['findings']) == sorted(expected)
    revision = RevisionResponse(id=rid, packet_id=pid, revision_number=2 if prepared else 1, manifest_hash=digest(json.dumps(docs,sort_keys=True)), documents=[dict(id=d['id'], kind=d['kind'], filename=d['title']+('.pdf' if d['kind']=='pdf' else '.txt'), sha256=d['sha256'], parser_version='text-v1', page_count=len(d['pages']), byte_size=d['byte_size']) for d in docs], is_current=True, created_at=NOW)
    packet = PacketDetailResponse(id=pid, title=title, state='ready', current_revision=revision.revision_number, review_version=0, synthetic_data_ack=True, created_at=NOW, updated_at=NOW, expires_at='2099-01-01T00:00:00Z', current_document_ids=[d['id'] for d in docs], documents=[dict(**d.model_dump(), packet_id=pid, parse_status='ready', created_at=NOW) for d in revision.documents], draft=dict(packet_id=pid, selected_document_ids=[d['id'] for d in docs], last_location='review', base_revision=revision.revision_number, draft_version=0, updated_at=NOW))
    run = RunResponse(id=runid, packet_id=pid, revision_id=rid, state='succeeded', mode='precomputed', stale=False, phase='complete', checklist_version=result['checklist_version'], prompt_version='authored-public-fixture', schema_version=result['schema_version'], model_requested=None, model_reported=None, created_at=NOW, finished_at=NOW, lease_expires_at=None, error_code=None, usage=None, result=result)
    return dict(packet=packet.model_dump(mode='json'), revision=revision.model_dump(mode='json'), run=run.model_dump(mode='json'), pages=[DocumentPageResponse(**p).model_dump(mode='json') for p in pages], originals=urls)

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--check', action='store_true'); args=parser.parse_args()
    assets=dict(normal=variant('normal','dev-03','Complete referral'), missing=variant('missing','dev-01','Missing claimed report',True), identity=variant('identity','dev-01','Conflicting dates of birth'), prepared=variant('missing','dev-01','Missing claimed report',True,True))
    output=json.dumps(assets,ensure_ascii=False,indent=2)+'\n'
    path=ROOT/'src/frontend/lib/referral-api/demo-assets.json'
    if args.check:
        assert path.read_text()==output, 'Demo assets drift; regenerate with scripts/referral_demo_assets.py'
    else: path.write_text(output)
    print('Four demo revisions validated against production contracts, source hashes and deterministic checklist.')
if __name__=='__main__': main()
