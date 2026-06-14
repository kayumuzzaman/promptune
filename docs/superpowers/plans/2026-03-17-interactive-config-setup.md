# Interactive Config Setup Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the silent `promptune config init` with an interactive wizard that guides users through provider selection and API key setup.

**Architecture:** New `promptune/setup.py` module with Click-based prompts for interactive setup. Minimal changes to `engine.py` (make registry public) and `cli.py` (wire wizard into `config init`). TOML written via manual string formatting (no new dependencies).

**Tech Stack:** Python 3.9+, Click (prompts/confirm), Rich (header display), existing config/provider infrastructure.

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `promptune/setup.py` | Create | All wizard logic: prompting, validation, TOML writing |
| `tests/test_setup.py` | Create | Unit tests for setup module |
| `promptune/engine.py` | Modify (line 61) | Rename `_get_registry()` → `get_registry()` |
| `promptune/cli.py` | Modify (lines 276-294) | Wire interactive wizard into `config init` |
| `tests/test_cli.py` | Modify | Add CLI integration tests for new `config init` behavior |

---

## Chunk 1: Pure Functions and Engine Change

### Task 1: `validate_key_format()` and `KEY_PREFIXES`

**Files:**
- Create: `promptune/setup.py`
- Create: `tests/test_setup.py`

- [ ] **Step 1: Write failing tests for `validate_key_format`**

```python
# tests/test_setup.py
"""Interactive config setup tests."""

from __future__ import annotations

import pytest

from promptune.setup import KEY_PREFIXES, validate_key_format


class TestValidateKeyFormat:
    """API key format validation."""

    def test_valid_claude_key(self) -> None:
        assert validate_key_format("claude", "sk-ant-api03-abc123") is None

    def test_valid_openai_key(self) -> None:
        assert validate_key_format("openai", "sk-proj-abc123") is None

    def test_valid_openrouter_key(self) -> None:
        assert validate_key_format("openrouter", "sk-or-v1-abc123") is None

    def test_wrong_prefix_returns_warning(self) -> None:
        result = validate_key_format("claude", "sk-proj-wrong")
        assert result is not None
        assert "claude" in result.lower()

    def test_empty_key_returns_error(self) -> None:
        result = validate_key_format("claude", "")
        assert result is not None
        assert "required" in result.lower()

    def test_unknown_provider_accepts_any_nonempty(self) -> None:
        assert validate_key_format("custom_provider", "any-key-123") is None

    def test_unknown_provider_rejects_empty(self) -> None:
        result = validate_key_format("custom_provider", "")
        assert result is not None

    def test_key_prefixes_has_known_providers(self) -> None:
        assert "claude" in KEY_PREFIXES
        assert "openai" in KEY_PREFIXES
        assert "openrouter" in KEY_PREFIXES
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_setup.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'promptune.setup'`

- [ ] **Step 3: Implement `validate_key_format` and `KEY_PREFIXES`**

```python
# promptune/setup.py
"""Interactive config setup wizard."""

from __future__ import annotations

KEY_PREFIXES: dict[str, str] = {
    "claude": "sk-ant-",
    "openai": "sk-",
    "openrouter": "sk-or-",
}


def validate_key_format(provider: str, key: str) -> str | None:
    """Validate API key format. Returns warning/error string or None if OK.

    - Empty key -> error message (mandatory)
    - Wrong prefix -> warning message (advisory)
    - Unknown provider -> accepts any non-empty string
    """
    if not key:
        return "API key is required for your selected provider."

    expected_prefix = KEY_PREFIXES.get(provider)
    if expected_prefix is None:
        return None

    if not key.startswith(expected_prefix):
        return (
            f"Warning: Key doesn't look like a {provider} key "
            f"(expected prefix '{expected_prefix}'). Saving anyway."
        )

    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_setup.py -v`
Expected: 8 PASSED

- [ ] **Step 5: Run full gate**

Run: `ruff check . && mypy promptune/ && pytest -v`
Expected: All pass, no regressions

---

### Task 2: `mask_key()`

**Files:**
- Modify: `promptune/setup.py`
- Modify: `tests/test_setup.py`

- [ ] **Step 1: Write failing tests for `mask_key`**

Add to `tests/test_setup.py`:

