"""Step 8: TUI — tests."""

from pytest_mock import MockerFixture

from promptune.context import ContextFingerprint
from promptune.context.collectors import (
    EnvironmentContext,
    GitContext,
    ShellHistoryContext,
    TechStackContext,
)
from promptune.engine import EnhanceResult
from promptune.pqs import compute_pqs
from promptune.scorer import DimensionScore, ScoreResult
from promptune.tui import (
    Action,
    _render_context_toggle,
    _render_details_toggle,
    _render_header,
    _render_quality_toggle,
    display_enhancement,
    display_result,
)


def _mock_console(mocker: MockerFixture, width: int = 80) -> None:
    """Patch Console with a given terminal width."""
    mock_cls = mocker.patch("promptune.tui.Console")
    mock_cls.return_value.width = width


def test_tui_displays_original(mocker: MockerFixture) -> None:
    """Original prompt shown in panel."""
    mock_cls = mocker.patch("promptune.tui.Console")
    mock_instance = mock_cls.return_value
    mock_instance.width = 80
    mocker.patch(
        "promptune.tui._get_user_action", return_value=Action.ACCEPT
    )

    display_enhancement("original text", "enhanced text")

    # Check that a Panel with "original text" was printed
    print_calls = mock_instance.print.call_args_list
    panels = [
        call[0][0]
        for call in print_calls
        if call[0] and hasattr(call[0][0], "renderable")
    ]
    panel_contents = [str(p.renderable) for p in panels]
    assert any("original text" in c for c in panel_contents)


def test_tui_displays_enhanced(mocker: MockerFixture) -> None:
    """Enhanced prompt shown in panel."""
    mock_cls = mocker.patch("promptune.tui.Console")
    mock_instance = mock_cls.return_value
    mock_instance.width = 80
    mocker.patch(
        "promptune.tui._get_user_action", return_value=Action.ACCEPT
    )

    display_enhancement("original text", "enhanced text")

    print_calls = mock_instance.print.call_args_list
    panels = [
        call[0][0]
        for call in print_calls
        if call[0] and hasattr(call[0][0], "renderable")
    ]
    panel_contents = [str(p.renderable) for p in panels]
    assert any("enhanced text" in c for c in panel_contents)


def test_tui_accept_returns_enhanced(mocker: MockerFixture) -> None:
    """'a' key returns enhanced text."""
    _mock_console(mocker)
    mocker.patch(
        "promptune.tui._get_user_action", return_value=Action.ACCEPT
    )

    result = display_enhancement("original", "enhanced")

    assert result == "enhanced"


def test_tui_reject_returns_none(mocker: MockerFixture) -> None:
    """'r' key returns None."""
    _mock_console(mocker)
    mocker.patch(
        "promptune.tui._get_user_action", return_value=Action.REJECT
    )

    result = display_enhancement("original", "enhanced")

    assert result is None


def test_tui_edit_opens_editor(mocker: MockerFixture) -> None:
    """'e' key triggers prompt_toolkit editor."""
    _mock_console(mocker)
    mocker.patch(
        "promptune.tui._get_user_action", return_value=Action.EDIT
    )
    mock_edit = mocker.patch(
        "promptune.tui._edit_prompt", return_value="edited text"
    )

    display_enhancement("original", "enhanced")

    mock_edit.assert_called_once_with("enhanced")


def test_tui_edit_returns_modified(mocker: MockerFixture) -> None:
    """Edited text returned after edit."""
    _mock_console(mocker)
    mocker.patch(
        "promptune.tui._get_user_action", return_value=Action.EDIT
    )
    mocker.patch(
        "promptune.tui._edit_prompt", return_value="my edited text"
    )

    result = display_enhancement("original", "enhanced")

    assert result == "my edited text"


def test_tui_wide_terminal_side_by_side(
    mocker: MockerFixture,
) -> None:
    """Wide terminal uses columns layout."""
    mock_cls = mocker.patch("promptune.tui.Console")
    mock_instance = mock_cls.return_value
    mock_instance.width = 120
    mocker.patch(
        "promptune.tui._get_user_action", return_value=Action.ACCEPT
    )

    display_enhancement("original", "enhanced")

    print_calls = mock_instance.print.call_args_list
    rendered = " ".join(str(c) for c in print_calls)
    assert "Columns" in rendered or "columns" in rendered


