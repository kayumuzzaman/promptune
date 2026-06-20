"""Router Engine: tier-based prompt enhancement orchestration.

Flow:
1. Score raw prompt
2. Apply Tier 0 rules (always)
3. Re-score post-Tier 0
4. Route: score >= 70 -> Tier 0 | try Tier 1 -> try Tier 2 -> fallback
5. Return EnhanceResult with full metadata

Design: Strategy pattern — tier handlers are independent functions.
Graceful degradation — always falls back to tier below on failure.
"""

from __future__ import annotations

import copy
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from promptune.config import ConfigError
from promptune.context import ContextFingerprint, collect_context
from promptune.context.collectors import (
    GitContext,
    ShellHistoryContext,
    TechStackContext,
)
from promptune.context.ranker import rank_context
from promptune.dedup import dedup_check
from promptune.history import HistoryEntry, HistoryStore
from promptune.meta_prompt import (
    build_system_prompt,
    detect_domain,
    detect_intent,
    detect_stack,
)
from promptune.preferences import analyse_edit_patterns, analyse_rule_preferences
from promptune.providers import (
    BaseProvider,
    ProviderError,
    ProviderNotFoundError,
    ProviderRegistry,
)
from promptune.providers.anthropic import register as register_claude
from promptune.providers.openai import register as register_openai
from promptune.providers.openrouter import (
    register as register_openrouter,
)
from promptune.scorer import ScoreResult, score_prompt
from promptune.templates import inject_variables, match_template
from promptune.tier0 import apply_rules

_log = logging.getLogger(__name__)

_TEMPLATE_INTENT_ALIASES: dict[str, list[str]] = {
    "debug": ["debug", "bug", "crash", "error", "failure", "fix"],
    "build": ["build", "create", "implement", "develop", "add"],
    "refactor": ["refactor", "rewrite", "migrate"],
}


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
    rules_explained: list[tuple[str, str]]
    context: Any  # ContextFingerprint | None — added in Task 6
    format_style: str  # vestigial; always "auto" (provider formatting removed)
    provider: str | None  # null for Tier 0
    model: str | None  # null for Tier 0
    # Row id of the history record written for this enhancement, so an
    # interactive caller can correct the decision (reject/edit) after the user
    # acts. None when nothing was recorded (history disabled or a dedup hit).
    history_id: int | None = None


def _detect_project_root() -> str:
    """Detect the current project root via git or cwd."""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return str(Path.cwd())


def _template_intent_aliases(prompt: str) -> list[str]:
    """Return template-specific intent labels promised in docs."""
    lower = prompt.lower()
    aliases: list[str] = []
    for intent, keywords in _TEMPLATE_INTENT_ALIASES.items():
        if any(_template_keyword_matches(lower, kw) for kw in keywords):
            aliases.append(intent)
    return aliases


def _template_keyword_matches(text: str, keyword: str) -> bool:
    last = re.escape(keyword[-1])
    pattern = rf"\b{re.escape(keyword)}(?:{last}?(?:ing|ed)|e?s)?\b"
    return re.search(pattern, text) is not None


def _dedup_provider_model_routes(
    cfg: dict[str, Any],
) -> set[tuple[str | None, str | None]] | None:
    """Return the effective AI routes needed for provider/model cache safety.

    A cached result from one provider/model is the wrong text for another, so
    auto-tier dedup is scoped to the routes this config could actually take.
    """
    max_tier = cfg["enhancement"].get("max_tier", 0)
    if max_tier == 0:
        return set()
    routes: set[tuple[str | None, str | None]] = set()
    if (
        cfg["local_llm"].get("enabled", False)
        and max_tier >= 1
    ):
        routes.add(("local", cfg["local_llm"].get("model", "")))
    elif max_tier >= 2:
        provider = cfg["provider"]["default"]
        model = cfg["provider"].get(f"model_{provider}", "")
        routes.add((provider, model))
    return routes


def _context_with_enabled_collectors(
    fp: ContextFingerprint,
    context_cfg: dict[str, Any],
) -> ContextFingerprint:
    git = fp.git if context_cfg.get("use_git", True) else GitContext(
        branch="",
        recent_commits=[],
        modified_files=[],
        diff_stats="",
        stash_count=0,
    )
    shell = (
        fp.shell
        if context_cfg.get("use_shell_history", True)
        else ShellHistoryContext(
            recent_commands=[],
            error_patterns=[],
            session_intent="unknown",
        )
    )
    tech = (
        fp.tech
        if context_cfg.get("use_stack_detection", True)
        else TechStackContext(
            languages=[],
            frameworks=[],
            package_manager=None,
        )
    )
    return ContextFingerprint(git=git, shell=shell, tech=tech, env=fp.env)


