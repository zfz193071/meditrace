"""Read synthetic files, execute bounded offline pipelines, record and recompute metrics."""
import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import platform
import math
from importlib.metadata import version
from pathlib import Path
import subprocess
import sys
import time
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src/backend'))
from referral_review.config import Settings
from referral_review.documents.parser import parse_pdf, parse_text, PDF_PARSER_VERSION
from referral_review.documents.text_rules import locate_quote
from referral_review.schemas import DocumentPageResponse
from referral_review.extraction.adapters import FakeAdapter, ExtractionError
from referral_review.extraction.contracts import Extraction, ExtractionRevision, PROMPT_VERSION, SCHEMA_VERSION
from referral_review.extraction.service import extract, validate_output, DATE, UNKNOWN, NONE
from referral_review.checklist import ChecklistManifest, evaluate
from referral_review.checklist.contracts import CHECKLIST_VERSION
from .metrics import score, aggregate
from .files import fixture_bytes, unique_json

CORPUS = ROOT / 'fixtures/referral-review'
REJECTIONS = {'SCANNED_PAGE':'PDF_UNREADABLE_PAGE','UNREADABLE_NONEMPTY_PAGE':'PDF_UNREADABLE_PAGE',
              'CORRUPT_PDF':'PDF_DAMAGED','ENCRYPTED_PDF':'PDF_ENCRYPTED','PDF_TOO_LARGE':'PDF_RESOURCE_LIMIT',
              'PACKET_PAGE_LIMIT':'PDF_PAGE_LIMIT'}
FIELDS = {'Patient':'patient.name','DOB':'patient.dob','Referrer':'referrer.name','Contact':'referrer.contact',
          'Recipient':'recipient','Reason':'referral.reason','Medications':'medications','Allergies':'allergies',
          'Attachment':'attachment_reference','Report':'report.description'}

def sha(body): return hashlib.sha256(body).hexdigest()
def uid(value): return str(uuid5(NAMESPACE_URL, 'meditrace-eval:'+value))
def read(path):
    if path.stat().st_size > 8_000_000: raise ValueError('Evaluation JSON exceeds 8 MB')
    return json.loads(path.read_text())
def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
    temp.replace(path)


def versions():
    paths = [ROOT/'evals/referral-review/referral_eval', ROOT/'src/backend/referral_review/extraction',
             ROOT/'src/backend/referral_review/checklist', ROOT/'src/backend/referral_review/documents']
    files = sorted([p for directory in paths for p in directory.glob('*.py')]+[ROOT/'src/backend/referral_review/schemas/__init__.py', ROOT/'src/backend/referral_review/config.py'])
    digest=sha(''.join(str(p.relative_to(ROOT))+':'+sha(p.read_bytes())+'\n' for p in files).encode())
    return dict(evaluator='offline-eval-v1', implementation_sha256=digest, schema=SCHEMA_VERSION,
                prompt=PROMPT_VERSION, checklist=CHECKLIST_VERSION, parser=PDF_PARSER_VERSION,
                model='fake-extraction-v1', price_version=None)


def load_cases(split):
    if split not in ('dev', 'test'): raise ValueError('Invalid split')
    manifest=unique_json(fixture_bytes(CORPUS,'manifest.json'))
    freeze=unique_json(fixture_bytes(CORPUS,'freeze.json'))
    if sha(fixture_bytes(CORPUS,'checklist.json')) != manifest['checklist_sha256'] or manifest['checklist_sha256'] != freeze['checklist_sha256']:
        raise ValueError('Checklist hash mismatch')
    cases=[]; seen=set()
    for entry in manifest['entries']:
        if entry['key'] in seen: raise ValueError('Duplicate packet key')
        seen.add(entry['key'])
        if entry['split'] != split: continue
        body=fixture_bytes(CORPUS,entry['packet_path'])
        path=CORPUS/entry['packet_path']
        if sha(body) != entry['sha256']: raise ValueError('Packet hash mismatch')
        if split=='test' and freeze['test_packets'].get(entry['key']) != entry['sha256']: raise ValueError('Frozen packet mismatch')
        packet=unique_json(body)
        if packet.get('synthetic') is not True: raise ValueError('Synthetic corpus required')
        if packet['key'] != entry['key']: raise ValueError('Packet identity mismatch')
        for doc in packet['documents']:
            if sha(packet_bytes(path.parent,doc['source_path'])) != doc['sha256']: raise ValueError('Packet-bound source hash mismatch')
            for page in doc['pages']:
                if sha(packet_bytes(path.parent,page['text_path'])) != page['text_hash']: raise ValueError('Packet-bound page hash mismatch')
            for relative in [doc['source_path']]+[p['text_path'] for p in doc['pages']]:
                file=path.parent/relative
                if sha(packet_bytes(path.parent,relative)) != manifest['files'][str(file.relative_to(CORPUS))]: raise ValueError('Source hash mismatch')
        cases.append((entry,packet,path.parent))
    if len(cases) != (10 if split=='dev' else 20): raise ValueError('Unexpected split size')
    return manifest,cases