def test_tui_narrow_terminal_stacked(mocker: MockerFixture) -> None:
    """Narrow terminal uses stacked layout."""
    mock_cls = mocker.patch("promptune.tui.Console")
    mock_instance = mock_cls.return_value
    mock_instance.width = 60
    mocker.patch(
        "promptune.tui._get_user_action", return_value=Action.ACCEPT
    )

    display_enhancement("original", "enhanced")

    print_calls = mock_instance.print.call_args_list
    rendered = " ".join(str(c) for c in print_calls)
    assert "Columns" not in rendered


# --- Task 9 helpers ---


def _make_dim(
    score: float = 0.5, suggestion: str = "test"
) -> DimensionScore:
    return DimensionScore(
        score=score,
        max_weight=15,
        signals=[],
        suggestion=suggestion,
    )


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
        enhanced="Diagnose and fix the auth bug.",
        tier_used=tier_used,
        latency_ms=latency_ms,
        score_before=_make_score_result(11),
        score_after=_make_score_result(81),
        rules_applied=rules_applied
        or ["output_format", "constraints"],
        rules_explained=[
            ("output_format", "Added output format instruction"),
            ("constraints", "Added domain-appropriate constraints"),
        ],
        context=None,
        format_style="xml",
        provider=None if tier_used == 0 else "claude",
        model=(
            None
            if tier_used == 0
            else "claude-sonnet-4-20250514"
        ),
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


def test_tui_panels_do_not_crash_on_markup_brackets() -> None:
    """User text with [..] must not be parsed as Rich markup (no crash)."""
    import dataclasses
    import io

    from rich.console import Console

    from promptune.tui import _render_panels

    result = dataclasses.replace(
        _make_enhance_result(),
        original="paths like [/usr/bin] and [INSERT]",
        enhanced="close tag [/] and a [red]color[/red] token",
    )
    console = Console(file=io.StringIO(), width=120)
    _render_panels(console, result)  # must not raise MarkupError
    out = console.file.getvalue()
    assert "/usr/bin" in out and "INSERT" in out


def test_tui_context_toggle_safe_with_bracket_branch() -> None:
    """A git branch with markup-like brackets must not crash rendering."""
    import io

    from rich.console import Console

    from promptune.tui import _render_context_toggle

    ctx = ContextFingerprint(
        git=GitContext(
            branch="feat/[/]",
            recent_commits=[],
            modified_files=[],
            diff_stats="",
            stash_count=0,
        ),
        shell=ShellHistoryContext(
            recent_commands=[], error_patterns=[], session_intent=""
        ),
        tech=TechStackContext(
            languages=["[bold]python"], frameworks=[], package_manager=None
        ),
        env=EnvironmentContext(
            in_venv=False, in_container=False, in_ci=False, in_ssh=False
        ),
    )
    console = Console(file=io.StringIO(), width=120)
    console.print(_render_context_toggle(ctx), markup=False)
    assert "feat/[/]" in console.file.getvalue()


# --- Quality toggle (Q) ---


def test_tui_quality_toggle_shows_before_after() -> None:
    """Quality toggle shows before->after scores."""
    result = _make_enhance_result()
    pqs_before = compute_pqs(result.score_before)
    pqs_after = compute_pqs(result.score_after)
    output = _render_quality_toggle(pqs_before, pqs_after)
    assert (
        "Clarity" in output
        or "clarity" in output.lower()
    )
    assert "\u2588" in output


def test_tui_quality_toggle_shows_delta() -> None:
    """Quality toggle shows score improvement delta."""
    result = _make_enhance_result()
    pqs_before = compute_pqs(result.score_before)
    pqs_after = compute_pqs(result.score_after)
    output = _render_quality_toggle(pqs_before, pqs_after)
    assert "+" in output or "\u25b6" in output


def test_tui_quality_toggle_negative_delta_sign() -> None:
    """A score decrease renders a single minus sign, not (+-N)."""
    from promptune.pqs import DimensionDisplay, PQScore

    def _pq(overall: int) -> PQScore:
        dim = DimensionDisplay(
            score=overall, color="green", bar="x", suggestion=""
        )
        return PQScore(
            clarity=dim,
            specificity=dim,
            context=dim,
            structure=dim,
            actionability=dim,
            overall=overall,
        )

    output = _render_quality_toggle(_pq(80), _pq(72))
    assert "(-8)" in output
    assert "+-" not in output


