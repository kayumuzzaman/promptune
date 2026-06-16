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
        "model_openrouter": "anthropic/claude-haiku-4.5",
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
        "dedup_enabled": True,
        "dedup_threshold": 0.85,
        "dedup_window": 50,
        "preference_learning": True,
        "preference_min_samples": 5,
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
    "daemon": {
        "hotkey": "ctrl+shift+e",
        "clipboard_settle_ms": 100,
        "notify": True,
        "notify_sound": True,
        "ollama_prewarm": True,
        "ollama_keepalive_minutes": 30,
        "log_level": "info",
    },
    "auto_enhance": {
        "enabled": True,
        "threshold": 40,
        "min_words": 5,
        "bypass_prefix": "!",
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
        try:
            config["enhancement"]["max_tier"] = int(cli_overrides["tier"])
        except (TypeError, ValueError) as exc:
            raise ConfigError(
                f"Invalid --tier value {cli_overrides['tier']!r}: "
                "must be an integer."
            ) from exc
    if "format" in cli_overrides:
        config["provider"]["format_style"] = cli_overrides["format"]
    return config


def _auto_downgrade_tier(config: dict[str, Any]) -> dict[str, Any]:
    """Auto-downgrade max_tier when no API keys or local LLM are configured.

    Ensures ``promptune enhance`` works instantly with zero config
    by falling back to Tier 0 (deterministic rules, free, instant).
    """
    max_tier = config["enhancement"]["max_tier"]
    if max_tier == 0:
        return config

    # Check if any cloud API key is set
    has_cloud_key = any(
        bool(v) for v in config.get("api_keys", {}).values()
    )

    # Check if local LLM is enabled (for tier 1)
    local_enabled = config.get("local_llm", {}).get(
        "enabled", False
    )

    if has_cloud_key:
        return config

    # No cloud keys — cap at tier 1 if local LLM enabled, else tier 0
    if local_enabled:
        if max_tier > 1:
            config["enhancement"]["max_tier"] = 1
    else:
        config["enhancement"]["max_tier"] = 0

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
    config = _auto_downgrade_tier(config)

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


def _format_toml_value(value: Any) -> str:
    """Format a Python value as a TOML scalar."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return f'"{value}"'
    return str(value)


def generate_default_config() -> str:
    """Return the full default config (every documented key) as TOML."""
    lines: list[str] = ["# Promptune Configuration", ""]
    for section, values in DEFAULT_CONFIG.items():
        lines.append(f"[{section}]")
        for key, val in values.items():
            lines.append(f"{key} = {_format_toml_value(val)}")
        lines.append("")
    return "\n".join(lines) + "\n"