```python
from promptune.setup import mask_key


class TestMaskKey:
    """API key masking for display."""

    def test_masks_normal_key(self) -> None:
        assert mask_key("sk-ant-api03-abc123xyz") == "sk-...3xyz"

    def test_empty_key_returns_empty(self) -> None:
        assert mask_key("") == ""

    def test_short_key_masks_all(self) -> None:
        # Keys shorter than 8 chars: show only last 4
        assert mask_key("abcd") == "****abcd"

    def test_medium_key(self) -> None:
        assert mask_key("sk-ant-xy") == "sk-...-xy"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_setup.py::TestMaskKey -v`
Expected: FAIL — `ImportError: cannot import name 'mask_key'`

- [ ] **Step 3: Implement `mask_key`**

Add to `promptune/setup.py`:

```python
def mask_key(key: str) -> str:
    """Mask API key for display, showing first 2 and last 4 chars.

    Returns empty string for empty input.
    Short keys (< 8 chars): '****' + last 4 (or full key if <= 4).
    Normal keys: first 2 chars + '...' + last 4 chars.
    """
    if not key:
        return ""
    if len(key) < 8:
        return "****" + key[-4:] if len(key) > 4 else "*" * len(key)
    return key[:2] + "..." + key[-4:]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_setup.py::TestMaskKey -v`
Expected: 4 PASSED

- [ ] **Step 5: Run full gate**

Run: `ruff check . && mypy promptune/ && pytest -v`
Expected: All pass

---

### Task 3: `write_config()`

**Files:**
- Modify: `promptune/setup.py`
- Modify: `tests/test_setup.py`

- [ ] **Step 1: Write failing tests for `write_config`**

Add to `tests/test_setup.py`:

```python
from pathlib import Path

from promptune.config import load_config
from promptune.setup import write_config


class TestWriteConfig:
    """TOML config file writing."""

    def test_creates_file(self, tmp_path: Path) -> None:
        config_path = tmp_path / "promptune" / "config.toml"
        config = {
            "provider": {"default": "openai"},
            "api_keys": {"openai": "sk-test123"},
        }
        write_config(config_path, config)
        assert config_path.exists()

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        config_path = tmp_path / "deep" / "nested" / "config.toml"
        write_config(config_path, {"provider": {"default": "claude"}})
        assert config_path.parent.exists()

    def test_roundtrips_through_load_config(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.toml"
        config = {
            "provider": {
                "default": "openai",
                "format_style": "markdown",
                "model_claude": "claude-haiku-4-5-20251001",
                "model_openai": "gpt-4o-mini",
                "model_openrouter": "anthropic/claude-haiku",
            },
            "api_keys": {
                "claude": "",
                "openai": "sk-test123",
                "openrouter": "",
            },
            "enhancement": {
                "max_tier": 1,
                "default_mode": "detailed",
                "max_tokens_output": 400,
                "timeout_seconds": 10,
            },
        }
        write_config(config_path, config)
        loaded = load_config(config_path=config_path)
        assert loaded["provider"]["default"] == "openai"
        assert loaded["provider"]["format_style"] == "markdown"
        assert loaded["api_keys"]["openai"] == "sk-test123"
        assert loaded["enhancement"]["max_tier"] == 1
        assert loaded["enhancement"]["default_mode"] == "detailed"

    def test_contains_all_sections(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.toml"
        config = {
            "provider": {"default": "claude"},
            "api_keys": {"claude": "sk-ant-test"},
            "enhancement": {"max_tier": 2, "default_mode": "balanced"},
        }
        write_config(config_path, config)
        content = config_path.read_text()
        assert "[provider]" in content
        assert "[api_keys]" in content
        assert "[enhancement]" in content
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_setup.py::TestWriteConfig -v`
Expected: FAIL — `ImportError: cannot import name 'write_config'`

- [ ] **Step 3: Implement `write_config`**

Add to `promptune/setup.py`:

```python
import copy
from pathlib import Path
from typing import Any

from promptune.config import DEFAULT_CONFIG


def _format_toml_value(value: object) -> str:
    """Format a Python value as a TOML value string."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return f'"{value}"'
    return str(value)


def write_config(config_path: Path, config: dict[str, Any]) -> None:
    """Write config dict to TOML file.

    Merges with DEFAULT_CONFIG for any missing sections/keys,
    then serializes using manual string formatting.
    Creates parent directories if needed.
    """
    merged = copy.deepcopy(DEFAULT_CONFIG)
    for section, values in config.items():
        if isinstance(values, dict) and section in merged:
            merged[section].update(values)
        else:
            merged[section] = values

    config_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = ["# Promptune Configuration\n"]

    for section, values in merged.items():
        if not isinstance(values, dict):
            continue
        lines.append(f"[{section}]")
        for key, val in values.items():
            lines.append(f"{key} = {_format_toml_value(val)}")
        lines.append("")

    config_path.write_text("\n".join(lines) + "\n")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_setup.py::TestWriteConfig -v`
