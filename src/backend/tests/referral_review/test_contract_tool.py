"""Exercise the same generator CI runs, without editing repository artifacts."""

import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[4]
ARTIFACTS = (
    "contracts/referral-review/openapi.json",
    "contracts/referral-review/domain.schema.json",
    "src/frontend/lib/referral-api/generated.d.ts",
)


def generate(mode, destination):
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts/referral_contracts.py"), mode, "--output-root", str(destination)],
        cwd=ROOT, env={**os.environ, "REFERRAL_PYTHON": sys.executable},
        capture_output=True, text=True,
    )


@pytest.fixture
def generated(tmp_path):
    result = generate("--write", tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    return tmp_path


def test_regeneration_is_byte_identical_and_ci_check_passes(generated):
    before = [(generated / path).read_bytes() for path in ARTIFACTS]
    assert generate("--write", generated).returncode == 0
    assert before == [(generated / path).read_bytes() for path in ARTIFACTS]
    assert generate("--check", generated).returncode == 0


@pytest.mark.parametrize("path", ARTIFACTS)
def test_ci_rejects_manual_artifact_drift(generated, path):
    target = generated / path
    target.write_text(target.read_text() + "\n")
    result = generate("--check", generated)
    assert result.returncode == 1
    assert "Contract drift:" in result.stderr
    assert path in result.stderr
