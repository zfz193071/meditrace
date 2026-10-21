"""Normalized result graph; written in the same transaction as successful settlement."""
from uuid import uuid5
import sqlalchemy as sa

from ..persistence import models as m
from ..schemas import Evidence, Fact, Finding, ReviewResult


def persist(conn, run, extraction, evaluation, check_deadline):
    rid = run["id"]
    for evidence in extraction.evidence:
        check_deadline()
        conn.execute(m.evidence.insert().values(**evidence.model_dump(), run_id=rid, revision_id=run["revision_id"]))
    for fact in extraction.facts:
        check_deadline()
        conn.execute(m.facts.insert().values(**fact.model_dump(exclude={"evidence_ids"}), run_id=rid))
        for eid in set(fact.evidence_ids):
            conn.execute(m.fact_evidence.insert().values(fact_id=fact.id, evidence_id=eid, run_id=rid))
    for finding in evaluation.findings:
        check_deadline()
        # Pure rule fingerprints are stable across runs; database IDs are run-scoped.
        fid = uuid5(rid, str(finding.id))
        conn.execute(m.findings.insert().values(**finding.model_dump(exclude={
            "id", "fact_ids", "evidence_ids", "checked_document_ids"}), id=fid, run_id=rid))
        for fact_id in finding.fact_ids:
            conn.execute(m.finding_facts.insert().values(finding_id=fid, fact_id=fact_id, run_id=rid))
        for eid in finding.evidence_ids:
            conn.execute(m.finding_evidence.insert().values(finding_id=fid, evidence_id=eid, run_id=rid))
        for did in finding.checked_document_ids:
            conn.execute(m.finding_documents.insert().values(finding_id=fid, document_id=did, run_id=rid,
                                                           revision_id=run["revision_id"]))


def load(conn, run):
    rid = run["id"]
    evidence = [Evidence(**{key: row[key] for key in Evidence.model_fields}) for row in conn.execute(
        sa.select(m.evidence).where(m.evidence.c.run_id == rid).order_by(m.evidence.c.id)).mappings()]
    def refs(table, source, source_id, target):
        return conn.execute(sa.select(table.c[target]).where(table.c.run_id == rid,
            table.c[source] == source_id).order_by(table.c[target])).scalars().all()
    facts = [Fact(**{key: row[key] for key in Fact.model_fields if key != "evidence_ids"},
        evidence_ids=refs(m.fact_evidence, "fact_id", row["id"], "evidence_id")) for row in conn.execute(
            sa.select(m.facts).where(m.facts.c.run_id == rid).order_by(m.facts.c.id)).mappings()]
    findings = [Finding(**{key: row[key] for key in Finding.model_fields if key not in (
        "fact_ids", "evidence_ids", "checked_document_ids")},
        fact_ids=refs(m.finding_facts, "finding_id", row["id"], "fact_id"),
        evidence_ids=refs(m.finding_evidence, "finding_id", row["id"], "evidence_id"),
        checked_document_ids=refs(m.finding_documents, "finding_id", row["id"], "document_id")) for row in conn.execute(
            sa.select(m.findings).where(m.findings.c.run_id == rid).order_by(m.findings.c.rule_id, m.findings.c.kind, m.findings.c.id)).mappings()]
    return ReviewResult(run_id=rid, revision_id=run["revision_id"], mode=run["mode"], created_at=run["finished_at"],
        checklist_version=run["checklist_version"], prompt_version=run["prompt_version"], schema_version=run["schema_version"],
        facts=facts, evidence=evidence, findings=findings)
