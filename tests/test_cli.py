"""CLI tests."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

import promptune
from promptune.cli import main
from promptune.providers import ProviderError
from promptune.scorer import DimensionScore, ScoreResult


def test_version_exists():
    """promptune.__version__ is a non-empty string."""
    assert hasattr(promptune, "__version__")
    assert isinstance(promptune.__version__, str)
    assert len(promptune.__version__) > 0


def test_version_flag_outputs_version():
    """`promptune --version` prints the version and exits 0."""
    result = CliRunner().invoke(main, ["--version"])
    assert result.exit_code == 0
    assert promptune.__version__ in result.output


def test_version_format():
    """Version matches semver pattern."""
    pattern = r"^\d+\.\d+\.\d+$"
    assert re.match(
        pattern, promptune.__version__
    ), (
        f"Version '{promptune.__version__}' "
        "does not match semver"
    )


def test_cli_version_command():
    """'promptune version' outputs the version."""
    runner = CliRunner()
    result = runner.invoke(main, ["version"])
    assert result.exit_code == 0
    assert promptune.__version__ in result.output


def test_cli_help():
    """'promptune --help' exits 0."""
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "Usage" in result.output


def test_version_sync():
    """Version in pyproject.toml matches __init__.py."""
    from pathlib import Path

    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import tomli as tomllib

    pyproject_path = (
        Path(__file__).parent.parent / "pyproject.toml"
    )
    with open(pyproject_path, "rb") as f:
        pyproject = tomllib.load(f)

    pyproject_version = pyproject["project"]["version"]
    assert pyproject_version == promptune.__version__


def test_module_runnable():
    """'python -m promptune' doesn't crash."""
    result = subprocess.run(
        [sys.executable, "-m", "promptune", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0


# --- Enhancement flags ---


def test_enhance_tier_flag(mocker) -> None:
    """--tier flag is accepted and passed through."""
    mock_enhance = mocker.patch(
        "promptune.cli.enhance"
    )
    mock_enhance.return_value = MagicMock(
        original="test",
        enhanced="enhanced test",
        tier_used=0,
        latency_ms=5,
        score_before=MagicMock(total=10),
        score_after=MagicMock(total=80),
        rules_applied=[],
        context=None,
        format_style="xml",
        provider=None,
        model=None,
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "enhance",
            "--tier",
            "0",
            "--no-tui",
            "test prompt",
        ],
    )
    assert result.exit_code == 0


def test_enhance_json_flag(mocker) -> None:
    """--json flag outputs structured JSON."""
    mock_enhance = mocker.patch(
        "promptune.cli.enhance"
    )
    mock_result = MagicMock()
    mock_result.original = "test"
    mock_result.enhanced = "enhanced test"
    mock_result.tier_used = 0
    mock_result.latency_ms = 5.0
    mock_result.score_before = MagicMock(total=10)
    mock_result.score_after = MagicMock(total=80)
    mock_result.format_style = "xml"
    mock_result.rules_applied = ["output_format"]
    mock_enhance.return_value = mock_result

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "enhance",
            "--json",
            "--no-tui",
            "test prompt",
        ],
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["original"] == "test"
    assert data["enhanced"] == "enhanced test"
    assert data["tier_used"] == 0


# --- Score command ---


def _make_score_result(total: int) -> ScoreResult:
    return ScoreResult(
        total=total,
        intent="coding",
        dimensions={
            "specificity": DimensionScore(0.3, 25.0, [], "Add more"),
            "clarity": DimensionScore(0.5, 20.0, [], "Good clarity"),
            "structure": DimensionScore(0.2, 15.0, [], "Add structure"),
            "actionability": DimensionScore(0.4, 15.0, [], "Good"),
            "context": DimensionScore(0.1, 10.0, [], "Add context"),
            "completeness": DimensionScore(0.1, 10.0, [], "Add format"),
            "conciseness": DimensionScore(0.7, 5.0, [], "Good"),
        },
    )


class TestScoreCommand:
    """promptune score command."""

    def test_score_prints_total(self, mocker) -> None:
        mocker.patch(
            "promptune.cli.score_prompt",
            return_value=_make_score_result(42),
        )
        runner = CliRunner()
        result = runner.invoke(
            main, ["score", "make a todo app"]
        )
        assert result.exit_code == 0
        assert "42" in result.output

    def test_score_json_output(self, mocker) -> None:
        mocker.patch(
            "promptune.cli.score_prompt",
            return_value=_make_score_result(42),
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["score", "--json", "make a todo app"],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["total"] == 42
        assert data["intent"] == "coding"
        assert "dimensions" in data

    def test_score_empty_prompt_exits_1(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["score"])
        assert result.exit_code == 1


# --- Config set commands ---


def test_config_set_key(mocker, tmp_path) -> None:
    """config --set-key writes API key."""
    config_file = tmp_path / "config.toml"
    mocker.patch(
        "promptune.cli._get_config_path",
        return_value=config_file,
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "config",
            "--set-key",
            "claude",
            "sk-ant-test123",
        ],
    )
    assert result.exit_code == 0


def test_set_key_writes_owner_only_permissions(mocker, tmp_path) -> None:
    """config --set-key writes a 0o600 file (contains a plaintext key)."""
    config_file = tmp_path / "config.toml"
    mocker.patch(
        "promptune.cli._get_config_path", return_value=config_file
    )
    runner = CliRunner()
    result = runner.invoke(
        main, ["config", "--set-key", "claude", "sk-ant-secret"]
    )
    assert result.exit_code == 0
    assert oct(config_file.stat().st_mode & 0o777) == "0o600"


def test_reset_writes_owner_only_permissions(mocker, tmp_path) -> None:
    """config --reset writes a 0o600 file."""
    config_file = tmp_path / "config.toml"
    mocker.patch(
        "promptune.cli._get_config_path", return_value=config_file
    )
    runner = CliRunner()
    result = runner.invoke(main, ["config", "--reset"], input="y\n")
    assert result.exit_code == 0
    assert oct(config_file.stat().st_mode & 0o777) == "0o600"


def test_set_key_persists_into_partial_config_missing_section(
    mocker, tmp_path
) -> None:
    """Setting a key whose [section] is absent must create it and persist."""
    config_file = tmp_path / "config.toml"
    config_file.write_text('[provider]\ndefault = "claude"\n')
    mocker.patch(
        "promptune.cli._get_config_path", return_value=config_file
    )
    runner = CliRunner()
    result = runner.invoke(
        main, ["config", "--set-key", "claude", "sk-ant-PERSISTME"]
    )
    assert result.exit_code == 0
    content = config_file.read_text()
    assert "sk-ant-PERSISTME" in content
    assert "[api_keys]" in content


def test_config_set_key_rejects_unknown_provider(mocker, tmp_path) -> None:
    """config --set-key validates the provider name."""
    config_file = tmp_path / "config.toml"
    mocker.patch(
        "promptune.cli._get_config_path",
        return_value=config_file,
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["config", "--set-key", "clade", "sk-ant-test123"],
    )
    assert result.exit_code != 0
    assert "Unknown provider" in result.output
    assert not config_file.exists()