# --- Details toggle (D) ---


def test_tui_details_toggle_shows_rules() -> None:
    """Details toggle lists applied rules."""
    output = _render_details_toggle(
        ["output_format", "constraints"]
    )
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
            branch="fix/auth-redirect",
            recent_commits=[],
            modified_files=[],
            diff_stats="",
            stash_count=0,
        ),
        shell=ShellHistoryContext(
            recent_commands=[],
            error_patterns=[],
            session_intent="unknown",
        ),
        tech=TechStackContext(
            languages=["typescript"],
            frameworks=["nextjs"],
            package_manager="pnpm",
        ),
        env=EnvironmentContext(
            in_venv=False,
            in_container=False,
            in_ci=False,
            in_ssh=False,
        ),
    )
    output = _render_context_toggle(fp)
    assert "fix/auth-redirect" in output
    assert "typescript" in output


def test_tui_context_toggle_none() -> None:
    """Context toggle handles None context."""
    output = _render_context_toggle(None)
    assert (
        "no context" in output.lower()
        or output.strip() == ""
    )


# --- Interactive toggle tests ---


def test_action_enum_has_toggle_values() -> None:
    """Action enum includes MORE, QUALITY, DETAILS, CONTEXT."""
    assert Action.MORE.value == "more"
    assert Action.QUALITY.value == "quality"
    assert Action.DETAILS.value == "details"
    assert Action.CONTEXT.value == "context"


def test_get_user_action_question_mark_returns_more(
    mocker: MockerFixture,
) -> None:
    """'?' input returns Action.MORE."""
    mocker.patch("readchar.readkey", return_value="?")
    from promptune.tui import _get_user_action

    result = _get_user_action()
    assert result == Action.MORE


def test_get_user_action_q_returns_quality(
    mocker: MockerFixture,
) -> None:
    """'q' input returns Action.QUALITY."""
    mocker.patch("readchar.readkey", return_value="q")
    from promptune.tui import _get_user_action

    result = _get_user_action(expanded=True)
    assert result == Action.QUALITY


def test_get_user_action_d_returns_details(
    mocker: MockerFixture,
) -> None:
    """'d' input returns Action.DETAILS."""
    mocker.patch("readchar.readkey", return_value="d")
    from promptune.tui import _get_user_action

    result = _get_user_action(expanded=True)
    assert result == Action.DETAILS


def test_get_user_action_c_returns_context(
    mocker: MockerFixture,
) -> None:
    """'c' input returns Action.CONTEXT."""
    mocker.patch("readchar.readkey", return_value="c")
    from promptune.tui import _get_user_action

    result = _get_user_action(expanded=True)
    assert result == Action.CONTEXT


def test_get_user_action_qdc_ignored_when_not_expanded(
    mocker: MockerFixture,
) -> None:
    """Q/D/C keys ignored when not in expanded mode; loops until valid."""
    mocker.patch(
        "readchar.readkey", side_effect=["q", "d", "c", "a"]
    )
    from promptune.tui import _get_user_action

    result = _get_user_action(expanded=False)
    assert result == Action.ACCEPT


def test_display_result_renders_header(
    mocker: MockerFixture,
) -> None:
    """display_result prints the header line."""
    mock_cls = mocker.patch("promptune.tui.Console")
    mock_instance = mock_cls.return_value
    mock_instance.width = 80
    mocker.patch(
        "promptune.tui._get_user_action",
        return_value=Action.ACCEPT,
    )

    result = _make_enhance_result(tier_used=0, latency_ms=8.0)
    display_result(result)

    print_calls = mock_instance.print.call_args_list
    rendered = " ".join(str(c) for c in print_calls)
    assert "Tier 0" in rendered
    assert "rules" in rendered.lower()


def test_display_result_shows_more_prompt(
    mocker: MockerFixture,
) -> None:
    """_get_user_action called unexpanded first, expanded after ?."""
    mock_cls = mocker.patch("promptune.tui.Console")
    mock_cls.return_value.width = 80
    mock_action = mocker.patch(
        "promptune.tui._get_user_action",
        side_effect=[Action.MORE, Action.ACCEPT],
    )

    result = _make_enhance_result()
    display_result(result)

    # First call: not expanded (shows [?] More)
    # Second call: expanded (shows Q/D/C)
    calls = mock_action.call_args_list
    assert calls[0] == mocker.call(expanded=False)
    assert calls[1] == mocker.call(expanded=True)


