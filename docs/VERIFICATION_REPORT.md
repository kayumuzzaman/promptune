# Promptune — Verification Report

> **Living document.** Update this after every verification run.
> Check this first in any new session before running full suite.

---

## Last Verified

| Field | Value |
|-------|-------|
| Date | 2026-06-18 |
| Branch | fix/validation-round5 |
| Python | 3.14.3 |
| Total Tests | 1109 |
| Test Result | **1103 passed, 6 skipped, 0 failed** |
| Coverage | **97%** (gate ≥ 85%) ✅ |
| Ruff | **PASS** — 0 errors |
| Mypy | **PASS** — 0 issues in 46 source files |
| ResourceWarnings | **0** (verified with `-W error::ResourceWarning`) ✅ |
| Pytest Warnings | **4** — `PytestUnhandledThreadExceptionWarning` in prewarm timer test |

---

## Quick Verification Commands

```bash
# Full suite (lint + types + tests + coverage)
.venv/bin/ruff check . && .venv/bin/mypy promptune/ && .venv/bin/pytest --cov=promptune --cov-report=term-missing -q

# Tests only (fast, 17s)
.venv/bin/pytest -q

# Coverage only
.venv/bin/pytest --cov=promptune --cov-report=term-missing -q

# Lint only
.venv/bin/ruff check .

# Types only
.venv/bin/mypy promptune/

# Auto-fix fixable lint errors
.venv/bin/ruff check . --fix

# Skip linux-only tests (run on macOS)
.venv/bin/pytest -m "not linux" -q
```

---

## Coverage by Module

| Module | Stmts | Miss | Cover | Status | Notes |
|--------|-------|------|-------|--------|-------|
| `promptune/__init__.py` | 1 | 0 | 100% | ✅ | |
| `promptune/__main__.py` | 2 | 0 | 100% | ✅ | Smoke test added |
| `promptune/cli.py` | 528 | 8 | 98% | ✅ | history_cmd lifecycle fix |
| `promptune/config.py` | 91 | 4 | 96% | ✅ | +auto_enhance defaults |
| `promptune/context/__init__.py` | 33 | 3 | 91% | ✅ | |
| `promptune/context/collectors.py` | 142 | 0 | 100% | ✅ | Was 85% |
| `promptune/context/ranker.py` | 56 | 1 | 98% | ✅ | |
| `promptune/context/sanitizer.py` | 35 | 2 | 94% | ✅ | |
| `promptune/daemon/__init__.py` | 0 | 0 | 100% | ✅ | |
| `promptune/daemon/clipboard.py` | 56 | 4 | 93% | ✅ | |
| `promptune/daemon/daemon.py` | 175 | 1 | 99% | ✅ | Clipboard delivery failure handling |
| `promptune/daemon/hotkey.py` | 61 | 0 | 100% | ✅ | Was 69% |
| `promptune/daemon/ipc.py` | 89 | 8 | 91% | ✅ | Was 82% |
| `promptune/daemon/launchagent.py` | 22 | 0 | 100% | ✅ | |
| `promptune/daemon/notify.py` | 18 | 0 | 100% | ✅ | |
| `promptune/daemon/platform/__init__.py` | 35 | 0 | 100% | ✅ | |
| `promptune/daemon/platform/base.py` | 54 | 0 | 100% | ✅ | |
| `promptune/daemon/platform/linux_service.py` | 64 | 0 | 100% | ✅ | |
| `promptune/daemon/platform/linux_wayland.py` | 278 | 14 | 95% | ✅ | Portal match/session/binding handling hardened |
| `promptune/daemon/platform/linux_x11.py` | 178 | 0 | 100% | ✅ | Real-display X11 tests + failure propagation |
| `promptune/daemon/platform/macos.py` | 47 | 2 | 96% | ✅ | |
| `promptune/daemon/prewarm.py` | 43 | 1 | 98% | ✅ | |
| `promptune/dedup.py` | 55 | 2 | 96% | ✅ | |
| `promptune/engine.py` | 177 | 4 | 98% | ✅ | Was 86% |
| `promptune/formatter.py` | 69 | 2 | 97% | ✅ | |
| `promptune/gate.py` | 51 | 0 | 100% | ✅ | Was 69% |
| `promptune/history.py` | 101 | 4 | 96% | ✅ | close() idempotent + context manager |
| `promptune/hooks/__init__.py` | 14 | 0 | 100% | ✅ | |
| `promptune/hooks/claude_code.py` | 51 | 2 | 96% | ✅ | |
| `promptune/mcp/__init__.py` | 0 | 0 | 100% | ✅ | |
| `promptune/mcp/server.py` | 32 | 0 | 100% | ✅ | Was 53% |
| `promptune/meta_prompt.py` | 47 | 0 | 100% | ✅ | |
| `promptune/pqs.py` | 50 | 0 | 100% | ✅ | |
| `promptune/preferences.py` | 62 | 2 | 97% | ✅ | |
| `promptune/providers/__init__.py` | 25 | 0 | 100% | ✅ | |
| `promptune/providers/anthropic.py` | 22 | 1 | 95% | ✅ | |
| `promptune/providers/local.py` | 33 | 2 | 94% | ✅ | |
| `promptune/providers/openai.py` | 21 | 1 | 95% | ✅ | |
| `promptune/providers/openrouter.py` | 29 | 3 | 90% | ✅ | |
| `promptune/scorer.py` | 250 | 16 | 94% | ✅ | |
| `promptune/setup.py` | 161 | 4 | 98% | ✅ | Optional API key + tier resolver |
| `promptune/shell.py` | 78 | 0 | 100% | ✅ | |
| `promptune/templates.py` | 82 | 6 | 93% | ✅ | Was 89% |
| `promptune/tier0.py` | 148 | 6 | 96% | ✅ | |
| `promptune/tui.py` | 146 | 3 | 98% | ✅ | |
| **TOTAL** | **3318** | **92** | **97%** | ✅ | Gate: ≥ 85% |

