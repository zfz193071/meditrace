"""Probe the guard with synthetic targets; nothing should reach the network."""

import asyncio
import os
from pathlib import Path
import socket
import subprocess
import sys
import urllib.request

import httpx
import pytest
import requests
from pydantic import SecretStr

from network_guard import NetworkBlocked
from referral_review.extraction.adapters import DeepSeekAdapter


@pytest.mark.expects_network_block
@pytest.mark.parametrize("resolve,args", [
    (socket.getaddrinfo, ("api.deepseek.com", 443)),
    (socket.gethostbyname, ("api.deepseek.com",)),
    (socket.gethostbyname_ex, ("api.deepseek.com",)),
    (socket.gethostbyaddr, ("192.0.2.1",)),
    (socket.getnameinfo, (("192.0.2.1", 443), 0)),
])
def test_dns_blocked_without_echoing_target(resolve, args):
    with pytest.raises(NetworkBlocked) as caught:
        resolve(*args)
    assert str(args[0]) not in str(caught.value)


@pytest.mark.expects_network_block
@pytest.mark.parametrize("family,address", [
    (socket.AF_INET, ("192.0.2.1", 443)),
    (socket.AF_INET6, ("2001:db8::1", 443)),
])
@pytest.mark.parametrize("operation", ["connect", "connect_ex", "sendto", "sendmsg"])
def test_numeric_socket_destinations_blocked(family, address, operation):
    with socket.socket(family, socket.SOCK_DGRAM if operation.startswith("send") else socket.SOCK_STREAM) as sock:
        with pytest.raises(NetworkBlocked):
            if operation == "sendto":
                sock.sendto(b"synthetic", address)
            elif operation == "sendmsg":
                sock.sendmsg([b"synthetic"], [], 0, address)
            else:
                getattr(sock, operation)(address)


@pytest.mark.expects_network_block
def test_unmocked_sync_http_clients_blocked():
    url = "https://api.deepseek.com/synthetic-probe?secret=must-not-echo"
    clients = [
        lambda: httpx.get(url, trust_env=False),
        lambda: urllib.request.build_opener(urllib.request.ProxyHandler({})).open(url),
    ]
    with requests.Session() as session:
        session.trust_env = False
        clients.append(lambda: session.get(url))
        for call in clients:
            with pytest.raises(NetworkBlocked) as caught:
                call()
            assert "must-not-echo" not in str(caught.value)


@pytest.mark.expects_network_block
async def test_unmocked_async_http_client_blocked():
    async with httpx.AsyncClient(trust_env=False) as client:
        with pytest.raises(NetworkBlocked):
            await client.get("https://api.deepseek.com/synthetic-probe")


@pytest.mark.expects_network_block
async def test_real_adapter_without_mock_cannot_dispatch():
    with pytest.raises(NetworkBlocked):
        await DeepSeekAdapter(SecretStr("synthetic-not-a-key")).complete({"synthetic": True})


async def test_mock_transport_and_event_loop_still_work():
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"fake": True}))) as client:
        assert (await client.get("https://api.deepseek.com/synthetic-probe")).json() == {"fake": True}
    left, right = socket.socketpair()
    try:
        left.send(b"ok")
        assert right.recv(2) == b"ok"
        await asyncio.sleep(0)
    finally:
        left.close()
        right.close()


@pytest.mark.parametrize("depth", [0, 1])
def test_python_children_inherit_guard_before_imports(tmp_path, depth):
    probe = tmp_path / "probe.py"
    probe.write_text('''import socket
from network_guard import NetworkBlocked
try:
    socket.getaddrinfo("api.deepseek.com", 443)
except NetworkBlocked:
    print("blocked")
else:
    raise AssertionError("network guard missing")
''')
    command = [sys.executable, str(probe)]
    if depth:
        command = [sys.executable, "-c", f"import subprocess; subprocess.run({command!r}, check=True)"]
    result = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "blocked"


def test_explicit_bootstrap_for_standalone_replay(tmp_path):
    guard_path = Path(__file__).resolve().parents[1] / "offline"
    result = subprocess.run(
        [sys.executable, "-c", "import network_guard; assert network_guard._installed; print('guard active')"],
        cwd=tmp_path, env={**os.environ, "PYTHONPATH": str(guard_path), "MEDITRACE_TEST_NETWORK_GUARD": "1"},
        capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "guard active"


def test_caught_network_error_still_fails_the_test(tmp_path):
    probe = tmp_path / "test_swallowed.py"
    probe.write_text('''import socket
def test_swallowed():
    try:
        socket.getaddrinfo("api.deepseek.com", 443)
    except RuntimeError:
        pass
''')
    plugin_path = str(Path(__file__).resolve().parent)
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "conftest", "-q", str(probe)],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": os.pathsep.join([plugin_path, os.environ["PYTHONPATH"]])},
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "Test attempted Internet access" in result.stdout
