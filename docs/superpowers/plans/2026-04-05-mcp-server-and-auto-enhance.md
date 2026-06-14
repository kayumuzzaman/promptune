# MCP Server & Auto-Enhance Implementation Plan

**Status:** Completed 2026-04-05

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an MCP server exposing `enhance` and `score` tools (works in any MCP-compatible AI tool), plus an auto-enhance hook that silently scores prompts and intercepts low-quality ones before they reach the AI.

**Architecture:** An MCP server (`promptune/mcp/server.py`) using FastMCP wraps the existing `engine.enhance()` and `scorer.score_prompt()` with zero duplication. A gate module (`promptune/gate.py`) reads prompts from stdin (Claude Code hook JSON), scores them, and enhances + copies to clipboard when below threshold. A hooks module (`promptune/hooks/`) handles tool detection and hook config installation, wired into `config init` and `doctor`.

**Tech Stack:** Python 3.9+, `mcp>=1.0` (optional dep), Click, existing promptune engine/scorer, subprocess for clipboard (pbcopy/xclip/wl-copy).

---

## File Map

### New Files
- `promptune/mcp/__init__.py` — package marker
- `promptune/mcp/server.py` — FastMCP server, `enhance` + `score` tools
- `promptune/gate.py` — gate logic: read stdin JSON, score, enhance, copy, exit code
- `promptune/hooks/__init__.py` — `HookInstaller` protocol, `get_installers()`, `detect_tools()`
- `promptune/hooks/claude_code.py` — `ClaudeCodeInstaller`: detect, install, uninstall, is_installed
- `tests/test_gate.py` — gate unit tests
- `tests/test_hooks/__init__.py` — package marker
- `tests/test_hooks/test_claude_code.py` — hook installer tests
- `tests/test_mcp/__init__.py` — package marker
- `tests/test_mcp/test_server.py` — MCP server tool tests

### Modified Files
- `promptune/config.py` — add `auto_enhance` section to `DEFAULT_CONFIG`
- `promptune/cli.py` — add `score`, `gate`, `mcp` commands; update `doctor` checks
- `promptune/setup.py` — add `_prompt_auto_enhance_settings()`, wire into `run_interactive_setup()`
- `tests/test_setup.py` — tests for auto-enhance setup step
- `tests/test_cli.py` — tests for `score`, `mcp` CLI commands and doctor auto-enhance checks
- `pyproject.toml` — add `mcp` optional dependency group, mypy override for `mcp`

---

## Task 1: Add `[auto_enhance]` to Config

**Files:**
- Modify: `promptune/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_config.py` in the existing `TestDefaultConfig` class (or create a new class):

```python
class TestAutoEnhanceDefaults:
    """auto_enhance section in DEFAULT_CONFIG."""

    def test_auto_enhance_section_exists(self) -> None:
        from promptune.config import DEFAULT_CONFIG
        assert "auto_enhance" in DEFAULT_CONFIG

    def test_auto_enhance_defaults(self) -> None:
        from promptune.config import DEFAULT_CONFIG
        ae = DEFAULT_CONFIG["auto_enhance"]
        assert ae["enabled"] is True
        assert ae["threshold"] == 60
        assert ae["min_words"] == 5

    def test_load_config_includes_auto_enhance(
        self, tmp_path: Path
    ) -> None:
        config_path = tmp_path / "config.toml"
        cfg = load_config(config_path=config_path)
        assert "auto_enhance" in cfg
        assert cfg["auto_enhance"]["threshold"] == 60
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/test_config.py::TestAutoEnhanceDefaults -v
```

Expected: FAIL — `KeyError: 'auto_enhance'`

- [ ] **Step 3: Add `auto_enhance` to DEFAULT_CONFIG in `promptune/config.py`**

In `promptune/config.py`, after the `"daemon"` section in `DEFAULT_CONFIG`, add:

```python
    "auto_enhance": {
        "enabled": True,
        "threshold": 60,
        "min_words": 5,
    },
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python3 -m pytest tests/test_config.py::TestAutoEnhanceDefaults -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add promptune/config.py tests/test_config.py
git commit -m "feat: add auto_enhance section to DEFAULT_CONFIG"
```

---

## Task 2: `promptune score` Command

**Files:**
- Modify: `promptune/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_cli.py`:

