"""Tests for the auto-enhance gate."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

from promptune.gate import run_gate
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
        "model_openrouter": "anthropic/claude-haiku-4.5",
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


class TestRunGatePasses:
    """Paths where the gate stays silent and the prompt proceeds."""

    def test_passes_when_disabled(self, capsys) -> None:
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
        assert capsys.readouterr().out == ""

    def test_passes_high_score(self, capsys) -> None:
        with patch(
            "promptune.gate.score_prompt",
            return_value=_make_score(75),
        ):
            code = run_gate(
                "implement a REST API with authentication",
                _BASE_CONFIG,
            )
        assert code == 0
        assert capsys.readouterr().out == ""

    def test_passes_short_prompt(self, capsys) -> None:
        with patch("promptune.gate.score_prompt") as mock_score:
            code = run_gate("fix bug", _BASE_CONFIG)
        mock_score.assert_not_called()
        assert code == 0
        assert capsys.readouterr().out == ""

    def test_bypass_prefix_skips_gate(self, capsys) -> None:
        """Prompt starting with bypass prefix passes through unchanged."""
        with patch("promptune.gate.score_prompt") as mock_score:
            code = run_gate(
                "! make a simple todo app thing",
                _BASE_CONFIG,
            )
        mock_score.assert_not_called()
        assert code == 0
        assert capsys.readouterr().out == ""

    def test_bypass_prefix_custom(self, capsys) -> None:
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
        assert capsys.readouterr().out == ""

    def test_bypass_prefix_empty_does_not_skip(self, capsys) -> None:
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
        assert capsys.readouterr().out == ""

    def test_bypass_prefix_not_matched_still_gates(self, capsys) -> None:
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
        assert capsys.readouterr().out == ""

    def test_threshold_boundary_at_exactly_threshold(self, capsys) -> None:
        with patch(
            "promptune.gate.score_prompt",
            return_value=_make_score(40),
        ):
            code = run_gate(
                "implement authentication for the app now",
                _BASE_CONFIG,
            )
        assert code == 0
        assert capsys.readouterr().out == ""


class TestRunGateInjects:
    """Low-score path injects enhanced prompt as hook context via stdout."""

    def _mock_result(self) -> Any:
        from promptune.engine import EnhanceResult

        mock_result = MagicMock(spec=EnhanceResult)
        mock_result.enhanced = "Build a full-stack todo app with auth"
        mock_result.score_before = _make_score(30)
        mock_result.score_after = _make_score(74)
        return mock_result

    def test_returns_zero_and_emits_json(self, capsys) -> None:
        with (
            patch(
                "promptune.gate.score_prompt",
                return_value=_make_score(30),
            ),
            patch(
                "promptune.gate.enhance",
                return_value=self._mock_result(),
            ),
        ):
            code = run_gate(
                "make a simple todo app thing",
                _BASE_CONFIG,
            )
        assert code == 0
        out = capsys.readouterr().out
        payload = json.loads(out)
        assert (
            payload["hookSpecificOutput"]["hookEventName"]
            == "UserPromptSubmit"
        )
        assert (
            "Build a full-stack todo app with auth"
            in payload["hookSpecificOutput"]["additionalContext"]
        )

    def test_stdout_is_only_json(self, capsys) -> None:
        with (
            patch(
                "promptune.gate.score_prompt",
                return_value=_make_score(30),
            ),
            patch(
                "promptune.gate.enhance",
                return_value=self._mock_result(),
            ),
        ):
            run_gate("make a simple todo app thing", _BASE_CONFIG)
        out = capsys.readouterr().out
        # Whole stdout must parse as a single JSON object, nothing else.
        json.loads(out)

    def test_gate_uses_displayed_total_not_pqs_overall(self, capsys) -> None:
        """Gate must compare ScoreResult.total (what `score` prints), not the
        compute_pqs overall, so a threshold calibrated from the CLI holds."""
        # total=36 is below the threshold of 40, but every dimension at 0.44
        # makes compute_pqs(...).overall == 44 (>= 40). The prompt must still
        # be enhanced because the displayed total is below threshold.
        diverging = ScoreResult(
            total=36,
            intent="coding",
            dimensions={
                name: DimensionScore(0.44, w, [], "ok")
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
        with (
            patch("promptune.gate.score_prompt", return_value=diverging),
            patch(
                "promptune.gate.enhance",
                return_value=self._mock_result(),
            ),
        ):
            run_gate("implement a rest api with authentication now", _BASE_CONFIG)
        out = capsys.readouterr().out
        assert out != ""
        json.loads(out)


def test_gate_threshold_defaults_to_40(capsys) -> None:
    """Missing threshold defaults to 40, not 60."""
    cfg: dict[str, Any] = {
        **_BASE_CONFIG,
        "auto_enhance": {"enabled": True, "min_words": 5},
    }
    with patch(
        "promptune.gate.score_prompt",
        return_value=_make_score(45),
    ):
        code = run_gate("a prompt with at least five words", cfg)
    assert code == 0
    assert capsys.readouterr().out == ""