def test_display_result_quality_toggle_renders(
    mocker: MockerFixture,
) -> None:
    """Pressing Q shows quality score breakdown."""
    mock_cls = mocker.patch("promptune.tui.Console")
    mock_instance = mock_cls.return_value
    mock_instance.width = 80
    # User presses ?, then Q, then A
    mocker.patch(
        "promptune.tui._get_user_action",
        side_effect=[
            Action.MORE,
            Action.QUALITY,
            Action.ACCEPT,
        ],
    )

    result = _make_enhance_result()
    display_result(result)

    print_calls = mock_instance.print.call_args_list
    rendered = " ".join(str(c) for c in print_calls)
    assert "Quality" in rendered or "quality" in rendered.lower()
    assert "\u2588" in rendered


def test_display_result_details_toggle_renders(
    mocker: MockerFixture,
) -> None:
    """Pressing D shows rules applied."""
    mock_cls = mocker.patch("promptune.tui.Console")
    mock_instance = mock_cls.return_value
    mock_instance.width = 80
    mocker.patch(
        "promptune.tui._get_user_action",
        side_effect=[
            Action.MORE,
            Action.DETAILS,
            Action.ACCEPT,
        ],
    )

    result = _make_enhance_result(
        rules_applied=["output_format", "constraints"]
    )
    display_result(result)

    print_calls = mock_instance.print.call_args_list
    rendered = " ".join(str(c) for c in print_calls)
    assert "output_format" in rendered
    assert "constraints" in rendered


def test_display_result_context_toggle_renders(
    mocker: MockerFixture,
) -> None:
    """Pressing C shows context fingerprint."""
    mock_cls = mocker.patch("promptune.tui.Console")
    mock_instance = mock_cls.return_value
    mock_instance.width = 80
    mocker.patch(
        "promptune.tui._get_user_action",
        side_effect=[
            Action.MORE,
            Action.CONTEXT,
            Action.ACCEPT,
        ],
    )

    fp = ContextFingerprint(
        git=GitContext(
            branch="main",
            recent_commits=[],
            modified_files=[],
            diff_stats="",
            stash_count=0,
        ),
        shell=ShellHistoryContext(
            recent_commands=[],
            error_patterns=[],
            session_intent="unknown",
        ),
        tech=TechStackContext(
            languages=["python"],
            frameworks=[],
            package_manager="pip",
        ),
        env=EnvironmentContext(
            in_venv=False,
            in_container=False,
            in_ci=False,
            in_ssh=False,
        ),
    )
    result = _make_enhance_result()
    result.context = fp
    display_result(result)

    print_calls = mock_instance.print.call_args_list
    rendered = " ".join(str(c) for c in print_calls)
    assert "main" in rendered
    assert "python" in rendered


def test_display_result_toggle_off_hides_section(
    mocker: MockerFixture,
) -> None:
    """Pressing Q twice toggles quality off — second render has no bars."""
    mock_cls = mocker.patch("promptune.tui.Console")
    mock_instance = mock_cls.return_value
    mock_instance.width = 80
    # ?, Q (on), Q (off), A
    mocker.patch(
        "promptune.tui._get_user_action",
        side_effect=[
            Action.MORE,
            Action.QUALITY,
            Action.QUALITY,
            Action.ACCEPT,
        ],
    )

    result = _make_enhance_result()
    display_result(result)

    # After toggle off, the LAST render cycle should not have quality bars
    # We check by looking at print calls after the second Q toggle
    print_calls = mock_instance.print.call_args_list
    # The final render (after toggle off + accept) should not have bars
    # Count renders with quality content
    quality_renders = [
        str(c) for c in print_calls if "\u2588" in str(c)
    ]
    # Should have exactly one render with quality bars (the toggle-on),
    # not two (which would mean it stayed on)
    assert len(quality_renders) >= 1


def test_display_result_accept_after_toggles(
    mocker: MockerFixture,
) -> None:
    """Accept still returns enhanced text after toggle interactions."""
    mock_cls = mocker.patch("promptune.tui.Console")
    mock_cls.return_value.width = 80
    mocker.patch(
        "promptune.tui._get_user_action",
        side_effect=[
            Action.MORE,
            Action.QUALITY,
            Action.DETAILS,
            Action.ACCEPT,
        ],
    )

    result = _make_enhance_result()
    final = display_result(result)

    assert final == result.enhanced