**Coverage status key:**
- ✅ = ≥ 90% (meets target)
- ❌ = < 90% (needs work, runnable on macOS)
- ⚠️ = platform-specific (linux-only, acceptable gap on macOS CI)

---

## Lint Issues (Ruff)

**All checks pass. Zero errors.**

---

## Known Issues

### -4. Audit round 5 (2026-06-18) — 5 findings [RESOLVED, per user decisions]
Fifth sub-agent pass. Findings were design decisions + consequences of the
now-active history feature; resolved per explicit user direction:

- **HIGH `formatter.py` (dead feature) — REMOVED.** The `--format-style` /
  provider-formatting feature (XML/MD/Plain) was parsed but never applied to
  output — `formatter.py` was never called by the pipeline. Per user decision,
  removed: `formatter.py` + its tests, the `--format` CLI flag, the MCP
  `output_format` param, the setup-wizard format prompt, and the `format_style`
  config field/validation. The history `format_style` column is kept (nullable,
  always written as `"auto"`) to avoid a DB migration; `EnhanceResult.format_style`
  is now a vestigial constant `"auto"`. Docs updated (README, USER_GUIDE,
  ARCHITECTURE, MANUAL_TESTING, CLAUDE.md).
- **HIGH `gate.py` (recording pollution) — FIXED.** The auto-enhance gate
  recorded every prompt as a confirmed `decision="accept"` with no accept/reject
  surface, polluting dedup + preference learning. `enhance()` gained a
  `record: bool = True` param; the gate now calls `enhance(record=False)`.
- **HIGH `daemon/clipboard.py` paste_result — FIXED.** macOS `paste_result()`
  always returned `True` even when the synthetic Cmd+V was dropped (no
  accessibility trust), unlike the X11/Wayland backends. Now checks
  `check_accessibility()` and returns `False` so the daemon tells the user to
  paste manually instead of clobbering the clipboard.
- **LOW `history.set_decision` — FIXED.** Now checks `rowcount` and debug-logs
  when the target row was already pruned, instead of a silent no-op.
