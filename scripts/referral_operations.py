#!/usr/bin/env python3
"""Operator CLI: default/read previews use GET; every mutation requires --apply.

Credentials come only from RR_MAINTENANCE_TOKEN and RR_MAINTENANCE_SITE_ORIGIN.
No redirects, model calls, automatic retries, exception details or error-body output.
"""
import argparse
import json
import os
import re
import sys
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from uuid import UUID


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", nargs="?", default="status", choices=("status", "reconcile", "retry-payment", "retry-cleanup"))
    parser.add_argument("--run-id", type=UUID)
    parser.add_argument("--request-id", type=UUID)
    parser.add_argument("--event-id")
    parser.add_argument("--job-id", type=UUID)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--retry-exhausted", action="store_true")
    args = parser.parse_args(argv)
    if args.action == "reconcile" and args.run_id is None:
        parser.error("reconcile requires --run-id")
    if args.action == "retry-payment" and not re.fullmatch(r"evt_[A-Za-z0-9_]{1,180}", args.event_id or ""):
        parser.error("retry-payment requires a valid --event-id")
    if args.action == "retry-cleanup" and args.job_id is None:
        parser.error("retry-cleanup requires --job-id")
    if args.apply and args.action == "status":
        parser.error("status is read-only")
    if args.retry_exhausted and (args.action != "retry-cleanup" or not args.apply):
        parser.error("--retry-exhausted requires retry-cleanup --apply")
    origin = os.environ.get("RR_MAINTENANCE_SITE_ORIGIN", "").rstrip("/")
    secret = os.environ.get("RR_MAINTENANCE_TOKEN", "")
    try:
        parsed = urlsplit(origin)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.path or parsed.query or parsed.fragment or not secret):
            raise ValueError()
        url = origin + "/api/v1/internal/operations"
        data = None
        if args.apply:
            body = {"action": args.action.replace("-", "_"), "apply": True}
            if args.action == "reconcile":
                body["run_id"] = str(args.run_id)
            elif args.action == "retry-payment":
                body["event_id"] = args.event_id
            else:
                body.update(job_id=str(args.job_id), retry_exhausted=args.retry_exhausted)
            data = json.dumps(body).encode()
        else:
            query = {key: str(value) for key, value in (("run_id", args.run_id), ("request_id", args.request_id)) if value}
            if query:
                url += "?" + urlencode(query)
        request = Request(url, method="POST" if data else "GET", data=data,
            headers={"Authorization": "Bearer " + secret, "Content-Type": "application/json"})
        with build_opener(NoRedirect()).open(request, timeout=55) as response:
            if response.status != 200:
                raise ValueError()
            payload = json.loads(response.read(262145))
        if not isinstance(payload, dict) or set(payload) != {"budgets", "alerts", "runs", "audit", "cleanup_jobs", "limit", "audit_limit"}:
            raise ValueError()
    except Exception:
        print("Operator request failed. Check readiness, operator credentials and recorded state before retrying.", file=sys.stderr)
        return 1
    print(json.dumps(payload, indent=2, sort_keys=True))
    if args.action != "status" and not args.apply:
        print("Read-only preview. Repeat the selected action with --apply to request recovery.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
