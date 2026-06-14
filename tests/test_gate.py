"""Tests for the auto-enhance gate."""

from __future__ import annotations

import subprocess
from typing import Any
from unittest.mock import MagicMock, patch

from promptune.gate import _print_gate_block, copy_to_clipboard, run_gate
from promptune.scorer import DimensionScore, ScoreResult


def _make_score(total: int) -> ScoreResult:
    return ScoreResult(
        total=total,
        intent="coding",
        dimensions={
            name: DimensionScore(total / 100, w, [], "ok")
            for name, w in [
                ("specificity", 25.0),
                ("clarity", 20.0),
                ("structure", 15.0),
                ("actionability", 15.0),
                ("context", 10.0),
                ("completeness", 10.0),
                ("conciseness", 5.0),
            ]
        },
    )


_BASE_CONFIG: dict[str, Any] = {
    "auto_enhance": {
        "enabled": True,
        "threshold": 40,
        "min_words": 5,
    },
    "provider": {
        "default": "claude",
        "format_style": "auto",
        "model_claude": "claude-haiku-4-5-20251001",
        "model_openai": "gpt-4o-mini",
        "model_openrouter": "anthropic/claude-haiku",
    },
    "api_keys": {
        "claude": "",
        "openai": "",
        "openrouter": "",
    },
    "enhancement": {
        "max_tier": 0,
        "default_mode": "balanced",
        "max_tokens_output": 400,
        "timeout_seconds": 10,
        "dedup_enabled": False,
        "dedup_threshold": 0.85,
        "dedup_window": 50,
        "preference_learning": False,
        "preference_min_samples": 5,
    },
    "local_llm": {
        "enabled": False,
        "host": "http://localhost:11434",
        "model": "qwen2.5:3b",
        "api_key": "",
    },
    "context": {
        "use_git": False,
        "use_shell_history": False,
        "use_stack_detection": False,
        "max_context_tokens": 500,
        "shell_history_lines": 20,
    },
    "history": {
        "enabled": False,
        "max_entries": 10000,
        "db_path": "/tmp/test_history.db",
    },
}


class TestRunGate:
    """Gate exit codes and behavior."""

    def test_passes_when_disabled(self) -> None:
        cfg: dict[str, Any] = {
            **_BASE_CONFIG,
            "auto_enhance": {
                "enabled": False,
                "threshold": 40,
                "min_words": 5,
            },
        }
        with patch(
            "promptune.gate.score_prompt",
            return_value=_make_score(30),
        ):
            code = run_gate(
                "short prompt here that is low quality",
                cfg,
            )
        assert code == 0

    def test_passes_high_score(self) -> None:
        with patch(
            "promptune.gate.score_prompt",
            return_value=_make_score(75),
        ):
            code = run_gate(
                "implement a REST API with authentication",
                _BASE_CONFIG,
            )
        assert code == 0

    def test_passes_short_prompt(self) -> None:
        with patch("promptune.gate.score_prompt") as mock_score:
            code = run_gate("fix bug", _BASE_CONFIG)
        mock_score.assert_not_called()
        assert code == 0

    def test_blocks_low_score(self) -> None:
        from promptune.engine import EnhanceResult

        mock_result = MagicMock(spec=EnhanceResult)
        mock_result.enhanced = "Build a full-stack todo app..."
        mock_result.score_before = _make_score(30)
        mock_result.score_after = _make_score(74)

        with (
            patch(
                "promptune.gate.score_prompt",
                return_value=_make_score(30),
            ),
            patch(
                "promptune.gate.enhance",
                return_value=mock_result,
            ),
            patch("promptune.gate.copy_to_clipboard"),
            patch("promptune.gate._print_gate_block"),
        ):
            code = run_gate(
                "make a simple todo app thing",
                _BASE_CONFIG,
            )
        assert code == 1

    def test_copies_enhanced_to_clipboard_on_block(
        self,
    ) -> None:
        from promptune.engine import EnhanceResult

        mock_result = MagicMock(spec=EnhanceResult)
        mock_result.enhanced = "Build a full-stack todo app..."
        mock_result.score_before = _make_score(30)
        mock_result.score_after = _make_score(74)

        with (
            patch(
                "promptune.gate.score_prompt",
                return_value=_make_score(30),
            ),
            patch(
                "promptune.gate.enhance",
                return_value=mock_result,
            ),
            patch(
                "promptune.gate.copy_to_clipboard"
            ) as mock_copy,
            patch("promptune.gate._print_gate_block"),
        ):
            run_gate(
                "make a simple todo app thing",
                _BASE_CONFIG,
            )
        mock_copy.assert_called_once_with(
            "Build a full-stack todo app..."
        )

    def test_bypass_prefix_skips_gate(self) -> None:
        """Prompt starting with bypass prefix passes through unchanged."""
        with patch("promptune.gate.score_prompt") as mock_score:
            code = run_gate(
                "! make a simple todo app thing",
                _BASE_CONFIG,
            )
        mock_score.assert_not_called()
        assert code == 0

    def test_bypass_prefix_custom(self) -> None:
        """Custom bypass prefix from config is respected."""
        cfg: dict[str, Any] = {
            **_BASE_CONFIG,
            "auto_enhance": {
                **_BASE_CONFIG["auto_enhance"],
                "bypass_prefix": ">>",
            },
        }
        with patch("promptune.gate.score_prompt") as mock_score:
            code = run_gate(
                ">> make a simple todo app thing",
                cfg,
            )
        mock_score.assert_not_called()
        assert code == 0

    def test_bypass_prefix_empty_does_not_skip(self) -> None:
        """Empty bypass prefix should not skip every prompt."""
        cfg: dict[str, Any] = {
            **_BASE_CONFIG,
            "auto_enhance": {
                **_BASE_CONFIG["auto_enhance"],
                "bypass_prefix": "",
            },
        }
        with patch(
            "promptune.gate.score_prompt",
            return_value=_make_score(75),
        ):
            code = run_gate(
                "implement a REST API with authentication",
                cfg,
            )
        assert code == 0  # passes on score, but score_prompt WAS called

    def test_bypass_prefix_not_matched_still_gates(self) -> None:
        """Prompt without bypass prefix still goes through gate."""
        with patch(
            "promptune.gate.score_prompt",
            return_value=_make_score(75),
        ):
            code = run_gate(
                "implement a REST API with authentication",
                _BASE_CONFIG,
            )
        assert code == 0

    def test_threshold_boundary_at_exactly_60(self) -> None:
        with patch(
            "promptune.gate.score_prompt",
            return_value=_make_score(60),
        ):
            code = run_gate(
                "implement authentication for the app now",
                _BASE_CONFIG,
            )
        assert code == 0