```python
class TestScoreCommand:
    """promptune score command."""

    def test_score_prints_total(self, mocker) -> None:
        mocker.patch(
            "promptune.cli.score_prompt",
            return_value=ScoreResult(
                total=42,
                intent="coding",
                dimensions={
                    "specificity": DimensionScore(0.3, 25.0, [], "Add more"),
                    "clarity": DimensionScore(0.5, 20.0, [], "Good clarity"),
                    "structure": DimensionScore(0.2, 15.0, [], "Add structure"),
                    "actionability": DimensionScore(0.4, 15.0, [], "Good"),
                    "context": DimensionScore(0.1, 10.0, [], "Add context"),
                    "completeness": DimensionScore(0.1, 10.0, [], "Add output format"),
                    "conciseness": DimensionScore(0.7, 5.0, [], "Good conciseness"),
                },
            ),
        )
        runner = CliRunner()
        result = runner.invoke(main, ["score", "make a todo app"])
        assert result.exit_code == 0
        assert "42" in result.output

    def test_score_json_output(self, mocker) -> None:
        mocker.patch(
            "promptune.cli.score_prompt",
            return_value=ScoreResult(
                total=42,
                intent="coding",
                dimensions={
                    "specificity": DimensionScore(0.3, 25.0, [], "Add more"),
                    "clarity": DimensionScore(0.5, 20.0, [], "Good"),
                    "structure": DimensionScore(0.2, 15.0, [], "Add structure"),
                    "actionability": DimensionScore(0.4, 15.0, [], "Good"),
                    "context": DimensionScore(0.1, 10.0, [], "Add context"),
                    "completeness": DimensionScore(0.1, 10.0, [], "Add format"),
                    "conciseness": DimensionScore(0.7, 5.0, [], "Good"),
                },
            ),
        )
        runner = CliRunner()
        result = runner.invoke(main, ["score", "--json", "make a todo app"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["total"] == 42
        assert data["intent"] == "coding"
        assert "dimensions" in data

    def test_score_empty_prompt_exits_1(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["score"])
        assert result.exit_code == 1
```

You need these imports at the top of `tests/test_cli.py` (add if missing):
```python
import json
from promptune.scorer import DimensionScore, ScoreResult
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_cli.py::TestScoreCommand -v
```

Expected: FAIL — `No such command 'score'`

- [ ] **Step 3: Add `score` command to `promptune/cli.py`**

Add this import near the top of `promptune/cli.py`:
```python
from promptune.scorer import score_prompt
```

Add this command after the `enhance_cmd` function:

```python
@main.command("score")
@click.argument("prompt", required=False)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Output structured JSON.",
)
def score_cmd(prompt: str | None, json_output: bool) -> None:
    """Score a prompt across 7 quality dimensions."""
    if not prompt:
        prompt = (
            sys.stdin.read().strip()
            if not sys.stdin.isatty()
            else ""
        )
    if not prompt:
        click.echo("Error: Empty prompt.", err=True)
        raise SystemExit(1)

    result = score_prompt(prompt)

    if json_output:
        output = {
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
        click.echo(json_mod.dumps(output, indent=2))
        return

    click.echo(f"  PQS: {result.total}/100  [{result.intent}]")
    click.echo()
    for name, dim in result.dimensions.items():
        pct = int(dim.score * 100)
        click.echo(f"  {name:<16} {pct:>3}%  — {dim.suggestion}")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_cli.py::TestScoreCommand -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add promptune/cli.py tests/test_cli.py
git commit -m "feat: add promptune score command"
```

---

## Task 3: Gate Logic (`promptune/gate.py`)

The gate reads a JSON payload from stdin (Claude Code hook format: `{"prompt": "..."}` ), scores the prompt, and if below threshold: enhances it, copies to clipboard, prints the auto-enhance block to stderr, exits 1. Otherwise exits 0.

**Files:**
- Create: `promptune/gate.py`
- Create: `tests/test_gate.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_gate.py`:

