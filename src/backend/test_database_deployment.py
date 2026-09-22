"""Deployment regressions: startup and persistence without calling AI services."""

import json
import os
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

import database
from main import app


@pytest.fixture(params=["sqlite", "postgresql", "postgresql_legacy"])
def client(request, tmp_path, monkeypatch):
    schema = None
    admin = None
    if request.param.startswith("postgresql"):
        url = os.getenv("TEST_DATABASE_URL")
        if not url:
            pytest.skip("TEST_DATABASE_URL is not configured")
        url = make_url(url)
        if url.host and url.host.endswith(".neon.tech"):
            url = url.set(host=url.host.replace("-pooler.", "."))
        admin = create_engine(url, connect_args={"connect_timeout": 10})
        schema = "deploy_test_" + uuid.uuid4().hex
        with admin.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_engine(url, connect_args={
            "options": f"-csearch_path={schema}", "connect_timeout": 10,
        })
    else:
        engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")

    monkeypatch.setattr(database, "engine", engine)
    try:
        if request.param == "postgresql_legacy":
            with engine.begin() as conn:
                conn.exec_driver_sql("""
                    CREATE TABLE conversations (
                        id UUID PRIMARY KEY, title VARCHAR(255) NOT NULL,
                        created_at TIMESTAMP DEFAULT NOW(), updated_at TIMESTAMP DEFAULT NOW()
                    );
                    CREATE TABLE messages (
                        id UUID PRIMARY KEY, conversation_id UUID NOT NULL
                            REFERENCES conversations(id) ON DELETE CASCADE,
                        role VARCHAR(50) NOT NULL, content TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT NOW()
                    );
                """)
                migration = Path(__file__).parent / "migrations/002_vercel_schema_compatibility.sql"
                conn.exec_driver_sql(migration.read_text())
                conn.exec_driver_sql(migration.read_text())
        with TestClient(app) as test_client:
            yield test_client
    finally:
        engine.dispose()
        if admin is not None:
            with admin.begin() as conn:
                conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            admin.dispose()


def test_startup_and_conversation_persistence(client):
    assert client.get("/health").json()["status"] == "healthy"
    response = client.post("/api/conversations", json={
        "patientId": "deployment-test", "title": "Persistence check",
    })
    assert response.status_code == 200
    conversation_id = response.json()["conversationId"]
    path = f"/api/conversations/{conversation_id}"
    assert client.get(path).json()["metadata"] == {}
    listing = client.get("/api/conversations", params={"patientId": "deployment-test"}).json()
    assert listing["total"] == 1
    assert listing["conversations"][0]["messageCount"] == 0
    title = "Quote ' and question ? stay literal"
    assert client.put(path, json={"title": title}).status_code == 200
    assert client.get(path).json()["title"] == title

    # Exercise JSONB, context reads and cascading deletion without an AI request.
    with database.get_db() as conn:
        conn.execute(
            "INSERT INTO messages (id, conversation_id, role, content, context_refs) VALUES (?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), conversation_id, "user", "Stored fixture", json.dumps(["reference"])),
        )
    assert client.get(path).json()["messages"][0]["contextRefs"] == ["reference"]
    from context_engine import ContextEngine
    assert ContextEngine().get_conversation_context(conversation_id)[0]["contextRefs"] == ["reference"]
    assert client.delete(path).status_code == 200
    assert client.get(path).status_code == 404
    with database.get_db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 0


def test_transaction_rollback(client):
    with pytest.raises(RuntimeError, match="rollback"):
        with database.get_db() as conn:
            conn.execute(
                "INSERT INTO conversations (id, patient_id, title) VALUES (?, ?, ?)",
                (str(uuid.uuid4()), "rollback-test", "Must not persist"),
            )
            raise RuntimeError("rollback")
    assert client.get("/api/conversations", params={"patientId": "rollback-test"}).json()["total"] == 0
