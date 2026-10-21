"""Operator tools never overwrite receipts or clean objects from another store."""

import importlib.util
import json
from pathlib import Path
import sys

import pytest


@pytest.fixture
def blob_cli(monkeypatch):
    path = Path(__file__).resolve().parents[4] / "scripts/check_private_blob.py"
    spec = importlib.util.spec_from_file_location("check_private_blob", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    calls = []
    class Store:
        def __init__(self, token):
            pass
        def write(self, key, body, media):
            calls.append(("write", key))
            raise RuntimeError("secret-provider-response")
        def delete(self, key):
            calls.append(("delete", key))
    monkeypatch.setattr(module, "PrivateBlobStore", Store)
    monkeypatch.setenv("BLOB_READ_WRITE_TOKEN", "vercel_blob_rw_syntheticstore_syntheticsecret")
    return module, calls


def test_cli_ambiguous_put_preserves_receipt_and_attempts_deletion(blob_cli, monkeypatch, tmp_path, capsys):
    module, calls = blob_cli
    receipt = tmp_path / "receipt.json"
    monkeypatch.setattr(sys, "argv", ["check_private_blob", "roundtrip", "--receipt", str(receipt)])
    with pytest.raises(SystemExit) as exc:
        module.main()
    assert exc.value.code == 1
    record = json.loads(receipt.read_text())
    assert calls == [("write", record["key"]), ("delete", record["key"])]
    assert receipt.stat().st_mode & 0o777 == 0o600
    assert "secret-provider-response" not in capsys.readouterr().err
    assert "syntheticsecret" not in receipt.read_text()
    calls.clear()
    with pytest.raises(SystemExit):
        module.main()
    assert not calls  # existing receipt cannot be overwritten


def test_cli_cleanup_rejects_another_store_or_untrusted_key(blob_cli, monkeypatch, tmp_path):
    module, calls = blob_cli
    receipt = tmp_path / "receipt.json"
    monkeypatch.setattr(sys, "argv", ["check_private_blob", "cleanup", "--receipt", str(receipt)])
    receipt.write_text(json.dumps({"store_hash": "wrong", "key": "rr-" + "a"*32 + "-" + "b"*32 + ".bin"}))
    with pytest.raises(SystemExit):
        module.main()
    receipt.write_text(json.dumps({"store_hash": "wrong", "key": "https://example.test/file"}))
    with pytest.raises(SystemExit):
        module.main()
    assert not calls
