"""Bounded fixture reads: validate paths before touching source contents."""
import json
import os
from pathlib import Path
import stat


def fixture_bytes(root, relative, limit=8_000_000):
    relative = Path(relative)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise ValueError("Invalid fixture path")
    root = Path(root)
    if root.is_symlink():
        raise ValueError("Invalid fixture path")
    directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in relative.parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            os.close(directory)
            directory = child
        descriptor = os.open(relative.parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        with os.fdopen(descriptor, "rb") as file:
            info = os.fstat(file.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
                raise ValueError("Invalid or oversized fixture file")
            body = file.read(limit + 1)
    except OSError:
        raise ValueError("Invalid fixture path") from None
    finally:
        os.close(directory)
    if len(body) > limit:
        raise ValueError("Invalid or oversized fixture file")
    return body


def unique_json(body):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result
    return json.loads(body, object_pairs_hook=pairs)
