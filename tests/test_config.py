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
model_openrouter = "anthropic/claude-haiku-4.5"

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
    # Auto-downgraded: no API keys → capped at 1 (local_llm enabled)
    assert config["enhancement"]["max_tier"] == 1
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
    assert config["provider"]["model_openrouter"] == "anthropic/claude-haiku-4.5"


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

    Uses CLI override to force tier 2 (auto-downgrade would cap it).
    """
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text("""\
[provider]
default = "claude"
""")
    with pytest.raises(ConfigError, match="api_key"):
        load_config(
            config_path=config_file,
            validate_keys=True,
            cli_overrides={"tier": "2"},
        )


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


class TestZeroConfigTierDowngrade:
    """Auto-downgrade max_tier when no API keys or local LLM configured."""

    def test_no_config_file_downgrades_to_tier1(
        self, tmp_path: Path
    ) -> None:
        """No config file → local_llm enabled by default → tier 1."""
        config_path = tmp_path / "nonexistent.toml"
        cfg = load_config(config_path=config_path)
        # Default has local_llm.enabled=True, so caps at 1
        assert cfg["enhancement"]["max_tier"] == 1

    def test_empty_api_keys_downgrades_to_tier1(
        self, tmp_path: Path
    ) -> None:
        """Config file with empty API keys + local LLM default → tier 1."""
        config_path = tmp_path / "config.toml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            '[provider]\ndefault = "claude"\n\n'
            '[api_keys]\nclaude = ""\n'
        )
        cfg = load_config(config_path=config_path)
        assert cfg["enhancement"]["max_tier"] == 1

    def test_api_key_present_keeps_tier2(
        self, tmp_path: Path
    ) -> None:
        """Config file with valid API key → tier preserved."""
        config_path = tmp_path / "config.toml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            '[provider]\ndefault = "claude"\n\n'
            '[api_keys]\nclaude = "sk-ant-real-key"\n'
        )
        cfg = load_config(config_path=config_path)
        assert cfg["enhancement"]["max_tier"] == 2

    def test_local_llm_enabled_keeps_tier1(
        self, tmp_path: Path
    ) -> None:
        """Local LLM enabled with no cloud keys → tier stays >= 1."""
        config_path = tmp_path / "config.toml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            '[provider]\ndefault = "claude"\n\n'
            '[api_keys]\nclaude = ""\n\n'
            '[enhancement]\nmax_tier = 1\n\n'
            '[local_llm]\nenabled = true\n'
        )
        cfg = load_config(config_path=config_path)
        assert cfg["enhancement"]["max_tier"] == 1

    def test_local_llm_disabled_no_keys_downgrades(
        self, tmp_path: Path
    ) -> None:
        """Local LLM disabled + no cloud keys → tier 0."""
        config_path = tmp_path / "config.toml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            '[provider]\ndefault = "claude"\n\n'
            '[api_keys]\nclaude = ""\n\n'
            '[local_llm]\nenabled = false\n'
        )
        cfg = load_config(config_path=config_path)
        assert cfg["enhancement"]["max_tier"] == 0

    def test_cli_tier_override_not_downgraded(
        self, tmp_path: Path
    ) -> None:
        """Explicit CLI --tier override is respected even without keys."""
        config_path = tmp_path / "nonexistent.toml"
        cfg = load_config(
            config_path=config_path,
            cli_overrides={"tier": "2"},
        )
        # CLI override happens after downgrade, so tier is 2
        assert cfg["enhancement"]["max_tier"] == 2


class TestAutoEnhanceDefaults:
    """auto_enhance section in DEFAULT_CONFIG."""

    def test_auto_enhance_section_exists(self) -> None:
        from promptune.config import DEFAULT_CONFIG
        assert "auto_enhance" in DEFAULT_CONFIG

    def test_auto_enhance_defaults(self) -> None:
        from promptune.config import DEFAULT_CONFIG
        ae = DEFAULT_CONFIG["auto_enhance"]
        assert ae["enabled"] is True
        assert ae["threshold"] == 40
        assert ae["min_words"] == 5

    def test_load_config_includes_auto_enhance(
        self, tmp_path: Path
    ) -> None:
        config_path = tmp_path / "config.toml"
        cfg = load_config(config_path=config_path)
        assert "auto_enhance" in cfg
        assert cfg["auto_enhance"]["threshold"] == 40


def test_validate_mode_name(config_file: Path) -> None:
    """Invalid mode name raises ConfigError."""
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text("""\
[enhancement]
default_mode = "ultra_mega"
""")
    with pytest.raises(ConfigError, match="[Mm]ode"):
        load_config(config_path=config_file, validate_keys=True)


def test_validate_max_tier(config_file: Path) -> None:
    """max_tier outside 0-2 raises ConfigError."""
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text("""\
[enhancement]
max_tier = 5
""")
    with pytest.raises(ConfigError, match="[Tt]ier"):
        load_config(
            config_path=config_file,
            validate_keys=True,
            cli_overrides={"tier": "5"},
        )


def test_wrong_typed_max_tier_raises_config_error(config_file: Path) -> None:
    """A string max_tier raises ConfigError, not a raw TypeError."""
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text('[enhancement]\nmax_tier = "two"\n')
    with pytest.raises(ConfigError, match="[Tt]ier"):
        load_config(config_path=config_file)


def test_wrong_typed_enhancement_section_raises_config_error(
    config_file: Path,
) -> None:
    """A scalar where a [section] table is expected raises ConfigError."""
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text('enhancement = "oops"\n')
    with pytest.raises(ConfigError, match="enhancement"):
        load_config(config_path=config_file)


def test_wrong_typed_api_keys_section_raises_config_error(
    config_file: Path,
) -> None:
    """A scalar api_keys raises ConfigError instead of AttributeError."""
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text('api_keys = "nope"\n')
    with pytest.raises(ConfigError, match="api_keys"):
        load_config(config_path=config_file)


def test_file_max_tier_out_of_range_raises_config_error(
    config_file: Path,
) -> None:
    """An out-of-range max_tier in the file is reported, not silently clamped."""
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text("[enhancement]\nmax_tier = 9\n")
    with pytest.raises(ConfigError, match="[Tt]ier"):
        load_config(config_path=config_file)


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


def test_config_defaults_include_dedup_keys() -> None:
    """Default config includes dedup and preference keys."""
    from promptune.config import DEFAULT_CONFIG

    enhancement = DEFAULT_CONFIG["enhancement"]
    assert enhancement["dedup_enabled"] is True
    assert enhancement["dedup_threshold"] == 0.85
    assert enhancement["dedup_window"] == 50
    assert enhancement["preference_learning"] is True
    assert enhancement["preference_min_samples"] == 5


def test_daemon_config_defaults() -> None:
    """Daemon config section has correct defaults."""
    from promptune.config import DEFAULT_CONFIG

    daemon = DEFAULT_CONFIG["daemon"]
    assert daemon["hotkey"] == "ctrl+shift+e"
    assert daemon["clipboard_settle_ms"] == 100
    assert daemon["notify"] is True
    assert daemon["notify_sound"] is True
    assert daemon["ollama_prewarm"] is True
    assert daemon["ollama_keepalive_minutes"] == 30
    assert daemon["log_level"] == "info"


def test_loaded_config_includes_daemon_defaults(tmp_path: Path) -> None:
    """Loading a config file without [daemon] section fills in defaults."""
    config_file = tmp_path / "config.toml"
    config_file.write_text('[provider]\ndefault = "claude"\n')
    from promptune.config import load_config

    cfg = load_config(config_file, validate_keys=False)
    assert "daemon" in cfg
    assert cfg["daemon"]["hotkey"] == "ctrl+shift+e"


def test_generate_default_config_round_trips() -> None:
    """Generated TOML parses back to the full DEFAULT_CONFIG."""
    try:
        import tomllib
    except ModuleNotFoundError:  # Python < 3.11
        import tomli as tomllib

    from promptune.config import DEFAULT_CONFIG, generate_default_config

    parsed = tomllib.loads(generate_default_config())
    assert parsed == DEFAULT_CONFIG


def test_format_toml_value_escapes_special_chars() -> None:
    """String values with quotes/backslashes/newlines are escaped and parse."""
    import tomllib

    from promptune.config import _format_toml_value

    value = 'a"b\\c\nd'
    rendered = f"k = {_format_toml_value(value)}"
    assert tomllib.loads(rendered)["k"] == value


def test_escape_toml_string_handles_controls() -> None:
    from promptune.config import escape_toml_string

    assert escape_toml_string('he said "hi"\\') == 'he said \\"hi\\"\\\\'
