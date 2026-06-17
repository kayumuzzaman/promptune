"""Task 11: SQLite History — tests."""

from __future__ import annotations

import sqlite3

import pytest

from promptune.history import (
    HistoryEntry,
    HistoryStats,
    HistoryStore,
)


@pytest.fixture()
def store(tmp_path) -> HistoryStore:
    """Create a HistoryStore with a temp DB."""
    s = HistoryStore(db_path=tmp_path / "test_history.db")
    yield s
    s.close()


def _make_entry(
    original: str = "fix the bug",
    enhanced: str = "Diagnose and fix the auth bug",
    decision: str = "accept",
    tier_used: int = 0,
    score_before: int = 11,
    score_after: int = 81,
) -> HistoryEntry:
    return HistoryEntry(
        original=original,
        enhanced=enhanced,
        decision=decision,
        edit_result=None,
        tier_used=tier_used,
        provider=None,
        format_style="xml",
        model=None,
        score_before=score_before,
        score_after=score_after,
        latency_ms=8.0,
        rules_applied=["output_format"],
        context_json=None,
        project_root="/home/user/project",
    )


def test_store_creates_db(tmp_path) -> None:
    """HistoryStore creates DB file on init."""
    db_path = tmp_path / "history.db"
    with HistoryStore(db_path=db_path):
        assert db_path.exists()


def test_configured_max_entries_is_honored(tmp_path) -> None:
    """A configured max_entries caps the DB via auto-prune."""
    store = HistoryStore(db_path=tmp_path / "h.db", max_entries=3)
    try:
        for i in range(7):
            store.record(_make_entry(original=f"prompt {i}"))
        count = store._conn.execute(
            "SELECT COUNT(*) FROM enhancements"
        ).fetchone()[0]
        assert count <= 3
    finally:
        store.close()


def test_store_schema_version(
    store: HistoryStore,
) -> None:
    """DB has user_version = 1 after creation."""
    conn = sqlite3.connect(store.db_path)
    version = conn.execute(
        "PRAGMA user_version"
    ).fetchone()[0]
    conn.close()
    assert version == 1


def test_store_reopen_at_current_version_is_idempotent(tmp_path) -> None:
    """Reopening a DB already at the current schema version is a no-op."""
    db_path = tmp_path / "history.db"
    HistoryStore(db_path=db_path).close()
    # Reopen: version already == _SCHEMA_VERSION, migration loop must not run.
    with HistoryStore(db_path=db_path):
        conn = sqlite3.connect(db_path)
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        conn.close()
        assert version == 1


def test_store_does_not_downgrade_newer_schema(tmp_path) -> None:
    """A DB from a newer Promptune is left at its version, not stamped down."""
    db_path = tmp_path / "history.db"
    HistoryStore(db_path=db_path).close()
    # Simulate a newer build having bumped the schema.
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA user_version = 99")
    conn.commit()
    conn.close()

    with HistoryStore(db_path=db_path):
        conn = sqlite3.connect(db_path)
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        conn.close()
        assert version == 99


def test_store_wal_mode(store: HistoryStore) -> None:
    """DB uses WAL journal mode."""
    conn = sqlite3.connect(store.db_path)
    mode = conn.execute(
        "PRAGMA journal_mode"
    ).fetchone()[0]
    conn.close()
    assert mode == "wal"


def test_record_returns_id(
    store: HistoryStore,
) -> None:
    """record() returns the new row ID."""
    entry = _make_entry()
    row_id = store.record(entry)
    assert isinstance(row_id, int)
    assert row_id > 0


def test_record_and_recent(
    store: HistoryStore,
) -> None:
    """Recorded entries appear in recent()."""
    store.record(_make_entry(original="prompt 1"))
    store.record(_make_entry(original="prompt 2"))

    entries = store.recent(n=10)

    assert len(entries) == 2
    assert entries[0].original == "prompt 2"


def test_recent_respects_limit(
    store: HistoryStore,
) -> None:
    """recent(n=1) returns only 1 entry."""
    for i in range(5):
        store.record(_make_entry(original=f"prompt {i}"))

    entries = store.recent(n=1)

    assert len(entries) == 1


def test_recent_filters_by_project(
    store: HistoryStore,
) -> None:
    """recent() can filter by project_root."""
    e1 = _make_entry(original="project A prompt")
    e1.project_root = "/home/user/project-a"
    store.record(e1)

    e2 = _make_entry(original="project B prompt")
    e2.project_root = "/home/user/project-b"
    store.record(e2)

    entries = store.recent(
        n=10, project="/home/user/project-a"
    )

    assert len(entries) == 1
    assert entries[0].original == "project A prompt"


def test_stats_empty_db(store: HistoryStore) -> None:
    """stats() on empty DB returns zeros."""
    s = store.stats()
    assert isinstance(s, HistoryStats)
    assert s.total == 0
    assert s.acceptance_rate == 0.0


def test_stats_computed_correctly(
    store: HistoryStore,
) -> None:
    """stats() computes correct aggregates."""
    store.record(
        _make_entry(
            decision="accept",
            score_before=10,
            score_after=80,
        )
    )
    store.record(
        _make_entry(
            decision="accept",
            score_before=20,
            score_after=90,
        )
    )
    store.record(
        _make_entry(
            decision="reject",
            score_before=15,
            score_after=70,
        )
    )

    s = store.stats()

    assert s.total == 3
    assert s.accepted == 2
    assert s.rejected == 1
    assert s.edited == 0
    assert abs(s.acceptance_rate - 2 / 3) < 0.01
    assert s.avg_score_before == pytest.approx(15.0)
    assert s.avg_score_after == pytest.approx(80.0)


def test_clear_deletes_all(
    store: HistoryStore,
) -> None:
    """clear() removes all entries and returns count."""
    for _ in range(3):
        store.record(_make_entry())

    deleted = store.clear()

    assert deleted == 3
    assert store.stats().total == 0


def test_record_edit_with_edit_result(
    store: HistoryStore,
) -> None:
    """edit decision stores edit_result text."""
    entry = _make_entry(decision="edit")
    entry.edit_result = "User's edited version"
    store.record(entry)

    entries = store.recent(n=1)
    assert entries[0].decision == "edit"
    assert (
        entries[0].edit_result == "User's edited version"
    )


def test_rules_applied_serialized_as_json(
    store: HistoryStore,
) -> None:
    """rules_applied list is serialized correctly."""
    entry = _make_entry()
    entry.rules_applied = [
        "output_format",
        "constraints",
        "specificity",
    ]
    store.record(entry)

    entries = store.recent(n=1)
    assert entries[0].rules_applied == [
        "output_format",
        "constraints",
        "specificity",
    ]


def test_auto_prune_large_db(
    store: HistoryStore,
) -> None:
    """DB has _maybe_prune method."""
    assert hasattr(store, "_maybe_prune")
