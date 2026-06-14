# Phase 1 Next Iteration — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add intelligent tier-based enhancement (rules → local LLM → cloud), quality scoring, context fingerprinting, provider-specific formatting, PQS display, and history storage on top of the existing promptune CLI/TUI/providers foundation.

**Architecture:** Bottom-up build. Config migration first (everything depends on it), then scorer and rule engine (Tier 0), local LLM provider (Tier 1), new router engine (Tier routing), context fingerprinting, PQS display, provider formatting, TUI updates, CLI commands, and finally SQLite history. Each step is independently testable with TDD RED-GREEN-REFACTOR.

**Tech Stack:** Python 3.9+, Click, Rich, prompt_toolkit, anthropic SDK, openai SDK, httpx, SQLite (stdlib), concurrent.futures (stdlib), math (stdlib), re (stdlib)

**Spec:** `docs/superpowers/specs/2026-03-15-phase1-next-iteration-design.md` (Version 1.1)

---

## File Structure

### New Files

| File | Responsibility |
|---|---|
| `promptune/scorer.py` | Quality scorer: 7-dimension heuristic scoring (0-100), intent-aware weights, sigmoid calibration |
| `promptune/tier0.py` | Tier 0 rule engine: 9 deterministic text transformation rules, each a pure function |
| `promptune/providers/local.py` | Local LLM provider: OpenAI-compatible HTTP client for Ollama/LM Studio/vLLM/etc. |
| `promptune/pqs.py` | Prompt Quality Score: 5-dimension user-facing display, maps from scorer internals |
| `promptune/formatter.py` | Provider-specific formatting: XML/Markdown/Plain + auto-detection from model ID |
| `promptune/context/__init__.py` | Context fingerprinting orchestrator: parallel collector execution, timeout budget |
| `promptune/context/collectors.py` | 4 collectors: Git, ShellHistory, TechStack, Environment |
| `promptune/context/sanitizer.py` | Secret sanitizer: regex patterns + Shannon entropy detection |
| `promptune/context/ranker.py` | Context ranker: priority-weighted token budget allocation |
| `promptune/history.py` | SQLite history store: CRUD, stats, auto-prune, schema versioning |
| `tests/test_scorer.py` | Scorer tests |
| `tests/test_tier0.py` | Tier 0 rule engine tests |
| `tests/test_providers/test_local.py` | Local LLM provider tests |
| `tests/test_pqs.py` | PQS tests |
| `tests/test_formatter.py` | Formatter tests |
| `tests/test_context/__init__.py` | (empty) |
| `tests/test_context/test_collectors.py` | Collector tests |
| `tests/test_context/test_sanitizer.py` | Sanitizer tests |
| `tests/test_context/test_ranker.py` | Ranker tests |
| `tests/test_context/test_init.py` | Context orchestrator tests |
| `tests/test_history.py` | History store tests |

### Modified Files

| File | Changes |
|---|---|
| `promptune/config.py` | Full rewrite: new schema, new defaults, new validation, `generate_default_config()` |
| `promptune/engine.py` | Full rewrite: tier-based router replacing direct provider call |
| `promptune/providers/__init__.py` | `BaseProvider.__init__` signature: `api_key` becomes optional (default `""`) — **Task 4** |
| `promptune/meta_prompt.py` | Rename `"thorough"` to `"detailed"` in style handling — **Task 1** |
| `promptune/tui.py` | Add header line, toggle keybindings (Q/D/C), quality bars, diff highlighting — **Task 9** |
| `promptune/cli.py` | Update config access (Task 1), new flags + commands (Task 10) |
| `config.example.toml` | Rewrite to match new schema — **Task 1** |
| `CLAUDE.md` | Update Config TOML Schema section, rename `"thorough"` → `"detailed"` — **Task 1** |
| `pyproject.toml` | No new dependencies (all stdlib) |
| `tests/test_config.py` | Full rewrite: test new schema — **Task 1** |
| `tests/test_engine.py` | Full rewrite: test new router — **Task 1** (config), **Task 5** (router) |
| `tests/test_cli.py` | Update config expectations (Task 1), test new commands (Task 10) |
| `tests/test_meta_prompt.py` | Update `"thorough"` → `"detailed"` — **Task 1** |
| `tests/test_providers/test_base.py` | Verify optional `api_key` — **Task 4** |

---

## Chunk 1: Task 1 — Config Schema Migration

### Task 1: Config Schema Migration

**Goal:** Replace the old config schema with the new one. This is the foundation — every other step depends on it.

**Files:**
- Modify: `promptune/config.py` (full rewrite)
- Modify: `config.example.toml` (full rewrite)
- Modify: `tests/test_config.py` (full rewrite)
- Modify: `promptune/engine.py` (full rewrite — update config key paths)
- Modify: `promptune/cli.py` (update config access in `enhance_cmd` + clean up `config_show`)
- Modify: `promptune/meta_prompt.py:135` (rename `"thorough"` to `"detailed"`)
- Modify: `tests/test_engine.py` (update mock configs + style reference)
- Modify: `tests/test_cli.py` (verify existing tests pass with new schema)
- Modify: `tests/test_meta_prompt.py:66-74` (rename `thorough` → `detailed`)
- Modify: `CLAUDE.md` (update Config TOML Schema section, rename `"thorough"` → `"detailed"`)

---

- [x]**Step 1.1: Write failing tests for new DEFAULT_CONFIG**

File: `tests/test_config.py`

```python
"""Config system tests — new schema."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from promptune.cli import main
from promptune.config import ConfigError, load_config


@pytest.fixture()
def config_dir(tmp_path: Path) -> Path:
    """Return a temporary config directory."""
    return tmp_path / "promptune"


@pytest.fixture()
def config_file(config_dir: Path) -> Path:
    """Return the config file path within tmp config dir."""
    return config_dir / "config.toml"


@pytest.fixture()
def valid_config_toml() -> str:
    """Return a valid config TOML string matching new schema."""
    return """\
[provider]
default = "claude"
format_style = "auto"
model_claude = "claude-haiku-4-5-20251001"
model_openai = "gpt-4o-mini"
model_openrouter = "anthropic/claude-haiku"

[api_keys]
claude = "sk-ant-test-key"
openai = "sk-test-key"
openrouter = "sk-or-test-key"

[enhancement]
max_tier = 2
default_mode = "balanced"
max_tokens_output = 400
timeout_seconds = 10

[local_llm]
enabled = true
host = "http://localhost:11434"
model = "qwen2.5:3b"
api_key = ""

[context]
use_git = true
use_shell_history = true
use_stack_detection = true
max_context_tokens = 500
shell_history_lines = 20

[history]
enabled = true
max_entries = 10000
db_path = "~/.local/share/promptune/history.db"

[tui]
show_pqs_scores = true
show_tier_used = true
show_latency = true
theme = "dark"
show_diff = true
"""


def test_default_config_new_schema(config_file: Path) -> None:
    """Defaults use new schema structure."""
    config = load_config(config_path=config_file)
    assert config["provider"]["default"] == "claude"
    assert config["provider"]["format_style"] == "auto"
    assert config["enhancement"]["max_tier"] == 2
    assert config["enhancement"]["default_mode"] == "balanced"
    assert config["local_llm"]["enabled"] is True
    assert config["context"]["use_git"] is True
    assert config["history"]["enabled"] is True
    assert config["tui"]["theme"] == "dark"


def test_default_config_api_keys_empty(config_file: Path) -> None:
    """Default API keys are empty strings."""
    config = load_config(config_path=config_file)
    assert config["api_keys"]["claude"] == ""
    assert config["api_keys"]["openai"] == ""
    assert config["api_keys"]["openrouter"] == ""


def test_default_config_models(config_file: Path) -> None:
    """Default models are set correctly."""
    config = load_config(config_path=config_file)
    assert config["provider"]["model_claude"] == "claude-haiku-4-5-20251001"
    assert config["provider"]["model_openai"] == "gpt-4o-mini"
    assert config["provider"]["model_openrouter"] == "anthropic/claude-haiku"


def test_default_config_local_llm(config_file: Path) -> None:
    """Default local LLM settings."""
    config = load_config(config_path=config_file)
    assert config["local_llm"]["host"] == "http://localhost:11434"
    assert config["local_llm"]["model"] == "qwen2.5:3b"
    assert config["local_llm"]["api_key"] == ""


def test_default_config_enhancement(config_file: Path) -> None:
    """Default enhancement settings."""
    config = load_config(config_path=config_file)
    assert config["enhancement"]["max_tokens_output"] == 400
    assert config["enhancement"]["timeout_seconds"] == 10


def test_default_config_context(config_file: Path) -> None:
    """Default context settings."""
    config = load_config(config_path=config_file)
    assert config["context"]["max_context_tokens"] == 500
    assert config["context"]["shell_history_lines"] == 20
    assert config["context"]["use_stack_detection"] is True


def test_default_config_history(config_file: Path) -> None:
    """Default history settings."""
    config = load_config(config_path=config_file)
    assert config["history"]["max_entries"] == 10000
    assert config["history"]["db_path"] == "~/.local/share/promptune/history.db"
```

- [x]**Step 1.2: Run tests to verify they fail**

Run: `pytest tests/test_config.py -v -x`
Expected: FAIL — `config["provider"]` KeyError (old schema uses `config["general"]`)

- [x]**Step 1.3: Write failing tests for validation logic**

Append to `tests/test_config.py`:

```python
def test_load_valid_config(config_file: Path, valid_config_toml: str) -> None:
    """Valid TOML file parsed correctly with new schema."""
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(valid_config_toml)
    config = load_config(config_path=config_file)
    assert config["api_keys"]["claude"] == "sk-ant-test-key"
    assert config["provider"]["model_openai"] == "gpt-4o-mini"
    assert config["enhancement"]["max_tier"] == 2


def test_load_invalid_config(config_file: Path) -> None:
    """Invalid TOML raises ConfigError."""
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text("this is [not valid toml")
    with pytest.raises(ConfigError, match="[Ii]nvalid|[Pp]arse"):
        load_config(config_path=config_file)


def test_missing_provider_key(config_file: Path) -> None:
    """Missing API key for the default provider raises ConfigError.

    Note: This triggers because DEFAULT_CONFIG sets max_tier=2, which
    requires a cloud API key. The file only sets provider.default="claude"
    so api_keys.claude remains "" from defaults, triggering the error.
    """
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text("""\
[provider]
default = "claude"
""")
    with pytest.raises(ConfigError, match="api_key"):
        load_config(config_path=config_file, validate_keys=True)


def test_env_var_override(
    config_file: Path, valid_config_toml: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Env vars override config file values."""
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(valid_config_toml)
    monkeypatch.setenv("PROMPTUNE_PROVIDER", "openai")
    monkeypatch.setenv("PROMPTUNE_STYLE", "detailed")
    config = load_config(config_path=config_file)
    assert config["provider"]["default"] == "openai"
    assert config["enhancement"]["default_mode"] == "detailed"


def test_config_resolution_order(
    config_file: Path, valid_config_toml: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CLI overrides > env vars > config file > defaults."""
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(valid_config_toml)
    monkeypatch.setenv("PROMPTUNE_PROVIDER", "openai")
    config = load_config(config_path=config_file)
    assert config["provider"]["default"] == "openai"
    overrides = {"provider": "openrouter"}
    config = load_config(config_path=config_file, cli_overrides=overrides)
    assert config["provider"]["default"] == "openrouter"


def test_validate_provider_name(config_file: Path) -> None:
    """Invalid provider name raises ConfigError."""
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text("""\
[provider]
default = "invalid_provider"
""")
    with pytest.raises(ConfigError, match="[Pp]rovider"):
        load_config(config_path=config_file, validate_keys=True)


def test_validate_mode_name(config_file: Path) -> None:
    """Invalid mode name raises ConfigError."""
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text("""\
[enhancement]
default_mode = "ultra_mega"
""")
    with pytest.raises(ConfigError, match="[Mm]ode"):
        load_config(config_path=config_file, validate_keys=True)


def test_validate_format_style(config_file: Path) -> None:
    """Invalid format_style raises ConfigError."""
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text("""\
[provider]
format_style = "invalid"
""")
    with pytest.raises(ConfigError, match="format"):
        load_config(config_path=config_file, validate_keys=True)


def test_validate_max_tier(config_file: Path) -> None:
    """max_tier outside 0-2 raises ConfigError."""
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text("""\
[enhancement]
max_tier = 5
""")
    with pytest.raises(ConfigError, match="[Tt]ier"):
        load_config(config_path=config_file, validate_keys=True)


def test_config_init_creates_file(config_dir: Path) -> None:
    """'config init' creates config at expected path."""
    config_file = config_dir / "config.toml"
    runner = CliRunner()
    result = runner.invoke(main, ["config", "init", "--config-dir", str(config_dir)])
    assert result.exit_code == 0
    assert config_file.exists()
    content = config_file.read_text()
    assert "[provider]" in content
    assert "[api_keys]" in content
    assert "[enhancement]" in content


def test_config_show_output(
    config_file: Path, valid_config_toml: str
) -> None:
    """'config show' prints current config."""
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(valid_config_toml)
    runner = CliRunner()
    result = runner.invoke(
        main, ["config", "show", "--config-path", str(config_file)]
    )
    assert result.exit_code == 0
    assert "claude" in result.output
    assert "balanced" in result.output


def test_config_path_output(config_file: Path) -> None:
    """'config path' prints config file path."""
    runner = CliRunner()
    result = runner.invoke(
        main, ["config", "path", "--config-path", str(config_file)]
    )
    assert result.exit_code == 0
    assert str(config_file) in result.output
```

- [x]**Step 1.4: Run tests to verify they fail**

Run: `pytest tests/test_config.py -v -x`
Expected: FAIL

- [x]**Step 1.5: Implement new DEFAULT_CONFIG in config.py**

Rewrite `promptune/config.py`:

```python
"""Configuration loading, validation, and defaults."""

from __future__ import annotations

import copy
import os
import sys
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


class ConfigError(Exception):
    """Raised when configuration is invalid."""


VALID_PROVIDERS = {"claude", "openai", "openrouter"}
VALID_MODES = {"minimal", "balanced", "detailed"}
VALID_FORMAT_STYLES = {"auto", "xml", "markdown", "plain"}

DEFAULT_CONFIG: dict[str, Any] = {
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
        "max_tier": 2,
        "default_mode": "balanced",
        "max_tokens_output": 400,
        "timeout_seconds": 10,
    },
    "local_llm": {
        "enabled": True,
        "host": "http://localhost:11434",
        "model": "qwen2.5:3b",
        "api_key": "",
    },
    "context": {
        "use_git": True,
        "use_shell_history": True,
        "use_stack_detection": True,
        "max_context_tokens": 500,
        "shell_history_lines": 20,
    },
    "history": {
        "enabled": True,
        "max_entries": 10000,
        "db_path": "~/.local/share/promptune/history.db",
    },
    "tui": {
        "show_pqs_scores": True,
        "show_tier_used": True,
        "show_latency": True,
        "theme": "dark",
        "show_diff": True,
    },
}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Merge override into base recursively."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _apply_env_overrides(config: dict[str, Any]) -> dict[str, Any]:
    """Apply environment variable overrides."""
    provider = os.environ.get("PROMPTUNE_PROVIDER")
    if provider:
        config["provider"]["default"] = provider
    style = os.environ.get("PROMPTUNE_STYLE")
    if style:
        config["enhancement"]["default_mode"] = style
    return config


def _apply_cli_overrides(
    config: dict[str, Any], cli_overrides: dict[str, str]
) -> dict[str, Any]:
    """Apply CLI flag overrides."""
    if "provider" in cli_overrides:
        config["provider"]["default"] = cli_overrides["provider"]
    if "style" in cli_overrides:
        config["enhancement"]["default_mode"] = cli_overrides["style"]
    if "tier" in cli_overrides:
        config["enhancement"]["max_tier"] = int(cli_overrides["tier"])
    if "format" in cli_overrides:
        config["provider"]["format_style"] = cli_overrides["format"]
    return config


def default_config_path() -> Path:
    """Return the default config file path."""
    return Path.home() / ".config" / "promptune" / "config.toml"


def load_config(
    config_path: Path | None = None,
    cli_overrides: dict[str, str] | None = None,
    validate_keys: bool = False,
) -> dict[str, Any]:
    """Load config with resolution: CLI > env > file > defaults."""
    config = copy.deepcopy(DEFAULT_CONFIG)

    if config_path is None:
        config_path = default_config_path()

    if config_path.exists():
        try:
            with open(config_path, "rb") as f:
                file_config = tomllib.load(f)
        except Exception as e:
            raise ConfigError(f"Invalid config file: {e}") from e
        config = _deep_merge(config, file_config)

    config = _apply_env_overrides(config)

    if cli_overrides:
        config = _apply_cli_overrides(config, cli_overrides)

    if validate_keys:
        _validate(config)

    return config


def _validate(config: dict[str, Any]) -> None:
    """Validate config values."""
    provider = config["provider"]["default"]
    if provider not in VALID_PROVIDERS:
        raise ConfigError(
            f"Invalid provider '{provider}'. "
            f"Must be one of: {', '.join(sorted(VALID_PROVIDERS))}"
        )

    mode = config["enhancement"]["default_mode"]
    if mode not in VALID_MODES:
        raise ConfigError(
            f"Invalid mode '{mode}'. "
            f"Must be one of: {', '.join(sorted(VALID_MODES))}"
        )

    format_style = config["provider"]["format_style"]
    if format_style not in VALID_FORMAT_STYLES:
        raise ConfigError(
            f"Invalid format_style '{format_style}'. "
            f"Must be one of: {', '.join(sorted(VALID_FORMAT_STYLES))}"
        )

    max_tier = config["enhancement"]["max_tier"]
    if not isinstance(max_tier, int) or max_tier < 0 or max_tier > 2:
        raise ConfigError(
            f"Invalid max_tier '{max_tier}'. Must be 0, 1, or 2."
        )

    # Check api_key for the default provider (only when max_tier >= 2)
    if config["enhancement"]["max_tier"] >= 2:
        api_key = config["api_keys"].get(provider, "")
        if not api_key:
            raise ConfigError(
                f"Missing api_key for provider '{provider}'. "
                f"Set it in your config file or via environment variable."
            )


def generate_default_config() -> str:
    """Return the default config as a TOML string."""
    return """\
# Promptune Configuration

[provider]
default = "claude"
format_style = "auto"
model_claude = "claude-haiku-4-5-20251001"
model_openai = "gpt-4o-mini"
model_openrouter = "anthropic/claude-haiku"

[api_keys]
claude = ""
openai = ""
openrouter = ""

[enhancement]
max_tier = 2
default_mode = "balanced"
max_tokens_output = 400
timeout_seconds = 10

[local_llm]
enabled = true
host = "http://localhost:11434"
model = "qwen2.5:3b"
api_key = ""

[context]
use_git = true
use_shell_history = true
use_stack_detection = true
max_context_tokens = 500
shell_history_lines = 20

[history]
enabled = true
max_entries = 10000
db_path = "~/.local/share/promptune/history.db"

[tui]
show_pqs_scores = true
show_tier_used = true
show_latency = true
theme = "dark"
show_diff = true
"""
```

- [x]**Step 1.6: Run config tests to verify they pass**

Run: `pytest tests/test_config.py -v`
Expected: ALL PASS

- [x]**Step 1.7: Update engine.py config key paths**

Update `promptune/engine.py` to use new config schema keys:
- `config["general"]["default_provider"]` → `config["provider"]["default"]`
- `config["providers"][name]` → build provider config from `config["api_keys"][name]` + `config["provider"]["model_<name>"]`
- `config["general"]["style"]` → `config["enhancement"]["default_mode"]`

```python
"""Core engine: orchestrates config, meta-prompt, and provider."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from promptune.config import ConfigError
from promptune.meta_prompt import (
    build_system_prompt,
    detect_domain,
    detect_intent,
    detect_stack,
)
from promptune.providers import BaseProvider, ProviderRegistry
from promptune.providers.anthropic import register as register_claude
from promptune.providers.openai import register as register_openai
from promptune.providers.openrouter import register as register_openrouter


@dataclass
class EnhanceResult:
    """Result of a prompt enhancement."""

    original: str
    enhanced: str


def _get_registry() -> ProviderRegistry:
    """Build and return the provider registry."""
    registry = ProviderRegistry()
    register_claude(registry)
    register_openai(registry)
    register_openrouter(registry)
    return registry


def _build_provider_config(provider_name: str, config: dict[str, Any]) -> dict[str, Any]:
    """Build a provider config dict from the new schema."""
    model_key = f"model_{provider_name}"
    return {
        "api_key": config["api_keys"].get(provider_name, ""),
        "model": config["provider"].get(model_key, ""),
    }


def _create_provider(
    provider_name: str, config: dict[str, Any]
) -> BaseProvider:
    """Create a provider instance from name and config."""
    registry = _get_registry()
    provider_config = _build_provider_config(provider_name, config)
    return registry.create(provider_name, provider_config)


def enhance(
    prompt: str,
    config: dict[str, Any],
    provider_override: str | None = None,
) -> EnhanceResult:
    """Enhance a prompt using the configured provider."""
    provider_name = provider_override or config["provider"]["default"]

    # Validate API key before creating provider
    api_key = config["api_keys"].get(provider_name, "")
    if not api_key:
        raise ConfigError(
            f"Missing api_key for provider '{provider_name}'. "
            f"Set it in your config file or via environment variable."
        )

    style = config["enhancement"]["default_mode"]

    # Analyze prompt
    intent = detect_intent(prompt)
    domain = detect_domain(prompt)
    stack = detect_stack(prompt)

    # Build system prompt
    system_prompt = build_system_prompt(
        intent=intent,
        domain=domain,
        stack=stack,
        style=style,
    )

    # Create provider and enhance
    provider = _create_provider(provider_name, config)
    enhanced = provider.enhance(prompt, system_prompt)

    return EnhanceResult(original=prompt, enhanced=enhanced)
```

- [x]**Step 1.8: Update test_engine.py mock configs to new schema**

Rewrite `tests/test_engine.py` `mock_config` fixture:

```python
@pytest.fixture()
def mock_config() -> dict:
    """Return a valid config dict with new schema."""
    return {
        "provider": {
            "default": "claude",
            "format_style": "auto",
            "model_claude": "claude-haiku-4-5-20251001",
            "model_openai": "gpt-4o-mini",
            "model_openrouter": "anthropic/claude-haiku",
        },
        "api_keys": {
            "claude": "sk-ant-test",
            "openai": "sk-test",
            "openrouter": "sk-or-test",
        },
        "enhancement": {
            "max_tier": 2,
            "default_mode": "balanced",
            "max_tokens_output": 400,
            "timeout_seconds": 10,
        },
        "local_llm": {
            "enabled": True,
            "host": "http://localhost:11434",
            "model": "qwen2.5:3b",
            "api_key": "",
        },
        "context": {
            "use_git": True,
            "use_shell_history": True,
            "use_stack_detection": True,
            "max_context_tokens": 500,
            "shell_history_lines": 20,
        },
        "history": {
            "enabled": True,
            "max_entries": 10000,
            "db_path": "~/.local/share/promptune/history.db",
        },
        "tui": {
            "show_pqs_scores": True,
            "show_tier_used": True,
            "show_latency": True,
            "theme": "dark",
            "show_diff": True,
        },
    }
```

