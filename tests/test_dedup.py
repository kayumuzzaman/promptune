"""Semantic deduplication tests."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from promptune.dedup import DedupHit, cosine_similarity, dedup_check, tokenize
from promptune.history import HistoryEntry, HistoryStore


@pytest.fixture
def store(tmp_path) -> Iterator[HistoryStore]:
    """Yield a HistoryStore that closes after the test."""
    s = HistoryStore(db_path=tmp_path / "h.db")
    yield s
    s.close()


class TestTokenize:
    def test_basic_tokenization(self) -> None:
        tokens = tokenize("fix the bug in login")
        assert tokens == ["fix", "the", "bug", "in", "login"]

    def test_lowercases(self) -> None:
        tokens = tokenize("Fix The Bug")
        assert tokens == ["fix", "the", "bug"]

    def test_strips_punctuation(self) -> None:
        tokens = tokenize("fix the bug, please!")
        assert tokens == ["fix", "the", "bug", "please"]

    def test_empty_string(self) -> None:
        assert tokenize("") == []

    def test_whitespace_only(self) -> None:
        assert tokenize("   ") == []


class TestCosineSimilarity:
    def test_identical_strings(self) -> None:
        score = cosine_similarity("fix the auth bug", "fix the auth bug")
        assert score == pytest.approx(1.0)

    def test_completely_different(self) -> None:
        score = cosine_similarity("fix the auth bug", "deploy kubernetes cluster")
        assert score < 0.2

    def test_similar_strings(self) -> None:
        score = cosine_similarity(
            "fix the authentication bug in login",
            "fix the auth bug in the login page",
        )
        assert score > 0.5

    def test_empty_string_returns_zero(self) -> None:
        assert cosine_similarity("", "fix bug") == 0.0
        assert cosine_similarity("fix bug", "") == 0.0

    def test_symmetry(self) -> None:
        a = "build a REST API with Flask"
        b = "create a Flask REST API"
        assert cosine_similarity(a, b) == pytest.approx(
            cosine_similarity(b, a)
        )


def _make_entry(
    original: str = "fix the bug",
    enhanced: str = "Diagnose and fix the authentication bug",
    decision: str = "accept",
    edit_result: str | None = None,
    project_root: str = "/home/user/project",
    rules_applied: list[str] | None = None,
    provider: str | None = None,
    format_style: str = "xml",
    model: str | None = None,
    tier_used: int = 0,
) -> HistoryEntry:
    return HistoryEntry(
        original=original,
        enhanced=enhanced,
        decision=decision,
        edit_result=edit_result,
        tier_used=tier_used,
        provider=provider,
        format_style=format_style,
        model=model,
        score_before=11,
        score_after=81,
        latency_ms=8.0,
        rules_applied=rules_applied or ["output_format"],
        context_json=None,
        project_root=project_root,
    )


class TestDedupCheck:
    def test_hit_returns_cached_enhanced(self, store: HistoryStore) -> None:
        store.record(_make_entry(
            original="fix the auth bug",
            enhanced="Diagnose and fix the authentication bug",
        ))

        result = dedup_check(
            prompt="fix the auth bug",
            project_root="/home/user/project",
            store=store,
            threshold=0.85,
            window=50,
        )

        assert result is not None
        assert isinstance(result, DedupHit)
        assert result.enhanced == "Diagnose and fix the authentication bug"

    def test_tier0_result_bypasses_provider_filter(
        self, store: HistoryStore
    ) -> None:
        """A tier-0 result (provider/model None) is provider-independent, so it
        honours any request regardless of the provider/model filters."""
        store.record(_make_entry(  # provider/model None => tier-0 origin
            original="fix the auth bug",
            enhanced="Diagnose and fix the authentication bug",
            provider=None,
        ))

        for prov in ("openai", "claude", None):
            hit = dedup_check(
                prompt="fix the auth bug",
                project_root="/home/user/project",
                store=store,
                threshold=0.85,
                provider=prov,
            )
            assert hit is not None, f"tier-0 entry should match provider={prov}"

    def test_provider_none_is_not_universal_for_ai_tiers(
        self, store: HistoryStore
    ) -> None:
        """Only true tier-0 history is provider-independent."""
        store.record(_make_entry(
            original="fix the auth bug",
            enhanced="AI result with missing provider metadata",
            provider=None,
            model=None,
            tier_used=2,
        ))

        result = dedup_check(
            prompt="fix the auth bug",
            project_root="/home/user/project",
            store=store,
            threshold=0.85,
            provider="claude",
        )

        assert result is None

    def test_miss_returns_none(self, store: HistoryStore) -> None:
        store.record(_make_entry(
            original="fix the auth bug",
            enhanced="Diagnose auth bug",
        ))

        result = dedup_check(
            prompt="deploy kubernetes cluster to production",
            project_root="/home/user/project",
            store=store,
            threshold=0.85,
            window=50,
        )

        assert result is None

    def test_rejected_entries_excluded(self, store: HistoryStore) -> None:
        store.record(_make_entry(
            original="fix the auth bug",
            enhanced="Bad enhancement",
            decision="reject",
        ))

        result = dedup_check(
            prompt="fix the auth bug",
            project_root="/home/user/project",
            store=store,
            threshold=0.85,
            window=50,
        )

        assert result is None

    def test_edited_entry_uses_edit_result(self, store: HistoryStore) -> None:
        store.record(_make_entry(
            original="fix the auth bug",
            enhanced="AI enhanced version",
            decision="edit",
            edit_result="User's preferred version",
        ))

        result = dedup_check(
            prompt="fix the auth bug",
            project_root="/home/user/project",
            store=store,
            threshold=0.85,
            window=50,
        )

        assert result is not None
        assert result.enhanced == "User's preferred version"

    def test_different_project_excluded(self, store: HistoryStore) -> None:
        store.record(_make_entry(
            original="fix the auth bug",
            enhanced="Enhanced",
            project_root="/home/user/other-project",
        ))

        result = dedup_check(
            prompt="fix the auth bug",
            project_root="/home/user/project",
            store=store,
            threshold=0.85,
            window=50,
        )

        assert result is None

    def test_short_prompt_skipped(self, store: HistoryStore) -> None:
        store.record(_make_entry(original="hi", enhanced="Hello"))

        result = dedup_check(
            prompt="hi",
            project_root="/home/user/project",
            store=store,
            threshold=0.85,
            window=50,
        )

        assert result is None

    def test_empty_history_returns_none(self, store: HistoryStore) -> None:
        result = dedup_check(
            prompt="fix the auth bug",
            project_root="/home/user/project",
            store=store,
            threshold=0.85,
            window=50,
        )

        assert result is None


class TestDedupTieBreak:
    def test_edit_result_preferred_over_accept_on_tie(
        self, store: HistoryStore
    ) -> None:
        """On equal similarity, a user-edited result wins over a plain accept."""
        # Record edit first, then accept — accept is newer so it is iterated
        # first by recent(); without the tie-break it would win.
        store.record(_make_entry(
            original="fix the auth bug",
            enhanced="generic enhanced version",
            decision="edit",
            edit_result="user-edited authentication fix",
        ))
        store.record(_make_entry(
            original="fix the auth bug",
            enhanced="generic enhanced version",
            decision="accept",
        ))

        result = dedup_check(
            prompt="fix the auth bug",
            project_root="/home/user/project",
            store=store,
            threshold=0.85,
            window=50,
        )

        assert result is not None
        assert result.enhanced == "user-edited authentication fix"
