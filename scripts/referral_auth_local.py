#!/usr/bin/env python3
"""Prepare an isolated OAuth acceptance environment; services start only on request.

Run with src/backend/.venv/bin/python. No dotenv loading or production credentials.
The private local OAuth credentials are accepted on stdin, never CLI arguments.
"""

import argparse
import json
import os
from pathlib import Path
import re
import stat
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/backend"))

from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient

from referral_review.app import create_app
from referral_review.config import Settings
from referral_review.operations.access_logging import access_log_config
from referral_review.persistence.database import create_engine
from referral_review.persistence.migrations import HEAD, require_current_schema, upgrade

DIRECTORY = ROOT / ".scratch/rr-auth-local"
ORIGIN = "http://127.0.0.1:3000"
CREDENTIAL_KEYS = {"client_id", "client_secret", "session_key"}


def private_file(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600:
        raise ValueError("Local acceptance files must be regular files with mode 0600")


def settings_for(directory):
    info = directory.lstat()
    if not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o700:
        raise ValueError("Local acceptance directory must have mode 0700")
    for name in ("credentials.json", "identity.db"):
        private_file(directory / name)
    credentials = json.loads((directory / "credentials.json").read_text())
    if set(credentials) != CREDENTIAL_KEYS:
        raise ValueError("Unexpected local credential fields")
    # Construct from explicit values: ambient DATABASE_URL, RR_*, VERCEL and
    # paid provider keys cannot change the database, origin or sandbox mode.
    return Settings(RR_ENVIRONMENT="development", RR_MODE="sandbox",
        DATABASE_URL=f"sqlite:///{directory.resolve() / 'identity.db'}",
        RR_SITE_ORIGIN=ORIGIN, RR_GITHUB_CALLBACK_URL=ORIGIN + "/api/v1/auth/github/callback",
        RR_GITHUB_CLIENT_ID=credentials["client_id"],
        RR_GITHUB_CLIENT_SECRET=credentials["client_secret"],
        RR_SESSION_ENCRYPTION_KEY=credentials["session_key"])


def prepare(directory, credentials):
    if set(credentials) != {"client_id", "client_secret"} or not all(
        isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_]{10,200}", value)
        for value in credentials.values()
    ):
        raise ValueError("Expected local OAuth client_id and client_secret")
    directory.parent.mkdir(parents=True, exist_ok=True)
    directory.mkdir(mode=0o700)  # Refuse to overwrite any existing environment.
    payload = {**credentials, "session_key": Fernet.generate_key().decode()}
    with os.fdopen(os.open(directory / "credentials.json",
                           os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as file:
        json.dump(payload, file)
    descriptor = os.open(directory / "identity.db", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(descriptor)
    settings = settings_for(directory)
    engine = create_engine(settings.database_url.get_secret_value())
    try:
        with engine.begin() as connection:
            upgrade(connection, HEAD)
    finally:
        engine.dispose()
    return settings


def application(directory):
    settings = settings_for(directory)
    engine = create_engine(settings.database_url.get_secret_value())
    try:
        with engine.connect() as connection:
            require_current_schema(connection)  # Serving never migrates.
    finally:
        engine.dispose()
    parent = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    parent.mount("/api/v1", create_app(settings))
    return parent


def check(directory):
    with TestClient(application(directory), base_url=ORIGIN, follow_redirects=False) as client:
        session = client.get("/api/v1/auth/session")
        readiness = client.get("/api/v1/readiness")
        if session.status_code != 200 or not session.json()["login_available"] or readiness.status_code != 200:
            raise ValueError("Local authentication environment is not ready")
    return {"local_auth_ready": True, "database": "isolated SQLite", "migration": HEAD,
            "origin": ORIGIN, "mode": "sandbox", "real_ai_enabled": False,
            "services_started": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "check", "backend", "frontend"))
    args = parser.parse_args()
    try:
        if args.action == "prepare":
            if sys.stdin.isatty():
                from getpass import getpass
                line = getpass("Local OAuth credentials JSON (hidden): ")
            else:
                line = sys.stdin.readline()
            prepare(DIRECTORY, json.loads(line))
            print(json.dumps(check(DIRECTORY)))
        elif args.action == "check":
            print(json.dumps(check(DIRECTORY)))
        elif args.action == "backend":
            import uvicorn
            os.umask(0o077)
            uvicorn.run(application(DIRECTORY), host="127.0.0.1", port=8000,
                        log_config=access_log_config())
        else:
            check(DIRECTORY)
            os.chdir(ROOT / "src/frontend")
            os.execvp("pnpm", ["pnpm", "dev", "--hostname", "127.0.0.1", "--port", "3000"])
    except Exception:
        # Configuration, provider and database errors can embed credentials.
        print("Local OAuth setup failed; check prerequisites and private file permissions. Existing files were not replaced.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
