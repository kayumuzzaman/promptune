# Spec: Code Quality Fixes

**Date:** 2026-03-29
**Status:** Ready for implementation
**Plan:** `docs/superpowers/plans/2026-03-29-code-quality-fixes.md`

---

## Why This Matters

These are not cosmetic issues. Each one has direct impact on CI health, developer experience, and production correctness:

1. **Ruff lint errors block CI.** The CI pipeline runs `ruff check .` and fails on any error. All 33 current errors are in test files — while production code is clean, a failing lint gate means every PR is red and developers learn to ignore CI. That habit carries over and eventually a real production bug is also ignored.

2. **SQLite ResourceWarnings mask real test failures.** Python's `ResourceWarning` floods test output. When real failures appear between the warnings, they are easy to miss. Unclosed database connections also risk data corruption in environments where the GC timing differs (PyPy, Python 3.14 where GC changed), and signal that the production `HistoryStore` class lacks proper lifecycle management.

---

## Scope

### 1. Ruff Lint Fixes

**Files affected:**
- `tests/test_daemon/test_daemon.py`
- `tests/test_daemon/test_platform/test_init.py`
- `tests/test_daemon/test_platform/test_linux_service.py`
- `tests/test_daemon/test_platform/test_linux_wayland.py`
- `tests/test_daemon/test_platform/test_linux_x11.py`
- `tests/test_daemon/test_platform/test_macos.py`

**Error categories:**
- `I001` — Import block unsorted (auto-fix)
- `F401` — Unused imports (`pytest`, `sys`) (auto-fix)
- `E501` — Lines > 88 characters (manual, 22 instances)

**E501 pattern — all are long `patch.dict` strings like:**
```python
# BEFORE (94 chars):
with patch.dict("sys.modules", {"promptune.daemon.platform.linux_x11": mock_x11}):

# AFTER (wrap with variable):
modules = {"promptune.daemon.platform.linux_x11": mock_x11}
with patch.dict("sys.modules", modules):
```

**Constraint:** Do not change test logic — only formatting. All 640 tests must still pass after.

**Corner cases:**
- `patch.dict` wraps that are nested inside `with (...)` multi-context managers — preserve the multi-context manager syntax, just extract the dict
- `patch(...)` strings with long paths that are arguments to `side_effect=` — these can be broken with a line continuation inside the string if needed, or extracted to a variable before the `with`
- After running `--fix`, verify manually that I001 fixes didn't reorder imports in a way that breaks relative import semantics (unlikely but check)

---

### 2. SQLite Unclosed Connection ResourceWarnings

**Root cause:** `HistoryStore` opens a `sqlite3.Connection` in `__init__` and never exposes `close()`. Tests create `HistoryStore` instances and let them GC. In Python 3.14 the GC timing changed, so connections outlive test teardown and emit `ResourceWarning`.

**Affected test files:**
- `tests/test_history.py` — 10 instances of unclosed connection warning
- Any other test file that constructs `HistoryStore` directly

**Production code change required:** `promptune/history.py`

**Design requirements:**

```python
class HistoryStore:
    # Add context manager support
    def __enter__(self) -> "HistoryStore":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        """Explicitly close the SQLite connection."""
        if hasattr(self, "_conn") and self._conn:
            self._conn.close()
            self._conn = None  # prevent double-close
```

**Test fixture change required:** `tests/conftest.py` and `tests/test_history.py`
- Any fixture that returns a `HistoryStore` must either use `with HistoryStore(...) as store:` or call `store.close()` in teardown
- Prefer `yield` fixture with explicit `store.close()` in teardown:

```python
@pytest.fixture
def history_store(tmp_path):
    store = HistoryStore(tmp_path / "test.db")
    yield store
    store.close()
```

**Corner cases:**
- `close()` called when `_conn` is already `None` (double-close) — must be idempotent
- `close()` called when `__init__` failed before creating `_conn` — must check `hasattr`
- Tests that call `HistoryStore` directly (not via fixture) — audit `tests/test_history.py` for all instantiation sites
- Any code path that calls `HistoryStore` methods after `close()` — should raise a clear error, not silently corrupt
- The `HistoryStore` is used in `engine.py` and `cli.py` — those callers manage the lifecycle via application context, not per-call. Ensure `close()` being available doesn't break existing usage patterns.
- Thread safety: `sqlite3.Connection` is not thread-safe by default. The existing code doesn't use threads for history, but document the assumption.

---

## Acceptance Criteria

- [ ] `ruff check .` exits 0 (no errors)
- [ ] `pytest -q` exits 0 with 640+ tests passing
- [ ] No `ResourceWarning: unclosed database` in test output
- [ ] `mypy promptune/` still passes (no new type errors from `close()` changes)
- [ ] Coverage does not decrease (≥ 85% overall)
- [ ] `HistoryStore.close()` is idempotent (calling twice does not raise)
- [ ] Context manager usage `with HistoryStore(...) as s:` works correctly

---

## Out of Scope

- Increasing coverage (separate spec: `2026-03-29-coverage-improvement.md`)
- Fixing mypy (currently clean, no changes needed)
- Adding `__aenter__`/`__aexit__` (no async usage)
