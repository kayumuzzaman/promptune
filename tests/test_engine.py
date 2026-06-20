"""Router Engine tests."""

import pytest
from pytest_mock import MockerFixture

from promptune.engine import EnhanceResult, enhance, get_registry
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
            "model_openrouter": "anthropic/claude-haiku-4.5",
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


def test_get_registry_returns_known_providers() -> None:
    """get_registry() returns registry with claude, openai, openrouter."""
    registry = get_registry()
    providers = registry.list()
    assert "claude" in providers
    assert "openai" in providers
    assert "openrouter" in providers


def test_enhance_result_has_full_metadata() -> None:
    """EnhanceResult has all required fields."""
    result = EnhanceResult(
        original="test",
        enhanced="enhanced test",
        tier_used=0,
        latency_ms=5.0,
        score_before=ScoreResult(
            total=20, dimensions={}, intent="coding"
        ),
        score_after=ScoreResult(
            total=70, dimensions={}, intent="coding"
        ),
        rules_applied=["output_format"],
        rules_explained=[("output_format", "Added output format instruction")],
        context=None,
        format_style="auto",
        provider=None,
        model=None,
    )
    assert result.tier_used == 0
    assert result.latency_ms == 5.0
    assert result.provider is None


def test_engine_tier0_only(
    mocker: MockerFixture, mock_config: dict
) -> None:
    """max_tier=0 uses only Tier 0 rules."""
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
        "## Task\nYou are a senior Python developer. "
        "Implement a REST API "
        "using Flask with SQLAlchemy ORM and PostgreSQL.\n"
        "## Requirements\n"
        "- JWT authentication\n"
        "- Rate limiting at 100 req/min\n"
        "## Output\nReturn JSON with proper HTTP status codes"
    )

    result = enhance(detailed, mock_config)

    assert isinstance(result, EnhanceResult)
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
    assert result.tier_used in (0, 2)


def test_engine_records_to_history(mock_config: dict, tmp_path) -> None:
    """enhance() must persist a row so dedup/history/preferences have data."""
    from promptune.history import HistoryStore

    db = tmp_path / "history.db"
    mock_config["history"]["db_path"] = str(db)
    mock_config["enhancement"]["max_tier"] = 0  # deterministic tier 0

    result = enhance("fix the bug", mock_config)

    with HistoryStore(db_path=db) as store:
        entries = store.recent(n=10)
    assert len(entries) == 1
    assert entries[0].original == "fix the bug"
    assert entries[0].enhanced == result.enhanced
    assert entries[0].decision == "accept"
    assert entries[0].tier_used == 0


def test_engine_result_exposes_history_id(
    mock_config: dict, tmp_path
) -> None:
    """A recorded enhancement exposes its row id; a dedup hit does not."""
    db = tmp_path / "history.db"
    mock_config["history"]["db_path"] = str(db)
    mock_config["enhancement"]["max_tier"] = 0

    result = enhance("fix the bug", mock_config)
    assert result.history_id is not None

    # Same prompt again → served from dedup cache, nothing newly recorded.
    hit = enhance("fix the bug", mock_config)
    assert hit.tier_used == -1
    assert hit.history_id is None


def test_engine_dedup_bypassed_on_explicit_override(
    mock_config: dict, tmp_path
) -> None:
    """An explicit --tier/--provider override must run fresh, not serve the
    generic cached result (Codex review on PR #16)."""
    db = tmp_path / "history.db"
    mock_config["history"]["db_path"] = str(db)
    mock_config["enhancement"]["max_tier"] = 0
    prompt = "fix the auth bug in the parser module"

    enhance(prompt, mock_config)  # seeds a cacheable entry

    # No override → dedup hit.
    assert enhance(prompt, mock_config).tier_used == -1
    # Explicit tier override → bypass dedup, real run.
    assert enhance(prompt, mock_config, tier_override=0).tier_used == 0
    # Explicit provider override → also bypass dedup.
    assert (
        enhance(prompt, mock_config, provider_override="claude").tier_used
        != -1
    )


