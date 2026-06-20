"""Interactive config setup wizard."""

from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any

import click

from promptune.config import (
    DEFAULT_CONFIG,
    escape_toml_string,
    load_config,
)
from promptune.hooks import detect_tools
from promptune.providers import ProviderRegistry

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


def mask_key(key: str) -> str:
    """Mask API key for display, showing first 2 and last 4 chars.

    Returns empty string for empty input.
    Short keys (< 8 chars): '****' + last 4 (or all stars if <= 4).
    Normal keys: first 2 chars + '...' + last 4 chars.
    """
    if not key:
        return ""
    if len(key) < 8:
        if len(key) <= 4:
            return "*" * len(key)
        return "****" + key[-4:]
    return key[:2] + "..." + key[-4:]


def _format_toml_value(value: object) -> str:
    """Format a Python value as a TOML value string."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return f'"{escape_toml_string(value)}"'
    return str(value)


def write_config(
    config_path: Path, config: dict[str, Any]
) -> None:
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
            lines.append(
                f"{key} = {_format_toml_value(val)}"
            )
        lines.append("")

    # Config may contain plaintext API keys — write atomically and restrict
    # to owner-only (0o600) from creation so it is never world/group readable
    # (no window between write and chmod).
    tmp = config_path.with_suffix(config_path.suffix + ".tmp")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write("\n".join(lines) + "\n")
    os.chmod(tmp, 0o600)
    os.replace(tmp, config_path)


def _print_tier_overview() -> None:
    """Explain the three enhancement tiers and their cost."""
    click.echo("  How Promptune enhances your prompts:")
    click.echo(
        "    Tier 0  Rule-based rewrite       FREE  · offline, no key"
    )
    click.echo(
        "    Tier 1  Local LLM (Ollama, …)    FREE  · private, no key"
    )
    click.echo(
        "    Tier 2  Cloud LLM (Claude/GPT)   PAID  · needs an API key"
    )
    click.echo()
    click.echo(
        "  Tiers 0 & 1 work with no API key. Tier 2 is optional —"
    )
    click.echo(
        "  prompts only escalate to it when the cheaper tiers fall short."
    )
    click.echo()


def _clamp_choice(value: Any, choices: list[str], fallback: str) -> str:
    """Return *value* if it's a valid (case-insensitive) choice, else *fallback*.

    The wizard pre-fills click.Choice prompts with values read from the user's
    config. click re-validates the default even on a blank Enter, so a stale or
    hand-edited invalid value would otherwise re-prompt forever — exactly the
    "fix my broken config" case the wizard exists to handle.
    """
    lowered = {c.lower() for c in choices}
    if isinstance(value, str) and value.lower() in lowered:
        return value
    return fallback


def _prompt_provider(
    registry: ProviderRegistry, default: str
) -> str:
    """Prompt user to select a provider from the registry."""
    providers = sorted(registry.list())
    choices = "/".join(providers)
    default = _clamp_choice(
        default, providers, DEFAULT_CONFIG["provider"]["default"]
    )

    provider = click.prompt(
        f"  Provider [{choices}]",
        type=click.Choice(providers, case_sensitive=False),
        default=default,
        show_choices=False,
        show_default=False,
    )
    return str(provider)


def _prompt_api_key(
    provider: str, existing: str
) -> str:
    """Prompt for API key with masking and format validation."""
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
        click.echo(
            "  Tier 2 (cloud) uses a PAID API key. Leave blank to "
            "skip it and"
        )
        click.echo(
            "  use the free tiers (rules + local LLM) only."
        )
        prompt_text = f"  {provider.title()} API key (blank = free mode)"
        key = click.prompt(
            prompt_text,
            hide_input=True,
            default="",
            show_default=False,
        )
        if not key:
            click.echo(
                "  ✓ No API key set — free mode: Tier 0 "
                "(rules) + Tier 1 (local LLM)."
            )
            return ""

    warning = validate_key_format(provider, key)
    if warning and "required" not in warning.lower():
        click.echo(f"  {warning}")
    elif warning is None:
        click.echo("  \u2713 Key format looks valid.")

    return str(key)


def _prompt_model(provider: str, default: str) -> str:
    """Prompt user for model name with pre-filled default."""
    model = click.prompt(
        f"  {provider.title()} model",
        default=default,
        show_default=True,
    )
    return str(model)


def _prompt_local_llm_settings(
    defaults: dict[str, Any],
) -> dict[str, Any]:
    """Prompt for local LLM settings (host, model)."""
    enabled = click.confirm(
        "  Enable local LLM (e.g. Ollama)?",
        default=defaults.get("enabled", True),
    )
    if not enabled:
        return {"enabled": False}

    host = click.prompt(
        "  Local LLM host",
        default=defaults.get("host", "http://localhost:11434"),
        show_default=True,
    )
    model = click.prompt(
        "  Local LLM model",
        default=defaults.get("model", "qwen2.5:3b"),
        show_default=True,
    )
    return {
        "enabled": True,
        "host": str(host),
        "model": str(model),
    }


def _prompt_optional_settings(
    defaults: dict[str, Any],
) -> tuple[dict[str, Any], bool]:
    """Prompt for optional advanced settings behind a y/N gate.

    Returns (settings_dict, advanced_accepted).
    """
    if not click.confirm(
        "  Configure advanced settings?", default=False
    ):
        return dict(defaults), False

    click.echo()

    mode = click.prompt(
        "  Enhancement style [minimal/balanced/detailed]",
        type=click.Choice(
            ["minimal", "balanced", "detailed"],
            case_sensitive=False,
        ),
        default=_clamp_choice(
            defaults["default_mode"],
            ["minimal", "balanced", "detailed"],
            DEFAULT_CONFIG["enhancement"]["default_mode"],
        ),
        show_choices=False,
        show_default=False,
    )

    tier = click.prompt(
        "  Max tier (0=rules, 1=+local, 2=+cloud) [0/1/2]",
        type=click.IntRange(0, 2),
        default=defaults["max_tier"],
        show_default=False,
    )

    return {
        "default_mode": str(mode),
        "max_tier": int(tier),
    }, True


def _default_max_tier_for_key_state(
    existing_tier: int, api_key: str, existing_key: str
) -> int:
    if not api_key:
        return min(existing_tier, 1)
    if existing_key:
        return existing_tier
    return 2


def _max_tier_for_key_state(requested_tier: int, api_key: str) -> int:
    if not api_key:
        return min(requested_tier, 1)
    return requested_tier


def _prompt_auto_enhance_settings() -> dict[str, Any] | None:
    """Detect AI tools and offer auto-enhance hook installation.

    Returns {"enabled": True} if accepted, None if skipped.
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
        has_mcp = (
            hasattr(installer, "install_mcp")
            and hasattr(installer, "is_mcp_installed")
        )
        if has_mcp and not installer.is_mcp_installed():  # type: ignore[attr-defined]
            installer.install_mcp()  # type: ignore[attr-defined]
            click.echo(
                f"  \u2713 MCP server registered for {installer.name}"
            )

    return {"enabled": True}


