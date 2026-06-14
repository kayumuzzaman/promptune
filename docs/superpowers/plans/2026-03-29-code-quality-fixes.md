# Plan: Code Quality Fixes

**Date:** 2026-03-29
**Status:** ✅ Completed 2026-04-17
**Spec:** `docs/superpowers/specs/2026-03-29-code-quality-fixes.md`
**Estimated effort:** ~1.5 hours

---

## Post-completion Notes

All 9 steps completed. Verified outcomes:
- Ruff: 0 errors (was 33)
- Mypy: 0 errors
- ResourceWarnings: 0 (verified with `-W error::ResourceWarning`)
- `HistoryStore.close()` is idempotent + context manager support
- Test fixtures in `test_history.py`, `test_preferences.py`, `test_dedup.py` use `yield`/teardown
- Additional fix beyond original spec: `cli.py:history_cmd` now wraps store in `try/finally` (was leaking on direct CLI invocation)

---

## Goal

Achieve a clean CI gate: `ruff check .` exits 0 and no `ResourceWarning` in test output.

---

## Step 1 — Auto-fix lint (5 min)

Run ruff auto-fixer. This resolves 11 of 33 errors (I001 import sorting, F401 unused imports):

```bash
.venv/bin/ruff check . --fix
```

Verify:
```bash
.venv/bin/pytest -q  # must still show 640 passed
```

Remaining errors after auto-fix will all be E501 (line too long). Proceed to Step 2.

---

## Step 2 — Fix E501 in `tests/test_daemon/test_daemon.py` (5 min)

**Line 194** — `patch(..., side_effect=RuntimeError("LLM timeout"))` string too long.

Extract to variable before the `with` block:
```python
# Before
with (
    patch("promptune.daemon.daemon.enhance", side_effect=RuntimeError("LLM timeout")),
    patch("promptune.daemon.daemon.UNDO_FILE", undo_file),
):

# After
enhance_err = RuntimeError("LLM timeout")
with (
    patch("promptune.daemon.daemon.enhance", side_effect=enhance_err),
    patch("promptune.daemon.daemon.UNDO_FILE", undo_file),
):
```

---

## Step 3 — Fix E501 in `tests/test_daemon/test_platform/test_init.py` (10 min)

All long lines are `patch.dict("sys.modules", {"promptune.daemon.platform.X": mock_X})`.

Pattern fix: extract the modules dict before the `with patch.dict` call.

**Template:**
```python
# Before
with patch.dict("sys.modules", {"promptune.daemon.platform.linux_x11": mock_x11}):

# After
mods = {"promptune.daemon.platform.linux_x11": mock_x11}
with patch.dict("sys.modules", mods):
```

Apply to all 7 E501 instances in this file. Each nested `patch.dict` gets its own variable name (`mods_macos`, `mods_x11`, `mods_wl`, etc.).

Also fix line 91 (`detect_session_type` return value) and line 113 (same pattern):
```python
# Before
patch("promptune.daemon.platform.detect_session_type", return_value="wayland"),

# After  — this is inside a multi-context manager tuple, break with backslash
patch(
    "promptune.daemon.platform.detect_session_type",
    return_value="wayland",
),
```

---

## Step 4 — Fix E501 in remaining test_platform files (15 min)

Apply the same `patch.dict` dict-extraction pattern to:
- `tests/test_daemon/test_platform/test_linux_service.py`
- `tests/test_daemon/test_platform/test_linux_wayland.py`
- `tests/test_daemon/test_platform/test_linux_x11.py`
- `tests/test_daemon/test_platform/test_macos.py`

For `test_macos.py`, all long lines are `patch("promptune.daemon.platform.macos.X_mod.method", return_value=Y)` strings. Break them across lines:
```python
# Before
with patch("promptune.daemon.platform.macos.clip_mod.save_clipboard", return_value="text") as mock_read:

# After
with patch(
    "promptune.daemon.platform.macos.clip_mod.save_clipboard",
    return_value="text",
) as mock_read:
```

---

## Step 5 — Verify lint clean (2 min)

```bash
.venv/bin/ruff check .
# Expected: exit 0, no output
```

If any E501 remain, fix manually by the same pattern. Do not suppress with `# noqa`.

---

## Step 6 — Add `close()` to `HistoryStore` (20 min)

Edit `promptune/history.py`:

1. Find the `__init__` method — note the attribute name for the SQLite connection (likely `self._conn` or `self.conn`)
2. Add `close()` method:
```python
def close(self) -> None:
    """Close the underlying SQLite connection. Idempotent."""
    conn = getattr(self, "_conn", None)
    if conn is not None:
        conn.close()
        self._conn = None
```
3. Add context manager:
```python
def __enter__(self) -> "HistoryStore":
    return self

def __exit__(self, *args: object) -> None:
    self.close()
```

4. Run mypy to confirm no type errors:
```bash
.venv/bin/mypy promptune/history.py
```

---

## Step 7 — Fix test fixtures for `HistoryStore` (20 min)

1. Audit all test files that instantiate `HistoryStore`:
```bash
grep -rn "HistoryStore(" tests/
```

2. For each fixture in `tests/conftest.py` that returns `HistoryStore`:
```python
# Before
@pytest.fixture
def history_store(tmp_path):
    return HistoryStore(tmp_path / "test.db")

# After
@pytest.fixture
def history_store(tmp_path):
    store = HistoryStore(tmp_path / "test.db")
    yield store
    store.close()
```

3. For inline instantiations inside individual tests (not using the fixture), convert:
```python
# Before
store = HistoryStore(tmp_path / "test.db")
# ... test body

# After
with HistoryStore(tmp_path / "test.db") as store:
    # ... test body
```

4. Run tests and confirm zero `ResourceWarning`:
```bash
.venv/bin/pytest tests/test_history.py -q -W error::ResourceWarning
```

---

## Step 8 — Full verification (5 min)

```bash
.venv/bin/ruff check . && .venv/bin/mypy promptune/ && .venv/bin/pytest -q -W error::ResourceWarning
```

Expected:
- `ruff`: exit 0
- `mypy`: 0 issues
- `pytest`: 640+ passed, 0 ResourceWarnings

---

## Step 9 — Update `docs/VERIFICATION_REPORT.md`

Update:
- **Last Verified** — new date, results
- **Lint Issues** — clear all 33 rows
- **Known Issues** — mark #1 (ResourceWarnings) and #3 (lint) as resolved
- **Remaining Work** — mark P0 lint row and P1 SQLite row as done
