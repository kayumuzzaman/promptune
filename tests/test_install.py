"""Tests for install.sh curl installer script."""

import os
import stat
import subprocess
from pathlib import Path

# Path to the install script
INSTALL_SCRIPT = Path(__file__).parent.parent / "install.sh"


def _run_install(
    env_overrides: dict[str, str] | None = None,
    tmp_path: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run install.sh with optional environment overrides."""
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    # Always use a tmp HOME to avoid polluting real home
    if tmp_path and "HOME" not in (env_overrides or {}):
        env["HOME"] = str(tmp_path)
    return subprocess.run(
        ["bash", str(INSTALL_SCRIPT)],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )


def _create_mock_binary(
    tmp_path: Path, name: str, script: str, make_executable: bool = True
) -> Path:
    """Create a mock binary script in tmp_path/bin/."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    binary = bin_dir / name
    binary.write_text(script)
    if make_executable:
        binary.chmod(binary.stat().st_mode | stat.S_IEXEC)
    return bin_dir


def test_rejects_unsupported_os(tmp_path: Path) -> None:
    """Script exits with error on an unsupported OS (not macOS or Linux)."""
    # Create a fake uname that reports an unsupported OS
    bin_dir = _create_mock_binary(
        tmp_path, "uname", '#!/bin/bash\necho "FreeBSD"'
    )
    result = _run_install(
        env_overrides={"PATH": f"{bin_dir}:{os.environ['PATH']}"},
        tmp_path=tmp_path,
    )
    assert result.returncode != 0
    assert "macOS" in result.stderr or "macOS" in result.stdout


def test_accepts_linux(tmp_path: Path) -> None:
    """Script proceeds past the OS gate on Linux and shows the daemon hint."""
    bin_dir = _create_mock_binary(
        tmp_path, "uname", '#!/bin/bash\necho "Linux"'
    )
    _create_mock_binary(
        tmp_path,
        "python3",
        '#!/bin/bash\n'
        'if [ "$1" = "--version" ]; then echo "Python 3.12.0"; '
        'elif [ "$1" = "-c" ]; then echo "3 12"; '
        'else exit 0; fi',
    )
    _create_mock_binary(tmp_path, "pipx", '#!/bin/bash\nexit 0')
    _create_mock_binary(tmp_path, "promptune", '#!/bin/bash\necho "0.1.0"')
    result = _run_install(
        env_overrides={"PATH": f"{bin_dir}:{os.environ['PATH']}"},
        tmp_path=tmp_path,
    )
    assert result.returncode == 0
    output = result.stdout + result.stderr
    assert "Linux" in output


def test_rejects_root(tmp_path: Path) -> None:
    """Script exits with error when PROMPTUNE_FAKE_EUID=0 is set."""
    # The macOS gate runs before the root check, so mock uname -> Darwin to
    # reach the root check on non-macOS CI runners. The script checks
    # PROMPTUNE_FAKE_EUID for testing, falling back to the real EUID.
    bin_dir = _create_mock_binary(
        tmp_path, "uname", '#!/bin/bash\necho "Darwin"'
    )
    result = _run_install(
        env_overrides={
            "PROMPTUNE_FAKE_EUID": "0",
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
        },
        tmp_path=tmp_path,
    )
    assert result.returncode != 0
    assert "root" in result.stderr or "root" in result.stdout


def test_rejects_old_python(tmp_path: Path) -> None:
    """Script exits with error when Python version is too old."""
    # The -c handler must output "3 8" (matching the script's sys.version_info parsing)
    bin_dir = _create_mock_binary(
        tmp_path,
        "python3",
        '#!/bin/bash\nif [ "$1" = "--version" ]; then echo "Python 3.8.0"; '
        'elif [ "$1" = "-c" ]; then echo "3 8"; else exit 0; fi',
    )
    _create_mock_binary(
        tmp_path, "uname", '#!/bin/bash\necho "Darwin"'
    )
    result = _run_install(
        env_overrides={"PATH": f"{bin_dir}:{os.environ['PATH']}"},
        tmp_path=tmp_path,
    )
    assert result.returncode != 0
    assert "3.9" in result.stderr or "3.9" in result.stdout


def test_prints_next_steps(tmp_path: Path) -> None:
    """Script output includes shell-init instructions and API key reminder."""
    bin_dir = _create_mock_binary(
        tmp_path, "uname", '#!/bin/bash\necho "Darwin"'
    )
    _create_mock_binary(
        tmp_path,
        "python3",
        '#!/bin/bash\n'
        'if [ "$1" = "--version" ]; then echo "Python 3.12.0"; '
        'elif [ "$1" = "-c" ]; then echo "3 12"; '
        'else exit 0; fi',
    )
    _create_mock_binary(
        tmp_path,
        "pipx",
        '#!/bin/bash\nexit 0',
    )
    _create_mock_binary(
        tmp_path,
        "promptune",
        '#!/bin/bash\necho "0.1.0"',
    )
    result = _run_install(
        env_overrides={"PATH": f"{bin_dir}:{os.environ['PATH']}"},
        tmp_path=tmp_path,
    )
    output = result.stdout + result.stderr
    assert "shell-init" in output
    assert "API key" in output or "api key" in output.lower()


def test_network_failure_graceful_exit(tmp_path: Path) -> None:
    """Script prints user-friendly error when pipx install fails."""
    bin_dir = _create_mock_binary(
        tmp_path, "uname", '#!/bin/bash\necho "Darwin"'
    )
    _create_mock_binary(
        tmp_path,
        "python3",
        '#!/bin/bash\n'
        'if [ "$1" = "--version" ]; then echo "Python 3.12.0"; '
        'elif [ "$1" = "-c" ]; then echo "3 12"; '
        'else exit 0; fi',
    )
    _create_mock_binary(
        tmp_path,
        "pipx",
        '#!/bin/bash\necho "ERROR: Could not install" >&2; exit 1',
    )
    result = _run_install(
        env_overrides={"PATH": f"{bin_dir}:{os.environ['PATH']}"},
        tmp_path=tmp_path,
    )
    assert result.returncode != 0
    output = result.stdout + result.stderr
    assert "fail" in output.lower() or "error" in output.lower()


def test_idempotent_install(tmp_path: Path) -> None:
    """Re-running script when promptune is already installed succeeds."""
    bin_dir = _create_mock_binary(
        tmp_path, "uname", '#!/bin/bash\necho "Darwin"'
    )
    _create_mock_binary(
        tmp_path,
        "python3",
        '#!/bin/bash\n'
        'if [ "$1" = "--version" ]; then echo "Python 3.12.0"; '
        'elif [ "$1" = "-c" ]; then echo "3 12"; '
        'else exit 0; fi',
    )
    _create_mock_binary(
        tmp_path,
        "pipx",
        '#!/bin/bash\nexit 0',
    )
    _create_mock_binary(
        tmp_path,
        "promptune",
        '#!/bin/bash\necho "0.1.0"',
    )
    result = _run_install(
        env_overrides={"PATH": f"{bin_dir}:{os.environ['PATH']}"},
        tmp_path=tmp_path,
    )
    assert result.returncode == 0


def test_installs_pipx_if_missing(tmp_path: Path) -> None:
    """Script attempts to install pipx when not found on PATH."""
    bin_dir = _create_mock_binary(
        tmp_path, "uname", '#!/bin/bash\necho "Darwin"'
    )
    _create_mock_binary(
        tmp_path,
        "python3",
        '#!/bin/bash\n'
        'if [ "$1" = "--version" ]; then echo "Python 3.12.0"; '
        'elif [ "$1" = "-c" ]; then echo "3 12"; '
        'elif [ "$1" = "-m" ] && [ "$2" = "pip" ]; then exit 0; '
        'elif [ "$1" = "-m" ] && [ "$2" = "pipx" ]; then exit 0; '
        'else exit 0; fi',
    )
    result = _run_install(
        env_overrides={"PATH": f"{bin_dir}:{os.environ['PATH']}"},
        tmp_path=tmp_path,
    )
    output = result.stdout + result.stderr
    assert "pipx" in output.lower()


def test_installs_promptune(tmp_path: Path) -> None:
    """Script installs promptune via pipx from GitHub."""
    bin_dir = _create_mock_binary(
        tmp_path, "uname", '#!/bin/bash\necho "Darwin"'
    )
    _create_mock_binary(
        tmp_path,
        "python3",
        '#!/bin/bash\n'
        'if [ "$1" = "--version" ]; then echo "Python 3.12.0"; '
        'elif [ "$1" = "-c" ]; then echo "3 12"; '
        'else exit 0; fi',
    )
    _create_mock_binary(
        tmp_path,
        "pipx",
        '#!/bin/bash\necho "pipx: $@"; exit 0',
    )
    _create_mock_binary(
        tmp_path,
        "promptune",
        '#!/bin/bash\necho "0.1.0"',
    )
    result = _run_install(
        env_overrides={"PATH": f"{bin_dir}:{os.environ['PATH']}"},
        tmp_path=tmp_path,
    )
    output = result.stdout + result.stderr
    assert "promptune" in output
    assert result.returncode == 0


def test_verifies_installation(tmp_path: Path) -> None:
    """Script runs promptune --version after install to verify."""
    bin_dir = _create_mock_binary(
        tmp_path, "uname", '#!/bin/bash\necho "Darwin"'
    )
    _create_mock_binary(
        tmp_path,
        "python3",
        '#!/bin/bash\n'
        'if [ "$1" = "--version" ]; then echo "Python 3.12.0"; '
        'elif [ "$1" = "-c" ]; then echo "3 12"; '
        'else exit 0; fi',
    )
    _create_mock_binary(
        tmp_path,
        "pipx",
        '#!/bin/bash\nexit 0',
    )
    _create_mock_binary(
        tmp_path,
        "promptune",
        '#!/bin/bash\necho "0.1.0"',
    )
    result = _run_install(
        env_overrides={"PATH": f"{bin_dir}:{os.environ['PATH']}"},
        tmp_path=tmp_path,
    )
    output = result.stdout + result.stderr
    assert "installed successfully" in output or "0.1.0" in output