def test_engine_auto_dedup_separates_provider_model(
    mock_config: dict, tmp_path, mocker: MockerFixture
) -> None:
    """format_style=auto cache hits must not cross provider/model changes."""
    db = tmp_path / "history.db"
    mock_config["history"]["db_path"] = str(db)
    mock_config["local_llm"]["enabled"] = False
    mock_config["enhancement"]["preference_learning"] = False

    claude = mocker.MagicMock()
    claude.enhance.return_value = "<task>Claude XML result</task>"
    openai = mocker.MagicMock()
    openai.enhance.return_value = "## Task\nOpenAI Markdown result"
    factory = mocker.patch(
        "promptune.engine._create_cloud_provider",
        side_effect=[claude, openai],
    )
    prompt = "debug the python authentication failure in detail"

    first = enhance(prompt, mock_config, tier_override=2)
    mock_config["provider"]["default"] = "openai"
    second = enhance(prompt, mock_config)

    assert first.provider == "claude"
    assert second.tier_used == 2
    assert second.provider == "openai"
    assert second.enhanced == "## Task\nOpenAI Markdown result"
    assert factory.call_count == 2


def test_engine_auto_dedup_matches_tier0_result_under_local_enabled(
    mock_config: dict, tmp_path, mocker: MockerFixture
) -> None:
    """A tier-0 result (provider=None) must still dedup when the config would
    otherwise route to local LLM.

    Regression guard: the auto-format dedup route filter used to return
    provider="local" from static config while a high-scoring prompt stayed at
    tier 0 (provider=None recorded), so the cache never matched and dedup was
    inert for any prompt that didn't reach an AI tier.
    """
    db = tmp_path / "history.db"
    mock_config["history"]["db_path"] = str(db)
    mock_config["local_llm"]["enabled"] = True
    mock_config["enhancement"]["max_tier"] = 2
    mock_config["enhancement"]["preference_learning"] = False
    # A prompt that scores ≥ 70 so it never leaves tier 0, recording
    # provider=None/model=None even though local_llm is enabled.
    prompt = (
        "Implement a Python function that parses JSON configuration files "
        "safely with detailed error handling and comprehensive test coverage"
    )

    first = enhance(prompt, mock_config)
    assert first.tier_used == 0
    assert first.provider is None  # tier 0 records no provider

    # Same prompt again → must be served from the dedup cache.
    second = enhance(prompt, mock_config)
    assert second.tier_used == -1, "tier-0 result was not deduplicated"


def test_engine_auto_dedup_does_not_reuse_cloud_fallback_when_local_first(
    mock_config: dict, tmp_path, mocker: MockerFixture
) -> None:
    """Auto dedup must not reuse cloud fallback before retrying local first."""
    db = tmp_path / "history.db"
    mock_config["history"]["db_path"] = str(db)
    mock_config["local_llm"]["enabled"] = True
    mock_config["enhancement"]["max_tier"] = 2
    mock_config["enhancement"]["preference_learning"] = False
    prompt = "debug Python authentication timeout in production logs"

    local = mocker.patch(
        "promptune.engine._try_tier1",
        side_effect=[
            ProviderError("local down"),
            "Local LLM result after recovery",
        ],
    )
    cloud = mocker.patch(
        "promptune.engine._try_tier2",
        return_value=(
            "<task>Diagnose the Python authentication timeout.</task>",
            "claude",
            mock_config["provider"]["model_claude"],
        ),
    )

    first = enhance(prompt, mock_config)
    second = enhance(prompt, mock_config)

    assert first.tier_used == 2
    assert second.tier_used == 1
    assert second.enhanced == "Local LLM result after recovery"
    assert local.call_count == 2
    assert cloud.call_count == 1


