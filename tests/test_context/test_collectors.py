"""Task 6: Context Fingerprinting — collector tests."""

from __future__ import annotations

from pathlib import Path

from pytest_mock import MockerFixture

from promptune.context import ContextFingerprint, collect_context
from promptune.context.collectors import (
    EnvironmentContext,
    GitContext,
    ShellHistoryContext,
    TechStackContext,
    collect_environment,
    collect_git,
    collect_shell_history,
    collect_tech_stack,
)

# --- GitCollector ---


def test_git_branch(mocker: MockerFixture) -> None:
    """Extracts current git branch name."""
    mocker.patch(
        "promptune.context.collectors._run_git",
        side_effect=lambda args, **kw: {
            ("branch", "--show-current"): "fix/auth-redirect",
            ("log", "--format=%h|%ar|%s", "-5"): (
                "abc1234|2h ago|fix auth\n"
                "def5678|5h ago|add login"
            ),
            ("status", "--porcelain", "-uno"): "M src/auth.py",
            ("diff", "--shortstat"): (
                " 1 file changed, 5 insertions(+),"
                " 2 deletions(-)"
            ),
            ("stash", "list"): "",
        }.get(args, ""),
    )

    result = collect_git()

    assert isinstance(result, GitContext)
    assert result.branch == "fix/auth-redirect"


def test_git_recent_commits(mocker: MockerFixture) -> None:
    """Parses recent commit messages."""
    mocker.patch(
        "promptune.context.collectors._run_git",
        side_effect=lambda args, **kw: {
            ("branch", "--show-current"): "main",
            ("log", "--format=%h|%ar|%s", "-5"): (
                "abc1234|2h ago|fix auth\n"
                "def5678|5h ago|add login"
            ),
            ("status", "--porcelain", "-uno"): "",
            ("diff", "--shortstat"): "",
            ("stash", "list"): "",
        }.get(args, ""),
    )

    result = collect_git()

    assert len(result.recent_commits) == 2
    assert "fix auth" in result.recent_commits[0]


def test_git_modified_files(mocker: MockerFixture) -> None:
    """Lists modified files from git status."""
    mocker.patch(
        "promptune.context.collectors._run_git",
        side_effect=lambda args, **kw: {
            ("branch", "--show-current"): "main",
            ("log", "--format=%h|%ar|%s", "-5"): "",
            ("status", "--porcelain", "-uno"): (
                "M src/auth.py\nA src/new.py"
            ),
            ("diff", "--shortstat"): "",
            ("stash", "list"): "",
        }.get(args, ""),
    )

    result = collect_git()

    assert "src/auth.py" in result.modified_files
    assert "src/new.py" in result.modified_files


def test_git_not_a_repo(mocker: MockerFixture) -> None:
    """Returns empty GitContext when not in a git repo."""
    mocker.patch(
        "promptune.context.collectors._run_git",
        side_effect=FileNotFoundError("git not found"),
    )

    result = collect_git()

    assert result.branch == ""
    assert result.recent_commits == []


# --- ShellHistoryCollector ---


def test_shell_history_recent_commands(
    mocker: MockerFixture, tmp_path
) -> None:
    """Reads recent commands from zsh history file."""
    hist_file = tmp_path / ".zsh_history"
    hist_file.write_text(
        ": 1710000000:0;pytest tests/\n"
        ": 1710000001:0;git status\n"
        ": 1710000002:0;npm run build\n"
    )
    mocker.patch(
        "promptune.context.collectors._find_history_file",
        return_value=hist_file,
    )

    result = collect_shell_history()

    assert isinstance(result, ShellHistoryContext)
    assert len(result.recent_commands) == 3


def test_shell_history_does_not_load_entire_large_file(
    mocker: MockerFixture, tmp_path
) -> None:
    """A huge history file is tail-read, not slurped whole into RAM."""
    hist_file = tmp_path / ".zsh_history"
    hist_file.write_text(
        "\n".join(f"echo cmd_{i}" for i in range(10000)) + "\n"
    )
    mocker.patch(
        "promptune.context.collectors._find_history_file",
        return_value=hist_file,
    )
    read_text_spy = mocker.spy(Path, "read_text")

    result = collect_shell_history(max_lines=5)

    assert len(result.recent_commands) <= 5
    # Must not slurp the whole file via read_text (bounded tail read instead).
    assert read_text_spy.call_count == 0


