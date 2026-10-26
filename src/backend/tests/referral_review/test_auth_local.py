import importlib.util
import json
from pathlib import Path

import pytest


spec = importlib.util.spec_from_file_location("auth_local", Path(__file__).resolve().parents[4] / "scripts/referral_auth_local.py")
local = importlib.util.module_from_spec(spec)
spec.loader.exec_module(local)


def test_local_auth_setup_is_isolated_migrated_and_never_overwrites(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://do-not-connect.invalid/production")
    monkeypatch.setenv("RR_MODE", "invited_real")
    monkeypatch.setenv("REAL_AI_ENABLED", "true")
    monkeypatch.setenv("VERCEL", "1")
    directory = tmp_path / "acceptance"
    settings = local.prepare(directory, {"client_id": "synthetic_client", "client_secret": "synthetic_secret"})
    assert settings.mode == "sandbox" and not settings.real_ai_enabled
    assert settings.storage_backend == "disabled" and settings.stripe_secret_key is None
    assert settings.database_url.get_secret_value() == f"sqlite:///{directory / 'identity.db'}"
    assert local.check(directory)["local_auth_ready"]
    original = (directory / "credentials.json").read_bytes()
    with pytest.raises(FileExistsError):
        local.prepare(directory, {"client_id": "replacement_client", "client_secret": "replacement_secret"})
    assert (directory / "credentials.json").read_bytes() == original


def test_local_auth_rejects_public_credentials_and_extra_configuration(tmp_path):
    directory = tmp_path / "acceptance"
    local.prepare(directory, {"client_id": "synthetic_client", "client_secret": "synthetic_secret"})
    path = directory / "credentials.json"
    path.chmod(0o644)
    with pytest.raises(ValueError, match="0600"):
        local.settings_for(directory)
    path.chmod(0o600)
    data = json.loads(path.read_text())
    data["DATABASE_URL"] = "postgresql://do-not-connect.invalid/production"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="Unexpected"):
        local.settings_for(directory)
