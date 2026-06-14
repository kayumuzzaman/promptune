# Spec: Coverage Improvement (85% → ≥90%)

**Date:** 2026-03-29
**Status:** Ready for implementation
**Plan:** `docs/superpowers/plans/2026-03-29-coverage-improvement.md`
**Current:** 85% overall | **Target:** ≥ 90% overall, ≥ 90% per non-platform module

---

## Why This Matters

**85% overall sounds acceptable, but the gap is concentrated in the most critical paths:**

- `cli.py` is the primary user-facing interface. At 67%, we have not tested ~154 lines of what users actually run. Bugs in daemon start/stop error handling, config validation messages, and history export go undetected until a real user hits them.
- `hotkey.py` at 69% and `ipc.py` at 82% mean the global hotkey registration and Unix socket IPC — the two mechanisms the daemon depends on — have untested failure modes. A registration failure that silently swallows the error would leave users with a daemon that appears to start but never responds to the hotkey.
- `daemon.py` at 83% means the lifecycle orchestration (start, stop, status, PID file management) has uncovered branches. PID file race conditions and cleanup failures are exactly the class of bugs that corrupt daemon state.
- The 90% gate in CI is currently failing, meaning every CI run is red. A perpetually-red CI desensitizes the team to failures — the same cognitive load that makes `ResourceWarning` noise dangerous applies here.

**Platform modules (`linux_x11.py` 46%, `linux_wayland.py` 51%):** These are lower priority since macOS CI cannot run them natively, but they have real users and deserve reasonable mock-based coverage.

---

## Module-by-Module Analysis

### Priority 0: `cli.py` (67% → ≥90%)

**Location:** `promptune/cli.py:466 lines, 154 uncovered`

**Uncovered regions (from coverage report):**

| Lines | Region | What it is |
|-------|--------|------------|
| 117, 119 | `enhance` command | Error path when provider fails |
| 152–158 | `enhance` command | `--no-history` flag path |
| 257, 271–282 | `history` command | `--export` and `--format` edge cases |
| 453–469 | `daemon start` | Success/already-running paths |
| 473–482 | `daemon stop` | Not-running path |
| 507–528 | `daemon status` | All status display paths |
| 560–561, 582–583 | `daemon install/uninstall` | Error paths |
| 628–960 (many) | Config/setup subcommands | Interactive wizard paths |
| 816–818, 839–845 | `config show` | Provider-specific display |
| 865–967 (various) | `config set`/`config reset` | Validation error paths |

**Test strategy for each:**
- `daemon start` success: mock `start_daemon()` returning `True`, assert exit 0 and success message
- `daemon start` already-running: mock `start_daemon()` returning `False`, assert appropriate message
- `daemon stop` not-running: mock `stop_daemon()` returning `False`
- `daemon status`: mock `get_status()` returning each of: running/stopped/unknown states
- `daemon install/uninstall`: mock platform service `install()`/`uninstall()`, cover success + `PermissionError`
- `enhance` error path: mock provider `enhance()` raising `ProviderError`, assert non-zero exit
- `enhance --no-history`: pass flag, verify `HistoryStore.save` not called
- `history --export`: mock `HistoryStore.export()`, verify file written
- `config show`: pass `--provider=claude`, `--provider=openai`, assert different output
- `config set` with invalid key: assert exit 1 + error message
- `config reset`: mock config write, verify defaults restored

**Corner cases:**
- Click's `invoke()` in tests captures `SystemExit` — use `result.exit_code` not `sys.exit` assertions
- Commands that call `sys.exit()` directly vs `ctx.exit()` — use `CliRunner(mix_stderr=False)` to capture separately
- `daemon install` on macOS calls `MacOSService.install()` — must mock at the `get_platform()` level
- Interactive prompts in config setup: use `CliRunner(input=...)` to simulate keystrokes
- Commands that read `~/.config/promptune/config.toml` — use `tmp_path` fixture and `PROMPTUNE_CONFIG` env var or monkeypatch

---

### Priority 1: `hotkey.py` (69% → ≥90%)

**Location:** `promptune/daemon/hotkey.py:61 stmts, 19 uncovered`

**Uncovered regions:**
- Line 13: Import-time guard (`if sys.platform != "darwin": raise ImportError`)
- Lines 86: `parse_hotkey` with invalid modifier combo
- Lines 148–162: `register_hotkey` — the `CGEventTap` setup path
- Lines 221–234: `stop_run_loop` — the RunLoop teardown
- Lines 241–243: CGEventTap callback error path

