"""Individual context collectors — each gathers one signal."""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

# --- Dataclasses ---


@dataclass
class GitContext:
    """Git repository context."""

    branch: str
    recent_commits: list[str]
    modified_files: list[str]
    diff_stats: str
    stash_count: int


@dataclass
class ShellHistoryContext:
    """Shell history context."""

    recent_commands: list[str]
    error_patterns: list[str]
    session_intent: str


@dataclass
class TechStackContext:
    """Tech stack context from marker files."""

    languages: list[str]
    frameworks: list[str]
    package_manager: str | None


@dataclass
class EnvironmentContext:
    """Runtime environment context."""

    in_venv: bool
    in_container: bool
    in_ci: bool
    in_ssh: bool


# --- Helpers ---


def _run_git(
    args: tuple[str, ...], timeout: float = 2.0
) -> str:
    """Run a git command and return stdout."""
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.stdout.strip()


def _safe_git(args: tuple[str, ...], timeout: float = 0.3) -> str:
    """Run a git command, returning '' on any failure or timeout."""
    try:
        return _run_git(args, timeout=timeout)
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return ""


def _find_history_file() -> Path | None:
    """Find the shell history file."""
    home = Path.home()
    candidates = [
        home / ".zsh_history",
        home / ".bash_history",
        home / ".local" / "share" / "fish" / "fish_history",
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def _get_project_root() -> Path:
    """Get project root via git or cwd."""
    root = _safe_git(("rev-parse", "--show-toplevel"), timeout=0.3)
    if root:
        return Path(root)
    return Path.cwd()


# --- Collectors ---


def collect_git() -> GitContext:
    """Collect git context signals; each signal degrades independently."""
    branch = _safe_git(("branch", "--show-current"))
    log_output = _safe_git(("log", "--format=%h|%ar|%s", "-5"))
    recent_commits = [
        line for line in log_output.splitlines() if line.strip()
    ]
    status_output = _safe_git(("status", "--porcelain", "-uno"))
    modified_files = [
        line[2:].strip()
        for line in status_output.splitlines()
        if line.strip()
    ]
    diff_stats = _safe_git(("diff", "--shortstat"))
    stash_output = _safe_git(("stash", "list"))
    stash_count = len(
        [line for line in stash_output.splitlines() if line.strip()]
    )

    return GitContext(
        branch=branch,
        recent_commits=recent_commits,
        modified_files=modified_files,
        diff_stats=diff_stats,
        stash_count=stash_count,
    )


def collect_shell_history(
    max_lines: int = 50,
) -> ShellHistoryContext:
    """Collect recent shell history and detect intent."""
    hist_file = _find_history_file()
    if hist_file is None:
        return ShellHistoryContext(
            recent_commands=[],
            error_patterns=[],
            session_intent="unknown",
        )

    try:
        # Bounded tail read: only the last chunk of the file is loaded, so a
        # multi-GB .zsh_history is never read in full just to grab max_lines.
        tail_bytes = max(max_lines * 1024, 65536)
        seeked = False
        with open(hist_file, "rb") as fh:
            try:
                fh.seek(-tail_bytes, os.SEEK_END)
                seeked = True
            except OSError:
                fh.seek(0)
            raw = fh.read()
        # When we seeked into the middle of the file the first line is likely
        # partial (and may even split a multi-byte char); drop it so decoding
        # never yields a mangled command.
        if seeked:
            newline = raw.find(b"\n")
            if newline != -1:
                raw = raw[newline + 1:]
        lines = raw.decode("utf-8", errors="replace").splitlines()[
            -max_lines:
        ]
    except (OSError, PermissionError):
        return ShellHistoryContext(
            recent_commands=[],
            error_patterns=[],
            session_intent="unknown",
        )

    # Parse zsh extended history: ": timestamp:0;command"
    commands: list[str] = []
    for line in lines:
        match = re.match(r"^:\s*\d+:\d+;(.+)$", line)
        if match:
            commands.append(match.group(1).strip())
        elif not line.startswith(":") and line.strip():
            commands.append(line.strip())

    session_intent = _detect_session_intent(commands)
    error_patterns = _detect_error_patterns(commands)

    return ShellHistoryContext(
        recent_commands=commands[-10:],
        error_patterns=error_patterns,
        session_intent=session_intent,
    )


def _detect_session_intent(commands: list[str]) -> str:
    """Detect session intent from command patterns."""
    if not commands:
        return "unknown"

    test_cmds = sum(
        1
        for c in commands
        if re.search(
            r"pytest|jest|cargo test|go test|npm test", c
        )
    )
    if test_cmds >= 3:
        return "debugging"

    for cmd in commands[-5:]:
        if re.search(r"git checkout -b|git switch -c", cmd):
            return "feature"
        if re.search(
            r"pip install|npm install|yarn add|pnpm add",
            cmd,
        ):
            return "integration"
        if re.search(
            r"docker build|docker-compose|docker compose",
            cmd,
        ):
            return "devops"
        if re.search(r"curl |httpie |http ", cmd):
            return "api"

    return "unknown"


def _detect_error_patterns(
    commands: list[str],
) -> list[str]:
    """Extract error-related patterns from commands."""
    patterns: list[str] = []
    for cmd in commands:
        if re.search(
            r"FAIL|ERROR|error|failed|traceback",
            cmd,
            re.IGNORECASE,
        ):
            patterns.append(cmd[:80])
    return patterns[:5]


def collect_tech_stack() -> TechStackContext:
    """Detect tech stack from marker files."""
    root = _get_project_root()

    languages: list[str] = []
    frameworks: list[str] = []
    package_manager: str | None = None

    markers: dict[str, str] = {
        "pyproject.toml": "python",
        "setup.py": "python",
        "requirements.txt": "python",
        "package.json": "javascript",
        "Cargo.toml": "rust",
        "go.mod": "go",
        "pom.xml": "java",
        "build.gradle": "java",
        "Gemfile": "ruby",
    }

    for marker, lang in markers.items():
        if (
            (root / marker).exists()
            and lang not in languages
        ):
            languages.append(lang)

    # TypeScript detection
    if (root / "tsconfig.json").exists():
        if "javascript" in languages:
            languages.remove("javascript")
        if "typescript" not in languages:
            languages.append("typescript")

    # Framework detection from package.json
    if (root / "package.json").exists():
        try:
            pkg = json.loads(
                (root / "package.json").read_text()
            )
            # A present-but-null or non-object dependencies field (valid JSON,
            # e.g. "dependencies": null) must not abort the whole collector and
            # lose the already-detected languages — skip framework detection for
            # it instead. ``.get(k, {})`` is unsafe here: a present null key
            # returns None, not the default.
            raw_deps = pkg.get("dependencies") if isinstance(pkg, dict) else None
            raw_dev = (
                pkg.get("devDependencies") if isinstance(pkg, dict) else None
            )
            all_deps = {
                **(raw_deps if isinstance(raw_deps, dict) else {}),
                **(raw_dev if isinstance(raw_dev, dict) else {}),
            }
            framework_map = {
                "react": "react",
                "next": "nextjs",
                "vue": "vue",
                "svelte": "svelte",
                "angular": "angular",
                "express": "express",
                "fastify": "fastify",
            }
            for dep, fw in framework_map.items():
                if dep in all_deps and fw not in frameworks:
                    frameworks.append(fw)
        except (json.JSONDecodeError, OSError):
            pass

    # Python framework detection from pyproject.toml
    if (root / "pyproject.toml").exists():
        try:
            content = (
                (root / "pyproject.toml").read_text()
            )
            py_frameworks = {
                "flask": "flask",
                "django": "django",
                "fastapi": "fastapi",
                "click": "click",
                "typer": "typer",
            }
            for pkg_name, fw in py_frameworks.items():
                if (
                    pkg_name in content.lower()
                    and fw not in frameworks
                ):
                    frameworks.append(fw)
        except OSError:
            pass

    # Package manager detection
    pm_markers = {
        "pnpm-lock.yaml": "pnpm",
        "yarn.lock": "yarn",
        "package-lock.json": "npm",
        "Pipfile.lock": "pipenv",
        "poetry.lock": "poetry",
        "uv.lock": "uv",
    }
    for marker, pm in pm_markers.items():
        if (root / marker).exists():
            package_manager = pm
            break

    return TechStackContext(
        languages=languages,
        frameworks=frameworks,
        package_manager=package_manager,
    )


def collect_environment() -> EnvironmentContext:
    """Detect runtime environment characteristics."""
    return EnvironmentContext(
        in_venv=bool(
            os.environ.get("VIRTUAL_ENV")
            or os.environ.get("CONDA_DEFAULT_ENV")
        ),
        in_container=(
            Path("/.dockerenv").exists()
            or Path("/run/.containerenv").exists()
        ),
        in_ci=bool(os.environ.get("CI")),
        in_ssh=bool(
            os.environ.get("SSH_CONNECTION")
            or os.environ.get("SSH_CLIENT")
        ),
    )