Expected: 4 PASSED

- [ ] **Step 5: Run full gate**

Run: `ruff check . && mypy promptune/ && pytest -v`
Expected: All pass

---

### Task 4: Rename `_get_registry()` to `get_registry()` in engine.py

**Files:**
- Modify: `promptune/engine.py` (lines 61, 85)
- Modify: `tests/test_engine.py` (if any direct references)

- [ ] **Step 1: Write a failing test for the public name**

Add to `tests/test_engine.py`:

```python
from promptune.engine import get_registry


def test_get_registry_returns_known_providers() -> None:
    """get_registry() returns registry with claude, openai, openrouter."""
    registry = get_registry()
    providers = registry.list()
    assert "claude" in providers
    assert "openai" in providers
    assert "openrouter" in providers
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_engine.py::test_get_registry_returns_known_providers -v`
Expected: FAIL — `ImportError: cannot import name 'get_registry'`

- [ ] **Step 3: Rename in engine.py**

In `promptune/engine.py`, change line 61:
```python
# Before:
def _get_registry() -> ProviderRegistry:
# After:
def get_registry() -> ProviderRegistry:
```

And update line 85 in `_create_cloud_provider`:
```python
# Before:
    registry = _get_registry()
# After:
    registry = get_registry()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_engine.py -v`
Expected: All PASSED (existing + new)

- [ ] **Step 5: Run full gate**

Run: `ruff check . && mypy promptune/ && pytest -v`
Expected: All pass, no regressions. Existing engine tests still work because they mock `_create_cloud_provider`, not `_get_registry` directly.

---

## Chunk 2: Interactive Prompt Functions

### Task 5: `_prompt_provider()`

**Files:**
- Modify: `promptune/setup.py`
- Modify: `tests/test_setup.py`

- [ ] **Step 1: Write failing tests for `_prompt_provider`**

Add to `tests/test_setup.py`:

```python
from unittest.mock import patch

from promptune.providers import ProviderRegistry
from promptune.setup import _prompt_provider


@pytest.fixture()
def mock_registry() -> ProviderRegistry:
    """Registry with test providers."""
    from promptune.engine import get_registry
    return get_registry()


class TestPromptProvider:
    """Provider selection prompt."""

    def test_selects_provider(self, mock_registry: ProviderRegistry) -> None:
        with patch("click.prompt", return_value="openai"):
            result = _prompt_provider(mock_registry, default="claude")
        assert result == "openai"

    def test_uses_default_on_enter(self, mock_registry: ProviderRegistry) -> None:
        with patch("click.prompt", return_value="claude"):
            result = _prompt_provider(mock_registry, default="claude")
        assert result == "claude"

    def test_shows_available_providers(self, mock_registry: ProviderRegistry) -> None:
        with patch("click.prompt", return_value="claude") as mock_prompt:
            _prompt_provider(mock_registry, default="claude")
        call_kwargs = mock_prompt.call_args
        # The prompt text should contain provider names
        prompt_text = call_kwargs[0][0] if call_kwargs[0] else call_kwargs[1].get("text", "")
        assert "claude" in prompt_text.lower() or "openai" in prompt_text.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_setup.py::TestPromptProvider -v`
Expected: FAIL — `ImportError: cannot import name '_prompt_provider'`

- [ ] **Step 3: Implement `_prompt_provider`**

Add to `promptune/setup.py`:

```python
import click

from promptune.providers import ProviderRegistry


def _prompt_provider(registry: ProviderRegistry, default: str) -> str:
    """Prompt user to select a provider from the registry.

    Shows available providers as choices with the current default.
    """
    providers = sorted(registry.list())
    choices = "/".join(providers)

    provider = click.prompt(
        f"  Provider [{choices}]",
        type=click.Choice(providers, case_sensitive=False),
        default=default,
        show_choices=False,
        show_default=False,
    )
    return str(provider)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_setup.py::TestPromptProvider -v`
Expected: 3 PASSED

- [ ] **Step 5: Run full gate**

