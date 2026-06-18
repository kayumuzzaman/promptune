"""Auto-enhance gate: score -> enhance if needed -> silently inject.

Used as a UserPromptSubmit hook command by AI tools (Claude Code, Codex).
Reads a JSON payload from stdin: {"prompt": "..."}.

When a prompt scores below the configured threshold it is enhanced and the
result is injected as ``additionalContext`` via the hook's stdout contract.
The hook always exits 0 so the original prompt proceeds; the model sees the
enhanced version alongside it. stdout carries ONLY the hook JSON.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from promptune.engine import enhance
from promptune.scorer import score_prompt

_INJECT_PREFIX = (
    "[promptune] Your prompt was automatically refined for clarity and"
    " specificity. Treat the following as the actual request:\n\n"
)


def _emit_inject(text: str) -> None:
    """Write the UserPromptSubmit hook injection JSON to stdout only."""
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": text,
        }
    }
    sys.stdout.write(json.dumps(payload))


def run_gate(prompt: str, config: dict[str, Any]) -> int:
    """Score prompt and silently inject an enhanced version if below threshold.

    Always returns 0 (the prompt proceeds). On the low-score path the enhanced
    prompt is written to stdout as a UserPromptSubmit ``additionalContext``
    injection; all other paths return 0 with no stdout output.
    """
    auto_cfg = config.get("auto_enhance", {})

    if not auto_cfg.get("enabled", True):
        return 0

    bypass = auto_cfg.get("bypass_prefix", "!")
    if bypass and prompt.startswith(bypass):
        return 0

    words = prompt.split()
    if len(words) < auto_cfg.get("min_words", 5):
        return 0

    threshold = auto_cfg.get("threshold", 40)
    # Compare the same number `promptune score` prints as PQS (ScoreResult
    # .total), so a threshold calibrated from the CLI behaves as expected.
    score_before = score_prompt(prompt)

    if score_before.total >= threshold:
        return 0

    # This runs as a UserPromptSubmit hook: it must always exit 0 and never
    # pollute stdout on failure, so the user's prompt proceeds unaltered even
    # if enhancement raises (network error, malformed config, etc.).
    try:
        # record=False: the gate has no accept/reject surface, so recording
        # every auto-enhanced prompt as a confirmed "accept" would pollute
        # dedup and preference learning with unconfirmed outcomes.
        result = enhance(prompt, config, record=False)
    except Exception as exc:  # noqa: BLE001 — hook must never crash
        print(f"promptune: enhancement skipped ({exc})", file=sys.stderr)
        return 0

    _emit_inject(_INJECT_PREFIX + result.enhanced)
    print(
        f"promptune: enhanced {score_before.total}"
        f"->{result.score_after.total}",
        file=sys.stderr,
    )
    return 0
