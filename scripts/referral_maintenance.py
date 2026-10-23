#!/usr/bin/env python3
"""Invoke protected maintenance in at most ten batches. Never print credentials/URLs."""
import json
import os
import sys
import time
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


ALERT_KEYS = ("financial_halt", "budget_overrun", "persistent_failures", "payment_failures",
              "payment_backlog", "cleanup_failures", "cleanup_exhausted", "cleanup_overdue", "unknown_runs")


def monitor(opener, origin, secret):
    try:
        request = Request(origin + "/api/v1/internal/operations", method="GET",
            headers={"Authorization": "Bearer " + secret})
        with opener.open(request, timeout=55) as response:
            if response.status != 200:
                raise ValueError()
            alerts = json.loads(response.read(262145))["alerts"]
        if set(alerts) != set(ALERT_KEYS) or any(type(alerts[key]) is not int or alerts[key] < 0 for key in ALERT_KEYS):
            raise ValueError()
    except Exception:
        print("Operator monitoring failed; check readiness and credentials.", file=sys.stderr)
        return 1
    print("Operator alerts: " + " ".join(f"{key}={alerts[key]}" for key in ALERT_KEYS))
    return int(any(alerts.values()))


def main():
    origin = os.environ.get("RR_MAINTENANCE_SITE_ORIGIN", "").rstrip("/")
    secret = os.environ.get("RR_MAINTENANCE_TOKEN", "")
    parsed = urlsplit(origin)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
        or parsed.path or parsed.query or parsed.fragment or not secret):
        print("Maintenance requires an HTTPS site origin and a dedicated token.", file=sys.stderr)
        return 1
    opener = build_opener(NoRedirect())
    cursor = None
    for batch in range(10):
        try:
            request = Request(origin + "/api/v1/internal/maintenance", method="POST",
                headers={"Authorization": "Bearer " + secret, "Content-Type": "application/json"},
                data=json.dumps({"limit": 200, "cursor": cursor}).encode())
            with opener.open(request, timeout=55) as response:
                if response.status != 200:
                    raise ValueError()
                body = json.loads(response.read(4096))
            for key in ("processed", "failed", "exhausted", "backlog"):
                if type(body.get(key)) is not int or body[key] < 0:
                    raise ValueError()
            cursor = body.get("cursor")
            if cursor not in (None, "continue") or bool(cursor) != bool(body["backlog"]):
                raise ValueError()
        except Exception:
            print("Maintenance request failed. Check service health and rerun after recovery.", file=sys.stderr)
            return 1
        print(f"Batch {batch + 1}: processed={body['processed']} failed={body['failed']} exhausted={body['exhausted']} backlog={body['backlog']}")
        if body["failed"] or body["exhausted"]:
            print("Maintenance has failed jobs; operator review is required.", file=sys.stderr)
            return 1
        if not body["backlog"]:
            return monitor(opener, origin, secret)
        if batch < 9:
            time.sleep(5)
    print("Maintenance backlog remains after ten batches. Inspect and rerun; cleanup is not complete.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
