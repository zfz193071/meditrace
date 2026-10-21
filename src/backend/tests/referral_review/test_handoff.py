"""Confirmed exports use synthetic snapshots only; no model, storage or payment calls."""
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID, uuid4
import copy
import json
import pytest
import pypdfium2 as pdfium
from pypdf import PdfReader
import sqlalchemy as sa
from referral_review.errors import ApiError
from referral_review.handoff import model, pdf
from referral_review.handoff.contracts import HandoffView
from referral_review.persistence import models as m
from referral_review.packets.service import _hash
from referral_review.reviews.contracts import SnapshotResponse
from test_identity import auth_client, sign_in
from test_packets import workspace, create, upload, save
from test_reviews import review, resolve, draft, confirm

ROOT = Path(__file__).resolve().parents[4]


def snapshot(r, unresolved=True):
    assert resolve(r, action="defer" if unresolved else "resolve", reason="Synthetic sender clarification",
        corrected_value="Synthetic reviewer correction", linked_evidence_ids=[r["eid"]]).status_code == 201
    assert draft(r, 1, mode="assisted", run_id=r["rid"], fields={"note": "Synthetic José 王明"}).status_code == 200
    response = confirm(r, 2)
    assert response.status_code == 201, response.text
    return SnapshotResponse.model_validate(response.json())


def export(r, sid, format="txt"):
    return r["client"].get(f"/packets/{r['pid']}/snapshots/{sid}/export", params={"format": format})


def test_screen_text_and_pdf_keep_confirmed_content_and_provenance(review):
    r = review
    snap = snapshot(r)
    original = copy.deepcopy(snap.payload)
    view = model.build(snap)
    response = r["client"].get(f"/packets/{r['pid']}/snapshots/{snap.id}/handoff")
    assert response.json() == view.model_dump(mode="json")
    txt = export(r, snap.id)
    assert txt.status_code == 200 and txt.text == model.text(view)
    for phrase in ["Identity unresolved", "unresolved items remain", "Synthetic reviewer correction", "Synthetic José 王明",
                   "Reviewer supplied", "Synthetic sender clarification", "Document", "page 1", "Source statement", str(snap.id)]:
        assert phrase in txt.text
    data = export(r, snap.id, "pdf")
    assert data.status_code == 200 and data.content.startswith(b"%PDF-"), data.text[:80] if data.status_code != 200 else ""
    reader = PdfReader(BytesIO(data.content))
    extracted = "\n".join(page.extract_text() for page in reader.pages)
    # fpdf2 line wrapping does not change confirmed values.
    assert "Synthetic reviewer correction" in extracted
    with pdfium.PdfDocument(data.content) as document:
        unicode_text = "\n".join(page.get_textpage().get_text_range() for page in document)
    assert "Synthetic José 王明" in unicode_text
    assert str(snap.id) in extracted
    assert "Identity unresolved" in extracted
    for index, page in enumerate(reader.pages, 1):
        assert f"Page {index} / {len(reader.pages)}" in page.extract_text()
    for response in [txt, data]:
        assert response.headers["cache-control"] == "private, no-store"
        assert response.headers["content-security-policy"] == "sandbox"
        assert str(snap.id) in response.headers["content-disposition"]
    assert snap.payload == original
    with r["identity"].engine.begin() as conn:
        assert conn.execute(sa.select(sa.func.count()).select_from(m.usage_reservations)).scalar_one() == 0
        assert conn.execute(sa.select(sa.func.count()).select_from(m.memberships)).scalar_one() == 0


def test_old_snapshot_uses_old_correction_and_gets_derived_history_mark(review):
    r = review
    snap = snapshot(r)
    assert resolve(r, 3, "resolve", corrected_value="Later correction").status_code == 201
    assert draft(r, 4, fields={"note": "Later draft"}).status_code == 200
    txt = export(r, snap.id).text
    assert "Historical revision" in txt and "Synthetic reviewer correction" in txt
    assert "Later correction" not in txt and "Later draft" not in txt
    stored = r["client"].get(f"/packets/{r['pid']}/snapshots/{snap.id}").json()
    assert stored["payload_hash"] == snap.payload_hash and stored["payload"] == snap.payload
    data = export(r, snap.id, "pdf")
    assert all("Historical revision" in page.extract_text() for page in PdfReader(BytesIO(data.content)).pages)


def test_manual_missing_fields_and_no_run_are_explicit(review):
    r = review
    snap = confirm(r, mode="manual", run_id=None).json()
    txt = export(r, snap["id"]).text
    assert "Not automatically checked" in txt and "None - manual review" in txt
    assert "Not recorded in the confirmed source result" in txt
    assert "No source evidence attached" in txt and "completeness has not been established" in txt


@pytest.mark.parametrize("blocked", ["anonymous", "foreign", "deleted", "expired"])
def test_export_access_checks(review, blocked):
    r = review
    snap = snapshot(r)
    if blocked == "anonymous":
        r["client"].cookies.clear()
    elif blocked == "foreign":
        r["transport"].subject = 55555
        sign_in(r["client"])
    elif blocked == "deleted":
        r["client"].delete(f"/packets/{r['pid']}", headers=r["headers"] | {"Idempotency-Key": uuid4().hex})
    else:
        r["clock"][0] += timedelta(days=8)
        sign_in(r["client"])
    expected = 401 if blocked == "anonymous" else 404
    for format in ["txt", "pdf"]:
        assert export(r, snap.id, format).status_code == expected
    assert r["client"].get(f"/packets/{r['pid']}/snapshots/{snap.id}/handoff").status_code == expected