```python
"""Tests for the auto-enhance gate."""

from __future__ import annotations

import json
import subprocess
import sys
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from promptune.gate import copy_to_clipboard, run_gate
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
    "auto_enhance": {"enabled": True, "threshold": 60, "min_words": 5},
    "provider": {"default": "claude", "format_style": "auto",
                 "model_claude": "claude-haiku-4-5-20251001",
                 "model_openai": "gpt-4o-mini",
                 "model_openrouter": "anthropic/claude-haiku"},
    "api_keys": {"claude": "", "openai": "", "openrouter": ""},
    "enhancement": {"max_tier": 0, "default_mode": "balanced",
                    "max_tokens_output": 400, "timeout_seconds": 10,
                    "dedup_enabled": False, "dedup_threshold": 0.85,
                    "dedup_window": 50, "preference_learning": False,
                    "preference_min_samples": 5},
    "local_llm": {"enabled": False, "host": "http://localhost:11434",
                  "model": "qwen2.5:3b", "api_key": ""},
    "context": {"use_git": False, "use_shell_history": False,
                "use_stack_detection": False, "max_context_tokens": 500,
                "shell_history_lines": 20},
    "history": {"enabled": False, "max_entries": 10000,
                "db_path": "/tmp/test_history.db"},
}


class TestRunGate:
    """Gate exit codes and behavior."""

    def test_passes_when_disabled(self) -> None:
        cfg = {**_BASE_CONFIG, "auto_enhance": {"enabled": False, "threshold": 60, "min_words": 5}}
        with patch("promptune.gate.score_prompt", return_value=_make_score(30)):
            code = run_gate("short prompt here that is low quality", cfg)
        assert code == 0

    def test_passes_high_score(self) -> None:
        with patch("promptune.gate.score_prompt", return_value=_make_score(75)):
            code = run_gate("implement a REST API with authentication", _BASE_CONFIG)
        assert code == 0

    def test_passes_short_prompt(self) -> None:
        # 3 words < min_words=5
        with patch("promptune.gate.score_prompt") as mock_score:
            code = run_gate("fix bug", _BASE_CONFIG)
        mock_score.assert_not_called()
        assert code == 0

    def test_blocks_low_score(self) -> None:
        from promptune.engine import EnhanceResult
        mock_result = MagicMock(spec=EnhanceResult)
        mock_result.enhanced = "Build a full-stack todo application..."
        mock_result.score_before = _make_score(30)
        mock_result.score_after = _make_score(74)

        with (
            patch("promptune.gate.score_prompt", return_value=_make_score(30)),
            patch("promptune.gate.enhance", return_value=mock_result),
            patch("promptune.gate.copy_to_clipboard"),
            patch("promptune.gate._print_gate_block"),
        ):
            code = run_gate("make a simple todo app thing", _BASE_CONFIG)
        assert code == 1

    def test_copies_enhanced_to_clipboard_on_block(self) -> None:
        from promptune.engine import EnhanceResult
        mock_result = MagicMock(spec=EnhanceResult)
        mock_result.enhanced = "Build a full-stack todo application..."
        mock_result.score_before = _make_score(30)
        mock_result.score_after = _make_score(74)

        with (
            patch("promptune.gate.score_prompt", return_value=_make_score(30)),
            patch("promptune.gate.enhance", return_value=mock_result),
            patch("promptune.gate.copy_to_clipboard") as mock_copy,
            patch("promptune.gate._print_gate_block"),
        ):
            run_gate("make a simple todo app thing", _BASE_CONFIG)
        mock_copy.assert_called_once_with("Build a full-stack todo application...")

    def test_threshold_boundary_at_exactly_60(self) -> None:
        with patch("promptune.gate.score_prompt", return_value=_make_score(60)):
            code = run_gate("implement authentication for the app now", _BASE_CONFIG)
        assert code == 0  # exactly at threshold passes


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

    def test_linux_falls_back_to_xclip(self, mocker) -> None:
        mocker.patch("sys.platform", "linux")
        mock_run = mocker.patch(
            "subprocess.run",
            side_effect=[
                subprocess.CalledProcessError(1, "wl-copy"),
                MagicMock(),
            ],
        )
        copy_to_clipboard("hello world")
        second_call = mock_run.call_args_list[1]
        assert "xclip" in second_call[0][0]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_gate.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'promptune.gate'`

- [ ] **Step 3: Create `promptune/gate.py`**