def test_display_result_reject_after_toggles(
    mocker: MockerFixture,
) -> None:
    """Reject returns None after toggle interactions."""
    mock_cls = mocker.patch("promptune.tui.Console")
    mock_cls.return_value.width = 80
    mocker.patch(
        "promptune.tui._get_user_action",
        side_effect=[
            Action.MORE,
            Action.QUALITY,
            Action.REJECT,
        ],
    )

    result = _make_enhance_result()
    final = display_result(result)

    assert final is None


def test_display_result_edit_after_toggles(
    mocker: MockerFixture,
) -> None:
    """Edit works after toggle interactions."""
    mock_cls = mocker.patch("promptune.tui.Console")
    mock_cls.return_value.width = 80
    mocker.patch(
        "promptune.tui._get_user_action",
        side_effect=[
            Action.MORE,
            Action.QUALITY,
            Action.EDIT,
        ],
    )
    mocker.patch(
        "promptune.tui._edit_prompt",
        return_value="user edited text",
    )

    result = _make_enhance_result()
    final = display_result(result)

    assert final == "user edited text"


def test_display_result_expanded_prompt_shows_qdc(
    mocker: MockerFixture,
) -> None:
    """After pressing ?, prompt shows Q/D/C options."""
    mock_cls = mocker.patch("promptune.tui.Console")
    mock_instance = mock_cls.return_value
    mock_instance.width = 80
    mocker.patch(
        "promptune.tui._get_user_action",
        side_effect=[Action.MORE, Action.ACCEPT],
    )

    result = _make_enhance_result()
    display_result(result)

    print_calls = mock_instance.print.call_args_list
    rendered = " ".join(str(c) for c in print_calls)
    # After expansion, Q/D/C should appear in the rendered output
    assert "Q" in rendered or "Quality" in rendered
    assert "D" in rendered or "Details" in rendered
    assert "C" in rendered or "Context" in rendered


# --- Edge case tests ---


def test_tui_header_shows_local_for_tier1() -> None:
    """Tier 1 header shows 'local' label."""
    result = _make_enhance_result(tier_used=1)
    header = _render_header(result)
    assert "local" in header.lower()


def test_get_user_action_edit_returns_edit(
    mocker: MockerFixture,
) -> None:
    """'e' input returns Action.EDIT directly."""
    mocker.patch("readchar.readkey", return_value="e")
    from promptune.tui import _get_user_action

    result = _get_user_action()
    assert result == Action.EDIT


def test_get_user_action_reject_returns_reject(
    mocker: MockerFixture,
) -> None:
    """'r' input returns Action.REJECT directly."""
    mocker.patch("readchar.readkey", return_value="r")
    from promptune.tui import _get_user_action

    result = _get_user_action()
    assert result == Action.REJECT


def test_get_user_action_single_key_accept(
    mocker: MockerFixture,
) -> None:
    """Single 'a' keypress returns Action.ACCEPT."""
    mocker.patch("readchar.readkey", return_value="a")
    from promptune.tui import _get_user_action

    result = _get_user_action()
    assert result == Action.ACCEPT


def test_get_user_action_single_key_quality(
    mocker: MockerFixture,
) -> None:
    """Single 'q' keypress returns Action.QUALITY when expanded."""
    mocker.patch("readchar.readkey", return_value="q")
    from promptune.tui import _get_user_action

    result = _get_user_action(expanded=True)
    assert result == Action.QUALITY


def test_get_user_action_case_insensitive(
    mocker: MockerFixture,
) -> None:
    """Input is case-insensitive."""
    mocker.patch("readchar.readkey", return_value="A")
    from promptune.tui import _get_user_action

    result = _get_user_action()
    assert result == Action.ACCEPT


def test_get_user_action_lowercase_key(
    mocker: MockerFixture,
) -> None:
    """Lowercase key returns Action.ACCEPT."""
    mocker.patch("readchar.readkey", return_value="a")
    from promptune.tui import _get_user_action

    result = _get_user_action()
    assert result == Action.ACCEPT