def test_unknown_snapshot_format_and_shared_rate_limit(review):
    r = review
    snap = snapshot(r)
    assert export(r, uuid4()).status_code == 404
    assert export(r, snap.id, "html").status_code == 422
    for _ in range(10):
        assert export(r, snap.id).status_code == 200
    assert export(r, snap.id, "pdf").json()["error"]["code"] == "RATE_LIMITED"
    r["clock"][0] += timedelta(minutes=1)
    assert export(r, snap.id).status_code == 200


def test_concurrent_exports_use_persisted_account_limit(review):
    r = review
    snap = snapshot(r)
    for _ in range(9):
        assert export(r, snap.id).status_code == 200
    barrier = Barrier(2)
    token = r["client"].cookies.get(r["identity"].session_cookie)
    def attempt(_):
        from referral_review.handoff import Handoff
        barrier.wait(timeout=10)
        try:
            Handoff(r["identity"]).export(token, UUID(r["pid"]), snap.id, "txt")
            return "exported"
        except ApiError as exc:
            return exc.code.value
    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(attempt, range(2))) == ["RATE_LIMITED", "exported"]


def test_membership_expired_or_zero_does_not_gate_export(review):
    r = review
    snap = snapshot(r)
    with r["identity"].engine.begin() as conn:
        oid = uuid4()
        conn.execute(m.orders.insert().values(id=oid, owner_id=r["owner"], environment="test", price_id="synthetic",
            amount=100, currency="usd", state="paid", created_at=r["clock"][0]))
        conn.execute(m.memberships.insert().values(owner_id=r["owner"], source_order_id=oid, environment="test",
            valid_from=r["clock"][0] - timedelta(days=2), valid_until=r["clock"][0] - timedelta(days=1), granted_units=0))
    assert export(r, snap.id).status_code == 200


def test_deletion_during_render_is_reauthorized(review, monkeypatch):
    r = review
    snap = snapshot(r)
    def render(_):
        with r["identity"].engine.begin() as conn:
            conn.execute(m.packets.update().where(m.packets.c.id == UUID(r["pid"])).values(deleted_at=r["clock"][0]))
        return b"%PDF-synthetic"
    monkeypatch.setattr(pdf, "render", render)
    assert export(r, snap.id, "pdf").status_code == 404


def test_oversize_returns_explicit_error_and_never_truncated_success(review, monkeypatch):
    r = review
    snap = snapshot(r)
    monkeypatch.setattr(pdf, "MAX_BYTES", 100)
    assert export(r, snap.id).json()["error"]["code"] == "EXPORT_TOO_LARGE"
    assert export(r, snap.id, "pdf").json()["error"]["code"] == "EXPORT_TOO_LARGE"
    monkeypatch.setattr(pdf, "MAX_PAGES", 1)
    with pytest.raises(ApiError) as caught:
        pdf.render(model.build(snap))
    assert caught.value.code == "EXPORT_TOO_LARGE"


def test_unsupported_glyph_is_not_silently_dropped_text_stays_complete(review):
    r = review
    assert draft(r, fields={"note": "Synthetic 😀"}).status_code == 200
    snap = confirm(r, 1, mode="manual", run_id=None).json()
    assert export(r, snap["id"], "pdf").json()["error"]["code"] == "EXPORT_UNSUPPORTED_TEXT"
    assert "Synthetic 😀" in export(r, snap["id"]).text


def test_snapshot_integrity_failure_and_no_input_mutation(review):
    snap = snapshot(review)
    corrupt = snap.model_copy(deep=True)
    corrupt.payload["status"] = "Forged"
    with pytest.raises(ValueError, match="Invalid confirmed snapshot"):
        model.build(corrupt)
    assert snap.payload["status"] != "Forged"


def test_bundled_demo_same_model_contract_and_print_text_fixtures():
    views = json.loads((ROOT / "src/frontend/lib/referral-api/demo-handoffs.json").read_text())
    for case, data in views.items():
        view = HandoffView.model_validate(data)
        output = model.text(view)
        assert "Precomputed synthetic example" in output
        assert "Source index" in output and "Snapshot SHA-256" in output
        if case == "dev-01":
            assert "Identity unresolved" in output and "page 1" in output
    short = HandoffView.model_validate_json((ROOT / "output/pdf/handoff-short.json").read_text())
    assert model.text(short) == (ROOT / "output/pdf/handoff-short.txt").read_text()
    for name in ["short", "long"]:
        reader = PdfReader(ROOT / f"output/pdf/handoff-{name}.pdf")
        content = "\n".join(page.extract_text() for page in reader.pages)
        with pdfium.PdfDocument(str(ROOT / f"output/pdf/handoff-{name}.pdf")) as document:
            unicode_text = "\n".join(page.get_textpage().get_text_range() for page in document)
        assert all(value in unicode_text for value in ["José", "Łukasz", "王明", "Ольга", "Δημήτρης"])
        assert len(reader.pages) > 1
        assert "Snapshot SHA-256" in content
        if name == "long":
            assert "Synthetic note 018" in " ".join(content.split()) and "page 2" in " ".join(content.split())
