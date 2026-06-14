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
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from promptune.config import ConfigError
from promptune.context import collect_context
from promptune.context.ranker import rank_context
from promptune.dedup import dedup_check
from promptune.history import HistoryStore
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
    format_style: str
    provider: str | None  # null for Tier 0
    model: str | None  # null for Tier 0


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


def enhance(
    prompt: str,
    config: dict[str, Any],
    provider_override: str | None = None,
    tier_override: int | None = None,
) -> EnhanceResult:
    """Enhance a prompt using tier-based routing."""
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
            with HistoryStore() as _store:
                # Dedup check — early exit if similar prompt was recently enhanced
                if dedup_cfg.get("dedup_enabled", True):
                    hit = dedup_check(
                        prompt=prompt,
                        project_root=project_root,
                        store=_store,
                        threshold=dedup_cfg.get("dedup_threshold", 0.85),
                        window=dedup_cfg.get("dedup_window", 50),
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
                            format_style=cfg["provider"]["format_style"],
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
    context_enabled = any([
        context_cfg.get("use_git", True),
        context_cfg.get("use_shell_history", True),
        context_cfg.get("use_stack_detection", True),
    ])
    context_fp = None
    if context_enabled:
        context_fp = collect_context(timeout_ms=400)
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
        matched_tpl = match_template(project_root, intent, domain)
        if matched_tpl is not None:
            tpl_vars: dict[str, str] = {
                "intent": intent,
                "domain": domain,
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
        if max_tier == 0:
            pass
        elif max_tier == 1:
            enhanced = _try_tier1(
                enhanced, system_prompt, cfg
            )
            tier_used = 1
            provider_name = "local"
            model_name = cfg["local_llm"]["model"]
        elif max_tier >= 2:
            result_text, provider_name, model_name = _try_tier2(
                enhanced, system_prompt, cfg
            )
            enhanced = result_text
            tier_used = 2
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
                except (ProviderError, ConfigError):
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
                except (ProviderError, ConfigError):
                    pass

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
        rules_explained=tier0_result.rules_explained,
        context=context_fp,
        format_style=cfg["provider"]["format_style"],
        provider=provider_name,
        model=model_name,
    )
