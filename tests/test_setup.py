"""Interactive config setup tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from promptune.config import load_config
from promptune.engine import get_registry
from promptune.providers import ProviderRegistry
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


@pytest.fixture()
def mock_registry() -> ProviderRegistry:
    """Registry with real providers."""
    return get_registry()


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


class TestMaskKey:
    """API key masking for display."""

    def test_masks_normal_key(self) -> None:
        assert mask_key("sk-ant-api03-abc123xyz") == "sk...3xyz"

    def test_empty_key_returns_empty(self) -> None:
        assert mask_key("") == ""

    def test_short_key_masks_all(self) -> None:
        assert mask_key("abcd") == "****"

    def test_very_short_key(self) -> None:
        assert mask_key("abc") == "***"

    def test_medium_key(self) -> None:
        assert mask_key("sk-ant-xy") == "sk...t-xy"


class TestWriteConfig:
    """TOML config file writing."""

    def test_creates_file(self, tmp_path: Path) -> None:
        config_path = tmp_path / "promptune" / "config.toml"
        config: dict = {
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
        config: dict = {
            "provider": {
                "default": "openai",
                "format_style": "markdown",
                "model_claude": "claude-haiku-4-5-20251001",
                "model_openai": "gpt-4o-mini",
                "model_openrouter": "anthropic/claude-haiku-4.5",
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
        config: dict = {
            "provider": {"default": "claude"},
            "api_keys": {"claude": "sk-ant-test"},
            "enhancement": {"max_tier": 2, "default_mode": "balanced"},
        }
        write_config(config_path, config)
        content = config_path.read_text()
        assert "[provider]" in content
        assert "[api_keys]" in content
        assert "[enhancement]" in content


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
        prompt_text = mock_prompt.call_args[0][0]
        assert "claude" in prompt_text or "openai" in prompt_text


class TestPromptApiKey:
    """API key prompt with masking and validation."""

    def test_accepts_valid_key(self) -> None:
        with (
            patch("click.prompt", return_value="sk-ant-test123"),
            patch("click.echo"),
        ):
            result = _prompt_api_key("claude", "")
        assert result == "sk-ant-test123"

    def test_keeps_existing_key_on_enter(self) -> None:
        with (
            patch("click.prompt", return_value="sk-ant-existing"),
            patch("click.echo"),
        ):
            result = _prompt_api_key("claude", "sk-ant-existing")
        assert result == "sk-ant-existing"

    def test_shows_masked_existing_in_prompt(self) -> None:
        with (
            patch("click.prompt", return_value="sk-ant-existing") as mock_prompt,
            patch("click.echo"),
        ):
            _prompt_api_key("claude", "sk-ant-existing")
        prompt_text = mock_prompt.call_args[0][0]
        assert "..." in prompt_text

    def test_warns_on_bad_prefix(self) -> None:
        with (
            patch("click.prompt", return_value="wrong-prefix-key"),
            patch("click.echo") as mock_echo,
        ):
            _prompt_api_key("claude", "")
        echo_calls = [str(c) for c in mock_echo.call_args_list]
        warning_printed = any("warning" in c.lower() for c in echo_calls)
        assert warning_printed

    def test_no_default_when_existing_empty(self) -> None:
        with (
            patch("click.prompt", return_value="sk-ant-new") as mock_prompt,
            patch("click.echo"),
        ):
            _prompt_api_key("claude", "")
        call_kwargs = mock_prompt.call_args[1] if mock_prompt.call_args[1] else {}
        default_val = call_kwargs.get("default", "")
        assert default_val == "" or default_val is None

    def test_accepts_blank_key_for_free_mode(self) -> None:
        with (
            patch("click.prompt", return_value=""),
            patch("click.echo"),
        ):
            result = _prompt_api_key("claude", "")
        assert result == ""

    def test_shows_paid_note_when_no_existing_key(self) -> None:
        with (
            patch("click.prompt", return_value="sk-ant-test123"),
            patch("click.echo") as mock_echo,
        ):
            _prompt_api_key("claude", "")
        text = " ".join(str(c) for c in mock_echo.call_args_list).lower()
        assert "paid" in text
        assert "blank" in text

    def test_blank_key_confirms_free_mode(self) -> None:
        with (
            patch("click.prompt", return_value=""),
            patch("click.echo") as mock_echo,
        ):
            _prompt_api_key("claude", "")
        text = " ".join(str(c) for c in mock_echo.call_args_list).lower()
        assert "free" in text
        assert "tier 0" in text
        assert "tier 1" in text


class TestPromptModel:
    """Model name prompt after API key."""

    def test_returns_user_input(self) -> None:
        with patch("click.prompt", return_value="gpt-4o"):
            result = _prompt_model("openai", "gpt-4o-mini")
        assert result == "gpt-4o"

    def test_prefills_default_model(self) -> None:
        default = "anthropic/claude-haiku-4.5"
        with patch("click.prompt", return_value=default) as mock_prompt:
            _prompt_model("openrouter", default)
        call_kwargs = mock_prompt.call_args[1] if mock_prompt.call_args[1] else {}
        assert call_kwargs.get("default") == "anthropic/claude-haiku-4.5"

    def test_keeps_default_on_enter(self) -> None:
        with patch("click.prompt", return_value="claude-haiku-4-5-20251001"):
            result = _prompt_model("claude", "claude-haiku-4-5-20251001")
        assert result == "claude-haiku-4-5-20251001"

    def test_prompt_text_contains_provider(self) -> None:
        with patch("click.prompt", return_value="some-model") as mock_prompt:
            _prompt_model("openrouter", "anthropic/claude-haiku-4.5")
        prompt_text = mock_prompt.call_args[0][0]
        assert "openrouter" in prompt_text.lower() or "model" in prompt_text.lower()


class TestPromptOptionalSettings:
    """Optional advanced settings behind y/N gate."""

    def test_skips_when_declined(self) -> None:
        defaults: dict = {
            "default_mode": "balanced",
            "max_tier": 2,
            "format_style": "auto",
        }
        with patch("click.confirm", return_value=False):
            result, accepted = _prompt_optional_settings(defaults)
        assert result == defaults
        assert accepted is False

    def test_collects_when_accepted(self) -> None:
        defaults: dict = {
            "default_mode": "balanced",
            "max_tier": 2,
            "format_style": "auto",
        }
        with (
            patch("click.confirm", return_value=True),
            patch("click.prompt", side_effect=["detailed", 1, "xml"]),
            patch("click.echo"),
        ):
            result, accepted = _prompt_optional_settings(defaults)
        assert result["default_mode"] == "detailed"
        assert result["max_tier"] == 1
        assert result["format_style"] == "xml"
        assert accepted is True

    def test_keeps_defaults_on_enter(self) -> None:
        defaults: dict = {
            "default_mode": "balanced",
            "max_tier": 2,
            "format_style": "auto",
        }
        with (
            patch("click.confirm", return_value=True),
            patch("click.prompt", side_effect=["balanced", 2, "auto"]),
            patch("click.echo"),
        ):
            result, accepted = _prompt_optional_settings(defaults)
        assert result == defaults
        assert accepted is True


class TestPromptLocalLlmSettings:
    """Local LLM settings prompt when max_tier >= 1."""

    def test_skips_when_disabled(self) -> None:
        defaults: dict = {
            "enabled": True,
            "host": "http://localhost:11434",
            "model": "qwen2.5:3b",
        }
        with patch("click.confirm", return_value=False):
            result = _prompt_local_llm_settings(defaults)
        assert result["enabled"] is False

    def test_collects_when_enabled(self) -> None:
        defaults: dict = {
            "enabled": True,
            "host": "http://localhost:11434",
            "model": "qwen2.5:3b",
        }
        with (
            patch("click.confirm", return_value=True),
            patch(
                "click.prompt",
                side_effect=[
                    "http://localhost:11434",
                    "llama3:8b",
                ],
            ),
        ):
            result = _prompt_local_llm_settings(defaults)
        assert result["enabled"] is True
        assert result["host"] == "http://localhost:11434"
        assert result["model"] == "llama3:8b"

    def test_prefills_existing_defaults(self) -> None:
        defaults: dict = {
            "enabled": True,
            "host": "http://myhost:8080",
            "model": "custom-model",
        }
        with (
            patch("click.confirm", return_value=True),
            patch(
                "click.prompt",
                side_effect=[
                    "http://myhost:8080",
                    "custom-model",
                ],
            ) as mock_prompt,
        ):
            _prompt_local_llm_settings(defaults)
        # Check host prompt has correct default
        host_call = mock_prompt.call_args_list[0]
        assert host_call[1].get("default") == "http://myhost:8080"
        # Check model prompt has correct default
        model_call = mock_prompt.call_args_list[1]
        assert model_call[1].get("default") == "custom-model"

    def test_custom_host_and_model(self) -> None:
        defaults: dict = {
            "enabled": False,
            "host": "http://localhost:11434",
            "model": "qwen2.5:3b",
        }
        with (
            patch("click.confirm", return_value=True),
            patch(
                "click.prompt",
                side_effect=[
                    "http://gpu-server:11434",
                    "mistral:7b",
                ],
            ),
        ):
            result = _prompt_local_llm_settings(defaults)
        assert result["host"] == "http://gpu-server:11434"
        assert result["model"] == "mistral:7b"


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

    def test_installs_mcp_when_available(self) -> None:
        mock_installer = MagicMock()
        mock_installer.name = "Claude Code"
        mock_installer.is_mcp_installed.return_value = False
        with (
            patch(
                "promptune.setup.detect_tools",
                return_value=[mock_installer],
            ),
            patch("click.confirm", return_value=True),
            patch("click.echo"),
        ):
            _prompt_auto_enhance_settings()
        mock_installer.install.assert_called_once()
        mock_installer.install_mcp.assert_called_once()

    def test_skips_mcp_when_not_available(self) -> None:
        mock_installer = MagicMock(spec=["name", "install", "detect"])
        mock_installer.name = "Other Tool"
        with (
            patch(
                "promptune.setup.detect_tools",
                return_value=[mock_installer],
            ),
            patch("click.confirm", return_value=True),
            patch("click.echo"),
        ):
            _prompt_auto_enhance_settings()
        mock_installer.install.assert_called_once()
        assert not hasattr(mock_installer, "install_mcp")

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


class TestRunInteractiveSetup:
    """Full wizard orchestration."""

    def test_first_time_setup(
        self, tmp_path: Path, mock_registry: ProviderRegistry
    ) -> None:
        config_path = tmp_path / "config.toml"
        with (
            patch(
                "click.prompt",
                side_effect=[
                    "claude",
                    "sk-ant-test123",
                    "claude-haiku-4-5-20251001",
                ],
            ),
            patch("click.confirm", return_value=False),
            patch("click.echo"),
            patch(
                "promptune.setup.detect_tools",
                return_value=[],
            ),
        ):
            result = run_interactive_setup(
                config_path, mock_registry
            )
        assert result["provider"]["default"] == "claude"
        assert (
            result["api_keys"]["claude"] == "sk-ant-test123"
        )
        assert (
            result["provider"]["model_claude"]
            == "claude-haiku-4-5-20251001"
        )

    def test_prefills_existing_config(
        self, tmp_path: Path, mock_registry: ProviderRegistry
    ) -> None:
        config_path = tmp_path / "config.toml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            '[provider]\ndefault = "openai"\n\n'
            '[api_keys]\nopenai = "sk-existing"\n'
        )
        with (
            patch(
                "click.prompt",
                side_effect=[
                    "openai",
                    "sk-existing",
                    "gpt-4o-mini",
                ],
            ),
            patch("click.confirm", return_value=False),
            patch("click.echo"),
            patch(
                "promptune.setup.detect_tools",
                return_value=[],
            ),
        ):
            result = run_interactive_setup(
                config_path, mock_registry
            )
        assert result["provider"]["default"] == "openai"
        assert (
            result["api_keys"]["openai"] == "sk-existing"
        )

    def test_with_advanced_settings_tier1_local_llm(
        self, tmp_path: Path, mock_registry: ProviderRegistry
    ) -> None:
        config_path = tmp_path / "config.toml"
        with (
            patch(
                "click.prompt",
                side_effect=[
                    "openai",
                    "sk-test123",
                    "gpt-4o",
                    "detailed",
                    1,
                    "xml",
                    "http://localhost:11434",
                    "llama3:8b",
                ],
            ),
            patch(
                "click.confirm",
                side_effect=[True, True],
            ),
            patch("click.echo"),
            patch(
                "promptune.setup.detect_tools",
                return_value=[],
            ),
        ):
            result = run_interactive_setup(
                config_path, mock_registry
            )
        assert result["provider"]["default"] == "openai"
        assert (
            result["provider"]["model_openai"] == "gpt-4o"
        )
        assert result["enhancement"]["max_tier"] == 1
        assert result["local_llm"]["enabled"] is True
        assert result["local_llm"]["model"] == "llama3:8b"

    def test_with_advanced_settings_tier0_skips_local(
        self, tmp_path: Path, mock_registry: ProviderRegistry
    ) -> None:
        config_path = tmp_path / "config.toml"
        with (
            patch(
                "click.prompt",
                side_effect=[
                    "claude",
                    "sk-ant-test123",
                    "claude-haiku-4-5-20251001",
                    "minimal",
                    0,
                    "auto",
                ],
            ),
            patch("click.confirm", return_value=True),
            patch("click.echo"),
            patch(
                "promptune.setup.detect_tools",
                return_value=[],
            ),
        ):
            result = run_interactive_setup(
                config_path, mock_registry
            )
        assert result["enhancement"]["max_tier"] == 0
        assert result["local_llm"]["enabled"] is True

    def test_advanced_tier1_local_llm_declined(
        self, tmp_path: Path, mock_registry: ProviderRegistry
    ) -> None:
        config_path = tmp_path / "config.toml"
        with (
            patch(
                "click.prompt",
                side_effect=[
                    "openai",
                    "sk-test123",
                    "gpt-4o-mini",
                    "balanced",
                    1,
                    "auto",
                ],
            ),
            patch(
                "click.confirm",
                side_effect=[True, False],
            ),
            patch("click.echo"),
            patch(
                "promptune.setup.detect_tools",
                return_value=[],
            ),
        ):
            result = run_interactive_setup(
                config_path, mock_registry
            )
        assert result["enhancement"]["max_tier"] == 1
        assert result["local_llm"]["enabled"] is False

    def test_model_saved_for_openrouter(
        self, tmp_path: Path, mock_registry: ProviderRegistry
    ) -> None:
        config_path = tmp_path / "config.toml"
        with (
            patch(
                "click.prompt",
                side_effect=[
                    "openrouter",
                    "sk-or-test123",
                    "google/gemini-pro",
                ],
            ),
            patch("click.confirm", return_value=False),
            patch("click.echo"),
            patch(
                "promptune.setup.detect_tools",
                return_value=[],
            ),
        ):
            result = run_interactive_setup(
                config_path, mock_registry
            )
        assert result["provider"]["default"] == "openrouter"
        assert (
            result["provider"]["model_openrouter"]
            == "google/gemini-pro"
        )

    def test_explains_tiers_and_cost(
        self, tmp_path: Path, mock_registry: ProviderRegistry
    ) -> None:
        config_path = tmp_path / "config.toml"
        with (
            patch(
                "click.prompt",
                side_effect=[
                    "claude",
                    "sk-ant-test123",
                    "claude-haiku-4-5-20251001",
                ],
            ),
            patch("click.confirm", return_value=False),
            patch("click.echo") as mock_echo,
            patch(
                "promptune.setup.detect_tools",
                return_value=[],
            ),
        ):
            run_interactive_setup(config_path, mock_registry)
        text = " ".join(str(c) for c in mock_echo.call_args_list).lower()
        assert "tier 0" in text
        assert "tier 1" in text
        assert "tier 2" in text
        assert "free" in text
        assert "api key" in text

    def test_completes_with_blank_key(
        self, tmp_path: Path, mock_registry: ProviderRegistry
    ) -> None:
        config_path = tmp_path / "config.toml"
        with (
            patch(
                "click.prompt",
                side_effect=[
                    "claude",
                    "",
                    "claude-haiku-4-5-20251001",
                ],
            ),
            patch("click.confirm", return_value=False),
            patch("click.echo"),
            patch(
                "promptune.setup.detect_tools",
                return_value=[],
            ),
        ):
            result = run_interactive_setup(config_path, mock_registry)
        assert result["provider"]["default"] == "claude"
        assert result["api_keys"]["claude"] == ""

    def test_key_enables_tier2_without_advanced(
        self, tmp_path: Path, mock_registry: ProviderRegistry
    ) -> None:
        config_path = tmp_path / "config.toml"
        with (
            patch(
                "click.prompt",
                side_effect=[
                    "claude",
                    "sk-ant-test123",
                    "claude-haiku-4-5-20251001",
                ],
            ),
            patch("click.confirm", return_value=False),
            patch("click.echo"),
            patch("promptune.setup.detect_tools", return_value=[]),
        ):
            result = run_interactive_setup(config_path, mock_registry)
        # Providing a key enables Tier 2 even without opening advanced settings.
        assert result["enhancement"]["max_tier"] == 2

    def test_blank_key_clamps_tier_even_with_other_provider_key(
        self, tmp_path: Path, mock_registry: ProviderRegistry
    ) -> None:
        config_path = tmp_path / "config.toml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            '[provider]\ndefault = "openai"\n\n'
            '[api_keys]\nopenai = "sk-existing"\n\n'
            "[enhancement]\nmax_tier = 2\n"
        )
        with (
            patch(
                "click.prompt",
                side_effect=[
                    "claude",
                    "",
                    "claude-haiku-4-5-20251001",
                ],
            ),
            patch("click.confirm", return_value=False),
            patch("click.echo"),
            patch("promptune.setup.detect_tools", return_value=[]),
        ):
            result = run_interactive_setup(config_path, mock_registry)
        # Blank key = free mode: clamp to Tier 1 so the saved config matches
        # what the wizard advertised, even though another provider has a key.
        assert result["api_keys"]["claude"] == ""
        assert result["enhancement"]["max_tier"] == 1

    def test_blank_key_clamps_advanced_tier_with_other_provider_key(
        self, tmp_path: Path, mock_registry: ProviderRegistry
    ) -> None:
        config_path = tmp_path / "config.toml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            '[provider]\ndefault = "openai"\n\n'
            '[api_keys]\nopenai = "sk-existing"\n\n'
            "[enhancement]\nmax_tier = 2\n"
        )
        with (
            patch(
                "click.prompt",
                side_effect=[
                    "claude",
                    "",
                    "claude-haiku-4-5-20251001",
                    "balanced",
                    2,
                    "auto",
                ],
            ),
            patch("click.confirm", side_effect=[True, False]),
            patch("click.echo"),
            patch("promptune.setup.detect_tools", return_value=[]),
        ):
            result = run_interactive_setup(config_path, mock_registry)
        assert result["api_keys"]["claude"] == ""
        assert result["enhancement"]["max_tier"] == 1

    def test_existing_key_preserves_tier_when_advanced_skipped(
        self, tmp_path: Path, mock_registry: ProviderRegistry
    ) -> None:
        config_path = tmp_path / "config.toml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            '[provider]\ndefault = "claude"\n\n'
            '[api_keys]\nclaude = "sk-ant-existing"\n\n'
            "[enhancement]\nmax_tier = 0\n"
        )
        with (
            patch(
                "click.prompt",
                side_effect=[
                    "claude",
                    "sk-ant-existing",
                    "claude-haiku-4-5-20251001",
                ],
            ),
            patch("click.confirm", return_value=False),
            patch("click.echo"),
            patch("promptune.setup.detect_tools", return_value=[]),
        ):
            result = run_interactive_setup(config_path, mock_registry)
        assert result["enhancement"]["max_tier"] == 0


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
        write_config(
            config_path,
            {
                "local_llm": {"enabled": True},
                "history": {"enabled": False},
            },
        )
        content = config_path.read_text()
        assert "true" in content
        assert "false" in content
