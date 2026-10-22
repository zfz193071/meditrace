"""Hand-calculated metric checks, replay integrity, fail-closed spending and interruption."""
import asyncio
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'evals/referral-review'))
from referral_eval.metrics import score,aggregate,ratio
from referral_eval.runner import run,comparable,load_cases,parse_case,scripted_output,execute


def example():
    text='Patient: Synthetic Example'
    evidence=dict(id='e',document_id='d',page_number=1,start_cp=0,end_cp=len(text),quote=text,text_hash=hashlib.sha256(text.encode()).hexdigest())
    fact=dict(id='f',field_key='patient.name',value_raw='Synthetic Example',value_normalized=None,assertion_status='stated',temporal_context=None,evidence_ids=['e'])
    finding=dict(rule_id='C02',kind='missing',field_keys=['patient.dob'])
    return dict(facts=[fact],evidence=[evidence],findings=[finding]),{('d',1):text}


def test_hand_computed_false_positive_false_negative_duplicates_and_citations():
    gold,pages=example(); predicted=deepcopy(gold)
    predicted['facts'].append(deepcopy(predicted['facts'][0]))
    predicted['facts'][1].update(id='duplicate',evidence_ids=[])
    predicted['findings']=[dict(rule_id='C07',kind='missing',field_keys=['allergies'])]
    m=score(predicted,gold,pages)
    assert m['facts']==dict(tp=1,fp=1,fn=0)
    assert m['findings']==dict(tp=0,fp=1,fn=1)
    assert m['citation_integrity']==ratio(1,2)
    assert m['missing_citations']==1
    assert score(None,gold,pages)['facts']==dict(tp=0,fp=0,fn=1)
    assert ratio(0,0)['value'] is None


def test_present_quote_does_not_imply_support_and_fabrication_separate():
    gold,pages=example(); predicted=deepcopy(gold)
    predicted['facts'][0]['field_key']='allergies'
    m=score(predicted,gold,pages)
    assert m['citation_integrity']['value']==1
    assert m['provisional_support']['value']==0
    assert m['unsupported_citations']==1
    assert m['lexically_absent_values']==0
    predicted['facts'][0]['value_raw']='Invented person'
    predicted['evidence'][0]['quote']='fabricated quote'
    m=score(predicted,gold,pages)
    assert m['invalid_citations']==1 and m['lexically_absent_values']==1
    assert m['unannotated_facts']==1


def test_wrong_date_status_unit_and_critical_value_are_not_normalized_away():
    gold,pages=example()
    for field,value in [('medications','Med A 5 mg'),('patient.dob','03/04/1980'),('allergies','Unknown')]:
        g=deepcopy(gold);g['facts'][0].update(field_key=field,value_raw=value)
        p=deepcopy(g);p['facts'][0]['value_raw']=value+' changed'
        assert score(p,g,pages)['facts']==dict(tp=0,fp=1,fn=1)
        assert score(p,g,pages)['critical_unannotated_facts']==1


def test_failed_packets_not_discarded_from_recall_or_negative_reporting():
    gold,pages=example();m=score(None,gold,pages)
    clean=deepcopy(gold);clean['findings']=[]
    wrong=deepcopy(clean);wrong['findings']=[dict(rule_id='C02',kind='identity_mismatch',field_keys=['patient.dob'])]
    summary=aggregate([dict(status='failed',metrics=m),dict(status='succeeded',metrics=score(wrong,clean,pages)),dict(status='rejected',metrics=None)])
    assert summary['packets_total']==3 and summary['packets_scored']==2
    assert summary['facts']['recall']==ratio(1,2)
    assert summary['negative_packets']==ratio(1,1)
    assert summary['negative_identity_false_positives']==1


@pytest.fixture(scope='module')
def fake_run(): return asyncio.run(run())