def test_get_project_root_uses_short_git_timeout(
    mocker: MockerFixture,
) -> None:
    """Project-root lookup uses the short (0.3s) git timeout, not 2.0s."""
    from promptune.context.collectors import _get_project_root

    spy = mocker.patch(
        "promptune.context.collectors._safe_git", return_value=""
    )
    root = _get_project_root()

    spy.assert_called_once()
    _, kwargs = spy.call_args
    assert kwargs.get("timeout", 2.0) <= 0.3
    assert isinstance(root, Path)


def test_safe_git_degrades_on_unicode_decode_error(
    mocker: MockerFixture,
) -> None:
    """Git output decode failures degrade like other git failures."""
    from promptune.context.collectors import _safe_git

    mocker.patch(
        "promptune.context.collectors._run_git",
        side_effect=UnicodeDecodeError("utf-8", b"\xff", 0, 1, "bad byte"),
    )

    assert _safe_git(("status", "--short")) == ""


def test_shell_history_error_patterns(
    mocker: MockerFixture, tmp_path
) -> None:
    """Detects repeated test failures as debugging intent."""
    hist_file = tmp_path / ".zsh_history"
    hist_file.write_text(
        ": 1710000000:0;pytest tests/ -x\n"
        ": 1710000001:0;pytest tests/ -x\n"
        ": 1710000002:0;pytest tests/ -x\n"
    )
    mocker.patch(
        "promptune.context.collectors._find_history_file",
        return_value=hist_file,
    )

    result = collect_shell_history()

    assert result.session_intent == "debugging"


def test_shell_history_no_file(mocker: MockerFixture) -> None:
    """Returns empty context when no history file found."""
    mocker.patch(
        "promptune.context.collectors._find_history_file",
        return_value=None,
    )

    result = collect_shell_history()

    assert result.recent_commands == []
    assert result.session_intent == "unknown"


# --- TechStackCollector ---