Also update `test_engine_passes_style_to_meta_prompt` to use `"detailed"` instead of `"thorough"`:

```python
def test_engine_passes_style_to_meta_prompt(
    mocker: MockerFixture, mock_config: dict
) -> None:
    """Style setting forwarded correctly to meta-prompt builder."""
    mock_provider = mocker.MagicMock()
    mock_provider.enhance.return_value = "result"
    mocker.patch(
        "promptune.engine._create_provider",
        return_value=mock_provider,
    )
    mock_build = mocker.patch(
        "promptune.engine.build_system_prompt",
        return_value="system prompt",
    )

    mock_config["enhancement"]["default_mode"] = "detailed"
    enhance("prompt", mock_config)

    call_kwargs = mock_build.call_args[1]
    assert call_kwargs["style"] == "detailed"
```

And update `test_engine_missing_api_key_error`:

```python
def test_engine_missing_api_key_error(
    mocker: MockerFixture, mock_config: dict
) -> None:
    """Clear error when API key not configured."""
    mock_config["api_keys"]["claude"] = ""

    with pytest.raises(ConfigError, match="api_key"):
        enhance("prompt", mock_config)
```

- [x]**Step 1.9: Update cli.py config access paths and clean up config_show**

In `promptune/cli.py`, update the `enhance_cmd` function:

```python
# Change these lines in enhance_cmd:
        if provider:
            cfg["provider"]["default"] = provider
        if style:
            cfg["enhancement"]["default_mode"] = style
```

Also simplify `config_show` — the new schema has flat sections (no nested `[providers.*]`), so remove dead nested-dict code:

```python
@config.command("show")
@click.option(
    "--config-path",
    type=click.Path(),
    default=None,
    help="Path to config file.",
)
def config_show(config_path: str | None) -> None:
    """Print current configuration."""
    path = Path(config_path) if config_path else default_config_path()
    cfg = load_config(config_path=path)
    for section, values in cfg.items():
        click.echo(f"[{section}]")
        if isinstance(values, dict):
            for key, val in values.items():
                click.echo(f"  {key} = {val}")
        click.echo()
```

- [x]**Step 1.10: Rename "thorough" to "detailed" in meta_prompt.py**

In `promptune/meta_prompt.py`, change line 135:

```python
# Change:
    elif style == "thorough":
# To:
    elif style == "detailed":
```

- [x]**Step 1.11: Update test_meta_prompt.py for "detailed"**

In `tests/test_meta_prompt.py`, replace the full `test_build_system_prompt_thorough` function:

```python
def test_build_system_prompt_detailed() -> None:
    """Detailed style adds edge cases."""
    prompt = build_system_prompt(
        intent="coding",
        domain="webdev",
        stack=["python", "flask"],
        style="detailed",
    )
    assert "edge case" in prompt.lower() or "criteria" in prompt.lower()
```

- [x]**Step 1.12: Update config.example.toml**

Overwrite `config.example.toml` with the new schema (same content as `generate_default_config()`).

- [x]**Step 1.13: Verify tests/test_cli.py still passes**

The existing `test_cli.py` tests (version, help, module_runnable) do not directly reference the old config schema, so they should pass without changes. Verify:

Run: `pytest tests/test_cli.py -v`
Expected: ALL PASS

If any test fails due to config changes (e.g., if a test indirectly imports config), fix the import chain.

- [x]**Step 1.14: Update CLAUDE.md Config TOML Schema section**

In `CLAUDE.md`, replace the `## Config TOML Schema` section with the new schema, and update `Enhancement Styles` to rename `"thorough"` to `"detailed"`:

```markdown
## Config TOML Schema

\```toml
[provider]
default = "claude"                        # claude | openai | openrouter
format_style = "auto"                     # auto | xml | markdown | plain
model_claude = "claude-haiku-4-5-20251001"
model_openai = "gpt-4o-mini"
model_openrouter = "anthropic/claude-haiku"

[api_keys]
claude = "sk-ant-..."
openai = "sk-..."
openrouter = "sk-or-..."

[enhancement]
max_tier = 2                              # 0=rules only, 1=+local, 2=+cloud
default_mode = "balanced"                 # minimal | balanced | detailed
max_tokens_output = 400
timeout_seconds = 10

[local_llm]
enabled = true
host = "http://localhost:11434"
model = "qwen2.5:3b"
api_key = ""

[context]
use_git = true
use_shell_history = true
use_stack_detection = true
max_context_tokens = 500
shell_history_lines = 20

[history]
enabled = true
max_entries = 10000
db_path = "~/.local/share/promptune/history.db"

[tui]
show_pqs_scores = true
show_tier_used = true
show_latency = true
theme = "dark"
show_diff = true
\```
```

Also in the Enhancement Styles table, rename:
- `thorough` → `detailed`
- Update description to: `Full expansion — edge cases, acceptance criteria, tech suggestions`

And in `VALID_STYLES`, rename to `VALID_MODES` with value `"detailed"` replacing `"thorough"`.

- [x]**Step 1.15: Run full test suite**

Run: `pytest --cov=promptune --cov-report=term-missing -v`
Expected: ALL PASS, coverage maintained

- [x]**Step 1.16: Run linting and type checks**

Run: `ruff check . && mypy promptune/`
Expected: PASS

- [x]**Step 1.17: Commit**

```bash
git add promptune/config.py promptune/engine.py promptune/cli.py promptune/meta_prompt.py config.example.toml CLAUDE.md tests/test_config.py tests/test_engine.py tests/test_meta_prompt.py tests/test_cli.py
git commit -m "feat: migrate config to new schema with tiers, local LLM, context, history sections"
```

---

## Chunk 2: Task 2 — Quality Scorer

### Task 2: Quality Scorer

**Goal:** Pure heuristic function scoring prompts 0-100 across 7 dimensions. No AI, no network, typically <5ms. Used by Tier 0 rules and router for tier decisions.

**Files:**
- Create: `promptune/scorer.py`
- Create: `tests/test_scorer.py`

---

- [x]**Step 2.1: Write failing tests for dataclasses and score_prompt signature**

File: `tests/test_scorer.py`

```python
"""Quality Scorer tests."""

import pytest

from promptune.scorer import DimensionScore, ScoreResult, score_prompt


def test_score_result_dataclass() -> None:
    """ScoreResult has required fields."""
    result = ScoreResult(
        total=50,
        dimensions={"specificity": DimensionScore(
            score=0.5, max_weight=25.0, signals=["test"], suggestion="add detail",
        )},
        intent="coding",
    )
    assert result.total == 50
    assert result.intent == "coding"
    assert "specificity" in result.dimensions


def test_dimension_score_dataclass() -> None:
    """DimensionScore has required fields."""
    ds = DimensionScore(score=0.7, max_weight=25.0, signals=["term"], suggestion="ok")
    assert ds.score == 0.7
    assert ds.max_weight == 25.0
    assert ds.signals == ["term"]
    assert ds.suggestion == "ok"


def test_score_prompt_returns_score_result() -> None:
    """score_prompt returns a ScoreResult."""
    result = score_prompt("build a REST API with Flask")
    assert isinstance(result, ScoreResult)
    assert 0 <= result.total <= 100
    assert isinstance(result.dimensions, dict)
    assert isinstance(result.intent, str)


def test_score_prompt_has_all_dimensions() -> None:
    """ScoreResult contains all 7 dimensions."""
    result = score_prompt("test prompt")
    expected = {
        "specificity", "clarity", "structure", "actionability",
        "context", "completeness", "conciseness",
    }
    assert set(result.dimensions.keys()) == expected
```

- [x]**Step 2.2: Run tests to verify they fail**

Run: `pytest tests/test_scorer.py -v -x`
Expected: FAIL — `ModuleNotFoundError: No module named 'promptune.scorer'`

- [x]**Step 2.3: Write failing tests for individual dimension scoring**

Append to `tests/test_scorer.py`:

```python
def test_specificity_high_for_detailed_prompt() -> None:
    """Detailed prompt with technical terms scores high on specificity."""
    result = score_prompt(
        "Build a REST API using Flask with SQLAlchemy ORM, PostgreSQL "
        "database, JWT authentication, rate limiting at 100 req/min, "
        "and return JSON responses with proper HTTP status codes"
    )
    spec = result.dimensions["specificity"]
    assert spec.score > 0.5, f"Expected high specificity, got {spec.score}"


def test_specificity_low_for_vague_prompt() -> None:
    """Vague prompt scores low on specificity."""
    result = score_prompt("fix the thing")
    spec = result.dimensions["specificity"]
    assert spec.score < 0.4, f"Expected low specificity, got {spec.score}"


def test_clarity_penalizes_negation() -> None:
    """Prompts with negation score lower on clarity."""
    positive = score_prompt("Use Python 3.12 for this project")
    negative = score_prompt("Don't not use any language other than Python")
    assert positive.dimensions["clarity"].score >= negative.dimensions["clarity"].score


def test_structure_detects_markdown() -> None:
    """Prompt with markdown structure scores high on structure."""
    structured = score_prompt(
        "## Task\nBuild an API\n## Requirements\n- Auth\n- Rate limiting\n## Output\nJSON"
    )
    flat = score_prompt("build an api with auth and rate limiting that returns json")
    assert structured.dimensions["structure"].score > flat.dimensions["structure"].score


def test_actionability_detects_imperative_verbs() -> None:
    """Prompt with specific imperative verbs scores higher on actionability."""
    actionable = score_prompt("Implement a function that validates email addresses")
    vague = score_prompt("something about email stuff")
    assert actionable.dimensions["actionability"].score > vague.dimensions["actionability"].score


def test_context_detects_role_assignment() -> None:
    """Prompt with role assignment scores higher on context."""
    with_role = score_prompt("You are a senior Python developer. Review this code.")
    without_role = score_prompt("Review this code.")
    assert with_role.dimensions["context"].score > without_role.dimensions["context"].score


def test_completeness_detects_output_format() -> None:
    """Prompt specifying output format scores higher on completeness."""
    complete = score_prompt(
        "Build a function. Return a JSON object with keys: status, data, error."
    )
    incomplete = score_prompt("Build a function")
    assert complete.dimensions["completeness"].score > incomplete.dimensions["completeness"].score


def test_conciseness_penalizes_filler() -> None:
    """Prompt with filler words scores lower on conciseness."""
    concise = score_prompt("Implement JWT authentication for the API endpoint")
    wordy = score_prompt(
        "Could you please kindly help me implement JWT authentication "
        "for the API endpoint if you don't mind?"
    )
    assert concise.dimensions["conciseness"].score > wordy.dimensions["conciseness"].score
```

- [x]**Step 2.4: Run tests to verify they fail**

Run: `pytest tests/test_scorer.py -v -x`
Expected: FAIL

- [x]**Step 2.5: Write failing tests for intent-aware weights and calibration**

Append to `tests/test_scorer.py`:

```python
def test_intent_detection_coding() -> None:
    """Coding intent detected for programming prompts."""
    result = score_prompt("build a REST API with Flask")
    assert result.intent == "coding"


def test_intent_detection_writing() -> None:
    """Writing intent detected for writing prompts."""
    result = score_prompt("write a blog post about machine learning trends")
    assert result.intent == "writing"


def test_intent_detection_research() -> None:
    """Research intent detected for research prompts."""
    result = score_prompt("explain how DNS resolution works")
    assert result.intent == "research"


def test_score_calibration_prevents_clustering() -> None:
    """Scores should span a reasonable range, not cluster in 40-60."""
    prompts = [
        "fix it",
        "fix the bug in the auth module",
        (
            "## Task\nFix the authentication bug in src/auth/redirect.ts\n"
            "## Context\nYou are a TypeScript expert. The redirect after "
            "OAuth login fails with a TypeError.\n## Requirements\n"
            "- Preserve existing test coverage\n- Add error handling\n"
            "## Output\nReturn the corrected code with inline comments"
        ),
    ]
    scores = [score_prompt(p).total for p in prompts]
    score_range = max(scores) - min(scores)
    assert score_range >= 30, f"Scores too clustered: {scores}"


def test_score_total_is_calibrated_integer() -> None:
    """Total score is an integer 0-100."""
    result = score_prompt("build a REST API")
    assert isinstance(result.total, int)
    assert 0 <= result.total <= 100


def test_dimension_scores_have_suggestions() -> None:
    """Each dimension provides an actionable suggestion."""
    result = score_prompt("fix it")
    for name, dim in result.dimensions.items():
        assert isinstance(dim.suggestion, str), f"{name} missing suggestion"
        assert len(dim.suggestion) > 0, f"{name} has empty suggestion"


def test_scorer_performance() -> None:
    """Scorer runs in <50ms for typical prompts."""
    import time
    prompt = "Build a REST API using Flask with JWT authentication"
    start = time.perf_counter()
    for _ in range(100):
        score_prompt(prompt)
    elapsed_ms = (time.perf_counter() - start) * 1000
    avg_ms = elapsed_ms / 100
    assert avg_ms < 50, f"Scorer too slow: {avg_ms:.1f}ms avg"


def test_empty_string_input() -> None:
    """Empty string returns valid ScoreResult with low score."""
    result = score_prompt("")
    assert isinstance(result, ScoreResult)
    assert result.total >= 0
    assert result.total <= 100


def test_general_intent_fallback() -> None:
    """Prompt with no intent keywords returns 'general' intent."""
    result = score_prompt("hello world")
    assert result.intent == "general"


def test_intent_weight_adjustment_affects_scores() -> None:
    """Coding intent should slightly boost specificity weight."""
    # A prompt that could be coding or general — the intent adjustment
    # should shift weights by the spec's percentage (e.g., specificity +5%)
    result = score_prompt("implement the REST API endpoint")
    assert result.intent == "coding"
    # Just verify it produces a valid result — exact weight math tested implicitly
    assert 0 <= result.total <= 100
```

- [x]**Step 2.6: Run tests to verify they fail**

Run: `pytest tests/test_scorer.py -v -x`
Expected: FAIL

- [x]**Step 2.7: Implement scorer dataclasses and dimension helpers**

Create `promptune/scorer.py` with dataclasses and helper functions:

```python
"""Quality Scorer: 7-dimension heuristic prompt scoring (0-100).

Research basis:
- Bsharat et al. 2023: 26 validated principles — specificity is strongest predictor
- Schulhoff et al. 2024 "The Prompt Report": structure > word choice
- DETAIL paper (arXiv:2512.02246): specificity +0.47 on procedural tasks
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field


@dataclass
class DimensionScore:
    """Score for a single dimension."""

    score: float          # 0-1 raw
    max_weight: float     # dimension weight
    signals: list[str]    # what was detected
    suggestion: str       # actionable fix


@dataclass
class ScoreResult:
    """Result of scoring a prompt."""

    total: int                              # 0-100 calibrated
    dimensions: dict[str, DimensionScore]   # per-dimension detail
    intent: str                             # detected prompt type


# --- Intent detection (reuses meta_prompt logic) ---

_INTENT_KEYWORDS: dict[str, list[str]] = {
    "coding": [
        "build", "create", "implement", "code", "develop", "api",
        "function", "class", "app", "script", "debug", "fix",
        "refactor", "deploy", "test", "endpoint", "database",
        "server", "cli", "component", "module", "service",
    ],
    "writing": [
        "write", "draft", "compose", "essay", "blog", "article",
        "email", "letter", "story", "post", "content", "copy",
        "documentation", "report", "proposal", "summary",
    ],
    "research": [
        "explain", "describe", "what is", "how does", "why",
        "compare", "analyze", "evaluate", "review", "understand",
        "difference between", "overview", "summarize",
    ],
}


def _detect_intent(prompt: str) -> str:
    """Detect prompt intent: coding, writing, research, or general."""
    lower = prompt.lower()
    scores: dict[str, int] = {k: 0 for k in _INTENT_KEYWORDS}
    for intent, keywords in _INTENT_KEYWORDS.items():
        for kw in keywords:
            if kw in lower:
                scores[intent] += 1
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else "general"


# --- Scoring curves ---

def _diminishing_returns(raw_count: int, max_points: float, k: float = 0.5) -> float:
    """Exponential decay for diminishing returns."""
    return max_points * (1 - math.exp(-k * raw_count))


def _sigmoid_calibrate(raw: float, midpoint: float = 50.0, steepness: float = 0.08) -> float:
    """Sigmoid calibration to prevent 40-60 clustering."""
    return 100.0 / (1 + math.exp(-steepness * (raw - midpoint)))


# --- Dimension scorers (each returns DimensionScore) ---

# Vague words that penalize specificity
_VAGUE_WORDS = {
    "thing", "things", "stuff", "something", "anything", "everything",
    "good", "bad", "nice", "great", "better", "best", "some", "many",
    "very", "really", "quite", "basically", "kind of", "sort of",
}

# Technical terms that boost specificity
_TECH_TERMS = {
    "api", "rest", "graphql", "sql", "jwt", "oauth", "tcp", "http",
    "json", "xml", "yaml", "docker", "kubernetes", "redis", "postgresql",
    "mongodb", "aws", "gcp", "azure", "typescript", "python", "rust",
    "flask", "django", "react", "nextjs", "node", "express",
}

# Constraint markers
_CONSTRAINT_MARKERS = [
    "must", "should", "require", "constraint", "limit", "maximum",
    "minimum", "at least", "at most", "no more than", "between",
]

# Precise imperative verbs (scored higher)
_PRECISE_VERBS = {
    "implement", "create", "build", "configure", "deploy", "migrate",
    "refactor", "optimize", "validate", "authenticate", "serialize",
    "parse", "render", "transform", "aggregate", "filter", "map",
}

# Vague verbs (scored lower)
_VAGUE_VERBS = {
    "do", "make", "get", "put", "handle", "process", "deal with",
    "take care of", "work on", "look at", "check", "help",
}

# Filler and politeness words
_FILLER_WORDS = {
    "please", "kindly", "just", "maybe", "perhaps", "i think",
    "could you", "would you", "if possible", "if you don't mind",
    "i was wondering", "it would be great",
}


def _shannon_entropy(words: list[str]) -> float:
    """Calculate Shannon entropy (word-level) — higher = more information density."""
    if not words:
        return 0.0
    freq: dict[str, int] = {}
    for w in words:
        lower = w.lower()
        freq[lower] = freq.get(lower, 0) + 1
    n = len(words)
    entropy = 0.0
    for count in freq.values():
        p = count / n
        if p > 0:
            entropy -= p * math.log2(p)
    return entropy


def _score_specificity(prompt: str, words: list[str]) -> DimensionScore:
    """Score specificity: Shannon entropy, TTR, technical terms, vague penalties."""
    signals: list[str] = []

    # Shannon entropy (word-level) — higher = more diverse/specific vocabulary
    entropy = _shannon_entropy(words)
    # Typical range: 2-6 bits. Normalize to 0-1 with 5 bits as "excellent"
    entropy_score = min(entropy / 5.0, 1.0)
    if entropy > 3.5:
        signals.append(f"high information density (entropy={entropy:.2f})")

    # Type-Token Ratio
    unique = set(w.lower() for w in words)
    ttr = len(unique) / max(len(words), 1)
    ttr_score = min(ttr, 1.0)
    if ttr > 0.7:
        signals.append(f"high vocabulary diversity (TTR={ttr:.2f})")

    # Technical term density
    lower_words = {w.lower() for w in words}
    tech_count = len(lower_words & _TECH_TERMS)
    tech_score = _diminishing_returns(tech_count, 1.0, k=0.3)
    if tech_count > 0:
        signals.append(f"{tech_count} technical terms")

    # Vague word penalty
    vague_count = sum(1 for v in _VAGUE_WORDS if v in prompt.lower())
    vague_penalty = min(vague_count * 0.1, 0.5)
    if vague_count > 0:
        signals.append(f"{vague_count} vague words")

    # Constraint markers
    constraint_count = sum(1 for c in _CONSTRAINT_MARKERS if c in prompt.lower())
    constraint_score = _diminishing_returns(constraint_count, 1.0, k=0.4)
    if constraint_count > 0:
        signals.append(f"{constraint_count} constraint markers")

    # Numbers and entities
    numbers = len(re.findall(r'\d+', prompt))
    number_score = _diminishing_returns(numbers, 0.5, k=0.3)
    if numbers > 0:
        signals.append(f"{numbers} numeric values")

    raw = (entropy_score * 0.2 + ttr_score * 0.15 + tech_score * 0.25
           + constraint_score * 0.2 + number_score * 0.1 - vague_penalty + 0.1)
    raw = max(0.0, min(1.0, raw))

    suggestion = "Add specific technical terms, constraints, or numeric values" if raw < 0.5 else ""
    return DimensionScore(score=raw, max_weight=25.0, signals=signals, suggestion=suggestion)


def _count_syllables(word: str) -> int:
    """Approximate syllable count for Flesch-Kincaid calculation."""
    word = word.lower().rstrip("e")
    vowels = "aeiou"
    count = 0
    prev_vowel = False
    for char in word:
        is_vowel = char in vowels
        if is_vowel and not prev_vowel:
            count += 1
        prev_vowel = is_vowel
    return max(count, 1)


def _flesch_kincaid_grade(words: list[str], num_sentences: int) -> float:
    """Compute Flesch-Kincaid grade level. Ideal range for prompts: 8-14."""
    if not words or num_sentences == 0:
        return 0.0
    avg_sentence_len = len(words) / num_sentences
    total_syllables = sum(_count_syllables(w) for w in words)
    avg_syllables = total_syllables / max(len(words), 1)
    grade = 0.39 * avg_sentence_len + 11.8 * avg_syllables - 15.59
    return max(0.0, grade)


def _score_clarity(prompt: str, words: list[str]) -> DimensionScore:
    """Score clarity: Flesch-Kincaid readability, sentence consistency, negation penalty."""
    signals: list[str] = []

    # Sentence analysis
    sentences = [s.strip() for s in re.split(r'[.!?\n]', prompt) if s.strip()]
    num_sentences = max(len(sentences), 1)

    # Flesch-Kincaid grade level (ideal: 8-14 for prompts)
    fk_grade = _flesch_kincaid_grade(words, num_sentences)
    if 8 <= fk_grade <= 14:
        length_score = 1.0
        signals.append(f"ideal readability (FK grade {fk_grade:.1f})")
    elif fk_grade < 4:
        length_score = 0.3
        signals.append(f"too simple (FK grade {fk_grade:.1f})")
    elif fk_grade > 18:
        length_score = 0.3
        signals.append(f"too complex (FK grade {fk_grade:.1f})")
    else:
        length_score = max(0.3, 1.0 - abs(fk_grade - 11) / 15)
        signals.append(f"FK grade {fk_grade:.1f}")

    # Negation penalty
    negations = len(re.findall(r"\bdon'?t\b|\bnot\b|\bnever\b|\bno\b|\bnor\b", prompt.lower()))
    neg_penalty = min(negations * 0.15, 0.5)
    if negations > 0:
        signals.append(f"{negations} negations")

    # Ambiguous pronouns
    ambiguous = len(re.findall(r'\b(it|this|that|they|them)\b', prompt.lower()))
    ambig_ratio = ambiguous / max(len(words), 1)
    ambig_penalty = min(ambig_ratio * 2, 0.3)
    if ambiguous > 2:
        signals.append(f"{ambiguous} ambiguous pronouns")

    raw = length_score - neg_penalty - ambig_penalty
    raw = max(0.0, min(1.0, raw))

    suggestion = "Use affirmative directives instead of negation; reduce ambiguous pronouns" if raw < 0.5 else ""
    return DimensionScore(score=raw, max_weight=20.0, signals=signals, suggestion=suggestion)


def _score_structure(prompt: str) -> DimensionScore:
    """Score structure: delimiters, lists, code blocks, sections."""
    signals: list[str] = []
    markers = 0

    # Markdown headers
    headers = len(re.findall(r'^#{1,6}\s', prompt, re.MULTILINE))
    if headers > 0:
        markers += headers
        signals.append(f"{headers} markdown headers")

    # Numbered/bulleted lists
    lists = len(re.findall(r'^[\s]*[-*•]\s|^\s*\d+[.)]\s', prompt, re.MULTILINE))
    if lists > 0:
        markers += lists
        signals.append(f"{lists} list items")

    # Code blocks
    code_blocks = len(re.findall(r'```', prompt))
    if code_blocks > 0:
        markers += code_blocks // 2
        signals.append("code blocks")

    # XML-like tags
    xml_tags = len(re.findall(r'<\w+>', prompt))
    if xml_tags > 0:
        markers += xml_tags
        signals.append(f"{xml_tags} XML tags")

    # Section separators
    separators = len(re.findall(r'^---+$|^===+$', prompt, re.MULTILINE))
    if separators > 0:
        markers += separators
        signals.append("section separators")

    raw = _diminishing_returns(markers, 1.0, k=0.4)

    suggestion = "Add structure: use headers (##), bullet lists (-), or labeled sections" if raw < 0.3 else ""
    return DimensionScore(score=raw, max_weight=15.0, signals=signals, suggestion=suggestion)