Run: `ruff check . && mypy promptune/ && pytest -v`
Expected: All pass

---

### Task 6: `_prompt_api_key()`

**Files:**
- Modify: `promptune/setup.py`
- Modify: `tests/test_setup.py`

- [ ] **Step 1: Write failing tests for `_prompt_api_key`**

Add to `tests/test_setup.py`:

```python
from promptune.setup import _prompt_api_key


class TestPromptApiKey:
    """API key prompt with masking and validation."""

    def test_accepts_valid_key(self) -> None:
        with patch("click.prompt", return_value="sk-ant-test123"):
            with patch("click.echo"):
                result = _prompt_api_key("claude", "")
        assert result == "sk-ant-test123"

    def test_keeps_existing_key_on_enter(self) -> None:
        with patch("click.prompt", return_value="sk-ant-existing"):
            with patch("click.echo"):
                result = _prompt_api_key("claude", "sk-ant-existing")
        assert result == "sk-ant-existing"

    def test_shows_masked_existing_in_prompt(self) -> None:
        with patch("click.prompt", return_value="sk-ant-existing") as mock_prompt:
            with patch("click.echo"):
                _prompt_api_key("claude", "sk-ant-existing")
        prompt_text = mock_prompt.call_args[0][0]
        assert "..." in prompt_text  # masked hint visible

    def test_warns_on_bad_prefix(self) -> None:
        with patch("click.prompt", return_value="wrong-prefix-key"):
            with patch("click.echo") as mock_echo:
                _prompt_api_key("claude", "")
        # Should have printed a warning
        echo_calls = [str(c) for c in mock_echo.call_args_list]
        warning_printed = any("warning" in c.lower() for c in echo_calls)
        assert warning_printed

    def test_no_default_when_existing_empty(self) -> None:
        with patch("click.prompt", return_value="sk-ant-new") as mock_prompt:
            with patch("click.echo"):
                _prompt_api_key("claude", "")
        call_kwargs = mock_prompt.call_args[1] if mock_prompt.call_args[1] else {}
        # When no existing key, default should not be set
        assert call_kwargs.get("default") is None or call_kwargs.get("default") == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_setup.py::TestPromptApiKey -v`
Expected: FAIL — `ImportError: cannot import name '_prompt_api_key'`

- [ ] **Step 3: Implement `_prompt_api_key`**

Add to `promptune/setup.py`:

```python
def _prompt_api_key(provider: str, existing: str) -> str:
    """Prompt for API key with masking and format validation.

    - existing non-empty: shows masked hint, default=existing (Enter keeps it)
    - existing empty: no default, forces input
    - Validates format and prints warning/success feedback
    """
    if existing:
        masked = mask_key(existing)
        prompt_text = f"  {provider.title()} API key [{masked}]"
        key = click.prompt(
            prompt_text,
            default=existing,
            hide_input=True,
            show_default=False,
        )
    else:
        prompt_text = f"  {provider.title()} API key"
        while True:
            key = click.prompt(
                prompt_text,
                hide_input=True,
                default="",
                show_default=False,
            )
            if key:
                break
            click.echo(
                "  Error: API key is required for your "
                "selected provider.",
                err=True,
            )

    warning = validate_key_format(provider, key)
    if warning and "required" not in warning.lower():
        click.echo(f"  {warning}")
    elif warning is None:
        click.echo("  \u2713 Key format looks valid.")

    return str(key)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_setup.py::TestPromptApiKey -v`
Expected: 5 PASSED

- [ ] **Step 5: Run full gate**

Run: `ruff check . && mypy promptune/ && pytest -v`
Expected: All pass

---

### Task 7: `_prompt_optional_settings()`

**Files:**
- Modify: `promptune/setup.py`
- Modify: `tests/test_setup.py`

- [ ] **Step 1: Write failing tests for `_prompt_optional_settings`**

Add to `tests/test_setup.py`:

