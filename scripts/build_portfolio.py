#!/usr/bin/env python3
"""Build and check a standalone, public-only static portfolio without service keys."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "src/frontend"
ROUTES = ("/", "/demo/", "/project/", "/evaluation/")
FILES = (
    "package.json", "tsconfig.json", "postcss.config.js", "tailwind.config.js",
    "app/layout.tsx", "app/globals.css", "app/page.tsx", "app/portfolio.css",
    "app/demo/page.tsx", "app/project/page.tsx", "app/evaluation/page.tsx",
    "app/evaluation/evaluation.css", "app/workspace/workspace.css",
    "public/evaluation/offline-summary.json",
)


class LocalReferences(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = set()

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key in ("href", "src") and value and value.startswith("/"):
                parsed = urlsplit(value)
                if not parsed.netloc:
                    self.paths.add(unquote(parsed.path))


def verify(output):
    expected = {route.lstrip("/") + "index.html" for route in ROUTES}
    html = {path.relative_to(output).as_posix() for path in output.rglob("*.html")}
    allowed = expected | {"404.html", "404/index.html", "_not-found/index.html"}
    if not expected.issubset(html) or html - allowed:
        raise RuntimeError(f"Unexpected exported pages: {sorted(html)}")
    for page in html:
        parser = LocalReferences()
        parser.feed((output / page).read_text())
        for reference in parser.paths:
            target = output / reference.lstrip("/")
            if not target.is_file() and not (target / "index.html").is_file():
                raise RuntimeError(f"Broken local reference in {page}: {reference}")
    for path in output.rglob("*"):
        if path.is_symlink() or path.name.startswith(".env") or path.name in {"node_modules", ".vercel"}:
            raise RuntimeError(f"Unexpected build content: {path.relative_to(output)}")
    return sorted(html)


def main():
    node = shutil.which("node")
    if not node or not (FRONTEND / "node_modules/next/dist/bin/next").exists():
        raise SystemExit("Install the locked frontend dependencies before building the portfolio.")
    artifacts = ROOT / "artifacts/portfolio"
    artifacts.mkdir(parents=True, exist_ok=True)
    # Each invocation gets a new directory; no existing build or deployment is overwritten.
    destination = Path(tempfile.mkdtemp(prefix="build-", dir=artifacts))
    with tempfile.TemporaryDirectory(prefix="meditrace-portfolio-") as temporary:
        stage = Path(temporary)
        for name in FILES:
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(FRONTEND / name, target)
        for name in ("components", "lib"):
            shutil.copytree(FRONTEND / name, stage / name)
        (stage / "node_modules").symlink_to(FRONTEND / "node_modules", target_is_directory=True)
        (stage / "next.config.js").write_text(
            'module.exports = { output: "export", trailingSlash: true, reactStrictMode: true };\n'
        )
        environment = {key: os.environ[key] for key in ("PATH", "HOME", "TMPDIR", "SystemRoot") if key in os.environ}
        environment.update(NODE_ENV="production", NEXT_TELEMETRY_DISABLED="1", NEXT_PUBLIC_PORTFOLIO_ONLY="true")
        subprocess.run([node, str(stage / "node_modules/next/dist/bin/next"), "build", "--webpack"],
                       cwd=stage, env=environment, check=True)
        pages = verify(stage / "out")
        shutil.copytree(stage / "out", destination / "site")
    (destination / "verification.json").write_text(json.dumps({
        "routes": list(ROUTES), "html_files": pages,
        "environment": "No .env files, backend or provider keys; existing locked dependencies reused",
        "checks": ["public route allowlist", "local HTML links and assets resolve", "no environment files or symlinks"],
        "deployed": False,
    }, indent=2) + "\n")
    print(f"Verified static portfolio: {destination / 'site'}", flush=True)
    print("Publish only the site directory to a separate static host; no service was started or deployed.", flush=True)


if __name__ == "__main__":
    main()
