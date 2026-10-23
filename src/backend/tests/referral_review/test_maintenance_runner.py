"""Scheduler runner contracts without network or repository secrets."""
import importlib.util
import json
from pathlib import Path

import pytest

path = Path(__file__).resolve().parents[4] / "scripts/referral_maintenance.py"
spec = importlib.util.spec_from_file_location("maintenance_runner", path)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


@pytest.mark.parametrize("backlog,failed,expected,calls", [(0, 0, 0, 2), (1, 0, 1, 10), (1, 1, 1, 1)])
def test_runner_bounded_batches_and_failure_exit(monkeypatch, capsys, backlog, failed, expected, calls):
    monkeypatch.setenv("RR_MAINTENANCE_SITE_ORIGIN", "https://synthetic.example.test")
    monkeypatch.setenv("RR_MAINTENANCE_TOKEN", "operator-secret-sentinel")
    requests = []
    class Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, count):
            if requests[-1].method == "GET":
                return json.dumps({"alerts": {key: 0 for key in runner.ALERT_KEYS}}).encode()
            return json.dumps(dict(processed=1, failed=failed, exhausted=0, backlog=backlog,
                cursor="continue" if backlog else None)).encode()
    class Opener:
        def open(self, request, timeout):
            requests.append(request)
            assert timeout == 55
            assert request.headers["Authorization"] == "Bearer operator-secret-sentinel"
            return Response()
    monkeypatch.setattr(runner, "build_opener", lambda handler: Opener())
    monkeypatch.setattr(runner.time, "sleep", lambda seconds: None)
    assert runner.main() == expected and len(requests) == calls
    output = capsys.readouterr()
    assert "operator-secret-sentinel" not in output.out + output.err


def test_runner_never_forwards_bearer_on_redirect():
    assert runner.NoRedirect().redirect_request(None, None, 302, "", {}, "https://other.example.test") is None


@pytest.mark.parametrize("alert", runner.ALERT_KEYS)
def test_monitor_turns_each_alert_into_failure_without_echoing_payload(alert, capsys):
    class Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, count):
            return json.dumps(dict(alerts={key: int(key == alert) for key in runner.ALERT_KEYS},
                                   ignored="source-secret-sentinel")).encode()
    class Opener:
        def open(self, request, timeout):
            assert request.method == "GET"
            return Response()
    assert runner.monitor(Opener(), "https://synthetic.test", "secret-sentinel") == 1
    output = capsys.readouterr()
    assert "sentinel" not in output.out + output.err


def test_monitor_failures_are_notifications_too(capsys):
    class Opener:
        def open(self, *args, **kwargs):
            raise RuntimeError("secret-sentinel")
    assert runner.monitor(Opener(), "https://synthetic.test", "secret-sentinel") == 1
    output = capsys.readouterr()
    assert "sentinel" not in output.out + output.err