```python
from promptune.setup import _prompt_optional_settings


class TestPromptOptionalSettings:
    """Optional advanced settings behind y/N gate."""

    def test_skips_when_declined(self) -> None:
        defaults = {
            "default_mode": "balanced",
            "max_tier": 2,
            "format_style": "auto",
        }
        with patch("click.confirm", return_value=False):
            result = _prompt_optional_settings(defaults)
        assert result == defaults

    def test_collects_when_accepted(self) -> None:
        defaults = {
            "default_mode": "balanced",
            "max_tier": 2,
            "format_style": "auto",
        }
        with patch("click.confirm", return_value=True):
            with patch("click.prompt", side_effect=["detailed", 1, "xml"]):
                result = _prompt_optional_settings(defaults)
        assert result["default_mode"] == "detailed"
        assert result["max_tier"] == 1
        assert result["format_style"] == "xml"

    def test_keeps_defaults_on_enter(self) -> None:
        defaults = {
            "default_mode": "balanced",
            "max_tier": 2,
            "format_style": "auto",
        }
        with patch("click.confirm", return_value=True):
            with patch("click.prompt", side_effect=["balanced", 2, "auto"]):
                result = _prompt_optional_settings(defaults)
        assert result == defaults
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_setup.py::TestPromptOptionalSettings -v`
Expected: FAIL — `ImportError: cannot import name '_prompt_optional_settings'`

- [ ] **Step 3: Implement `_prompt_optional_settings`**

Add to `promptune/setup.py`:

```python
def _prompt_optional_settings(defaults: dict[str, Any]) -> dict[str, Any]:
    """Prompt for optional advanced settings behind a y/N gate.

    Returns dict with keys: default_mode, max_tier, format_style.
    If user declines, returns defaults unchanged.
    """
    if not click.confirm(
        "  Configure advanced settings?", default=False
    ):
        return dict(defaults)

    click.echo()

    mode = click.prompt(
        "  Enhancement style [minimal/balanced/detailed]",
        type=click.Choice(
            ["minimal", "balanced", "detailed"],
            case_sensitive=False,
        ),
        default=defaults["default_mode"],
        show_choices=False,
        show_default=False,
    )

    tier = click.prompt(
        "  Max tier (0=rules, 1=+local, 2=+cloud) [0/1/2]",
        type=click.IntRange(0, 2),
        default=defaults["max_tier"],
        show_default=False,
    )

    fmt = click.prompt(
        "  Format style [auto/xml/markdown/plain]",
        type=click.Choice(
            ["auto", "xml", "markdown", "plain"],
            case_sensitive=False,
        ),
        default=defaults["format_style"],
        show_choices=False,
        show_default=False,
    )

    return {
        "default_mode": str(mode),
        "max_tier": int(tier),
        "format_style": str(fmt),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_setup.py::TestPromptOptionalSettings -v`
Expected: 3 PASSED

- [ ] **Step 5: Run full gate**

Run: `ruff check . && mypy promptune/ && pytest -v`
Expected: All pass

---

## Chunk 3: Orchestrator and CLI Integration

### Task 8: `run_interactive_setup()`

**Files:**
- Modify: `promptune/setup.py`
- Modify: `tests/test_setup.py`

- [ ] **Step 1: Write failing tests for `run_interactive_setup`**

Add to `tests/test_setup.py`:

```python
from promptune.setup import run_interactive_setup


class TestRunInteractiveSetup:
    """Full wizard orchestration."""

    def test_first_time_setup(
        self, tmp_path: Path, mock_registry: ProviderRegistry
    ) -> None:
        config_path = tmp_path / "config.toml"
        with patch("click.prompt", side_effect=["claude", "sk-ant-test123"]):
            with patch("click.confirm", return_value=False):
                with patch("click.echo"):
                    result = run_interactive_setup(config_path, mock_registry)
        assert result["provider"]["default"] == "claude"
        assert result["api_keys"]["claude"] == "sk-ant-test123"

    def test_prefills_existing_config(
        self, tmp_path: Path, mock_registry: ProviderRegistry
    ) -> None:
        config_path = tmp_path / "config.toml"
        # Create existing config
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            '[provider]\ndefault = "openai"\n\n'
            '[api_keys]\nopenai = "sk-existing"\n'
        )
        with patch("click.prompt", side_effect=["openai", "sk-existing"]):
            with patch("click.confirm", return_value=False):
                with patch("click.echo"):
                    result = run_interactive_setup(config_path, mock_registry)
        assert result["provider"]["default"] == "openai"
        assert result["api_keys"]["openai"] == "sk-existing"

    def test_with_advanced_settings(
        self, tmp_path: Path, mock_registry: ProviderRegistry
    ) -> None:
        config_path = tmp_path / "config.toml"
        with patch(
            "click.prompt",
            side_effect=[
                "openai",         # provider
                "sk-test123",     # api key
                "detailed",       # style
                1,                # max tier
                "xml",            # format
            ],
        ):
            with patch("click.confirm", return_value=True):
                with patch("click.echo"):
                    result = run_interactive_setup(config_path, mock_registry)
        assert result["provider"]["default"] == "openai"
        assert result["api_keys"]["openai"] == "sk-test123"
        assert result["enhancement"]["default_mode"] == "detailed"
        assert result["enhancement"]["max_tier"] == 1
        assert result["provider"]["format_style"] == "xml"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_setup.py::TestRunInteractiveSetup -v`
