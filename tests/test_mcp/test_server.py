"""Tests for MCP server tools."""

from __future__ import annotations

import sys
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from promptune.config import ConfigError
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


class TestMcpEnhanceTool:
    """enhance tool returns correct structure."""

    def test_enhance_returns_required_keys(self) -> None:
        from promptune.engine import EnhanceResult
        from promptune.mcp.server import _tool_enhance

        mock_result = MagicMock(spec=EnhanceResult)
        mock_result.original = "make a todo app"
        mock_result.enhanced = "Build a full-stack todo app..."
        mock_result.score_before = _make_score(38)
        mock_result.score_after = _make_score(74)
        mock_result.tier_used = 0
        mock_result.rules_applied = ["vague_verbs"]
        mock_result.rules_explained = [
            ("vague_verbs", "Replaced vague verbs with specific alternatives"),
        ]
        mock_result.latency_ms = 50.0

        with (
            patch(
                "promptune.mcp.server.load_config",
                return_value={},
            ),
            patch(
                "promptune.mcp.server.enhance",
                return_value=mock_result,
            ),
        ):
            result = _tool_enhance("make a todo app")

        assert result["original"] == "make a todo app"
        assert (
            result["enhanced"]
            == "Build a full-stack todo app..."
        )
        assert result["score_before"] == 38
        assert result["score_after"] == 74
        assert result["tier_used"] == 0
        assert result["rules_applied"] == ["vague_verbs"]
        assert "latency_ms" in result

    def test_enhance_passes_style_override(self) -> None:
        from promptune.engine import EnhanceResult
        from promptune.mcp.server import _tool_enhance

        mock_result = MagicMock(spec=EnhanceResult)
        mock_result.original = "make a todo app"
        mock_result.enhanced = "Build..."
        mock_result.score_before = _make_score(38)
        mock_result.score_after = _make_score(74)
        mock_result.tier_used = 0
        mock_result.rules_applied = []
        mock_result.rules_explained = []
        mock_result.latency_ms = 50.0

        mock_cfg: dict[str, Any] = {
            "enhancement": {"default_mode": "balanced"}
        }

        with (
            patch(
                "promptune.mcp.server.load_config",
                return_value=mock_cfg,
            ),
            patch(
                "promptune.mcp.server.enhance",
                return_value=mock_result,
            ) as mock_enhance,
        ):
            _tool_enhance(
                "make a todo app", style="detailed"
            )

        call_cfg = mock_enhance.call_args[0][1]
        assert (
            call_cfg["enhancement"]["default_mode"]
            == "detailed"
        )

    def test_enhance_rejects_invalid_style(self) -> None:
        from promptune.config import ConfigError
        from promptune.mcp.server import _tool_enhance

        mock_cfg: dict[str, Any] = {
            "enhancement": {"default_mode": "balanced"},
            "provider": {},
        }

        with (
            patch(
                "promptune.mcp.server.load_config",
                return_value=mock_cfg,
            ),
            patch("promptune.mcp.server.enhance") as mock_enhance,
            pytest.raises(ConfigError, match="Invalid mode"),
        ):
            _tool_enhance("prompt", style="detialed")

        mock_enhance.assert_not_called()

    def test_enhance_rejects_empty_style(self) -> None:
        from promptune.config import ConfigError
        from promptune.mcp.server import _tool_enhance

        mock_cfg: dict[str, Any] = {
            "enhancement": {"default_mode": "balanced"},
            "provider": {},
        }

        with (
            patch(
                "promptune.mcp.server.load_config",
                return_value=mock_cfg,
            ),
            patch("promptune.mcp.server.enhance") as mock_enhance,
            pytest.raises(ConfigError, match="Invalid mode"),
        ):
            _tool_enhance("prompt", style="")

        mock_enhance.assert_not_called()

    @pytest.mark.parametrize("tier", [True, 99, -2])
    def test_enhance_rejects_invalid_tier(self, tier: object) -> None:
        from promptune.config import ConfigError
        from promptune.mcp.server import _tool_enhance

        with (
            patch(
                "promptune.mcp.server.load_config",
                return_value={"enhancement": {"default_mode": "balanced"}},
            ),
            patch("promptune.mcp.server.enhance") as mock_enhance,
            pytest.raises(ConfigError, match="Invalid tier"),
        ):
            _tool_enhance("prompt", tier=tier)  # type: ignore[arg-type]

        mock_enhance.assert_not_called()


