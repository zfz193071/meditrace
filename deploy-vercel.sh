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
    required = {"src/backend/main.py", "src/backend/referral_review/app.py", "src/backend/requirements.txt",
                "src/backend/migrations_referral/versions/rr_0001_create_isolated_referral_domain.py",
                "src/backend/fonts/SourceHanSansCN-Regular.ttf",
                "src/frontend/package.json", "vercel.json"}
    if not required.issubset(files):
        raise DeployError("Missing deployment files: " + ", ".join(sorted(required - files)))
    if any(("venv" in Path(path).parts or "node_modules" in Path(path).parts or
            Path(path).name.startswith(".env") or
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


def fetch(origin, path, headers=None, staged=False):
    request = urllib.request.Request(origin + path, headers=headers or {}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status, response.read(2_000_000).decode("utf-8")
    except urllib.error.HTTPError as exc:
        if staged and exc.code in (401, 403):
            raise Unreachable("Staged deployment requires protection access.") from None
        return exc.code, exc.read(2_000_000).decode("utf-8")
    except (urllib.error.URLError, TimeoutError, OSError):
        raise Unreachable(f"Cannot connect to {origin}.") from None


def verify(origin, headers=None, attempts=1, staged=False):
    # GET only: no packet creation, AI, payment or chain calls.
    paths = ["/", "/api/v1/readiness"]
    for attempt in range(attempts):
        try:
            for path in paths:
                status, body = fetch(origin, path, headers, staged)
                if status != 200:
                    raise DeployError(f"{path} returned HTTP {status}.")
                if path == "/":
                    valid = "<!doctype html>" in body.lower()
                else:
                    try:
                        data = json.loads(body)
                        valid = data.get("status") == "ready" and all(
                            value == "ready" for value in data.get("checks", {}).values())
                    except (ValueError, AttributeError):
                        valid = False
                if not valid:
                    raise DeployError(f"{path} returned an unexpected response.")
            for path in ("/health", "/api/diagnose", "/api/history/retirement-check", "/api/verify/retirement-check",
                         "/api/report/retirement-check", "/api/conversations", "/api/generate-title"):
                status, body = fetch(origin, path, headers, staged)
                try:
                    retired = json.loads(body).get("error") == "LEGACY_API_RETIRED"
                except (ValueError, AttributeError):
                    retired = False
                if status != 410 or not retired:
                    raise DeployError(f"{path} is not safely retired (HTTP {status}).")
            note(f"Verified {origin}: frontend HTML, referral readiness and retired legacy GET routes.")
            return
        except DeployError:
            if attempt + 1 == attempts:
                raise
            note(f"Verification not ready; retry {attempt + 2}/{attempts} in 3 seconds.")
            time.sleep(3)


def migrate():
    # Only reviewed additive rr_* revisions; never execute legacy SQL.
    if not Path(sys.executable).is_relative_to(ROOT / "src/backend/venv"):
        raise DeployError("--migrate requires src/backend/venv and its installed dependencies.")
    from dotenv import dotenv_values
    sys.path.insert(0, str(ROOT / "src/backend"))
    from referral_review.persistence.database import create_engine
    from referral_review.persistence.migrations import HEAD, REVIEWED_REVISIONS, current_revision, upgrade
    settings = dotenv_values(ROOT / "src/backend/.env")
    url = os.environ.get("DATABASE_URL") or settings.get("DATABASE_URL")
    if not url or not url.startswith(("postgresql://", "postgres://")):
        raise DeployError("--migrate requires a PostgreSQL DATABASE_URL in the environment or src/backend/.env.")
    SECRETS.extend(value for value in settings.values() if value)
    SECRETS.append(url)
    from urllib.parse import urlsplit
    location = urlsplit(url)
    if HEAD not in REVIEWED_REVISIONS:
        raise DeployError("Referral migration head is not reviewed.")
    note(f"Applying reviewed referral migrations through {HEAD} to {location.hostname}{location.path}.")
    engine = create_engine(url.replace("postgres://", "postgresql://", 1))
    try:
        with engine.begin() as connection:
            upgrade(connection, HEAD)
            if current_revision(connection) != HEAD:
                raise DeployError("Referral migration head was not reached.")
    except DeployError:
        raise
    except Exception as exc:
        raise DeployError(f"Database migration failed ({type(exc).__name__}); transaction rolled back.") from None
    finally:
        engine.dispose()
    note(f"Reviewed additive referral migration {HEAD} completed.")


def save_state(state):
    destination = STATE_DIR / "last-deploy.json"
    temporary = destination.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(destination)


def deploy(project, with_migration):
    previous = active_deployment()
    if previous.get("projectId") != PROJECT or not previous.get("id"):
        raise DeployError("Cannot identify the current production deployment for rollback.")
    # The first cutover needs a separately established compatible baseline.
    # An unsafe previous deployment must never become an automatic rollback target.
    try:
        verify(ORIGIN)
    except (DeployError, Unreachable):
        raise DeployError("Current production is not a verified retired-API baseline; establish a safe compatible rollback deployment before using this workflow.") from None
    if active_deployment().get("id") != previous["id"]:
        raise DeployError("Production changed while checking the safe rollback baseline.")
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


def first_cutover(project, backup_reference):
    """Establish the first verified safe rollback baseline without restoring legacy APIs."""
    previous = active_deployment()
    if previous.get("projectId") != PROJECT or not previous.get("id"):
        raise DeployError("Cannot identify the current production deployment for first cutover.")
    state = {"started_at": datetime.now(timezone.utc).isoformat(), "previous_id": previous["id"],
             "origin": ORIGIN, "status": "first-cutover-building",
             "backup_reference_provided": bool(backup_reference)}
    save_state(state)
    try:
        stdout, stderr = vc("deploy", "--prod", "--skip-domain", "--yes", "--json", timeout=1200)
    except DeployError:
        state["status"] = "first-cutover-build-failed"
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
        state["status"] = "first-cutover-build-result-invalid"
        save_state(state)
        raise DeployError("Build did not return a READY deployment; production was not promoted.") from None
    state.update(deployment_id=new_id, deployment_url=new_url, status="first-cutover-built")
    save_state(state)
    note("First-cutover candidate built: " + new_url)

    # The rr_* migration is additive. Keep the existing deployment active until
    # the staged candidate proves readiness against the migrated schema.
    try:
        migrate()
    except DeployError:
        state["status"] = "first-cutover-migration-failed"
        save_state(state)
        raise
    bypass = next((key for key, value in project.get("protectionBypass", {}).items()
                   if value.get("scope") == "automation-bypass"), None)
    if bypass:
        SECRETS.append(bypass)
    try:
        verify(new_url, {"x-vercel-protection-bypass": bypass} if bypass else {}, staged=True)
    except (DeployError, Unreachable):
        state["status"] = "first-cutover-staged-verification-failed"
        save_state(state)
        raise
    if active_deployment().get("id") != previous["id"]:
        state["status"] = "first-cutover-production-changed"
        save_state(state)
        raise DeployError("Production changed during first cutover; candidate was not promoted.")

    try:
        note("Promoting the first safe baseline to " + ORIGIN)
        vc("promote", new_url, "--yes", timeout=240)
    except DeployError:
        state["status"] = "first-cutover-promotion-unknown"
        save_state(state)
        raise DeployError("First-cutover promotion outcome is unknown; inspect Vercel before retrying.") from None
    state["status"] = "first-cutover-promoted"
    save_state(state)
    try:
        if active_deployment().get("id") != new_id:
            raise DeployError("The production domain does not point to the first-cutover deployment.")
        verify(ORIGIN, attempts=3)
    except (DeployError, KeyboardInterrupt):
        # Never roll back to the release that exposed retired routes. Keep the
        # new release active and require forward repair if production checks fail.
        state["status"] = "first-cutover-unverified"
        save_state(state)
        raise
    state.update(status="first-cutover-verified", finished_at=datetime.now(timezone.utc).isoformat())
    save_state(state)
    note("First safe production baseline established and verified: " + ORIGIN)


def main():
    global LOG
    parser = argparse.ArgumentParser(prog="deploy-vercel.sh", description="Deploy MediTrace frontend + backend to the existing Vercel Hobby project.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="check prerequisites and deployment inputs without publishing")
    mode.add_argument("--verify", action="store_true", help="verify the current production frontend, backend and database without publishing")
    parser.add_argument("--migrate", action="store_true", help="apply reviewed referral migrations before a normal deployment (explicit opt-in)")
    parser.add_argument("--first-cutover", action="store_true", help="establish the first safe production baseline; requires explicit cutover and backup confirmations")
    parser.add_argument("--confirm-production-cutover", help="must exactly match the production origin for --first-cutover")
    parser.add_argument("--backup-reference", help="operator-verified production backup reference required for --first-cutover")
    args = parser.parse_args()
    if args.first_cutover:
        if args.check or args.verify or args.migrate:
            parser.error("--first-cutover cannot be combined with --check, --verify or --migrate")
        if args.confirm_production_cutover != ORIGIN or not args.backup_reference or len(args.backup_reference) > 200:
            parser.error("--first-cutover requires --confirm-production-cutover matching the production origin and a --backup-reference")
    elif args.confirm_production_cutover or args.backup_reference:
        parser.error("cutover confirmations can only be used with --first-cutover")
    elif args.migrate and (args.check or args.verify):
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
        elif args.first_cutover:
            first_cutover(project, args.backup_reference)
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