- **MEDIUM dedup-hit rejection persistence — DEFERRED** (per user "fix gate +
  mechanical only" decision). A reject of a dedup-served result still isn't
  persisted; left as a known limitation rather than adding schema/source-column
  complexity.

### -3. Audit round 4 + Codex PR-bot review (2026-06-18) — 6 findings [RESOLVED]
Fourth sub-agent pass plus 2 P2 comments the Codex GitHub bot left on PR #16.
Most findings were consequences of the round-3 history-recording change:

- **Codex P2 / HIGH** `engine.py` + `cli.py` — recording hardcoded `decision=
  "accept"` *before* the interactive user acted, so rejected/edited prompts were
  stored as accepted and could be resurfaced by dedup. The engine now records
  `accept` and returns the row id on `EnhanceResult.history_id`; the CLI corrects
  it to the real `reject`/`edit` (with edit text) after `display_result()` via
  the new `HistoryStore.set_decision()`. This also makes preference learning see
  real decisions (resolves the round-4 "always-accept inert" finding).
- **Codex P2 / HIGH** `engine.py` + `dedup.py` — dedup matched prompt+project
  only, ignoring effective options, so a later same-prompt run with `--tier 0` /
  a different provider / format was served the stale cached result. Now dedup is
  bypassed when explicit `tier`/`provider` overrides are present, and a cached
  hit is only reused when its `format_style` matches the request.
- **HIGH** `preferences.py` — `analyse_rule_preferences`/`analyse_edit_patterns`
  scanned `recent(n=10000)` (full table) on every `enhance()` including the hot
  gate path; was free when the table was empty, real cost once recording was
  wired. Bounded to a `_PREF_WINDOW = 500` recent-window.
- **HIGH** `daemon/clipboard.py` — `get_frontmost_app()` had no exception guard
  (only None checks), unlike the X11/Wayland backends; a transient PyObjC failure
  crashed the per-press hotkey thread with no user feedback. Now degrades to "".
- **HIGH** `tui.py` — `_render_header` had no `tier_used == -1` branch, rendering
  a dedup cache hit as a misleading "Tier -1 · cloud". Now shows "Cached · history".
- **HIGH** `mcp/server.py` — `enhance_prompt` collapsed an explicit `style=
  "balanced"` to `None`, indistinguishable from "unset", so a client asking for
  balanced silently got the configured `default_mode`. Style now passes through.

Accepted minor (documented, not fixed): `enhance()` opens a second short-lived
sqlite connection for the record write rather than reusing the read-phase store.
The dominant load cost (the full-table preference scan) is fixed above; a local
sqlite open is sub-millisecond and not worth re-indenting the core routing
function. The `--format-style` CLI flag on `enhance` is also currently a no-op
(never applied to cfg) — pre-existing, tracked separately.

### -2. Multi-agent audit round 3 (2026-06-18) — 3 findings [RESOLVED]
Third parallel sub-agent pass. CLI/config domain came back clean; daemon and
core surfaced 3 defects, all fixed with regression tests + test isolation:

- **CRITICAL** `engine.py` / `cli.py` — `HistoryStore.record()` was never called
  in production, so the history table was always empty. That silently disabled
  three documented, default-on features: semantic **dedup** (queried an empty
  table), **preference learning**, and the `history`/`preferences` CLI commands.
  The engine read side was wired; the write side never was. Fixed by recording
  each completed enhancement in `engine.enhance()` (decision defaults to
  `accept`; best-effort — a history failure never breaks enhancement). Added an
  autouse `tests/conftest.py` `_isolate_home` fixture redirecting `$HOME` to a
  temp dir so the suite no longer reads/writes the real user DB and dedup cache
  hits can't leak across tests (this also fixed pre-existing real-home pollution).
- **HIGH** `daemon/platform/macos.py` — `MacOSService.purge()` only removed the
  login item, leaving the socket / PID / undo / log files behind, violating the
  `ServiceBackend.purge()` contract and the CLI's own "remove all daemon files"
  promise. Now deletes all four (lazy import to avoid a cycle), mirroring
  `LinuxService.purge()`.
- **MEDIUM** `daemon/notify.py` — `notify()` ran `osascript` via subprocess that
  could raise `TimeoutExpired`/`OSError`; callers invoke it inside the
  clipboard-delivery `try/except`, so a notification failure after a *successful*
  paste was misreported to the user as a paste failure. `notify()` now swallows
  subprocess errors (best-effort feedback never raises).

### -1. Multi-agent audit round 2 (2026-06-17) — 2 findings [RESOLVED]
A second parallel sub-agent pass (after PR #14 merged) found 2 more latent
defects; both fixed with regression tests:

- **HIGH** `setup.py` — the interactive wizard pre-filled `click.prompt(type=
  Choice, default=...)` for provider / mode / format directly from the user's
  config. click re-validates the default even on a blank Enter, so a stale or
  hand-edited invalid value made the wizard re-prompt forever — exactly the
  "fix my broken config" case it exists for. Added `_clamp_choice()` to fall
  back to the `DEFAULT_CONFIG` value when the stored default is invalid.
- **MEDIUM** `scorer.py` — `_INTENT_KEYWORDS["coding"]` had silently drifted
  from `meta_prompt._INTENT_KEYWORDS["coding"]` (missing application/program/
  tool/library/package/migrate), so the two intent code paths disagreed.
  scorer now imports meta_prompt's table directly (single source of truth).

### 0. Multi-agent codebase audit (2026-06-17) — 8 findings [RESOLVED]
A parallel sub-agent review of the whole codebase surfaced 8 latent defects
(tests were green but missed these). All fixed with regression tests this session:

- **CRITICAL** `daemon/daemon.py` — hotkey guard was a `threading.Event` with a
  check-then-set race; overlapping events (OS key autorepeat) could run
  `_on_hotkey` concurrently. Now an atomic `threading.Lock` (`acquire(blocking=False)`).
- **CRITICAL** `daemon/hotkey.py` (macOS) — CGEventTap fired on OS key-repeat
  events. Now ignores events with `kCGKeyboardEventAutorepeat` set.
- **CRITICAL** `daemon/platform/linux_x11.py` — X11 loop fired on every
  autorepeat `KeyPress`. Now enables detectable auto-repeat (best-effort) and
  tracks held-key via `KeyRelease` so a held hotkey fires once.
- **HIGH** `providers/openrouter.py` & `providers/local.py` — response parsing
  ran outside the `try`; a malformed (non-dict) API body raised `AttributeError`
  past the `ProviderError` handler, breaking tier fallback. Now shape-guarded.
- **HIGH** `engine.py` — tier-1/2 `except` clauses missed `ProviderNotFoundError`
  (not a `ProviderError` subclass), so an unknown `--provider` crashed instead of
  degrading. Added to all five except tuples.
- **HIGH** `cli.py` — `_get_history_store()` ignored configured `history.db_path`
  / `max_entries`, so `promptune history*` operated on the wrong DB. Now mirrors
  engine construction.
- `tier0.py` — `rule_code_delimiters` closed the code fence on blank lines inside
  an indented block, splitting one block into several. Blank lines now continue
  the block.

### 1. ~~SQLite Unclosed Connection Warnings~~ [RESOLVED]
**Fixed:** `HistoryStore.close()` is now idempotent (None guard on `_conn_inner`). Test fixture uses `yield`+teardown. Zero ResourceWarnings with `-W error::ResourceWarning`.

### 2. ~~Coverage Below Target (85% vs ≥90%)~~ [RESOLVED]
**Fixed:** Overall coverage 85% → 93%. All non-platform modules at ≥90%.

### 3. ~~Ruff Lint Failures (33 errors)~~ [RESOLVED]
**Fixed:** All 33 errors resolved (auto-fix + manual E501 wraps + SIM105 rewrites).

### 4. ~~Linux Platform Coverage (P3 — known gap)~~ [RESOLVED]
**Fixed:** Mocked coverage is now `linux_x11.py` 100% and `linux_wayland.py` 96%. X11 real-display tests run under Xvfb in CI; Wayland hardware sign-off remains manual.

### 5. ~~`gate.py` Coverage Below Target~~ [RESOLVED]
**Fixed:** `_print_gate_block` rendering tested directly (border chars, score display, multiline handling, line truncation, end-to-end via `run_gate`). Now 100%.

### 6. ~~`mcp/server.py` Coverage Below Target~~ [RESOLVED]
**Fixed:** `run_server()` covered including `ImportError` path when `mcp` dep missing, FastMCP stdio startup, and both registered tools (`enhance_prompt`, `score_prompt_quality`) delegating correctly. Now 100%.

### 7. Missing PARTIAL test scenarios (deferred)
**Severity:** Low
**Items:**
- `test_engine.py` — explicit "all providers fail" test
- `test_collectors.py` — empty `requirements.txt` test
- `test_ipc.py` — explicit "connection refused" test
- `test_templates.py` — explicit "missing template variable" test

**Status:** Deferred — module coverage already at target. See TaskList task #6.

### 8. Prewarm timer emits thread exception warnings (P2)
**Severity:** Medium
**Test:** `tests/test_daemon/test_prewarm.py::TestStartPrewarmTimer::test_cancel_stops_repeating_chain`
**Symptom:** Full suite passes but emits 4 `PytestUnhandledThreadExceptionWarning` warnings.
**Cause:** A repeating timer can call `prewarm_ollama()` after test cancellation; the test mock leaves `httpx.HTTPStatusError` as a non-exception object in that background path.
**Fix pointer:** Tighten timer cancellation/test cleanup or harden the mocked `httpx` exception setup.

---

## Remaining Work

| Priority | Item | Status | Notes |
|----------|------|--------|-------|
| ~~P0~~ | ~~Fix 33 ruff lint errors~~ | ✅ Done | 0 errors |
| ~~P0~~ | ~~Improve `cli.py` coverage 67% → ≥90%~~ | ✅ Done | 98% |
| ~~P1~~ | ~~Fix SQLite `ResourceWarning`~~ | ✅ Done | Idempotent close + lifecycle |
| ~~P1~~ | ~~Improve `hotkey.py` 69% → ≥90%~~ | ✅ Done | 100% |
| ~~P1~~ | ~~Improve `ipc.py` 82% → ≥90%~~ | ✅ Done | 91% |
| ~~P1~~ | ~~Improve `daemon.py` 83% → ≥90%~~ | ✅ Done | 99% |
| ~~P2~~ | ~~Improve `engine.py` 86% → ≥90%~~ | ✅ Done | 98% |
| ~~P2~~ | ~~Improve `collectors.py` 85% → ≥90%~~ | ✅ Done | 100% |
| ~~P2~~ | ~~Add `__main__.py` smoke test~~ | ✅ Done | 100% (runpy) |
| ~~P2~~ | ~~Improve `templates.py` 89% → ≥90%~~ | ✅ Done | 93% |
| ~~P1~~ | ~~Improve `gate.py` 69% → ≥90%~~ | ✅ Done | 100% |
| ~~P1~~ | ~~Improve `mcp/server.py` 53% → ≥90%~~ | ✅ Done | 100% |
| P2 | Add missing PARTIAL test scenarios | Deferred | Task #6 |
| P2 | Fix prewarm timer thread warning | Open | `test_cancel_stops_repeating_chain` background timer |
| ~~P3~~ | ~~Improve `linux_x11.py` 46% → ≥70%~~ | ✅ Done | 100% mocked + Xvfb CI |
| ~~P3~~ | ~~Improve `linux_wayland.py` 51% → ≥70%~~ | ✅ Done | 95% mocked; hardware sign-off still manual |

---

## How to Update This Document

After running verification, update:
1. **Last Verified** table — date, test count, overall result
2. **Coverage by Module** — update Cover%, Status columns for any changed modules
3. **Lint Issues** — remove resolved items, add new ones
4. **Known Issues** — mark resolved, add new
5. **Remaining Work** — tick off completed items

---

## CI Pipeline Reference

See `.github/workflows/ci.yml` for automated checks.
Coverage gate is enforced with `--cov-fail-under=85` (now passing at 97%).