def packet_bytes(directory, relative):
    # Always walk from the corpus root, including packet-directory components.
    # A previously checked directory may have been replaced with a symlink.
    relative = Path(relative)
    if relative.is_absolute() or '..' in relative.parts or not relative.parts:
        raise ValueError('Invalid fixture path')
    return fixture_bytes(CORPUS, directory.relative_to(CORPUS) / relative)


def parse_case(packet, directory):
    docs=[]; issue=None
    for d in packet['documents']:
        raw=packet_bytes(directory,d['source_path'])
        if sha(raw) != d['sha256']: raise ValueError('Packet-bound source hash mismatch')
        parsed=(parse_pdf if d['kind']=='pdf' else parse_text)(raw)
        issue=issue or parsed.issue_code
        pages=[DocumentPageResponse(document_id=d['id'],page_number=p.page_number,normalized_text=p.normalized_text,
                                    text_hash=p.text_hash,parse_quality=p.parse_quality,parser_version=parsed.parser_version) for p in parsed.pages]
        docs.append(dict(id=d['id'],title=d['title'],kind=d['kind'],parse_status=parsed.status,
                         page_count=parsed.page_count or 1,pages=pages))
    return docs,issue


def scripted_output(pages, *, baseline=False):
    """Line-prefix reader, deliberately simple; never reads gold. Not a language model."""
    facts=[]
    for page in pages:
        offset=0
        for line in page.normalized_text.splitlines(keepends=True):
            quote=line.rstrip('\n'); prefix, separator, raw=quote.partition(': ')
            if separator and prefix in FIELDS and raw:
                field=FIELDS[prefix]
                dates=DATE.findall(quote)
                facts.append(dict(field_key=field,
                    value_raw=quote if field in ('medications','report.description') else raw,
                    value_normalized=None,
                    assertion_status='unknown' if UNKNOWN.search(raw) else 'explicitly_none' if NONE.search(raw) else 'stated',
                    temporal_context=None if baseline or not dates or field not in ('medications','report.description') else ', '.join(dates),
                    sources=[dict(document_id=str(page.document_id),page_number=page.page_number,quote=quote,
                                  before=page.normalized_text[:offset],after='')]))
            offset+=len(line)
    return dict(facts=facts)


def candidate_result(output,pages):
    """Diagnostic pre-validation score, kept separate from accepted-output metrics."""
    page_map={(str(p.document_id),p.page_number):p for p in pages}
    facts=[]; evidence=[]
    for i,f in enumerate(output.get('facts',[])):
        ids=[]
        for j,s in enumerate(f.get('sources',[])):
            eid=uid(f'candidate:{i}:{j}'); ids.append(eid)
            p=page_map.get((s['document_id'],s['page_number']))
            try:
                anchor=locate_quote(p.normalized_text,s['quote'],before=s.get('before',''),after=s.get('after',''))
                start,end,hash_=anchor.start_cp,anchor.end_cp,anchor.text_hash
            except (ValueError,AttributeError): start,end,hash_=0,len(s['quote']),'0'*64
            evidence.append(dict(id=eid,document_id=s['document_id'],page_number=s['page_number'],start_cp=start,end_cp=end,quote=s['quote'],text_hash=hash_))
        facts.append(dict(id=uid(f'candidate:{i}'),**{k:f[k] for k in ('field_key','value_raw','value_normalized','assertion_status','temporal_context')},evidence_ids=ids))
    return dict(facts=facts,evidence=evidence,findings=[])


