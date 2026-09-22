#!/usr/bin/env bash
# One entry point for MediTrace's Vercel frontend and backend deployment.
set -euo pipefail
DEPLOY_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$DEPLOY_ROOT"
if [[ -x src/backend/venv/bin/python ]]; then
  DEPLOY_PYTHON="$DEPLOY_ROOT/src/backend/venv/bin/python"
else
  DEPLOY_PYTHON="$(command -v python3)"
fi
exec "$DEPLOY_PYTHON" - "$@" <<'PY'
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone

ROOT = Path.cwd()
PROJECT = "prj_QlLheFSLOElrMGgf3hXjZESfINVb"
TEAM = "team_oFSqjDwtcOUZSSUWsdRYL0gZ"
SCOPE = "lucyzhus-projects"
ORIGIN = "https://meditrace.baozaolaoba.top"
STATE_DIR = ROOT / ".vercel"
LOG = None
SECRETS = []


class DeployError(RuntimeError):
    pass


class Unreachable(DeployError):
    pass


def redact(value):
    for secret in SECRETS:
        if len(secret) > 8:
            value = value.replace(secret, "<REDACTED>")
    value = re.sub(r"postgres(?:ql)?://[^\s\"']+", "<DATABASE_URL>", value)
    value = re.sub(r"\bsk-[A-Za-z0-9_-]+", "<API_KEY>", value)
    return value


def note(message):
    line = redact(message)
    print(line, flush=True)
    if LOG:
        LOG.write(line + "\n")
        LOG.flush()


