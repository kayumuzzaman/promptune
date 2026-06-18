"""MCP server for promptune — exposes enhance and score tools.

Start via: promptune mcp
AI tools (Claude Code, Codex, Cursor, etc.) launch this via stdio transport.
"""

from __future__ import annotations

import copy
from typing import Any

from promptune.config import load_config
from promptune.engine import enhance
from promptune.scorer import score_prompt


def _tool_enhance(
    prompt: str,
    style: str | None = None,
    tier: int | None = None,
) -> dict[str, Any]:
    """Enhance a prompt using the 3-tier engine."""
    cfg = copy.deepcopy(load_config())
    if style:
        cfg["enhancement"]["default_mode"] = style

    result = enhance(prompt, cfg, tier_override=tier)
    return {
        "original": result.original,
        "enhanced": result.enhanced,
        "score_before": result.score_before.total,
        "score_after": result.score_after.total,
        "tier_used": result.tier_used,
        "rules_applied": result.rules_applied,
        "rules_explained": [
            {"rule": name, "reason": desc}
            for name, desc in result.rules_explained
        ],
        "latency_ms": round(result.latency_ms, 1),
    }


def _tool_score(prompt: str) -> dict[str, Any]:
    """Score a prompt across 7 quality dimensions."""
    result = score_prompt(prompt)
    return {
        "total": result.total,
        "intent": result.intent,
        "dimensions": {
            name: {
                "score": round(dim.score, 3),
                "weight": dim.max_weight,
                "suggestion": dim.suggestion,
            }
            for name, dim in result.dimensions.items()
        },
    }


def run_server() -> None:
    """Start the MCP server on stdio transport."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as e:
        raise ImportError(
            "MCP support requires: pip install promptune[mcp]"
        ) from e

    mcp = FastMCP("promptune")

    @mcp.tool()
    def enhance_prompt(  # type: ignore[no-untyped-def]
        prompt: str,
        style: str = "balanced",
        tier: int = -1,
    ) -> dict[str, Any]:
        """Enhance a prompt using AI (3-tier: rules, local LLM, cloud).

        Args:
            prompt: The prompt text to enhance.
            style: Enhancement style: minimal, balanced, or detailed.
            tier: Force tier (-1=auto, 0=rules, 1=local, 2=cloud).
        """
        tier_override = tier if tier >= 0 else None
        # Pass the requested style through verbatim. Previously an explicit
        # style="balanced" was collapsed to None — indistinguishable from "not
        # set" — so a client asking for balanced silently got the configured
        # default_mode instead. "balanced" is the tool's documented default.
        return _tool_enhance(
            prompt,
            style=style,
            tier=tier_override,
        )

    @mcp.tool()
    def score_prompt_quality(  # type: ignore[no-untyped-def]
        prompt: str,
    ) -> dict[str, Any]:
        """Score a prompt across 7 quality dimensions (0-100).

        Returns total PQS score, detected intent, and per-dimension
        breakdown with actionable suggestions.

        Args:
            prompt: The prompt text to score.
        """
        return _tool_score(prompt)

    mcp.run(transport="stdio")