Expected: FAIL — `ImportError: cannot import name 'run_interactive_setup'`

- [ ] **Step 3: Implement `run_interactive_setup`**

Add to `promptune/setup.py`:

```python
from promptune.config import DEFAULT_CONFIG, load_config


def run_interactive_setup(
    config_path: Path, registry: ProviderRegistry
) -> dict[str, Any]:
    """Run the interactive config setup wizard.

    Loads existing config for pre-filling if config_path exists.
    Prompts for mandatory fields (provider, API key) and optional
    advanced settings. Returns a complete config dict ready to write.
    """
    click.echo()
    click.echo("  Promptune Setup")
    click.echo("  \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500")
    click.echo()

    # Load existing config for pre-filling
    existing = load_config(config_path=config_path)

    # Mandatory: provider
    provider = _prompt_provider(
        registry, default=existing["provider"]["default"]
    )

    # Mandatory: API key for selected provider
    existing_key = existing["api_keys"].get(provider, "")
    api_key = _prompt_api_key(provider, existing_key)

    # Optional: advanced settings
    click.echo()
    optional_defaults = {
        "default_mode": existing["enhancement"]["default_mode"],
        "max_tier": existing["enhancement"]["max_tier"],
        "format_style": existing["provider"]["format_style"],
    }
    optional = _prompt_optional_settings(optional_defaults)

    # Build complete config
    config = copy.deepcopy(existing)
    config["provider"]["default"] = provider
    config["api_keys"][provider] = api_key
    config["enhancement"]["default_mode"] = optional["default_mode"]
    config["enhancement"]["max_tier"] = optional["max_tier"]
    config["provider"]["format_style"] = optional["format_style"]

    return config
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_setup.py::TestRunInteractiveSetup -v`
Expected: 3 PASSED

- [ ] **Step 5: Run full gate**

Run: `ruff check . && mypy promptune/ && pytest -v`
Expected: All pass

---

### Task 9: Wire wizard into `config init` CLI command

**Files:**
- Modify: `promptune/cli.py` (lines 276-294)
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests for new `config init` behavior**

Add to `tests/test_cli.py`:

```python
from pathlib import Path


class TestConfigInitInteractive:
    """Interactive config init wizard via CLI."""

    def test_interactive_creates_config(
        self, mocker, tmp_path: Path
    ) -> None:
        config_file = tmp_path / "config.toml"
        mocker.patch(
            "promptune.cli._get_config_path",
            return_value=config_file,
        )

        runner = CliRunner()
        # Simulate: choose claude, enter API key, decline advanced
        result = runner.invoke(
            main,
            ["config", "init"],
            input="claude\nsk-ant-test123\nn\n",
        )
        assert result.exit_code == 0
        assert config_file.exists()
        content = config_file.read_text()
        assert "sk-ant-test123" in content

    def test_interactive_with_existing_config(
        self, mocker, tmp_path: Path
    ) -> None:
        config_file = tmp_path / "config.toml"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(
            '[provider]\ndefault = "openai"\n\n'
            '[api_keys]\nopenai = "sk-existing"\n'
        )
        mocker.patch(
            "promptune.cli._get_config_path",
            return_value=config_file,
        )

        runner = CliRunner()
        # Just press Enter through everything (keep defaults)
        result = runner.invoke(
            main,
            ["config", "init"],
            input="\n\nn\n",
        )
        assert result.exit_code == 0

    def test_non_interactive_creates_default(
        self, mocker, tmp_path: Path
    ) -> None:
        config_file = tmp_path / "config.toml"
        mocker.patch(
            "promptune.cli._get_config_path",
            return_value=config_file,
        )
        # Force non-interactive by mocking isatty
        mocker.patch("sys.stdin.isatty", return_value=False)

        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(main, ["config", "init"])
        assert result.exit_code == 0
        assert config_file.exists()
        # Instructions printed to stderr
        assert "edit" in result.stderr.lower() or "config" in result.stderr.lower()

    def test_config_dir_flag_still_works(
        self, tmp_path: Path
    ) -> None:
        config_dir = tmp_path / "custom"
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["config", "init", "--config-dir", str(config_dir)],
            input="claude\nsk-ant-test\nn\n",
        )
        assert result.exit_code == 0
        assert (config_dir / "config.toml").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py::TestConfigInitInteractive -v`