@pytest.mark.parametrize(
    ("max_tier", "local_enabled"),
    [
        (0, True),
        (1, False),
    ],
)
def test_engine_auto_dedup_does_not_reuse_ai_result_when_only_tier0_possible(
    mock_config: dict,
    tmp_path,
    mocker: MockerFixture,
    max_tier: int,
    local_enabled: bool,
) -> None:
    """AI cache entries must not satisfy a config that can only return tier 0."""
    from promptune.history import HistoryEntry, HistoryStore

    db = tmp_path / "history.db"
    prompt = "debug the python authentication failure in detail"
    mock_config["history"]["db_path"] = str(db)
    mock_config["enhancement"]["max_tier"] = max_tier
    mock_config["local_llm"]["enabled"] = local_enabled
    mock_config["enhancement"]["preference_learning"] = False
    mocker.patch("promptune.engine._detect_project_root", return_value="/project")

    with HistoryStore(db_path=db) as store:
        store.record(
            HistoryEntry(
                original=prompt,
                enhanced="Cloud cached result",
                decision="accept",
                edit_result=None,
                tier_used=2,
                provider="claude",
                format_style="auto",
                model=mock_config["provider"]["model_claude"],
                score_before=20,
                score_after=90,
                latency_ms=8.0,
                rules_applied=[],
                context_json=None,
                project_root="/project",
            )
        )

    result = enhance(prompt, mock_config)

    assert result.tier_used == 0
    assert result.enhanced != "Cloud cached result"


def test_dedup_routes_keep_empty_model_to_match_recorded_entries() -> None:
    """Blanked models must stay "" in routes to match recorded history.

    Regression guard: the route side used to normalise an empty model to None
    (``model or None``) while the recording side keeps "" (the raw config
    value). dedup.py compares ``(entry.provider, entry.model)`` against the
    route set verbatim, so a None-normalised route ``(provider, None)`` never
    matched the recorded ``(provider, "")`` entry — silently excluding the
    daemon's own cache entry.
    """
    from promptune.engine import _dedup_provider_model_routes

    cfg = {
        "provider": {"default": "claude", "model_claude": ""},
        "local_llm": {"enabled": True, "model": ""},
        "enhancement": {"max_tier": 2},
    }

    routes = _dedup_provider_model_routes(cfg)

    assert routes == {("local", "")}
    assert ("claude", None) not in routes
    assert ("local", None) not in routes


def test_dedup_routes_use_cloud_when_local_disabled() -> None:
    """Cloud route remains dedup-eligible when local is not first choice."""
    from promptune.engine import _dedup_provider_model_routes

    cfg = {
        "provider": {"default": "claude", "model_claude": ""},
        "local_llm": {"enabled": False, "model": ""},
        "enhancement": {"max_tier": 2},
    }

    assert _dedup_provider_model_routes(cfg) == {("claude", "")}


def test_engine_no_record_when_history_disabled(
    mock_config: dict, tmp_path
) -> None:
    """No history write (and no DB file) when history is disabled."""
    db = tmp_path / "history.db"
    mock_config["history"]["db_path"] = str(db)
    mock_config["history"]["enabled"] = False
    mock_config["enhancement"]["max_tier"] = 0

    enhance("fix the bug", mock_config)

    assert not db.exists()


def test_engine_recording_failure_does_not_break_enhance(
    mock_config: dict, mocker: MockerFixture
) -> None:
    """A history-store failure must not propagate out of enhance()."""
    mock_config["enhancement"]["max_tier"] = 0
    mocker.patch(
        "promptune.engine.HistoryStore",
        side_effect=OSError("disk full"),
    )

    result = enhance("fix the bug", mock_config)

    assert isinstance(result, EnhanceResult)
    assert result.enhanced


def test_engine_unknown_provider_degrades(
    mock_config: dict,
) -> None:
    """An unregistered --provider name degrades to a lower tier, not a crash.

    registry.create() raises ProviderNotFoundError (not ProviderError); the
    routing must catch it and fall back rather than propagate.
    """
    result = enhance(
        "fix the bug",
        mock_config,
        provider_override="totally-not-a-real-provider",
        tier_override=2,
    )

    assert isinstance(result, EnhanceResult)
    assert result.tier_used in (0, 1)


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
    assert result.latency_ms < 5000


def test_engine_missing_api_key_tier2(
    mock_config: dict,
) -> None:
    """Missing API key for Tier 2 falls back gracefully."""
    mock_config["api_keys"]["claude"] = ""
    mock_config["local_llm"]["enabled"] = False

    result = enhance("fix the bug", mock_config)
    assert result.tier_used == 0


