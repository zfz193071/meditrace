"""Offline by default, including ordinary Python subprocesses and spawn workers."""

import os
from pathlib import Path
import sys

import pytest


_guard_path = str(Path(__file__).resolve().parents[1] / "offline")
sys.path.insert(0, _guard_path)
import network_guard  # noqa: E402

network_guard.install()
os.environ["RR_TEST_NETWORK_GUARD"] = "1"
_python_paths = os.environ.get("PYTHONPATH", "").split(os.pathsep)
os.environ["PYTHONPATH"] = os.pathsep.join([_guard_path, *[p for p in _python_paths if p and p != _guard_path]])


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "expects_network_block: deliberately probes the offline guard; blocking stays enabled"
    )


@pytest.fixture(autouse=True)
def reject_unexpected_network_attempts(request):
    before = network_guard.blocked_attempts
    yield
    if request.node.get_closest_marker("expects_network_block") is None:
        assert network_guard.blocked_attempts == before, "Test attempted Internet access (even if its exception was caught)"