async def execute(packet,docs,provider,output,recorded_error=None):
    pages=[p for d in docs for p in d['pages']]
    revision=uid(packet['key']+':revision')
    if recorded_error: raise ExtractionError(recorded_error)
    if provider=='baseline':
        candidate=candidate_result(output,pages)
        extraction=Extraction(revision_id=revision,mode='fake',model_requested='line-prefix-baseline-v1',model_reported=None,provider_request_id=None,usage=None,facts=candidate['facts'],evidence=candidate['evidence'])
    elif provider=='fake':
        extraction=await extract(ExtractionRevision(revision_id=revision,pages=pages),Settings(),FakeAdapter(output))
    else:
        # Re-run validation and deterministic rules on recorded synthetic model-shaped output.
        content=json.dumps(output)
        if len(content.encode())>128_000: raise ExtractionError('MODEL_INVALID_OUTPUT')
        facts,evidence=validate_output(content,ExtractionRevision(revision_id=revision,pages=pages))
        extraction=Extraction(revision_id=revision,mode='fake',model_requested='replay',model_reported=None,provider_request_id=None,usage=None,facts=facts,evidence=evidence)
    checked=evaluate(extraction,ChecklistManifest(revision_id=revision,documents=docs))
    return dict(facts=[f.model_dump(mode='json') for f in extraction.facts],evidence=[e.model_dump(mode='json') for e in extraction.evidence],findings=[f.model_dump(mode='json') for f in checked.findings])


