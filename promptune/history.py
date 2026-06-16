"""SQLite history store — persistent enhancement log."""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path

_SCHEMA_VERSION = 1

_CREATE_SQL = """\
CREATE TABLE IF NOT EXISTS enhancements (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    original        TEXT NOT NULL,
    enhanced        TEXT NOT NULL,
    decision        TEXT CHECK(
        decision IN ('accept', 'reject', 'edit')
    ) NOT NULL,
    edit_result     TEXT,
    tier_used       INTEGER NOT NULL,
    provider        TEXT,
    format_style    TEXT,
    model           TEXT,
    score_before    INTEGER NOT NULL,
    score_after     INTEGER NOT NULL,
    latency_ms      REAL NOT NULL,
    rules_applied   TEXT,
    context_json    TEXT,
    project_root    TEXT,
    created_at      INTEGER NOT NULL DEFAULT (
        strftime('%s', 'now')
    )
);

CREATE INDEX IF NOT EXISTS idx_enhancements_created_at
    ON enhancements(created_at);
CREATE INDEX IF NOT EXISTS idx_enhancements_project
    ON enhancements(project_root);
"""

# Map of from-version -> SQL to migrate to from-version + 1.
# Add an entry here whenever _SCHEMA_VERSION is bumped.
_MIGRATIONS: dict[int, str] = {}

_MAX_ENTRIES = 10000


@dataclass
class HistoryEntry:
    """Single enhancement record."""

    original: str
    enhanced: str
    decision: str
    edit_result: str | None
    tier_used: int
    provider: str | None
    format_style: str | None
    model: str | None
    score_before: int
    score_after: int
    latency_ms: float
    rules_applied: list[str] | None
    context_json: str | None
    project_root: str | None


@dataclass
class HistoryStats:
    """Aggregate statistics."""

    total: int
    accepted: int
    rejected: int
    edited: int
    acceptance_rate: float
    avg_score_before: float
    avg_score_after: float
    avg_improvement: float
    tier_distribution: dict[int, int]