def test_config_flags_mutually_exclusive(mocker, tmp_path) -> None:
    """Passing two of --set-key/--set-tier/--reset is rejected."""
    config_file = tmp_path / "config.toml"
    mocker.patch(
        "promptune.cli._get_config_path",
        return_value=config_file,
    )
    runner = CliRunner()
    result = runner.invoke(
        main, ["config", "--reset", "--set-tier", "1"]
    )
    assert result.exit_code != 0
    assert "mutually exclusive" in result.output


def test_config_set_tier(mocker, tmp_path) -> None:
    """config --set-tier updates max_tier."""
    config_file = tmp_path / "config.toml"
    mocker.patch(
        "promptune.cli._get_config_path",
        return_value=config_file,
    )

    runner = CliRunner()
    result = runner.invoke(
        main, ["config", "--set-tier", "1"]
    )
    assert result.exit_code == 0


def test_config_reset(mocker, tmp_path) -> None:
    """config --reset restores defaults."""
    config_file = tmp_path / "config.toml"
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(
        "[provider]\ndefault = 'openai'\n"
    )
    mocker.patch(
        "promptune.cli._get_config_path",
        return_value=config_file,
    )

    runner = CliRunner()
    result = runner.invoke(
        main, ["config", "--reset"], input="y\n"
    )
    assert result.exit_code == 0


# --- Doctor ---


def test_doctor_command_runs(mocker) -> None:
    """'promptune doctor' exits 0."""
    mocker.patch(
        "promptune.cli._check_python",
        return_value=(True, "3.12.1"),
    )
    mocker.patch(
        "promptune.cli._check_config",
        return_value=(True, "found"),
    )
    mocker.patch(
        "promptune.cli._check_tier0",
        return_value=(True, "ready"),
    )
    mocker.patch(
        "promptune.cli._check_tier1",
        return_value=(False, "not configured"),
    )
    mocker.patch(
        "promptune.cli._check_tier2",
        return_value=(False, "no API key"),
    )

    runner = CliRunner()
    result = runner.invoke(main, ["doctor"])
    assert result.exit_code == 0
    assert "Python" in result.output


# --- Doctor auto-enhance ---


class TestDoctorAutoEnhance:
    """Doctor shows auto-enhance status per tool."""

    def test_doctor_shows_auto_enhance_installed(
        self, mocker
    ) -> None:
        mock_installer = MagicMock()
        mock_installer.name = "Claude Code"
        mock_installer.detect.return_value = True
        mock_installer.is_installed.return_value = True
        mocker.patch(
            "promptune.cli.get_installers",
            return_value=[mock_installer],
        )
        runner = CliRunner()
        result = runner.invoke(main, ["doctor"])
        assert "Claude Code" in result.output
        assert "\u2713" in result.output

    def test_doctor_survives_installer_is_installed_error(
        self, mocker
    ) -> None:
        """A malformed settings file must not crash 'doctor'."""
        mock_installer = MagicMock()
        mock_installer.name = "Claude Code"
        mock_installer.detect.return_value = True
        mock_installer.is_installed.side_effect = AttributeError(
            "'str' object has no attribute 'get'"
        )
        mocker.patch(
            "promptune.cli.get_installers",
            return_value=[mock_installer],
        )
        runner = CliRunner()
        result = runner.invoke(main, ["doctor"])
        assert result.exit_code == 0

    def test_doctor_shows_auto_enhance_not_installed(
        self, mocker
    ) -> None:
        mock_installer = MagicMock()
        mock_installer.name = "Claude Code"
        mock_installer.detect.return_value = True
        mock_installer.is_installed.return_value = False
        mocker.patch(
            "promptune.cli.get_installers",
            return_value=[mock_installer],
        )
        runner = CliRunner()
        result = runner.invoke(main, ["doctor"])
        assert "Claude Code" in result.output
        assert "\u2717" in result.output

    def test_doctor_skips_undetected_tools(
        self, mocker
    ) -> None:
        mock_installer = MagicMock()
        mock_installer.name = "Codex"
        mock_installer.detect.return_value = False
        mock_installer.is_installed.return_value = False
        mocker.patch(
            "promptune.cli.get_installers",
            return_value=[mock_installer],
        )
        runner = CliRunner()
        result = runner.invoke(main, ["doctor"])
        assert "Codex" in result.output


# --- Gate command ---


class TestGateCommand:
    """promptune gate reads stdin JSON and calls run_gate."""

    def test_gate_passes_clean_prompt(self, mocker) -> None:
        mocker.patch(
            "promptune.cli.run_gate", return_value=0
        )
        runner = CliRunner()
        stdin_data = json.dumps(
            {"prompt": "implement a REST API"}
        )
        result = runner.invoke(
            main, ["gate"], input=stdin_data
        )
        assert result.exit_code == 0

    def test_gate_blocks_low_quality_prompt(
        self, mocker
    ) -> None:
        mocker.patch(
            "promptune.cli.run_gate", return_value=1
        )
        runner = CliRunner()
        stdin_data = json.dumps(
            {"prompt": "make a todo app"}
        )
        result = runner.invoke(
            main, ["gate"], input=stdin_data
        )
        assert result.exit_code == 1

    def test_gate_passes_on_invalid_json(
        self, mocker
    ) -> None:
        mocker.patch("promptune.cli.run_gate")
        runner = CliRunner()
        result = runner.invoke(
            main, ["gate"], input="not valid json"
        )
        assert result.exit_code == 0

    def test_gate_passes_on_missing_prompt_key(
        self, mocker
    ) -> None:
        mocker.patch("promptune.cli.run_gate")
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["gate"],
            input=json.dumps({"session_id": "abc"}),
        )
        assert result.exit_code == 0

    def test_gate_passes_on_non_dict_json(self, mocker) -> None:
        mocker.patch("promptune.cli.run_gate")
        runner = CliRunner()
        for payload in ('"hello"', "[1, 2]", "42"):
            result = runner.invoke(main, ["gate"], input=payload)
            assert result.exit_code == 0, payload
            assert result.exception is None or isinstance(
                result.exception, SystemExit
            )


# --- Local LLM status ---


def test_local_llm_status_command(mocker) -> None:
    """'promptune local-llm-status' exits 0."""
    mocker.patch(
        "promptune.cli._check_local_llm_connectivity",
        return_value=(True, "qwen2.5:3b responding"),
    )

    runner = CliRunner()
    result = runner.invoke(main, ["local-llm-status"])
    assert result.exit_code == 0


# --- History ---


def test_history_command_runs(mocker) -> None:
    """'promptune history' exits 0."""
    mock_store = MagicMock()
    mock_store.recent.return_value = []
    mocker.patch(
        "promptune.cli._get_history_store",
        return_value=mock_store,
    )

    runner = CliRunner()
    result = runner.invoke(main, ["history"])
    assert result.exit_code == 0