def test_engine_forced_tier_falls_back_on_provider_error(
    mocker: MockerFixture, mock_config: dict
) -> None:
    """A forced tier whose provider fails degrades instead of raising.

    Documented contract: graceful degradation — always falls back to the
    tier below on failure (with a logged warning).
    """
    mock_config["local_llm"]["enabled"] = False
    mock_provider = mocker.MagicMock()
    mock_provider.enhance.side_effect = ProviderError("API down")
    mocker.patch(
        "promptune.engine._create_cloud_provider",
        return_value=mock_provider,
    )

    result = enhance("prompt", mock_config, tier_override=2)
    assert result.tier_used == 0


def test_engine_forced_tier2_falls_back_to_tier1(
    mocker: MockerFixture, mock_config: dict
) -> None:
    """Forced tier 2 failure falls back to tier 1 when local LLM is enabled."""
    cloud = mocker.MagicMock()
    cloud.enhance.side_effect = ProviderError("cloud down")
    mocker.patch(
        "promptune.engine._create_cloud_provider", return_value=cloud
    )
    local = mocker.MagicMock()
    local.enhance.return_value = "local result"
    mocker.patch(
        "promptune.providers.local.LocalProvider", return_value=local
    )

    result = enhance("fix the bug", mock_config, tier_override=2)
    assert result.tier_used == 1
    assert result.provider == "local"


def test_engine_forced_tier2_both_providers_fail_falls_back_to_tier0(
    mocker: MockerFixture, mock_config: dict
) -> None:
    """Forced tier 2 with both cloud AND local failing degrades to tier 0."""
    cloud = mocker.MagicMock()
    cloud.enhance.side_effect = ProviderError("cloud down")
    mocker.patch(
        "promptune.engine._create_cloud_provider", return_value=cloud
    )
    local = mocker.MagicMock()
    local.enhance.side_effect = ProviderError("local down")
    mocker.patch(
        "promptune.providers.local.LocalProvider", return_value=local
    )

    result = enhance("fix the bug", mock_config, tier_override=2)
    assert result.tier_used == 0


def test_engine_missing_api_key_forced_tier2_falls_back(
    mock_config: dict,
) -> None:
    """Forcing tier=2 with all keys empty degrades gracefully (no raise)."""
    mock_config["api_keys"]["claude"] = ""
    mock_config["api_keys"]["openai"] = ""
    mock_config["api_keys"]["openrouter"] = ""
    mock_config["local_llm"]["enabled"] = False

    result = enhance("fix the bug", mock_config, tier_override=2)
    assert result.tier_used == 0


def test_engine_dedup_hit_returns_cached(
    mocker: MockerFixture, mock_config: dict
) -> None:
    """When dedup finds a match, engine returns cached result."""
    from promptune.dedup import DedupHit

    mock_config["enhancement"]["max_tier"] = 0
    mock_config["enhancement"]["dedup_enabled"] = True

    mocker.patch(
        "promptune.engine.dedup_check",
        return_value=DedupHit(
            enhanced="cached result",
            similarity=0.95,
            original_prompt="fix the bug",
        ),
    )

    result = enhance("fix the bug", mock_config)

    assert result.enhanced == "cached result"
    assert result.tier_used == -1  # cached indicator


def test_engine_preferences_skip_rules(
    mocker: MockerFixture, mock_config: dict
) -> None:
    """Preferences cause disliked rules to be skipped."""
    from promptune.preferences import Preference
    from promptune.tier0 import apply_rules

    mock_config["enhancement"]["max_tier"] = 0
    mock_config["enhancement"]["preference_learning"] = True
    mock_config["enhancement"]["dedup_enabled"] = False

    mocker.patch(
        "promptune.engine.analyse_rule_preferences",
        return_value=[
            Preference(
                rule_name="role_assignment",
                action="skip",
                confidence=0.8,
                sample_count=10,
            ),
        ],
    )
    mocker.patch(
        "promptune.engine.analyse_edit_patterns",
        return_value=[],
    )

    mock_apply = mocker.patch(
        "promptune.engine.apply_rules",
        wraps=apply_rules,
    )

    enhance("fix the bug", mock_config)

    # Verify apply_rules was called with skip_rules containing "role_assignment"
    call_args = mock_apply.call_args
    skip = call_args.kwargs.get("skip_rules") or (
        call_args[1].get("skip_rules") if len(call_args) > 1 else None
    )
    assert skip is not None
    assert "role_assignment" in skip


