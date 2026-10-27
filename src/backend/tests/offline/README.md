# Offline Python tests

`tests/referral_review/conftest.py` installs this guard before importing tests.
Python DNS resolution and IPv4/IPv6 connect/connect_ex/sendto/sendmsg raise
`NetworkBlocked`, including loopback destinations. Mock HTTP transports,
in-process ASGI clients and Unix socket pairs remain usable. A per-test fixture
also fails on blocked attempts whose exceptions the application caught.
`expects_network_block` permits deliberate probes to observe the exception;
it never disables blocking.

The conftest exports `MEDITRACE_TEST_NETWORK_GUARD=1` and prepends this directory to
`PYTHONPATH`. Ordinary Python children and multiprocessing spawn workers inherit
`sitecustomize.py`, which installs the guard before application imports. To use
the same protection for a standalone fixture/replay command from the repo root:

```sh
MEDITRACE_TEST_NETWORK_GUARD=1 PYTHONPATH="$PWD/src/backend/tests/offline" \
  src/backend/.venv/bin/python scripts/referral_fixtures.py --check
```

CI applies this bootstrap to standalone fixture/contract checks; pytest installs
it automatically. Dependency installation and vulnerability audits deliberately
run outside the guard because they require registry access. Both test jobs set
`REAL_AI_ENABLED=false` and an empty `DEEPSEEK_API_KEY`, without paid-key secrets.

This is an accidental Python-network-use tripwire, **not an OS sandbox**. Native
libraries such as psycopg2/libpq bypass Python sockets; PostgreSQL CI therefore
uses its own disposable service, not a production connection. Node processes,
external executables, Python launched with `-I`/`-S` or a scrubbed environment,
and code deliberately undoing monkeypatches are outside this protection. The
production PDF parser intentionally gives its fixed worker a minimal environment
without credentials; it does not inherit this test bootstrap. No production
code or runtime network policy is changed. Caught attempts in child processes
are still blocked but are not included in the parent's per-test counter.

`test_offline_network.py` covers DNS, numeric IPv4/IPv6, HTTP clients, an unmocked
DeepSeek adapter with a synthetic key, MockTransport, Unix socket pairs, child
and grandchild startup, standalone bootstrap and swallowed-error test failure.
