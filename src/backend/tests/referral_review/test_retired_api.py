"""MT-21: old API paths must be inert even with legacy credentials configured."""

import pytest
from fastapi.testclient import TestClient


LEGACY_PATHS = (
    "/health", "/api", "/api/diagnose", "/api/history/patient", "/api/verify/diagnosis",
    "/api/report/diagnosis", "/api/conversations", "/api/conversations/record",
    "/api/conversations/record/messages", "/api/conversations/record/messages/stream",
    "/api/generate-title", "/api/unknown-legacy-entry",
)
METHODS = ("GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS")


@pytest.mark.parametrize("path", LEGACY_PATHS)
@pytest.mark.parametrize("method", METHODS)
def test_every_old_api_method_returns_410_without_legacy_service_import(path, method, monkeypatch):
    monkeypatch.setenv("SEPOLIA_PRIVATE_KEY", "unused")
    monkeypatch.setenv("PINATA_JWT_TOKEN", "unused")
    import main
    app = main.app
    with TestClient(app) as client:
        response = client.request(method, path, content=b"not valid JSON")
    assert response.status_code == 410
    assert response.headers["Cache-Control"] == "no-store"
    if method != "HEAD":
        assert response.json()["error"] == "LEGACY_API_RETIRED"
    assert not any(name in main.__dict__ for name in
                   ("get_blockchain_client", "get_ipfs_client", "get_deepseek_client", "init_database"))


def test_new_api_still_mounted_without_legacy_startup_ddl(monkeypatch):
    for name in ("SEPOLIA_PRIVATE_KEY", "SEPOLIA_RPC_URL", "PINATA_JWT_TOKEN", "PINATA_API_KEY", "PINATA_SECRET_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    import importlib
    import main
    app = importlib.reload(main).app
    with TestClient(app) as client:
        assert client.get("/api/v1/capabilities").status_code == 200
        assert client.get("/api/v1/readiness").status_code in (200, 503)