```python
"""Auto-enhance gate: score → enhance if needed → clipboard → exit code.

Used as a hook command by AI tools (Claude Code, etc.).
Reads a JSON payload from stdin: {"prompt": "..."}.
Exits 0 to allow, 1 to block (showing enhanced version).
"""

from __future__ import annotations

import subprocess
import sys
from typing import Any

from promptune.engine import EnhanceResult, enhance
from promptune.scorer import ScoreResult, score_prompt


def copy_to_clipboard(text: str) -> None:
    """Copy text to system clipboard using platform-appropriate tool."""
    if sys.platform == "darwin":
        subprocess.run(["pbcopy"], input=text, text=True, check=True)
    else:
        try:
            subprocess.run(
                ["wl-copy"], input=text, text=True, check=True
            )
        except (FileNotFoundError, subprocess.CalledProcessError):
            subprocess.run(
                ["xclip", "-selection", "clipboard"],
                input=text,
                text=True,
                check=True,
            )


def _print_gate_block(
    original: str,
    result: EnhanceResult,
    score_before: ScoreResult,
) -> None:
    """Print the auto-enhance block to stderr."""
    width = 48
    border = "─" * width
    print(f"\n┌─ Auto-enhance {border[:width - 16]}┐", file=sys.stderr)
    print(f"│", file=sys.stderr)
    print(
        f"│  Your prompt scored {score_before.total}/100.",
        file=sys.stderr,
    )
    print(
        f"│  Enhanced version (copied to clipboard):",
        file=sys.stderr,
    )
    print(f"│", file=sys.stderr)
    for line in result.enhanced.splitlines():
        chunk = line[:width - 4]
        print(f"│  {chunk}", file=sys.stderr)
    print(f"│", file=sys.stderr)
    print(
        f"│  Score: {score_before.total} → {result.score_after.total}",
        file=sys.stderr,
    )
    print(f"│", file=sys.stderr)
    print(
        f"│  [Paste] to use · [Retype] to use original",
        file=sys.stderr,
    )
    print(f"└{'─' * (width + 2)}┘\n", file=sys.stderr)


def run_gate(prompt: str, config: dict[str, Any]) -> int:
    """Score prompt and enhance if below threshold.

    Returns 0 (allow) or 1 (block with enhanced copy on clipboard).
    """
    auto_cfg = config.get("auto_enhance", {})

    if not auto_cfg.get("enabled", True):
        return 0

    words = prompt.split()
    if len(words) < auto_cfg.get("min_words", 5):
        return 0

    threshold = auto_cfg.get("threshold", 60)
    score_before = score_prompt(prompt)

    if score_before.total >= threshold:
        return 0

    result = enhance(prompt, config)
    copy_to_clipboard(result.enhanced)
    _print_gate_block(prompt, result, score_before)
    return 1
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_gate.py -v
```

Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add promptune/gate.py tests/test_gate.py
git commit -m "feat: add gate module for auto-enhance hook"
```

---

## Task 4: Hook Detection + Claude Code Installer

**Files:**
- Create: `promptune/hooks/__init__.py`
- Create: `promptune/hooks/claude_code.py`
- Create: `tests/test_hooks/__init__.py`
- Create: `tests/test_hooks/test_claude_code.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_hooks/__init__.py` (empty).

Create `tests/test_hooks/test_claude_code.py`:

```python
"""Tests for Claude Code hook installer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from promptune.hooks.claude_code import (
    HOOK_COMMAND,
    ClaudeCodeInstaller,
)
from promptune.hooks import detect_tools, get_installers


class TestClaudeCodeDetect:
    """Detection of Claude Code installation."""

    def test_detects_when_claude_dir_exists(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        monkeypatch.setattr(
            "promptune.hooks.claude_code.CLAUDE_DIR",
            claude_dir,
        )
        installer = ClaudeCodeInstaller()
        assert installer.detect() is True

    def test_not_detected_when_no_claude_dir(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        monkeypatch.setattr(
            "promptune.hooks.claude_code.CLAUDE_DIR",
            tmp_path / ".claude_nonexistent",
        )
        installer = ClaudeCodeInstaller()
        assert installer.detect() is False


class TestClaudeCodeInstall:
    """Hook install/uninstall in settings.json."""

    def test_install_creates_settings_with_hook(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        settings_path = tmp_path / "settings.json"
        monkeypatch.setattr(
            "promptune.hooks.claude_code.SETTINGS_PATH",
            settings_path,
        )
        installer = ClaudeCodeInstaller()
        installer.install()
        assert settings_path.exists()
        data = json.loads(settings_path.read_text())
        hooks = data["hooks"]["UserPromptSubmit"]
        commands = [h["command"] for entry in hooks for h in entry["hooks"]]
        assert any(HOOK_COMMAND in cmd for cmd in commands)

    def test_install_merges_with_existing_settings(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        settings_path = tmp_path / "settings.json"
        settings_path.write_text(
            json.dumps({"theme": "dark", "hooks": {}})
        )
        monkeypatch.setattr(
            "promptune.hooks.claude_code.SETTINGS_PATH",
            settings_path,
        )
        installer = ClaudeCodeInstaller()
        installer.install()
        data = json.loads(settings_path.read_text())
        assert data["theme"] == "dark"
        assert "UserPromptSubmit" in data["hooks"]

    def test_is_installed_returns_true_after_install(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        settings_path = tmp_path / "settings.json"
        monkeypatch.setattr(
            "promptune.hooks.claude_code.SETTINGS_PATH",
            settings_path,
        )
        installer = ClaudeCodeInstaller()
        assert installer.is_installed() is False
        installer.install()
        assert installer.is_installed() is True

    def test_uninstall_removes_hook(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        settings_path = tmp_path / "settings.json"
        monkeypatch.setattr(
            "promptune.hooks.claude_code.SETTINGS_PATH",
            settings_path,
        )
        installer = ClaudeCodeInstaller()
        installer.install()
        assert installer.is_installed() is True
        installer.uninstall()
        assert installer.is_installed() is False

    def test_install_idempotent(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        settings_path = tmp_path / "settings.json"
        monkeypatch.setattr(
            "promptune.hooks.claude_code.SETTINGS_PATH",
            settings_path,
        )
        installer = ClaudeCodeInstaller()
        installer.install()
        installer.install()
        data = json.loads(settings_path.read_text())
        hooks = data["hooks"]["UserPromptSubmit"]
        commands = [h["command"] for entry in hooks for h in entry["hooks"]]
        # Only one copy of the command
        matching = [cmd for cmd in commands if HOOK_COMMAND in cmd]
        assert len(matching) == 1


class TestGetInstallers:
    """Installer registry."""

    def test_get_installers_returns_list(self) -> None:
        installers = get_installers()
        assert isinstance(installers, list)
        assert len(installers) >= 1

    def test_installer_has_name(self) -> None:
        for installer in get_installers():
            assert hasattr(installer, "name")
            assert isinstance(installer.name, str)

    def test_detect_tools_returns_only_detected(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        monkeypatch.setattr(
            "promptune.hooks.claude_code.CLAUDE_DIR",
            tmp_path / ".claude_nonexistent",
        )
        found = detect_tools()
        names = [i.name for i in found]
        assert "Claude Code" not in names
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_hooks/ -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'promptune.hooks'`

- [ ] **Step 3: Create `promptune/hooks/__init__.py`**

```python
"""Hook detection and installer registry for AI coding tools."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class HookInstaller(Protocol):
    """Protocol for tool-specific hook installers."""

    name: str

    def detect(self) -> bool:
        """Return True if the tool is installed on this machine."""
        ...

    def install(self) -> None:
        """Install the promptune gate hook into the tool's config."""
        ...

    def uninstall(self) -> None:
        """Remove the promptune gate hook from the tool's config."""
        ...

    def is_installed(self) -> bool:
        """Return True if the hook is currently installed."""
        ...