class TestMcpScoreTool:
    """score tool returns correct structure."""

    def test_score_returns_total_and_dimensions(
        self,
    ) -> None:
        from promptune.mcp.server import _tool_score

        with patch(
            "promptune.mcp.server.score_prompt",
            return_value=_make_score(42),
        ):
            result = _tool_score("make a todo app")

        assert result["total"] == 42
        assert result["intent"] == "coding"
        assert "dimensions" in result
        assert "specificity" in result["dimensions"]

    def test_score_dimension_has_required_fields(
        self,
    ) -> None:
        from promptune.mcp.server import _tool_score

        with patch(
            "promptune.mcp.server.score_prompt",
            return_value=_make_score(42),
        ):
            result = _tool_score("make a todo app")

        dim = result["dimensions"]["specificity"]
        assert "score" in dim
        assert "weight" in dim
        assert "suggestion" in dim


class TestRunServer:
    """run_server entry point — covers lines 65-112."""

    def test_raises_clear_error_when_mcp_not_installed(
        self, monkeypatch
    ) -> None:
        """Missing `mcp` dep raises ImportError with install hint."""
        from promptune.mcp import server as mcp_server

        # Simulate `import mcp.server.fastmcp` failing
        for mod in list(sys.modules):
            if mod.startswith("mcp"):
                monkeypatch.delitem(sys.modules, mod, raising=False)
        monkeypatch.setitem(sys.modules, "mcp", None)

        with pytest.raises(ImportError, match="promptune\\[mcp\\]"):
            mcp_server.run_server()

    def test_starts_fastmcp_with_stdio_transport(self) -> None:
        """run_server registers tools and starts FastMCP on stdio."""
        from promptune.mcp import server as mcp_server

        mock_fastmcp_class = MagicMock()
        mock_fastmcp_instance = MagicMock()
        mock_fastmcp_class.return_value = mock_fastmcp_instance
        # tool() returns a decorator that returns the function unchanged
        mock_fastmcp_instance.tool.return_value = lambda fn: fn

        fake_module = MagicMock()
        fake_module.FastMCP = mock_fastmcp_class

        with patch.dict(
            sys.modules,
            {
                "mcp": MagicMock(),
                "mcp.server": MagicMock(),
                "mcp.server.fastmcp": fake_module,
            },
        ):
            mcp_server.run_server()

        mock_fastmcp_class.assert_called_once_with("promptune")
        mock_fastmcp_instance.run.assert_called_once_with(transport="stdio")
        # Both tools should have been registered (decorator called twice)
        assert mock_fastmcp_instance.tool.call_count == 2

    def test_registered_enhance_tool_delegates_to_tool_enhance(
        self,
    ) -> None:
        """The enhance_prompt MCP tool delegates to _tool_enhance."""
        from promptune.mcp import server as mcp_server

        registered: dict[str, Any] = {}

        def fake_tool_decorator() -> Any:
            def wrapper(fn: Any) -> Any:
                registered[fn.__name__] = fn
                return fn

            return wrapper

        mock_fastmcp_class = MagicMock()
        mock_fastmcp_instance = MagicMock()
        mock_fastmcp_class.return_value = mock_fastmcp_instance
        mock_fastmcp_instance.tool.side_effect = fake_tool_decorator

        fake_module = MagicMock()
        fake_module.FastMCP = mock_fastmcp_class

        with patch.dict(
            sys.modules,
            {
                "mcp": MagicMock(),
                "mcp.server": MagicMock(),
                "mcp.server.fastmcp": fake_module,
            },
        ), patch(
            "promptune.mcp.server._tool_enhance",
            return_value={"enhanced": "ok"},
        ) as mock_enhance:
            mcp_server.run_server()
            # enhance_prompt tool should now be registered
            assert "enhance_prompt" in registered
            result = registered["enhance_prompt"](
                "prompt", style="detailed", tier=2
            )

        assert result == {"enhanced": "ok"}
        mock_enhance.assert_called_once_with(
            "prompt", style="detailed", tier=2
        )

    def test_registered_enhance_tool_auto_tier_passes_none(
        self,
    ) -> None:
        """When tier=-1 (auto), tier_override should be None."""
        from promptune.mcp import server as mcp_server

        registered: dict[str, Any] = {}

        def fake_tool_decorator() -> Any:
            def wrapper(fn: Any) -> Any:
                registered[fn.__name__] = fn
                return fn

            return wrapper

        mock_fastmcp_class = MagicMock()
        mock_fastmcp_instance = MagicMock()
        mock_fastmcp_class.return_value = mock_fastmcp_instance
        mock_fastmcp_instance.tool.side_effect = fake_tool_decorator

        fake_module = MagicMock()
        fake_module.FastMCP = mock_fastmcp_class

        with patch.dict(
            sys.modules,
            {
                "mcp": MagicMock(),
                "mcp.server": MagicMock(),
                "mcp.server.fastmcp": fake_module,
            },
        ), patch(
            "promptune.mcp.server._tool_enhance",
            return_value={},
        ) as mock_enhance:
            mcp_server.run_server()
            registered["enhance_prompt"](
                "prompt", style="balanced", tier=-1
            )

        # tier=-1 → None; style passes through verbatim (an explicit "balanced"
        # must not be collapsed to None/config default).
        mock_enhance.assert_called_once_with(
            "prompt", style="balanced", tier=None
        )

    def test_registered_enhance_tool_rejects_invalid_negative_tier(
        self,
    ) -> None:
        """Only tier=-1 can request auto mode."""
        from promptune.mcp import server as mcp_server

        registered: dict[str, Any] = {}

        def fake_tool_decorator() -> Any:
            def wrapper(fn: Any) -> Any:
                registered[fn.__name__] = fn
                return fn

            return wrapper

        mock_fastmcp_class = MagicMock()
        mock_fastmcp_instance = MagicMock()
        mock_fastmcp_class.return_value = mock_fastmcp_instance
        mock_fastmcp_instance.tool.side_effect = fake_tool_decorator

        fake_module = MagicMock()
        fake_module.FastMCP = mock_fastmcp_class

        with patch.dict(
            sys.modules,
            {
                "mcp": MagicMock(),
                "mcp.server": MagicMock(),
                "mcp.server.fastmcp": fake_module,
            },
        ), patch(
            "promptune.mcp.server._tool_enhance",
            return_value={},
        ) as mock_enhance:
            mcp_server.run_server()
            with pytest.raises(ConfigError, match="Invalid tier"):
                registered["enhance_prompt"](
                    "prompt", style="balanced", tier=-2
                )

        mock_enhance.assert_not_called()

    def test_registered_enhance_tool_passes_style_through(
        self,
    ) -> None:
        """An explicit style must reach _tool_enhance unchanged."""
        from promptune.mcp import server as mcp_server

        registered: dict[str, Any] = {}

        def fake_tool_decorator() -> Any:
            def wrapper(fn: Any) -> Any:
                registered[fn.__name__] = fn
                return fn

            return wrapper

        mock_fastmcp_class = MagicMock()
        mock_fastmcp_instance = MagicMock()
        mock_fastmcp_class.return_value = mock_fastmcp_instance
        mock_fastmcp_instance.tool.side_effect = fake_tool_decorator

        fake_module = MagicMock()
        fake_module.FastMCP = mock_fastmcp_class

        with patch.dict(
            sys.modules,
            {
                "mcp": MagicMock(),
                "mcp.server": MagicMock(),
                "mcp.server.fastmcp": fake_module,
            },
        ), patch(
            "promptune.mcp.server._tool_enhance",
            return_value={},
        ) as mock_enhance:
            mcp_server.run_server()
            registered["enhance_prompt"](
                "prompt", style="detailed", tier=2
            )

        mock_enhance.assert_called_once_with(
            "prompt", style="detailed", tier=2
        )

    def test_registered_score_tool_delegates_to_tool_score(
        self,
    ) -> None:
        """The score_prompt_quality MCP tool delegates to _tool_score."""
        from promptune.mcp import server as mcp_server

        registered: dict[str, Any] = {}

        def fake_tool_decorator() -> Any:
            def wrapper(fn: Any) -> Any:
                registered[fn.__name__] = fn
                return fn

            return wrapper

        mock_fastmcp_class = MagicMock()
        mock_fastmcp_instance = MagicMock()
        mock_fastmcp_class.return_value = mock_fastmcp_instance
        mock_fastmcp_instance.tool.side_effect = fake_tool_decorator

        fake_module = MagicMock()
        fake_module.FastMCP = mock_fastmcp_class

        with patch.dict(
            sys.modules,
            {
                "mcp": MagicMock(),
                "mcp.server": MagicMock(),
                "mcp.server.fastmcp": fake_module,
            },
        ), patch(
            "promptune.mcp.server._tool_score",
            return_value={"total": 70},
        ) as mock_score:
            mcp_server.run_server()
            assert "score_prompt_quality" in registered
            result = registered["score_prompt_quality"]("a prompt")

        assert result == {"total": 70}
        mock_score.assert_called_once_with("a prompt")
