"""Synthetic planning/approval binding only; never grants or spends real budget."""
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
from uuid import uuid4

import pytest
import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "evals/referral-review"))
from referral_eval import planning as p, runner
from referral_eval.files import fixture_bytes, unique_json
from referral_review.documents.parser import PDF_PARSER_VERSION
from referral_review.extraction.contracts import ExtractionRevision
from referral_review.persistence import models as m
from referral_review.errors import ApiError
from test_persistence import engine, empty_engine, NOW
from test_usage import configuration


@pytest.fixture(scope="module")
def preview(tmp_path_factory):
    root = tmp_path_factory.mktemp("evaluation-plan")
    return p.build_plan(batch_id=uuid4(), operator_id=uuid4(), split="dev", output=root / "report",
        model="synthetic-model", price_version="synthetic-v1", input_price=1000, output_price=2000,
        max_cost_usd="0.01")


def approval(plan, **changes):
    return dict(approved_sha256=plan.sha256, approved_max_cost_usd="0.01", operator_id=plan.operator_id,
                settings=configuration([plan.operator_id])) | changes


def revision(key="dev-01"):
    _, cases = runner.load_cases("dev")
    _, packet, directory = next(c for c in cases if c[0]["key"] == key)
    docs, issue = runner.parse_case(packet, directory)
    assert issue is None
    return ExtractionRevision(revision_id=runner.uid(key + ":revision"), pages=[pg for d in docs for pg in d["pages"]])


def test_preview_has_all_denominators_prices_and_no_source_or_approval(preview):
    s = p.summary(preview)
    assert s["samples"] == 10 and s["callable_samples"] == 9
    assert s["rejected_samples"] == [{"key": "dev-10", "reason": "PDF_UNREADABLE_PAGE"}]
    assert s["within_cap"] is True and s["approval"] == "not_recorded" and s["execution"] == "disabled"
    assert s["upper_microusd"] == sum(x.upper_microusd for x in preview.samples)
    assert preview.parser_version == PDF_PARSER_VERSION == runner.versions()["parser"]
    data = p.canonical(preview.model_dump(mode="json"))
    assert b"source_pages" not in data and b"messages" not in data and b"Patient:" not in data
    assert not Path(preview.output).exists()
    assert p.rebuild(preview).sha256 == preview.sha256
    p.validate_approval_binding(preview, **approval(preview))


@pytest.mark.parametrize("change", ["hash", "non_ascii_hash", "operator", "cap", "model", "price", "disabled", "invite"])
def test_changed_approval_or_runtime_settings_are_rejected(preview, change):
    args = approval(preview)
    if change == "hash": args["approved_sha256"] = "0" * 64
    if change == "non_ascii_hash": args["approved_sha256"] = "错误"
    if change == "operator": args["operator_id"] = uuid4()
    if change == "cap": args["approved_max_cost_usd"] = "0.02"
    if change == "model": args["settings"] = configuration([preview.operator_id], RR_MODEL_ID="other-model")
    if change == "price": args["settings"] = configuration([preview.operator_id], RR_MODEL_INPUT_MICROUSD_PER_MILLION_TOKENS=1001)
    if change == "disabled": args["settings"] = configuration([preview.operator_id], REAL_AI_ENABLED=False)
    if change == "invite": args["settings"] = configuration([])
    with pytest.raises(ValueError): p.validate_approval_binding(preview, **args)


@pytest.mark.parametrize("change", ["output", "samples", "implementation", "request", "prompt"])
def test_tampered_plan_requires_new_review(preview, tmp_path, change):
    data = preview.model_dump(mode="json")
    if change == "output": data["output"] = str(tmp_path / "elsewhere")
    if change == "samples": data["samples"] = data["samples"][:-1]
    if change == "implementation": data["implementation_sha256"] = "0" * 64
    if change == "request": data["samples"][0]["request_sha256"] = "0" * 64
    if change == "prompt": data["prompt_version"] = "changed"
    changed = p.Plan.model_validate(data)
    with pytest.raises(ValueError, match="Approval does not match"):
        p.validate_approval_binding(changed, **approval(preview))