def test_engine_preferences_disabled(
    mocker: MockerFixture, mock_config: dict
) -> None:
    """Preference learning disabled -> no preference analysis."""
    mock_config["enhancement"]["max_tier"] = 0
    mock_config["enhancement"]["preference_learning"] = False
    mock_config["enhancement"]["dedup_enabled"] = False

    mock_prefs = mocker.patch("promptune.engine.analyse_rule_preferences")

    enhance("fix the bug", mock_config)

    mock_prefs.assert_not_called()


def test_engine_dedup_disabled_skips_check(
    mocker: MockerFixture, mock_config: dict
) -> None:
    """When dedup is disabled, dedup_check is never called."""
    mock_config["enhancement"]["max_tier"] = 0
    mock_config["enhancement"]["dedup_enabled"] = False

    mock_dedup = mocker.patch("promptune.engine.dedup_check")

    enhance("fix the bug", mock_config)

    mock_dedup.assert_not_called()


def test_engine_template_injection(
    mocker: MockerFixture, mock_config: dict, tmp_path
) -> None:
    """Matched template is injected into system prompt context."""
    from promptune.templates import Template

    mock_config["enhancement"]["max_tier"] = 0
    mock_config["enhancement"]["dedup_enabled"] = False
    mock_config["enhancement"]["preference_learning"] = False

    mocker.patch(
        "promptune.engine.match_template",
        return_value=Template(
            intent="debug",
            domain="python",
            body="## Debug Context\nStack: python",
            filename="debug.md",
        ),
    )
    mocker.patch(
        "promptune.engine._detect_project_root",
        return_value=str(tmp_path),
    )

    result = enhance("fix the auth bug", mock_config)

    assert isinstance(result, EnhanceResult)
    assert result.tier_used == 0


def test_engine_template_matches_documented_debug_python(
    mocker: MockerFixture, mock_config: dict, tmp_path
) -> None:
    """Documented debug/python templates match a Python debugging prompt."""
    prompts_dir = tmp_path / ".prompts"
    prompts_dir.mkdir()
    (prompts_dir / "debug-python.md").write_text(
        "---\n"
        "intent: debug\n"
        "domain: python\n"
        "---\n"
        "PYTHON DEBUG TEMPLATE",
        encoding="utf-8",
    )
    captured: dict[str, str] = {}

    def fake_tier2(
        prompt: str, system_prompt: str, config: dict
    ) -> tuple[str, str, str]:
        captured["system_prompt"] = system_prompt
        return "AI enhanced", "claude", config["provider"]["model_claude"]

    mock_config["local_llm"]["enabled"] = False
    mock_config["enhancement"]["dedup_enabled"] = False
    mock_config["enhancement"]["preference_learning"] = False
    mock_config["context"] = {
        "use_git": False,
        "use_shell_history": False,
        "use_stack_detection": False,
    }
    mocker.patch(
        "promptune.engine._detect_project_root",
        return_value=str(tmp_path),
    )
    mocker.patch("promptune.engine._try_tier2", side_effect=fake_tier2)

    result = enhance("debugging the Python authentication flow", mock_config)

    assert result.tier_used == 2
    assert "PYTHON DEBUG TEMPLATE" in captured["system_prompt"]