def get_registry() -> ProviderRegistry:
    """Build and return the provider registry."""
    registry = ProviderRegistry()
    register_claude(registry)
    register_openai(registry)
    register_openrouter(registry)
    return registry


def _build_provider_config(
    provider_name: str, config: dict[str, Any]
) -> dict[str, Any]:
    """Build a provider config dict from the new schema."""
    model_key = f"model_{provider_name}"
    timeout = config["enhancement"].get("timeout_seconds", 10)
    return {
        "api_key": config["api_keys"].get(provider_name, ""),
        "model": config["provider"].get(model_key, ""),
        "timeout": float(timeout),
        "max_tokens": config["enhancement"].get("max_tokens_output", 400),
    }


def _create_cloud_provider(
    provider_name: str, config: dict[str, Any]
) -> BaseProvider:
    """Create a cloud provider instance."""
    registry = get_registry()
    provider_config = _build_provider_config(
        provider_name, config
    )
    return registry.create(provider_name, provider_config)


def _try_tier1(
    prompt: str, system_prompt: str, config: dict[str, Any]
) -> str:
    """Attempt Tier 1 enhancement via local LLM."""
    from promptune.providers.local import LocalProvider

    local_cfg = config["local_llm"]
    timeout = config["enhancement"].get("timeout_seconds", 10)
    provider = LocalProvider(
        model=local_cfg["model"],
        host=local_cfg["host"],
        api_key=local_cfg.get("api_key", ""),
        timeout=float(timeout),
        max_tokens=config["enhancement"].get("max_tokens_output", 400),
    )
    return provider.enhance(prompt, system_prompt)


def _try_tier2(
    prompt: str, system_prompt: str, config: dict[str, Any]
) -> tuple[str, str, str]:
    """Attempt Tier 2 enhancement via cloud provider."""
    provider_name = config["provider"]["default"]
    api_key = config["api_keys"].get(provider_name, "")
    if not api_key:
        raise ConfigError(
            f"Missing API key for provider '{provider_name}'."
        )

    provider = _create_cloud_provider(provider_name, config)
    model_key = f"model_{provider_name}"
    model = config["provider"].get(model_key, "")
    enhanced = provider.enhance(prompt, system_prompt)
    return enhanced, provider_name, model


def _record_enhancement(
    history_cfg: dict[str, Any],
    *,
    original: str,
    enhanced: str,
    tier_used: int,
    provider: str | None,
    format_style: str | None,
    model: str | None,
    score_before: int,
    score_after: int,
    latency_ms: float,
    rules_applied: list[str],
    project_root: str | None,
) -> int | None:
    """Persist a completed enhancement to the history store (best-effort).

    Returns the new row id (so an interactive caller can later correct the
    decision via ``HistoryStore.set_decision``) or ``None`` on failure. The
    enhancement is recorded as ``"accept"`` — the true interactive decision isn't
    known at engine level and is corrected post-hoc by the CLI. A failure here is
    logged and swallowed — recording must never break the enhancement path.
    """
    try:
        with HistoryStore(
            db_path=Path(
                history_cfg.get(
                    "db_path", "~/.local/share/promptune/history.db"
                )
            ).expanduser(),
            max_entries=history_cfg.get("max_entries", 10000),
        ) as store:
            return store.record(
                HistoryEntry(
                    original=original,
                    enhanced=enhanced,
                    decision="accept",
                    edit_result=None,
                    tier_used=tier_used,
                    provider=provider,
                    format_style=format_style,
                    model=model,
                    score_before=score_before,
                    score_after=score_after,
                    latency_ms=latency_ms,
                    rules_applied=rules_applied,
                    context_json=None,
                    project_root=project_root,
                )
            )
    except Exception:
        _log.warning(
            "Failed to record enhancement to history", exc_info=True
        )
        return None