class HistoryStore:
    """SQLite-backed enhancement history."""

    def __init__(
        self, db_path: Path | None = None
    ) -> None:
        if db_path is None:
            db_path = (
                Path.home()
                / ".local"
                / "share"
                / "promptune"
                / "history.db"
            )

        db_path = Path(db_path).expanduser()
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)

        self._lock = threading.RLock()
        self._conn_inner: sqlite3.Connection | None = (
            sqlite3.connect(str(db_path), check_same_thread=False)
        )
        self._conn_inner.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    @property
    def _conn(self) -> sqlite3.Connection:
        """Return connection, raising if closed."""
        if self._conn_inner is None:
            msg = "HistoryStore is closed"
            raise RuntimeError(msg)
        return self._conn_inner

    def close(self) -> None:
        """Close the database connection (idempotent)."""
        if self._conn_inner is not None:
            self._conn_inner.close()
            self._conn_inner = None

    def __enter__(self) -> HistoryStore:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _init_schema(self) -> None:
        """Create tables on a fresh DB, then run any pending migrations."""
        version = self._conn.execute(
            "PRAGMA user_version"
        ).fetchone()[0]
        if version == 0:
            self._conn.executescript(_CREATE_SQL)
            version = _SCHEMA_VERSION
        while version < _SCHEMA_VERSION:
            self._conn.executescript(_MIGRATIONS[version])
            version += 1
        self._conn.execute(
            f"PRAGMA user_version = {_SCHEMA_VERSION}"
        )
        self._conn.commit()

    def record(self, entry: HistoryEntry) -> int:
        """Insert an enhancement record."""
        rules_json = (
            json.dumps(entry.rules_applied)
            if entry.rules_applied
            else None
        )

        with self._lock:
            cursor = self._conn.execute(
                """INSERT INTO enhancements
                   (original, enhanced, decision,
                    edit_result, tier_used, provider,
                    format_style, model, score_before,
                    score_after, latency_ms,
                    rules_applied, context_json,
                    project_root)
                   VALUES (
                       ?, ?, ?, ?, ?, ?, ?,
                       ?, ?, ?, ?, ?, ?, ?
                   )""",
                (
                    entry.original,
                    entry.enhanced,
                    entry.decision,
                    entry.edit_result,
                    entry.tier_used,
                    entry.provider,
                    entry.format_style,
                    entry.model,
                    entry.score_before,
                    entry.score_after,
                    entry.latency_ms,
                    rules_json,
                    entry.context_json,
                    entry.project_root,
                ),
            )
            self._conn.commit()
            self._maybe_prune()
            row_id: int = cursor.lastrowid or 0
            return row_id

    def recent(
        self,
        n: int = 20,
        project: str | None = None,
    ) -> list[HistoryEntry]:
        """Get most recent entries."""
        n = max(n, 0)
        with self._lock:
            if project:
                rows = self._conn.execute(
                    """SELECT original, enhanced,
                              decision, edit_result,
                              tier_used, provider,
                              format_style, model,
                              score_before, score_after,
                              latency_ms, rules_applied,
                              context_json, project_root
                       FROM enhancements
                       WHERE project_root = ?
                       ORDER BY created_at DESC, id DESC
                       LIMIT ?""",
                    (project, n),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    """SELECT original, enhanced,
                              decision, edit_result,
                              tier_used, provider,
                              format_style, model,
                              score_before, score_after,
                              latency_ms, rules_applied,
                              context_json, project_root
                       FROM enhancements
                       ORDER BY created_at DESC, id DESC
                       LIMIT ?""",
                    (n,),
                ).fetchall()

        return [self._row_to_entry(row) for row in rows]

    def stats(self) -> HistoryStats:
        """Compute aggregate statistics."""
        with self._lock:
            row = self._conn.execute(
                """SELECT COUNT(*),
                          SUM(CASE WHEN decision='accept'
                              THEN 1 ELSE 0 END),
                          SUM(CASE WHEN decision='reject'
                              THEN 1 ELSE 0 END),
                          SUM(CASE WHEN decision='edit'
                              THEN 1 ELSE 0 END),
                          AVG(score_before),
                          AVG(score_after)
                   FROM enhancements"""
            ).fetchone()

            tier_rows = self._conn.execute(
                "SELECT tier_used, COUNT(*) "
                "FROM enhancements GROUP BY tier_used"
            ).fetchall()

        total = row[0] or 0
        accepted = row[1] or 0
        rejected = row[2] or 0
        edited = row[3] or 0
        avg_before = row[4] or 0.0
        avg_after = row[5] or 0.0
        tier_dist = {r[0]: r[1] for r in tier_rows}

        return HistoryStats(
            total=total,
            accepted=accepted,
            rejected=rejected,
            edited=edited,
            acceptance_rate=(
                accepted / total if total > 0 else 0.0
            ),
            avg_score_before=avg_before,
            avg_score_after=avg_after,
            avg_improvement=avg_after - avg_before,
            tier_distribution=tier_dist,
        )

    def clear(self) -> int:
        """Delete all entries. Returns count deleted."""
        with self._lock:
            count: int = self._conn.execute(
                "SELECT COUNT(*) FROM enhancements"
            ).fetchone()[0]
            self._conn.execute("DELETE FROM enhancements")
            self._conn.commit()
            return count

    def _maybe_prune(self) -> None:
        """Auto-prune if over MAX_ENTRIES."""
        count = self._conn.execute(
            "SELECT COUNT(*) FROM enhancements"
        ).fetchone()[0]
        if count > _MAX_ENTRIES:
            self._conn.execute(
                """DELETE FROM enhancements
                   WHERE id NOT IN (
                       SELECT id FROM enhancements
                       ORDER BY created_at DESC, id DESC
                       LIMIT ?
                   )""",
                (_MAX_ENTRIES,),
            )
            self._conn.commit()

    @staticmethod
    def _row_to_entry(row: tuple) -> HistoryEntry:
        """Convert a DB row to HistoryEntry."""
        rules = (
            json.loads(row[11]) if row[11] else None
        )
        return HistoryEntry(
            original=row[0],
            enhanced=row[1],
            decision=row[2],
            edit_result=row[3],
            tier_used=row[4],
            provider=row[5],
            format_style=row[6],
            model=row[7],
            score_before=row[8],
            score_after=row[9],
            latency_ms=row[10],
            rules_applied=rules,
            context_json=row[12],
            project_root=row[13],
        )