def get_installers() -> list[HookInstaller]:
    """Return all known hook installers."""
    from promptune.hooks.claude_code import ClaudeCodeInstaller

    return [ClaudeCodeInstaller()]


def detect_tools() -> list[HookInstaller]:
    """Return installers for tools detected on this machine."""
    return [i for i in get_installers() if i.detect()]
```

- [ ] **Step 4: Create `promptune/hooks/claude_code.py`**

```python
"""Claude Code hook installer.

Installs a UserPromptSubmit hook in ~/.claude/settings.json that
pipes every prompt through `promptune gate`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CLAUDE_DIR = Path.home() / ".claude"
SETTINGS_PATH = CLAUDE_DIR / "settings.json"
HOOK_COMMAND = "promptune gate"


def _load_settings() -> dict[str, Any]:
    """Load settings.json or return empty dict."""
    if SETTINGS_PATH.exists():
        try:
            return json.loads(SETTINGS_PATH.read_text())  # type: ignore[no-any-return]
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_settings(data: dict[str, Any]) -> None:
    """Write settings.json, creating parent dirs if needed."""
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(json.dumps(data, indent=2))


class ClaudeCodeInstaller:
    """Hook installer for Claude Code."""

    name = "Claude Code"

    def detect(self) -> bool:
        """Return True if ~/.claude/ directory exists."""
        return CLAUDE_DIR.exists()

    def install(self) -> None:
        """Add UserPromptSubmit hook to ~/.claude/settings.json."""
        if self.is_installed():
            return

        data = _load_settings()
        data.setdefault("hooks", {})
        data["hooks"].setdefault("UserPromptSubmit", [])

        hook_entry = {
            "matcher": "",
            "hooks": [{"type": "command", "command": HOOK_COMMAND}],
        }
        data["hooks"]["UserPromptSubmit"].append(hook_entry)
        _save_settings(data)

    def uninstall(self) -> None:
        """Remove promptune UserPromptSubmit hook from settings.json."""
        data = _load_settings()
        entries = data.get("hooks", {}).get("UserPromptSubmit", [])
        data["hooks"]["UserPromptSubmit"] = [
            entry
            for entry in entries
            if not any(
                HOOK_COMMAND in h.get("command", "")
                for h in entry.get("hooks", [])
            )
        ]
        _save_settings(data)

    def is_installed(self) -> bool:
        """Return True if promptune hook is in settings.json."""
        data = _load_settings()
        entries = data.get("hooks", {}).get("UserPromptSubmit", [])
        return any(
            HOOK_COMMAND in h.get("command", "")
            for entry in entries
            for h in entry.get("hooks", [])
        )
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_hooks/ -v
```

Expected: all passed

- [ ] **Step 6: Commit**

```bash
git add promptune/hooks/__init__.py promptune/hooks/claude_code.py \
        tests/test_hooks/__init__.py tests/test_hooks/test_claude_code.py
git commit -m "feat: add hook detection and Claude Code installer"
```

---

## Task 5: Setup Wizard — Auto-Enhance Step

**Files:**
- Modify: `promptune/setup.py`
- Modify: `tests/test_setup.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_setup.py`, updating the import:

```python
from promptune.setup import (
    KEY_PREFIXES,
    _prompt_api_key,
    _prompt_auto_enhance_settings,
    _prompt_local_llm_settings,
    _prompt_model,
    _prompt_optional_settings,
    _prompt_provider,
    mask_key,
    run_interactive_setup,
    validate_key_format,
    write_config,
)
```

Add new test class:

```python
class TestPromptAutoEnhanceSettings:
    """Auto-enhance step in setup wizard."""

    def test_skips_when_no_tools_detected(self) -> None:
        with patch(
            "promptune.setup.detect_tools", return_value=[]
        ):
            result = _prompt_auto_enhance_settings()
        assert result is None

    def test_returns_none_when_declined(self) -> None:
        mock_installer = MagicMock()
        mock_installer.name = "Claude Code"
        with (
            patch(
                "promptune.setup.detect_tools",
                return_value=[mock_installer],
            ),
            patch("click.confirm", return_value=False),
            patch("click.echo"),
        ):
            result = _prompt_auto_enhance_settings()
        assert result is None

    def test_installs_hooks_when_accepted(self) -> None:
        mock_installer = MagicMock()
        mock_installer.name = "Claude Code"
        with (
            patch(
                "promptune.setup.detect_tools",
                return_value=[mock_installer],
            ),
            patch("click.confirm", return_value=True),
            patch("click.echo"),
        ):
            result = _prompt_auto_enhance_settings()
        mock_installer.install.assert_called_once()
        assert result == {"enabled": True}

    def test_installs_all_detected_tools(self) -> None:
        mock1 = MagicMock()
        mock1.name = "Claude Code"
        mock2 = MagicMock()
        mock2.name = "Gemini CLI"
        with (
            patch(
                "promptune.setup.detect_tools",
                return_value=[mock1, mock2],
            ),
            patch("click.confirm", return_value=True),
            patch("click.echo"),
        ):
            _prompt_auto_enhance_settings()
        mock1.install.assert_called_once()
        mock2.install.assert_called_once()
```

Also add this import at the top of `tests/test_setup.py`:
```python
from unittest.mock import MagicMock
```

And update `test_first_time_setup` in `TestRunInteractiveSetup` — the wizard now calls `detect_tools` so we need to patch it:

```python
def test_first_time_setup(
    self, tmp_path: Path, mock_registry: ProviderRegistry
) -> None:
    config_path = tmp_path / "config.toml"
    with (
        patch(
            "click.prompt",
            side_effect=["claude", "sk-ant-test123", "claude-haiku-4-5-20251001"],
        ),
        patch("click.confirm", return_value=False),
        patch("click.echo"),
        patch("promptune.setup.detect_tools", return_value=[]),
    ):
        result = run_interactive_setup(config_path, mock_registry)
    assert result["provider"]["default"] == "claude"
    assert result["api_keys"]["claude"] == "sk-ant-test123"
    assert result["provider"]["model_claude"] == "claude-haiku-4-5-20251001"
```

Apply the same `patch("promptune.setup.detect_tools", return_value=[])` to all other `TestRunInteractiveSetup` tests that do not test the auto-enhance step specifically.

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_setup.py::TestPromptAutoEnhanceSettings -v
```

Expected: FAIL — `cannot import name '_prompt_auto_enhance_settings'`

- [ ] **Step 3: Add `_prompt_auto_enhance_settings` to `promptune/setup.py`**

Add this import near the top of `promptune/setup.py`:
```python
from promptune.hooks import detect_tools
```

Add this function before `run_interactive_setup`:

```python
def _prompt_auto_enhance_settings() -> dict[str, Any] | None:
    """Detect AI tools and offer auto-enhance hook installation.

    Returns {"enabled": True} if accepted, None if skipped or no tools found.
    """
    found = detect_tools()
    if not found:
        return None

    names = ", ".join(i.name for i in found)
    click.echo(f"  Found: {names}")

    if not click.confirm(
        "  Auto-enhance prompts in these tools?",
        default=True,
    ):
        return None

    for installer in found:
        installer.install()
        click.echo(f"  \u2713 Hook installed for {installer.name}")

    return {"enabled": True}
```

Then in `run_interactive_setup`, after the local LLM block and before building the config, add:

```python
    # Auto-enhance — detect AI tools and offer hook installation
    click.echo()
    auto_enhance_settings = _prompt_auto_enhance_settings()
```

And in the "Build complete config" block, add:

```python
    if auto_enhance_settings is not None:
        config["auto_enhance"].update(auto_enhance_settings)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_setup.py -v
```

Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add promptune/setup.py tests/test_setup.py
git commit -m "feat: add auto-enhance step to config init wizard"
```

---

## Task 6: Doctor Integration for Auto-Enhance

**Files:**
- Modify: `promptune/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_cli.py`:

```python
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
        # Undetected tools show as not detected
        assert "Codex" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_cli.py::TestDoctorAutoEnhance -v
```

Expected: FAIL — doctor doesn't show auto-enhance lines yet

- [ ] **Step 3: Update `doctor_cmd` in `promptune/cli.py`**

Add this import near the top of `promptune/cli.py`:
```python
from promptune.hooks import get_installers
```

Update `doctor_cmd` to add auto-enhance checks after the existing checks:

```python
@main.command("doctor")
def doctor_cmd() -> None:
    """Run system health check."""
    checks = [
        ("Python", _check_python),
        ("Config", _check_config),
        ("Tier 0", _check_tier0),
        ("Tier 1", _check_tier1),
        ("Tier 2", _check_tier2),
        ("Shell Widget", _check_shell_widget),
    ]

    issues: list[str] = []
    for name, check_fn in checks:
        ok, detail = check_fn()
        symbol = "\u2713" if ok else "\u2717"
        click.echo(f"  {name:<14} {symbol}  {detail}")
        if not ok:
            issues.append(detail)

    # Auto-enhance per tool
    for installer in get_installers():
        detected = installer.detect()
        if not detected:
            click.echo(
                f"  Auto-enhance   \u2717  {installer.name} (not detected)"
            )
            continue
        installed = installer.is_installed()
        symbol = "\u2713" if installed else "\u2717"
        cfg = load_config()
        threshold = cfg.get("auto_enhance", {}).get("threshold", 60)
        detail = (
            f"{installer.name} (threshold: {threshold})"
            if installed
            else f"{installer.name} (hook not installed — run: promptune config init)"
        )
        click.echo(f"  Auto-enhance   {symbol}  {detail}")
        if not installed:
            issues.append(detail)

    if issues:
        click.echo("\n  Issues:")
        for issue in issues:
            click.echo(f"    - {issue}")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_cli.py::TestDoctorAutoEnhance -v
```

Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add promptune/cli.py tests/test_cli.py
git commit -m "feat: add auto-enhance status to doctor command"
```

---

## Task 7: `promptune gate` CLI Command

**Files:**
- Modify: `promptune/cli.py`
- Modify: `tests/test_cli.py`

The `gate` command reads JSON from stdin (Claude Code hook format), extracts the prompt, and calls `run_gate()`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_cli.py`:

```python
class TestGateCommand:
    """promptune gate reads stdin JSON and calls run_gate."""

    def test_gate_passes_clean_prompt(self, mocker) -> None:
        mocker.patch("promptune.cli.run_gate", return_value=0)
        runner = CliRunner()
        stdin_data = json.dumps({"prompt": "implement a REST API"})
        result = runner.invoke(
            main, ["gate"], input=stdin_data
        )
        assert result.exit_code == 0

    def test_gate_blocks_low_quality_prompt(self, mocker) -> None:
        mocker.patch("promptune.cli.run_gate", return_value=1)
        runner = CliRunner()
        stdin_data = json.dumps({"prompt": "make a todo app"})
        result = runner.invoke(
            main, ["gate"], input=stdin_data
        )
        assert result.exit_code == 1

    def test_gate_passes_on_invalid_json(self, mocker) -> None:
        # Malformed JSON → pass through (don't break workflow)
        mocker.patch("promptune.cli.run_gate")
        runner = CliRunner()
        result = runner.invoke(
            main, ["gate"], input="not valid json"
        )
        assert result.exit_code == 0

    def test_gate_passes_on_missing_prompt_key(self, mocker) -> None:
        mocker.patch("promptune.cli.run_gate")
        runner = CliRunner()
        result = runner.invoke(
            main, ["gate"], input=json.dumps({"session_id": "abc"})
        )
        assert result.exit_code == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_cli.py::TestGateCommand -v
```

Expected: FAIL — `No such command 'gate'`

- [ ] **Step 3: Add `gate` command to `promptune/cli.py`**

Add this import near the top of `promptune/cli.py`:
```python
from promptune.gate import run_gate
```

Add this command (hidden from help, internal use):

```python
@main.command("gate", hidden=True)
def gate_cmd() -> None:
    """Auto-enhance gate hook (reads JSON from stdin)."""
    import json as _json

    try:
        raw = sys.stdin.read()
        data = _json.loads(raw)
        prompt = data.get("prompt", "")
    except (ValueError, KeyError):
        raise SystemExit(0) from None

    if not prompt:
        raise SystemExit(0)

    try:
        cfg = load_config()
    except ConfigError:
        raise SystemExit(0) from None

    code = run_gate(prompt, cfg)
    raise SystemExit(code)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_cli.py::TestGateCommand -v
```

Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add promptune/cli.py tests/test_cli.py
git commit -m "feat: add gate CLI command for hook integration"
```

---

## Task 8: MCP Server

**Files:**
- Create: `promptune/mcp/__init__.py`
- Create: `promptune/mcp/server.py`
- Create: `tests/test_mcp/__init__.py`
- Create: `tests/test_mcp/test_server.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Add `mcp` optional dependency to `pyproject.toml`**

In `pyproject.toml`, add after `linux-daemon`:

```toml
mcp = [
    "mcp>=1.0",
]
```

Also add a mypy override so mypy doesn't fail if `mcp` is not installed:

```toml
[[tool.mypy.overrides]]
module = ["mcp", "mcp.*"]
ignore_missing_imports = true
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_mcp/__init__.py` (empty).

Create `tests/test_mcp/test_server.py`:

```python
"""Tests for MCP server tools."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

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
        from promptune.mcp.server import _tool_enhance

        from promptune.engine import EnhanceResult

        mock_result = MagicMock(spec=EnhanceResult)
        mock_result.original = "make a todo app"
        mock_result.enhanced = "Build a full-stack todo application..."
        mock_result.score_before = _make_score(38)
        mock_result.score_after = _make_score(74)
        mock_result.tier_used = 0
        mock_result.rules_applied = ["vague_verbs"]
        mock_result.latency_ms = 50.0

        with (
            patch("promptune.mcp.server.load_config", return_value={}),
            patch("promptune.mcp.server.enhance", return_value=mock_result),
        ):
            result = _tool_enhance("make a todo app")

        assert result["original"] == "make a todo app"
        assert result["enhanced"] == "Build a full-stack todo application..."
        assert result["score_before"] == 38
        assert result["score_after"] == 74
        assert result["tier_used"] == 0
        assert result["rules_applied"] == ["vague_verbs"]
        assert "latency_ms" in result

    def test_enhance_passes_style_override(self) -> None:
        from promptune.mcp.server import _tool_enhance
        from promptune.engine import EnhanceResult

        mock_result = MagicMock(spec=EnhanceResult)
        mock_result.original = "make a todo app"
        mock_result.enhanced = "Build..."
        mock_result.score_before = _make_score(38)
        mock_result.score_after = _make_score(74)
        mock_result.tier_used = 0
        mock_result.rules_applied = []
        mock_result.latency_ms = 50.0

        mock_cfg: dict[str, Any] = {"enhancement": {"default_mode": "balanced"}}

        with (
            patch("promptune.mcp.server.load_config", return_value=mock_cfg),
            patch("promptune.mcp.server.enhance", return_value=mock_result) as mock_enhance,
        ):
            _tool_enhance("make a todo app", style="detailed")

        call_cfg = mock_enhance.call_args[0][1]
        assert call_cfg["enhancement"]["default_mode"] == "detailed"


