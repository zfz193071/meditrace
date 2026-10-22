"""Explicit multiset denominators. Empty denominators are unmeasured, never 100%."""
from collections import Counter
import hashlib

PREFIXES = {'medications': 'Medications: ', 'report.description': 'Report: '}
KEY_FIELDS = ('patient.name', 'patient.dob', 'medications', 'allergies', 'report.description')


def value(fact):
    raw = fact['value_raw']
    prefix = PREFIXES.get(fact['field_key'])
    return raw[len(prefix):] if prefix and raw.startswith(prefix) else raw


def signature(fact):
    return (fact['field_key'], value(fact), fact['assertion_status'], fact.get('temporal_context'))


def finding_keys(findings):
    return Counter((f['rule_id'], f['kind'], field) for f in findings for field in f['field_keys'])


def counts(predicted, gold):
    tp = sum((predicted & gold).values())
    return dict(tp=tp, fp=sum(predicted.values())-tp, fn=sum(gold.values())-tp)


def ratio(numerator, denominator):
    return dict(numerator=numerator, denominator=denominator,
                value=numerator / denominator if denominator else None)


def intact(e, pages):
    page = pages.get((e['document_id'], e['page_number']))
    if page is None: return False
    start, end = e['start_cp'], e['end_cp']
    return (0 <= start < end <= len(page) and page[start:end] == e['quote']
            and hashlib.sha256(page.encode()).hexdigest() == e['text_hash'])


def score(result, gold, pages):
    """gold is provisional. Exact annotated-support agreement is NOT human validation."""
    result = result or dict(facts=[], evidence=[], findings=[])
    gold = gold or dict(facts=[], evidence=[], findings=[])
    facts, expected = result['facts'], gold['facts']
    evidence = {e['id']: e for e in result['evidence']}
    expected_evidence = {e['id']: e for e in gold['evidence']}
    fact_counts = counts(Counter(map(signature, facts)), Counter(map(signature, expected)))
    by_field = {field: counts(Counter(signature(f) for f in facts if f['field_key']==field),
                              Counter(signature(f) for f in expected if f['field_key']==field))
                for field in sorted(set([f['field_key'] for f in facts+expected]))}
    complete = supported = missing_citations = invalid_citations = unsupported = 0
    for f in facts:
        refs = f.get('evidence_ids', [])
        valid = bool(refs) and all(eid in evidence and intact(evidence[eid], pages) for eid in refs)
        complete += valid
        if not refs: missing_citations += 1
        elif not valid: invalid_citations += 1
        # Both fact semantics and every cited span must match a gold-supported source.
        candidates = [g for g in expected if signature(g) == signature(f)]
        def supports(g):
            anchors = [expected_evidence[eid] for eid in g['evidence_ids']]
            return all(any(evidence[eid]['document_id']==a['document_id'] and evidence[eid]['page_number']==a['page_number']
                       and evidence[eid]['start_cp'] >= a['start_cp'] and evidence[eid]['end_cp'] <= a['end_cp']
                       for a in anchors) for eid in refs)
        agrees = valid and any(supports(g) for g in candidates)
        supported += agrees
        unsupported += valid and not agrees
    findings = counts(finding_keys(result['findings']), finding_keys(gold['findings']))
    kinds = sorted({f['kind'] for f in result['findings']+gold['findings']})
    differences = dict(unmatched_facts=list((Counter(map(signature,facts))-Counter(map(signature,expected))).elements()),
        missing_facts=list((Counter(map(signature,expected))-Counter(map(signature,facts))).elements()),
        extra_findings=list((finding_keys(result['findings'])-finding_keys(gold['findings'])).elements()),
        missing_findings=list((finding_keys(gold['findings'])-finding_keys(result['findings'])).elements()))
    return dict(differences=differences, facts=fact_counts, by_field=by_field, findings=findings,
        by_kind={kind: counts(finding_keys([f for f in result['findings'] if f['kind']==kind]),
                             finding_keys([f for f in gold['findings'] if f['kind']==kind])) for kind in kinds},
        citation_integrity=ratio(complete,len(facts)), provisional_support=ratio(supported,len(facts)),
        missing_citations=missing_citations, invalid_citations=invalid_citations, unsupported_citations=unsupported,
        lexically_absent_values=sum(not any(value(f) in page for page in pages.values()) for f in facts),
        unannotated_facts=fact_counts['fp'], critical_unannotated_facts=sum(by_field.get(f,{}).get('fp',0) for f in KEY_FIELDS),
        clean_negative=not gold['findings'], negative_false_positive_items=len(result['findings']) if not gold['findings'] else 0,
        negative_identity_false_positives=sum(f['kind']=='identity_mismatch' for f in result['findings']) if not gold['findings'] else 0)


def aggregate(rows):
    scored = [r['metrics'] for r in rows if r['metrics'] is not None]
    def summed(key): return {k:sum(s[key][k] for s in scored) for k in ('tp','fp','fn')}
    def rates(c): return dict(**c, precision=ratio(c['tp'],c['tp']+c['fp']), recall=ratio(c['tp'],c['tp']+c['fn']))
    def grouped(key):
        return {group:rates({k:sum(s[key].get(group,{}).get(k,0) for s in scored) for k in ('tp','fp','fn')})
                for group in sorted({group for s in scored for group in s[key]})}
    negatives=[s for s in scored if s['clean_negative']]
    return dict(packets_total=len(rows), packets_scored=len(scored),
        successful=sum(r['status']=='succeeded' for r in rows),
        rejected=sum(r['status']=='rejected' for r in rows), failed=sum(r['status']=='failed' for r in rows),
        facts=rates(summed('facts')), findings=rates(summed('findings')), by_field=grouped('by_field'), by_kind=grouped('by_kind'),
        citation_integrity=ratio(sum(s['citation_integrity']['numerator'] for s in scored),sum(s['citation_integrity']['denominator'] for s in scored)),
        provisional_support=ratio(sum(s['provisional_support']['numerator'] for s in scored),sum(s['provisional_support']['denominator'] for s in scored)),
        human_verified_citation_support=None,
        negative_packets=ratio(sum(s['negative_false_positive_items']>0 for s in negatives),len(negatives)),
        negative_false_positive_items=sum(s['negative_false_positive_items'] for s in negatives),
        negative_identity_false_positives=sum(s['negative_identity_false_positives'] for s in negatives),
        **{key:sum(s[key] for s in scored) for key in ('missing_citations','invalid_citations','unsupported_citations','unannotated_facts','critical_unannotated_facts','lexically_absent_values')})
