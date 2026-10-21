"""Private object adapters. Only server-generated opaque keys are accepted.

No public URLs, overwrite, redirects, implicit local fallback or SDK retries.
Operations run outside database transactions and outside the async event loop.
"""

from contextlib import contextmanager
import os
from pathlib import Path
import re
import secrets
import stat
from typing import Protocol
from uuid import UUID

from ..config import ConfigurationError

MAX_BYTES = 2 * 1024 * 1024
KEY = re.compile(r"rr-[0-9a-f]{32}-[0-9a-f]{32}\.bin\Z")


class StorageUnavailable(Exception):
    def __init__(self):
        super().__init__("Private storage operation failed")


class ObjectStore(Protocol):
    def write(self, key: str, body: bytes, content_type: str) -> None: ...
    def read(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...


def object_key(document_id: UUID) -> str:
    return f"rr-{document_id.hex}-{secrets.token_hex(16)}.bin"


def check_key(key: str):
    if not KEY.fullmatch(key):
        raise StorageUnavailable()


class LocalStore:
    def __init__(self, directory: str):
        path = Path(directory).expanduser()
        repository = Path(__file__).resolve().parents[4]
        resolved = path.resolve()
        if (not path.is_absolute() or path.is_symlink() or resolved.is_relative_to(repository)
            or "public" in resolved.parts):
            raise ConfigurationError("RR_PRIVATE_STORAGE_DIR must be an absolute private directory outside the repository and public roots")
        self.directory = resolved

    @contextmanager
    def _root(self):
        try:
            self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                info = os.fstat(fd)
                if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
                    raise StorageUnavailable()
                yield fd
            finally:
                os.close(fd)
        except OSError:
            raise StorageUnavailable() from None

    def write(self, key: str, body: bytes, content_type: str) -> None:
        check_key(key)
        if len(body) > MAX_BYTES:
            raise StorageUnavailable()
        with self._root() as root:
            with os.fdopen(os.open(key, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                   0o600, dir_fd=root), "wb") as file:
                file.write(body)
                file.flush()
                os.fsync(file.fileno())

    def read(self, key: str) -> bytes:
        check_key(key)
        with self._root() as root:
            with os.fdopen(os.open(key, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=root), "rb") as file:
                info = os.fstat(file.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_mode & 0o077:
                    raise StorageUnavailable()
                body = file.read(MAX_BYTES + 1)
                if len(body) > MAX_BYTES:
                    raise StorageUnavailable()
                return body

    def delete(self, key: str) -> None:
        check_key(key)
        with self._root() as root:
            try:
                os.unlink(key, dir_fd=root)
            except FileNotFoundError:
                pass


class PrivateBlobStore:
    def __init__(self, token: str, *, http_client_factory=None):
        from vercel.blob import sync as blob

        match = re.fullmatch(r"vercel_blob_rw_([A-Za-z0-9]+)_([A-Za-z0-9_-]+)", token)
        if not match:
            raise ConfigurationError("BLOB_READ_WRITE_TOKEN has an invalid format")
        self._credentials = blob.BlobCredentials(token=token, store_id=match[1])
        self._http_client_factory = http_client_factory

    @contextmanager
    def _session(self):
        import httpx2
        from vercel.api import session
        from vercel.blob import sync as blob

        options = blob.SyncBlobServiceOptions(base_url="https://vercel.com/api/blob",
                                             credentials_factory=lambda: self._credentials)
        factory = self._http_client_factory or (lambda: httpx2.Client(timeout=30, follow_redirects=False))
        try:
            with session(service_options=[options], httpx_client_factory=factory):
                yield blob
        except Exception:
            # Provider bodies/URLs/token must never escape into an application log.
            raise StorageUnavailable() from None

    def write(self, key: str, body: bytes, content_type: str) -> None:
        check_key(key)
        if len(body) > MAX_BYTES:
            raise StorageUnavailable()
        with self._session() as blob:
            result = blob.put_blob(key, body, access="private", content_type=content_type,
                                   add_random_suffix=False, allow_overwrite=False, cache_control_max_age=60)
            if result.pathname != key or ".private.blob.vercel-storage.com/" not in result.url:
                raise StorageUnavailable()

    def read(self, key: str) -> bytes:
        check_key(key)
        with self._session() as blob:
            with blob.stream_blob(key, access="private") as download:
                body = bytearray()
                for chunk in download:
                    if len(body) + len(chunk) > MAX_BYTES:
                        raise StorageUnavailable()
                    body.extend(chunk)
                return bytes(body)

    def delete(self, key: str) -> None:
        check_key(key)
        with self._session() as blob:
            blob.delete_blob(key)
