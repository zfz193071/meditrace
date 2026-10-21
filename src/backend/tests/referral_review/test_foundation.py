"""Cost-free foundation invariants. These tests never import a model client."""

import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from referral_review.app import create_app
from referral_review.config import ConfigurationError, Settings, load_settings
from referral_review.export_contracts import artifacts
from referral_review.schemas import Evidence, Fact, ReviewResult


def test_missing_credentials_start_in_demo_mode_without_enabling_workflows():
    settings = load_settings({})
    with TestClient(create_app(settings)) as client:
        response = client.get("/capabilities")
        assert response.status_code == 200
        data = response.json()
        assert data["mode"] == "bundled_demo"
        assert data["demo_mode_available"] is True
        assert data["demo_cases_available"] is False
        assert data["real_ai_execution_available"] is False
        assert data["payments_available"] is False
        assert client.get("/readiness").status_code == 503
        assert client.get("/readiness").json()["checks"]["migrations"] == "not_implemented"
    with pytest.raises(ConfigurationError):
        settings.require_real_ai_configuration()


@pytest.mark.parametrize("env", [
    {"RR_ALLOW_FAKE_IDENTITY": "true"},
    {"RR_DEV_GRANT": "true"},
    {"VERCEL": "1", "RR_ENVIRONMENT": "development"},
    {"VERCEL_ENV": "production", "RR_ENVIRONMENT": "test"},
    {"RR_ENVIRONMENT": "production", "RR_SITE_ORIGIN": "http://example.test"},
    {"RR_ENVIRONMENT": "production", "DATABASE_URL": "sqlite:///secret-data.db"},
    {"RR_STRIPE_SECRET_KEY": "sk_live_do-not-leak"},
    {"RR_SESSION_ENCRYPTION_KEY": "short-secret"},
    {"RR_DAILY_BUDGET_MICROUSD": "-1"},
    {"RR_REAL_AI_USER_IDS": "do-not-leak"},
    {"RR_MODE": "real"},
    {"RR_SITE_ORIGIN": "https://example.test/path"},
    {"RR_SITE_ORIGIN": "https://example.test", "RR_GITHUB_CALLBACK_URL": "https://evil.test/callback"},
])
def test_invalid_or_unsafe_configuration_fails_without_echoing_values(env):
    with pytest.raises(ConfigurationError) as caught:
        load_settings(env)
    assert "do-not-leak" not in str(caught.value)
    assert "short-secret" not in str(caught.value)
    assert "secret-data" not in str(caught.value)


def configured_real_environment():
    return {
        "RR_MODE": "invited_real", "REAL_AI_ENABLED": "true", "DEEPSEEK_API_KEY": "secret-sentinel",
        "RR_MODEL_ID": "test-model", "RR_MODEL_PRICE_VERSION": "test-price",
        "RR_MODEL_INPUT_MICROUSD_PER_MILLION_TOKENS": "1",
        "RR_MODEL_OUTPUT_MICROUSD_PER_MILLION_TOKENS": "1",
        "RR_DAILY_BUDGET_MICROUSD": "100", "RR_MONTHLY_BUDGET_MICROUSD": "200",
        "RR_REAL_AI_USER_IDS": str(uuid4()),
    }


@pytest.mark.parametrize("missing", list(configured_real_environment()))
def test_every_real_configuration_precondition_is_required(missing):
    env = configured_real_environment()
    del env[missing]
    with pytest.raises(ConfigurationError):
        load_settings(env).require_real_ai_configuration()


def test_complete_configuration_is_not_runtime_authorization():
    settings = load_settings(configured_real_environment())
    settings.require_real_ai_configuration()
    assert "secret-sentinel" not in repr(settings)
    assert "secret-sentinel" not in settings.model_dump_json()
    with TestClient(create_app(settings)) as client:
        assert client.get("/capabilities").json()["mode"] == "invited_real"
        assert client.get("/capabilities").json()["real_ai_execution_available"] is False
        response = client.post(f"/runs/{uuid4()}/execute", headers={"X-User-ID": str(uuid4()), "X-Member": "true"})
        assert response.status_code == 404


def test_deployed_defaults_are_production():
    assert load_settings({"VERCEL": "1"}).environment == "production"