def test_tech_stack_python(
    tmp_path, mocker: MockerFixture
) -> None:
    """Detects Python project from pyproject.toml."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "foo"\n'
    )
    mocker.patch(
        "promptune.context.collectors._get_project_root",
        return_value=tmp_path,
    )

    result = collect_tech_stack()

    assert isinstance(result, TechStackContext)
    assert "python" in result.languages


def test_tech_stack_node(
    tmp_path, mocker: MockerFixture
) -> None:
    """Detects Node.js project from package.json."""
    (tmp_path / "package.json").write_text(
        '{"name": "foo", "dependencies": {"react": "^18"}}'
    )
    mocker.patch(
        "promptune.context.collectors._get_project_root",
        return_value=tmp_path,
    )

    result = collect_tech_stack()

    assert (
        "javascript" in result.languages
        or "typescript" in result.languages
    )
    assert "react" in result.frameworks


def test_tech_stack_non_utf8_manifest_keeps_languages(
    tmp_path, mocker: MockerFixture
) -> None:
    """A non-UTF-8 manifest must not discard already-detected languages.

    read_text() raises UnicodeDecodeError (a ValueError, not OSError/
    JSONDecodeError) on invalid bytes; framework detection must swallow it so
    the package.json language marker survives — mirroring the null-dependencies
    guard.
    """
    (tmp_path / "package.json").write_bytes(b"\xff\xff\xff not utf-8")
    mocker.patch(
        "promptune.context.collectors._get_project_root",
        return_value=tmp_path,
    )

    result = collect_tech_stack()

    assert "javascript" in result.languages


def test_tech_stack_no_markers(
    tmp_path, mocker: MockerFixture
) -> None:
    """Returns empty when no marker files found."""
    mocker.patch(
        "promptune.context.collectors._get_project_root",
        return_value=tmp_path,
    )

    result = collect_tech_stack()

    assert result.languages == []
    assert result.frameworks == []


# --- EnvironmentCollector ---


def test_environment_venv(mocker: MockerFixture) -> None:
    """Detects active virtual environment."""
    mocker.patch.dict(
        "os.environ", {"VIRTUAL_ENV": "/home/user/.venv"}
    )

    result = collect_environment()

    assert isinstance(result, EnvironmentContext)
    assert result.in_venv is True


def test_environment_ci(mocker: MockerFixture) -> None:
    """Detects CI environment from CI env var."""
    mocker.patch.dict(
        "os.environ", {"CI": "true"}, clear=False
    )

    result = collect_environment()

    assert result.in_ci is True


# --- Parallel collection ---


def test_collect_context_parallel(
    mocker: MockerFixture,
) -> None:
    """collect_context runs all collectors."""
    mocker.patch(
        "promptune.context.collect_git",
        return_value=GitContext(
            branch="main",
            recent_commits=[],
            modified_files=[],
            diff_stats="",
            stash_count=0,
        ),
    )
    mocker.patch(
        "promptune.context.collect_shell_history",
        return_value=ShellHistoryContext(
            recent_commands=[],
            error_patterns=[],
            session_intent="unknown",
        ),
    )
    mocker.patch(
        "promptune.context.collect_tech_stack",
        return_value=TechStackContext(
            languages=[],
            frameworks=[],
            package_manager=None,
        ),
    )
    mocker.patch(
        "promptune.context.collect_environment",
        return_value=EnvironmentContext(
            in_venv=False,
            in_container=False,
            in_ci=False,
            in_ssh=False,
        ),
    )

    result = collect_context(timeout_ms=400)

    assert isinstance(result, ContextFingerprint)
    assert result.git.branch == "main"


def test_collect_context_skips_disabled_collectors(
    mocker: MockerFixture,
) -> None:
    """Disabled collectors are not submitted."""
    git = mocker.patch(
        "promptune.context.collect_git",
        side_effect=AssertionError("git collector should not run"),
    )
    shell = mocker.patch(
        "promptune.context.collect_shell_history",
        side_effect=AssertionError("shell collector should not run"),
    )
    tech = mocker.patch(
        "promptune.context.collect_tech_stack",
        side_effect=AssertionError("tech collector should not run"),
    )
    env = mocker.patch(
        "promptune.context.collect_environment",
        return_value=EnvironmentContext(
            in_venv=True,
            in_container=False,
            in_ci=False,
            in_ssh=False,
        ),
    )

    result = collect_context(
        timeout_ms=400,
        include_git=False,
        include_shell=False,
        include_tech=False,
    )

    git.assert_not_called()
    shell.assert_not_called()
    tech.assert_not_called()
    env.assert_called_once()
    assert result.git.branch == ""
    assert result.shell.recent_commands == []
    assert result.tech.languages == []
    assert result.env.in_venv is True


def test_collect_context_timeout(
    mocker: MockerFixture,
) -> None:
    """Timed-out collectors return defaults."""
    import time

    def slow_git():
        time.sleep(2)
        return GitContext(
            branch="slow",
            recent_commits=[],
            modified_files=[],
            diff_stats="",
            stash_count=0,
        )

    mocker.patch(
        "promptune.context.collect_git",
        side_effect=slow_git,
    )
    mocker.patch(
        "promptune.context.collect_shell_history",
        return_value=ShellHistoryContext(
            recent_commands=[],
            error_patterns=[],
            session_intent="unknown",
        ),
    )
    mocker.patch(
        "promptune.context.collect_tech_stack",
        return_value=TechStackContext(
            languages=[],
            frameworks=[],
            package_manager=None,
        ),
    )
    mocker.patch(
        "promptune.context.collect_environment",
        return_value=EnvironmentContext(
            in_venv=False,
            in_container=False,
            in_ci=False,
            in_ssh=False,
        ),
    )

    result = collect_context(timeout_ms=100)

    # Git timed out — should get default empty GitContext
    assert result.git.branch == ""


def test_collect_context_does_not_block_on_slow_collector(
    mocker: MockerFixture,
) -> None:
    """A hung collector must not block the call past the timeout budget."""
    import time

    def slow_git():
        time.sleep(2)
        return GitContext(
            branch="slow",
            recent_commits=[],
            modified_files=[],
            diff_stats="",
            stash_count=0,
        )

    mocker.patch("promptune.context.collect_git", side_effect=slow_git)
    mocker.patch(
        "promptune.context.collect_shell_history",
        return_value=ShellHistoryContext(
            recent_commands=[], error_patterns=[], session_intent="unknown"
        ),
    )
    mocker.patch(
        "promptune.context.collect_tech_stack",
        return_value=TechStackContext(
            languages=[], frameworks=[], package_manager=None
        ),
    )
    mocker.patch(
        "promptune.context.collect_environment",
        return_value=EnvironmentContext(
            in_venv=False, in_container=False, in_ci=False, in_ssh=False
        ),
    )

    start = time.monotonic()
    result = collect_context(timeout_ms=100)
    elapsed = time.monotonic() - start

    assert result.git.branch == ""
    assert elapsed < 1.0  # must not wait for the 2s collector to finish


# --- _find_history_file: no candidates exist ---


def test_find_history_file_none(
    mocker: MockerFixture, tmp_path
) -> None:
    """Returns None when no history file exists."""
    mocker.patch(
        "promptune.context.collectors.Path.home",
        return_value=tmp_path,
    )
    from promptune.context.collectors import (
        _find_history_file,
    )

    assert _find_history_file() is None


# --- _get_project_root: git fails ---


def test_get_project_root_no_git(
    mocker: MockerFixture,
) -> None:
    """Falls back to cwd when git is missing."""

    mocker.patch(
        "promptune.context.collectors._run_git",
        side_effect=FileNotFoundError("no git"),
    )
    from promptune.context.collectors import (
        _get_project_root,
    )

    result = _get_project_root()
    from pathlib import Path

    assert result == Path.cwd()


def test_get_project_root_subprocess_error(
    mocker: MockerFixture,
) -> None:
    """Falls back to cwd on SubprocessError."""
    import subprocess

    mocker.patch(
        "promptune.context.collectors._run_git",
        side_effect=subprocess.SubprocessError("fail"),
    )
    from promptune.context.collectors import (
        _get_project_root,
    )

    result = _get_project_root()
    from pathlib import Path

    assert result == Path.cwd()


# --- collect_shell_history: unreadable file ---


def test_shell_history_unreadable(
    mocker: MockerFixture, tmp_path
) -> None:
    """Returns empty context on PermissionError."""
    hist_file = tmp_path / ".zsh_history"
    hist_file.write_text("data")
    mocker.patch(
        "promptune.context.collectors._find_history_file",
        return_value=hist_file,
    )
    mocker.patch(
        "builtins.open",
        side_effect=PermissionError("denied"),
    )

    result = collect_shell_history()

    assert result.recent_commands == []
    assert result.session_intent == "unknown"


# --- _detect_session_intent: edge cases ---


def test_session_intent_empty() -> None:
    """Empty commands yields unknown intent."""
    from promptune.context.collectors import (
        _detect_session_intent,
    )

    assert _detect_session_intent([]) == "unknown"


def test_session_intent_feature() -> None:
    """Detects feature intent from git checkout -b."""
    from promptune.context.collectors import (
        _detect_session_intent,
    )

    cmds = ["ls", "git checkout -b feat/new"]
    assert _detect_session_intent(cmds) == "feature"


def test_session_intent_integration() -> None:
    """Detects integration intent from pip install."""
    from promptune.context.collectors import (
        _detect_session_intent,
    )

    cmds = ["pip install requests"]
    assert _detect_session_intent(cmds) == "integration"


def test_session_intent_devops() -> None:
    """Detects devops intent from docker build."""
    from promptune.context.collectors import (
        _detect_session_intent,
    )

    cmds = ["docker build ."]
    assert _detect_session_intent(cmds) == "devops"


def test_session_intent_api() -> None:
    """Detects api intent from curl command."""
    from promptune.context.collectors import (
        _detect_session_intent,
    )

    cmds = ["curl http://localhost:8000/api"]
    assert _detect_session_intent(cmds) == "api"


# --- _detect_error_patterns: truncation ---


def test_error_pattern_truncation() -> None:
    """Error patterns are truncated to 80 chars."""
    from promptune.context.collectors import (
        _detect_error_patterns,
    )

    long_cmd = "ERROR " + "x" * 200
    result = _detect_error_patterns([long_cmd])
    assert len(result) == 1
    assert len(result[0]) == 80


# --- TypeScript detection ---


def test_tech_stack_typescript(
    tmp_path, mocker: MockerFixture
) -> None:
    """tsconfig.json replaces javascript with typescript."""
    (tmp_path / "package.json").write_text(
        '{"name": "app"}'
    )
    (tmp_path / "tsconfig.json").write_text("{}")
    mocker.patch(
        "promptune.context.collectors._get_project_root",
        return_value=tmp_path,
    )

    result = collect_tech_stack()

    assert "typescript" in result.languages
    assert "javascript" not in result.languages


# --- Malformed package.json ---


def test_tech_stack_malformed_package_json(
    tmp_path, mocker: MockerFixture
) -> None:
    """Handles malformed package.json gracefully."""
    (tmp_path / "package.json").write_text("{not json!!")
    mocker.patch(
        "promptune.context.collectors._get_project_root",
        return_value=tmp_path,
    )

    result = collect_tech_stack()

    assert "javascript" in result.languages
    assert result.frameworks == []


def test_tech_stack_null_dependencies_preserves_languages(
    tmp_path, mocker: MockerFixture
) -> None:
    """Valid package.json with null dependencies must not abort the collector.

    Regression: ``{**pkg.get("dependencies", {})}`` raised TypeError when the
    key is present but null (``.get`` returns None, not the default). The
    exception propagated out of collect_tech_stack and lost the already
    detected languages instead of just skipping framework detection.
    """
    (tmp_path / "package.json").write_text(
        '{"name": "app", "dependencies": null, "devDependencies": null}'
    )
    mocker.patch(
        "promptune.context.collectors._get_project_root",
        return_value=tmp_path,
    )

    result = collect_tech_stack()

    assert "javascript" in result.languages
    assert result.frameworks == []


def test_tech_stack_non_dict_dependencies_preserves_languages(
    tmp_path, mocker: MockerFixture
) -> None:
    """A non-object dependencies value is ignored, languages still detected."""
    (tmp_path / "package.json").write_text(
        '{"name": "app", "dependencies": ["react"]}'
    )
    mocker.patch(
        "promptune.context.collectors._get_project_root",
        return_value=tmp_path,
    )

    result = collect_tech_stack()

    assert "javascript" in result.languages
    assert result.frameworks == []


# --- pyproject.toml OSError ---


def test_tech_stack_pyproject_os_error(
    tmp_path, mocker: MockerFixture
) -> None:
    """Handles unreadable pyproject.toml gracefully."""
    pf = tmp_path / "pyproject.toml"
    pf.write_text('[project]\nname = "x"\n')
    mocker.patch(
        "promptune.context.collectors._get_project_root",
        return_value=tmp_path,
    )
    # Make read_text raise after exists() succeeds
    original_read = Path.read_text

    def patched_read(self, *a, **kw):
        if self.name == "pyproject.toml":
            raise OSError("disk error")
        return original_read(self, *a, **kw)

    mocker.patch.object(
        Path, "read_text", patched_read
    )

    result = collect_tech_stack()

    assert "python" in result.languages
    # Frameworks empty due to OSError
    assert result.frameworks == []


# --- Package manager detection ---


def test_tech_stack_package_manager(
    tmp_path, mocker: MockerFixture
) -> None:
    """Detects package manager from lock files."""
    (tmp_path / "poetry.lock").write_text("")
    mocker.patch(
        "promptune.context.collectors._get_project_root",
        return_value=tmp_path,
    )

    result = collect_tech_stack()

    assert result.package_manager == "poetry"


def test_tech_stack_package_manager_pnpm(
    tmp_path, mocker: MockerFixture
) -> None:
    """Detects pnpm from pnpm-lock.yaml."""
    (tmp_path / "pnpm-lock.yaml").write_text("")
    mocker.patch(
        "promptune.context.collectors._get_project_root",
        return_value=tmp_path,
    )

    result = collect_tech_stack()

    assert result.package_manager == "pnpm"
