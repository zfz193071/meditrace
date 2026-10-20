#!/usr/bin/env python3
"""Generate or check canonical OpenAPI / JSON Schema / TypeScript; no network calls."""

import argparse
import difflib
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "src/backend"
FRONTEND = ROOT / "src/frontend"


def find_python() -> str:
    if os.environ.get("REFERRAL_PYTHON"):
        return os.environ["REFERRAL_PYTHON"]
    for path in (BACKEND / ".venv/bin/python", BACKEND / "venv/bin/python"):
        if path.exists():
            return str(path)
    return sys.executable


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--output-root", type=Path, default=ROOT, help="Artifact destination root (also used by isolated drift regression tests)")
    args = parser.parse_args()
    generator = FRONTEND / "node_modules/.bin/openapi-typescript"
    if not generator.exists():
        parser.error("Install locked frontend development dependencies before generating contracts")
    with tempfile.TemporaryDirectory(prefix="meditrace-contracts-") as directory:
        output = Path(directory)
        subprocess.run([find_python(), "-m", "referral_review.export_contracts", "--output-dir", directory], cwd=BACKEND, check=True)
        subprocess.run([str(generator), str(output / "openapi.json"), "--output", str(output / "generated.d.ts"), "--alphabetize"], cwd=FRONTEND, check=True)
        targets = {
            "openapi.json": args.output_root / "contracts/referral-review/openapi.json",
            "domain.schema.json": args.output_root / "contracts/referral-review/domain.schema.json",
            "generated.d.ts": args.output_root / "src/frontend/lib/referral-api/generated.d.ts",
        }
        drift = []
        for name, destination in targets.items():
            generated = (output / name).read_text(encoding="utf-8")
            if args.write:
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(generated, encoding="utf-8")
            else:
                existing = destination.read_text(encoding="utf-8") if destination.exists() else ""
                if existing != generated:
                    drift.append(str(destination.relative_to(args.output_root)))
                    print("".join(list(difflib.unified_diff(existing.splitlines(True), generated.splitlines(True), fromfile=str(destination.relative_to(args.output_root)), tofile="regenerated"))[:60]))
        if drift:
            print("Contract drift: " + ", ".join(drift), file=sys.stderr)
            return 1
    print("Contracts generated." if args.write else "Contracts match their canonical Pydantic schemas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
