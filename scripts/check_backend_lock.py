#!/usr/bin/env python3
"""Verify pyproject -> uv.lock -> runtime requirements without modifying files."""

import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
uv = os.environ.get("UV", "uv")
subprocess.run([uv, "lock", "--project", "src/backend", "--check", "--offline"], cwd=ROOT, check=True)
result = subprocess.run(
    [uv, "export", "--project", "src/backend", "--frozen", "--no-dev", "--no-emit-project", "--no-header"],
    cwd=ROOT, check=True, capture_output=True, text=True,
)
existing = (ROOT / "src/backend/requirements.txt").read_text()
body = "\n".join(line for line in existing.splitlines() if not line.startswith("#")) + "\n"
if body != result.stdout:
    sys.exit("Backend requirements drift: regenerate with the documented uv export command")
root_lines = [line for line in (ROOT / "requirements.txt").read_text().splitlines() if line and not line.startswith("#")]
if root_lines != ["-r src/backend/requirements.txt"]:
    sys.exit("Root requirements must only delegate to the generated backend requirements")
print("Backend lock and runtime requirements match.")
