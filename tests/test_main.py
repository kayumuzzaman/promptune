"""Smoke test for python -m promptune."""

from __future__ import annotations

import runpy
import subprocess
import sys
from unittest.mock import patch


def test_module_entry_point_invokes_main() -> None:
    """`python -m promptune` calls promptune.cli.main()."""
    with patch("promptune.cli.main") as mock_main:
        runpy.run_module("promptune", run_name="__main__", alter_sys=True)
    mock_main.assert_called_once()


def test_module_entry_point_help_subprocess() -> None:
    """End-to-end smoke: `python -m promptune --help` exits 0."""
    result = subprocess.run(
        [sys.executable, "-m", "promptune", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    assert "promptune" in result.stdout.lower()