def test_fake_recording_recomputes_counts_without_provider_or_key(fake_run,monkeypatch):
    import referral_eval.runner as runner
    report,capture=fake_run
    async def forbidden(*args,**kwargs): raise AssertionError('Replay must not call an adapter')
    monkeypatch.setattr(runner,'extract',forbidden)
    replay,_=asyncio.run(run(provider='replay',recording=capture))
    # Normalize tuple/list differences introduced by actual JSON recording.
    assert json.dumps(comparable(report),sort_keys=True)==json.dumps(comparable(replay),sort_keys=True)
    assert replay['provider']=='replay' and replay['origin']=='fake'
    assert replay['summary']['human_verified_citation_support'] is None
    assert replay['cost']['actual_usd'] is None
    assert report['summary']['packets_total']==10
    assert report['summary']['rejected']==1
    assert report['release_status']=='BLOCKED'


def test_missing_duplicate_or_foreign_recordings_cannot_improve_denominators(fake_run):
    _,capture=fake_run
    for mutate in ('missing','duplicate','hash','split'):
        changed=deepcopy(capture)
        if mutate=='missing': changed['records'].pop()
        if mutate=='duplicate': changed['records'][-1]=changed['records'][0]
        if mutate=='hash': changed['records'][0]['packet_sha256']='0'*64
        if mutate=='split': changed['split']='test'
        with pytest.raises(ValueError): asyncio.run(run(provider='replay',recording=changed))


def test_interrupted_remainder_retains_denominators_and_replays():
    report,capture=asyncio.run(run(interrupt_after=1))
    assert report['summary']['packets_total']==10
    assert report['summary']['failed']==8
    assert report['summary']['facts']['fn']>0
    replay,_=asyncio.run(run(provider='replay',recording=capture))
    assert comparable(report)==comparable(replay)


def test_fault_injection_false_quote_rejected_not_counted_as_success():
    _,cases=load_cases('dev');_,packet,directory=cases[0]
    docs,issue=parse_case(packet,directory);assert issue is None
    output=scripted_output([p for d in docs for p in d['pages']])
    output['facts'][0]['sources'][0]['quote']='Fabricated citation'
    with pytest.raises(Exception,match='MODEL_INVALID_OUTPUT'):
        asyncio.run(execute(packet,docs,'fake',output))


@pytest.mark.parametrize('cap',[None,'0','-1','nan','100'])
def test_real_cli_never_spends_even_with_cap(tmp_path,cap):
    args=[sys.executable,str(ROOT/'evals/referral-review/run.py'),'--provider','real','--output',str(tmp_path/'out')]
    if cap is not None:args+=['--max-cost-usd',cap]
    result=subprocess.run(args,capture_output=True,text=True)
    assert result.returncode==2 and 'No request sent' in result.stderr
    assert not (tmp_path/'out').exists()


def test_test_split_requires_explicit_exposure_ack(tmp_path):
    result=subprocess.run([sys.executable,str(ROOT/'evals/referral-review/run.py'),'--split','test','--output',str(tmp_path/'out')],capture_output=True,text=True)
    assert result.returncode==2 and 'ack-test-exposure' in result.stderr
    assert not (tmp_path/'out').exists()


def test_programmatic_entry_cannot_mislabel_recordings_or_enable_real():
    with pytest.raises(ValueError,match='offline providers'):
        asyncio.run(run(provider='real'))
    with pytest.raises(ValueError,match='only in replay'):
        asyncio.run(run(provider='fake',recording={'origin':'baseline'}))


def test_manifest_rewrite_cannot_detach_source_from_packet_hash(tmp_path,monkeypatch):
    import shutil
    import referral_eval.runner as runner
    corpus=tmp_path/'corpus';corpus.mkdir()
    shutil.copytree(runner.CORPUS/'dev',corpus/'dev')
    for name in ('manifest.json','freeze.json','checklist.json'):
        shutil.copyfile(runner.CORPUS/name,corpus/name)
    manifest=json.loads((corpus/'manifest.json').read_text())
    packet=json.loads((corpus/'dev/dev-01/packet.json').read_text())
    source=corpus/'dev/dev-01'/packet['documents'][0]['source_path']
    source.write_bytes(source.read_bytes()+b'changed')
    manifest['files'][str(source.relative_to(corpus))]=hashlib.sha256(source.read_bytes()).hexdigest()
    (corpus/'manifest.json').write_text(json.dumps(manifest))
    monkeypatch.setattr(runner,'CORPUS',corpus)
    with pytest.raises(ValueError,match='Packet-bound source hash'):
        runner.load_cases('dev')
