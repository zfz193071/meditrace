"""Operator commands and notification exits, with no external HTTP."""
import importlib.util
import json
from pathlib import Path
from uuid import uuid4

import pytest

path = Path(__file__).resolve().parents[4] / "scripts/referral_operations.py"
spec = importlib.util.spec_from_file_location("operations_runner", path)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


@pytest.mark.parametrize("action,args", [
    ("status", []), ("reconcile", ["--run-id", str(uuid4())]),
    ("retry-payment", ["--event-id", "evt_retry1"]), ("retry-cleanup", ["--job-id", str(uuid4())]),
])
@pytest.mark.parametrize("apply", [False, True])
def test_cli_is_read_only_unless_explicitly_applied(monkeypatch, capsys, action, args, apply):
    monkeypatch.setenv("RR_MAINTENANCE_SITE_ORIGIN", "https://synthetic.example.test")
    monkeypatch.setenv("RR_MAINTENANCE_TOKEN", "credential-sentinel")
    requests = []
    class Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, count):
            return json.dumps(dict(budgets=[], alerts={}, runs=[], audit=[], cleanup_jobs=[], limit=20, audit_limit=100)).encode()
    class Opener:
        def open(self, request, timeout):
            requests.append(request)
            assert request.headers["Authorization"] == "Bearer credential-sentinel"
            assert "credential-sentinel" not in request.full_url
            return Response()
    monkeypatch.setattr(runner, "build_opener", lambda handler: Opener())
    command = [action, *args, *(["--apply"] if apply else [])]
    if action == "status" and apply:
        with pytest.raises(SystemExit):
            runner.main(command)
        assert requests == []
    else:
        assert runner.main(command) == 0
        assert len(requests) == 1
        assert requests[0].method == ("POST" if apply else "GET")
        if apply:
            assert json.loads(requests[0].data)["apply"] is True
    output = capsys.readouterr()
    assert "credential-sentinel" not in output.out + output.err


@pytest.mark.parametrize("origin", ["http://synthetic.test", "https://user:secret@synthetic.test", "https://synthetic.test?key=secret", "https://synthetic.test/path"])
def test_cli_refuses_unsafe_origins_without_leaking(monkeypatch, capsys, origin):
    monkeypatch.setenv("RR_MAINTENANCE_SITE_ORIGIN", origin)
    monkeypatch.setenv("RR_MAINTENANCE_TOKEN", "credential-sentinel")
    assert runner.main([]) == 1
    output = capsys.readouterr()
    assert "secret" not in output.out + output.err


def test_cli_no_redirects_and_errors_never_print_exception(monkeypatch, capsys):
    assert runner.NoRedirect().redirect_request(None, None, 302, "", {}, "https://other.example.test") is None
    monkeypatch.setenv("RR_MAINTENANCE_SITE_ORIGIN", "https://synthetic.example.test")
    monkeypatch.setenv("RR_MAINTENANCE_TOKEN", "credential-sentinel")
    def fail(*args):
        raise RuntimeError("credential-sentinel source-sentinel")
    monkeypatch.setattr(runner, "build_opener", fail)
    assert runner.main([]) == 1
    output = capsys.readouterr()
    assert "sentinel" not in output.out + output.err
