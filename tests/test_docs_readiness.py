"""Documentation and release-readiness consistency checks."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


def test_install_extras_are_quoted_for_zsh() -> None:
    """Shell install hints quote extras so zsh does not glob them."""
    pattern = re.compile(r"(?<![\"'])promptune\[[^]]+\]")
    rel_paths = [
        "README.md",
        "docs/ARCHITECTURE.md",
        "docs/USER_GUIDE.md",
        "docs/MANUAL_TESTING.md",
        "promptune/mcp/server.py",
    ]
    offenders: list[str] = []

    for rel_path in rel_paths:
        for line_no, line in enumerate(_read(rel_path).splitlines(), start=1):
            if (
                "pip install" in line or "pipx install" in line
            ) and pattern.search(line):
                offenders.append(f"{rel_path}:{line_no}: {line.strip()}")

    assert offenders == []


def test_coverage_gate_is_consistent_across_docs_and_ci() -> None:
    """Docs and workflows advertise the same coverage gate."""
    targets = {
        "README.md": r"Coverage gate:\s*.?\s*(\d+)%",
        "docs/VERIFICATION_REPORT.md": r"--cov-fail-under=(\d+)",
        ".github/workflows/ci.yml": r"--cov-fail-under=(\d+)",
        ".github/workflows/release.yml": r"--cov-fail-under=(\d+)",
    }
    values: dict[str, str] = {}

    for rel_path, regex in targets.items():
        match = re.search(regex, _read(rel_path))
        assert match is not None, rel_path
        values[rel_path] = match.group(1)

    assert len(set(values.values())) == 1, values


def test_macos_daemon_modules_are_not_globally_omitted() -> None:
    """Global coverage config should not hide macOS daemon tests on macOS."""
    pyproject = _read("pyproject.toml")

    assert "promptune/daemon/clipboard.py" not in pyproject
    assert "promptune/daemon/ipc.py" not in pyproject


def test_linux_coverage_keeps_shared_daemon_modules_visible() -> None:
    """Linux coverage omit only excludes platform-specific daemon modules."""
    linux_cov = _read(".coveragerc-linux")

    assert "promptune/daemon/ipc.py" not in linux_cov
    assert "promptune/daemon/prewarm.py" not in linux_cov


def test_manual_auto_enhance_docs_match_hook_contract() -> None:
    """Manual gate docs describe stdout context injection and exit 0."""
    manual = _read("docs/MANUAL_TESTING.md")
    section_match = re.search(
        r"## 24\. Auto-Enhance Gate(?P<section>.*?)(?:\n---|\Z)",
        manual,
        re.S,
    )
    assert section_match is not None
    section = section_match.group("section")

    assert "exit 1" not in section
    assert "clipboard" not in section.lower()
    assert "additionalContext" in section
    assert "exit 0" in section


def test_release_runs_x11_integration_before_build() -> None:
    """Release validation includes the Xvfb-backed X11 smoke suite."""
    release_yml = _read(".github/workflows/release.yml")

    assert "xvfb-run -a pytest -m x11" in release_yml


def test_release_checks_built_distribution() -> None:
    """Release build validates the wheel users will install."""
    release_yml = _read(".github/workflows/release.yml")

    assert "twine check dist/*" in release_yml
    assert "pip install dist/" in release_yml
    assert "promptune --version" in release_yml
    assert "python -m promptune --help" in release_yml


def test_release_publish_and_release_are_tag_gated() -> None:
    """Manual branch dispatch must not publish artifacts."""
    release_yml = _read(".github/workflows/release.yml")

    assert release_yml.count("startsWith(github.ref, 'refs/tags/v')") >= 2


def test_github_release_waits_for_pypi_publish() -> None:
    """GitHub Release is created only after PyPI publish succeeds."""
    release_yml = _read(".github/workflows/release.yml")

    assert re.search(r"\n  publish:\n(?:.*\n)*?    needs: build", release_yml)
    assert re.search(r"\n  release:\n(?:.*\n)*?    needs: publish", release_yml)


def test_public_config_docs_do_not_advertise_removed_format_style() -> None:
    """Public config docs should not mention removed provider formatting."""
    public_docs = [
        "README.md",
        "docs/USER_GUIDE.md",
        "docs/ARCHITECTURE.md",
        "config.example.toml",
    ]
    offenders: list[str] = []

    for rel_path in public_docs:
        for line_no, line in enumerate(_read(rel_path).splitlines(), start=1):
            if re.search(r"\bformat[_ ]style\b|\bformat overrides\b", line):
                offenders.append(f"{rel_path}:{line_no}: {line.strip()}")

    assert offenders == []


def test_verification_report_has_no_stale_formatter_noop_note() -> None:
    """Verification report should not keep stale current-state format notes."""
    report = _read("docs/VERIFICATION_REPORT.md")

    assert "currently a no-op" not in report
    assert "--format-style" not in report