def test_current_implementation_and_corpus_must_still_match(preview, monkeypatch, tmp_path):
    with monkeypatch.context() as patch:
        patch.setattr(p, "implementation_hash", lambda: "0" * 64)
        with pytest.raises(ValueError, match="Inputs or implementation changed"):
            p.validate_approval_binding(preview, **approval(preview))
    root = tmp_path / "corpus"
    root.mkdir()
    for name in ("manifest.json", "freeze.json"):
        shutil.copyfile(runner.CORPUS / name, root / name)
    (root / "manifest.json").write_text((root / "manifest.json").read_text() + "\n")
    monkeypatch.setattr(runner, "CORPUS", root)
    with pytest.raises(ValueError, match="Unreviewed corpus"):
        p.validate_approval_binding(preview, **approval(preview))


def test_cap_shortfall_and_existing_output_are_preflight_blockers(preview):
    small = preview.model_copy(update={"max_cost_microusd": 1})
    assert not p.summary(small)["within_cap"]
    with pytest.raises(ValueError, match="exceed approved cap"):
        p.validate_approval_binding(small, **approval(small, approved_max_cost_usd="0.000001"))
    target = Path(preview.output)
    target.mkdir()
    try:
        with pytest.raises(ValueError, match="directory must be new"):
            p.validate_approval_binding(preview, **approval(preview))
    finally:
        target.rmdir()


def test_exact_request_bytes_are_bound_to_selected_sample(preview):
    source = revision()
    request = p.bound_request(preview, "dev-01", source)
    assert isinstance(request, bytes) and p.runner.sha(request) == preview.samples[0].request_sha256
    changed = source.model_copy(deep=True)
    changed.pages[0].document_id = uuid4()
    with pytest.raises(ValueError, match="differs from reviewed inputs"):
        p.bound_request(preview, "dev-01", changed)
    for key in ("dev-10", "test-01", "unknown"):
        with pytest.raises(ValueError, match="not approved"):
            p.bound_request(preview, key, source)


def test_frozen_split_and_subset_require_explicit_selection(preview, tmp_path):
    args = dict(batch_id=uuid4(), operator_id=preview.operator_id, split="test", output=tmp_path / "report",
                model=preview.model, price_version=preview.price_version, input_price=1000, output_price=2000, max_cost_usd="0.01")
    with pytest.raises(ValueError, match="exposure acknowledgement"): p.build_plan(**args)
    for keys in ([], ["test-01", "test-01"], ["dev-01"]):
        with pytest.raises(ValueError, match="Invalid sample selection"):
            p.build_plan(**args, packet_keys=keys, ack_test_exposure=True)


@pytest.mark.parametrize("kind", ["parent", "absolute", "file_symlink", "directory_symlink", "fifo", "size"])
def test_unsafe_fixture_paths_rejected_before_content_read(tmp_path, kind):
    root = tmp_path / "corpus"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.write_text("PRIVATE SYNTHETIC SENTINEL")
    relative = "safe"
    if kind == "parent": relative = "../outside"
    if kind == "absolute": relative = str(outside)
    if kind == "file_symlink": (root / relative).symlink_to(outside)
    if kind == "directory_symlink":
        (root / "nested").symlink_to(tmp_path, target_is_directory=True)
        relative = "nested/outside"
    if kind == "fifo": os.mkfifo(root / relative)
    if kind == "size": (root / relative).write_bytes(b"12345")
    with pytest.raises(ValueError): fixture_bytes(root, relative, limit=4)


def test_reparse_revalidates_packet_bound_source(tmp_path, monkeypatch):
    _, cases = runner.load_cases("dev")
    _, packet, directory = cases[0]
    shutil.copytree(directory, tmp_path / "packet")
    target = tmp_path / "packet" / packet["documents"][0]["source_path"]
    target.write_bytes(b"different synthetic source")
    monkeypatch.setattr(runner, "CORPUS", tmp_path)
    with pytest.raises(ValueError, match="Packet-bound source"):
        runner.parse_case(packet, tmp_path / "packet")