Expected: FAIL — current `config init` doesn't prompt interactively

- [ ] **Step 3: Modify `config_init` in `cli.py`**

Replace the existing `config_init` function (lines 276-294 of `promptune/cli.py`) with:

```python
@config.command("init")
@click.option(
    "--config-dir",
    type=click.Path(),
    default=None,
    help="Directory to create config in.",
)
def config_init(config_dir: str | None) -> None:
    """Create or update config via interactive setup wizard."""
    import sys

    if config_dir:
        config_path = Path(config_dir) / "config.toml"
    else:
        config_path = _get_config_path()

    # Non-interactive: create default + print instructions
    if not sys.stdin.isatty():
        config_path.parent.mkdir(parents=True, exist_ok=True)
        if not config_path.exists():
            config_path.write_text(generate_default_config())
        click.echo(
            f"  No terminal detected. Config file created "
            f"with defaults at:\n"
            f"    {config_path}\n"
            f"  Edit it manually to set your provider and API key.",
            err=True,
        )
        return

    # Interactive: run wizard
    try:
        from promptune.engine import get_registry
        from promptune.setup import run_interactive_setup, write_config

        registry = get_registry()
        config = run_interactive_setup(config_path, registry)
        write_config(config_path, config)
        click.echo()
        click.echo(f"  \u2713 Config saved to {config_path}")
        click.echo("  Run `promptune doctor` to verify your setup.")
    except KeyboardInterrupt:
        click.echo("\nSetup cancelled.", err=True)
        raise SystemExit(130) from None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli.py::TestConfigInitInteractive -v`
Expected: 4 PASSED

- [ ] **Step 5: Run full gate — verify NO regressions**

Run: `ruff check . && mypy promptune/ && pytest -v`
Expected: All pass. Critical checks:
- `test_config_init_creates_file` in `tests/test_config.py` — uses `--config-dir` and CliRunner without `input=`, so CliRunner's stdin is non-TTY → takes non-interactive path → creates default config → still passes.
- All existing `config show`, `config path`, `--reset` tests unchanged.

---

### Task 10: Final verification and edge cases

**Files:**
- Modify: `tests/test_setup.py` (add edge case tests)
- Modify: `tests/test_cli.py` (add Ctrl+C test)

- [ ] **Step 1: Add edge case tests**

Add to `tests/test_setup.py`:

```python
class TestWriteConfigEdgeCases:
    """Edge cases for config writing."""

    def test_overwrites_existing_file(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.toml"
        config_path.write_text("old content")
        write_config(config_path, {"provider": {"default": "openai"}})
        content = config_path.read_text()
        assert "old content" not in content
        assert "openai" in content

    def test_boolean_values_formatted_correctly(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.toml"
        write_config(config_path, {
            "local_llm": {"enabled": True},
            "history": {"enabled": False},
        })
        content = config_path.read_text()
        assert "true" in content
        assert "false" in content
```

Add to `tests/test_cli.py`:

```python
def test_config_init_ctrl_c_no_partial_write(
    mocker, tmp_path: Path
) -> None:
    """Ctrl+C during wizard does not write partial config."""
    config_file = tmp_path / "config.toml"
    mocker.patch(
        "promptune.cli._get_config_path",
        return_value=config_file,
    )
    mocker.patch(
        "promptune.setup.run_interactive_setup",
        side_effect=KeyboardInterrupt,
    )

    runner = CliRunner()
    result = runner.invoke(main, ["config", "init"])
    assert result.exit_code == 130
    assert not config_file.exists()
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `pytest tests/test_setup.py::TestWriteConfigEdgeCases tests/test_cli.py::test_config_init_ctrl_c_no_partial_write -v`
Expected: 3 PASSED

- [ ] **Step 3: Run full gate — final verification**

Run: `ruff check . && mypy promptune/ && pytest --cov=promptune --cov-report=term-missing -v`
Expected: All pass, coverage ≥90%, no regressions in any existing test file.