def enhance(
    prompt: str,
    config: dict[str, Any],
    provider_override: str | None = None,
    tier_override: int | None = None,
    record: bool = True,
) -> EnhanceResult:
    """Enhance a prompt using tier-based routing.

    When *record* is False the enhancement is not written to history. The
    auto-enhance gate uses this: it has no accept/reject surface, so recording
    every gated prompt as a confirmed "accept" would pollute dedup and
    preference learning with outcomes the user never confirmed.
    """
    start = time.perf_counter()

    cfg = copy.deepcopy(config)
    if provider_override:
        cfg["provider"]["default"] = provider_override

    max_tier = cfg["enhancement"]["max_tier"]
    if tier_override is not None:
        max_tier = tier_override
        forced_tier = True
    else:
        forced_tier = False

    # Detect project root once (used by dedup, preferences, templates)
    project_root = _detect_project_root()

    # Dedup check + preference learning — share a single HistoryStore
    dedup_cfg = cfg["enhancement"]
    history_cfg = cfg.get("history", {})
    history_enabled = history_cfg.get("enabled", True)

    skip_rules: set[str] = set()
    style = cfg["enhancement"]["default_mode"]

    if history_enabled:
        try:
            with HistoryStore(
                db_path=Path(
                    history_cfg.get(
                        "db_path",
                        "~/.local/share/promptune/history.db",
                    )
                ).expanduser(),
                max_entries=history_cfg.get("max_entries", 10000),
            ) as _store:
                # Dedup check — early exit if similar prompt was recently
                # enhanced under the same effective options. Explicit per-call
                # overrides (--tier / --provider) must be honoured with a fresh
                # run, never served a generic cached result, and a cached hit is
                # only reused when its format matches the current request.
                if (
                    dedup_cfg.get("dedup_enabled", True)
                    and tier_override is None
                    and provider_override is None
                ):
                    dedup_routes = _dedup_provider_model_routes(cfg)
                    hit = dedup_check(
                        prompt=prompt,
                        project_root=project_root,
                        store=_store,
                        threshold=dedup_cfg.get("dedup_threshold", 0.85),
                        window=dedup_cfg.get("dedup_window", 50),
                        provider_model_routes=dedup_routes,
                    )
                    if hit is not None:
                        latency_ms = (time.perf_counter() - start) * 1000
                        score_before = score_prompt(prompt)
                        score_after = score_prompt(hit.enhanced)
                        return EnhanceResult(
                            original=prompt,
                            enhanced=hit.enhanced,
                            tier_used=-1,
                            latency_ms=latency_ms,
                            score_before=score_before,
                            score_after=score_after,
                            rules_applied=[],
                            rules_explained=[],
                            context=None,
                            format_style="auto",
                            provider=None,
                            model=None,
                        )

                # Preference learning — determine rules to skip
                if dedup_cfg.get("preference_learning", True):
                    min_samples = dedup_cfg.get("preference_min_samples", 5)
                    rule_prefs = analyse_rule_preferences(
                        _store,
                        min_samples=min_samples,
                        project=project_root,
                    )
                    for pref in rule_prefs:
                        if pref.action == "skip":
                            skip_rules.add(pref.rule_name)

                    edit_patterns = analyse_edit_patterns(
                        _store,
                        min_samples=min_samples,
                        project=project_root,
                    )
                    for pat in edit_patterns:
                        if pat.pattern_type == "removes_role":
                            skip_rules.add("role_assignment")
                        elif pat.pattern_type == "removes_format":
                            skip_rules.add("output_format")
        except Exception:
            _log.warning(
                "History/dedup/preferences failed", exc_info=True
            )

    # Step 1: Score raw prompt
    score_before = score_prompt(prompt)

    # Step 2: Apply Tier 0 rules (always)
    tier0_result = apply_rules(prompt, score_before, skip_rules=skip_rules)

    # Step 3: Re-score post-Tier 0
    score_after = score_prompt(tier0_result.enhanced)

    # Build system prompt for AI tiers
    intent = detect_intent(prompt)
    domain = detect_domain(prompt)
    stack = detect_stack(prompt)
    system_prompt = build_system_prompt(
        intent=intent,
        domain=domain,
        stack=stack,
        style=style,
    )

    # Collect context if enabled
    context_cfg = cfg.get("context", {})
    use_git = context_cfg.get("use_git", True)
    use_shell = context_cfg.get("use_shell_history", True)
    use_tech = context_cfg.get("use_stack_detection", True)
    context_enabled = any([use_git, use_shell, use_tech])
    context_fp = None
    if context_enabled:
        context_fp = _context_with_enabled_collectors(
            collect_context(
                timeout_ms=400,
                include_git=use_git,
                include_shell=use_shell,
                include_tech=use_tech,
            ),
            context_cfg,
        )
        context_str = rank_context(
            context_fp,
            token_budget=context_cfg.get(
                "max_context_tokens", 500
            ),
        )
        if context_str:
            system_prompt += (
                f"\n\n## Context\n{context_str}"
            )

    # Template injection — match .prompts/ template and add to system prompt
    try:
        matched_tpl = match_template(
            project_root,
            intent,
            domain,
            intent_aliases=_template_intent_aliases(prompt),
            domain_aliases=stack,
        )
        if matched_tpl is not None:
            tpl_vars: dict[str, str] = {
                "intent": matched_tpl.intent or intent,
                "domain": matched_tpl.domain or domain,
                "project_root": project_root,
            }
            if context_fp is not None:
                tpl_vars["branch"] = context_fp.git.branch
                tpl_vars["stack"] = ", ".join(
                    context_fp.tech.languages + context_fp.tech.frameworks
                )
            tpl_body = inject_variables(matched_tpl.body, tpl_vars)
            system_prompt += f"\n\n## Template\n{tpl_body}"
    except Exception:
        _log.warning("Template injection failed", exc_info=True)

    # Step 4: Route
    enhanced = tier0_result.enhanced
    tier_used = 0
    provider_name: str | None = None
    model_name: str | None = None

    if forced_tier:
        # Graceful degradation: a forced tier that fails falls back to the
        # tier below (down to tier 0) with a logged warning, mirroring the
        # auto-routing contract rather than raising a hard error.
        if max_tier == 1:
            try:
                enhanced = _try_tier1(
                    enhanced, system_prompt, cfg
                )
                tier_used = 1
                provider_name = "local"
                model_name = cfg["local_llm"]["model"]
            except (ProviderError, ProviderNotFoundError, ConfigError) as exc:
                _log.warning(
                    "Forced tier 1 failed, falling back to tier 0: %s", exc
                )
        elif max_tier >= 2:
            try:
                result_text, provider_name, model_name = _try_tier2(
                    enhanced, system_prompt, cfg
                )
                enhanced = result_text
                tier_used = 2
            except (ProviderError, ProviderNotFoundError, ConfigError) as exc:
                _log.warning(
                    "Forced tier 2 failed, falling back: %s", exc
                )
                if cfg["local_llm"]["enabled"]:
                    try:
                        enhanced = _try_tier1(
                            enhanced, system_prompt, cfg
                        )
                        tier_used = 1
                        provider_name = "local"
                        model_name = cfg["local_llm"]["model"]
                    except (ProviderError, ProviderNotFoundError, ConfigError) as exc2:
                        _log.warning(
                            "Tier 1 fallback also failed, "
                            "using tier 0: %s",
                            exc2,
                        )
    else:
        if score_after.total < 70:
            # Try Tier 1 if enabled
            if max_tier >= 1 and cfg["local_llm"]["enabled"]:
                try:
                    enhanced = _try_tier1(
                        enhanced, system_prompt, cfg
                    )
                    tier_used = 1
                    provider_name = "local"
                    model_name = cfg["local_llm"]["model"]
                except (ProviderError, ProviderNotFoundError, ConfigError):
                    pass

            # Try Tier 2 if Tier 1 didn't work
            if tier_used == 0 and max_tier >= 2:
                try:
                    (
                        result_text,
                        provider_name,
                        model_name,
                    ) = _try_tier2(
                        enhanced, system_prompt, cfg
                    )
                    enhanced = result_text
                    tier_used = 2
                except (ProviderError, ProviderNotFoundError, ConfigError):
                    pass

    # Re-score final result if AI tier was used
    if tier_used > 0:
        score_after = score_prompt(enhanced)

    latency_ms = (time.perf_counter() - start) * 1000

    # Persist to history. This write side is what powers dedup, the
    # `history`/`preferences` commands, and preference learning — the read side
    # was always wired, the write side never was. Best-effort: a history failure
    # must never break enhancement.
    history_id: int | None = None
    if history_enabled and record:
        history_id = _record_enhancement(
            history_cfg,
            original=prompt,
            enhanced=enhanced,
            tier_used=tier_used,
            provider=provider_name,
            format_style="auto",
            model=model_name,
            score_before=round(score_before.total),
            score_after=round(score_after.total),
            latency_ms=latency_ms,
            rules_applied=tier0_result.rules_applied,
            project_root=project_root,
        )

    return EnhanceResult(
        original=prompt,
        enhanced=enhanced,
        tier_used=tier_used,
        latency_ms=latency_ms,
        score_before=score_before,
        score_after=score_after,
        rules_applied=tier0_result.rules_applied,
        rules_explained=tier0_result.rules_explained,
        context=context_fp,
        format_style="auto",
        provider=provider_name,
        model=model_name,
        history_id=history_id,
    )