def test_reparse_cannot_follow_replaced_packet_ancestor(tmp_path, monkeypatch):
    _, cases = runner.load_cases("dev")
    _, packet, directory = cases[0]
    shutil.copytree(directory, tmp_path / "outside" / "packet")
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "dev").symlink_to(tmp_path / "outside", target_is_directory=True)
    monkeypatch.setattr(runner, "CORPUS", corpus)
    with pytest.raises(ValueError, match="Invalid fixture path"):
        runner.parse_case(packet, corpus / "dev" / "packet")


def test_pinned_roots_check_exact_consumed_bytes(monkeypatch):
    read = runner.fixture_bytes
    calls = []
    def changed(root, relative, **kwargs):
        calls.append(str(relative))
        body = read(root, relative, **kwargs)
        return body + b"\n" if relative == "manifest.json" else body
    monkeypatch.setattr(runner, "fixture_bytes", changed)
    with pytest.raises(ValueError, match="Unreviewed corpus"):
        runner.load_cases("dev", expected_manifest=p.MANIFEST_SHA256, expected_freeze=p.FREEZE_SHA256)
    assert calls == ["manifest.json", "freeze.json"]  # No referenced file is consumed.


def test_plan_reader_rejects_duplicate_keys_and_unknown_fields(preview, tmp_path):
    path = tmp_path / "plan.json"
    path.write_bytes(p.canonical(preview.model_dump(mode="json")))
    assert p.read_plan(path) == preview
    path.write_text('{"format":"evaluation-plan-v1","format":"evaluation-plan-v1"}')
    with pytest.raises(ValueError, match="Duplicate JSON key"): p.read_plan(path)
    data = preview.model_dump(mode="json") | {"approved": True}
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError): p.read_plan(path)


def test_operator_is_rechecked_in_caller_transaction(engine, preview):
    settings = configuration([preview.operator_id])
    with engine.begin() as conn:
        with pytest.raises(ApiError, match="AUTH_REQUIRED"): p.require_operator(conn, preview, settings)
        conn.execute(m.users.insert().values(id=preview.operator_id, github_subject=str(preview.operator_id),
            display_name="Synthetic operator", created_at=NOW))
        p.require_operator(conn, preview, settings)
        conn.execute(m.users.update().values(disabled_at=NOW))
        with pytest.raises(ApiError, match="AUTH_REQUIRED"): p.require_operator(conn, preview, settings)
    with engine.connect() as conn:
        with pytest.raises(ValueError, match="transaction"): p.require_operator(conn, preview, settings)
    with engine.begin() as conn:
        assert conn.execute(sa.select(sa.func.count()).select_from(m.evaluation_batches)).scalar_one() == 0


def test_cli_preview_is_private_non_overwriting_and_ignores_provider_credentials(tmp_path):
    path = tmp_path / "plan.json"
    output = tmp_path / "report"
    command = [sys.executable, str(ROOT / "evals/referral-review/plan.py"), "--plan-file", str(path),
        "--output", str(output), "--operator-id", str(uuid4()), "--model", "synthetic-model",
        "--price-version", "synthetic-v1", "--input-price", "1000", "--output-price", "2000",
        "--max-cost-usd", "0.01", "--packet", "dev-01"]
    env = dict(os.environ, DEEPSEEK_API_KEY="must-not-appear", DATABASE_URL="invalid-must-not-open",
               RR_UNKNOWN_PREVIEW_OPTION="must-not-load-settings")
    result = subprocess.run(command, capture_output=True, text=True, env=env)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["samples"] == 1
    assert "must-not" not in result.stdout + result.stderr
    assert not output.exists() and stat.S_IMODE(path.stat().st_mode) == 0o600
    original = path.read_bytes()
    repeated = subprocess.run(command, capture_output=True, text=True, env=env)
    assert repeated.returncode == 2 and path.read_bytes() == original
