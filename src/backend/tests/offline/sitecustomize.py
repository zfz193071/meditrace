"""Install before imports in Python children that inherit the test environment."""

import os

if os.environ.get("RR_TEST_NETWORK_GUARD") == "1":
    from network_guard import install

    install()