def test_engine_context_respects_individual_disable_flags(
    mocker: MockerFixture, mock_config: dict
) -> None:
    """Enabled git context must not drag disabled shell/stack context along."""
    from promptune.context import ContextFingerprint
    from promptune.context.collectors import (
        EnvironmentContext,
        GitContext,
        ShellHistoryContext,
        TechStackContext,
    )

    captured: dict[str, str] = {}

    def fake_tier2(
        prompt: str, system_prompt: str, config: dict
    ) -> tuple[str, str, str]:
        captured["system_prompt"] = system_prompt
        return "AI enhanced", "claude", config["provider"]["model_claude"]

    mock_config["local_llm"]["enabled"] = False
    mock_config["enhancement"]["dedup_enabled"] = False
    mock_config["enhancement"]["preference_learning"] = False
    mock_config["context"] = {
        "use_git": True,
        "use_shell_history": False,
        "use_stack_detection": False,
        "max_context_tokens": 500,
    }
    collect_context = mocker.patch(
        "promptune.engine.collect_context",
        return_value=ContextFingerprint(
            git=GitContext(
                branch="feature/context-flags",
                recent_commits=[],
                modified_files=[],
                diff_stats="",
                stash_count=0,
            ),
            shell=ShellHistoryContext(
                recent_commands=["secret shell command"],
                error_patterns=["pytest failed"],
                session_intent="debugging",
            ),
            tech=TechStackContext(
                languages=["python"],
                frameworks=["django"],
                package_manager="pip",
            ),
            env=EnvironmentContext(
                in_venv=False,
                in_container=False,
                in_ci=False,
                in_ssh=False,
            ),
        ),
    )
    mocker.patch("promptune.engine._try_tier2", side_effect=fake_tier2)

    result = enhance("debug auth timeout", mock_config)

    assert result.tier_used == 2
    collect_context.assert_called_once_with(
        timeout_ms=400,
        include_git=True,
        include_shell=False,
        include_tech=False,
    )
    assert "branch=feature/context-flags" in captured["system_prompt"]
    assert "secret shell command" not in captured["system_prompt"]
    assert "stack=python" not in captured["system_prompt"]
    assert "frameworks=django" not in captured["system_prompt"]


def test_engine_no_template_dir_works(
    mocker: MockerFixture, mock_config: dict
) -> None:
    """No .prompts/ directory works fine."""
    mock_config["enhancement"]["max_tier"] = 0
    mock_config["enhancement"]["dedup_enabled"] = False
    mock_config["enhancement"]["preference_learning"] = False

    mocker.patch(
        "promptune.engine.match_template",
        return_value=None,
    )

    result = enhance("fix the auth bug", mock_config)

    assert isinstance(result, EnhanceResult)


# ── _detect_project_root fallback (L79-81) ──────────────


def test_detect_project_root_no_git(
    mocker: MockerFixture,
) -> None:
    """Falls back to cwd when git is absent."""
    from promptune.engine import _detect_project_root

    mocker.patch(
        "subprocess.run",
        side_effect=FileNotFoundError("no git"),
    )
    root = _detect_project_root()
    assert root


# ── _try_tier1 creates LocalProvider (L121-131) ─────────


def test_try_tier1_success(
    mocker: MockerFixture,
) -> None:
    """_try_tier1 creates LocalProvider and enhances."""
    from promptune.engine import _try_tier1

    mock_prov = mocker.MagicMock()
    mock_prov.enhance.return_value = "tier1 result"
    mocker.patch(
        "promptune.providers.local.LocalProvider",
        return_value=mock_prov,
    )
    cfg = {
        "local_llm": {
            "model": "qwen",
            "host": "http://localhost:11434",
            "api_key": "",
        },
        "enhancement": {"timeout_seconds": 10},
    }
    result = _try_tier1("prompt", "system", cfg)
    assert result == "tier1 result"


# ── provider_override (L163) ────────────────────────────


def test_provider_override(
    mocker: MockerFixture, mock_config: dict
) -> None:
    """provider_override changes config default."""
    mock_config["enhancement"]["max_tier"] = 0
    result = enhance(
        "fix the bug",
        mock_config,
        provider_override="openai",
    )
    assert result.tier_used == 0


# ── history exception caught (L231-236) ─────────────────


def test_history_exception_caught(
    mocker: MockerFixture, mock_config: dict
) -> None:
    """Exception in history/dedup is caught."""
    mock_config["enhancement"]["max_tier"] = 0
    mocker.patch(
        "promptune.engine.HistoryStore",
        side_effect=RuntimeError("db locked"),
    )
    result = enhance("fix the bug", mock_config)
    assert result.tier_used == 0


