#!/usr/bin/env python3
"""Generate explicitly synthetic, offline QA samples with the production handoff model."""
import argparse
from datetime import datetime, timezone
import copy
import hashlib
import json
from pathlib import Path
import sys
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/backend"))
from referral_review.handoff.model import build, text
from referral_review.handoff.pdf import render
from referral_review.packets.service import _hash
from referral_review.reviews.contracts import SnapshotResponse


def demo_snapshot(case):
    directory = ROOT / "fixtures/referral-review/public" / case
    result = json.loads((directory / "run.json").read_text())
    review = json.loads((directory / "review-after.json").read_text())
    sid, actor = [uuid5(NAMESPACE_URL, f"meditrace-demo-{case}-{name}") for name in ("snapshot", "reviewer")]
    decisions, states = {}, []
    for version, item in enumerate(review["resolutions"], 1):
        fid = item["finding_id"]
        content = dict(finding_id=fid, action="defer", status=item["status"], reason=item["reason"],
            corrected_value=None, linked_evidence_ids=[], provenance=None)
        decisions[fid] = dict(id=str(uuid5(sid, fid)), actor_id=str(actor), review_version=version,
            created_at=review["confirmed_at"], content=content)
        states.append(dict(finding_id=fid, status=item["status"]))
    warnings = (["Identity unresolved"] if review["identity_unresolved"] else [])
    warnings.append("Precomputed synthetic example - illustrative confirmation only")
    payload = dict(schema_version="review-snapshot-v1", packet_id=review["packet_id"], revision_id=review["revision_id"],
        revision_number=1, manifest_hash="0" * 64, run_id=review["run_id"], mode="assisted", review_version=review["review_version"],
        confirmed_by=str(actor), confirmed_at=review["confirmed_at"], warnings=warnings,
        has_unresolved=review["has_unresolved"], identity_unresolved=review["identity_unresolved"], status=review["heading"],
        result=result, decisions=decisions, finding_states=states, handoff=dict(mode="assisted", fields={}))
    return SnapshotResponse(id=sid, packet_id=review["packet_id"], revision_id=review["revision_id"], run_id=review["run_id"],
        review_version=review["review_version"], confirmed_by=actor, confirmed_at=review["confirmed_at"], payload=payload,
        payload_hash=_hash(payload), has_unresolved=review["has_unresolved"], historical=False)


def sample(long=False):
    sid, pid, revision, actor = [uuid5(NAMESPACE_URL, f"meditrace-handoff-qa-{name}") for name in (str(long), "packet", "revision", "reviewer")]
    now = datetime(2026, 10, 21, tzinfo=timezone.utc)
    fields = {"patient.name": {"value": "Synthetic José Łukasz / 王明 / Ольга / Δημήτρης", "provenance": "Reviewer supplied"},
        "referral.reason": {"value": "Synthetic referral for document review. No clinical conclusion is implied.", "provenance": "Reviewer supplied"}}
    if long:
        for part in range(3):
            fields[f"handoff.notes{part + 1}"] = {"value": "\n".join(f"Synthetic note {i:03}: Please request the missing source report. Identity remains unverified; do not merge the records. " + "LongName" * 15 for i in range(part * 6 + 1, part * 6 + 7)), "provenance": "Reviewer supplied"}
        snapshot = demo_snapshot("dev-01")
        payload = copy.deepcopy(snapshot.payload)
        quote = "Synthetic QA report on source page two; no clinical conclusion."
        document_id, eid, fid = [str(uuid5(snapshot.id, name)) for name in ("qa-report", "qa-evidence", "qa-fact")]
        payload["result"]["evidence"].append(dict(id=eid, document_id=document_id, page_number=2,
            start_cp=0, end_cp=len(quote), quote=quote, text_hash=hashlib.sha256(quote.encode()).hexdigest()))
        payload["result"]["facts"].append(dict(id=fid, field_key="report.description", value_raw=quote,
            value_normalized=None, assertion_status="stated", temporal_context=None, evidence_ids=[eid]))
        payload["warnings"].append("Synthetic QA variant - includes an authored two-page report")
        first_decision = next(iter(payload["decisions"].values()))
        first_decision["content"]["corrected_value"] = "Synthetic reviewer note: identity is still awaiting sender verification."
        payload["handoff"] = dict(mode="assisted", fields=fields)
        return snapshot.model_copy(update={"id": sid, "payload": payload, "payload_hash": _hash(payload), "historical": True})
    payload = dict(schema_version="review-snapshot-v1", packet_id=str(pid), revision_id=str(revision), revision_number=1,
        manifest_hash="0" * 64, run_id=None, mode="manual", review_version=1, confirmed_by=str(actor), confirmed_at=now.isoformat(),
        warnings=["Not automatically checked", "Synthetic QA example - illustrative confirmation only"],
        has_unresolved=False, identity_unresolved=False, status="Reviewed", result=None,
        decisions={}, finding_states=[], handoff=dict(mode="manual", fields=fields))
    return SnapshotResponse(id=sid, packet_id=pid, revision_id=revision, run_id=None, review_version=1,
        confirmed_by=actor, confirmed_at=now, payload=payload, payload_hash=_hash(payload), has_unresolved=False, historical=long)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "output/pdf")
    parser.add_argument("--check-demo", action="store_true")
    args = parser.parse_args()
    demo = {case: build(demo_snapshot(case)).model_dump(mode="json") for case in ("dev-01", "dev-02", "dev-03")}
    serialized = json.dumps(demo, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    demo_path = ROOT / "src/frontend/lib/referral-api/demo-handoffs.json"
    if args.check_demo:
        if demo_path.read_text() != serialized:
            raise SystemExit("Demo handoff model drift")
        print("Demo handoffs match the shared model")
        return
    demo_path.write_text(serialized, encoding="utf-8")
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "handoff-long-source.txt").write_text("Synthetic QA report, cover page.\fSynthetic QA report on source page two; no clinical conclusion.", encoding="utf-8")
    for name, long in [("handoff-short", False), ("handoff-long", True)]:
        view = build(sample(long))
        (args.output / f"{name}.pdf").write_bytes(render(view))
        (args.output / f"{name}.txt").write_text(text(view), encoding="utf-8")
        (args.output / f"{name}.json").write_text(view.model_dump_json(indent=2) + "\n", encoding="utf-8")
        print(name)


if __name__ == "__main__":
    main()