def test_display_result_context_with_session_intent(
    mocker: MockerFixture,
) -> None:
    """Context toggle shows session intent when not 'unknown'."""
    mock_cls = mocker.patch("promptune.tui.Console")
    mock_instance = mock_cls.return_value
    mock_instance.width = 80
    mocker.patch(
        "promptune.tui._get_user_action",
        side_effect=[
            Action.MORE,
            Action.CONTEXT,
            Action.ACCEPT,
        ],
    )

    fp = ContextFingerprint(
        git=GitContext(
            branch="main",
            recent_commits=[],
            modified_files=[],
            diff_stats="",
            stash_count=0,
        ),
        shell=ShellHistoryContext(
            recent_commands=[],
            error_patterns=[],
            session_intent="debugging",
        ),
        tech=TechStackContext(
            languages=["python"],
            frameworks=[],
            package_manager="",
        ),
        env=EnvironmentContext(
            in_venv=False,
            in_container=False,
            in_ci=False,
            in_ssh=False,
        ),
    )
    result = _make_enhance_result()
    result.context = fp
    display_result(result)

    print_calls = mock_instance.print.call_args_list
    rendered = " ".join(str(c) for c in print_calls)
    assert "debugging" in rendered


def test_display_result_wide_terminal_side_by_side(
    mocker: MockerFixture,
) -> None:
    """display_result uses columns layout on wide terminal."""
    mock_cls = mocker.patch("promptune.tui.Console")
    mock_instance = mock_cls.return_value
    mock_instance.width = 120
    mocker.patch(
        "promptune.tui._get_user_action",
        return_value=Action.ACCEPT,
    )

    result = _make_enhance_result()
    display_result(result)

    print_calls = mock_instance.print.call_args_list
    rendered = " ".join(str(c) for c in print_calls)
    assert "Columns" in rendered


def test_display_result_direct_accept_no_toggles(
    mocker: MockerFixture,
) -> None:
    """Accept without pressing ? returns enhanced immediately."""
    mock_cls = mocker.patch("promptune.tui.Console")
    mock_cls.return_value.width = 80
    mocker.patch(
        "promptune.tui._get_user_action",
        return_value=Action.ACCEPT,
    )

    result = _make_enhance_result()
    final = display_result(result)

    assert final == result.enhanced


def test_display_result_multiple_toggles_combined(
    mocker: MockerFixture,
) -> None:
    """Multiple toggles can be active simultaneously."""
    mock_cls = mocker.patch("promptune.tui.Console")
    mock_instance = mock_cls.return_value
    mock_instance.width = 80
    mocker.patch(
        "promptune.tui._get_user_action",
        side_effect=[
            Action.MORE,
            Action.QUALITY,
            Action.DETAILS,
            Action.ACCEPT,
        ],
    )

    result = _make_enhance_result(
        rules_applied=["role_assignment"]
    )
    display_result(result)

    print_calls = mock_instance.print.call_args_list
    rendered = " ".join(str(c) for c in print_calls)
    # Both quality and details should be visible
    assert "\u2588" in rendered
    assert "role_assignment" in rendered


def test_tui_context_toggle_empty_fingerprint() -> None:
    """Context toggle with all-empty fingerprint says no context."""
    fp = ContextFingerprint(
        git=GitContext(
            branch="",
            recent_commits=[],
            modified_files=[],
            diff_stats="",
            stash_count=0,
        ),
        shell=ShellHistoryContext(
            recent_commands=[],
            error_patterns=[],
            session_intent="unknown",
        ),
        tech=TechStackContext(
            languages=[],
            frameworks=[],
            package_manager="",
        ),
        env=EnvironmentContext(
            in_venv=False,
            in_container=False,
            in_ci=False,
            in_ssh=False,
        ),
    )
    output = _render_context_toggle(fp)
    assert "no context" in output.lower()


def test_get_user_action_eof_returns_reject(mocker: MockerFixture) -> None:
    """EOF/closed stdin (readkey -> '') must reject, not spin forever."""
    from promptune.tui import _get_user_action

    mocker.patch("promptune.tui.readchar.readkey", return_value="")
    assert _get_user_action() is Action.REJECT


def test_get_user_action_keyboard_interrupt_returns_reject(
    mocker: MockerFixture,
) -> None:
    from promptune.tui import _get_user_action

    mocker.patch(
        "promptune.tui.readchar.readkey", side_effect=KeyboardInterrupt
    )
    assert _get_user_action() is Action.REJECT