def test_history_stats_flag(mocker) -> None:
    """'promptune history --stats' shows statistics."""
    mock_store = MagicMock()
    mock_store.stats.return_value = MagicMock(
        total=100,
        accepted=70,
        rejected=20,
        edited=10,
        acceptance_rate=0.7,
        avg_score_before=30,
        avg_score_after=75,
        avg_improvement=45,
        tier_distribution={0: 60, 1: 25, 2: 15},
    )
    mocker.patch(
        "promptune.cli._get_history_store",
        return_value=mock_store,
    )

    runner = CliRunner()
    result = runner.invoke(main, ["history", "--stats"])
    assert result.exit_code == 0


def test_history_clear_with_confirm(mocker) -> None:
    """'promptune history --clear' requires confirm."""
    mock_store = MagicMock()
    mock_store.clear.return_value = 50
    mocker.patch(
        "promptune.cli._get_history_store",
        return_value=mock_store,
    )

    runner = CliRunner()
    result = runner.invoke(
        main, ["history", "--clear"], input="y\n"
    )
    assert result.exit_code == 0


def test_doctor_warns_warp_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    """Doctor warns when Warp Terminal is detected."""
    monkeypatch.setenv("TERM_PROGRAM", "WarpTerminal")
    monkeypatch.setattr("promptune.cli._check_tier1", lambda: (True, "Mocked"))
    monkeypatch.setattr("promptune.cli._check_tier2", lambda: (True, "Mocked"))
    runner = CliRunner()
    result = runner.invoke(main, ["doctor"])
    assert result.exit_code == 0
    assert "Warp" in result.output