def run_interactive_setup(
    config_path: Path, registry: ProviderRegistry
) -> dict[str, Any]:
    """Run the interactive config setup wizard.

    Loads existing config for pre-filling if config_path exists.
    Returns a complete config dict ready to write.
    """
    click.echo()
    click.echo("  Promptune Setup")
    click.echo(
        "  \u2500\u2500\u2500\u2500\u2500\u2500\u2500"
        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
    )
    click.echo()

    # Explain tiers + cost before asking for anything
    _print_tier_overview()

    # Load existing config for pre-filling
    existing = load_config(config_path=config_path)

    # Mandatory: provider
    provider = _prompt_provider(
        registry,
        default=existing["provider"]["default"],
    )

    # Mandatory: API key for selected provider
    existing_key = existing["api_keys"].get(provider, "")
    api_key = _prompt_api_key(provider, existing_key)

    # Mandatory: model name for selected provider
    model_key = f"model_{provider}"
    existing_model = existing["provider"].get(model_key, "")
    model = _prompt_model(provider, existing_model)

    # Optional: advanced settings
    click.echo()
    max_tier_default = _default_max_tier_for_key_state(
        existing["enhancement"]["max_tier"],
        api_key,
        existing_key,
    )
    optional_defaults = {
        "default_mode": existing["enhancement"][
            "default_mode"
        ],
        "max_tier": max_tier_default,
    }
    optional, advanced_accepted = _prompt_optional_settings(
        optional_defaults,
    )

    # Local LLM settings — only in advanced mode when tier allows it
    local_llm_settings: dict[str, Any] | None = None
    if advanced_accepted and optional["max_tier"] >= 1:
        click.echo()
        local_llm_settings = _prompt_local_llm_settings(
            existing.get("local_llm", {}),
        )

    # Build complete config
    config = copy.deepcopy(existing)
    config["provider"]["default"] = provider
    config["api_keys"][provider] = api_key
    config["provider"][model_key] = model
    config["enhancement"]["default_mode"] = optional[
        "default_mode"
    ]
    config["enhancement"]["max_tier"] = _max_tier_for_key_state(
        optional["max_tier"], api_key
    )
    if local_llm_settings is not None:
        config["local_llm"].update(local_llm_settings)

    # Auto-enhance — detect AI tools and offer hook installation
    click.echo()
    auto_enhance_settings = _prompt_auto_enhance_settings()
    if auto_enhance_settings is not None:
        config["auto_enhance"].update(auto_enhance_settings)

    return config