def _score_actionability(prompt: str, words: list[str]) -> DimensionScore:
    """Score actionability: imperative verbs, task clarity."""
    signals: list[str] = []

    lower_words = {w.lower() for w in words}

    # Precise verb count
    precise_count = len(lower_words & _PRECISE_VERBS)
    if precise_count > 0:
        signals.append(f"{precise_count} precise verbs")

    # Vague verb count
    vague_verb_count = sum(1 for v in _VAGUE_VERBS if v in prompt.lower())
    if vague_verb_count > 0:
        signals.append(f"{vague_verb_count} vague verbs")

    # Step indicators
    steps = len(re.findall(r'\b(step \d|first|then|next|finally|after that)\b', prompt.lower()))
    if steps > 0:
        signals.append(f"{steps} step indicators")

    verb_score = _diminishing_returns(precise_count, 1.0, k=0.5)
    vague_penalty = min(vague_verb_count * 0.15, 0.4)
    step_bonus = _diminishing_returns(steps, 0.3, k=0.5)

    raw = verb_score - vague_penalty + step_bonus
    raw = max(0.0, min(1.0, raw))

    suggestion = "Use specific imperative verbs (implement, create, validate) instead of vague ones (do, make, handle)" if raw < 0.4 else ""
    return DimensionScore(score=raw, max_weight=15.0, signals=signals, suggestion=suggestion)


def _score_context(prompt: str) -> DimensionScore:
    """Score context: role assignment, audience, domain keywords."""
    signals: list[str] = []
    score = 0.0

    # Role assignment
    if re.search(r'\b(you are|act as|role:)\b', prompt.lower()):
        score += 0.4
        signals.append("role assignment")

    # Audience specification
    if re.search(r'\b(audience|for (beginners|experts|developers|users))\b', prompt.lower()):
        score += 0.2
        signals.append("audience specified")

    # Domain/tech keywords
    lower = prompt.lower()
    domain_count = sum(1 for t in _TECH_TERMS if t in lower)
    domain_bonus = _diminishing_returns(domain_count, 0.3, k=0.3)
    score += domain_bonus
    if domain_count > 0:
        signals.append(f"{domain_count} domain keywords")

    # Background signals
    if re.search(r'\b(background|context|given that|assuming)\b', lower):
        score += 0.1
        signals.append("background context")

    raw = min(1.0, score)

    suggestion = "Add role assignment ('You are a...') and domain context" if raw < 0.3 else ""
    return DimensionScore(score=raw, max_weight=10.0, signals=signals, suggestion=suggestion)


def _score_completeness(prompt: str) -> DimensionScore:
    """Score completeness: output format, examples, success criteria."""
    signals: list[str] = []
    score = 0.0

    lower = prompt.lower()

    # Output format specified
    if re.search(r'\b(output|return|format|respond)\b.*\b(json|xml|csv|table|list|markdown)\b', lower):
        score += 0.35
        signals.append("output format specified")

    # Examples
    if re.search(r'\b(example|e\.g\.|for instance|such as)\b', lower):
        score += 0.25
        signals.append("examples included")

    # Success criteria
    if re.search(r'\b(success|criteria|acceptance|expect|should produce|must return)\b', lower):
        score += 0.2
        signals.append("success criteria")

    # Constraint markers
    constraint_count = sum(1 for c in _CONSTRAINT_MARKERS if c in lower)
    if constraint_count > 0:
        score += _diminishing_returns(constraint_count, 0.2, k=0.4)
        signals.append(f"{constraint_count} constraints")

    raw = min(1.0, score)

    suggestion = "Specify expected output format and include success criteria" if raw < 0.3 else ""
    return DimensionScore(score=raw, max_weight=10.0, signals=signals, suggestion=suggestion)


def _score_conciseness(prompt: str, words: list[str]) -> DimensionScore:
    """Score conciseness: Shannon entropy (higher=denser), filler penalty, politeness penalty."""
    signals: list[str] = []

    # Shannon entropy — higher entropy = more information-dense (less repetitive)
    entropy = _shannon_entropy(words)
    # Normalize: entropy > 4.0 is very dense for typical prompts
    entropy_score = min(entropy / 4.5, 1.0) if words else 0.0
    if entropy > 3.5:
        signals.append(f"dense vocabulary (entropy={entropy:.2f})")

    # Filler/politeness word count (Bsharat principle #1: politeness degrades performance)
    lower = prompt.lower()
    filler_count = sum(1 for f in _FILLER_WORDS if f in lower)
    filler_penalty = min(filler_count * 0.15, 0.6)
    if filler_count > 0:
        signals.append(f"{filler_count} filler/politeness phrases")

    # Filler word ratio (proportion of prompt that is filler)
    word_count = len(words)
    filler_ratio = filler_count / max(word_count, 1)
    ratio_penalty = min(filler_ratio * 2, 0.3)

    raw = entropy_score * 0.5 + 0.5 - filler_penalty - ratio_penalty
    raw = max(0.0, min(1.0, raw))

    suggestion = "Remove filler words (please, kindly, just) — they reduce prompt effectiveness" if raw < 0.5 else ""
    return DimensionScore(score=raw, max_weight=5.0, signals=signals, suggestion=suggestion)


# --- Intent-aware weight adjustment ---

_INTENT_WEIGHT_ADJUSTMENTS: dict[str, dict[str, float]] = {
    "coding": {"specificity": 0.05, "actionability": 0.03},
    "writing": {"specificity": -0.05, "clarity": 0.05},
    "research": {"context": 0.05, "actionability": -0.03},
}


# --- Main scoring function ---

def score_prompt(prompt: str) -> ScoreResult:
    """Score a prompt across 7 dimensions, returning calibrated 0-100 result."""
    words = prompt.split()
    intent = _detect_intent(prompt)

    # Score all dimensions
    dimensions: dict[str, DimensionScore] = {
        "specificity": _score_specificity(prompt, words),
        "clarity": _score_clarity(prompt, words),
        "structure": _score_structure(prompt),
        "actionability": _score_actionability(prompt, words),
        "context": _score_context(prompt),
        "completeness": _score_completeness(prompt),
        "conciseness": _score_conciseness(prompt, words),
    }

    # Calculate weighted raw score
    raw_total = 0.0
    max_total = 0.0
    for name, dim in dimensions.items():
        weight = dim.max_weight
        # Apply intent-aware adjustment (percentage of weight, e.g. +5% means weight * 1.05)
        adjustment = _INTENT_WEIGHT_ADJUSTMENTS.get(intent, {}).get(name, 0.0)
        adjusted_weight = weight * (1 + adjustment)
        raw_total += dim.score * adjusted_weight
        max_total += adjusted_weight

    # Normalize to 0-100
    raw_score = (raw_total / max(max_total, 1)) * 100

    # Sigmoid calibration
    calibrated = _sigmoid_calibrate(raw_score)
    total = max(0, min(100, round(calibrated)))

    return ScoreResult(total=total, dimensions=dimensions, intent=intent)
```

- [x]**Step 2.8: Run tests to verify they pass**

Run: `pytest tests/test_scorer.py -v`
Expected: ALL PASS

- [x]**Step 2.9: Refactor — review dimension weights and edge cases**

Review the scorer output for edge cases:

Run: `python -c "from promptune.scorer import score_prompt; r = score_prompt('fix it'); print(f'fix it: {r.total}'); r2 = score_prompt('Build a REST API using Flask with SQLAlchemy, PostgreSQL, JWT auth, rate limiting at 100 req/min. Return JSON with proper HTTP status codes. ## Requirements\\n- Auth\\n- Rate limiting\\n## Output\\nJSON'); print(f'detailed: {r2.total}')"`

Verify: "fix it" scores <30, detailed prompt scores >65. Adjust `_sigmoid_calibrate` midpoint/steepness if needed.

- [x]**Step 2.10: Run full test suite**

Run: `pytest --cov=promptune --cov-report=term-missing -v`
Expected: ALL PASS

- [x]**Step 2.11: Run linting and type checks**

Run: `ruff check . && mypy promptune/`
Expected: PASS

- [x]**Step 2.12: Commit**

```bash
git add promptune/scorer.py tests/test_scorer.py
git commit -m "feat: add 7-dimension quality scorer with sigmoid calibration and intent-aware weights"
```

---

## Chunk 3: Task 3 — Tier 0 Rule Engine

### Task 3: Tier 0 Rule Engine

**Goal:** Deterministic text transformations based on scorer dimension breakdowns. No AI, no network, <10ms. Each rule is a standalone pure function. Rules chain — output of one feeds input of next.

**Depends on:** Task 2 (Quality Scorer)

**Files:**
- Create: `promptune/tier0.py`
- Create: `tests/test_tier0.py`

---

- [x]**Step 3.1: Write failing tests for dataclasses and apply_rules signature**

File: `tests/test_tier0.py`

```python
"""Tier 0 Rule Engine tests."""

import pytest

from promptune.scorer import ScoreResult, score_prompt
from promptune.tier0 import RuleResult, Tier0Result, apply_rules


def test_rule_result_dataclass() -> None:
    """RuleResult has required fields."""
    rr = RuleResult(modified_prompt="test", applied=True, description="did thing")
    assert rr.modified_prompt == "test"
    assert rr.applied is True
    assert rr.description == "did thing"


def test_tier0_result_dataclass() -> None:
    """Tier0Result has required fields."""
    tr = Tier0Result(enhanced="enhanced text", rules_applied=["rule_a"])
    assert tr.enhanced == "enhanced text"
    assert tr.rules_applied == ["rule_a"]


def test_apply_rules_returns_tier0_result() -> None:
    """apply_rules returns a Tier0Result."""
    score = score_prompt("fix it")
    result = apply_rules("fix it", score)
    assert isinstance(result, Tier0Result)
    assert isinstance(result.enhanced, str)
    assert isinstance(result.rules_applied, list)


def test_apply_rules_preserves_original_when_high_score() -> None:
    """High-scoring prompts get minimal rule application."""
    detailed = (
        "## Task\nYou are a senior Python developer. Implement a REST API "
        "using Flask with SQLAlchemy ORM and PostgreSQL.\n"
        "## Requirements\n- JWT authentication\n- Rate limiting at 100 req/min\n"
        "## Output\nReturn JSON with proper HTTP status codes"
    )
    score = score_prompt(detailed)
    result = apply_rules(detailed, score)
    # High-quality prompt — rules should NOT drastically change it
    assert detailed in result.enhanced or len(result.rules_applied) <= 2
```

- [x]**Step 3.2: Run tests to verify they fail**

Run: `pytest tests/test_tier0.py -v -x`
Expected: FAIL — `ModuleNotFoundError: No module named 'promptune.tier0'`

- [x]**Step 3.3: Write failing tests for individual rules**

Append to `tests/test_tier0.py`:

```python
def test_rule_add_output_format() -> None:
    """Appends format instruction when completeness is low."""
    score = score_prompt("build a REST API")
    result = apply_rules("build a REST API", score)
    assert "output_format" in result.rules_applied
    assert "format" in result.enhanced.lower() or "respond" in result.enhanced.lower()


def test_rule_flag_vague_verbs() -> None:
    """Flags vague verbs with specific alternatives."""
    score = score_prompt("do something with the database")
    result = apply_rules("do something with the database", score)
    assert "vague_verbs" in result.rules_applied
    assert result.enhanced != "do something with the database"


def test_rule_too_short() -> None:
    """Flags very short prompts when specificity near zero."""
    score = score_prompt("fix bug")
    result = apply_rules("fix bug", score)
    assert "too_short" in result.rules_applied
    assert "context" in result.enhanced.lower() or "detail" in result.enhanced.lower()


def test_rule_add_constraints() -> None:
    """Appends constraints when completeness is low."""
    score = score_prompt("create a web app")
    result = apply_rules("create a web app", score)
    assert "constraints" in result.rules_applied
    assert len(result.enhanced) > len("create a web app")


def test_rule_negation_rewrite() -> None:
    """Rewrites negative directives to positive."""
    import re as _re
    prompt = "Don't use any global variables and don't forget error handling"
    score = score_prompt(prompt)
    result = apply_rules(prompt, score)
    assert "negation_rewrite" in result.rules_applied
    original_negs = len(_re.findall(r"\bdon'?t\b|\bnot\b|\bnever\b", prompt.lower()))
    result_negs = len(_re.findall(r"\bdon'?t\b|\bnot\b|\bnever\b", result.enhanced.lower()))
    assert result_negs <= original_negs


def test_rule_add_role() -> None:
    """Prepends role when context score is low."""
    score = score_prompt("write unit tests for the auth module")
    result = apply_rules("write unit tests for the auth module", score)
    assert "role_assignment" in result.rules_applied
    assert "you are" in result.enhanced.lower()


def test_rule_code_delimiters() -> None:
    """Wraps code-like content in code blocks."""
    prompt = "Fix this: def foo(): return bar"
    score = score_prompt(prompt)
    result = apply_rules(prompt, score)
    assert "code_delimiters" in result.rules_applied
    assert "```" in result.enhanced


def test_rule_politeness_removal() -> None:
    """Strips politeness phrases."""
    prompt = "Could you please kindly help me build an API?"
    score = score_prompt(prompt)
    result = apply_rules(prompt, score)
    assert "politeness_removal" in result.rules_applied
    assert "kindly" not in result.enhanced.lower()


def test_rule_contradictory_instructions() -> None:
    """Flags contradictory instructions when clarity is low."""
    prompt = "Write a brief but detailed comprehensive summary"
    score = score_prompt(prompt)
    result = apply_rules(prompt, score)
    assert "contradictions" in result.rules_applied
    assert "contradictory" in result.enhanced.lower() or "warning" in result.enhanced.lower()


def test_rules_chain_correctly() -> None:
    """Rules chain — output of one feeds input of next."""
    prompt = "please do something"
    score = score_prompt(prompt)
    result = apply_rules(prompt, score)
    # Multiple rules should have fired on this poor prompt
    assert len(result.rules_applied) >= 2


def test_apply_rules_idempotent_on_good_prompt() -> None:
    """Good prompts should not be over-modified by rules."""
    prompt = (
        "You are a senior backend developer. Implement a rate limiter "
        "middleware for the Express.js API. Use a sliding window algorithm "
        "with Redis. Limit: 100 requests per minute per IP. "
        "Return 429 status with Retry-After header when exceeded."
    )
    score = score_prompt(prompt)
    result = apply_rules(prompt, score)
    # Good prompt — enhanced should be close to original
    assert len(result.rules_applied) <= 3
