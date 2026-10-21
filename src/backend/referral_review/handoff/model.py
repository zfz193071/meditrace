"""Pure projection of a confirmed snapshot. Never reads live facts or drafts."""
from ..packets.service import _hash
from ..reviews.contracts import SnapshotResponse
from ..schemas import ReviewResult
from .contracts import HandoffSection, HandoffView

FIELDS = {
    "patient.name": "Patient name", "patient.dob": "Date of birth",
    "referrer.name": "Referrer", "referrer.contact": "Referrer contact", "recipient": "Recipient",
    "referral.reason": "Referral reason", "medications": "Medications", "allergies": "Allergies",
    "attachment_reference": "Attachment reference", "report.description": "Report description",
}
ASSERTIONS = {"stated": "Recorded in source", "explicitly_none": "Explicitly none recorded", "unknown": "Unknown in source"}
GROUPS = (
    ("Identity and referral details", ("patient.name", "patient.dob", "referrer.name", "referrer.contact", "recipient")),
    ("Referral reason", ("referral.reason",)), ("Medications", ("medications",)),
    ("Allergies", ("allergies",)), ("Reports and attachment references", ("report.description", "attachment_reference")),
)


def build(snapshot: SnapshotResponse) -> HandoffView:
    payload = snapshot.payload
    if payload.get("schema_version") != "review-snapshot-v1" or _hash(payload) != snapshot.payload_hash:
        raise ValueError("Invalid confirmed snapshot")
    if (payload["packet_id"] != str(snapshot.packet_id) or payload["revision_id"] != str(snapshot.revision_id)
        or payload["review_version"] != snapshot.review_version):
        raise ValueError("Snapshot envelope mismatch")
    result = ReviewResult.model_validate(payload["result"]) if payload.get("result") else None
    if result and (result.run_id != snapshot.run_id or result.revision_id != snapshot.revision_id):
        raise ValueError("Result does not belong to snapshot")
    facts = result.facts if result else []
    evidence = sorted(result.evidence, key=lambda e: (str(e.document_id), e.page_number, e.start_cp, str(e.id))) if result else []
    refs = {str(item.id): f"S{index}" for index, item in enumerate(evidence, 1)}
    def sources(ids):
        return ", ".join(refs[str(eid)] for eid in ids)
    sections = []
    def section(heading, paragraphs):
        sections.append(HandoffSection(heading=heading, paragraphs=paragraphs))
    warnings = list(payload["warnings"])
    if snapshot.historical:
        warnings.insert(0, "Historical revision - not the current confirmed review")
    if result and result.mode != "real":
        warnings.append(f"Synthetic demonstration - {result.mode} result; not a live AI review")
    if payload["mode"] == "manual" and "Not automatically checked" not in warnings:
        warnings.append("Not automatically checked")
    for heading, keys in GROUPS:
        lines = []
        for key in keys:
            matching = [fact for fact in facts if fact.field_key == key]
            if not matching:
                lines.append(f"{FIELDS[key]}: Not recorded in the confirmed source result.")
            for fact in matching:
                temporal = f"; context: {fact.temporal_context}" if fact.temporal_context else ""
                lines.append(f"{FIELDS[key]}: {fact.value_raw}\nSource statement; {ASSERTIONS[fact.assertion_status]}{temporal}. [{sources(fact.evidence_ids)}]")
        section(heading, lines)
    decisions = payload["decisions"]
    unresolved, reviewed = [], []
    for finding in result.findings if result else []:
        decision = decisions.get(str(finding.id))
        if decision is None or decision["content"]["status"] == "open":
            raise ValueError("Snapshot contains unreviewed findings")
        content = decision["content"]
        labels = ", ".join(FIELDS[key] for key in finding.field_keys)
        line = f"{finding.rule_id} - {labels} [{content['status']}]\n{finding.message}"
        if content.get("corrected_value") is not None:
            line += f"\nReviewer supplied correction: {content['corrected_value']}"
        line += f"\nReason: {content['reason'] or 'No reason recorded.'}"
        linked = content.get("linked_evidence_ids", [])
        line += f"\nCorrection sources: [{sources(linked)}]." if linked else "\nNo additional evidence linked by reviewer."
        if finding.evidence_ids:
            line += f"\nFinding sources: [{sources(finding.evidence_ids)}]."
        line += f"\nDecision {decision['id']}; reviewer {decision['actor_id']}; review v{decision['review_version']}; {decision['created_at']}."
        (unresolved if content["status"] == "unresolved" else reviewed).append(line)
    section("Unresolved items", unresolved or ["No unresolved items recorded." if result else "Not automatically checked; completeness has not been established."])
    section("Reviewer decisions and corrections", reviewed or ["No other reviewer decisions recorded."])
    fields = payload.get("handoff", {}).get("fields", {})
    section("Reviewer supplied additions", [f"{FIELDS.get(key, key)}: {item['value']}\nReviewer supplied; no source citation is implied."
        for key, item in sorted(fields.items())] or ["No reviewer additions recorded."])
    section("Source index", [f"[{refs[str(e.id)]}] Document {e.document_id}; page {e.page_number}; characters {e.start_cp}-{e.end_cp} (end exclusive).\n{e.quote}"
        for e in evidence] or ["No source evidence attached to this confirmation."])
    section("Confirmation and version", [
        f"Snapshot: {snapshot.id}\nPacket: {snapshot.packet_id}\nRevision: {payload['revision_number']} ({snapshot.revision_id})\nReview version: {snapshot.review_version}",
        f"Confirmed: {snapshot.confirmed_at.isoformat()}\nReviewer: {snapshot.confirmed_by}\nMode: {payload['mode']}\nRun: {snapshot.run_id or 'None - manual review'}",
        f"Checklist: {result.checklist_version if result else 'Not automatically checked'}\nSnapshot SHA-256: {snapshot.payload_hash}",
        "Referral material handoff only. This is not a diagnosis, referral approval or proof of completeness.",
    ])
    return HandoffView(snapshot_id=snapshot.id, packet_id=snapshot.packet_id, revision_id=snapshot.revision_id,
        review_version=snapshot.review_version, confirmed_at=snapshot.confirmed_at, payload_hash=snapshot.payload_hash,
        historical=snapshot.historical, title="Referral review handoff", status=payload["status"], warnings=warnings, sections=sections)


def text(view: HandoffView) -> str:
    blocks = [view.title, view.status, *view.warnings]
    for section in view.sections:
        blocks.extend([section.heading, *section.paragraphs])
    return "\n\n".join(blocks) + "\n"
