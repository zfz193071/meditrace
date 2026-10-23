"""Bounded read-only DB/schema probe and deterministic checklist self-check."""
from pathlib import Path
from uuid import UUID

import sqlalchemy as sa

from ..checklist import CHECKLIST_VERSION, ChecklistManifest, evaluate
from ..documents.text_rules import text_hash
from ..extraction.contracts import Extraction
from ..persistence.database import create_engine
from ..persistence.migrations import HEAD, current_revision
from ..persistence.models import metadata
from ..schemas import ReadinessResponse


def checklist_ready():
    rid, did = UUID(int=1), UUID(int=2)
    manifest = ChecklistManifest(revision_id=rid, documents=[dict(id=did, title="Probe", kind="text",
        parse_status="ready", page_count=1, pages=[dict(document_id=did, page_number=1,
        normalized_text="Probe", text_hash=text_hash("Probe"), parse_quality="ready", parser_version="text-v1")])])
    extraction = Extraction(revision_id=rid, mode="fake", model_requested="probe", model_reported=None,
        provider_request_id=None, usage=None, facts=[], evidence=[])
    result = evaluate(extraction, manifest, CHECKLIST_VERSION)
    return result.assessments == {**{f"C0{i}": "missing" for i in range(1, 8)}, "C08": "not_applicable"}


def probe(settings, identity=None):
    checks = {"database": "unavailable", "migrations": "not_checked", "checklist": "unavailable"}
    revision = None
    engine = identity.engine if identity is not None else None
    owned = False
    try:
        if engine is None and settings.database_url:
            url = settings.database_url.get_secret_value()
            parsed = sa.engine.make_url(url)
            # SQLite opening a nonexistent file would create it: fail without opening it.
            if parsed.get_backend_name() != "sqlite" or (parsed.database and Path(parsed.database).is_file()):
                engine, owned = create_engine(url), True
        if engine is not None:
            with engine.connect() as conn:
                if conn.dialect.name == "postgresql":
                    conn.exec_driver_sql("SET TRANSACTION READ ONLY")
                conn.execute(sa.text("SELECT 1"))
                checks["database"] = "ready"
                revision = current_revision(conn)
                checks["migrations"] = "unavailable"
                if revision == HEAD:
                    # Detect a stamped but incomplete schema without DDL or touching records.
                    for table in metadata.sorted_tables:
                        conn.execute(sa.select(table).limit(0))
                    checks["migrations"] = "ready"
    except Exception:
        checks["migrations"] = "unavailable" if checks["database"] == "ready" else "not_checked"
    finally:
        if owned:
            engine.dispose()
    try:
        if checklist_ready():
            checks["checklist"] = "ready"
    except Exception:
        pass
    ready = all(value == "ready" for value in checks.values())
    # A corrupted version-table string is not safe diagnostic output.
    return ReadinessResponse(status="ready" if ready else "not_ready", checks=checks,
        schema_version=HEAD if revision == HEAD else None,
        checklist_version=CHECKLIST_VERSION if checks["checklist"] == "ready" else None)
