"""Exercise deployment failure/recovery paths without changing Vercel or calling AI."""

import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error


SCRIPT = Path(__file__).resolve().parents[1] / "deploy-vercel.sh"
SOURCE = SCRIPT.read_text().split("<<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.module = {"__name__": "deploy_workflow_test"}
        exec(compile(SOURCE, str(SCRIPT), "exec"), self.module)
        self.module["STATE_DIR"] = Path(self.temp.name)
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
        self.assertEqual(origins, ["https://staged.example", self.module["ORIGIN"]])
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
            if not kwargs.get("staged"):
                self.active = "someone-elses-release"
                raise self.module["DeployError"]("Concurrent deployment")
        self.module["verify"] = verify
        with self.assertRaises(self.module["DeployError"]):
            self.module["deploy"]({}, False)
        self.assertEqual(self.active, "someone-elses-release")
        self.assertNotIn("rollback", [call[0] for call in self.calls])

    def test_does_not_promote_over_a_concurrent_release_during_build(self):
        def verify(*args, **kwargs):
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
            if request.full_url.endswith("/health"):
                return Response(b'{"status":"healthy"}')
            if "/api/conversations?patientId=deploy-check-" in request.full_url:
                return Response(b'{"conversations":[],"total":0}')
            return Response(b"<!DOCTYPE html><html></html>")
        with patch("urllib.request.urlopen", side_effect=response):
            namespace["verify"]("https://example.test")
        self.assertEqual(len(paths), 3)
        self.assertFalse(any("messages" in path or "diagnose" in path for path in paths))

    def test_http_500_is_not_treated_as_network_failure(self):
        namespace = {"__name__": "verify_test"}
        exec(compile(SOURCE, str(SCRIPT), "exec"), namespace)
        error = urllib.error.HTTPError("https://example.test", 500, "Failed", {}, None)
        with patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaises(namespace["DeployError"]) as raised:
                namespace["verify"]("https://example.test", staged=True)
        self.assertNotIsInstance(raised.exception, namespace["Unreachable"])


if __name__ == "__main__":
    unittest.main()