class TestMcpScoreTool:
    """score tool returns correct structure."""

    def test_score_returns_total_and_dimensions(self) -> None:
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

    def test_score_dimension_has_required_fields(self) -> None:
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
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_mcp/ -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'promptune.mcp'`

- [ ] **Step 4: Create `promptune/mcp/__init__.py`**

```python
"""Promptune MCP server package."""
```

- [ ] **Step 5: Create `promptune/mcp/server.py`**

```python
"""MCP server for promptune — exposes enhance and score tools.

Start via: promptune mcp
AI tools (Claude Code, Codex, Cursor, etc.) launch this via stdio transport.
"""

from __future__ import annotations

from typing import Any

from promptune.config import load_config
from promptune.engine import enhance
from promptune.scorer import score_prompt


def _tool_enhance(
    prompt: str,
    style: str | None = None,
    tier: int | None = None,
    format_style: str | None = None,
) -> dict[str, Any]:
    """Enhance a prompt using the 3-tier engine."""
    cfg = load_config()
    if style:
        cfg["enhancement"]["default_mode"] = style
    if format_style:
        cfg["provider"]["format_style"] = format_style

    result = enhance(prompt, cfg, tier_override=tier)
    return {
        "original": result.original,
        "enhanced": result.enhanced,
        "score_before": result.score_before.total,
        "score_after": result.score_after.total,
        "tier_used": result.tier_used,
        "rules_applied": result.rules_applied,
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
        format: str = "auto",
    ) -> dict[str, Any]:
        """Enhance a prompt using AI (3-tier: rules → local LLM → cloud).

        Args:
            prompt: The prompt text to enhance.
            style: Enhancement style — minimal, balanced, or detailed.
            tier: Force specific tier (-1=auto, 0=rules only, 1=local, 2=cloud).
            format: Output format — auto, xml, markdown, or plain.
        """
        tier_override = tier if tier >= 0 else None
        fmt = format if format != "auto" else None
        return _tool_enhance(
            prompt,
            style=style if style != "balanced" else None,
            tier=tier_override,
            format_style=fmt,
        )

    @mcp.tool()
    def score_prompt_quality(prompt: str) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        """Score a prompt across 7 quality dimensions (0-100).

        Returns total PQS score, detected intent, and per-dimension
        breakdown with actionable suggestions.

        Args:
            prompt: The prompt text to score.
        """
        return _tool_score(prompt)

    mcp.run(transport="stdio")
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_mcp/ -v
```

Expected: all passed

- [ ] **Step 7: Commit**

```bash
git add promptune/mcp/__init__.py promptune/mcp/server.py \
        tests/test_mcp/__init__.py tests/test_mcp/test_server.py \
        pyproject.toml
