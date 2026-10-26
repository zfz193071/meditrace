"""Private, immutable rehearsal recordings. POSIX local disk; never public storage.

The directory lock serializes local writers; the DB dispatch marker remains the
authority across machines. A missing/corrupt recording never permits redispatch.
"""
import fcntl
import os
from pathlib import Path
import stat
from uuid import uuid4

from .files import unique_json
from .planning import canonical, digest


class Journal:
    def __init__(self, plan, *, resume=False):
        self.directory = self.lock = None
        self.plan = plan
        path = Path(plan.output)
        try:
            if not resume:
                path.mkdir(mode=0o700)
            self.directory = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            info = os.fstat(self.directory)
            if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
                raise ValueError("Private journal directory required")
            self.lock = os.open(".lock", os.O_RDWR | (0 if resume else os.O_CREAT) | os.O_NOFOLLOW | os.O_NONBLOCK,
                                0o600, dir_fd=self.directory)
            if not stat.S_ISREG(os.fstat(self.lock).st_mode):
                raise ValueError("Invalid journal lock")
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            binding = dict(format="evaluation-rehearsal-v1", origin="fake", plan_sha256=plan.sha256,
                           plan=plan.model_dump(mode="json"), approval="synthetic_parameters_only")
            if resume:
                if self.read("binding.json") != binding:
                    raise ValueError("Journal belongs to a different plan")
            else:
                self.write("binding.json", binding)
                # Persist the new directory entry as well as its contents.
                parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(parent)
                finally:
                    os.close(parent)
        except BaseException:
            self.close()
            raise

    def close(self):
        for name in ("lock", "directory"):
            descriptor = getattr(self, name)
            if descriptor is not None:
                os.close(descriptor)
                setattr(self, name, None)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def _name(self, name):
        if not name or Path(name).name != name or name in (".", "..", ".lock"):
            raise ValueError("Invalid journal entry")
        if self.directory is None:
            raise ValueError("Journal is closed")

    def read(self, name):
        self._name(name)
        try:
            descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=self.directory)
        except FileNotFoundError:
            return None
        with os.fdopen(descriptor, "rb") as file:
            info = os.fstat(file.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) & 0o077 or info.st_size > 256_000):
                raise ValueError("Invalid journal entry")
            body = file.read(256_001)
        if len(body) > 256_000:
            raise ValueError("Journal entry exceeds limit")
        envelope = unique_json(body)
        if (not isinstance(envelope, dict) or set(envelope) != {"sha256", "record"}
            or digest(envelope["record"]) != envelope["sha256"]):
            raise ValueError("Journal checksum mismatch")
        return envelope["record"]

    def write(self, name, record):
        self._name(name)
        body = canonical(dict(sha256=digest(record), record=record)) + b"\n"
        if len(body) > 256_000:
            raise ValueError("Journal entry exceeds limit")
        previous = self.read(name)
        if previous is not None:
            if previous != record:
                raise ValueError("Journal entries are immutable")
            return
        temporary = ".pending-" + uuid4().hex
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o600, dir_fd=self.directory)
        try:
            with os.fdopen(descriptor, "wb") as file:
                file.write(body)
                file.flush()
                os.fsync(file.fileno())
            # Atomic no-clobber publish. Partial temporary files are never read.
            os.link(temporary, name, src_dir_fd=self.directory, dst_dir_fd=self.directory,
                    follow_symlinks=False)
        finally:
            os.unlink(temporary, dir_fd=self.directory)
            os.fsync(self.directory)