def test_doctor_ok_for_iterm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Doctor shows OK for standard terminals."""
    monkeypatch.setenv("TERM_PROGRAM", "iTerm.app")
    monkeypatch.setattr("promptune.cli._check_tier1", lambda: (True, "Mocked"))
    monkeypatch.setattr("promptune.cli._check_tier2", lambda: (True, "Mocked"))
    runner = CliRunner()
    result = runner.invoke(main, ["doctor"])
    assert "Warp" not in result.output
    assert "Shell widget compatible" in result.output


class TestShellInitCLI:
    """CLI shell-init command with --shell and --key flags."""

    def test_default_outputs_zsh(self) -> None:
        runner = CliRunner()
        # Pin $SHELL so detection is deterministic across CI platforms
        # (the Linux runner defaults to bash, which has no bindkey).
        result = runner.invoke(
            main, ["shell-init"], env={"SHELL": "/bin/zsh"}
        )
        assert result.exit_code == 0
        assert "bindkey" in result.output

    def test_shell_bash_flag(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["shell-init", "--shell", "bash"])
        assert result.exit_code == 0
        assert "bind -x" in result.output
        assert "READLINE_LINE" in result.output

    def test_shell_fish_flag(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["shell-init", "--shell", "fish"])
        assert result.exit_code == 0
        assert "commandline" in result.output

    def test_custom_key_flag(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            main, ["shell-init", "--shell", "zsh", "--key", "ctrl+x ctrl+e"]
        )
        assert result.exit_code == 0
        assert "'^X^E'" in result.output

    def test_shell_fish_with_custom_key(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            main, ["shell-init", "--shell", "fish", "--key", "alt+e"]
        )
        assert result.exit_code == 0
        assert "\\ee" in result.output


# --- MCP command ---


class TestMcpCommand:
    """promptune mcp command."""

    def test_mcp_calls_run_server(self, mocker) -> None:
        mock_run = mocker.patch(
            "promptune.cli.run_mcp_server"
        )
        runner = CliRunner()
        result = runner.invoke(main, ["mcp"])
        assert result.exit_code == 0
        mock_run.assert_called_once()

    def test_mcp_exits_1_when_mcp_not_installed(
        self, mocker
    ) -> None:
        mocker.patch(
            "promptune.cli.run_mcp_server",
            side_effect=ImportError(
                "pip install promptune[mcp]"
            ),
        )
        runner = CliRunner()
        result = runner.invoke(main, ["mcp"])
        assert result.exit_code == 1
        assert "pip install" in result.output


# --- Config init interactive ---


class TestConfigInitInteractive:
    """Interactive config init wizard via CLI."""

    def test_interactive_creates_config(
        self, mocker, tmp_path,
    ) -> None:
        config_file = tmp_path / "config.toml"
        mocker.patch(
            "promptune.cli._get_config_path",
            return_value=config_file,
        )
        mocker.patch(
            "promptune.cli._is_interactive",
            return_value=True,
        )
        mocker.patch(
            "promptune.setup.detect_tools",
            return_value=[],
        )

        runner = CliRunner()
        result = runner.invoke(
            main,
            ["config", "init"],
            input="claude\nsk-ant-test123\n\nn\n",
        )
        assert result.exit_code == 0
        assert config_file.exists()
        content = config_file.read_text()
        assert "sk-ant-test123" in content

    def test_interactive_with_existing_config(
        self, mocker, tmp_path,
    ) -> None:
        config_file = tmp_path / "config.toml"
        config_file.parent.mkdir(
            parents=True, exist_ok=True
        )
        config_file.write_text(
            '[provider]\ndefault = "openai"\n\n'
            '[api_keys]\nopenai = "sk-existing"\n'
        )
        mocker.patch(
            "promptune.cli._get_config_path",
            return_value=config_file,
        )
        mocker.patch(
            "promptune.cli._is_interactive",
            return_value=True,
        )
        mocker.patch(
            "promptune.setup.detect_tools",
            return_value=[],
        )

        runner = CliRunner()
        result = runner.invoke(
            main,
            ["config", "init"],
            input="\n\n\nn\n",
        )
        assert result.exit_code == 0

    def test_non_interactive_creates_default(
        self, mocker, tmp_path,
    ) -> None:
        config_file = tmp_path / "config.toml"
        mocker.patch(
            "promptune.cli._get_config_path",
            return_value=config_file,
        )
        mocker.patch(
            "promptune.cli._is_interactive",
            return_value=False,
        )

        runner = CliRunner()
        result = runner.invoke(
            main, ["config", "init"]
        )
        assert result.exit_code == 0
        assert config_file.exists()
        assert oct(config_file.stat().st_mode & 0o777) == "0o600"

    def test_config_dir_flag_still_works(
        self, mocker, tmp_path,
    ) -> None:
        config_dir = tmp_path / "custom"
        mocker.patch(
            "promptune.cli._is_interactive",
            return_value=True,
        )
        mocker.patch(
            "promptune.setup.detect_tools",
            return_value=[],
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "config", "init",
                "--config-dir", str(config_dir),
            ],
            input="claude\nsk-ant-test\n\nn\n",
        )
        assert result.exit_code == 0
        assert (config_dir / "config.toml").exists()


def test_config_init_ctrl_c_no_partial_write(
    mocker, tmp_path,
) -> None:
    """Ctrl+C during wizard does not write partial config."""
    config_file = tmp_path / "config.toml"
    mocker.patch(
        "promptune.cli._get_config_path",
        return_value=config_file,
    )
    mocker.patch(
        "promptune.cli._is_interactive",
        return_value=True,
    )
    mocker.patch(
        "promptune.setup.run_interactive_setup",
        side_effect=KeyboardInterrupt,
    )

    runner = CliRunner()
    result = runner.invoke(main, ["config", "init"])
    assert result.exit_code == 130
    assert not config_file.exists()


def test_history_preferences_flag(tmp_path, mocker) -> None:
    """--preferences flag shows learned preferences."""
    from click.testing import CliRunner

    from promptune.cli import main
    from promptune.preferences import EditPattern, Preference

    mocker.patch(
        "promptune.cli.load_config",
        return_value={
            "history": {"enabled": True},
            "enhancement": {"preference_min_samples": 5},
        },
    )

    mock_store = mocker.MagicMock()
    mocker.patch("promptune.cli.HistoryStore", return_value=mock_store)

    mocker.patch(
        "promptune.cli.analyse_rule_preferences",
        return_value=[
            Preference(
                rule_name="role_assignment",
                action="skip",
                confidence=0.8,
                sample_count=10,
            ),
        ],
    )
    mocker.patch(
        "promptune.cli.analyse_edit_patterns",
        return_value=[
            EditPattern(
                pattern_type="removes_role",
                description="User removes role assignment",
                frequency=0.85,
                sample_count=10,
            ),
        ],
    )

    runner = CliRunner()
    result = runner.invoke(main, ["history", "--preferences"])

    assert result.exit_code == 0
    assert "role_assignment" in result.output
    assert "skip" in result.output


# ── Daemon CLI tests ─────────────────────────────────────────────


def test_daemon_group_exists():
    runner = CliRunner()
    result = runner.invoke(main, ["daemon", "--help"])
    assert result.exit_code == 0
    assert "start" in result.output
    assert "stop" in result.output
    assert "status" in result.output
    assert "setup" in result.output
    assert "diagnose" in result.output
    assert "install" in result.output
    assert "uninstall" in result.output
    assert "purge" in result.output


def test_daemon_start_help():
    runner = CliRunner()
    result = runner.invoke(main, ["daemon", "start", "--help"])
    assert result.exit_code == 0
    assert "--foreground" in result.output


def test_daemon_status_not_running(mocker):
    mock_status = MagicMock(
        running=False,
        pid=None,
        uptime_seconds=None,
        enhancement_count=0,
        socket_exists=False,
        accessibility_granted=True,
    )
    mocker.patch(
        "promptune.cli._get_daemon_status",
        return_value=mock_status,
    )
    runner = CliRunner()
    result = runner.invoke(main, ["daemon", "status"])
    assert result.exit_code == 0
    assert "not running" in result.output.lower()
    assert "granted" in result.output


def test_daemon_status_running(mocker):
    mock_status = MagicMock(
        running=True,
        pid=12345,
        uptime_seconds=3720.0,
        enhancement_count=42,
        socket_exists=True,
        accessibility_granted=True,
    )
    mocker.patch(
        "promptune.cli._get_daemon_status",
        return_value=mock_status,
    )
    runner = CliRunner()
    result = runner.invoke(main, ["daemon", "status"])
    assert result.exit_code == 0
    assert "12345" in result.output
    assert "42" in result.output


def test_daemon_diagnose(mocker):
    mock_status = MagicMock(
        running=False,
        pid=None,
        uptime_seconds=None,
        enhancement_count=0,
        socket_exists=False,
        accessibility_granted=True,
    )
    mocker.patch(
        "promptune.cli._get_daemon_status",
        return_value=mock_status,
    )
    mock_platform = MagicMock()
    mock_platform.service.is_installed.return_value = False
    mocker.patch(
        "promptune.daemon.platform.get_platform",
        return_value=mock_platform,
    )
    runner = CliRunner()
    result = runner.invoke(main, ["daemon", "diagnose"])
    assert result.exit_code == 0
    assert "diagnose" in result.output
    assert "Issues" in result.output


def test_daemon_install_calls_service(mocker):
    mock_platform = MagicMock()
    mocker.patch(
        "promptune.daemon.platform.get_platform",
        return_value=mock_platform,
    )
    # On Linux, `daemon install` runs a real dependency check before
    # installing; stub it so the install path is exercised on every platform.
    mock_checker = mocker.patch(
        "promptune.daemon.platform.linux_service.LinuxDependencyChecker"
    )
    mock_checker.return_value.check.return_value = []
    runner = CliRunner()
    result = runner.invoke(main, ["daemon", "install"])
    assert result.exit_code == 0
    mock_platform.service.install.assert_called_once()


def test_daemon_uninstall_calls_service(mocker):
    mock_platform = MagicMock()
    mocker.patch(
        "promptune.daemon.platform.get_platform",
        return_value=mock_platform,
    )
    runner = CliRunner()
    result = runner.invoke(main, ["daemon", "uninstall"])
    assert result.exit_code == 0
    mock_platform.service.uninstall.assert_called_once()


def test_daemon_purge_calls_service(mocker):
    mock_platform = MagicMock()
    mocker.patch(
        "promptune.daemon.platform.get_platform",
        return_value=mock_platform,
    )
    runner = CliRunner()
    result = runner.invoke(main, ["daemon", "purge"], input="y\n")
    assert result.exit_code == 0
    mock_platform.service.purge.assert_called_once()


def test_daemon_install_login_item_help():
    runner = CliRunner()
    result = runner.invoke(
        main, ["daemon", "install-login-item", "--help"]
    )
    assert result.exit_code == 0


def test_daemon_uninstall_login_item_help():
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["daemon", "uninstall-login-item", "--help"],
    )
    assert result.exit_code == 0


# ── Enhance: empty prompt / stdin / errors ────────────────────


def test_enhance_empty_prompt_exits_1():
    """Empty prompt with no stdin → exit 1."""
    runner = CliRunner()
    result = runner.invoke(main, ["enhance"])
    assert result.exit_code == 1
    assert "Empty prompt" in result.output


def test_enhance_stdin_pipe(mocker):
    """Prompt read from piped stdin."""
    mock_enhance = mocker.patch("promptune.cli.enhance")
    mock_enhance.return_value = MagicMock(
        original="piped",
        enhanced="piped enhanced",
        tier_used=0,
        latency_ms=1.0,
        score_before=MagicMock(total=10),
        score_after=MagicMock(total=80),
        rules_applied=[],
        format_style="xml",
    )
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["enhance", "--no-tui"],
        input="piped prompt\n",
    )
    assert result.exit_code == 0
    assert "piped enhanced" in result.output


def test_enhance_config_error(mocker):
    """ConfigError → exit 1 with message."""
    from promptune.config import ConfigError

    mocker.patch(
        "promptune.cli.load_config",
        side_effect=ConfigError("bad config"),
    )
    runner = CliRunner()
    result = runner.invoke(
        main, ["enhance", "--no-tui", "test"]
    )
    assert result.exit_code == 1
    assert "bad config" in result.output


def test_enhance_provider_error(mocker):
    """ProviderError → exit 1 with message."""
    mocker.patch(
        "promptune.cli.load_config",
        side_effect=ProviderError("no key"),
    )
    runner = CliRunner()
    result = runner.invoke(
        main, ["enhance", "--no-tui", "test"]
    )
    assert result.exit_code == 1
    assert "no key" in result.output


def test_enhance_keyboard_interrupt(mocker):
    """Ctrl+C → exit 130."""
    mocker.patch(
        "promptune.cli.load_config",
        side_effect=KeyboardInterrupt,
    )
    runner = CliRunner()
    result = runner.invoke(
        main, ["enhance", "--no-tui", "test"]
    )
    assert result.exit_code == 130


def test_enhance_tui_display(mocker):
    """TUI branch when --no-tui is not set."""
    mock_enhance = mocker.patch("promptune.cli.enhance")
    mock_enhance.return_value = MagicMock(
        original="test",
        enhanced="enhanced test",
        tier_used=0,
        latency_ms=1.0,
        score_before=MagicMock(total=10),
        score_after=MagicMock(total=80),
        rules_applied=[],
        format_style="xml",
    )
    mock_display = mocker.patch(
        "promptune.tui.display_result",
        return_value="final output",
    )
    runner = CliRunner()
    result = runner.invoke(main, ["enhance", "test"])
    assert result.exit_code == 0
    mock_display.assert_called_once()


def test_enhance_tui_reject(mocker):
    """TUI returns None (user rejected) → exit 1."""
    mock_enhance = mocker.patch("promptune.cli.enhance")
    mock_enhance.return_value = MagicMock(
        original="test",
        enhanced="enhanced test",
        tier_used=0,
        latency_ms=1.0,
        score_before=MagicMock(total=10),
        score_after=MagicMock(total=80),
        rules_applied=[],
        format_style="xml",
    )
    mocker.patch(
        "promptune.tui.display_result",
        return_value=None,
    )
    runner = CliRunner()
    result = runner.invoke(main, ["enhance", "test"])
    assert result.exit_code == 1


def test_enhance_provider_override(mocker):
    """--provider flag sets cfg override."""
    mock_enhance = mocker.patch("promptune.cli.enhance")
    mock_enhance.return_value = MagicMock(
        original="test",
        enhanced="enhanced",
        tier_used=2,
        latency_ms=1.0,
        score_before=MagicMock(total=10),
        score_after=MagicMock(total=80),
        rules_applied=[],
        format_style="xml",
    )
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["enhance", "--provider", "openai", "--no-tui", "test"],
    )
    assert result.exit_code == 0
    call_cfg = mock_enhance.call_args[0][1]
    assert call_cfg["provider"]["default"] == "openai"


def test_enhance_style_override(mocker):
    """--style flag sets mode override."""
    mock_enhance = mocker.patch("promptune.cli.enhance")
    mock_enhance.return_value = MagicMock(
        original="test",
        enhanced="enhanced",
        tier_used=0,
        latency_ms=1.0,
        score_before=MagicMock(total=10),
        score_after=MagicMock(total=80),
        rules_applied=[],
        format_style="xml",
    )
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "enhance", "--style", "detailed",
            "--no-tui", "test",
        ],
    )
    assert result.exit_code == 0


def test_enhance_rejects_invalid_style() -> None:
    """--style rejects typos instead of silently dropping AI guidance."""
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "enhance", "--style", "detialed",
            "--no-tui", "test",
        ],
    )

    assert result.exit_code != 0
    assert "Invalid value for '--style'" in result.output


# ── Config show / path commands ───────────────────────────────


def test_config_show(mocker, tmp_path):
    """config show prints sections and masked keys."""
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[provider]\ndefault = "claude"\n\n'
        '[api_keys]\nclaude = "sk-ant-secret"\n'
    )
    mocker.patch(
        "promptune.cli.default_config_path",
        return_value=config_file,
    )
    runner = CliRunner()
    result = runner.invoke(main, ["config", "show"])
    assert result.exit_code == 0
    assert "[provider]" in result.output
    # Key should be masked
    assert "sk-ant-secret" not in result.output


def test_config_show_custom_path(mocker, tmp_path):
    """config show --config-path uses specified file."""
    config_file = tmp_path / "my.toml"
    config_file.write_text(
        '[provider]\ndefault = "openai"\n'
    )
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["config", "show", "--config-path", str(config_file)],
    )
    assert result.exit_code == 0
    assert "openai" in result.output


def test_config_path_cmd(mocker, tmp_path):
    """config path prints the config file path."""
    config_file = tmp_path / "config.toml"
    mocker.patch(
        "promptune.cli.default_config_path",
        return_value=config_file,
    )
    runner = CliRunner()
    result = runner.invoke(main, ["config", "path"])
    assert result.exit_code == 0
    assert str(config_file) in result.output


def test_config_path_custom(tmp_path):
    """config path --config-path overrides default."""
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "config", "path",
            "--config-path", str(tmp_path / "c.toml"),
        ],
    )
    assert result.exit_code == 0
    assert "c.toml" in result.output


# ── _update_config_value edge cases ──────────────────────────


def test_update_config_value_adds_missing_key(tmp_path):
    """Key not in file → appended under section."""
    from promptune.cli import _update_config_value

    cfg = tmp_path / "config.toml"
    cfg.write_text("[provider]\ndefault = \"claude\"\n")
    _update_config_value(cfg, "provider.model", "gpt-4o")
    content = cfg.read_text()
    assert 'model = "gpt-4o"' in content


def test_update_config_value_escapes_special_chars(tmp_path):
    """A value with quotes/backslashes round-trips through the TOML parser."""
    import tomllib

    from promptune.cli import _update_config_value

    cfg = tmp_path / "config.toml"
    cfg.write_text('[api_keys]\nclaude = ""\n')
    nasty = 'sk-"; evil = "x\\y'
    _update_config_value(cfg, "api_keys.claude", nasty)
    parsed = tomllib.loads(cfg.read_text())
    assert parsed["api_keys"]["claude"] == nasty
    assert "evil" not in parsed["api_keys"]


# ── History: disabled, preferences empty ─────────────────────


def test_history_disabled(mocker):
    """History disabled → message."""
    mocker.patch(
        "promptune.cli._get_history_store",
        return_value=None,
    )
    runner = CliRunner()
    result = runner.invoke(main, ["history"])
    assert result.exit_code == 0
    assert "disabled" in result.output.lower()


def test_history_with_entries(mocker):
    """History with entries prints them."""
    mock_entry = MagicMock(
        tier_used=1,
        original="write tests for the CLI",
        score_before=30,
        score_after=80,
    )
    mock_store = MagicMock()
    mock_store.recent.return_value = [mock_entry]
    mocker.patch(
        "promptune.cli._get_history_store",
        return_value=mock_store,
    )
    runner = CliRunner()
    result = runner.invoke(main, ["history"])
    assert result.exit_code == 0
    assert "[1]" in result.output


def test_history_preferences_empty(mocker):
    """No preferences → message."""
    mocker.patch(
        "promptune.cli.load_config",
        return_value={
            "history": {"enabled": True},
            "enhancement": {"preference_min_samples": 5},
        },
    )
    mock_store = MagicMock()
    mocker.patch(
        "promptune.cli._get_history_store",
        return_value=mock_store,
    )
    mocker.patch(
        "promptune.cli.analyse_rule_preferences",
        return_value=[],
    )
    mocker.patch(
        "promptune.cli.analyse_edit_patterns",
        return_value=[],
    )
    runner = CliRunner()
    result = runner.invoke(
        main, ["history", "--preferences"]
    )
    assert result.exit_code == 0
    assert "No preferences" in result.output


# ── Daemon start/stop/restart execution ──────────────────────


def test_daemon_start_calls_start(mocker):
    """daemon start invokes start_daemon."""
    mock_start = mocker.patch(
        "promptune.daemon.daemon.start_daemon",
    )
    runner = CliRunner()
    result = runner.invoke(main, ["daemon", "start"])
    assert result.exit_code == 0
    mock_start.assert_called_once_with(foreground=False)


def test_daemon_start_foreground(mocker):
    """daemon start --foreground passes flag."""
    mock_start = mocker.patch(
        "promptune.daemon.daemon.start_daemon",
    )
    runner = CliRunner()
    result = runner.invoke(
        main, ["daemon", "start", "--foreground"]
    )
    assert result.exit_code == 0
    mock_start.assert_called_once_with(foreground=True)


def test_daemon_stop_calls_stop(mocker):
    """daemon stop invokes stop_daemon."""
    mock_stop = mocker.patch(
        "promptune.daemon.daemon.stop_daemon",
    )
    runner = CliRunner()
    result = runner.invoke(main, ["daemon", "stop"])
    assert result.exit_code == 0
    mock_stop.assert_called_once()


def test_daemon_restart_calls_both(mocker):
    """daemon restart calls stop then start."""
    mock_stop = mocker.patch(
        "promptune.daemon.daemon.stop_daemon",
    )
    mock_start = mocker.patch(
        "promptune.daemon.daemon.start_daemon",
    )
    runner = CliRunner()
    result = runner.invoke(main, ["daemon", "restart"])
    assert result.exit_code == 0
    mock_stop.assert_called_once()
    mock_start.assert_called_once()


# ── Daemon setup (macOS path) ────────────────────────────────


@pytest.mark.skipif(
    sys.platform != "darwin",
    reason="patches macOS-only promptune.daemon.hotkey (unimportable on Linux)",
)
def test_daemon_setup_macos_already_granted(mocker):
    """setup on macOS when already granted → early return."""
    mocker.patch("sys.platform", "darwin")
    mocker.patch(
        "promptune.daemon.hotkey.check_accessibility",
        return_value=True,
    )
    runner = CliRunner()
    result = runner.invoke(main, ["daemon", "setup"])
    assert result.exit_code == 0
    assert "already granted" in result.output


@pytest.mark.skipif(
    sys.platform != "darwin",
    reason="patches macOS-only promptune.daemon.hotkey (unimportable on Linux)",
)
def test_daemon_setup_macos_wait_grant(mocker):
    """setup on macOS waits then grants."""
    mocker.patch("sys.platform", "darwin")
    call_count = 0

    def mock_check():
        nonlocal call_count
        call_count += 1
        return call_count >= 3

    mocker.patch(
        "promptune.daemon.hotkey.check_accessibility",
        side_effect=mock_check,
    )
    mocker.patch(
        "promptune.daemon.hotkey.request_accessibility",
    )
    mocker.patch("subprocess.run")
    mocker.patch("time.sleep")
    runner = CliRunner()
    result = runner.invoke(main, ["daemon", "setup"])
    assert result.exit_code == 0
    assert "granted" in result.output


@pytest.mark.skipif(
    sys.platform != "darwin",
    reason="patches macOS-only promptune.daemon.hotkey (unimportable on Linux)",
)
def test_daemon_setup_macos_timeout(mocker):
    """setup on macOS times out after 60 checks."""
    mocker.patch("sys.platform", "darwin")
    mocker.patch(
        "promptune.daemon.hotkey.check_accessibility",
        return_value=False,
    )
    mocker.patch(
        "promptune.daemon.hotkey.request_accessibility",
    )
    mocker.patch("subprocess.run")
    mocker.patch("time.sleep")
    runner = CliRunner()
    result = runner.invoke(main, ["daemon", "setup"])
    assert result.exit_code == 0
    assert "Timeout" in result.output


def test_daemon_setup_linux(mocker):
    """setup on linux checks dependencies."""
    mocker.patch("sys.platform", "linux")
    mock_dep = MagicMock(installed=True, required=True)
    mock_dep.name = "xdotool"
    mock_checker = MagicMock()
    mock_checker.check.return_value = [mock_dep]
    mocker.patch(
        "promptune.daemon.platform.linux_service"
        ".LinuxDependencyChecker",
        return_value=mock_checker,
    )
    mocker.patch.dict("os.environ", {"XDG_SESSION_TYPE": ""})
    runner = CliRunner()
    result = runner.invoke(main, ["daemon", "setup"])
    assert result.exit_code == 0
    assert "All dependencies" in result.output


def test_daemon_setup_unsupported_platform(mocker):
    """setup on unsupported platform → exit 1."""
    mocker.patch("sys.platform", "win32")
    runner = CliRunner()
    result = runner.invoke(main, ["daemon", "setup"])
    assert result.exit_code == 1
    assert "Unsupported" in result.output


# ── Daemon install/uninstall PlatformError ────────────────────


def test_daemon_install_platform_error(mocker):
    """install with PlatformError → exit 1."""
    from promptune.daemon.platform import PlatformError

    mocker.patch(
        "promptune.daemon.platform.get_platform",
        side_effect=PlatformError("unsupported"),
    )
    runner = CliRunner()
    result = runner.invoke(main, ["daemon", "install"])
    assert result.exit_code == 1
    assert "unsupported" in result.output


def test_daemon_uninstall_platform_error(mocker):
    """uninstall with PlatformError → exit 1."""
    from promptune.daemon.platform import PlatformError

    mocker.patch(
        "promptune.daemon.platform.get_platform",
        side_effect=PlatformError("unsupported"),
    )
    runner = CliRunner()
    result = runner.invoke(
        main, ["daemon", "uninstall"]
    )
    assert result.exit_code == 1
    assert "unsupported" in result.output


def test_daemon_purge_platform_error(mocker):
    """purge with PlatformError → exit 1."""
    from promptune.daemon.platform import PlatformError

    mocker.patch(
        "promptune.daemon.platform.get_platform",
        side_effect=PlatformError("unsupported"),
    )
    runner = CliRunner()
    result = runner.invoke(
        main, ["daemon", "purge"], input="y\n"
    )
    assert result.exit_code == 1
    assert "unsupported" in result.output


def test_daemon_purge_declined(mocker):
    """purge declined → no action."""
    runner = CliRunner()
    result = runner.invoke(
        main, ["daemon", "purge"], input="n\n"
    )
    assert result.exit_code == 0


def test_daemon_diagnose_platform_error(mocker):
    """diagnose with PlatformError → exit 1."""
    from promptune.daemon.platform import PlatformError

    mocker.patch(
        "promptune.daemon.platform.get_platform",
        side_effect=PlatformError("unsupported"),
    )
    runner = CliRunner()
    result = runner.invoke(
        main, ["daemon", "diagnose"]
    )
    assert result.exit_code == 1


# ── Login item commands (macOS execution) ────────────────────


def test_install_login_item_macos(mocker):
    """install-login-item on macOS calls the function."""
    mocker.patch("sys.platform", "darwin")
    mock_install = mocker.patch(
        "promptune.daemon.launchagent.install_login_item",
    )
    runner = CliRunner()
    result = runner.invoke(
        main, ["daemon", "install-login-item"]
    )
    assert result.exit_code == 0
    mock_install.assert_called_once()
    assert "LaunchAgent installed" in result.output


def test_install_login_item_non_macos(mocker):
    """install-login-item on linux → exit 1."""
    mocker.patch("sys.platform", "linux")
    runner = CliRunner()
    result = runner.invoke(
        main, ["daemon", "install-login-item"]
    )
    assert result.exit_code == 1
    assert "macOS-only" in result.output


def test_uninstall_login_item_macos(mocker):
    """uninstall-login-item on macOS calls the function."""
    mocker.patch("sys.platform", "darwin")
    mock_uninstall = mocker.patch(
        "promptune.daemon.launchagent.uninstall_login_item",
    )
    runner = CliRunner()
    result = runner.invoke(
        main, ["daemon", "uninstall-login-item"]
    )
    assert result.exit_code == 0
    mock_uninstall.assert_called_once()


def test_uninstall_login_item_non_macos(mocker):
    """uninstall-login-item on linux → exit 1."""
    mocker.patch("sys.platform", "linux")
    runner = CliRunner()
    result = runner.invoke(
        main, ["daemon", "uninstall-login-item"]
    )
    assert result.exit_code == 1
    assert "macOS-only" in result.output


# ── _check helper functions ──────────────────────────────────


def test_check_tier1_not_configured(mocker):
    """_check_tier1 when local_llm disabled."""
    from promptune.cli import _check_tier1

    mocker.patch(
        "promptune.cli.load_config",
        return_value={"local_llm": {"enabled": False}},
    )
    ok, msg = _check_tier1()
    assert not ok
    assert "Not configured" in msg


def test_check_tier1_reachable(mocker):
    """_check_tier1 when LLM responds 200."""
    from promptune.cli import _check_tier1

    mocker.patch(
        "promptune.cli.load_config",
        return_value={
            "local_llm": {
                "enabled": True,
                "host": "http://localhost:11434",
            }
        },
    )
    mock_resp = MagicMock(status_code=200)
    mocker.patch("httpx.get", return_value=mock_resp)
    ok, msg = _check_tier1()
    assert ok


def test_check_tier1_unreachable(mocker):
    """_check_tier1 when LLM unreachable."""
    from promptune.cli import _check_tier1

    mocker.patch(
        "promptune.cli.load_config",
        return_value={
            "local_llm": {
                "enabled": True,
                "host": "http://localhost:11434",
            }
        },
    )
    mocker.patch(
        "httpx.get",
        side_effect=ConnectionError("refused"),
    )
    ok, msg = _check_tier1()
    assert not ok
    assert "Cannot reach" in msg


def test_check_tier2_no_key(mocker):
    """_check_tier2 when no API key."""
    from promptune.cli import _check_tier2

    mocker.patch(
        "promptune.cli.load_config",
        return_value={
            "provider": {"default": "claude"},
            "api_keys": {"claude": ""},
        },
    )
    ok, msg = _check_tier2()
    assert not ok
    assert "No API key" in msg


def test_check_tier2_has_key(mocker):
    """_check_tier2 when API key set."""
    from promptune.cli import _check_tier2

    mocker.patch(
        "promptune.cli.load_config",
        return_value={
            "provider": {"default": "claude"},
            "api_keys": {"claude": "sk-ant-test"},
        },
    )
    ok, msg = _check_tier2()
    assert ok


def test_check_local_llm_connectivity_ok(mocker):
    """_check_local_llm_connectivity success."""
    from promptune.cli import (
        _check_local_llm_connectivity,
    )

    mocker.patch(
        "promptune.cli.load_config",
        return_value={
            "local_llm": {
                "host": "http://localhost:11434",
                "model": "qwen",
            }
        },
    )
    mock_resp = MagicMock(status_code=200)
    mocker.patch("httpx.get", return_value=mock_resp)
    ok, msg = _check_local_llm_connectivity()
    assert ok
    assert "qwen" in msg


def test_check_local_llm_connectivity_error(mocker):
    """_check_local_llm_connectivity connection error."""
    from promptune.cli import (
        _check_local_llm_connectivity,
    )

    mocker.patch(
        "promptune.cli.load_config",
        return_value={
            "local_llm": {
                "host": "http://localhost:11434",
                "model": "qwen",
            }
        },
    )
    mocker.patch(
        "httpx.get",
        side_effect=ConnectionError("refused"),
    )
    ok, msg = _check_local_llm_connectivity()
    assert not ok
    assert "Cannot reach" in msg


def test_check_local_llm_connectivity_non200(mocker):
    """_check_local_llm_connectivity non-200 status."""
    from promptune.cli import (
        _check_local_llm_connectivity,
    )

    mocker.patch(
        "promptune.cli.load_config",
        return_value={
            "local_llm": {
                "host": "http://localhost:11434",
                "model": "qwen",
            }
        },
    )
    mock_resp = MagicMock(status_code=500)
    mocker.patch("httpx.get", return_value=mock_resp)
    ok, msg = _check_local_llm_connectivity()
    assert not ok
    assert "HTTP 500" in msg


# ── Linux daemon install with missing deps ───────────────────


def test_daemon_install_linux_missing_deps(mocker):
    """install on Linux with missing deps → exit 1."""
    mocker.patch("sys.platform", "linux")
    mock_dep = MagicMock(installed=False, required=True)
    mock_dep.name = "xdotool"
    mock_checker = MagicMock()
    mock_checker.check.return_value = [mock_dep]
    mock_checker.get_install_command.return_value = (
        "sudo apt install xdotool"
    )
    mocker.patch(
        "promptune.daemon.platform.linux_service"
        ".LinuxDependencyChecker",
        return_value=mock_checker,
    )
    mock_platform = MagicMock()
    mocker.patch(
        "promptune.daemon.platform.get_platform",
        return_value=mock_platform,
    )
    runner = CliRunner()
    result = runner.invoke(main, ["daemon", "install"])
    assert result.exit_code == 1
    assert "Missing" in result.output


# ── Linux setup: wayland input group ─────────────────────────


def test_daemon_setup_linux_missing_deps(mocker):
    """setup on linux with missing deps shows install cmd."""
    mocker.patch("sys.platform", "linux")
    mock_dep = MagicMock(installed=False, required=True)
    mock_dep.name = "xclip"
    mock_checker = MagicMock()
    mock_checker.check.return_value = [mock_dep]
    mock_checker.get_install_command.return_value = (
        "sudo apt install xclip"
    )
    mocker.patch(
        "promptune.daemon.platform.linux_service"
        ".LinuxDependencyChecker",
        return_value=mock_checker,
    )
    mocker.patch.dict("os.environ", {"XDG_SESSION_TYPE": ""})
    runner = CliRunner()
    result = runner.invoke(main, ["daemon", "setup"])
    assert result.exit_code == 0
    assert "Install" in result.output


def test_daemon_setup_linux_wayland_group(mocker):
    """setup on linux wayland suggests input group."""
    mocker.patch("sys.platform", "linux")
    mock_checker = MagicMock()
    mock_checker.check.return_value = []
    mocker.patch(
        "promptune.daemon.platform.linux_service"
        ".LinuxDependencyChecker",
        return_value=mock_checker,
    )
    mocker.patch.dict(
        "os.environ", {"XDG_SESSION_TYPE": "wayland"}
    )
    mock_grp = MagicMock()
    mock_grp.gr_mem = []
    mocker.patch("grp.getgrnam", return_value=mock_grp)
    mock_pwd = MagicMock()
    mock_pwd.pw_name = "testuser"
    mocker.patch("pwd.getpwuid", return_value=mock_pwd)
    runner = CliRunner()
    result = runner.invoke(main, ["daemon", "setup"])
    assert result.exit_code == 0
    assert "usermod" in result.output


# ── Daemon diagnose: linux branch ────────────────────────────


def test_daemon_diagnose_linux(mocker):
    """diagnose on Linux checks dependencies."""
    mocker.patch("sys.platform", "linux")
    mock_status = MagicMock(
        running=True,
        pid=1234,
        uptime_seconds=100.0,
        enhancement_count=5,
        socket_exists=True,
        accessibility_granted=True,
    )
    mocker.patch(
        "promptune.cli._get_daemon_status",
        return_value=mock_status,
    )
    mock_platform = MagicMock()
    mock_platform.service.is_installed.return_value = True
    mocker.patch(
        "promptune.daemon.platform.get_platform",
        return_value=mock_platform,
    )
    mock_dep = MagicMock(installed=True, required=True)
    mock_dep.name = "xdotool"
    mock_checker = MagicMock()
    mock_checker.check.return_value = [mock_dep]
    mocker.patch(
        "promptune.daemon.platform.linux_service"
        ".LinuxDependencyChecker",
        return_value=mock_checker,
    )
    runner = CliRunner()
    result = runner.invoke(main, ["daemon", "diagnose"])
    assert result.exit_code == 0
    assert "xdotool" in result.output


# ── Config reset declined ────────────────────────────────────


def test_config_reset_declined(mocker, tmp_path):
    """config --reset with 'n' → no change."""
    config_file = tmp_path / "config.toml"
    config_file.write_text('[provider]\ndefault="x"\n')
    mocker.patch(
        "promptune.cli._get_config_path",
        return_value=config_file,
    )
    runner = CliRunner()
    result = runner.invoke(
        main, ["config", "--reset"], input="n\n"
    )
    assert result.exit_code == 0
    assert config_file.read_text().startswith("[provider]")


# ── _get_history_store branches ──────────────────────────────


def test_get_history_store_disabled(mocker):
    """_get_history_store returns None when disabled."""
    from promptune.cli import _get_history_store

    mocker.patch(
        "promptune.cli.load_config",
        return_value={"history": {"enabled": False}},
    )
    assert _get_history_store() is None


def test_get_history_store_enabled(mocker):
    """_get_history_store returns store when enabled."""
    from promptune.cli import _get_history_store

    mocker.patch(
        "promptune.cli.load_config",
        return_value={"history": {"enabled": True}},
    )
    mock_store = MagicMock()
    mocker.patch(
        "promptune.cli.HistoryStore",
        return_value=mock_store,
    )
    result = _get_history_store()
    assert result is mock_store


def test_get_history_store_passes_configured_path(mocker):
    """_get_history_store honours configured db_path and max_entries."""
    from pathlib import Path

    from promptune.cli import _get_history_store

    mocker.patch(
        "promptune.cli.load_config",
        return_value={
            "history": {
                "enabled": True,
                "db_path": "~/custom/place/history.db",
                "max_entries": 42,
            }
        },
    )
    store_cls = mocker.patch("promptune.cli.HistoryStore")

    _get_history_store()

    kwargs = store_cls.call_args.kwargs
    assert kwargs["max_entries"] == 42
    assert kwargs["db_path"] == Path("~/custom/place/history.db").expanduser()


def test_malformed_config_shows_clean_error_not_traceback(tmp_path) -> None:
    """Commands that load config report a clean error on a malformed file."""
    bad = tmp_path / "config.toml"
    bad.write_text("this is = [[[ not valid toml")
    runner = CliRunner()
    result = runner.invoke(
        main, ["config", "show", "--config-path", str(bad)]
    )
    assert result.exit_code == 1
    assert "Error:" in result.output
    # A clean SystemExit, not an unhandled ConfigError traceback.
    assert result.exception is None or isinstance(
        result.exception, SystemExit
    )


def test_enhance_reject_records_reject_decision(mocker) -> None:
    """Rejecting in the TUI corrects the history record to 'reject' so dedup
    never resurfaces a declined enhancement (Codex review on PR #16)."""
    spy = mocker.patch("promptune.cli._update_history_decision")
    mocker.patch("promptune.tui.display_result", return_value=None)

    result = CliRunner().invoke(
        main, ["enhance", "fix the bug in the parser module"]
    )

    assert result.exit_code == 1  # reject exits non-zero
    assert spy.called
    _cfg, _id, decision, edit_result = spy.call_args[0]
    assert decision == "reject"
    assert edit_result is None


def test_enhance_edit_records_edit_decision(mocker) -> None:
    """Editing in the TUI records the edited text under an 'edit' decision."""
    spy = mocker.patch("promptune.cli._update_history_decision")
    mocker.patch(
        "promptune.tui.display_result", return_value="my edited version"
    )

    result = CliRunner().invoke(
        main, ["enhance", "fix the bug in the parser module"]
    )

    assert result.exit_code == 0
    assert spy.called
    _cfg, _id, decision, edit_result = spy.call_args[0]
    assert decision == "edit"
    assert edit_result == "my edited version"


def test_enhance_accept_leaves_decision_untouched(mocker) -> None:
    """Accepting leaves the 'accept' record as-is — no decision correction."""
    spy = mocker.patch("promptune.cli._update_history_decision")
    # display_result returning the unchanged enhanced text == ACCEPT.
    mocker.patch(
        "promptune.tui.display_result",
        side_effect=lambda result: result.enhanced,
    )

    out = CliRunner().invoke(
        main, ["enhance", "fix the bug in the parser module"]
    )

    assert out.exit_code == 0
    spy.assert_not_called()