git commit -m "feat: add MCP server with enhance and score tools"
```

---

## Task 9: `promptune mcp` CLI Command

**Files:**
- Modify: `promptune/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_cli.py`:

```python
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
            side_effect=ImportError("pip install promptune[mcp]"),
        )
        runner = CliRunner()
        result = runner.invoke(main, ["mcp"])
        assert result.exit_code == 1
        assert "pip install" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_cli.py::TestMcpCommand -v
```

Expected: FAIL — `No such command 'mcp'`

- [ ] **Step 3: Add `mcp` command to `promptune/cli.py`**

Add this import near the top of `promptune/cli.py`:
```python
from promptune.mcp.server import run_server as run_mcp_server
```

Add this command:

```python
@main.command("mcp")
def mcp_cmd() -> None:
    """Start the MCP server (stdio transport for AI tools)."""
    try:
        run_mcp_server()
    except ImportError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1) from e
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_cli.py::TestMcpCommand -v
```

Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add promptune/cli.py tests/test_cli.py
git commit -m "feat: add promptune mcp command"
```

---

## Task 10: Full Check Suite

- [ ] **Step 1: Run ruff**

```bash
ruff check .
```

Expected: `All checks passed!`

- [ ] **Step 2: Run mypy**

```bash
mypy promptune/
```

Expected: `Success: no issues found in N source files`

- [ ] **Step 3: Run full test suite with coverage**

```bash
python3 -m pytest --cov=promptune --cov-report=term-missing -v
```

Expected: all passed, ≥ 90% coverage overall, new modules ≥ 90% coverage each.

- [ ] **Step 4: Fix any failures**

If ruff flags a line-too-long: wrap the offending line.

If mypy flags a type error: fix the type annotation — do not use `# type: ignore` unless it's for a third-party import.

If a test fails: diagnose the root cause from the error message and fix the code or the test.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: all checks passing for MCP + auto-enhance phase"
```