@pytest.mark.parametrize("environment", ["development", "production"])
def test_mounted_routes_request_ids_no_store_and_no_trusted_identity_headers(environment):
    parent = FastAPI()
    parent.mount("/api/v1", create_app(Settings(RR_ENVIRONMENT=environment)))
    with TestClient(parent) as client:
        response = client.get("/api/v1/capabilities", headers={"X-Request-ID": "secret-sentinel", "X-User-ID": "admin"})
        assert response.status_code == 200
        UUID(response.headers["X-Request-ID"])
        assert response.headers["Cache-Control"] == "private, no-store"
        assert "secret-sentinel" not in response.text
        error = client.post("/api/v1/capabilities", json={"secret": "secret-sentinel"})
        assert error.status_code == 405
        assert error.json()["error"]["code"] == "METHOD_NOT_ALLOWED"
        assert error.json()["request_id"] == error.headers["X-Request-ID"]
        assert "secret-sentinel" not in error.text
        assert client.post("/api/v1/dev/grant", headers={"X-User-ID": "admin"}).status_code == 404


def test_legacy_entrypoint_mounts_foundation_without_starting_services():
    from main import app

    # No context manager: do not execute legacy startup DDL or connect to a database.
    client = TestClient(app)
    assert client.get("/api/v1/capabilities").status_code == 200
    assert client.get("/api/v1/readiness").status_code == 503


def test_validation_and_unexpected_errors_do_not_leak_inputs_or_exception(caplog):
    app = create_app(Settings())

    # Validation-only probe is read-only; registered mutations now require CSRF.
    @app.get("/test-evidence")
    def accept_evidence(evidence: Evidence):
        return evidence

    @app.get("/test-failure")
    def fail():
        raise RuntimeError("secret-sentinel: patient content and token")

    # Default raise_server_exceptions=True proves errors do not escape to ASGI logs.
    with TestClient(app) as client:
        invalid = client.request("GET", "/test-evidence", json={"quote": "secret-sentinel"})
        assert invalid.status_code == 422
        assert invalid.json()["error"]["code"] == "SCHEMA_INVALID"
        failed = client.get("/test-failure")
        assert failed.status_code == 500
        assert failed.json()["request_id"] == failed.headers["X-Request-ID"]
        assert "secret-sentinel" not in invalid.text + failed.text + caplog.text


def sample_result():
    evidence = Evidence(id=uuid4(), document_id=uuid4(), page_number=1, start_cp=2, end_cp=4, quote="A😀", text_hash="a" * 64)
    fact = Fact(id=uuid4(), field_key="patient.name", value_raw="A😀", assertion_status="stated", evidence_ids=[evidence.id])
    return {
        "run_id": uuid4(), "revision_id": uuid4(), "mode": "precomputed",
        "created_at": "2026-10-20T08:00:00+08:00", "checklist_version": "outpatient-referral-demo@1",
        "prompt_version": "not-applicable", "schema_version": "0.1.0",
        "facts": [fact], "evidence": [evidence], "findings": [],
    }


def test_contract_uuid_utc_unicode_and_round_trip():
    result = ReviewResult.model_validate(sample_result())
    assert result.created_at == datetime(2026, 10, 20, tzinfo=timezone.utc)
    assert json.loads(result.model_dump_json())["created_at"] == "2026-10-20T00:00:00Z"
    assert ReviewResult.model_validate_json(result.model_dump_json()) == result


def test_contract_rejects_naive_time_fabricated_refs_extra_fields_and_bad_span():
    data = sample_result()
    with pytest.raises(ValidationError):
        ReviewResult.model_validate({**data, "created_at": "2026-10-20T08:00:00"})
    with pytest.raises(ValidationError):
        ReviewResult.model_validate({**data, "evidence": []})
    with pytest.raises(ValidationError):
        ReviewResult.model_validate({**data, "owner_id": str(uuid4())})
    with pytest.raises(ValidationError):
        Evidence.model_validate({**data["evidence"][0].model_dump(), "end_cp": 5})


def test_schema_generation_is_deterministic_and_does_not_depend_on_environment(monkeypatch):
    baseline = artifacts()
    monkeypatch.setenv("RR_MODE", "invalid-sentinel")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "secret-sentinel")
    assert artifacts() == baseline
    assert set(baseline["openapi.json"]["paths"]) == {
        "/capabilities", "/readiness", "/membership", "/auth/session", "/auth/github/start",
        "/auth/github/callback", "/auth/logout",
        "/packets/{packet_id}/documents", "/packets/{packet_id}/documents/{document_id}",
        "/packets/{packet_id}/documents/{document_id}/original",
        "/packets/{packet_id}/documents/{document_id}/pages/{page_number}",
        "/packets", "/packets/{packet_id}", "/packets/{packet_id}/draft",
        "/packets/{packet_id}/revisions", "/packets/{packet_id}/revisions/{revision_number}",
    }
    assert "secret-sentinel" not in json.dumps(baseline)
