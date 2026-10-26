"""Uvicorn access logs retain paths/statuses without OAuth query parameters."""

from copy import deepcopy
import logging

from uvicorn.config import LOGGING_CONFIG


class QuerylessAccessLog(logging.Filter):
    def filter(self, record):
        # Uvicorn's access formatter expects these five positional arguments.
        # Unknown shapes fail closed rather than printing an unreviewed message.
        if not isinstance(record.args, tuple) or len(record.args) != 5:
            return False
        client, method, target, version, status = record.args
        if not isinstance(target, str):
            return False
        record.args = (client, method, target.split("?", 1)[0], version, status)
        return True


def access_log_config():
    config = deepcopy(LOGGING_CONFIG)
    config["filters"] = {"queryless": {"()": QuerylessAccessLog}}
    config["handlers"]["access"]["filters"] = ["queryless"]
    return config