def vc(*args, timeout=120):
    try:
        result = subprocess.run(
            ["vercel", *args, "--scope", SCOPE], cwd=ROOT,
            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise DeployError(f"Vercel {args[0]} timed out; check Vercel before retrying.") from None
    if result.returncode:
        raise DeployError(redact((result.stderr + result.stdout)[-4000:]))
    return result.stdout, result.stderr


def api(endpoint):
    stdout, _ = vc("api", endpoint, "--raw")
    try:
        return json.loads(stdout)
    except ValueError:
        raise DeployError("Vercel API returned invalid JSON.") from None


def active_deployment():
    return api("/v13/deployments/" + ORIGIN.removeprefix("https://"))


def check_inputs():
    stdout, _ = vc("deploy", "--dry", "--json")
    files = {item["path"] for item in json.loads(stdout)["files"]}
    required = {"src/backend/main.py", "src/backend/database.py", "src/backend/requirements.txt",
                "src/backend/abi/DiagnosisRecord.json", "src/backend/fonts/SourceHanSansCN-Regular.ttf",
                "src/frontend/package.json", "vercel.json"}
    if not required.issubset(files):
        raise DeployError("Missing deployment files: " + ", ".join(sorted(required - files)))
    if any(("venv" in Path(path).parts or "node_modules" in Path(path).parts or
            (Path(path).name.startswith(".env") and path != "src/frontend/.env.production") or
            Path(path).suffix in (".db", ".sqlite", ".sqlite3")) for path in files):
        raise DeployError("Deployment inputs contain local dependencies, database files or environment files.")
    note(f"Deployment inputs verified ({len(files)} files).")


def preflight():
    if not shutil.which("vercel"):
        raise DeployError("Install Vercel CLI first: npm install -g vercel")
    link_path = STATE_DIR / "project.json"
    if not link_path.exists():
        raise DeployError("Link this checkout first: vercel link --project meditrace --scope " + SCOPE + " --yes")
    link = json.loads(link_path.read_text())
    if link.get("projectId") != PROJECT or link.get("orgId") != TEAM:
        raise DeployError("This checkout is linked to a different Vercel project; refusing to deploy.")
    config = json.loads((ROOT / "vercel.json").read_text())
    services = config.get("services", {})
    for name, path in (("frontend", "src/frontend"), ("backend", "src/backend")):
        if services.get(name, {}).get("root", "").rstrip("/") != path:
            raise DeployError(f"vercel.json must include the {name} service at {path}.")
    vc("whoami")
    project = api("/v9/projects/" + PROJECT)
    for variable in project.get("env", []):
        value = variable.get("value")
        if isinstance(value, str):
            SECRETS.append(value)
    if project.get("framework") != "services" or project.get("rootDirectory") not in (None, "", "."):
        raise DeployError("Vercel project must use Services with the repository root directory.")
    teams = api("/v2/teams").get("teams", [])
    team = next((item for item in teams if item.get("id") == TEAM), None)
    if not team or team.get("billing", {}).get("plan") != "hobby":
        raise DeployError("Could not confirm the expected Hobby plan; no deployment was created.")
    production_env = {item["key"] for item in project.get("env", []) if "production" in item.get("target", [])}
    if "DATABASE_URL" not in production_env:
        raise DeployError("Production DATABASE_URL is missing in Vercel.")
    note("Preflight passed: MediTrace, frontend + backend Services, Hobby plan, production database configured.")
    if "DEEPSEEK_API_KEY" not in production_env:
        note("AI remains in demo mode (production DEEPSEEK_API_KEY is not configured).")
    return project


def verify(origin, headers=None, attempts=1, staged=False):
    # Read-only requests: never invoke AI, upload reports or submit transactions.
    patient = "deploy-check-" + uuid.uuid4().hex[:24]
    paths = ["/", "/health", "/api/conversations?patientId=" + patient]
    for attempt in range(attempts):
        try:
            for path in paths:
                request = urllib.request.Request(origin + path, headers=headers or {})
                try:
                    with urllib.request.urlopen(request, timeout=20) as response:
                        body = response.read(2_000_000).decode("utf-8")
                        status = response.status
                except urllib.error.HTTPError as exc:
                    if staged and exc.code in (401, 403):
                        raise Unreachable("Staged deployment requires protection access.") from None
                    raise DeployError(f"{path.split('?')[0]} returned HTTP {exc.code}.") from None
                except (urllib.error.URLError, TimeoutError, OSError):
                    raise Unreachable(f"Cannot connect to {origin}.") from None
                if status != 200:
                    raise DeployError(f"{path.split('?')[0]} returned HTTP {status}.")
                if path == "/":
                    valid = "<!doctype html>" in body.lower()
                else:
                    try:
                        data = json.loads(body)
                        valid = (data.get("status") == "healthy") if path == "/health" else (
                            isinstance(data.get("conversations"), list) and isinstance(data.get("total"), int)
                        )
                    except (ValueError, AttributeError):
                        valid = False
                if not valid:
                    raise DeployError(f"{path.split('?')[0]} returned an unexpected response.")
            note(f"Verified {origin}: frontend HTML, backend health and PostgreSQL conversation list.")
            return
        except DeployError:
            if attempt + 1 == attempts:
                raise
            note(f"Verification not ready; retry {attempt + 2}/{attempts} in 3 seconds.")
            time.sleep(3)


def migrate():
    # Only the reviewed additive migration is allowed; 001_conversations.sql drops tables.
    if not Path(sys.executable).is_relative_to(ROOT / "src/backend/venv"):
        raise DeployError("--migrate requires src/backend/venv and its installed dependencies.")
    from dotenv import dotenv_values
    from sqlalchemy import create_engine, text
    settings = dotenv_values(ROOT / "src/backend/.env")
    url = os.environ.get("DATABASE_URL") or settings.get("DATABASE_URL")
    if not url or not url.startswith(("postgresql://", "postgres://")):
        raise DeployError("--migrate requires a PostgreSQL DATABASE_URL in the environment or src/backend/.env.")
    SECRETS.extend(value for value in settings.values() if value)
    SECRETS.append(url)
    from urllib.parse import urlsplit
    location = urlsplit(url)
    note(f"Applying the known additive migration to {location.hostname}{location.path}.")
    engine = create_engine(url.replace("postgres://", "postgresql://", 1), connect_args={"connect_timeout": 10})
    try:
        with engine.begin() as connection:
            tables = {row[0] for row in connection.execute(text(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = current_schema()"
            ))}
            if not {"conversations", "messages"}.issubset(tables):
                raise DeployError("Expected legacy tables are missing; refusing to infer a different migration.")
            connection.exec_driver_sql((ROOT / "src/backend/migrations/002_vercel_schema_compatibility.sql").read_text())
    except DeployError:
        raise
    except Exception as exc:
        raise DeployError(f"Database migration failed ({type(exc).__name__}); transaction rolled back.") from None
    finally:
        engine.dispose()
    note("Known additive schema migration completed.")


def save_state(state):
    destination = STATE_DIR / "last-deploy.json"
    temporary = destination.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(destination)


def deploy(project, with_migration):
    previous = active_deployment()
    if previous.get("projectId") != PROJECT or not previous.get("id"):
        raise DeployError("Cannot identify the current production deployment for rollback.")
    state = {"started_at": datetime.now(timezone.utc).isoformat(), "previous_id": previous["id"],
             "origin": ORIGIN, "status": "building"}
    save_state(state)
    if with_migration:
        migrate()
    note("Building frontend and backend on Vercel; production aliases stay on the current release.")
    try:
        stdout, stderr = vc("deploy", "--prod", "--skip-domain", "--yes", "--json", timeout=1200)
    except DeployError:
        state["status"] = "build-failed"
        save_state(state)
        raise
    if LOG:
        LOG.write(redact(stderr) + "\n")
        LOG.flush()
    try:
        deployment = json.loads(stdout)["deployment"]
        new_id = deployment["id"]
        new_url = deployment["url"]
        if not new_url.startswith("https://"):
            new_url = "https://" + new_url
        if deployment.get("readyState") != "READY":
            raise ValueError("not ready")
    except (ValueError, KeyError, TypeError):
        state["status"] = "build-result-invalid"
        save_state(state)
        raise DeployError("Build did not return a READY deployment; production was not promoted.") from None
    state.update(deployment_id=new_id, deployment_url=new_url, status="built")
    save_state(state)
    note("Build ready: " + new_url)
    bypass = next((key for key, value in project.get("protectionBypass", {}).items()
                   if value.get("scope") == "automation-bypass"), None)
    if bypass:
        SECRETS.append(bypass)
    try:
        verify(new_url, {"x-vercel-protection-bypass": bypass} if bypass else {}, staged=True)
    except Unreachable as exc:
        note(str(exc) + " Will verify via the custom domain immediately after promotion.")
    except DeployError:
        state["status"] = "staged-verification-failed"
        save_state(state)
        raise
    if active_deployment().get("id") != previous["id"]:
        state["status"] = "production-changed"
        save_state(state)
        raise DeployError("Production changed during the build; this release was not promoted.")
    try:
        note("Promoting the new release to " + ORIGIN)
        vc("promote", new_url, "--yes", timeout=240)
        state["status"] = "promoted"
        save_state(state)
        if active_deployment().get("id") != new_id:
            raise DeployError("The production domain does not point to this deployment.")
        verify(ORIGIN, attempts=3)
    except (DeployError, KeyboardInterrupt):
        # Do not undo a different deployment made concurrently by another operator.
        if active_deployment().get("id") == new_id:
            note("Release verification failed or was interrupted. Rolling back to " + previous["id"])
            state["status"] = "rolling-back"
            save_state(state)
            vc("rollback", previous["id"], "--yes", timeout=240)
            if active_deployment().get("id") != previous["id"]:
                raise DeployError("Rollback could not be confirmed; inspect Vercel immediately.")
            state["status"] = "rolled-back"
            save_state(state)
            verify(ORIGIN)
            note("Previous production deployment restored. This deployment is marked FAILED.")
        else:
            state["status"] = "not-active"
            save_state(state)
            note("This release is not active; no other production deployment was changed.")
        raise
    state.update(status="verified", finished_at=datetime.now(timezone.utc).isoformat())
    save_state(state)
    note("Deployment succeeded: " + ORIGIN)


def main():
    global LOG
    parser = argparse.ArgumentParser(prog="deploy-vercel.sh", description="Deploy MediTrace frontend + backend to the existing Vercel Hobby project.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="check prerequisites and deployment inputs without publishing")
    mode.add_argument("--verify", action="store_true", help="verify the current production frontend, backend and database without publishing")
    parser.add_argument("--migrate", action="store_true", help="apply only migration 002 to local DATABASE_URL before deploying (explicit opt-in)")
    args = parser.parse_args()
    if args.migrate and (args.check or args.verify):
        parser.error("--migrate can only be used with a deployment")
    os.umask(0o077)
    STATE_DIR.mkdir(exist_ok=True)
    with (STATE_DIR / "deploy.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise DeployError("Another MediTrace deployment/check is running in this checkout.") from None
        LOG = (STATE_DIR / ("deploy-" + datetime.now().strftime("%Y%m%d-%H%M%S") + ".log")).open("a")
        note("MediTrace deployment workflow")
        project = preflight()
        if not args.verify:
            check_inputs()
        if args.check:
            note("Checks passed. No deployment or migration was performed.")
        elif args.verify:
            verify(ORIGIN, attempts=3)
        else:
            deploy(project, args.migrate)
        note("Log: " + str(Path(LOG.name).relative_to(ROOT)))


if __name__ == "__main__":
    try:
        main()
    except (DeployError, ValueError, OSError) as exc:
        note("FAILED: " + redact(str(exc)))
        sys.exit(1)
    except KeyboardInterrupt:
        note("Interrupted; check .vercel/last-deploy.json and Vercel before retrying.")
        sys.exit(130)
    finally:
        if LOG:
            LOG.close()
PY