**Test strategy:**
- Import guard: test that importing on non-macOS raises `ImportError` (mock `sys.platform = "linux"`)
- `parse_hotkey` invalid: `parse_hotkey("invalidkey")` → assert `ValueError`
- `parse_hotkey` all modifiers: test `cmd+ctrl+shift+alt+e` → verify all modifier flags ORed
- `register_hotkey`: mock `Quartz.CGEventTapCreate` to return a mock tap object; verify `CFRunLoopAddSource` called
- `register_hotkey` failure: mock `CGEventTapCreate` returning `None` → assert `RuntimeError`
- `stop_run_loop`: mock `CFRunLoopStop`; verify called with correct args
- CGEventTap callback: create the callback function with a mock event, verify it calls `_on_event`

**Corner cases:**
- `Quartz` and `ApplicationServices` are macOS-only — tests must patch at the module level before import, or use `importlib.reload` after patching `sys.modules`
- The RunLoop runs in a thread — tests must not actually start the thread; mock `threading.Thread.start`
- Callback errors that happen inside the CGEventTap callback run on the RunLoop thread — verify exceptions are caught and logged, not silently lost

---

### Priority 1: `ipc.py` (82% → ≥90%)

**Location:** `promptune/daemon/ipc.py:89 stmts, 16 uncovered`

**Uncovered regions:**
- Lines 41–43: `UnixSocketServer.__init__` with `socket_path` already existing (stale socket cleanup)
- Lines 65–66: `start()` — bind failure path (e.g. `PermissionError`)
- Lines 101–102: Client disconnect mid-message (partial read)
- Lines 108–109: Malformed JSON from client
- Lines 116–117: Handler raises exception
- Lines 148–149: `stop()` — cleanup when socket file doesn't exist
- Lines 152–154: `CWDClient.send()` — connection refused path

