"""Step 10: Polish & Release — tests."""


from click.testing import CliRunner
from pytest_mock import MockerFixture

from promptune.cli import main
from promptune.providers import ProviderError


def test_no_tui_flag_prints_directly(mocker: MockerFixture) -> None:
    """--no-tui skips TUI, prints to stdout."""
    mocker.patch(
        "promptune.cli.enhance",
        return_value=mocker.MagicMock(
            original="rough", enhanced="polished prompt"
        ),
    )
    mocker.patch(
        "promptune.cli.load_config",
        return_value={
            "general": {"default_provider": "claude", "style": "balanced"},
            "providers": {
                "claude": {"api_key": "k", "model": "m"},
            },
            "tui": {"theme": "dark", "show_diff": True},
        },
    )

    runner = CliRunner()
    result = runner.invoke(
        main, ["enhance", "--no-tui", "rough"]
    )

    assert result.exit_code == 0
    assert "polished prompt" in result.output


def test_empty_prompt_error() -> None:
    """Empty input shows helpful error."""
    runner = CliRunner()
    result = runner.invoke(main, ["enhance", ""])

    assert result.exit_code != 0
    assert "empty" in result.output.lower() or "prompt" in result.output.lower()


def test_network_error_message(mocker: MockerFixture) -> None:
    """Connection failure shows user-friendly message."""
    mocker.patch(
        "promptune.cli.enhance",
        side_effect=ProviderError("Connection refused"),
    )
    mocker.patch(
        "promptune.cli.load_config",
        return_value={
            "general": {"default_provider": "claude", "style": "balanced"},
            "providers": {
                "claude": {"api_key": "k", "model": "m"},
            },
            "tui": {"theme": "dark", "show_diff": True},
        },
    )

    runner = CliRunner()
    result = runner.invoke(main, ["enhance", "--no-tui", "test"])

    assert result.exit_code != 0
    assert "error" in result.output.lower() or "Connection" in result.output


def test_keyboard_interrupt_clean_exit(
    mocker: MockerFixture,
) -> None:
    """Ctrl+C exits gracefully."""
    mocker.patch(
        "promptune.cli.enhance",
        side_effect=KeyboardInterrupt,
    )
    mocker.patch(
        "promptune.cli.load_config",
        return_value={
            "general": {"default_provider": "claude", "style": "balanced"},
            "providers": {
                "claude": {"api_key": "k", "model": "m"},
            },
            "tui": {"theme": "dark", "show_diff": True},
        },
    )

    runner = CliRunner()
    result = runner.invoke(main, ["enhance", "--no-tui", "test"])

    # Should not show a traceback
    assert "Traceback" not in result.output


def test_enhance_cli_with_pipe(mocker: MockerFixture) -> None:
    """Piped input works."""
    mocker.patch(
        "promptune.cli.enhance",
        return_value=mocker.MagicMock(
            original="piped", enhanced="enhanced piped"
        ),
    )
    mocker.patch(
        "promptune.cli.load_config",
        return_value={
            "general": {"default_provider": "claude", "style": "balanced"},
            "providers": {
                "claude": {"api_key": "k", "model": "m"},
            },
            "tui": {"theme": "dark", "show_diff": True},
        },
    )

    runner = CliRunner()
    result = runner.invoke(
        main, ["enhance", "--no-tui"], input="piped prompt\n"
    )

    assert result.exit_code == 0
    assert "enhanced piped" in result.output


def test_enhance_cli_with_argument(mocker: MockerFixture) -> None:
    """'promptune enhance "my prompt"' works."""
    mocker.patch(
        "promptune.cli.enhance",
        return_value=mocker.MagicMock(
            original="my prompt", enhanced="better prompt"
        ),
    )
    mocker.patch(
        "promptune.cli.load_config",
        return_value={
            "general": {"default_provider": "claude", "style": "balanced"},
            "providers": {
                "claude": {"api_key": "k", "model": "m"},
            },
            "tui": {"theme": "dark", "show_diff": True},
        },
    )

    runner = CliRunner()
    result = runner.invoke(
        main, ["enhance", "--no-tui", "my prompt"]
    )

    assert result.exit_code == 0
    assert "better prompt" in result.output


def test_full_integration_mock(mocker: MockerFixture) -> None:
    """End-to-end with mocked provider."""
    mocker.patch(
        "promptune.cli.enhance",
        return_value=mocker.MagicMock(
            original="build a todo app",
            enhanced="Build a full-stack todo application",
        ),
    )
    mocker.patch(
        "promptune.cli.load_config",
        return_value={
            "general": {"default_provider": "claude", "style": "balanced"},
            "providers": {
                "claude": {"api_key": "k", "model": "m"},
            },
            "tui": {"theme": "dark", "show_diff": True},
        },
    )

    runner = CliRunner()
    result = runner.invoke(
        main, ["enhance", "--no-tui", "build a todo app"]
    )

    assert result.exit_code == 0
    assert "full-stack todo" in result.output