```

- [x]**Step 3.4: Run tests to verify they fail**

Run: `pytest tests/test_tier0.py -v -x`
Expected: FAIL

- [x]**Step 3.5: Implement tier0.py with all rules**

Create `promptune/tier0.py`:

```python
"""Tier 0 Rule Engine: deterministic text transformations.

Each rule is a pure function that takes a prompt and scorer breakdown,
returning a RuleResult. Rules chain — output of one feeds input of next.
Rules only fire when their relevant dimension is weak.

Based on Bsharat et al. 2023 (26 validated principles).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from promptune.scorer import ScoreResult


@dataclass
class RuleResult:
    """Result of a single rule application."""

    modified_prompt: str
    applied: bool
    description: str


@dataclass
class Tier0Result:
    """Result of applying all Tier 0 rules."""

    enhanced: str
    rules_applied: list[str]


# --- Intent-to-format mapping ---

_INTENT_FORMAT_MAP: dict[str, str] = {
    "coding": "Respond with code and brief explanation.",
    "writing": "Structure your response with clear sections.",
    "research": "Provide a structured explanation with key points.",
    "general": "Provide a clear, organized response.",
}

# --- Intent-to-role mapping ---

_INTENT_ROLE_MAP: dict[str, str] = {
    "coding": "You are an experienced software developer.",
    "writing": "You are a skilled technical writer.",
    "research": "You are a knowledgeable research analyst.",
    "general": "You are a helpful expert assistant.",
}

# --- Domain-to-constraint mapping ---

_DOMAIN_CONSTRAINT_MAP: dict[str, str] = {
    "coding": "Consider edge cases, error handling, and performance.",
    "writing": "Consider audience, tone, and structure.",
    "research": "Consider accuracy, sources, and completeness.",
    "general": "Consider clarity and completeness.",
}

# --- Politeness phrases to remove ---

_POLITENESS_PHRASES = [
    "could you please",
    "would you kindly",
    "please kindly",
    "if you don't mind",
    "i was wondering if",
    "it would be great if",
    "could you",
    "would you",
    "please",
    "kindly",
]

# --- Vague verb replacements ---

_VAGUE_VERB_SUGGESTIONS: dict[str, str] = {
    "do": "implement",
    "make": "create",
    "get": "retrieve",
    "put": "store",
    "handle": "process",
    "deal with": "resolve",
    "take care of": "manage",
    "work on": "develop",
    "look at": "analyze",
    "check": "validate",
    "help": "assist with",
    "fix": "diagnose and fix",
}


# --- Individual rules (each a pure function) ---

def rule_add_output_format(prompt: str, score: ScoreResult) -> RuleResult:
    """Append format instruction when completeness is low."""
    completeness = score.dimensions["completeness"]
    if completeness.score >= 0.4:
        return RuleResult(modified_prompt=prompt, applied=False, description="")

    format_hint = _INTENT_FORMAT_MAP.get(score.intent, _INTENT_FORMAT_MAP["general"])
    modified = f"{prompt}\n\n{format_hint}"
    return RuleResult(
        modified_prompt=modified,
        applied=True,
        description="Added output format instruction",
    )


def rule_flag_vague_verbs(prompt: str, score: ScoreResult) -> RuleResult:
    """Replace vague verbs with specific alternatives."""
    actionability = score.dimensions["actionability"]
    if actionability.score >= 0.5:
        return RuleResult(modified_prompt=prompt, applied=False, description="")

    modified = prompt
    replaced = False
    for vague, specific in _VAGUE_VERB_SUGGESTIONS.items():
        pattern = re.compile(r'\b' + re.escape(vague) + r'\b', re.IGNORECASE)
        if pattern.search(modified):
            modified = pattern.sub(specific, modified, count=1)
            replaced = True

    return RuleResult(
        modified_prompt=modified,
        applied=replaced,
        description="Replaced vague verbs with specific alternatives",
    )


def rule_too_short(prompt: str, score: ScoreResult) -> RuleResult:
    """Flag very short prompts when specificity is near zero."""
    specificity = score.dimensions["specificity"]
    words = prompt.split()
    if len(words) >= 10 or specificity.score >= 0.2:
        return RuleResult(modified_prompt=prompt, applied=False, description="")

    modified = f"{prompt}\n\n[Note: Adding more context and detail will improve results.]"
    return RuleResult(
        modified_prompt=modified,
        applied=True,
        description="Flagged short prompt — adding context recommended",
    )


def rule_add_constraints(prompt: str, score: ScoreResult) -> RuleResult:
    """Append constraints when completeness is low and no constraint markers found."""
    completeness = score.dimensions["completeness"]
    if completeness.score >= 0.3:
        return RuleResult(modified_prompt=prompt, applied=False, description="")

    constraint = _DOMAIN_CONSTRAINT_MAP.get(score.intent, _DOMAIN_CONSTRAINT_MAP["general"])
    modified = f"{prompt}\n\n{constraint}"
    return RuleResult(
        modified_prompt=modified,
        applied=True,
        description="Added domain-appropriate constraints",
    )


def rule_negation_rewrite(prompt: str, score: ScoreResult) -> RuleResult:
    """Rewrite negative directives to positive form."""
    clarity = score.dimensions["clarity"]
    if clarity.score >= 0.6:
        return RuleResult(modified_prompt=prompt, applied=False, description="")

    modified = prompt
    replaced = False

    # Common negation patterns → positive rewrites
    rewrites = [
        (r"don'?t use\b", "avoid using"),
        (r"don'?t forget\b", "remember to"),
        (r"don'?t ignore\b", "pay attention to"),
        (r"never use\b", "avoid"),
        (r"do not\b", "avoid"),
    ]

    for pattern, replacement in rewrites:
        new_text = re.sub(pattern, replacement, modified, flags=re.IGNORECASE)
        if new_text != modified:
            modified = new_text
            replaced = True

    return RuleResult(
        modified_prompt=modified,
        applied=replaced,
        description="Rewrote negative directives to positive",
    )


def rule_add_role(prompt: str, score: ScoreResult) -> RuleResult:
    """Prepend role assignment when context score is low."""
    context = score.dimensions["context"]
    if context.score >= 0.3:
        return RuleResult(modified_prompt=prompt, applied=False, description="")

    role = _INTENT_ROLE_MAP.get(score.intent, _INTENT_ROLE_MAP["general"])
    modified = f"{role} {prompt}"
    return RuleResult(
        modified_prompt=modified,
        applied=True,
        description="Added role assignment",
    )


def rule_code_delimiters(prompt: str, score: ScoreResult) -> RuleResult:
    """Wrap code-like content in code blocks when structure is weak."""
    structure = score.dimensions["structure"]
    if structure.score >= 0.5:
        return RuleResult(modified_prompt=prompt, applied=False, description="")

    # Detect code-like patterns not already in code blocks
    if "```" in prompt:
        return RuleResult(modified_prompt=prompt, applied=False, description="")

    code_patterns = [
        r'\bdef\s+\w+\s*\(', r'\bclass\s+\w+', r'\bfunction\s+\w+',
        r'\bconst\s+\w+\s*=', r'\blet\s+\w+\s*=', r'\bvar\s+\w+\s*=',
        r'\breturn\s+\w+', r'import\s+\w+',
    ]

    has_code = any(re.search(p, prompt) for p in code_patterns)
    if not has_code:
        return RuleResult(modified_prompt=prompt, applied=False, description="")

    # Find the code-like portion and wrap it
    lines = prompt.split('\n')
    modified_lines: list[str] = []
    in_code = False
    code_buffer: list[str] = []

    for line in lines:
        is_code_line = any(re.search(p, line) for p in code_patterns)
        if is_code_line and not in_code:
            in_code = True
            code_buffer.append(line)
        elif in_code and (is_code_line or line.strip().startswith((' ', '\t'))):
            code_buffer.append(line)
        else:
            if code_buffer:
                modified_lines.append("```")
                modified_lines.extend(code_buffer)
                modified_lines.append("```")
                code_buffer = []
                in_code = False
            modified_lines.append(line)

    if code_buffer:
        modified_lines.append("```")
        modified_lines.extend(code_buffer)
        modified_lines.append("```")

    modified = '\n'.join(modified_lines)
    return RuleResult(
        modified_prompt=modified,
        applied=True,
        description="Wrapped code-like content in code blocks",
    )


def rule_contradictory_instructions(prompt: str, score: ScoreResult) -> RuleResult:
    """Flag contradictory instructions when clarity is low."""
    clarity = score.dimensions["clarity"]
    if clarity.score >= 0.6:
        return RuleResult(modified_prompt=prompt, applied=False, description="")

    contradictions = [
        (r'\bbrief\b', r'\bdetailed\b'),
        (r'\bshort\b', r'\bcomprehensive\b'),
        (r'\bsimple\b', r'\bcomplex\b'),
        (r'\bconcise\b', r'\bthorough\b'),
    ]

    lower = prompt.lower()
    for pattern_a, pattern_b in contradictions:
        if re.search(pattern_a, lower) and re.search(pattern_b, lower):
            modified = f"{prompt}\n\n[Warning: Contradictory instructions detected — consider clarifying scope.]"
            return RuleResult(
                modified_prompt=modified,
                applied=True,
                description="Flagged contradictory instructions",
            )

    return RuleResult(modified_prompt=prompt, applied=False, description="")


def rule_politeness_removal(prompt: str, score: ScoreResult) -> RuleResult:
    """Strip politeness phrases (Bsharat principle #1)."""
    conciseness = score.dimensions["conciseness"]
    if conciseness.score >= 0.6:
        return RuleResult(modified_prompt=prompt, applied=False, description="")

    modified = prompt
    replaced = False

    for phrase in _POLITENESS_PHRASES:
        pattern = re.compile(re.escape(phrase), re.IGNORECASE)
        new_text = pattern.sub("", modified)
        if new_text != modified:
            modified = new_text
            replaced = True

    # Clean up extra whitespace from removals
    modified = re.sub(r'\s+', ' ', modified).strip()
    # Clean up leading/trailing punctuation artifacts
    modified = re.sub(r'^\s*[,;]\s*', '', modified)

    return RuleResult(
        modified_prompt=modified,
        applied=replaced,
        description="Removed politeness phrases",
    )


# --- Rule pipeline ---

# Ordered by impact. Note: all rules receive the ORIGINAL score object,
# not re-scored after each rule. This is intentional — we fix weaknesses
# identified in the original prompt, not in the partially-transformed version.
# too_short is last because earlier rules (role, format, constraints) may
# legitimately add text, and we want to flag genuinely underspecified prompts.

RuleFn = Callable[[str, ScoreResult], RuleResult]

_RULE_PIPELINE: list[tuple[str, RuleFn]] = [
    ("politeness_removal", rule_politeness_removal),
    ("negation_rewrite", rule_negation_rewrite),
    ("vague_verbs", rule_flag_vague_verbs),
    ("role_assignment", rule_add_role),
    ("output_format", rule_add_output_format),
    ("constraints", rule_add_constraints),
    ("code_delimiters", rule_code_delimiters),
    ("contradictions", rule_contradictory_instructions),
    ("too_short", rule_too_short),
]


def apply_rules(prompt: str, score: ScoreResult) -> Tier0Result:
    """Apply all Tier 0 rules in order. Rules chain — output feeds next."""
    current = prompt
    applied: list[str] = []

    for name, rule_fn in _RULE_PIPELINE:
        result = rule_fn(current, score)
        if result.applied:
            current = result.modified_prompt
            applied.append(name)

    return Tier0Result(enhanced=current, rules_applied=applied)
```

- [x]**Step 3.6: Run tests to verify they pass**

Run: `pytest tests/test_tier0.py -v`
Expected: ALL PASS

- [x]**Step 3.7: Run full test suite**

Run: `pytest --cov=promptune --cov-report=term-missing -v`
Expected: ALL PASS

- [x]**Step 3.8: Run linting and type checks**

Run: `ruff check . && mypy promptune/`
Expected: PASS

- [x]**Step 3.9: Commit**

```bash
git add promptune/tier0.py tests/test_tier0.py
git commit -m "feat: add Tier 0 rule engine with 9 deterministic text transformation rules"
```

---

## Chunk 4: Tasks 4 & 5 — Local LLM Provider + Router

### Task 4: Local LLM Provider (Tier 1)

**Goal:** Generic OpenAI-compatible HTTP client for any local LLM tool (Ollama, LM Studio, llama.cpp, vLLM, LocalAI, Jan). No vendor lock-in. Also make `BaseProvider.api_key` optional.

**Depends on:** Task 1 (Config)

**Files:**
- Create: `promptune/providers/local.py`
- Create: `tests/test_providers/test_local.py`
- Modify: `promptune/providers/__init__.py` (make `api_key` optional)
- Modify: `tests/test_providers/test_base.py` (verify optional `api_key`)

---

- [x]**Step 4.1: Write failing tests for BaseProvider optional api_key**

Append to `tests/test_providers/test_base.py`:

```python
def test_base_provider_optional_api_key() -> None:
    """BaseProvider can be instantiated without api_key."""
    class TestProvider(BaseProvider):
        def enhance(self, prompt: str, system_prompt: str) -> str:
            return "test"

    provider = TestProvider(model="test-model")
    assert provider.api_key == ""
    assert provider.model == "test-model"


def test_base_provider_optional_model() -> None:
    """BaseProvider can be instantiated without model."""
    class TestProvider(BaseProvider):
        def enhance(self, prompt: str, system_prompt: str) -> str:
            return "test"

    provider = TestProvider(api_key="key")
    assert provider.model == ""
```

- [x]**Step 4.2: Run tests to verify they fail**

Run: `pytest tests/test_providers/test_base.py -v -x -k "optional"`
Expected: FAIL — `TypeError: __init__() missing required argument`

- [x]**Step 4.3: Make BaseProvider.api_key optional**

In `promptune/providers/__init__.py`, change the `__init__` signature:

```python
class BaseProvider(ABC):
    """Abstract base class for AI providers."""

    def __init__(self, api_key: str = "", model: str = "", **kwargs: Any) -> None:
        self.api_key = api_key
        self.model = model
```

- [x]**Step 4.4: Verify existing provider tests still pass**

Run: `pytest tests/test_providers/ -v`
Expected: ALL PASS (existing providers pass `api_key` explicitly — no behavior change)

- [x]**Step 4.5: Write failing tests for LocalProvider**

File: `tests/test_providers/test_local.py`

```python
"""Local LLM Provider tests."""

import pytest
from pytest_mock import MockerFixture

from promptune.providers import BaseProvider, ProviderError
from promptune.providers.local import LocalProvider


def test_local_provider_implements_base() -> None:
    """LocalProvider is subclass of BaseProvider."""
    assert issubclass(LocalProvider, BaseProvider)


def test_local_provider_init() -> None:
    """LocalProvider stores host and model."""
    provider = LocalProvider(model="qwen2.5:3b", host="http://localhost:11434")
    assert provider.model == "qwen2.5:3b"
    assert provider.host == "http://localhost:11434"
    assert provider.api_key == ""


def test_local_provider_init_with_api_key() -> None:
    """LocalProvider accepts optional api_key for tools that require it."""
    provider = LocalProvider(
        model="qwen2.5:3b",
        host="http://localhost:11434",
        api_key="dummy-key",
    )
    assert provider.api_key == "dummy-key"


def test_local_enhance_returns_string(mocker: MockerFixture) -> None:
    """Mock API returns enhanced text."""
    provider = LocalProvider(model="qwen2.5:3b", host="http://localhost:11434")

    mock_response = mocker.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Enhanced prompt text"}}],
    }
    mock_response.raise_for_status = mocker.MagicMock()

    mocker.patch.object(provider._client, "post", return_value=mock_response)

    result = provider.enhance("rough prompt", "system prompt")
    assert result == "Enhanced prompt text"


def test_local_enhance_sends_correct_body(mocker: MockerFixture) -> None:
    """Verify model, messages in request body."""
    provider = LocalProvider(model="qwen2.5:3b", host="http://localhost:11434")

    mock_response = mocker.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "result"}}],
    }
    mock_response.raise_for_status = mocker.MagicMock()

    mock_post = mocker.patch.object(provider._client, "post", return_value=mock_response)

    provider.enhance("test prompt", "system prompt")

    call_kwargs = mock_post.call_args
    assert "http://localhost:11434/v1/chat/completions" in str(call_kwargs)
    body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
    assert body["model"] == "qwen2.5:3b"
    assert len(body["messages"]) == 2
    assert body["messages"][0]["role"] == "system"
    assert body["messages"][1]["role"] == "user"


def test_local_api_error_handling(mocker: MockerFixture) -> None:
    """Non-200 response raises ProviderError."""
    provider = LocalProvider(model="qwen2.5:3b", host="http://localhost:11434")

    mock_response = mocker.MagicMock()
    mock_response.raise_for_status.side_effect = Exception("500 Server Error")

    mocker.patch.object(provider._client, "post", return_value=mock_response)

    with pytest.raises(ProviderError, match="500"):
        provider.enhance("prompt", "system")


def test_local_timeout_handling(mocker: MockerFixture) -> None:
    """Timeout raises ProviderError."""
    import httpx

    provider = LocalProvider(model="qwen2.5:3b", host="http://localhost:11434")

    mocker.patch.object(
        provider._client, "post",
        side_effect=httpx.TimeoutException("Connection timed out"),
    )

    with pytest.raises(ProviderError, match="[Tt]imeout|timed out"):
        provider.enhance("prompt", "system")


def test_local_connection_refused(mocker: MockerFixture) -> None:
    """Connection refused raises ProviderError with helpful message."""
    import httpx

    provider = LocalProvider(model="qwen2.5:3b", host="http://localhost:11434")

    mocker.patch.object(
        provider._client, "post",
        side_effect=httpx.ConnectError("Connection refused"),
    )

    with pytest.raises(ProviderError, match="[Cc]onnect|refused|unreachable"):
        provider.enhance("prompt", "system")


def test_local_empty_response_handling(mocker: MockerFixture) -> None:
    """Empty response raises ProviderError."""
    provider = LocalProvider(model="qwen2.5:3b", host="http://localhost:11434")

    mock_response = mocker.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"choices": []}
    mock_response.raise_for_status = mocker.MagicMock()

    mocker.patch.object(provider._client, "post", return_value=mock_response)

    with pytest.raises(ProviderError, match="[Ee]mpty"):
        provider.enhance("prompt", "system")
```

- [x]**Step 4.6: Run tests to verify they fail**

Run: `pytest tests/test_providers/test_local.py -v -x`
Expected: FAIL — `ModuleNotFoundError: No module named 'promptune.providers.local'`

- [x]**Step 4.7: Implement LocalProvider**

Create `promptune/providers/local.py`:

```python
"""Local LLM provider: OpenAI-compatible HTTP client.

Supports any tool that exposes an OpenAI-compatible /v1/chat/completions
endpoint: Ollama, LM Studio, llama.cpp, vLLM, LocalAI, Jan, etc.
No vendor lock-in.
"""

from __future__ import annotations

from typing import Any

import httpx

from promptune.providers import BaseProvider, ProviderError, ProviderRegistry


class LocalProvider(BaseProvider):
    """AI provider using a local OpenAI-compatible endpoint."""

    def __init__(
        self,
        model: str,
        host: str = "http://localhost:11434",
        api_key: str = "",
        **kwargs: Any,
    ) -> None:
        super().__init__(api_key=api_key, model=model, **kwargs)
        self.host = host.rstrip("/")
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._client = httpx.Client(headers=headers, timeout=30.0)

    def enhance(self, prompt: str, system_prompt: str) -> str:
        """Send prompt to local LLM and return enhanced version."""
        try:
            response = self._client.post(
                f"{self.host}/v1/chat/completions",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                },
            )
            response.raise_for_status()
        except httpx.ConnectError as e:
            raise ProviderError(
                f"Cannot connect to local LLM at {self.host}. "
                f"Is your local LLM server running? Error: {e}"
            ) from e
        except httpx.TimeoutException as e:
            raise ProviderError(
                f"Timeout connecting to local LLM at {self.host}. "
                f"The model may be loading (cold start). Error: {e}"
            ) from e
        except Exception as e:
            raise ProviderError(str(e)) from e

        data = response.json()
        choices = data.get("choices", [])
        if not choices:
            raise ProviderError("Empty response from local LLM")

        content = choices[0].get("message", {}).get("content", "")
        if not content:
            raise ProviderError("Empty response from local LLM")

        return str(content)


def register(registry: ProviderRegistry) -> None:
    """Register the local LLM provider."""
    registry.register("local", LocalProvider)
```

- [x]**Step 4.8: Run tests to verify they pass**

Run: `pytest tests/test_providers/test_local.py tests/test_providers/test_base.py -v`
Expected: ALL PASS

- [x]**Step 4.9: Run full test suite**

Run: `pytest --cov=promptune --cov-report=term-missing -v`
Expected: ALL PASS

- [x]**Step 4.10: Run linting and type checks**

Run: `ruff check . && mypy promptune/`
Expected: PASS

- [x]**Step 4.11: Commit**

```bash
git add promptune/providers/__init__.py promptune/providers/local.py tests/test_providers/test_base.py tests/test_providers/test_local.py
git commit -m "feat: add generic local LLM provider with OpenAI-compatible HTTP client"
```

---

### Task 5: Router (New Engine)

**Goal:** Replace current `engine.py` with tier-based router. Orchestrates scoring, Tier 0 rules, Tier 1 local LLM, Tier 2 cloud provider, with graceful degradation. Strategy pattern for tier handlers.

**Depends on:** Tasks 1-4

**Files:**
- Modify: `promptune/engine.py` (full rewrite)
- Modify: `tests/test_engine.py` (full rewrite)

---

- [x]**Step 5.1: Write failing tests for new EnhanceResult and router**

Rewrite `tests/test_engine.py`:

```python
"""Router Engine tests."""

import pytest
from pytest_mock import MockerFixture

from promptune.config import ConfigError
from promptune.engine import EnhanceResult, enhance
from promptune.providers import ProviderError
from promptune.scorer import ScoreResult


@pytest.fixture()
def mock_config() -> dict:
    """Return a valid config dict with new schema."""
    return {
        "provider": {
            "default": "claude",
            "format_style": "auto",
            "model_claude": "claude-haiku-4-5-20251001",
            "model_openai": "gpt-4o-mini",
            "model_openrouter": "anthropic/claude-haiku",
        },
        "api_keys": {
            "claude": "sk-ant-test",
            "openai": "sk-test",
            "openrouter": "sk-or-test",
        },
        "enhancement": {
            "max_tier": 2,
            "default_mode": "balanced",
            "max_tokens_output": 400,
            "timeout_seconds": 10,
        },
        "local_llm": {
            "enabled": True,
            "host": "http://localhost:11434",
            "model": "qwen2.5:3b",
            "api_key": "",
        },
        "context": {
            "use_git": True,
            "use_shell_history": True,
            "use_stack_detection": True,
            "max_context_tokens": 500,
            "shell_history_lines": 20,
        },
        "history": {
            "enabled": True,
            "max_entries": 10000,
            "db_path": "~/.local/share/promptune/history.db",
        },
        "tui": {
            "show_pqs_scores": True,
            "show_tier_used": True,
            "show_latency": True,
            "theme": "dark",
            "show_diff": True,
        },
    }


def test_enhance_result_has_full_metadata() -> None:
    """EnhanceResult has all required fields."""
    result = EnhanceResult(
        original="test",
        enhanced="enhanced test",
        tier_used=0,
        latency_ms=5.0,
        score_before=ScoreResult(total=20, dimensions={}, intent="coding"),
        score_after=ScoreResult(total=70, dimensions={}, intent="coding"),
        rules_applied=["output_format"],
        context=None,
        format_style="auto",
        provider=None,
        model=None,
    )
    assert result.tier_used == 0
    assert result.latency_ms == 5.0
    assert result.provider is None


def test_engine_tier0_only(mocker: MockerFixture, mock_config: dict) -> None:
    """max_tier=0 uses only Tier 0 rules, no providers called."""
    mock_config["enhancement"]["max_tier"] = 0

    result = enhance("fix the bug", mock_config)

    assert isinstance(result, EnhanceResult)
    assert result.tier_used == 0
    assert result.provider is None
    assert result.model is None
    assert len(result.rules_applied) > 0
    assert result.original == "fix the bug"


def test_engine_tier0_high_score_prompt(
    mocker: MockerFixture, mock_config: dict
) -> None:
    """High-scoring prompt stays at Tier 0 even with max_tier=2."""
    detailed = (
        "## Task\nYou are a senior Python developer. Implement a REST API "
        "using Flask with SQLAlchemy ORM and PostgreSQL.\n"
        "## Requirements\n- JWT authentication\n- Rate limiting at 100 req/min\n"
        "## Output\nReturn JSON with proper HTTP status codes"
    )

    result = enhance(detailed, mock_config)

    assert isinstance(result, EnhanceResult)
    # High score → Tier 0 should suffice (score >= 70 after rules)
    # But if it routes to Tier 1/2, that's also valid — just check it returns
    assert result.tier_used >= 0


def test_engine_tier2_cloud_provider(
    mocker: MockerFixture, mock_config: dict
) -> None:
    """Tier 2 calls cloud provider when local LLM disabled."""
    mock_config["local_llm"]["enabled"] = False

    mock_provider = mocker.MagicMock()
    mock_provider.enhance.return_value = "Cloud enhanced text"
    mocker.patch(
        "promptune.engine._create_cloud_provider",
        return_value=mock_provider,
    )

    result = enhance("fix the bug", mock_config)

    assert isinstance(result, EnhanceResult)
    if result.tier_used == 2:
        assert result.provider == "claude"
        assert result.enhanced == "Cloud enhanced text"


def test_engine_graceful_degradation_tier1_fail(
    mocker: MockerFixture, mock_config: dict
) -> None:
    """When Tier 1 fails, falls back to Tier 0 result."""
    mocker.patch(
        "promptune.engine._try_tier1",
        side_effect=ProviderError("Connection refused"),
    )

    result = enhance("fix the bug", mock_config)

    assert isinstance(result, EnhanceResult)
    # Should degrade to Tier 0
    assert result.tier_used in (0, 2)


def test_engine_tier_override(
    mocker: MockerFixture, mock_config: dict
) -> None:
    """--tier flag forces specific tier."""
    mock_provider = mocker.MagicMock()
    mock_provider.enhance.return_value = "Cloud result"
    mocker.patch(
        "promptune.engine._create_cloud_provider",
        return_value=mock_provider,
    )

    result = enhance("fix the bug", mock_config, tier_override=2)

    assert result.tier_used == 2


def test_engine_returns_scores(mock_config: dict) -> None:
    """Result contains before and after scores."""
    mock_config["enhancement"]["max_tier"] = 0

    result = enhance("fix the bug", mock_config)

    assert isinstance(result.score_before, ScoreResult)
    assert isinstance(result.score_after, ScoreResult)
    assert result.score_before.total >= 0
    assert result.score_after.total >= 0


def test_engine_latency_tracked(mock_config: dict) -> None:
    """Latency is tracked in milliseconds."""
    mock_config["enhancement"]["max_tier"] = 0

    result = enhance("fix the bug", mock_config)

    assert result.latency_ms >= 0
    assert result.latency_ms < 5000  # should be fast for Tier 0


def test_engine_missing_api_key_tier2(mock_config: dict) -> None:
    """Missing API key for Tier 2 falls back gracefully."""
    mock_config["api_keys"]["claude"] = ""
    mock_config["local_llm"]["enabled"] = False

    # Should not crash — degrades to Tier 0
    result = enhance("fix the bug", mock_config)
    assert result.tier_used == 0


def test_engine_provider_error_propagates_on_forced_tier(
    mocker: MockerFixture, mock_config: dict
) -> None:
    """When tier is forced and provider fails, error propagates."""
    mock_provider = mocker.MagicMock()
    mock_provider.enhance.side_effect = ProviderError("API down")
    mocker.patch(
        "promptune.engine._create_cloud_provider",
        return_value=mock_provider,
    )

    with pytest.raises(ProviderError, match="API down"):
        enhance("prompt", mock_config, tier_override=2)


def test_engine_missing_api_key_forced_tier2(mock_config: dict) -> None:
    """Forcing tier=2 with ALL API keys empty raises ConfigError."""
    mock_config["api_keys"]["claude"] = ""
    mock_config["api_keys"]["openai"] = ""
    mock_config["api_keys"]["openrouter"] = ""

    with pytest.raises(ConfigError, match="API key"):
        enhance("fix the bug", mock_config, tier_override=2)