**Test strategy:**
- Stale socket cleanup: create a file at the socket path before constructing `UnixSocketServer`; verify it's removed
- Bind failure: mock `socket.bind` raising `PermissionError`; assert `start()` raises
- Partial read: send truncated JSON bytes; verify server handles gracefully (logs, doesn't crash)
- Malformed JSON: send `b"not json\n"`; verify server sends error response, doesn't crash
- Handler exception: register a handler that raises; verify server continues serving other clients
- `stop()` missing socket: delete socket file before `stop()`; verify no exception
- `CWDClient` connection refused: mock `socket.connect` raising `ConnectionRefusedError`; verify `send()` returns `False` or raises defined exception

**Corner cases:**
- Unix domain sockets in tests: use `tmp_path / "test.sock"` — never hardcode `/tmp/promptune.sock` in tests
- Server must run in a thread for tests; use `threading.Thread(daemon=True)` and join with timeout
- Race between `start()` spawning thread and test sending message — use a `threading.Event` set when server is ready
- `stop()` must unblock the `accept()` call — verify it uses `self._sock.close()` which raises `OSError` on the blocking thread
- Test cleanup: if a test leaves a socket file, next test must not fail on socket-already-exists

---

### Priority 1: `daemon.py` (83% → ≥90%)

**Location:** `promptune/daemon/daemon.py:184 stmts, 32 uncovered`

**Uncovered regions:**
- Lines 126–127: `_write_pid` with `PermissionError` (read-only directory)
- Lines 216–230: `_is_running` with live PID that exists but process is not promptune (PID reuse)
- Lines 257–267: `start_daemon` — already-running branch + fork failure path
- Lines 279: Signal handler registration failure
- Lines 299–302: `_cleanup` with stale PID file and no process
- Lines 324: `_on_hotkey` — enhancement returns empty string
- Lines 359–365: `_enhancing` — `undo()` failure path

**Test strategy:**
- `_write_pid` permission error: mock `open()` raising `PermissionError`; verify `start_daemon` raises with clear message
- `_is_running` PID reuse: write a PID file with PID of a running process (e.g. `os.getpid()`), but with a different process name; mock `/proc/{pid}/cmdline` or `psutil.Process.name()` to return a non-promptune name
- `start_daemon` already-running: mock `_is_running` returning `True`; verify returns `False` + logs appropriate message
- `start_daemon` fork failure: mock `os.fork()` raising `OSError`; verify clean error handling
- `_cleanup` stale PID: write PID file with dead PID; call `_cleanup`; verify PID file removed
- `_on_hotkey` empty enhancement: mock `enhance()` returning `""`; verify clipboard not written
- `_enhancing` undo failure: mock `undo()` raising exception; verify daemon continues (doesn't crash)

**Corner cases:**
- `os.fork()` creates a real child process in tests — always mock fork, never actually fork in unit tests
- `_is_running` reads `/proc/{pid}` on Linux vs `ps` on macOS — the cross-platform check must be mocked at the right level
- Signal handlers are process-global — tests that register signal handlers must restore them in teardown (`signal.signal(signal.SIGTERM, original_handler)`)
- PID file paths: tests must use `tmp_path`, never `~/.local/share/promptune/promptune.pid`
- The enhancement pipeline in `_on_hotkey` calls clipboard → enhance → clipboard: if clipboard read returns `None` (empty clipboard), must not call enhance

---

### Priority 2: `engine.py` (86% → ≥90%)

**Uncovered regions (lines 79–81, 121–131, 163, 231–236, 295–296, 306, 308–313, 328–330):**

| Lines | What |
|-------|------|
| 79–81 | `_route_tier` when `max_tier=0` but local is configured |
| 121–131 | `_apply_context` when context collection raises timeout |
| 163 | `enhance()` when all providers fail (fallback exhausted) |
| 231–236 | `_score_and_store` when history is disabled |
| 295–296 | `_dedup_check` when dedup is disabled |
| 306, 308–313 | `_apply_preferences` edge paths |
| 328–330 | `enhance()` return when tier0 result is sufficient (no LLM needed) |

**Test strategy:**
- `max_tier=0` with local configured: set `config.enhancement.max_tier=0`; verify local provider not called
- Context timeout: mock `collect_context()` raising `asyncio.TimeoutError`; verify engine continues with empty context
- All providers fail: mock all providers raising `ProviderError`; verify `enhance()` raises or returns original prompt with flag
- History disabled: set `config.history.enabled=False`; verify `HistoryStore.save` not called
- Dedup disabled: set `config.enhancement.dedup_enabled=False`; verify dedup not run
- Tier0 sufficient: craft a prompt where tier0 rules fully handle it; verify no LLM call made
- Preferences with < min_samples: set `preference_min_samples=5`, provide 3 samples; verify preferences not applied

**Corner cases:**
- Engine uses async internally — test with `pytest-asyncio` or wrap in `asyncio.run()`
- Provider timeout vs provider error — both should be caught; verify timeout doesn't crash engine
- `dedup_check` returning `True` should return the cached result, not the new enhanced result
- When `max_tier` is exceeded mid-enhance (e.g. tier1 fails and tier2 is disabled), engine must not silently return empty string

---

### Priority 2: `context/collectors.py` (85% → ≥90%)

**Uncovered regions (lines 81, 90–92, 165–166, 194, 208, 213, 218, 220, 236, 269–272, 296–297, 318–319, 332–333):**

| Lines | What |
|-------|------|
| 81 | `GitCollector` when `.git` doesn't exist (not a git repo) |
| 90–92 | `GitCollector` when `git` binary not found |
| 165–166 | `ShellHistoryCollector` when `HISTFILE` is unreadable |
| 194 | `ShellHistoryCollector` for fish history (different format) |
| 208, 213 | `StackCollector` when `package.json` is malformed JSON |
| 218, 220 | `StackCollector` when `requirements.txt` is empty |
| 236 | `StackCollector` when `go.mod` has no module line |
| 269–272 | `EnvCollector` when env var value is `None` |
| 296–297 | `collect_all()` when a collector raises unexpectedly |
| 318–319 | Timeout path in `collect_all()` |
| 332–333 | `collect_all()` when all collectors return empty |

**Test strategy:**
- No git repo: run `GitCollector` with `cwd` pointing to `tmp_path` (no `.git` dir)
- Git binary not found: mock `subprocess.run` raising `FileNotFoundError`
- Unreadable HISTFILE: create a file with mode `000`; verify collector returns empty, doesn't raise
- Fish history: create a fish_history YAML file in `tmp_path`; verify parsed correctly
- Malformed `package.json`: write `{invalid json`; verify returns empty stack, no crash
- Empty `requirements.txt`: write empty file; verify returns empty, no crash
- `go.mod` no module line: write `go.mod` with only `go 1.21`; verify no crash
- `EnvCollector` with `None` value: mock `os.environ.get` returning `None`; verify skipped
- Collector raises: mock one collector's `collect()` raising `RuntimeError`; verify others still run
- Timeout: mock collector taking > timeout; verify `collect_all()` returns within timeout

**Corner cases:**
- Permission error on HISTFILE must be caught silently (not all shells have readable history)
- Fish history uses YAML not bash format — parser must handle both
- `collect_all()` uses `asyncio.gather` with `return_exceptions=True` — verify exceptions are logged not re-raised
- `subprocess.run` for git must use `capture_output=True, text=True` — don't let subprocess inherit test's stderr

---

### Priority 2: `__main__.py` (0% → 100%)

**File:** `promptune/__main__.py` (2 statements)

```python
from promptune.cli import main
main()
```

**Test:**
```python
import subprocess, sys

def test_main_module_invocable():
    result = subprocess.run(
        [sys.executable, "-m", "promptune", "--help"],
        capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "promptune" in result.stdout.lower()
```

**Corner cases:**
- Must test via `subprocess` — not via direct import — because `main()` calls `sys.exit()`
- Must not require API keys — `--help` exits before any provider call

---

### Priority 2: `templates.py` (89% → ≥90%)

**Uncovered regions (lines 48, 55, 58, 62–63, 92–93, 117–118):**

| Lines | What |
|-------|------|
| 48 | `TemplateStore` when `.prompts/` directory doesn't exist |
| 55, 58 | Template file with no YAML frontmatter |
| 62–63 | Template file with malformed YAML frontmatter |
| 92–93 | `match()` with no templates loaded |
| 117–118 | `render()` with missing variable in template |

**Test strategy:**
- No `.prompts/` dir: construct `TemplateStore(tmp_path)` where `tmp_path` has no `.prompts/`; verify returns empty list
- No frontmatter: write a `.md` file with just plain text; verify loaded as template with empty metadata
- Malformed YAML: write `---\ninvalid: [yaml\n---`; verify skipped with logged warning, no crash
- Empty store `match()`: `TemplateStore` with no templates; call `match("any prompt")`; verify returns `None`
- Missing template variable: template has `{{name}}`, `render()` called without `name`; verify raises `KeyError` or returns unrendered placeholder per design

**Corner cases:**
- YAML frontmatter parsing uses `yaml.safe_load` — must handle edge cases like `null` values and multiline strings
- Template matching uses cosine similarity — with zero templates, must not divide by zero

---

### Priority 3: `linux_x11.py` (46% → ≥70%) and `linux_wayland.py` (51% → ≥70%)

These require `python-xlib`, `evdev`, `dbus-next` — dependencies only available on Linux. Tests must:
1. Mock all native library calls
2. Be marked `@pytest.mark.linux`
3. Still run on macOS via mock — the business logic (key parsing, event dispatch, IPC routing) can be tested without real X11/Wayland

**X11 uncovered (lines 35–43, 56–57, 63–94, 103–128, 191–192, 205–223):**
- `XGrabKey` setup and teardown path
- `XNextEvent` loop — event dispatch to callback
- `xclip` / `xdotool` subprocess calls
- `xclip` not found (`FileNotFoundError`)
- Invalid display (`DISPLAY` not set)

**Wayland uncovered (lines 39–40, 46–53, 63–103, 114–167, 228–231, 246, 275–290, 293–300, 320):**
- `wl-clipboard` subprocess path
- `ydotool` paste path
- Portal DBus path for clipboard
- Session type detection (`XDG_SESSION_TYPE` not set)
- `evdev` device discovery (no input devices found)
- `evdev` grab failure (`PermissionError` on `/dev/input/eventX`)

**Corner cases for both:**
- Mock `sys.modules` for `Xlib`, `evdev`, `dbus_next` before import
- Tests must not actually connect to X11/Wayland display
- `DISPLAY` env var must be mocked/unset in tests that test "no display" path
- `XDG_SESSION_TYPE` env var controls session detection — mock both `wayland` and `x11` values
- File permission errors on `/dev/input/` should be caught and produce a user-readable error, not a traceback

---

## Acceptance Criteria

- [ ] Overall coverage ≥ 90%
- [ ] `cli.py` ≥ 90%
- [ ] `hotkey.py` ≥ 90%
- [ ] `ipc.py` ≥ 90%
- [ ] `daemon.py` ≥ 90%
- [ ] `engine.py` ≥ 90%
- [ ] `context/collectors.py` ≥ 90%
- [ ] `__main__.py` = 100%
- [ ] `templates.py` ≥ 90%
- [ ] `linux_x11.py` ≥ 70% (linux-only mark)
- [ ] `linux_wayland.py` ≥ 70% (linux-only mark)
- [ ] All 640+ tests still pass (no regressions)
- [ ] No new mypy errors introduced by test helpers
- [ ] CI coverage gate passes (`--cov-fail-under=90`)

---

## Out of Scope

- Ruff lint fixes (separate spec: `2026-03-29-code-quality-fixes.md`)
- Adding new production features
- Integration tests (these are all unit/mock-based)
- 100% coverage for platform modules (too brittle, requires real OS)
