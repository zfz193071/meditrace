"""Recovery CLI preview/apply boundaries; all recordings and costs are synthetic."""
import asyncio
from contextlib import contextmanager
from dataclasses import asdict, replace
import json
from pathlib import Path
import sys

import pytest
import sqlalchemy as sa

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "evals/referral-review"))
from referral_eval import recovery
from referral_eval.journal import Journal
from referral_review.persistence import models as m
from referral_review.persistence.test_database import Receipt, fingerprint
from test_evaluation_coordinator import setup, session, fake
from test_persistence import engine, empty_engine
from test_usage import values
from test_usage_pg import pg


def files(tmp_path, plan, receipt=None):
    path = tmp_path / "plan.json"
    path.write_text(plan.model_dump_json())
    owned = tmp_path / "owned.json"
    owned.write_text(json.dumps(asdict(receipt or Receipt("rr_test_" + "a" * 32, "b" * 32, "c" * 64))))
    owned.chmod(0o600)
    return ["--plan", str(path), "--database-receipt", str(owned)]


def test_preview_does_not_settle_apply_requires_hash_and_no_transport(engine, setup, tmp_path, monkeypatch, capsys):
    with session(engine, setup) as run:
        def interrupted(*args, **kw): raise RuntimeError("injected")
        monkeypatch.setattr(run.ledger, "settle", interrupted)
        with pytest.raises(RuntimeError): asyncio.run(run.execute("dev-04", fake()))
    if engine.dialect.name == "postgresql":
        url = engine.url.render_as_string(hide_password=False)
        monkeypatch.setenv("TEST_DATABASE_URL", url)
        with engine.connect() as conn:
            schema = conn.execute(sa.text("SELECT current_schema()")).scalar_one()
            token = conn.execute(sa.text("SELECT token FROM _meditrace_test_guard")).scalar_one()
        args = files(tmp_path, setup[0], Receipt(schema, token, fingerprint(url)))
    else:
        args = files(tmp_path, setup[0])
        @contextmanager
        def owned(receipt, *, apply):
            yield engine
        monkeypatch.setattr(recovery, "owned_engine", owned)
    before = values(engine, m.evaluation_attempts)
    journal = Path(setup[0].output)
    before_files = {f.name: (f.read_bytes(), f.stat().st_mtime_ns) for f in journal.iterdir()}
    recovery.main(args)
    result = json.loads(capsys.readouterr().out)
    assert result["operation"] == "preview" and result["samples"][0]["state"] == "dispatched"
    assert values(engine, m.evaluation_attempts) == before
    assert {f.name: (f.read_bytes(), f.stat().st_mtime_ns) for f in journal.iterdir()} == before_files
    with pytest.raises(SystemExit): recovery.main(args + ["--apply"])
    assert values(engine, m.evaluation_attempts) == before
    recovery.main(args + ["--apply", "--confirm-plan", setup[0].sha256])
    result = json.loads(capsys.readouterr().out)
    assert result["operation"] == "reconcile" and result["samples"][0]["state"] == "settled"
    assert result["origin"] == "fake" and result["real_measurement"] is False
    recovery.main(args + ["--apply", "--confirm-plan", setup[0].sha256])
    assert json.loads(capsys.readouterr().out) == result


def test_missing_journal_lock_is_rejected_without_recreating(engine, setup):
    with session(engine, setup): pass
    path = Path(setup[0].output) / ".lock"
    path.unlink()
    with pytest.raises(FileNotFoundError):
        with Journal(setup[0], resume=True): pass
    assert not path.exists()


def test_recovery_errors_never_echo_driver_or_environment_secrets(engine, setup, tmp_path, monkeypatch, capsys):
    with session(engine, setup): pass
    args = files(tmp_path, setup[0])
    def forbidden(*args, **kw): raise ValueError("postgresql://private-password/source-payload")
    monkeypatch.setattr(recovery, "owned_engine", forbidden)
    with pytest.raises(SystemExit): recovery.main(args)
    output = capsys.readouterr()
    assert output.out == "" and "private-password" not in output.err and "source-payload" not in output.err
    assert "Evaluation recovery failed" in output.err


@pytest.mark.parametrize("unsafe", ["public", "symlink", "large", "invalid_schema", "duplicate"])
def test_ownership_receipt_rejects_unsafe_files(tmp_path, unsafe):
    path = tmp_path / "owned.json"
    content = asdict(Receipt("rr_test_" + "a" * 32, "b" * 32, "c" * 64))
    if unsafe == "invalid_schema": content["schema"] = "public"
    path.write_text(json.dumps(content))
    path.chmod(0o600)
    if unsafe == "public": path.chmod(0o644)
    if unsafe == "large": path.write_text("x" * 4097)
    if unsafe == "duplicate": path.write_text('{"schema":"public","schema":"other"}')
    if unsafe == "symlink":
        link = tmp_path / "link"
        link.symlink_to(path)
        path = link
    with pytest.raises((ValueError, OSError)): recovery.ownership(path)


def test_recovery_never_falls_back_to_production_database(monkeypatch):
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://do-not-connect")
    with pytest.raises(ValueError, match="no production fallback"):
        with recovery.owned_engine(Receipt("rr_test_" + "a" * 32, "b" * 32, "c" * 64), apply=True): pass


def test_owned_postgres_preview_enforces_readonly_and_apply_checks_marker(pg, monkeypatch):
    url = pg.url.render_as_string(hide_password=False)
    monkeypatch.setenv("TEST_DATABASE_URL", url)
    with pg.connect() as conn:
        schema = conn.execute(sa.text("SELECT current_schema()")).scalar_one()
        token = conn.execute(sa.text("SELECT token FROM _meditrace_test_guard")).scalar_one()
    receipt = Receipt(schema, token, fingerprint(url))
    for bad in (replace(receipt, database_fingerprint="wrong"), replace(receipt, token="0" * 32)):
        with pytest.raises(ValueError):
            with recovery.owned_engine(bad, apply=True): pytest.fail("Ownership must reject before yielding")
    with recovery.owned_engine(receipt, apply=False) as readonly:
        with readonly.begin() as conn:
            assert conn.execute(sa.text("SHOW transaction_read_only")).scalar_one() == "on"
        with pytest.raises(sa.exc.DBAPIError):
            with readonly.begin() as conn: conn.execute(m.usage_controls.insert().values(key="preview-must-fail"))
    assert values(pg, m.usage_controls) == []
    with recovery.owned_engine(receipt, apply=True) as mutable:
        with mutable.begin() as conn:
            assert conn.execute(sa.text("SHOW transaction_read_only")).scalar_one() == "off"