async def run(split='dev',provider='fake',recording=None,interrupt_after=None):
    if provider not in ('baseline','fake','replay'): raise ValueError('Only offline providers are supported')
    if recording is not None and provider!='replay': raise ValueError('Recordings are accepted only in replay mode')
    manifest,cases=load_cases(split); rows=[]; records=[]
    if provider=='replay':
        if not recording or recording.get('schema_version')!='eval-recording-v1' or recording.get('origin') not in ('fake','baseline'): raise ValueError('Invalid recording')
        if recording['split']!=split or recording['corpus_sha256']!=sha((CORPUS/'manifest.json').read_bytes()): raise ValueError('Recording corpus/split mismatch')
        saved={r['key']:r for r in recording['records']}
        if len(saved)!=len(cases) or len(recording['records'])!=len(cases) or set(saved)!={e['key'] for e,_,_ in cases}: raise ValueError('Recording must contain every case once')
    for index,(entry,packet,directory) in enumerate(cases):
        started=time.perf_counter(); docs,issue=parse_case(packet,directory)
        pages=[p for d in docs for p in d['pages']]
        page_map={(str(p.document_id),p.page_number):p.normalized_text for p in pages}
        result=None; error=None; output=None; candidate=None
        if provider=='replay':
            record=saved[entry['key']]
            if record['packet_sha256']!=entry['sha256']: raise ValueError('Recording packet mismatch')
            output=record['output']
        else: record=None
        try:
            if issue or record and record.get('input_rejection'):
                status='rejected'; error=issue or record['input_rejection']
            elif interrupt_after is not None and index>=interrupt_after: status='failed'; error='EVALUATION_INTERRUPTED'
            else:
                if record and record['execution_error'] and output is None: raise ExtractionError(record['execution_error'])
                if record and output is None: raise ExtractionError('EVALUATION_RECORDING_MISSING_OUTPUT')
                output=output if record else scripted_output(pages,baseline=provider=='baseline')
                candidate=score(candidate_result(output,pages),packet['gold']['result'],page_map)
                replay_provider=('baseline' if recording and recording['origin']=='baseline' else provider)
                result=await execute(packet,docs,replay_provider,output,record['execution_error'] if record else None)
                status='succeeded'
        except (ExtractionError,ValueError,TypeError,KeyError) as exc:
            status='failed'; error=getattr(exc,'code','OUTPUT_VALIDATION_FAILED')
        elapsed=round((time.perf_counter()-started)*1000,3)
        gold=packet['gold']; metrics=score(result,gold['result'],page_map) if gold['automated_review_allowed'] else None
        rows.append(dict(key=entry['key'],packet_sha256=entry['sha256'],status=status,error=error,
            expected_rejection=gold['expected_rejection'],unexpected_outcome=(status!='succeeded' if gold['automated_review_allowed'] else status!='rejected' or error!=REJECTIONS.get(gold['expected_rejection'])),
            metrics=metrics,candidate_metrics=candidate,elapsed_ms=elapsed,
            original_elapsed_ms=record['elapsed_ms'] if record else None,page_count=len(pages),
            tokens=None,actual_cost_usd=None,estimated_cost_usd=None))
        records.append(dict(key=entry['key'],packet_sha256=entry['sha256'],output=output,
            input_rejection=error if status=='rejected' else None,
            execution_error=error if status=='failed' else None,elapsed_ms=elapsed))
    summary=aggregate(rows)
    report_gates = dict(citation_integrity=summary['citation_integrity']['value']==1,
        provisional_fact_precision=(summary['facts']['precision']['value'] or 0)>=.95,
        finding_precision=(summary['findings']['precision']['value'] or 0)>=.90,
        finding_recall=(summary['findings']['recall']['value'] or 0)>=.90,
        no_critical_annotation_mismatch=summary['critical_unannotated_facts']==0,
        no_unexpected_outcomes=not any(r['unexpected_outcome'] for r in rows),
        minimum_clean_test_negatives=split=='test' and summary['negative_packets']['denominator']>=5,
        no_negative_identity_false_positives=summary['negative_identity_false_positives']==0)

    latencies=sorted(r['elapsed_ms'] for r in rows if r['page_count']<=5 and r['status']=='succeeded')
    measured=dict(scope='local offline execution, not model latency',success_count=len(latencies),total_packets=len(rows),
                  failures=sum(r['status']=='failed' for r in rows),p95_ms=latencies[max(0,math.ceil(len(latencies)*.95)-1)] if latencies else None,
                  release_latency_eligible=False)
    version_info=versions()
    version_info['model']='line-prefix-baseline-v1' if provider=='baseline' or recording and recording['origin']=='baseline' else 'fake-extraction-v1'
    report=dict(schema_version='eval-report-v1',provider=provider,origin=recording['origin'] if recording else provider,split=split,
        annotation_status=manifest['annotation_status'],corpus_sha256=sha((CORPUS/'manifest.json').read_bytes()),
        environment=dict(python=platform.python_version(),system=platform.system(),pydantic=version('pydantic'),pypdf=version('pypdf')),
        versions=version_info,recorded_versions=recording['versions'] if recording else None,
        requires_new_real_evaluation=True,release_status='BLOCKED',
        blockers=['Operator gold review pending','No authorized real-model evaluation; real runner dispatch/recording integration pending',
                  'Frozen release gates and 20 real latency measurements not established'],
        offline_gates=report_gates,frozen_test_exposed=split=='test',summary=summary,latency=measured,rows=rows,
        cost=dict(measurement='not measured; offline synthetic output',input_tokens=None,output_tokens=None,actual_usd=None,estimated_usd=None,unknown_packets=len(rows)))
    capture=dict(schema_version='eval-recording-v1',origin=recording['origin'] if recording else provider,split=split,
        corpus_sha256=report['corpus_sha256'],versions=version_info,records=records)
    return report,capture


def comparable(report):
    return json.loads(json.dumps(dict(summary=report['summary'],cases=[dict(key=r['key'],status=r['status'],error=r['error'],metrics=r['metrics'],candidate_metrics=r['candidate_metrics']) for r in report['rows']])))


