"""Preference learning tests."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from promptune.history import HistoryEntry, HistoryStore
from promptune.preferences import (
    analyse_edit_patterns,
    analyse_rule_preferences,
)


@pytest.fixture
def store(tmp_path) -> Iterator[HistoryStore]:
    """Yield a HistoryStore that closes after the test."""
    s = HistoryStore(db_path=tmp_path / "h.db")
    yield s
    s.close()


def _make_entry(
    decision: str = "accept",
    rules_applied: list[str] | None = None,
    edit_result: str | None = None,
    enhanced: str = "Enhanced prompt",
    project_root: str = "/home/user/project",
) -> HistoryEntry:
    return HistoryEntry(
        original="fix the bug",
        enhanced=enhanced,
        decision=decision,
        edit_result=edit_result,
        tier_used=0,
        provider=None,
        format_style="xml",
        model=None,
        score_before=11,
        score_after=81,
        latency_ms=8.0,
        rules_applied=rules_applied or [],
        context_json=None,
        project_root=project_root,
    )


class TestRulePreferences:
    def test_disliked_rule_detected(self, store: HistoryStore) -> None:
        for _ in range(4):
            store.record(_make_entry(
                decision="reject",
                rules_applied=["role_assignment"],
            ))
        store.record(_make_entry(
            decision="accept",
            rules_applied=["role_assignment"],
        ))

        prefs = analyse_rule_preferences(store, min_samples=5)

        assert len(prefs) == 1
        assert prefs[0].rule_name == "role_assignment"
        assert prefs[0].action == "skip"
        assert prefs[0].confidence > 0.6

    def test_liked_rule_detected(self, store: HistoryStore) -> None:
        for _ in range(4):
            store.record(_make_entry(
                decision="accept",
                rules_applied=["output_format"],
            ))
        store.record(_make_entry(
            decision="reject",
            rules_applied=["output_format"],
        ))

        prefs = analyse_rule_preferences(store, min_samples=5)

        assert len(prefs) == 1
        assert prefs[0].rule_name == "output_format"
        assert prefs[0].action == "keep"

    def test_insufficient_samples_returns_empty(self, store: HistoryStore) -> None:
        store.record(_make_entry(decision="reject", rules_applied=["role_assignment"]))

        prefs = analyse_rule_preferences(store, min_samples=5)

        assert prefs == []

    def test_conflicting_signals_returns_empty(self, store: HistoryStore) -> None:
        for _ in range(5):
            store.record(_make_entry(decision="accept", rules_applied=["constraints"]))
        for _ in range(5):
            store.record(_make_entry(decision="reject", rules_applied=["constraints"]))

        prefs = analyse_rule_preferences(store, min_samples=5)

        assert prefs == []

    def test_empty_history_returns_empty(self, store: HistoryStore) -> None:
        prefs = analyse_rule_preferences(store, min_samples=5)
        assert prefs == []


class TestEditPatterns:
    def test_role_removal_detected(self, store: HistoryStore) -> None:
        for _ in range(5):
            store.record(_make_entry(
                decision="edit",
                enhanced="You are an experienced developer. Fix the auth bug in login",
                edit_result="Fix the auth bug in login",
            ))

        patterns = analyse_edit_patterns(store, min_samples=5)

        assert len(patterns) >= 1
        assert any(p.pattern_type == "removes_role" for p in patterns)

    def test_role_removal_detected_hyphenated_role(
        self, store: HistoryStore
    ) -> None:
        for _ in range(5):
            store.record(_make_entry(
                decision="edit",
                enhanced="You are a back-end developer. Fix the auth bug",
                edit_result="Fix the auth bug",
            ))

        patterns = analyse_edit_patterns(store, min_samples=5)

        assert any(p.pattern_type == "removes_role" for p in patterns)

    def test_format_removal_detected(self, store: HistoryStore) -> None:
        for _ in range(5):
            store.record(_make_entry(
                decision="edit",
                enhanced="Fix the bug\n\nRespond with code and brief explanation.",
                edit_result="Fix the bug",
            ))

        patterns = analyse_edit_patterns(store, min_samples=5)

        assert len(patterns) >= 1
        assert any(p.pattern_type == "removes_format" for p in patterns)

    def test_role_removal_detected_when_role_only_in_some_edits(
        self, store: HistoryStore
    ) -> None:
        """Removal rate is over edits that HAD a role, not all edits."""
        # 4 edits that contained a role — user removed it every time.
        for _ in range(4):
            store.record(_make_entry(
                decision="edit",
                enhanced="You are an expert developer. Fix the auth bug",
                edit_result="Fix the auth bug",
            ))
        # 6 unrelated edits with no role — must not dilute the role rate.
        for _ in range(6):
            store.record(_make_entry(
                decision="edit",
                enhanced="Fix the parser bug",
                edit_result="Fix the parser bug now",
            ))

        patterns = analyse_edit_patterns(store, min_samples=5)

        assert any(p.pattern_type == "removes_role" for p in patterns)

    def test_insufficient_edit_samples(self, store: HistoryStore) -> None:
        store.record(_make_entry(
            decision="edit",
            enhanced="You are a dev. Fix bug",
            edit_result="Fix bug",
        ))

        patterns = analyse_edit_patterns(store, min_samples=5)

        assert patterns == []

    def test_no_edits_returns_empty(self, store: HistoryStore) -> None:
        store.record(_make_entry(decision="accept"))

        patterns = analyse_edit_patterns(store, min_samples=5)

        assert patterns == []