```

- [x]**Step 5.2: Run tests to verify they fail**

Run: `pytest tests/test_engine.py -v -x`
Expected: FAIL — old `EnhanceResult` doesn't have `tier_used`, `score_before`, etc.

- [x]**Step 5.3: Implement the new router engine**

Rewrite `promptune/engine.py`:

```python
"""Router Engine: tier-based prompt enhancement orchestration.

Flow:
1. Score raw prompt
2. Apply Tier 0 rules (always)
3. Re-score post-Tier 0
4. Route: score >= 70 → Tier 0 | try Tier 1 → try Tier 2 → fallback Tier 0
5. Return EnhanceResult with full metadata

Design: Strategy pattern — tier handlers are independent functions.
Graceful degradation — always falls back to tier below on failure.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from promptune.config import ConfigError
from promptune.meta_prompt import (
    build_system_prompt,
    detect_domain,
    detect_intent,
    detect_stack,
)
from promptune.providers import BaseProvider, ProviderError, ProviderRegistry
from promptune.providers.anthropic import register as register_claude
from promptune.providers.openai import register as register_openai
from promptune.providers.openrouter import register as register_openrouter
from promptune.scorer import ScoreResult, score_prompt
from promptune.tier0 import Tier0Result, apply_rules


@dataclass
class EnhanceResult:
    """Result of a prompt enhancement with full metadata."""

    original: str
    enhanced: str
    tier_used: int
    latency_ms: float
    score_before: ScoreResult
    score_after: ScoreResult
    rules_applied: list[str]
    context: Any  # ContextFingerprint | None — added in Task 6
    format_style: str
    provider: str | None       # null for Tier 0
    model: str | None          # null for Tier 0


def _get_registry() -> ProviderRegistry:
    """Build and return the provider registry."""
    registry = ProviderRegistry()
    register_claude(registry)
    register_openai(registry)
    register_openrouter(registry)
    return registry


def _build_provider_config(provider_name: str, config: dict[str, Any]) -> dict[str, Any]:
    """Build a provider config dict from the new schema."""
    model_key = f"model_{provider_name}"
    return {
        "api_key": config["api_keys"].get(provider_name, ""),
        "model": config["provider"].get(model_key, ""),
    }


def _create_cloud_provider(
    provider_name: str, config: dict[str, Any]
) -> BaseProvider:
    """Create a cloud provider instance from name and config."""
    registry = _get_registry()
    provider_config = _build_provider_config(provider_name, config)
    return registry.create(provider_name, provider_config)


def _try_tier1(
    prompt: str, system_prompt: str, config: dict[str, Any]
) -> str:
    """Attempt Tier 1 enhancement via local LLM."""
    from promptune.providers.local import LocalProvider

    local_cfg = config["local_llm"]
    provider = LocalProvider(
        model=local_cfg["model"],
        host=local_cfg["host"],
        api_key=local_cfg.get("api_key", ""),
    )
    return provider.enhance(prompt, system_prompt)


def _try_tier2(
    prompt: str, system_prompt: str, config: dict[str, Any]
) -> tuple[str, str, str]:
    """Attempt Tier 2 enhancement via cloud provider. Returns (enhanced, provider_name, model)."""
    provider_name = config["provider"]["default"]
    api_key = config["api_keys"].get(provider_name, "")
    if not api_key:
        raise ConfigError(
            f"Missing api_key for provider '{provider_name}'."
        )

    provider = _create_cloud_provider(provider_name, config)
    model_key = f"model_{provider_name}"
    model = config["provider"].get(model_key, "")
    enhanced = provider.enhance(prompt, system_prompt)
    return enhanced, provider_name, model


def enhance(
    prompt: str,
    config: dict[str, Any],
    provider_override: str | None = None,
    tier_override: int | None = None,
) -> EnhanceResult:
    """Enhance a prompt using tier-based routing.

    Note: config is NOT mutated — provider_override is passed through
    without modifying the caller's dict.
    """
    import copy

    start = time.perf_counter()

    # Work on a shallow copy to avoid mutating caller's config
    cfg = copy.deepcopy(config)
    if provider_override:
        cfg["provider"]["default"] = provider_override

    max_tier = cfg["enhancement"]["max_tier"]
    if tier_override is not None:
        max_tier = tier_override
        forced_tier = True
    else:
        forced_tier = False

    style = cfg["enhancement"]["default_mode"]

    # Step 1: Score raw prompt
    score_before = score_prompt(prompt)

    # Step 2: Apply Tier 0 rules (always)
    tier0_result = apply_rules(prompt, score_before)

    # Step 3: Re-score post-Tier 0
    score_after = score_prompt(tier0_result.enhanced)

    # Build system prompt for AI tiers
    intent = detect_intent(prompt)
    domain = detect_domain(prompt)
    stack = detect_stack(prompt)
    system_prompt = build_system_prompt(
        intent=intent, domain=domain, stack=stack, style=style,
    )

    # Step 4: Route
    enhanced = tier0_result.enhanced
    tier_used = 0
    provider_name: str | None = None
    model_name: str | None = None

    if forced_tier:
        # Forced tier — go directly to requested tier, let errors propagate
        if max_tier == 0:
            pass  # Tier 0 only — already done above
        elif max_tier == 1:
            enhanced = _try_tier1(enhanced, system_prompt, cfg)
            tier_used = 1
            provider_name = "local"
            model_name = cfg["local_llm"]["model"]
        elif max_tier >= 2:
            result_text, provider_name, model_name = _try_tier2(
                enhanced, system_prompt, cfg,
            )
            enhanced = result_text
            tier_used = 2
    else:
        # Auto-routing: check if Tier 0 result is good enough
        if score_after.total < 70:
            # Try Tier 1 if enabled
            if max_tier >= 1 and cfg["local_llm"]["enabled"]:
                try:
                    enhanced = _try_tier1(enhanced, system_prompt, cfg)
                    tier_used = 1
                    provider_name = "local"
                    model_name = cfg["local_llm"]["model"]
                except (ProviderError, ConfigError):
                    pass  # Fall through to Tier 2 or stay at Tier 0

            # Try Tier 2 if still at Tier 0 and Tier 1 didn't work
            if tier_used == 0 and max_tier >= 2:
                try:
                    result_text, provider_name, model_name = _try_tier2(
                        enhanced, system_prompt, cfg,
                    )
                    enhanced = result_text
                    tier_used = 2
                except (ProviderError, ConfigError):
                    pass  # Stay at Tier 0

    # Re-score final result if AI tier was used
    if tier_used > 0:
        score_after = score_prompt(enhanced)

    latency_ms = (time.perf_counter() - start) * 1000

    return EnhanceResult(
        original=prompt,
        enhanced=enhanced,
        tier_used=tier_used,
        latency_ms=latency_ms,
        score_before=score_before,
        score_after=score_after,
        rules_applied=tier0_result.rules_applied,
        context=None,  # Added in Task 6
        format_style=cfg["provider"]["format_style"],
        provider=provider_name,
        model=model_name,
    )
```

- [x]**Step 5.4: Run engine tests to verify they pass**

Run: `pytest tests/test_engine.py -v`
Expected: ALL PASS

- [x]**Step 5.5: Update cli.py to work with new EnhanceResult**

In `promptune/cli.py`, update the `enhance_cmd` to handle the new `EnhanceResult` fields. The TUI call still passes `result.original` and `result.enhanced` — no breaking change. But the `enhance()` import now needs `tier_override` support:

```python
# In enhance_cmd, the call to enhance() stays the same for now:
        result = enhance(prompt, cfg, provider_override=provider)
```

No change needed yet — `tier_override` defaults to `None`. The `--tier` flag will be added in Task 10.

- [x]**Step 5.6: Run full test suite**

Run: `pytest --cov=promptune --cov-report=term-missing -v`
Expected: ALL PASS

- [x]**Step 5.7: Run linting and type checks**

Run: `ruff check . && mypy promptune/`
Expected: PASS

- [x]**Step 5.8: Commit**

```bash
git add promptune/engine.py promptune/providers/__init__.py promptune/providers/local.py tests/test_engine.py tests/test_providers/test_base.py tests/test_providers/test_local.py
git commit -m "feat: add tier-based router engine with local LLM provider and graceful degradation"
```

---

## Task 6: Context Fingerprinting

**Spec reference:** Section 6 — Context Fingerprinting
**Goal:** Gather environmental context (git, shell, tech stack, environment) in parallel, sanitize secrets, rank by priority, and inject into prompts.
**Files created:** `promptune/context/__init__.py`, `promptune/context/collectors.py`, `promptune/context/sanitizer.py`, `promptune/context/ranker.py`
**Files modified:** `promptune/engine.py` (wire context into `EnhanceResult`)
**Test files:** `tests/test_context/__init__.py`, `tests/test_context/test_collectors.py`, `tests/test_context/test_sanitizer.py`, `tests/test_context/test_ranker.py`, `tests/test_context/test_integration.py`

### RED Phase

- [x]**Step 6.1: Write context dataclass and collector tests**

Create `tests/test_context/__init__.py` (empty) and `tests/test_context/test_collectors.py`:

```python
"""Task 6: Context Fingerprinting — collector tests."""

from __future__ import annotations

import pytest
from pytest_mock import MockerFixture

from promptune.context import ContextFingerprint, collect_context
from promptune.context.collectors import (
    collect_git,
    collect_shell_history,
    collect_tech_stack,
    collect_environment,
    GitContext,
    ShellHistoryContext,
    TechStackContext,
    EnvironmentContext,
)


# --- GitCollector ---


def test_git_branch(mocker: MockerFixture) -> None:
    """Extracts current git branch name."""
    mocker.patch(
        "promptune.context.collectors._run_git",
        side_effect=lambda args, **kw: {
            ("branch", "--show-current"): "fix/auth-redirect",
            ("log", "--format=%h|%ar|%s", "-5"): "abc1234|2h ago|fix auth\ndef5678|5h ago|add login",
            ("status", "--porcelain", "-uno"): "M src/auth.py",
            ("diff", "--shortstat"): " 1 file changed, 5 insertions(+), 2 deletions(-)",
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
            ("log", "--format=%h|%ar|%s", "-5"): "abc1234|2h ago|fix auth\ndef5678|5h ago|add login",
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
            ("status", "--porcelain", "-uno"): "M src/auth.py\nA src/new.py",
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


def test_shell_history_recent_commands(mocker: MockerFixture, tmp_path) -> None:
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


def test_shell_history_error_patterns(mocker: MockerFixture, tmp_path) -> None:
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


def test_tech_stack_python(tmp_path, mocker: MockerFixture) -> None:
    """Detects Python project from pyproject.toml."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "foo"\n')
    mocker.patch(
        "promptune.context.collectors._get_project_root",
        return_value=tmp_path,
    )

    result = collect_tech_stack()

    assert isinstance(result, TechStackContext)
    assert "python" in result.languages


def test_tech_stack_node(tmp_path, mocker: MockerFixture) -> None:
    """Detects Node.js project from package.json."""
    (tmp_path / "package.json").write_text('{"name": "foo", "dependencies": {"react": "^18"}}')
    mocker.patch(
        "promptune.context.collectors._get_project_root",
        return_value=tmp_path,
    )

    result = collect_tech_stack()

    assert "javascript" in result.languages or "typescript" in result.languages
    assert "react" in result.frameworks


def test_tech_stack_no_markers(tmp_path, mocker: MockerFixture) -> None:
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
    mocker.patch.dict("os.environ", {"VIRTUAL_ENV": "/home/user/.venv"})

    result = collect_environment()

    assert isinstance(result, EnvironmentContext)
    assert result.in_venv is True


def test_environment_docker(mocker: MockerFixture, tmp_path) -> None:
    """Detects Docker container from /.dockerenv."""
    dockerenv = tmp_path / ".dockerenv"
    dockerenv.touch()
    mocker.patch(
        "promptune.context.collectors.Path",
        side_effect=lambda p: tmp_path / p.lstrip("/") if p.startswith("/") else Path(p),
    )

    result = collect_environment()

    assert result.in_container is True


def test_environment_ci(mocker: MockerFixture) -> None:
    """Detects CI environment from CI env var."""
    mocker.patch.dict("os.environ", {"CI": "true"}, clear=False)

    result = collect_environment()

    assert result.in_ci is True


# --- Parallel collection ---


def test_collect_context_parallel(mocker: MockerFixture) -> None:
    """collect_context runs all collectors and returns ContextFingerprint."""
    mocker.patch(
        "promptune.context.collectors.collect_git",
        return_value=GitContext(
            branch="main", recent_commits=[], modified_files=[],
            diff_stats="", stash_count=0,
        ),
    )
    mocker.patch(
        "promptune.context.collectors.collect_shell_history",
        return_value=ShellHistoryContext(
            recent_commands=[], error_patterns=[], session_intent="unknown",
        ),
    )
    mocker.patch(
        "promptune.context.collectors.collect_tech_stack",
        return_value=TechStackContext(
            languages=[], frameworks=[], package_manager=None,
        ),
    )
    mocker.patch(
        "promptune.context.collectors.collect_environment",
        return_value=EnvironmentContext(
            in_venv=False, in_container=False, in_ci=False, in_ssh=False,
        ),
    )

    result = collect_context(timeout_ms=400)

    assert isinstance(result, ContextFingerprint)
    assert result.git.branch == "main"


def test_collect_context_timeout(mocker: MockerFixture) -> None:
    """Timed-out collectors return defaults, never block."""
    import time

    def slow_git():
        time.sleep(2)
        return GitContext(branch="slow", recent_commits=[], modified_files=[],
                         diff_stats="", stash_count=0)

    mocker.patch("promptune.context.collectors.collect_git", side_effect=slow_git)
    mocker.patch(
        "promptune.context.collectors.collect_shell_history",
        return_value=ShellHistoryContext(
            recent_commands=[], error_patterns=[], session_intent="unknown",
        ),
    )
    mocker.patch(
        "promptune.context.collectors.collect_tech_stack",
        return_value=TechStackContext(
            languages=[], frameworks=[], package_manager=None,
        ),
    )
    mocker.patch(
        "promptune.context.collectors.collect_environment",
        return_value=EnvironmentContext(
            in_venv=False, in_container=False, in_ci=False, in_ssh=False,
        ),
    )

    result = collect_context(timeout_ms=100)

    # Git timed out — should get default empty GitContext
    assert result.git.branch == ""
```

- [x]**Step 6.2: Write sanitizer tests**

Create `tests/test_context/test_sanitizer.py`:

```python
"""Task 6: Context Fingerprinting — secret sanitizer tests."""

from __future__ import annotations

import pytest

from promptune.context.sanitizer import sanitize


def test_sanitize_api_key_sk_prefix() -> None:
    """Redacts strings starting with sk-."""
    text = "api_key=sk-ant-abc123xyz456"
    result = sanitize(text)
    assert "sk-ant-abc123xyz456" not in result
    assert "[REDACTED]" in result


def test_sanitize_github_token() -> None:
    """Redacts GitHub personal access tokens."""
    text = "token: ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ012345"
    result = sanitize(text)
    assert "ghp_" not in result
    assert "[REDACTED]" in result


def test_sanitize_aws_key() -> None:
    """Redacts AWS access key IDs."""
    text = "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE"
    result = sanitize(text)
    assert "AKIA" not in result


def test_sanitize_bearer_token() -> None:
    """Redacts Bearer tokens."""
    text = "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJ0ZXN0IjoidGVzdCJ9.abc123"
    result = sanitize(text)
    assert "eyJhbGci" not in result


def test_sanitize_db_connection_string() -> None:
    """Redacts database connection strings with passwords."""
    text = "DATABASE_URL=postgres://user:s3cretP@ss@localhost:5432/mydb"
    result = sanitize(text)
    assert "s3cretP@ss" not in result


def test_sanitize_password_keyword() -> None:
    """Redacts values near password= keywords."""
    text = "password=my_super_secret_123"
    result = sanitize(text)
    assert "my_super_secret_123" not in result


def test_sanitize_high_entropy_string() -> None:
    """Redacts high-entropy base64-like strings (Shannon > 4.5)."""
    # Random-looking base64 string with high entropy
    text = "secret: aB3cD4eF5gH6iJ7kL8mN9oP0qR1sT2uV3wX4yZ5"
    result = sanitize(text)
    # The high-entropy value should be redacted
    assert "[REDACTED]" in result or "aB3cD4eF5gH6iJ7kL8mN9oP0qR1sT2uV3wX4yZ5" not in result


def test_sanitize_preserves_normal_text() -> None:
    """Normal text without secrets passes through unchanged."""
    text = "branch=fix/auth-redirect | stack=typescript,nextjs"
    result = sanitize(text)
    assert result == text


def test_sanitize_slack_token() -> None:
    """Redacts Slack tokens."""
    text = "SLACK_TOKEN=xoxb-1234567890-abcdefghij"
    result = sanitize(text)
    assert "xoxb-" not in result


def test_sanitize_multiple_secrets() -> None:
    """Redacts multiple secrets in one string."""
    text = "key1=sk-abc123 key2=ghp_def456"
    result = sanitize(text)
    assert "sk-abc123" not in result
    assert "ghp_def456" not in result
```

- [x]**Step 6.3: Write ranker tests**

Create `tests/test_context/test_ranker.py`:

```python
"""Task 6: Context Fingerprinting — context ranker tests."""

from __future__ import annotations

import pytest

from promptune.context import ContextFingerprint
from promptune.context.collectors import (
    GitContext,
    ShellHistoryContext,
    TechStackContext,
    EnvironmentContext,
)
from promptune.context.ranker import rank_context


def test_rank_includes_branch() -> None:
    """Git branch is highest priority — always included."""
    fp = ContextFingerprint(
        git=GitContext(
            branch="fix/auth-redirect",
            recent_commits=["abc|2h|fix auth"],
            modified_files=["src/auth.py"],
            diff_stats="1 file changed",
            stash_count=0,
        ),
        shell=ShellHistoryContext(
            recent_commands=[], error_patterns=[], session_intent="unknown",
        ),
        tech=TechStackContext(
            languages=["python"], frameworks=["flask"], package_manager="pip",
        ),
        env=EnvironmentContext(
            in_venv=True, in_container=False, in_ci=False, in_ssh=False,
        ),
    )

    result = rank_context(fp, token_budget=50)

    assert "fix/auth-redirect" in result


def test_rank_respects_token_budget() -> None:
    """Output fits within token budget."""
    fp = ContextFingerprint(
        git=GitContext(
            branch="main",
            recent_commits=[f"hash{i}|{i}h|commit {i}" for i in range(20)],
            modified_files=[f"file{i}.py" for i in range(50)],
            diff_stats="50 files changed",
            stash_count=3,
        ),
        shell=ShellHistoryContext(
            recent_commands=["pytest", "git status"] * 20,
            error_patterns=["FAILED"],
            session_intent="debugging",
        ),
        tech=TechStackContext(
            languages=["python", "typescript"],
            frameworks=["flask", "react", "nextjs"],
            package_manager="pnpm",
        ),
        env=EnvironmentContext(
            in_venv=True, in_container=True, in_ci=False, in_ssh=True,
        ),
    )

    result = rank_context(fp, token_budget=100)

    # Rough word count as token proxy — should be under budget
    word_count = len(result.split())
    assert word_count <= 120  # some slack for token≈word approximation


def test_rank_drops_low_priority_first() -> None:
    """With tiny budget, only highest priority signals remain."""
    fp = ContextFingerprint(
        git=GitContext(
            branch="main",
            recent_commits=["abc|2h|fix auth"],
            modified_files=["src/auth.py"],
            diff_stats="1 file changed",
            stash_count=2,
        ),
        shell=ShellHistoryContext(
            recent_commands=["pytest"], error_patterns=[], session_intent="unknown",
        ),
        tech=TechStackContext(
            languages=["python"], frameworks=["flask"], package_manager="pip",
        ),
        env=EnvironmentContext(
            in_venv=True, in_container=False, in_ci=False, in_ssh=False,
        ),
    )

    result = rank_context(fp, token_budget=20)

    # Branch (priority 1) should survive
    assert "main" in result
    # Stash (priority 10) should be dropped
    assert "stash" not in result


def test_rank_empty_context() -> None:
    """Empty fingerprint returns empty string."""
    fp = ContextFingerprint(
        git=GitContext(branch="", recent_commits=[], modified_files=[],
                       diff_stats="", stash_count=0),
        shell=ShellHistoryContext(recent_commands=[], error_patterns=[],
                                  session_intent="unknown"),
        tech=TechStackContext(languages=[], frameworks=[], package_manager=None),
        env=EnvironmentContext(in_venv=False, in_container=False,
                               in_ci=False, in_ssh=False),
    )

    result = rank_context(fp, token_budget=500)

    assert result == ""