def markdown(report):
    s=report['summary']; lines=['# Offline referral evaluation', '',f"Mode: **{report['provider']}**; origin: **{report['origin']}**; split: **{report['split']}**.",
        '', 'Provisional annotations. Not clinical validation or a real-model quality score.', '',
        f"Release status: **{report['release_status']}**. Commit: `{report.get('commit','unrecorded')}`.",
        f"Implementation SHA-256: `{report['versions']['implementation_sha256']}`.", '',
        '| Metric | Counts |','| --- | --- |',
        f"| Packets | {s['packets_total']} total; {s['successful']} succeeded; {s['rejected']} rejected; {s['failed']} failed |",
        f"| Accepted facts | TP {s['facts']['tp']}; FP {s['facts']['fp']}; FN {s['facts']['fn']} |",
        f"| Findings (rule/kind/field) | TP {s['findings']['tp']}; FP {s['findings']['fp']}; FN {s['findings']['fn']} |",
        f"| Citation integrity | {s['citation_integrity']['numerator']} / {s['citation_integrity']['denominator']} accepted facts |",
        f"| Provisional annotated support agreement | {s['provisional_support']['numerator']} / {s['provisional_support']['denominator']} |",
        '| Human-verified support, real tokens, cost, model latency | Not measured |', '',
        '## Case results', '', '| Case | Outcome | Error | Fact TP / FP / FN | Finding TP / FP / FN |', '| --- | --- | --- | --- | --- |']
    for r in report['rows']:
        m=r['metrics']; fmt=lambda k: 'N/A — rejected input gold' if m is None else ' / '.join(str(m[k][x]) for x in ('tp','fp','fn'))
        lines.append(f"| {r['key']} | {r['status']} | {r['error'] or '—'} | {fmt('facts')} | {fmt('findings')} |")
    lines+=['','Failed supported packets retain all gold false negatives. Rejected-input packets remain in total and rejection counts, not in successful fact denominators.',
            '', 'See report.json for per-field/per-kind counts, candidate diagnostics, negative packet and item false positives, versions, timing and cost provenance.', '', '## Blockers','']+['- '+b for b in report['blockers']]
    return '\n'.join(lines)+'\n'


def main():
    parser=argparse.ArgumentParser(description='Offline synthetic evaluation. Real spending is fail-closed.')
    parser.add_argument('--provider',choices=['baseline','fake','replay','real'],default='fake')
    parser.add_argument('--split',choices=['dev','test'],default='dev')
    parser.add_argument('--ack-test-exposure',action='store_true')
    parser.add_argument('--max-cost-usd',type=str)
    parser.add_argument('--recording',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--check-gates',action='store_true',help='Exit nonzero when any offline gate is unmet; cannot establish release readiness')
    parser.add_argument('--compare',type=Path,help='Fail if factual/finding counts differ from this report')
    args=parser.parse_args()
    if args.provider=='real':
        parser.error('Real evaluation disabled: an authorized cap alone is insufficient; the accounting ledger still requires operator authorization, synthetic-input binding and recording/recovery integration before real execution. No request sent.')
    if args.split=='test' and not args.ack_test_exposure: parser.error('Frozen test inspection requires --ack-test-exposure; do not tune against inspected tests.')
    if args.recording and args.provider!='replay': parser.error('--recording is only valid with --provider replay')
    if args.provider=='replay' and not args.recording: parser.error('--recording is required for replay')
    if args.output.exists(): parser.error('Output directory must be new; existing evidence is never overwritten')
    args.output.mkdir(parents=True)
    dump(args.output/'status.json',dict(state='running',provider=args.provider,split=args.split))
    try:
        report,capture=asyncio.run(run(args.split,args.provider,read(args.recording) if args.recording else None))
        report['commit']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        report['working_tree_dirty']=bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip())
        report['created_at']=datetime.now(timezone.utc).isoformat()
        dump(args.output/'recording.json',capture)
        report['recording_sha256']=sha((args.output/'recording.json').read_bytes())
        dump(args.output/'report.json',report)
        (args.output/'report.md').write_text(markdown(report))
        dump(args.output/'status.json',dict(state='complete',release_status='BLOCKED'))
        if args.compare and comparable(read(args.compare))!=comparable(report):
            raise ValueError('Regression comparison failed: per-case or aggregate count drift')
        if args.check_gates and not all(report['offline_gates'].values()):
            raise ValueError('Offline gates unmet; see report.json. No release claim is permitted.')
        print(json.dumps(dict(output=str(args.output),summary=report['summary'],release_status='BLOCKED')))
    except BaseException:
        dump(args.output/'status.json',dict(state='interrupted_or_failed',metrics_valid=(args.output/'report.json').exists()))
        raise

if __name__=='__main__': main()