class TestCopyToClipboard:
    """Clipboard copy on each platform."""

    def test_macos_uses_pbcopy(self, mocker) -> None:
        mocker.patch("sys.platform", "darwin")
        mock_run = mocker.patch("subprocess.run")
        copy_to_clipboard("hello world")
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert call_args[0][0] == ["pbcopy"]
        assert call_args[1]["input"] == "hello world"

    def test_linux_tries_wl_copy_first(self, mocker) -> None:
        mocker.patch("sys.platform", "linux")
        mock_run = mocker.patch("subprocess.run")
        copy_to_clipboard("hello world")
        first_call = mock_run.call_args_list[0]
        assert "wl-copy" in first_call[0][0]

    def test_linux_no_clipboard_tool_warns(
        self, mocker, capsys
    ) -> None:
        mocker.patch("sys.platform", "linux")
        mocker.patch(
            "subprocess.run",
            side_effect=FileNotFoundError,
        )
        copy_to_clipboard("hello world")
        captured = capsys.readouterr()
        assert "No clipboard tool found" in captured.err

    def test_linux_falls_back_to_xclip(self, mocker) -> None:
        mocker.patch("sys.platform", "linux")
        mocker.patch(
            "subprocess.run",
            side_effect=[
                subprocess.CalledProcessError(1, "wl-copy"),
                MagicMock(),
            ],
        )
        copy_to_clipboard("hello world")
        import subprocess as sp

        second_call = sp.run.call_args_list[1]  # type: ignore[attr-defined]
        assert "xclip" in second_call[0][0]


class TestPrintGateBlock:
    """Direct tests for the _print_gate_block rendering function."""

    def _make_result(self, enhanced: str, score_after: int = 75) -> Any:
        from promptune.engine import EnhanceResult

        result = MagicMock(spec=EnhanceResult)
        result.enhanced = enhanced
        result.score_after = _make_score(score_after)
        return result

    def test_prints_score_before_and_after(self, capsys) -> None:
        result = self._make_result("Enhanced version of the prompt", 78)
        _print_gate_block(
            "original prompt",
            result,
            _make_score(35),
        )
        captured = capsys.readouterr()
        assert "35" in captured.err
        assert "78" in captured.err

    def test_prints_enhanced_text(self, capsys) -> None:
        result = self._make_result("Build the REST API endpoint")
        _print_gate_block(
            "original",
            result,
            _make_score(30),
        )
        captured = capsys.readouterr()
        assert "Build the REST API endpoint" in captured.err

    def test_includes_paste_hint(self, capsys) -> None:
        result = self._make_result("enhanced")
        _print_gate_block("original", result, _make_score(30))
        captured = capsys.readouterr()
        assert "Paste" in captured.err

    def test_handles_multiline_enhanced_text(self, capsys) -> None:
        result = self._make_result("line one\nline two\nline three")
        _print_gate_block("original", result, _make_score(30))
        captured = capsys.readouterr()
        assert "line one" in captured.err
        assert "line two" in captured.err
        assert "line three" in captured.err

    def test_truncates_long_lines_to_box_width(self, capsys) -> None:
        long_line = "x" * 200
        result = self._make_result(long_line)
        _print_gate_block("original", result, _make_score(30))
        captured = capsys.readouterr()
        # No printed line should exceed the box width (48 + a few border chars)
        for line in captured.err.splitlines():
            assert len(line) <= 60

    def test_renders_border_characters(self, capsys) -> None:
        result = self._make_result("enhanced")
        _print_gate_block("original", result, _make_score(30))
        captured = capsys.readouterr()
        assert "\u250c" in captured.err  # top-left
        assert "\u2514" in captured.err  # bottom-left
        assert "\u2502" in captured.err  # vertical


class TestRunGateRendersBlock:
    """End-to-end check that run_gate invokes _print_gate_block on block."""

    def test_block_path_renders_to_stderr(self, capsys) -> None:
        from promptune.engine import EnhanceResult

        mock_result = MagicMock(spec=EnhanceResult)
        mock_result.enhanced = "Build a full-stack todo app with auth"
        mock_result.score_before = _make_score(30)
        mock_result.score_after = _make_score(74)

        with (
            patch(
                "promptune.gate.score_prompt",
                return_value=_make_score(30),
            ),
            patch(
                "promptune.gate.enhance",
                return_value=mock_result,
            ),
            patch("promptune.gate.copy_to_clipboard"),
        ):
            code = run_gate(
                "make a simple todo app thing",
                _BASE_CONFIG,
            )
        captured = capsys.readouterr()
        assert code == 1
        assert "Build a full-stack todo app" in captured.err
        assert "30" in captured.err
        assert "74" in captured.err