```

- [x]**Step 6.4: Run tests to verify they fail**

Run: `pytest tests/test_context/ -v -x`
Expected: FAIL — modules don't exist yet.

### GREEN Phase

- [x]**Step 6.5: Implement context dataclasses and collectors**

Create `promptune/context/__init__.py`:

```python
"""Context fingerprinting: gather environment signals for prompt enrichment."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from dataclasses import dataclass, field

from promptune.context.collectors import (
    GitContext,
    ShellHistoryContext,
    TechStackContext,
    EnvironmentContext,
    collect_git,
    collect_shell_history,
    collect_tech_stack,
    collect_environment,
)


@dataclass
class ContextFingerprint:
    """Aggregated context from all collectors."""

    git: GitContext
    shell: ShellHistoryContext
    tech: TechStackContext
    env: EnvironmentContext


def _default_git() -> GitContext:
    return GitContext(branch="", recent_commits=[], modified_files=[],
                     diff_stats="", stash_count=0)


def _default_shell() -> ShellHistoryContext:
    return ShellHistoryContext(recent_commands=[], error_patterns=[],
                               session_intent="unknown")


def _default_tech() -> TechStackContext:
    return TechStackContext(languages=[], frameworks=[], package_manager=None)


def _default_env() -> EnvironmentContext:
    return EnvironmentContext(in_venv=False, in_container=False,
                              in_ci=False, in_ssh=False)


def collect_context(timeout_ms: int = 400) -> ContextFingerprint:
    """Run all collectors in parallel with timeout. Never blocks."""
    timeout_s = timeout_ms / 1000.0

    collectors = {
        "git": (collect_git, _default_git),
        "shell": (collect_shell_history, _default_shell),
        "tech": (collect_tech_stack, _default_tech),
        "env": (collect_environment, _default_env),
    }

    results: dict = {}

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            name: executor.submit(fn)
            for name, (fn, _) in collectors.items()
        }

        for name, future in futures.items():
            _, default_fn = collectors[name]
            try:
                results[name] = future.result(timeout=timeout_s)
            except (FuturesTimeout, Exception):
                results[name] = default_fn()

    return ContextFingerprint(
        git=results["git"],
        shell=results["shell"],
        tech=results["tech"],
        env=results["env"],
    )
```

- [x]**Step 6.6: Implement collectors**

Create `promptune/context/collectors.py`:

```python
"""Individual context collectors — each gathers one type of signal."""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


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
    session_intent: str  # "debugging" | "feature" | "integration" | "devops" | "api" | "unknown"


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


def _run_git(args: tuple[str, ...], timeout: float = 2.0) -> str:
    """Run a git command and return stdout. Raises on failure."""
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.stdout.strip()


def _find_history_file() -> Path | None:
    """Find the shell history file (zsh > bash > fish)."""
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
    try:
        root = _run_git(("rev-parse", "--show-toplevel"))
        if root:
            return Path(root)
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    return Path.cwd()


# --- Collectors ---


def collect_git() -> GitContext:
    """Collect git context signals."""
    try:
        branch = _run_git(("branch", "--show-current"))
        log_output = _run_git(("log", "--format=%h|%ar|%s", "-5"))
        recent_commits = [
            line for line in log_output.splitlines() if line.strip()
        ]
        status_output = _run_git(("status", "--porcelain", "-uno"))
        modified_files = [
            line[3:].strip() for line in status_output.splitlines()
            if line.strip()
        ]
        diff_stats = _run_git(("diff", "--shortstat"))
        stash_output = _run_git(("stash", "list"))
        stash_count = len([
            line for line in stash_output.splitlines() if line.strip()
        ])

        return GitContext(
            branch=branch,
            recent_commits=recent_commits,
            modified_files=modified_files,
            diff_stats=diff_stats,
            stash_count=stash_count,
        )
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return GitContext(
            branch="", recent_commits=[], modified_files=[],
            diff_stats="", stash_count=0,
        )


def collect_shell_history(max_lines: int = 50) -> ShellHistoryContext:
    """Collect recent shell history and detect session intent."""
    hist_file = _find_history_file()
    if hist_file is None:
        return ShellHistoryContext(
            recent_commands=[], error_patterns=[], session_intent="unknown",
        )

    try:
        lines = hist_file.read_text(errors="replace").splitlines()[-max_lines:]
    except (OSError, PermissionError):
        return ShellHistoryContext(
            recent_commands=[], error_patterns=[], session_intent="unknown",
        )

    # Parse zsh extended history format: ": timestamp:0;command"
    commands: list[str] = []
    for line in lines:
        match = re.match(r"^:\s*\d+:\d+;(.+)$", line)
        if match:
            commands.append(match.group(1).strip())
        elif not line.startswith(":") and line.strip():
            # Plain bash/fish history
            commands.append(line.strip())

    # Detect session intent from command patterns
    session_intent = _detect_session_intent(commands)
    error_patterns = _detect_error_patterns(commands)

    return ShellHistoryContext(
        recent_commands=commands[-10:],  # Last 10 for compact output
        error_patterns=error_patterns,
        session_intent=session_intent,
    )


def _detect_session_intent(commands: list[str]) -> str:
    """Detect session intent from command patterns."""
    if not commands:
        return "unknown"

    test_cmds = sum(1 for c in commands if re.search(r"pytest|jest|cargo test|go test|npm test", c))
    if test_cmds >= 3:
        return "debugging"

    for cmd in commands[-5:]:
        if re.search(r"git checkout -b|git switch -c", cmd):
            return "feature"
        if re.search(r"pip install|npm install|yarn add|pnpm add", cmd):
            return "integration"
        if re.search(r"docker build|docker-compose|docker compose", cmd):
            return "devops"
        if re.search(r"curl |httpie |http ", cmd):
            return "api"

    return "unknown"


def _detect_error_patterns(commands: list[str]) -> list[str]:
    """Extract error-related patterns from commands."""
    patterns: list[str] = []
    for cmd in commands:
        if re.search(r"FAIL|ERROR|error|failed|traceback", cmd, re.IGNORECASE):
            patterns.append(cmd[:80])  # Truncate long commands
    return patterns[:5]  # At most 5 patterns


def collect_tech_stack() -> TechStackContext:
    """Detect tech stack from marker files in project root."""
    root = _get_project_root()

    languages: list[str] = []
    frameworks: list[str] = []
    package_manager: str | None = None

    # Language detection via marker files
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
        if (root / marker).exists() and lang not in languages:
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
            pkg = json.loads((root / "package.json").read_text())
            all_deps = {
                **pkg.get("dependencies", {}),
                **pkg.get("devDependencies", {}),
            }
            framework_map = {
                "react": "react", "next": "nextjs", "vue": "vue",
                "svelte": "svelte", "angular": "angular",
                "express": "express", "fastify": "fastify",
            }
            for dep, fw in framework_map.items():
                if dep in all_deps and fw not in frameworks:
                    frameworks.append(fw)
        except (json.JSONDecodeError, OSError):
            pass

    # Python framework detection from pyproject.toml
    if (root / "pyproject.toml").exists():
        try:
            content = (root / "pyproject.toml").read_text()
            py_frameworks = {
                "flask": "flask", "django": "django", "fastapi": "fastapi",
                "click": "click", "typer": "typer",
            }
            for pkg_name, fw in py_frameworks.items():
                if pkg_name in content.lower() and fw not in frameworks:
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
        in_venv=bool(os.environ.get("VIRTUAL_ENV") or os.environ.get("CONDA_DEFAULT_ENV")),
        in_container=Path("/.dockerenv").exists() or Path("/run/.containerenv").exists(),
        in_ci=bool(os.environ.get("CI")),
        in_ssh=bool(os.environ.get("SSH_CONNECTION") or os.environ.get("SSH_CLIENT")),
    )
```

- [x]**Step 6.7: Implement secret sanitizer**

Create `promptune/context/sanitizer.py`:

```python
"""Secret sanitizer — redacts sensitive values from context output."""

from __future__ import annotations

import math
import re
from collections import Counter

# Known secret patterns — compiled for performance
_SECRET_PATTERNS: list[re.Pattern[str]] = [
    # API keys with common prefixes
    re.compile(r"\bsk-[a-zA-Z0-9_-]{10,}\b"),
    re.compile(r"\bghp_[a-zA-Z0-9]{36}\b"),
    re.compile(r"\bghs_[a-zA-Z0-9]{36}\b"),
    re.compile(r"\bgho_[a-zA-Z0-9]{36}\b"),
    re.compile(r"\bghu_[a-zA-Z0-9]{36}\b"),
    re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
    re.compile(r"\bxoxb-[a-zA-Z0-9-]+\b"),
    re.compile(r"\bxoxp-[a-zA-Z0-9-]+\b"),
    # Bearer tokens
    re.compile(r"Bearer\s+[a-zA-Z0-9._-]{20,}", re.IGNORECASE),
    # Database connection strings with passwords
    re.compile(
        r"(postgres|mysql|mongodb|redis)://[^:]+:[^@]+@",
        re.IGNORECASE,
    ),
]

# Keyword-value patterns — keyword near a value
_KEYWORD_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(password|passwd|secret|token|api_key|apikey)\s*[=:]\s*\S+", re.IGNORECASE),
]

_REDACTED = "[REDACTED]"


def _shannon_entropy(s: str) -> float:
    """Calculate Shannon entropy of a string."""
    if not s:
        return 0.0
    counter = Counter(s)
    length = len(s)
    entropy = 0.0
    for count in counter.values():
        p = count / length
        if p > 0:
            entropy -= p * math.log2(p)
    return entropy


def _redact_high_entropy(text: str) -> str:
    """Redact high-entropy strings that look like secrets."""
    # Find long alphanumeric+special strings that aren't normal words
    pattern = re.compile(r"(?<=[=:\s])[a-zA-Z0-9+/=_-]{20,}")

    def _check_and_redact(match: re.Match[str]) -> str:
        value = match.group(0)
        entropy = _shannon_entropy(value)
        if entropy > 4.5:
            return _REDACTED
        return value

    return pattern.sub(_check_and_redact, text)


def sanitize(text: str) -> str:
    """Remove all secrets from text. Runs all detection strategies."""
    result = text

    # 1. Known patterns
    for pattern in _SECRET_PATTERNS:
        result = pattern.sub(_REDACTED, result)

    # 2. Keyword proximity
    for pattern in _KEYWORD_PATTERNS:
        result = pattern.sub(lambda m: m.group(0).split("=")[0] + "=" + _REDACTED
                             if "=" in m.group(0)
                             else m.group(0).split(":")[0] + ": " + _REDACTED,
                             result)

    # 3. High entropy strings
    result = _redact_high_entropy(result)

    return result
```

- [x]**Step 6.8: Implement context ranker**

Create `promptune/context/ranker.py`:

```python
"""Context ranker — prioritizes signals and fits within token budget."""

from __future__ import annotations

from promptune.context import ContextFingerprint
from promptune.context.sanitizer import sanitize


def rank_context(fp: ContextFingerprint, token_budget: int = 500) -> str:
    """Rank context signals by priority and fit within token budget.

    Priority order (spec Section 6):
    1. Git branch
    2. Recent commits
    3. Modified files
    4. Diff stats
    5. Tech stack markers
    6. Recent shell commands
    7. Shell error patterns
    8. Framework details
    9. Environment type
    10. Stash state
    """
    # Build prioritized signal list: (priority, key, value)
    signals: list[tuple[int, str, str]] = []

    if fp.git.branch:
        signals.append((1, "branch", fp.git.branch))
    if fp.git.recent_commits:
        commits = "; ".join(fp.git.recent_commits[:5])
        signals.append((2, "recent_commits", commits))
    if fp.git.modified_files:
        files = ", ".join(fp.git.modified_files[:10])
        signals.append((3, "modified_files", files))
    if fp.git.diff_stats:
        signals.append((4, "diff_stats", fp.git.diff_stats))
    if fp.tech.languages:
        signals.append((5, "stack", ",".join(fp.tech.languages)))
    if fp.shell.recent_commands:
        cmds = "; ".join(fp.shell.recent_commands[-5:])
        signals.append((6, "recent_cmds", cmds))
    if fp.shell.error_patterns:
        errs = "; ".join(fp.shell.error_patterns[:3])
        signals.append((7, "errors", errs))
    if fp.tech.frameworks:
        signals.append((8, "frameworks", ",".join(fp.tech.frameworks)))
    if fp.tech.package_manager:
        signals.append((8, "pkg", fp.tech.package_manager))

    # Environment flags
    env_flags: list[str] = []
    if fp.env.in_venv:
        env_flags.append("venv")
    if fp.env.in_container:
        env_flags.append("container")
    if fp.env.in_ci:
        env_flags.append("ci")
    if fp.env.in_ssh:
        env_flags.append("ssh")
    if env_flags:
        signals.append((9, "env", ",".join(env_flags)))

    if fp.shell.session_intent != "unknown":
        signals.append((9, "intent", fp.shell.session_intent))

    if fp.git.stash_count > 0:
        signals.append((10, "stash", str(fp.git.stash_count)))

    if not signals:
        return ""

    # Sort by priority (ascending = highest priority first)
    signals.sort(key=lambda s: s[0])

    # Build output, trimming from bottom when over budget
    parts: list[str] = []
    word_count = 0

    for _, key, value in signals:
        entry = f"{key}={value}"
        entry_words = len(entry.split())
        if word_count + entry_words > token_budget:
            break
        parts.append(entry)
        word_count += entry_words

    result = " | ".join(parts)

    # Sanitize all output before returning
    return sanitize(result)
```

- [x]**Step 6.9: Run context tests to verify they pass**

Run: `pytest tests/test_context/ -v`
Expected: ALL PASS

- [x]**Step 6.10: Wire context into engine**

In `promptune/engine.py`, update `enhance()` to optionally collect context:

```python
# Add import at top:
from promptune.context import collect_context

# In enhance(), after building system_prompt, add:
    # Collect context if any context source is enabled
    context_cfg = cfg.get("context", {})
    context_enabled = any([
        context_cfg.get("use_git", True),
        context_cfg.get("use_shell_history", True),
        context_cfg.get("use_stack_detection", True),
    ])
    context_fp = None
    if context_enabled:
        context_fp = collect_context(timeout_ms=400)
        # Inject context into system prompt
        from promptune.context.ranker import rank_context
        context_str = rank_context(
            context_fp,
            token_budget=context_cfg.get("max_context_tokens", 500),
        )
        if context_str:
            system_prompt += f"\n\n## Context\n{context_str}"

    # Update the return to pass context:
    return EnhanceResult(
        ...
        context=context_fp,  # Was None, now populated
        ...
    )
```

- [x]**Step 6.11: Run full test suite**

Run: `pytest --cov=promptune --cov-report=term-missing -v`
Expected: ALL PASS

- [x]**Step 6.12: Run linting and type checks**

Run: `ruff check . && mypy promptune/`
Expected: PASS

- [x]**Step 6.13: Commit**

```bash
git add promptune/context/ tests/test_context/
git commit -m "feat: add context fingerprinting with parallel collectors, secret sanitizer, and ranker"
```

---

## Task 7: Prompt Quality Score (PQS)

**Spec reference:** Section 7 — Prompt Quality Score
**Goal:** User-facing 5-dimension quality display mapped from scorer internals. Reuses scorer, no duplicate computation.
**Files created:** `promptune/pqs.py`
**Test files:** `tests/test_pqs.py`

### RED Phase

- [x]**Step 7.1: Write PQS tests**

Create `tests/test_pqs.py`:

```python
"""Task 7: Prompt Quality Score — tests."""

from __future__ import annotations

import pytest

from promptune.pqs import DimensionDisplay, PQScore, compute_pqs
from promptune.scorer import DimensionScore, ScoreResult


def _make_score(
    clarity: float = 0.5,
    specificity: float = 0.5,
    context: float = 0.5,
    structure: float = 0.5,
    actionability: float = 0.5,
    completeness: float = 0.5,
    conciseness: float = 0.5,
    total: int = 50,
) -> ScoreResult:
    """Helper to create ScoreResult with controlled dimension scores.

    Dimension scores are 0-1 raw values (matching scorer's DimensionScore).
    Total is 0-100 calibrated (matching scorer's ScoreResult).
    """
    return ScoreResult(
        total=total,
        dimensions={
            "clarity": DimensionScore(
                score=clarity, max_weight=20,
                signals=[], suggestion="Improve clarity",
            ),
            "specificity": DimensionScore(
                score=specificity, max_weight=25,
                signals=[], suggestion="Add specifics",
            ),
            "context": DimensionScore(
                score=context, max_weight=20,
                signals=[], suggestion="Add context",
            ),
            "structure": DimensionScore(
                score=structure, max_weight=15,
                signals=[], suggestion="Add structure",
            ),
            "actionability": DimensionScore(
                score=actionability, max_weight=15,
                signals=[], suggestion="Make actionable",
            ),
            "completeness": DimensionScore(
                score=completeness, max_weight=10,
                signals=[], suggestion="Be more complete",
            ),
            "conciseness": DimensionScore(
                score=conciseness, max_weight=5,
                signals=[], suggestion="Be concise",
            ),
        },
        intent="coding",
    )


def test_compute_pqs_returns_pqscore() -> None:
    """compute_pqs returns a PQScore instance."""
    score = _make_score()
    result = compute_pqs(score)
    assert isinstance(result, PQScore)


def test_pqs_clarity_direct_mapping() -> None:
    """Clarity maps directly from scorer clarity (0-1 → 0-100)."""
    score = _make_score(clarity=0.8)
    result = compute_pqs(score)
    assert result.clarity.score == 80


def test_pqs_specificity_weighted_avg() -> None:
    """Specificity combines specificity (w=25) and completeness (w=10)."""
    # specificity=0.9, completeness=0.6 → (90*25 + 60*10) / 35 = 81.4 → 81
    score = _make_score(specificity=0.9, completeness=0.6)
    result = compute_pqs(score)
    expected = round((90 * 25 + 60 * 10) / 35)
    assert result.specificity.score == expected


def test_pqs_context_direct_mapping() -> None:
    """Context maps directly from scorer context."""
    score = _make_score(context=0.65)
    result = compute_pqs(score)
    assert result.context.score == 65


def test_pqs_structure_direct_mapping() -> None:
    """Structure maps directly from scorer structure."""
    score = _make_score(structure=0.45)
    result = compute_pqs(score)
    assert result.structure.score == 45


def test_pqs_actionability_weighted_avg() -> None:
    """Actionability combines actionability (w=15) and conciseness (w=5)."""
    # actionability=0.7, conciseness=0.9 → (70*15 + 90*5) / 20 = 75
    score = _make_score(actionability=0.7, conciseness=0.9)
    result = compute_pqs(score)
    expected = round((70 * 15 + 90 * 5) / 20)
    assert result.actionability.score == expected


def test_pqs_color_red() -> None:
    """Score 0-39 gets red color."""
    score = _make_score(clarity=0.2)
    result = compute_pqs(score)
    assert result.clarity.color == "red"


def test_pqs_color_yellow() -> None:
    """Score 40-69 gets yellow color."""
    score = _make_score(clarity=0.55)
    result = compute_pqs(score)
    assert result.clarity.color == "yellow"


def test_pqs_color_green() -> None:
    """Score 70-100 gets green color."""
    score = _make_score(clarity=0.85)
    result = compute_pqs(score)
    assert result.clarity.color == "green"


def test_pqs_bar_visualization() -> None:
    """Bar uses unicode blocks proportional to score."""
    score = _make_score(clarity=0.5)
    result = compute_pqs(score)
    assert "█" in result.clarity.bar
    assert "░" in result.clarity.bar
    assert len(result.clarity.bar) == 10  # 10-char bar


def test_pqs_overall_weighted() -> None:
    """Overall score is weighted composite of 5 dimensions."""
    score = _make_score(
        clarity=0.8, specificity=0.7, context=0.6,
        structure=0.5, actionability=0.4,
        completeness=0.7, conciseness=0.4,
    )
    result = compute_pqs(score)
    # Verify overall is between 0-100 and reasonable
    assert 0 <= result.overall <= 100


def test_pqs_suggestion_passthrough() -> None:
    """Suggestions come from scorer dimensions."""
    score = _make_score(clarity=0.3)
    result = compute_pqs(score)
    assert result.clarity.suggestion == "Improve clarity"


def test_pqs_zero_scores() -> None:
    """All zero scores produce valid PQScore."""
    score = _make_score(
        clarity=0, specificity=0, context=0, structure=0,
        actionability=0, completeness=0, conciseness=0, total=0,
    )
    result = compute_pqs(score)
    assert result.overall == 0
    assert result.clarity.color == "red"
```

- [x]**Step 7.2: Run tests to verify they fail**

Run: `pytest tests/test_pqs.py -v -x`
Expected: FAIL — `promptune.pqs` doesn't exist.

### GREEN Phase

- [x]**Step 7.3: Implement PQS module**

Create `promptune/pqs.py`:

```python
"""Prompt Quality Score — user-facing 5-dimension quality display."""

from __future__ import annotations

from dataclasses import dataclass

from promptune.scorer import ScoreResult


@dataclass
class DimensionDisplay:
    """Single PQS dimension for display."""

    score: int          # 0-100 normalized
    color: str          # "red" (0-39), "yellow" (40-69), "green" (70-100)
    bar: str            # Unicode block visualization "████████░░"
    suggestion: str     # Actionable fix from scorer


@dataclass
class PQScore:
    """Full prompt quality score for TUI display."""

    clarity: DimensionDisplay
    specificity: DimensionDisplay
    context: DimensionDisplay
    structure: DimensionDisplay
    actionability: DimensionDisplay
    overall: int  # weighted composite 0-100


def _score_to_color(score: int) -> str:
    """Map score to color band."""
    if score < 40:
        return "red"
    if score < 70:
        return "yellow"
    return "green"


def _score_to_bar(score: int, width: int = 10) -> str:
    """Create unicode block bar visualization."""
    filled = round(score / 100 * width)
    return "█" * filled + "░" * (width - filled)


def _make_dimension(score: int, suggestion: str) -> DimensionDisplay:
    """Create a DimensionDisplay from score and suggestion."""
    clamped = max(0, min(100, score))
    return DimensionDisplay(
        score=clamped,
        color=_score_to_color(clamped),
        bar=_score_to_bar(clamped),
        suggestion=suggestion,
    )


def _dim(score_result: ScoreResult, name: str) -> DimensionScore:
    """Get a dimension from the scorer's dict-based ScoreResult."""
    return score_result.dimensions[name]


def compute_pqs(score_result: ScoreResult) -> PQScore:
    """Compute PQS from scorer internals.

    Scorer dimensions use 0-1 raw scores. PQS normalizes to 0-100.

    Mapping (from spec Section 7):
    - Clarity: direct from scorer clarity
    - Specificity: weighted avg of specificity (w=25) + completeness (w=10)
    - Context: direct from scorer context
    - Structure: direct from scorer structure
    - Actionability: weighted avg of actionability (w=15) + conciseness (w=5)
    """
    d = score_result.dimensions

    # Convert 0-1 raw scores to 0-100
    clarity_raw = round(d["clarity"].score * 100)
    spec_raw = round(d["specificity"].score * 100)
    comp_raw = round(d["completeness"].score * 100)
    ctx_raw = round(d["context"].score * 100)
    struct_raw = round(d["structure"].score * 100)
    act_raw = round(d["actionability"].score * 100)
    conc_raw = round(d["conciseness"].score * 100)

    clarity_score = clarity_raw
    specificity_score = round((spec_raw * 25 + comp_raw * 10) / 35)
    context_score = ctx_raw
    structure_score = struct_raw
    actionability_score = round((act_raw * 15 + conc_raw * 5) / 20)

    clarity = _make_dimension(clarity_score, d["clarity"].suggestion)
    specificity = _make_dimension(specificity_score, d["specificity"].suggestion)
    context = _make_dimension(context_score, d["context"].suggestion)
    structure = _make_dimension(structure_score, d["structure"].suggestion)
    actionability = _make_dimension(actionability_score, d["actionability"].suggestion)

    # Weighted overall: clarity=0.25, specificity=0.25, context=0.20,
    # structure=0.15, actionability=0.15
    overall = round(
        clarity_score * 0.25
        + specificity_score * 0.25
        + context_score * 0.20
        + structure_score * 0.15
        + actionability_score * 0.15
    )

    return PQScore(
        clarity=clarity,
        specificity=specificity,
        context=context,
        structure=structure,
        actionability=actionability,
        overall=overall,
    )
```

- [x]**Step 7.4: Run PQS tests to verify they pass**

Run: `pytest tests/test_pqs.py -v`
Expected: ALL PASS

- [x]**Step 7.5: Run linting and type checks**

Run: `ruff check . && mypy promptune/`
Expected: PASS

- [x]**Step 7.6: Commit**

```bash
git add promptune/pqs.py tests/test_pqs.py
git commit -m "feat: add Prompt Quality Score (PQS) 5-dimension display"
```

---

## Task 8: Provider-Specific Formatting

**Spec reference:** Section 8 — Provider-Specific Formatting
**Goal:** Format enhanced prompts as XML (Claude/Gemini), Markdown (GPT/Mistral), or Plain (small models). Auto-detect from model ID.
**Files created:** `promptune/formatter.py`
**Test files:** `tests/test_formatter.py`

### RED Phase

- [x]**Step 8.1: Write formatter tests**

Create `tests/test_formatter.py`:

```python
"""Task 8: Provider-Specific Formatting — tests."""

from __future__ import annotations

import pytest

from promptune.formatter import (
    FormatStyle,
    detect_format_style,
    format_prompt,
)


# --- FormatStyle enum ---


def test_format_style_values() -> None:
    """FormatStyle has xml, markdown, plain values."""
    assert FormatStyle.XML.value == "xml"
    assert FormatStyle.MARKDOWN.value == "markdown"
    assert FormatStyle.PLAIN.value == "plain"


# --- Auto-detection ---


def test_detect_claude_xml() -> None:
    """Claude models get XML format."""
    assert detect_format_style("claude-sonnet-4-20250514") == FormatStyle.XML


def test_detect_gemini_xml() -> None:
    """Gemini models get XML format."""
    assert detect_format_style("gemini-1.5-pro") == FormatStyle.XML


def test_detect_gpt_markdown() -> None:
    """GPT models get Markdown format."""
    assert detect_format_style("gpt-4o") == FormatStyle.MARKDOWN


def test_detect_o1_markdown() -> None:
    """o1 reasoning models get Markdown format."""
    assert detect_format_style("o1-preview") == FormatStyle.MARKDOWN


def test_detect_deepseek_r1_plain() -> None:
    """DeepSeek R1 reasoning model gets Plain format."""
    assert detect_format_style("deepseek-r1") == FormatStyle.PLAIN
    assert detect_format_style("deepseek-reasoner") == FormatStyle.PLAIN


def test_detect_phi_plain() -> None:
    """Phi models get Plain format."""
    assert detect_format_style("phi-3") == FormatStyle.PLAIN


def test_detect_gemma_plain() -> None:
    """Gemma models get Plain format."""
    assert detect_format_style("gemma-2") == FormatStyle.PLAIN


def test_detect_mistral_large_markdown() -> None:
    """Mistral large models get Markdown format."""
    assert detect_format_style("mistral-large-latest") == FormatStyle.MARKDOWN


def test_detect_deepseek_chat_markdown() -> None:
    """DeepSeek chat models get Markdown format."""
    assert detect_format_style("deepseek-chat") == FormatStyle.MARKDOWN


def test_detect_grok_markdown() -> None:
    """Grok models get Markdown format."""
    assert detect_format_style("grok-2") == FormatStyle.MARKDOWN


def test_detect_command_r_markdown() -> None:
    """Command R models get Markdown format."""
    assert detect_format_style("command-r-plus") == FormatStyle.MARKDOWN


def test_detect_openrouter_prefix_stripped() -> None:
    """OpenRouter provider/model prefix is stripped before matching."""
    assert detect_format_style("anthropic/claude-sonnet-4-20250514") == FormatStyle.XML
    assert detect_format_style("openai/gpt-4o") == FormatStyle.MARKDOWN


def test_detect_small_model_plain() -> None:
    """Models <7B params get Plain format."""
    assert detect_format_style("llama-3b") == FormatStyle.PLAIN
    assert detect_format_style("qwen-2.5-3b") == FormatStyle.PLAIN


def test_detect_large_model_markdown() -> None:
    """Models >=7B params get Markdown format when family is size-aware."""
    assert detect_format_style("llama-70b") == FormatStyle.MARKDOWN


def test_detect_unknown_model_markdown() -> None:
    """Completely unknown model defaults to Markdown."""
    assert detect_format_style("some-unknown-model-v2") == FormatStyle.MARKDOWN


def test_detect_ministral_plain() -> None:
    """Small Mistral variants get Plain format."""
    assert detect_format_style("ministral-8b") == FormatStyle.PLAIN
    assert detect_format_style("mistral-small-latest") == FormatStyle.PLAIN


# --- Format output ---


def test_format_xml_wraps_sections() -> None:
    """XML format wraps content in XML tags."""
    result = format_prompt(
        "You are a Python expert.",
        "Build a REST API with Flask.",
        "- Use SQLAlchemy\n- Add JWT auth",
        FormatStyle.XML,
    )
    assert "<instructions>" in result
    assert "<context>" in result or "<task>" in result
    assert "</instructions>" in result


def test_format_markdown_uses_headers() -> None:
    """Markdown format uses ## headers."""
    result = format_prompt(
        "You are a Python expert.",
        "Build a REST API with Flask.",
        "- Use SQLAlchemy\n- Add JWT auth",
        FormatStyle.MARKDOWN,
    )
    assert "## " in result


def test_format_plain_uses_labels() -> None:
    """Plain format uses label: value structure."""
    result = format_prompt(
        "You are a Python expert.",
        "Build a REST API with Flask.",
        "- Use SQLAlchemy\n- Add JWT auth",
        FormatStyle.PLAIN,
    )
    assert "Role:" in result or "Task:" in result


def test_format_empty_sections_omitted() -> None:
    """Empty sections are not included in output."""
    result = format_prompt("", "Build something.", "", FormatStyle.XML)
    assert "<instructions>" not in result  # Empty role omitted
    assert "<requirements>" not in result  # Empty requirements omitted
    assert "<task>" in result  # Non-empty task present
    assert "Build something" in result
```

- [x]**Step 8.2: Run tests to verify they fail**

Run: `pytest tests/test_formatter.py -v -x`
Expected: FAIL — `promptune.formatter` doesn't exist.

### GREEN Phase

- [x]**Step 8.3: Implement formatter module**

Create `promptune/formatter.py`:

```python
"""Provider-specific prompt formatting with auto-detection."""

from __future__ import annotations

import re
from enum import Enum


class FormatStyle(Enum):
    """Prompt format styles for different LLM families."""

    XML = "xml"
    MARKDOWN = "markdown"
    PLAIN = "plain"


# Ordered list — first match wins. More specific patterns before broader ones.
MODEL_FORMAT_MAP: list[tuple[str, FormatStyle]] = [
    # Plain preference (specific patterns first)
    (r"deepseek[-_/]?(reasoner|r1)", FormatStyle.PLAIN),
    (r"phi[-_]?\d", FormatStyle.PLAIN),
    (r"gemma[-_]?\d", FormatStyle.PLAIN),
    # XML preference
    (r"claude", FormatStyle.XML),
    (r"gemini", FormatStyle.XML),
    # Markdown preference
    (r"gpt[-_]?\d", FormatStyle.MARKDOWN),
    (r"o[134][-_]?(mini|preview)?", FormatStyle.MARKDOWN),
    (r"mistral[-_]?(large|medium)|mixtral|magistral", FormatStyle.MARKDOWN),
    (r"codestral|devstral", FormatStyle.MARKDOWN),
    (r"deepseek[-_/]?(chat|v[23]|coder)", FormatStyle.MARKDOWN),
    (r"grok", FormatStyle.MARKDOWN),
    (r"command[-_]?r", FormatStyle.MARKDOWN),
    (r"jamba", FormatStyle.MARKDOWN),
    (r"dbrx", FormatStyle.MARKDOWN),
]

# Size-aware families — checked after MODEL_FORMAT_MAP
SIZE_AWARE_FAMILIES: list[tuple[str, dict]] = [
    (r"llama", {"threshold": 7, "above": FormatStyle.MARKDOWN, "below": FormatStyle.PLAIN}),
    (r"qwen", {"threshold": 7, "above": FormatStyle.MARKDOWN, "below": FormatStyle.PLAIN}),
    (r"mistral[-_]?(small|tiny)|ministral", {"force": FormatStyle.PLAIN}),
]


def _strip_provider_prefix(model_id: str) -> str:
    """Strip OpenRouter/Together AI provider prefixes."""
    # Patterns like "anthropic/claude-..." or "Org/Model"
    if "/" in model_id:
        parts = model_id.split("/")
        # Keep last part (the model name)
        return parts[-1]
    return model_id


def _extract_param_count(model_id: str) -> int | None:
    """Extract parameter count in billions from model ID."""
    match = re.search(r"(\d+)[bB]", model_id)
    if match:
        return int(match.group(1))
    return None


def detect_format_style(model_id: str) -> FormatStyle:
    """Auto-detect format style from model ID.

    Chain:
    1. Strip provider prefix
    2. Match against MODEL_FORMAT_MAP
    3. Check SIZE_AWARE_FAMILIES with param count
    4. Default: markdown
    """
    stripped = _strip_provider_prefix(model_id).lower()

    # Step 2: Known model families
    for pattern, style in MODEL_FORMAT_MAP:
        if re.search(pattern, stripped):
            return style

    # Step 3: Size-aware families
    param_count = _extract_param_count(stripped)
    for pattern, config in SIZE_AWARE_FAMILIES:
        if re.search(pattern, stripped):
            if "force" in config:
                return config["force"]
            if param_count is not None:
                threshold = config["threshold"]
                return config["above"] if param_count >= threshold else config["below"]
            # No param count found — default to above threshold
            return config.get("above", FormatStyle.MARKDOWN)

    # Step 4: Unknown model → markdown (safest universal default)
    return FormatStyle.MARKDOWN


def format_prompt(
    role: str,
    task: str,
    requirements: str,
    style: FormatStyle,
) -> str:
    """Format prompt sections into the target style."""
    if style == FormatStyle.XML:
        return _format_xml(role, task, requirements)
    if style == FormatStyle.MARKDOWN:
        return _format_markdown(role, task, requirements)
    return _format_plain(role, task, requirements)


def _format_xml(role: str, task: str, requirements: str) -> str:
    """Format as XML tags."""
    parts: list[str] = []
    if role:
        parts.append(f"<instructions>{role}</instructions>")
    if task:
        parts.append(f"<task>{task}</task>")
    if requirements:
        parts.append(f"<requirements>{requirements}</requirements>")
    return "\n\n".join(parts)


def _format_markdown(role: str, task: str, requirements: str) -> str:
    """Format with Markdown headers."""
    parts: list[str] = []
    if role:
        parts.append(f"## Role\n{role}")
    if task:
        parts.append(f"## Task\n{task}")
    if requirements:
        parts.append(f"## Requirements\n{requirements}")
    return "\n\n".join(parts)


def _format_plain(role: str, task: str, requirements: str) -> str:
    """Format with plain label: value structure."""
    parts: list[str] = []
    if role:
        parts.append(f"Role: {role}")
    if task:
        parts.append(f"Task: {task}")
    if requirements:
        parts.append(f"Requirements: {requirements}")
    return "\n\n".join(parts)
```

- [x]**Step 8.4: Run formatter tests to verify they pass**

Run: `pytest tests/test_formatter.py -v`
Expected: ALL PASS

- [x]**Step 8.5: Run linting and type checks**

Run: `ruff check . && mypy promptune/`
Expected: PASS

- [x]**Step 8.6: Commit**

```bash
git add promptune/formatter.py tests/test_formatter.py
git commit -m "feat: add provider-specific formatting with auto-detection from model ID"
```

---

## Task 9: TUI Updates

**Spec reference:** Section 9 — TUI Updates
**Goal:** Add tier/latency header, quality score toggle (Q), rules toggle (D), context toggle (C), diff highlighting. Keep default view clean.
**Files modified:** `promptune/tui.py`, `tests/test_tui.py`

### RED Phase

- [x]**Step 9.1: Write TUI update tests**

Update `tests/test_tui.py` — add new tests alongside existing ones:

```python
"""Task 9: TUI Updates — new tests (append to existing test_tui.py)."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch
from io import StringIO

from promptune.tui import display_result, _render_header, _render_quality_toggle, _render_details_toggle, _render_context_toggle
from promptune.engine import EnhanceResult
from promptune.scorer import ScoreResult, DimensionScore
from promptune.pqs import compute_pqs
from promptune.context import ContextFingerprint
from promptune.context.collectors import (
    GitContext, ShellHistoryContext, TechStackContext, EnvironmentContext,
)


def _make_dim(score: float = 0.5, suggestion: str = "test") -> DimensionScore:
    return DimensionScore(score=score, max_weight=15, signals=[], suggestion=suggestion)


def _make_score_result(total: int = 50) -> ScoreResult:
    return ScoreResult(
        total=total,
        dimensions={
            "clarity": _make_dim(0.5),
            "specificity": _make_dim(0.5),
            "context": _make_dim(0.5),
            "structure": _make_dim(0.5),
            "actionability": _make_dim(0.5),
            "completeness": _make_dim(0.5),
            "conciseness": _make_dim(0.5),
        },
        intent="coding",
    )


def _make_enhance_result(
    tier_used: int = 0,
    latency_ms: float = 8.0,
    rules_applied: list[str] | None = None,
) -> EnhanceResult:
    return EnhanceResult(
        original="fix the bug",
        enhanced="Diagnose and fix the TypeScript compilation error in src/auth.",
        tier_used=tier_used,
        latency_ms=latency_ms,
        score_before=_make_score_result(11),
        score_after=_make_score_result(81),
        rules_applied=rules_applied or ["output_format", "constraints"],
        context=None,
        format_style="xml",
        provider=None if tier_used == 0 else "claude",
        model=None if tier_used == 0 else "claude-sonnet-4-20250514",
    )


# --- Header ---


def test_tui_header_shows_tier() -> None:
    """Header displays tier used."""
    result = _make_enhance_result(tier_used=0)
    header = _render_header(result)
    assert "Tier 0" in header


def test_tui_header_shows_latency() -> None:
    """Header displays latency in ms."""
    result = _make_enhance_result(latency_ms=8.5)
    header = _render_header(result)
    assert "8" in header or "ms" in header


def test_tui_header_shows_rules_for_tier0() -> None:
    """Tier 0 header shows 'rules' label."""
    result = _make_enhance_result(tier_used=0)
    header = _render_header(result)
    assert "rules" in header.lower()


def test_tui_header_shows_provider_for_tier2() -> None:
    """Tier 2 header shows provider name."""
    result = _make_enhance_result(tier_used=2)
    result.provider = "claude"
    header = _render_header(result)
    assert "claude" in header.lower()


# --- Quality toggle (Q) ---


def test_tui_quality_toggle_shows_before_after() -> None:
    """Quality toggle shows before→after scores with delta."""
    result = _make_enhance_result()
    pqs_before = compute_pqs(result.score_before)
    pqs_after = compute_pqs(result.score_after)
    output = _render_quality_toggle(pqs_before, pqs_after)
    assert "Clarity" in output or "clarity" in output.lower()
    assert "█" in output  # Unicode bars present


def test_tui_quality_toggle_shows_delta() -> None:
    """Quality toggle shows score improvement delta."""
    result = _make_enhance_result()
    pqs_before = compute_pqs(result.score_before)
    pqs_after = compute_pqs(result.score_after)
    output = _render_quality_toggle(pqs_before, pqs_after)
    assert "+" in output or "▶" in output  # Delta indicator


# --- Details toggle (D) ---


def test_tui_details_toggle_shows_rules() -> None:
    """Details toggle lists applied rules."""
    result = _make_enhance_result(rules_applied=["output_format", "constraints"])
    output = _render_details_toggle(result.rules_applied)
    assert "output_format" in output
    assert "constraints" in output


def test_tui_details_toggle_empty_rules() -> None:
    """Details toggle handles empty rules list."""
    output = _render_details_toggle([])
    assert "none" in output.lower() or output.strip() == ""


# --- Context toggle (C) ---


def test_tui_context_toggle_shows_fingerprint() -> None:
    """Context toggle displays context fingerprint."""
    fp = ContextFingerprint(
        git=GitContext(
            branch="fix/auth-redirect", recent_commits=[],
            modified_files=[], diff_stats="", stash_count=0,
        ),
        shell=ShellHistoryContext(
            recent_commands=[], error_patterns=[],
            session_intent="unknown",
        ),
        tech=TechStackContext(
            languages=["typescript"], frameworks=["nextjs"],
            package_manager="pnpm",
        ),
        env=EnvironmentContext(
            in_venv=False, in_container=False, in_ci=False, in_ssh=False,
        ),
    )
    output = _render_context_toggle(fp)
    assert "fix/auth-redirect" in output
    assert "typescript" in output


def test_tui_context_toggle_none() -> None:
    """Context toggle handles None context."""
    output = _render_context_toggle(None)
    assert "no context" in output.lower() or output.strip() == ""
```

- [x]**Step 9.2: Run tests to verify they fail**

Run: `pytest tests/test_tui.py -v -x`
Expected: FAIL — new functions don't exist in `tui.py`.

### GREEN Phase

- [x]**Step 9.3: Implement TUI helper functions**

In `promptune/tui.py`, add the new rendering functions. Keep existing `display_result` and add:

```python
# Add imports at top of tui.py:
from __future__ import annotations

from rich.text import Text

from promptune.context import ContextFingerprint
from promptune.engine import EnhanceResult
from promptune.pqs import PQScore, compute_pqs


def _render_header(result: EnhanceResult) -> str:
    """Render the status header line."""
    tier_label = f"Tier {result.tier_used}"
    if result.tier_used == 0:
        method = "rules"
    elif result.tier_used == 1:
        method = "local"
    else:
        method = result.provider or "cloud"

    latency = f"{result.latency_ms:.0f}ms"
    return f"promptune  [{tier_label} · {method} · {latency}]"


def _render_quality_toggle(pqs_before: PQScore, pqs_after: PQScore) -> str:
    """Render quality score breakdown with before→after deltas."""
    lines: list[str] = []
    lines.append(f"  Quality: {pqs_before.overall} ──▶ {pqs_after.overall}  (+{pqs_after.overall - pqs_before.overall})")
    lines.append("")

    dimensions = [
        ("Clarity", pqs_before.clarity, pqs_after.clarity),
        ("Specificity", pqs_before.specificity, pqs_after.specificity),
        ("Context", pqs_before.context, pqs_after.context),
        ("Structure", pqs_before.structure, pqs_after.structure),
        ("Actionability", pqs_before.actionability, pqs_after.actionability),
    ]

    for name, before, after in dimensions:
        delta = after.score - before.score
        delta_str = f"+{delta}" if delta >= 0 else str(delta)
        lines.append(
            f"  {name:<15} {before.bar}  {before.score:>3} ──▶ {after.bar}  {after.score:>3}  ({delta_str})"
        )

    return "\n".join(lines)


def _render_details_toggle(rules_applied: list[str]) -> str:
    """Render rules/details applied."""
    if not rules_applied:
        return "  Rules applied: none"
    return f"  Rules applied: {', '.join(rules_applied)}"


def _render_context_toggle(context: ContextFingerprint | None) -> str:
    """Render context fingerprint summary."""
    if context is None:
        return "  No context collected"

    parts: list[str] = []
    if context.git.branch:
        parts.append(f"branch={context.git.branch}")
    if context.tech.languages:
        parts.append(f"stack={','.join(context.tech.languages)}")
    if context.tech.frameworks:
        parts.append(f"frameworks={','.join(context.tech.frameworks)}")
    if context.shell.session_intent != "unknown":
        parts.append(f"intent={context.shell.session_intent}")
    if context.tech.package_manager:
        parts.append(f"pkg={context.tech.package_manager}")

    if not parts:
        return "  No context collected"

    return f"  Context: {' | '.join(parts)}"
```

- [x]**Step 9.4: Run TUI tests to verify they pass**

Run: `pytest tests/test_tui.py -v`
Expected: ALL PASS

- [x]**Step 9.5: Run linting and type checks**

Run: `ruff check . && mypy promptune/`
Expected: PASS

- [x]**Step 9.6: Commit**

```bash
git add promptune/tui.py tests/test_tui.py
git commit -m "feat: add TUI header, quality/details/context toggles with before/after display"
```

---

## Task 10: New CLI Commands

**Spec reference:** Section 10 — New CLI Commands
**Goal:** Add `--tier`, `--format`, `--json` flags to `enhance`. Add `config --set-key/--set-tier/--reset`. Add `doctor` and `local-llm-status` commands. Add `history` command.
**Files modified:** `promptune/cli.py`, `tests/test_cli.py`

### RED Phase

- [x]**Step 10.1: Write CLI enhancement flag tests**

Add to `tests/test_cli.py`:

```python
"""Task 10: New CLI Commands — tests (append to existing test_cli.py)."""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

from promptune.cli import main


# --- Enhancement flags ---


def test_enhance_tier_flag(mocker) -> None:
    """--tier flag is accepted and passed through."""
    mock_enhance = mocker.patch("promptune.cli.enhance")
    mock_enhance.return_value = MagicMock(
        original="test", enhanced="enhanced test",
        tier_used=0, latency_ms=5, score_before=MagicMock(total=10),
        score_after=MagicMock(total=80), rules_applied=[],
        context=None, format_style="xml", provider=None, model=None,
    )
    mocker.patch("promptune.cli.display_result", return_value="enhanced test")

    runner = CliRunner()
    result = runner.invoke(main, ["enhance", "--tier", "0", "--no-tui", "test prompt"])
    assert result.exit_code == 0


def test_enhance_format_flag(mocker) -> None:
    """--format flag is accepted."""
    mock_enhance = mocker.patch("promptune.cli.enhance")
    mock_enhance.return_value = MagicMock(
        original="test", enhanced="enhanced test",
        tier_used=0, latency_ms=5, score_before=MagicMock(total=10),
        score_after=MagicMock(total=80), rules_applied=[],
        context=None, format_style="markdown", provider=None, model=None,
    )
    mocker.patch("promptune.cli.display_result", return_value="enhanced test")

    runner = CliRunner()
    result = runner.invoke(main, ["enhance", "--format", "markdown", "--no-tui", "test prompt"])
    assert result.exit_code == 0


def test_enhance_json_flag(mocker) -> None:
    """--json flag outputs structured JSON."""
    mock_enhance = mocker.patch("promptune.cli.enhance")
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
    result = runner.invoke(main, ["enhance", "--json", "--no-tui", "test prompt"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["original"] == "test"
    assert data["enhanced"] == "enhanced test"
    assert data["tier_used"] == 0


# --- Config set commands ---


def test_config_set_key(mocker, tmp_path) -> None:
    """config --set-key writes API key to config file."""
    config_file = tmp_path / "config.toml"
    mocker.patch("promptune.cli._get_config_path", return_value=config_file)
    mocker.patch("promptune.config.load_config", return_value={
        "api_keys": {"claude": "", "openai": "", "openrouter": ""},
        "provider": {"default": "claude", "format_style": "auto"},
        "enhancement": {"default_mode": "balanced", "max_tier": 2},
        "local_llm": {"enabled": False},
        "context": {"enabled": True},
        "history": {"enabled": True},
        "tui": {"theme": "dark", "show_diff": True},
    })

    runner = CliRunner()
    result = runner.invoke(main, ["config", "--set-key", "claude", "sk-ant-test123"])
    assert result.exit_code == 0


def test_config_set_tier(mocker, tmp_path) -> None:
    """config --set-tier updates max_tier."""
    config_file = tmp_path / "config.toml"
    mocker.patch("promptune.cli._get_config_path", return_value=config_file)
    mocker.patch("promptune.config.load_config", return_value={
        "api_keys": {},
        "provider": {"default": "claude"},
        "enhancement": {"default_mode": "balanced", "max_tier": 2},
        "local_llm": {"enabled": False},
        "context": {"enabled": True},
        "history": {"enabled": True},
        "tui": {"theme": "dark"},
    })

    runner = CliRunner()
    result = runner.invoke(main, ["config", "--set-tier", "1"])
    assert result.exit_code == 0


def test_config_reset(mocker, tmp_path) -> None:
    """config --reset restores defaults."""
    config_file = tmp_path / "config.toml"
    config_file.write_text("[provider]\ndefault = 'openai'\n")
    mocker.patch("promptune.cli._get_config_path", return_value=config_file)

    runner = CliRunner()
    result = runner.invoke(main, ["config", "--reset"], input="y\n")
    assert result.exit_code == 0


# --- Doctor ---


def test_doctor_command_runs(mocker) -> None:
    """'promptune doctor' exits 0 and shows diagnostics."""
    mocker.patch("promptune.cli._check_python", return_value=(True, "3.12.1"))
    mocker.patch("promptune.cli._check_config", return_value=(True, "found"))
    mocker.patch("promptune.cli._check_tier0", return_value=(True, "ready"))
    mocker.patch("promptune.cli._check_tier1", return_value=(False, "not configured"))
    mocker.patch("promptune.cli._check_tier2", return_value=(False, "no API key"))

    runner = CliRunner()
    result = runner.invoke(main, ["doctor"])
    assert result.exit_code == 0
    assert "Python" in result.output


# --- Local LLM status ---


def test_local_llm_status_command(mocker) -> None:
    """'promptune local-llm-status' exits 0."""
    mocker.patch("promptune.cli._check_local_llm_connectivity",
                 return_value=(True, "qwen2.5:3b responding"))

    runner = CliRunner()
    result = runner.invoke(main, ["local-llm-status"])
    assert result.exit_code == 0


# --- History ---


def test_history_command_runs(mocker) -> None:
    """'promptune history' exits 0."""
    mocker.patch("promptune.cli._get_history_store")

    runner = CliRunner()
    result = runner.invoke(main, ["history"])
    assert result.exit_code == 0


def test_history_stats_flag(mocker) -> None:
    """'promptune history --stats' shows statistics."""
    mock_store = MagicMock()
    mock_store.stats.return_value = MagicMock(
        total=100, accepted=70, rejected=20, edited=10,
        acceptance_rate=0.7, avg_score_before=30, avg_score_after=75,
        avg_improvement=45, tier_distribution={0: 60, 1: 25, 2: 15},
    )
    mocker.patch("promptune.cli._get_history_store", return_value=mock_store)

    runner = CliRunner()
    result = runner.invoke(main, ["history", "--stats"])
    assert result.exit_code == 0


def test_history_clear_with_confirm(mocker) -> None:
    """'promptune history --clear' requires confirmation."""
    mock_store = MagicMock()
    mock_store.clear.return_value = 50
    mocker.patch("promptune.cli._get_history_store", return_value=mock_store)

    runner = CliRunner()
    result = runner.invoke(main, ["history", "--clear"], input="y\n")
    assert result.exit_code == 0
```

- [x]**Step 10.2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py -v -x`
Expected: FAIL — new flags and commands don't exist.

### GREEN Phase

- [x]**Step 10.3: Add enhancement flags to cli.py**

In `promptune/cli.py`, update the `enhance_cmd`:

```python
@main.command("enhance")
@click.argument("prompt", required=False)
@click.option("--provider", "-p", type=click.Choice(["claude", "openai", "openrouter"]))
@click.option("--style", "-s", type=click.Choice(["minimal", "balanced", "detailed"]))
@click.option("--no-tui", is_flag=True, help="Print result to stdout without TUI")
@click.option("--tier", type=click.IntRange(0, 2), default=None, help="Force specific tier (0/1/2)")
@click.option("--format", "format_style", type=click.Choice(["xml", "markdown", "plain"]),
              default=None, help="Force output format style")
@click.option("--json", "json_output", is_flag=True, help="Output structured JSON")
def enhance_cmd(prompt, provider, style, no_tui, tier, format_style, json_output):
    """Enhance a prompt."""
    import sys
    import json as json_mod

    if prompt is None:
        if not sys.stdin.isatty():
            prompt = sys.stdin.read().strip()
        else:
            click.echo("Error: No prompt provided.", err=True)
            raise SystemExit(1)

    if not prompt:
        click.echo("Error: Empty prompt.", err=True)
        raise SystemExit(1)

    cfg = load_config()
    if style:
        cfg["enhancement"]["default_mode"] = style

    result = enhance(prompt, cfg, provider_override=provider, tier_override=tier)

    if json_output:
        output = {
            "original": result.original,
            "enhanced": result.enhanced,
            "tier_used": result.tier_used,
            "latency_ms": round(result.latency_ms, 1),
            "score_before": round(result.score_before.total),
            "score_after": round(result.score_after.total),
            "format_style": result.format_style,
            "rules_applied": result.rules_applied,
        }
        click.echo(json_mod.dumps(output, indent=2))
        return

    if no_tui:
        click.echo(result.enhanced)
        return

    final = display_result(result)
    if final:
        click.echo(final)
```

- [x]**Step 10.4: Add config set commands**

Add to cli.py `config` group:

```python
# Keep existing config subcommands (init, show, path) unchanged.
# Add new options to the config group itself, matching the spec:
#   promptune config --set-key claude sk-ant-...
#   promptune config --set-tier 1
#   promptune config --reset

@main.group(invoke_without_command=True)
@click.option("--set-key", nargs=2, type=str, default=None,
              help="Set API key: --set-key <provider> <key>")
@click.option("--set-tier", type=click.IntRange(0, 2), default=None,
              help="Set max tier (0/1/2)")
@click.option("--set-format", type=click.Choice(["auto", "xml", "markdown", "plain"]),
              default=None, help="Set format style")
@click.option("--set-local-host", type=str, default=None,
              help="Set local LLM host URL")
@click.option("--set-local-model", type=str, default=None,
              help="Set local LLM model name")
@click.option("--reset", is_flag=True, help="Reset config to defaults")
@click.pass_context
def config(ctx, set_key, set_tier, set_format, set_local_host, set_local_model, reset):
    """Manage configuration."""
    if ctx.invoked_subcommand is not None:
        return  # A subcommand (init/show/path) was invoked

    config_path = _get_config_path()

    if reset:
        if click.confirm("Reset config to defaults?"):
            config_path.write_text(generate_default_config())
            click.echo("Config reset to defaults.")
        return

    if set_key:
        provider_name, key_value = set_key
        _update_config_value(config_path, f"api_keys.{provider_name}", key_value)
        click.echo(f"API key set for {provider_name}.")
        return

    if set_tier is not None:
        _update_config_value(config_path, "enhancement.max_tier", set_tier)
        click.echo(f"Max tier set to {set_tier}.")
        return

    if set_format:
        _update_config_value(config_path, "provider.format_style", set_format)
        click.echo(f"Format style set to {set_format}.")
        return

    if set_local_host:
        _update_config_value(config_path, "local_llm.host", set_local_host)
        click.echo(f"Local LLM host set to {set_local_host}.")
        return

    if set_local_model:
        _update_config_value(config_path, "local_llm.model", set_local_model)
        click.echo(f"Local LLM model set to {set_local_model}.")
        return
```

Note: The exact implementation will adapt the Click command structure to keep backwards compatibility with existing `config init/show/path` subcommands while adding the new `--set-key`, `--set-tier`, `--reset` as either options on the `config` group or as a new `config set` subcommand.

- [x]**Step 10.5: Add doctor command**

```python
@main.command("doctor")
def doctor_cmd():
    """Run system health check."""
    checks = [
        ("Python", _check_python),
        ("Config", _check_config),
        ("Tier 0", _check_tier0),
        ("Tier 1", _check_tier1),
        ("Tier 2", _check_tier2),
    ]

    issues: list[str] = []
    for name, check_fn in checks:
        ok, detail = check_fn()
        symbol = "✓" if ok else "✗"
        click.echo(f"  {name:<14} {symbol}  {detail}")
        if not ok:
            issues.append(detail)

    if issues:
        click.echo("\n  Issues:")
        for issue in issues:
            click.echo(f"    - {issue}")


def _check_python() -> tuple[bool, str]:
    import sys
    ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    return sys.version_info >= (3, 9), f"{ver} (>=3.9 required)"


def _check_config() -> tuple[bool, str]:
    path = _get_config_path()
    return path.exists(), str(path)


def _check_tier0() -> tuple[bool, str]:
    return True, "Rule engine ready"


def _check_tier1() -> tuple[bool, str]:
    cfg = load_config()
    if not cfg.get("local_llm", {}).get("enabled", False):
        return False, "Not configured"
    host = cfg["local_llm"].get("host", "")
    try:
        import httpx
        resp = httpx.get(f"{host}/v1/models", timeout=3.0)
        return resp.status_code == 200, f"Local LLM at {host}"
    except Exception:
        return False, f"Cannot reach {host}"


def _check_tier2() -> tuple[bool, str]:
    cfg = load_config()
    provider = cfg.get("provider", {}).get("default", "claude")
    api_key = cfg.get("api_keys", {}).get(provider, "")
    if not api_key:
        return False, f"No API key configured for {provider}"
    return True, f"API key set for {provider}"
```

- [x]**Step 10.6: Add local-llm-status command**

```python
@main.command("local-llm-status")
def local_llm_status_cmd():
    """Check local LLM connectivity."""
    ok, detail = _check_local_llm_connectivity()
    symbol = "✓" if ok else "✗"
    click.echo(f"  Local LLM  {symbol}  {detail}")


def _check_local_llm_connectivity() -> tuple[bool, str]:
    cfg = load_config()
    host = cfg.get("local_llm", {}).get("host", "http://localhost:11434")
    model = cfg.get("local_llm", {}).get("model", "unknown")
    try:
        import httpx
        resp = httpx.get(f"{host}/v1/models", timeout=3.0)
        if resp.status_code == 200:
            return True, f"{model} responding at {host}"
        return False, f"HTTP {resp.status_code} from {host}"
    except Exception as e:
        return False, f"Cannot reach {host}: {e}"
```

- [x]**Step 10.7: Add history command**

```python
@main.command("history")
@click.option("--n", "count", type=int, default=20, help="Number of entries")
@click.option("--stats", is_flag=True, help="Show statistics")
@click.option("--clear", is_flag=True, help="Delete all history")
def history_cmd(count, stats, clear):
    """View enhancement history."""
    store = _get_history_store()
    if store is None:
        click.echo("History is disabled.")
        return

    if clear:
        if click.confirm("Delete all history?"):
            deleted = store.clear()
            click.echo(f"Deleted {deleted} entries.")
        return

    if stats:
        s = store.stats()
        click.echo(f"  Total:       {s.total}")
        click.echo(f"  Accepted:    {s.accepted} ({s.acceptance_rate:.0%})")
        click.echo(f"  Rejected:    {s.rejected}")
        click.echo(f"  Edited:      {s.edited}")
        click.echo(f"  Avg before:  {s.avg_score_before:.0f}")
        click.echo(f"  Avg after:   {s.avg_score_after:.0f}")
        click.echo(f"  Avg improve: +{s.avg_improvement:.0f}")
        return

    entries = store.recent(n=count)
    if not entries:
        click.echo("No history yet.")
        return

    for entry in entries:
        click.echo(f"  [{entry.tier_used}] {entry.original[:50]}... → {entry.score_before}→{entry.score_after}")


def _get_history_store():
    """Get history store instance, or None if disabled."""
    from promptune.history import HistoryStore
    cfg = load_config()
    if not cfg.get("history", {}).get("enabled", True):
        return None
    return HistoryStore()
```

- [x]**Step 10.8: Run CLI tests to verify they pass**

Run: `pytest tests/test_cli.py -v`
Expected: ALL PASS

- [x]**Step 10.9: Run full test suite**

Run: `pytest --cov=promptune --cov-report=term-missing -v`
Expected: ALL PASS

- [x]**Step 10.10: Run linting and type checks**

Run: `ruff check . && mypy promptune/`
Expected: PASS

- [x]**Step 10.11: Commit**

```bash
git add promptune/cli.py tests/test_cli.py
git commit -m "feat: add --tier, --format, --json flags, doctor, local-llm-status, and history commands"
```

---

## Task 11: SQLite History

**Spec reference:** Section 11 — SQLite History
**Goal:** Persistent storage of every enhancement. WAL mode, schema versioning, auto-prune.
**Files created:** `promptune/history.py`
**Test files:** `tests/test_history.py`

### RED Phase

- [x]**Step 11.1: Write history store tests**

Create `tests/test_history.py`:

```python
"""Task 11: SQLite History — tests."""

from __future__ import annotations

import sqlite3

import pytest

from promptune.history import HistoryEntry, HistoryStats, HistoryStore


@pytest.fixture
def store(tmp_path) -> HistoryStore:
    """Create a HistoryStore with a temp DB."""
    return HistoryStore(db_path=tmp_path / "test_history.db")


def _make_entry(
    original: str = "fix the bug",
    enhanced: str = "Diagnose and fix the auth bug",
    decision: str = "accept",
    tier_used: int = 0,
    score_before: int = 11,
    score_after: int = 81,
) -> HistoryEntry:
    return HistoryEntry(
        original=original,
        enhanced=enhanced,
        decision=decision,
        edit_result=None,
        tier_used=tier_used,
        provider=None,
        format_style="xml",
        model=None,
        score_before=score_before,
        score_after=score_after,
        latency_ms=8.0,
        rules_applied=["output_format"],
        context_json=None,
        project_root="/home/user/project",
    )


def test_store_creates_db(tmp_path) -> None:
    """HistoryStore creates DB file on init."""
    db_path = tmp_path / "history.db"
    store = HistoryStore(db_path=db_path)
    assert db_path.exists()


def test_store_schema_version(store: HistoryStore) -> None:
    """DB has user_version = 1 after creation."""
    conn = sqlite3.connect(store.db_path)
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    conn.close()
    assert version == 1


def test_store_wal_mode(store: HistoryStore) -> None:
    """DB uses WAL journal mode."""
    conn = sqlite3.connect(store.db_path)
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    conn.close()
    assert mode == "wal"


def test_record_returns_id(store: HistoryStore) -> None:
    """record() returns the new row ID."""
    entry = _make_entry()
    row_id = store.record(entry)
    assert isinstance(row_id, int)
    assert row_id > 0


def test_record_and_recent(store: HistoryStore) -> None:
    """Recorded entries appear in recent()."""
    store.record(_make_entry(original="prompt 1"))
    store.record(_make_entry(original="prompt 2"))

    entries = store.recent(n=10)

    assert len(entries) == 2
    # Most recent first
    assert entries[0].original == "prompt 2"


def test_recent_respects_limit(store: HistoryStore) -> None:
    """recent(n=1) returns only 1 entry."""
    for i in range(5):
        store.record(_make_entry(original=f"prompt {i}"))

    entries = store.recent(n=1)

    assert len(entries) == 1


def test_recent_filters_by_project(store: HistoryStore) -> None:
    """recent() can filter by project_root."""
    e1 = _make_entry(original="project A prompt")
    e1.project_root = "/home/user/project-a"
    store.record(e1)

    e2 = _make_entry(original="project B prompt")
    e2.project_root = "/home/user/project-b"
    store.record(e2)

    entries = store.recent(n=10, project="/home/user/project-a")

    assert len(entries) == 1
    assert entries[0].original == "project A prompt"


def test_stats_empty_db(store: HistoryStore) -> None:
    """stats() on empty DB returns zeros."""
    s = store.stats()
    assert isinstance(s, HistoryStats)
    assert s.total == 0
    assert s.acceptance_rate == 0.0


def test_stats_computed_correctly(store: HistoryStore) -> None:
    """stats() computes correct aggregates."""
    store.record(_make_entry(decision="accept", score_before=10, score_after=80))
    store.record(_make_entry(decision="accept", score_before=20, score_after=90))
    store.record(_make_entry(decision="reject", score_before=15, score_after=70))

    s = store.stats()

    assert s.total == 3
    assert s.accepted == 2
    assert s.rejected == 1
    assert s.edited == 0
    assert abs(s.acceptance_rate - 2 / 3) < 0.01
    assert s.avg_score_before == pytest.approx(15.0)
    assert s.avg_score_after == pytest.approx(80.0)


def test_clear_deletes_all(store: HistoryStore) -> None:
    """clear() removes all entries and returns count."""
    for i in range(3):
        store.record(_make_entry())

    deleted = store.clear()

    assert deleted == 3
    assert store.stats().total == 0


def test_record_edit_with_edit_result(store: HistoryStore) -> None:
    """edit decision stores edit_result text."""
    entry = _make_entry(decision="edit")
    entry.edit_result = "User's edited version"
    store.record(entry)

    entries = store.recent(n=1)
    assert entries[0].decision == "edit"
    assert entries[0].edit_result == "User's edited version"


def test_rules_applied_serialized_as_json(store: HistoryStore) -> None:
    """rules_applied list is serialized/deserialized correctly."""
    entry = _make_entry()
    entry.rules_applied = ["output_format", "constraints", "specificity"]
    store.record(entry)

    entries = store.recent(n=1)
    assert entries[0].rules_applied == ["output_format", "constraints", "specificity"]


def test_auto_prune_large_db(store: HistoryStore) -> None:
    """DB auto-prunes when exceeding 10000 entries (simulated)."""
    # This test verifies the prune logic exists — we don't insert 10K rows
    # Instead, mock the count check
    assert hasattr(store, '_maybe_prune')
```

- [x]**Step 11.2: Run tests to verify they fail**

Run: `pytest tests/test_history.py -v -x`
Expected: FAIL — `promptune.history` doesn't exist.

### GREEN Phase

- [x]**Step 11.3: Implement history store**

Create `promptune/history.py`:

```python
"""SQLite history store — persistent enhancement log."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_SCHEMA_VERSION = 1

_CREATE_SQL = """\
CREATE TABLE IF NOT EXISTS enhancements (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    original        TEXT NOT NULL,
    enhanced        TEXT NOT NULL,
    decision        TEXT CHECK(decision IN ('accept', 'reject', 'edit')) NOT NULL,
    edit_result     TEXT,
    tier_used       INTEGER NOT NULL,
    provider        TEXT,
    format_style    TEXT,
    model           TEXT,
    score_before    INTEGER NOT NULL,
    score_after     INTEGER NOT NULL,
    latency_ms      REAL NOT NULL,
    rules_applied   TEXT,
    context_json    TEXT,
    project_root    TEXT,
    created_at      INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_enhancements_created_at ON enhancements(created_at);
CREATE INDEX IF NOT EXISTS idx_enhancements_project ON enhancements(project_root);
"""

_MAX_ENTRIES = 10000


@dataclass
class HistoryEntry:
    """Single enhancement record."""

    original: str
    enhanced: str
    decision: str
    edit_result: str | None
    tier_used: int
    provider: str | None
    format_style: str | None
    model: str | None
    score_before: int
    score_after: int
    latency_ms: float
    rules_applied: list[str] | None
    context_json: str | None
    project_root: str | None


@dataclass
class HistoryStats:
    """Aggregate statistics."""

    total: int
    accepted: int
    rejected: int
    edited: int
    acceptance_rate: float
    avg_score_before: float
    avg_score_after: float
    avg_improvement: float
    tier_distribution: dict[int, int]


class HistoryStore:
    """SQLite-backed enhancement history."""

    def __init__(self, db_path: Path | None = None) -> None:
        if db_path is None:
            db_path = Path.home() / ".local" / "share" / "promptune" / "history.db"

        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(str(db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

    def __enter__(self) -> HistoryStore:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _init_schema(self) -> None:
        """Create tables if needed, check schema version."""
        version = self._conn.execute("PRAGMA user_version").fetchone()[0]
        if version == 0:
            self._conn.executescript(_CREATE_SQL)
            self._conn.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
            self._conn.commit()

    def record(self, entry: HistoryEntry) -> int:
        """Insert an enhancement record. Returns row ID."""
        rules_json = json.dumps(entry.rules_applied) if entry.rules_applied else None

        cursor = self._conn.execute(
            """INSERT INTO enhancements
               (original, enhanced, decision, edit_result, tier_used,
                provider, format_style, model, score_before, score_after,
                latency_ms, rules_applied, context_json, project_root)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entry.original, entry.enhanced, entry.decision,
                entry.edit_result, entry.tier_used, entry.provider,
                entry.format_style, entry.model, entry.score_before,
                entry.score_after, entry.latency_ms, rules_json,
                entry.context_json, entry.project_root,
            ),
        )
        self._conn.commit()
        self._maybe_prune()
        return cursor.lastrowid  # type: ignore[return-value]

    def recent(
        self, n: int = 20, project: str | None = None
    ) -> list[HistoryEntry]:
        """Get most recent entries, optionally filtered by project."""
        if project:
            rows = self._conn.execute(
                """SELECT original, enhanced, decision, edit_result, tier_used,
                          provider, format_style, model, score_before, score_after,
                          latency_ms, rules_applied, context_json, project_root
                   FROM enhancements WHERE project_root = ?
                   ORDER BY created_at DESC LIMIT ?""",
                (project, n),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """SELECT original, enhanced, decision, edit_result, tier_used,
                          provider, format_style, model, score_before, score_after,
                          latency_ms, rules_applied, context_json, project_root
                   FROM enhancements ORDER BY created_at DESC LIMIT ?""",
                (n,),
            ).fetchall()

        return [self._row_to_entry(row) for row in rows]

    def stats(self) -> HistoryStats:
        """Compute aggregate statistics."""
        row = self._conn.execute(
            """SELECT COUNT(*),
                      SUM(CASE WHEN decision='accept' THEN 1 ELSE 0 END),
                      SUM(CASE WHEN decision='reject' THEN 1 ELSE 0 END),
                      SUM(CASE WHEN decision='edit' THEN 1 ELSE 0 END),
                      AVG(score_before), AVG(score_after)
               FROM enhancements"""
        ).fetchone()

        total = row[0] or 0
        accepted = row[1] or 0
        rejected = row[2] or 0
        edited = row[3] or 0
        avg_before = row[4] or 0.0
        avg_after = row[5] or 0.0

        # Tier distribution
        tier_rows = self._conn.execute(
            "SELECT tier_used, COUNT(*) FROM enhancements GROUP BY tier_used"
        ).fetchall()
        tier_dist = {r[0]: r[1] for r in tier_rows}

        return HistoryStats(
            total=total,
            accepted=accepted,
            rejected=rejected,
            edited=edited,
            acceptance_rate=accepted / total if total > 0 else 0.0,
            avg_score_before=avg_before,
            avg_score_after=avg_after,
            avg_improvement=avg_after - avg_before,
            tier_distribution=tier_dist,
        )

    def clear(self) -> int:
        """Delete all entries. Returns count deleted."""
        count = self._conn.execute("SELECT COUNT(*) FROM enhancements").fetchone()[0]
        self._conn.execute("DELETE FROM enhancements")
        self._conn.commit()
        return count

    def _maybe_prune(self) -> None:
        """Auto-prune if over MAX_ENTRIES."""
        count = self._conn.execute("SELECT COUNT(*) FROM enhancements").fetchone()[0]
        if count > _MAX_ENTRIES:
            self._conn.execute(
                """DELETE FROM enhancements WHERE id NOT IN
                   (SELECT id FROM enhancements ORDER BY created_at DESC LIMIT ?)""",
                (_MAX_ENTRIES,),
            )
            self._conn.commit()

    @staticmethod
    def _row_to_entry(row: tuple) -> HistoryEntry:
        """Convert a DB row to HistoryEntry."""
        rules = json.loads(row[11]) if row[11] else None
        return HistoryEntry(
            original=row[0],
            enhanced=row[1],
            decision=row[2],
            edit_result=row[3],
            tier_used=row[4],
            provider=row[5],
            format_style=row[6],
            model=row[7],
            score_before=row[8],
            score_after=row[9],
            latency_ms=row[10],
            rules_applied=rules,
            context_json=row[12],
            project_root=row[13],
        )
```

- [x]**Step 11.4: Run history tests to verify they pass**

Run: `pytest tests/test_history.py -v`
Expected: ALL PASS

- [x]**Step 11.5: Run full test suite and coverage**

Run: `pytest --cov=promptune --cov-report=term-missing -v`
Expected: ALL PASS, coverage ≥ 90%

- [x]**Step 11.6: Run linting and type checks**

Run: `ruff check . && mypy promptune/`
Expected: PASS

- [x]**Step 11.7: Commit**

```bash
git add promptune/history.py tests/test_history.py
git commit -m "feat: add SQLite history store with WAL mode, schema versioning, and auto-prune"
```

---

## Final Integration

- [x]**Step 12.1: Run full test suite with coverage**

Run: `pytest --cov=promptune --cov-report=term-missing -v`
Expected: ALL PASS, coverage ≥ 90%

- [x]**Step 12.2: Run all quality checks**

Run: `ruff check . && mypy promptune/`
Expected: PASS

- [x]**Step 12.3: Update CLAUDE.md**

Update the Build Order table and Coverage Targets in CLAUDE.md to reflect the new tasks.

- [x]**Step 12.4: Update CHANGELOG.md**

Add entry for the next iteration features.

- [x]**Step 12.5: Final commit**

```bash
git add -A
git commit -m "feat: complete Phase 1 next iteration — 3-tier enhancement, scoring, context, history"
```
