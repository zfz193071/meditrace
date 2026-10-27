#!/usr/bin/env python3
"""Prepare a static-only Vercel bundle, or verify its public HTTPS deployment."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import urlopen

from build_portfolio import LocalReferences, ROUTES, verify

PROJECT = "meditrace-portfolio-mvp"
SCOPE = "lucyzhus-projects"


def prepare(site):
    verify(site)
    # Outside the checkout so the existing Services config/project link is never inherited.
    bundle = Path(tempfile.mkdtemp(prefix="meditrace-portfolio-release-"))
    output = bundle / ".vercel/output"
    shutil.copytree(site, output / "static")
    (output / "config.json").write_text(json.dumps({
        "version": 3,
        "routes": [
            {"src": "/(demo|project|evaluation)", "status": 308, "headers": {"Location": "/$1/"}},
            {"src": "/", "dest": "/index.html"},
            {"src": "/(demo|project|evaluation)/", "dest": "/$1/index.html"},
            {"handle": "filesystem"},
            {"src": "/.*", "status": 404, "dest": "/404.html"},
        ],
    }, indent=2) + "\n")
    (bundle / "vercel.json").write_text(json.dumps({"framework": None, "git": {"deploymentEnabled": False}}, indent=2) + "\n")
    print(bundle)
    print(f"Static bundle only. Deploy from this directory with --prebuilt --prod --project {PROJECT} --scope {SCOPE}.")
    return bundle


def verify_public(site, origin):
    verify(site)
    parsed = urlsplit(origin)
    if parsed.scheme != "https" or parsed.hostname != PROJECT + ".vercel.app" or parsed.path not in ("", "/") or parsed.query or parsed.fragment or parsed.username or parsed.port:
        raise ValueError("Verify only the independent portfolio project's public HTTPS origin")
    origin = origin.rstrip("/")
    results = []

    def read(route, expected_status, expected_file=None):
        try:
            response = urlopen(origin + route, timeout=30)
        except HTTPError as error:
            response = error
        with response:
            body = response.read()
            if response.status != expected_status or not response.url.startswith(origin + "/"):
                raise RuntimeError(f"Unexpected response for {route}: {response.status} {response.url}")
            if expected_file and body != expected_file.read_bytes():
                raise RuntimeError(f"Deployed bytes differ from the verified artifact: {route}")
            results.append({"path": route, "status": response.status, "sha256": hashlib.sha256(body).hexdigest()})

    resources = set()
    for route in ROUTES:
        page = site / route.lstrip("/") / "index.html"
        read(route, 200, page)
        parser = LocalReferences()
        parser.feed(page.read_text())
        resources.update(parser.paths)
    for resource in sorted(resources):
        file = site / resource.lstrip("/")
        if file.is_file():
            read(resource, 200, file)
    for route in ("/demo", "/project", "/evaluation"):
        read(route, 200, site / route.lstrip("/") / "index.html")
    for route in ("/workspace/", "/login/", "/account/", "/api/v1/readiness", "/api/v1/auth/session", "/not-a-portfolio-page"):
        read(route, 404)
    report = {"origin": origin, "artifact": site.parent.name, "checks": results,
              "limits": "Unauthenticated HTTPS GET and artifact-byte verification; no model calls or private workspace acceptance"}
    (site.parent / "public-verification.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"Verified {len(results)} public HTTP checks at {origin}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "verify"))
    parser.add_argument("site", type=Path)
    parser.add_argument("--origin", default="https://" + PROJECT + ".vercel.app")
    args = parser.parse_args()
    site = args.site.resolve(strict=True)
    if args.action == "prepare":
        prepare(site)
    else:
        verify_public(site, args.origin)


if __name__ == "__main__":
    main()
