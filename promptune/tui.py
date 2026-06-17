"""Rich TUI: display original vs enhanced, accept/edit/reject."""

from __future__ import annotations

from enum import Enum

import readchar
from prompt_toolkit import prompt as pt_prompt
from rich.columns import Columns
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel

from promptune.context import ContextFingerprint
from promptune.engine import EnhanceResult
from promptune.pqs import PQScore, compute_pqs


class Action(Enum):
    """User action in the TUI."""

    ACCEPT = "accept"
    EDIT = "edit"
    REJECT = "reject"
    MORE = "more"
    QUALITY = "quality"
    DETAILS = "details"
    CONTEXT = "context"


def _get_user_action(
    *, expanded: bool = False
) -> Action:
    """Prompt user for action via single keypress.

    When expanded=False: accepts A/E/R/?
    When expanded=True: also accepts Q/D/C
    """
    if expanded:
        prompt_text = (
            "\n[A]ccept  [E]dit  [R]eject  "
            "[Q]uality  [D]etails  [C]ontext: "
        )
    else:
        prompt_text = (
            "\n[A]ccept  [E]dit  [R]eject  [?] More: "
        )

    print(prompt_text, end="", flush=True)
    while True:
        try:
            key = readchar.readkey().lower()
        except (KeyboardInterrupt, EOFError):
            print()
            return Action.REJECT
        # EOF / closed stdin yields an empty string; treat as reject rather
        # than spinning the loop forever (100% CPU) on an unmatched key.
        if not key:
            print()
            return Action.REJECT
        if key == "a":
            print(key)
            return Action.ACCEPT
        if key == "e":
            print(key)
            return Action.EDIT
        if key == "r":
            print(key)
            return Action.REJECT
        if key == "?":
            print(key)
            return Action.MORE
        if expanded and key == "q":
            print(key)
            return Action.QUALITY
        if expanded and key == "d":
            print(key)
            return Action.DETAILS
        if expanded and key == "c":
            print(key)
            return Action.CONTEXT


def _edit_prompt(text: str) -> str:
    """Open prompt_toolkit editor for editing the enhanced prompt."""
    print("\nEdit the enhanced prompt (press Esc then Enter to finish):")
    edited = pt_prompt(
        "> ",
        default=text,
        multiline=True,
    )
    return edited


def display_enhancement(
    original: str,
    enhanced: str,
) -> str | None:
    """Display original and enhanced prompts, return user's choice."""
    console = Console()

    original_panel = Panel(
        escape(original),
        title="Original",
        border_style="dim",
    )
    enhanced_panel = Panel(
        escape(enhanced),
        title="Enhanced",
        border_style="green",
    )

    if console.width >= 100:
        console.print(Columns([original_panel, enhanced_panel]))
    else:
        console.print(original_panel)
        console.print(enhanced_panel)

    action = _get_user_action()

    if action == Action.ACCEPT:
        return enhanced
    if action == Action.EDIT:
        return _edit_prompt(enhanced)
    return None


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
    return (
        f"promptune  [{tier_label} \u00b7 "
        f"{method} \u00b7 {latency}]"
    )


def _render_quality_toggle(
    pqs_before: PQScore, pqs_after: PQScore
) -> str:
    """Render quality score breakdown."""
    delta_overall = pqs_after.overall - pqs_before.overall
    delta_str = (
        f"+{delta_overall}" if delta_overall >= 0 else str(delta_overall)
    )
    lines: list[str] = []
    lines.append(
        f"  Quality: {pqs_before.overall} "
        f"\u2500\u2500\u25b6 {pqs_after.overall}  "
        f"({delta_str})"
    )
    lines.append("")

    dimensions = [
        (
            "Clarity",
            pqs_before.clarity,
            pqs_after.clarity,
        ),
        (
            "Specificity",
            pqs_before.specificity,
            pqs_after.specificity,
        ),
        (
            "Context",
            pqs_before.context,
            pqs_after.context,
        ),
        (
            "Structure",
            pqs_before.structure,
            pqs_after.structure,
        ),
        (
            "Actionability",
            pqs_before.actionability,
            pqs_after.actionability,
        ),
    ]

    for name, before, after in dimensions:
        delta = after.score - before.score
        delta_str = (
            f"+{delta}" if delta >= 0 else str(delta)
        )
        lines.append(
            f"  {name:<15} {before.bar}  "
            f"{before.score:>3} \u2500\u2500\u25b6 "
            f"{after.bar}  {after.score:>3}  "
            f"({delta_str})"
        )

    return "\n".join(lines)


def _render_details_toggle(
    rules_applied: list[str],
) -> str:
    """Render rules/details applied."""
    if not rules_applied:
        return "  Rules applied: none"
    return (
        f"  Rules applied: {', '.join(rules_applied)}"
    )


def _render_context_toggle(
    context: ContextFingerprint | None,
) -> str:
    """Render context fingerprint summary."""
    if context is None:
        return "  No context collected"

    parts: list[str] = []
    if context.git.branch:
        parts.append(f"branch={context.git.branch}")
    if context.tech.languages:
        parts.append(
            f"stack={','.join(context.tech.languages)}"
        )
    if context.tech.frameworks:
        parts.append(
            "frameworks="
            f"{','.join(context.tech.frameworks)}"
        )
    if context.shell.session_intent != "unknown":
        parts.append(
            f"intent={context.shell.session_intent}"
        )
    if context.tech.package_manager:
        parts.append(
            f"pkg={context.tech.package_manager}"
        )

    if not parts:
        return "  No context collected"

    return f"  Context: {' | '.join(parts)}"


def _render_panels(
    console: Console, result: EnhanceResult
) -> None:
    """Render original and enhanced panels."""
    original_panel = Panel(
        escape(result.original),
        title="Original",
        border_style="dim",
    )
    enhanced_panel = Panel(
        escape(result.enhanced),
        title="Enhanced",
        border_style="green",
    )

    if console.width >= 100:
        console.print(
            Columns([original_panel, enhanced_panel])
        )
    else:
        console.print(original_panel)
        console.print(enhanced_panel)


def display_result(result: EnhanceResult) -> str | None:
    """Display full enhancement result with TUI.

    Interactive loop: shows header + panels, then prompts
    for action. [?] expands to show Q/D/C toggles.
    Toggle keys show/hide quality, details, context sections.
    A/E/R exits the loop with a decision.
    """
    console = Console()
    pqs_before = compute_pqs(result.score_before)
    pqs_after = compute_pqs(result.score_after)

    expanded = False
    show_quality = False
    show_details = False
    show_context = False

    while True:
        console.print(_render_header(result))
        _render_panels(console, result)

        if show_quality:
            console.print(
                _render_quality_toggle(
                    pqs_before, pqs_after
                )
            )
        if show_details:
            console.print(
                _render_details_toggle(
                    result.rules_applied
                )
            )
        if show_context:
            console.print(
                _render_context_toggle(result.context),
                markup=False,
            )

        if expanded:
            console.print(
                "\n[A]ccept  [E]dit  [R]eject  "
                "[Q]uality  [D]etails  [C]ontext"
            )

        action = _get_user_action(expanded=expanded)

        if action == Action.ACCEPT:
            return result.enhanced
        if action == Action.EDIT:
            return _edit_prompt(result.enhanced)
        if action == Action.REJECT:
            return None
        if action == Action.MORE:
            expanded = True
        elif action == Action.QUALITY:
            show_quality = not show_quality
        elif action == Action.DETAILS:
            show_details = not show_details
        elif action == Action.CONTEXT:
            show_context = not show_context
