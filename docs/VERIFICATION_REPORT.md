# Promptune — Verification Report

> **Living document.** Update this after every verification run.
> Check this first in any new session before running full suite.

---

## Last Verified

| Field | Value |
|-------|-------|
| Date | 2026-06-15 |
| Branch | feat/linux-daemon-hardening (merged with main) |
| Python | 3.14.3 |
| Total Tests | 944 |
| Test Result | **937 passed, 7 linux-only deselected, 0 failed** |
| Coverage | **97%** (target ≥ 90%) ✅ |
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
| **TOTAL** | **3318** | **92** | **97%** | ✅ | Target: ≥ 90% |

**Coverage status key:**
- ✅ = ≥ 90% (meets target)
- ❌ = < 90% (needs work, runnable on macOS)
- ⚠️ = platform-specific (linux-only, acceptable gap on macOS CI)

---

## Lint Issues (Ruff)

**All checks pass. Zero errors.**

---

## Known Issues

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
Coverage gate is enforced with `--cov-fail-under=90` (now passing at 93%).
