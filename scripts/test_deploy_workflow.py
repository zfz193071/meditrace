"""Exercise deployment failure/recovery paths without changing Vercel or calling AI."""

import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import sys
import types


SCRIPT = Path(__file__).resolve().parents[1] / "deploy-vercel.sh"
SOURCE = SCRIPT.read_text().split("<<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.module = {"__name__": "deploy_workflow_test"}
        exec(compile(SOURCE, str(SCRIPT), "exec"), self.module)
        self.module["STATE_DIR"] = Path(self.temp.name)
        self.module["ROOT"] = SCRIPT.parent
        self.module["note"] = lambda message: None
        self.active = "old-release"
        self.calls = []
        self.module["active_deployment"] = lambda: {
            "id": self.active, "projectId": self.module["PROJECT"],
        }
        self.module["vc"] = self.command
        self.module["verify"] = lambda *args, **kwargs: None

    def command(self, *args, **kwargs):
        self.calls.append(args)
        if args[0] == "deploy":
            return json.dumps({"deployment": {
                "id": "new-release", "url": "https://staged.example", "readyState": "READY",
            }}), "build log"
        if args[0] == "promote":
            self.active = "new-release"
        if args[0] == "rollback":
            self.active = args[1]
        return "", ""

    def state(self):
        return json.loads((Path(self.temp.name) / "last-deploy.json").read_text())

    def test_success_promotes_then_records_verified_release(self):
        self.module["migrate"] = lambda: self.fail("Normal deployment must not migrate databases")
        self.module["deploy"]({}, False)
        self.assertEqual(self.active, "new-release")
        self.assertEqual(self.state()["status"], "verified")
        self.assertEqual([call[0] for call in self.calls], ["deploy", "promote"])
        self.assertIn("--skip-domain", self.calls[0])

    def test_first_cutover_builds_migrates_and_verifies_before_promoting(self):
        order = []
        self.module["migrate"] = lambda: order.append("migrate")
        self.module["verify"] = lambda origin, *args, **kwargs: order.append(
            "staged-verify" if kwargs.get("staged") else "production-verify")
        self.module["first_cutover"]({}, "backup-2026-10-26")
        self.assertEqual(self.active, "new-release")
        self.assertEqual(self.state()["status"], "first-cutover-verified")
        self.assertEqual(order, ["migrate", "staged-verify", "production-verify"])
        self.assertEqual([call[0] for call in self.calls], ["deploy", "promote"])

    def test_first_cutover_staged_failure_keeps_old_alias_and_never_promotes(self):
        self.module["migrate"] = lambda: None
        def verify(origin, *args, **kwargs):
            if kwargs.get("staged"):
                raise self.module["DeployError"]("readiness failed")
        self.module["verify"] = verify
        with self.assertRaisesRegex(self.module["DeployError"], "readiness failed"):
            self.module["first_cutover"]({}, "backup-2026-10-26")
        self.assertEqual(self.active, "old-release")
        self.assertEqual(self.state()["status"], "first-cutover-staged-verification-failed")
        self.assertEqual([call[0] for call in self.calls], ["deploy"])

    def test_first_cutover_migration_failure_keeps_old_alias_and_never_verifies(self):
        def fail_migration():
            raise self.module["DeployError"]("migration failed")
        self.module["migrate"] = fail_migration
        self.module["verify"] = lambda *args, **kwargs: self.fail("Must not verify or promote after migration failure")
        with self.assertRaisesRegex(self.module["DeployError"], "migration failed"):
            self.module["first_cutover"]({}, "backup-2026-10-26")
        self.assertEqual(self.active, "old-release")
        self.assertEqual(self.state()["status"], "first-cutover-migration-failed")
        self.assertEqual([call[0] for call in self.calls], ["deploy"])

    def test_first_cutover_never_rolls_back_to_unsafe_previous_release(self):
        self.module["migrate"] = lambda: None
        def verify(origin, *args, **kwargs):
            if not kwargs.get("staged") and self.active == "new-release":
                raise self.module["DeployError"]("production readiness failed")
        self.module["verify"] = verify
        with self.assertRaisesRegex(self.module["DeployError"], "production readiness failed"):
            self.module["first_cutover"]({}, "backup-2026-10-26")
        self.assertEqual(self.active, "new-release")
        self.assertEqual(self.state()["status"], "first-cutover-unverified")
        self.assertNotIn("rollback", [call[0] for call in self.calls])

    def test_first_cutover_requires_exact_origin_and_backup_reference(self):
        for args in (
            ["--first-cutover"],
            ["--first-cutover", "--confirm-production-cutover", "https://wrong.example",
             "--backup-reference", "snapshot-1"],
            ["--first-cutover", "--confirm-production-cutover", self.module["ORIGIN"], "--migrate",
             "--backup-reference", "snapshot-1"],
        ):
            with self.subTest(args=args), patch.object(sys, "argv", ["deploy-vercel.sh", *args]):
                with self.assertRaises(SystemExit):
                    self.module["main"]()
        self.assertEqual(self.calls, [])

    def test_build_failure_never_changes_production(self):
        def fail(*args, **kwargs):
            raise self.module["DeployError"]("Build failed")
        self.module["vc"] = fail
        with self.assertRaises(self.module["DeployError"]):
            self.module["deploy"]({}, False)
        self.assertEqual(self.active, "old-release")
        self.assertEqual(self.state()["status"], "build-failed")

    def test_staged_application_failure_never_promotes(self):
        def fail(*args, **kwargs):
            if kwargs.get("staged"):
                raise self.module["DeployError"]("HTTP 500")
        self.module["verify"] = fail
        with self.assertRaises(self.module["DeployError"]):
            self.module["deploy"]({}, False)
        self.assertEqual(self.active, "old-release")
        self.assertEqual([call[0] for call in self.calls], ["deploy"])

    def test_staged_network_failure_uses_custom_domain_verification(self):
        origins = []
        def verify(origin, *args, **kwargs):
            origins.append(origin)
            if kwargs.get("staged"):
                raise self.module["Unreachable"]("DNS unavailable")
        self.module["verify"] = verify
        self.module["deploy"]({}, False)
        self.assertEqual(origins, [self.module["ORIGIN"], "https://staged.example", self.module["ORIGIN"]])
        self.assertEqual(self.state()["status"], "verified")

    def test_production_failure_rolls_back_and_still_fails(self):
        def verify(origin, *args, **kwargs):
            if self.active == "new-release":
                raise self.module["DeployError"]("Database unavailable")
        self.module["verify"] = verify
        with self.assertRaises(self.module["DeployError"]):
            self.module["deploy"]({}, False)
        self.assertEqual(self.active, "old-release")
        self.assertEqual(self.state()["status"], "rolled-back")
        self.assertEqual([call[0] for call in self.calls], ["deploy", "promote", "rollback"])

    def test_partial_promotion_failure_is_also_rolled_back(self):
        def command(*args, **kwargs):
            result = self.command(*args, **kwargs)
            if args[0] == "promote":
                raise self.module["DeployError"]("CLI lost connection after promotion")
            return result
        self.module["vc"] = command
        with self.assertRaises(self.module["DeployError"]):
            self.module["deploy"]({}, False)
        self.assertEqual(self.active, "old-release")
        self.assertEqual(self.state()["status"], "rolled-back")

    def test_does_not_roll_back_another_operators_deployment(self):
        def verify(origin, *args, **kwargs):
            if self.active == "new-release" and not kwargs.get("staged"):
                self.active = "someone-elses-release"
                raise self.module["DeployError"]("Concurrent deployment")
        self.module["verify"] = verify
        with self.assertRaises(self.module["DeployError"]):
            self.module["deploy"]({}, False)
        self.assertEqual(self.active, "someone-elses-release")
        self.assertNotIn("rollback", [call[0] for call in self.calls])

    def test_does_not_promote_over_a_concurrent_release_during_build(self):
        def verify(*args, **kwargs):
            if kwargs.get("staged"):
                self.active = "someone-elses-release"
        self.module["verify"] = verify
        with self.assertRaises(self.module["DeployError"]):
            self.module["deploy"]({}, False)
        self.assertEqual(self.active, "someone-elses-release")
        self.assertEqual([call[0] for call in self.calls], ["deploy"])

    def test_http_verification_reads_only_non_ai_endpoints(self):
        namespace = {"__name__": "verify_test"}
        exec(compile(SOURCE, str(SCRIPT), "exec"), namespace)
        namespace["note"] = lambda message: None
        paths = []
        class Response(io.BytesIO):
            status = 200
        def response(request, **kwargs):
            self.assertEqual(request.get_method(), "GET")
            paths.append(request.full_url)
            if request.full_url.endswith("/api/v1/readiness"):
                return Response(b'{"status":"ready","checks":{"database":"ready","migrations":"ready","checklist":"ready"}}')
            if "/api/" in request.full_url:
                return Response(b'{"error":"LEGACY_API_RETIRED"}')
            return Response(b"<!DOCTYPE html><html></html>")
        with patch("urllib.request.urlopen", side_effect=response):
            namespace["fetch"] = lambda origin, path, *args: (410, '{"error":"LEGACY_API_RETIRED"}') if (path.startswith("/api/") and path != "/api/v1/readiness") or path == "/health" else (200, response(urllib.request.Request(origin + path)).read().decode())
            namespace["verify"]("https://example.test")
        self.assertEqual(len(paths), 2)
        self.assertFalse(any("messages" in path or "execute" in path for path in paths))

    def test_http_500_is_not_treated_as_network_failure(self):
        namespace = {"__name__": "verify_test"}
        exec(compile(SOURCE, str(SCRIPT), "exec"), namespace)
        error = urllib.error.HTTPError("https://example.test", 500, "Failed", {}, io.BytesIO(b"failed"))
        with patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaises(namespace["DeployError"]) as raised:
                namespace["verify"]("https://example.test", staged=True)
        self.assertNotIsInstance(raised.exception, namespace["Unreachable"])

    def test_unsafe_previous_release_blocks_before_build(self):
        self.module["verify"] = lambda *args, **kwargs: (_ for _ in ()).throw(self.module["DeployError"]("old API open"))
        with self.assertRaisesRegex(self.module["DeployError"], "safe compatible rollback"):
            self.module["deploy"]({}, False)
        self.assertEqual(self.calls, [])

    def test_rollback_failure_never_reports_success(self):
        def verify(origin, *args, **kwargs):
            if self.active == "new-release":
                raise self.module["DeployError"]("new release unavailable")
        self.module["verify"] = verify
        original = self.command
        def command(*args, **kwargs):
            if args[0] == "rollback":
                raise self.module["DeployError"]("rollback failed")
            return original(*args, **kwargs)
        self.module["vc"] = command
        with self.assertRaisesRegex(self.module["DeployError"], "rollback failed"):
            self.module["deploy"]({}, False)
        self.assertEqual(self.state()["status"], "rolling-back")

    def test_migration_uses_only_reviewed_referral_runner(self):
        backend = SCRIPT.parent / "src/backend"
        sys.path.insert(0, str(backend))
        self.addCleanup(lambda: sys.path.remove(str(backend)))
        calls = []
        database = types.ModuleType("referral_review.persistence.database")
        database.create_engine = lambda url: Engine()
        migrations = types.ModuleType("referral_review.persistence.migrations")
        migrations.HEAD = "rr_0006"
        migrations.REVIEWED_REVISIONS = frozenset({"rr_0006"})
        migrations.upgrade = lambda conn, target: calls.append(target)
        migrations.current_revision = lambda conn: migrations.HEAD
        dotenv = types.ModuleType("dotenv")
        dotenv.dotenv_values = lambda path: {}
        class Engine:
            def begin(self):
                class Transaction:
                    def __enter__(self):
                        return object()
                    def __exit__(self, *args):
                        pass
                return Transaction()
            def dispose(self):
                calls.append("disposed")
        with patch.object(sys, "executable", str(backend / "venv/bin/python")), \
             patch.dict("os.environ", {"DATABASE_URL": "postgresql://user:pass@localhost/rr_test"}), \
             patch.dict(sys.modules, {"dotenv": dotenv, "referral_review.persistence.database": database,
                                      "referral_review.persistence.migrations": migrations}):
            self.module["migrate"]()
        self.assertEqual(calls, [migrations.HEAD, "disposed"])


if __name__ == "__main__":
    unittest.main()
