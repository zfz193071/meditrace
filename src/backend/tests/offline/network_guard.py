"""Test-only tripwire for Python Internet sockets, not an OS network sandbox.

Unix sockets remain available to asyncio/multiprocessing. Native libpq connections
are outside this boundary; CI uses only its disposable PostgreSQL service.
Never include destinations, credentials or request contents in diagnostics.
"""

import socket


class NetworkBlocked(RuntimeError):
    pass


blocked_attempts = 0
_installed = False


def _deny(*args, **kwargs):
    global blocked_attempts
    blocked_attempts += 1
    raise NetworkBlocked("Offline test blocked Python Internet access; use a mock transport")


def _guard_method(original):
    def guarded(sock, *args, **kwargs):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            return _deny()
        return original(sock, *args, **kwargs)

    return guarded


def install():
    global _installed
    if _installed:
        return
    # Block name resolution as well as direct numeric-address TCP/UDP traffic.
    for name in ("getaddrinfo", "gethostbyname", "gethostbyname_ex", "gethostbyaddr", "getnameinfo"):
        setattr(socket, name, _deny)
    for name in ("connect", "connect_ex", "sendto", "sendmsg"):
        if hasattr(socket.socket, name):
            setattr(socket.socket, name, _guard_method(getattr(socket.socket, name)))
    _installed = True
