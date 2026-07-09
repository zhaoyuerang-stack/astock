"""Naming taxonomy guard tests.

Run:
    cd factor_research && python3 tests/test_naming_taxonomy_guard.py
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_naming_taxonomy_guard_passes_current_tree():
    proc = subprocess.run(
        [sys.executable, "scripts/ci/check_naming_taxonomy.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


if __name__ == "__main__":
    test_naming_taxonomy_guard_passes_current_tree()
    print("naming taxonomy guard tests passed")