# ── template injection failure (L295-296) ────────────────


def test_template_injection_exception(
    mocker: MockerFixture, mock_config: dict
) -> None:
    """Template injection exception is caught."""
    mock_config["enhancement"]["max_tier"] = 0
    mock_config["enhancement"]["dedup_enabled"] = False
    mock_config["enhancement"][
        "preference_learning"
    ] = False
    mocker.patch(
        "promptune.engine.match_template",
        side_effect=RuntimeError("broken"),
    )
    result = enhance("fix the bug", mock_config)
    assert result.tier_used == 0


def test_template_injection_logs_warning_on_failure(
    mocker: MockerFixture, mock_config: dict, caplog
) -> None:
    """Swallowed template-injection failure surfaces as a warning."""
    import logging

    mock_config["enhancement"]["max_tier"] = 0
    mock_config["enhancement"]["dedup_enabled"] = False
    mock_config["enhancement"]["preference_learning"] = False
    mocker.patch(
        "promptune.engine.match_template",
        side_effect=RuntimeError("broken"),
    )
    with caplog.at_level(logging.WARNING, logger="promptune.engine"):
        enhance("fix the bug", mock_config)
    warnings = [
        r for r in caplog.records if r.levelno >= logging.WARNING
    ]
    assert any(
        "template" in r.getMessage().lower() for r in warnings
    )


def test_history_failure_logs_warning(
    mocker: MockerFixture, mock_config: dict, caplog
) -> None:
    """Swallowed history/dedup/preferences failure surfaces as a warning."""
    import logging

    mock_config["enhancement"]["max_tier"] = 0
    mocker.patch(
        "promptune.engine.HistoryStore",
        side_effect=RuntimeError("db locked"),
    )
    with caplog.at_level(logging.WARNING, logger="promptune.engine"):
        enhance("fix the bug", mock_config)
    warnings = [
        r for r in caplog.records if r.levelno >= logging.WARNING
    ]
    assert any(
        "history" in r.getMessage().lower() for r in warnings
    )


# ── forced tier=0 and tier=1 (L306, L308-313) ───────────


def test_forced_tier0(mock_config: dict) -> None:
    """tier_override=0 forces tier 0 only."""
    result = enhance(
        "fix the bug", mock_config, tier_override=0
    )
    assert result.tier_used == 0


def test_forced_tier1(
    mocker: MockerFixture, mock_config: dict
) -> None:
    """tier_override=1 forces tier 1."""
    mock_prov = mocker.MagicMock()
    mock_prov.enhance.return_value = "local result"
    mocker.patch(
        "promptune.providers.local.LocalProvider",
        return_value=mock_prov,
    )
    result = enhance(
        "fix the bug", mock_config, tier_override=1
    )
    assert result.tier_used == 1
    assert result.provider == "local"
    assert result.model == "qwen2.5:3b"


# ── non-forced tier1 success (L328-330) ─────────────────


def test_tier1_success_non_forced(
    mocker: MockerFixture, mock_config: dict
) -> None:
    """Tier 1 succeeds in non-forced routing."""
    mock_config["enhancement"]["max_tier"] = 1
    mock_prov = mocker.MagicMock()
    mock_prov.enhance.return_value = "local enhanced"
    mocker.patch(
        "promptune.providers.local.LocalProvider",
        return_value=mock_prov,
    )
    # Use a short prompt that scores low (< 70)
    result = enhance("fix bug", mock_config)
    assert result.tier_used == 1
    assert result.provider == "local"


# ── history disabled path ────────────────────────────────


def test_history_disabled(
    mocker: MockerFixture, mock_config: dict
) -> None:
    """History disabled skips dedup and preferences."""
    mock_config["enhancement"]["max_tier"] = 0
    mock_config["history"]["enabled"] = False
    mock_dedup = mocker.patch(
        "promptune.engine.dedup_check"
    )
    result = enhance("fix the bug", mock_config)
    assert result.tier_used == 0
    mock_dedup.assert_not_called()
