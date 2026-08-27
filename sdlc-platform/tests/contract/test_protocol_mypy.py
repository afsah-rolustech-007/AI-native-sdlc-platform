"""mypy must reject a class that does not implement ModelAdapter."""

import subprocess
import sys
from pathlib import Path

SAMPLE = Path(__file__).with_name("incomplete_adapter_sample.py")


def test_incomplete_adapter_fails_mypy() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mypy",
            str(SAMPLE),
            "--pretty",
            "--show-error-codes",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0, result.stdout + result.stderr
    combined = result.stdout + result.stderr
    assert "Incomplete" in combined or "ModelAdapter" in combined
