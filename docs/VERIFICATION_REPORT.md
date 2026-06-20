# Promptune — Verification Report

> **Living document.** Update this after every verification run.
> Check this first in any new session before running full suite.

---

## Last Verified

| Field | Value |
|-------|-------|
| Date | 2026-06-20 |
| Branch | fix/gemini-review-hardening |
| Python | 3.14.3 |
| Total Tests | 1231 |
| Test Result | **1225 passed, 6 skipped, 0 failed** |
| Coverage | **97.33%** (gate ≥ 85%) ✅ |
| Ruff | **PASS** — 0 errors |
| Mypy | **PASS** — 0 issues in 45 source files |
| Actionlint | **PASS** — 0 issues |
| ResourceWarnings | **0** (verified with `-W error::ResourceWarning`) ✅ |
| Pytest Warnings | **0** (verified with `-W error::pytest.PytestUnhandledThreadExceptionWarning`) ✅ |

---

## Quick Verification Commands

```bash
# Full suite (lint + types + tests + coverage)
.venv/bin/ruff check . && .venv/bin/mypy promptune/ && .venv/bin/pytest --cov=promptune --cov-report=term-missing --cov-fail-under=85 -q

# Tests only (fast, 20s)
.venv/bin/pytest -q

# Coverage only
.venv/bin/pytest --cov=promptune --cov-report=term-missing --cov-fail-under=85 -q

# Linux CI coverage (omits macOS-only daemon modules on Linux only)
.venv/bin/pytest -m "not linux" --cov=promptune --cov-report=term-missing --cov-config=.coveragerc-linux --cov-fail-under=85 -q

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
| `promptune/cli.py` | 562 | 10 | 98% | ✅ | style override validation |
| `promptune/config.py` | 109 | 5 | 95% | ✅ | +auto_enhance defaults |
| `promptune/context/__init__.py` | 44 | 0 | 100% | ✅ | disabled collector gating |
| `promptune/context/collectors.py` | 156 | 1 | 99% | ✅ | Was 85% |
| `promptune/context/ranker.py` | 56 | 1 | 98% | ✅ | |
| `promptune/context/sanitizer.py` | 50 | 2 | 96% | ✅ | |
| `promptune/daemon/__init__.py` | 0 | 0 | 100% | ✅ | |
| `promptune/daemon/clipboard.py` | 78 | 3 | 96% | ✅ | macOS coverage no longer globally omitted |
| `promptune/daemon/daemon.py` | 279 | 13 | 95% | ✅ | executable-bound PID identity + reuse-safe stop cleanup |
| `promptune/daemon/hotkey.py` | 65 | 0 | 100% | ✅ | Event tap re-enable |
| `promptune/daemon/ipc.py` | 126 | 10 | 92% | ✅ | non-dict JSON + handler-exception guards |
| `promptune/daemon/launchagent.py` | 24 | 0 | 100% | ✅ | Creates log parent |
| `promptune/daemon/notify.py` | 20 | 0 | 100% | ✅ | |
| `promptune/daemon/platform/__init__.py` | 22 | 0 | 100% | ✅ | |
| `promptune/daemon/platform/base.py` | 23 | 0 | 100% | ✅ | |
| `promptune/daemon/platform/linux_service.py` | 65 | 0 | 100% | ✅ | |
| `promptune/daemon/platform/linux_wayland.py` | 316 | 14 | 96% | ✅ | Portal match/session/binding handling hardened |
| `promptune/daemon/platform/linux_x11.py` | 220 | 0 | 100% | ✅ | Real-display X11 tests + failure propagation |
| `promptune/daemon/platform/macos.py` | 52 | 1 | 98% | ✅ | |
| `promptune/daemon/prewarm.py` | 44 | 0 | 100% | ✅ | Timer callback exceptions contained |
| `promptune/dedup.py` | 64 | 4 | 94% | ✅ | auto cache route filters provider/model |
| `promptune/engine.py` | 229 | 6 | 97% | ✅ | template aliases + context collector gating |
| `promptune/gate.py` | 32 | 0 | 100% | ✅ | Was 69% |
| `promptune/history.py` | 125 | 5 | 96% | ✅ | close() idempotent + context manager |
| `promptune/hooks/__init__.py` | 16 | 0 | 100% | ✅ | |
| `promptune/hooks/claude_code.py` | 82 | 0 | 100% | ✅ | |
| `promptune/hooks/codex.py` | 64 | 0 | 100% | ✅ | |
| `promptune/mcp/__init__.py` | 0 | 0 | 100% | ✅ | |
| `promptune/mcp/server.py` | 40 | 0 | 100% | ✅ | validates tool + tier overrides |
| `promptune/meta_prompt.py` | 56 | 1 | 98% | ✅ | |
| `promptune/pqs.py` | 50 | 0 | 100% | ✅ | |
| `promptune/preferences.py` | 68 | 2 | 97% | ✅ | |
| `promptune/providers/__init__.py` | 50 | 2 | 96% | ✅ | URL-userinfo redaction helpers |
| `promptune/providers/anthropic.py` | 23 | 0 | 100% | ✅ | |
| `promptune/providers/local.py` | 45 | 1 | 98% | ✅ | |
| `promptune/providers/openai.py` | 27 | 1 | 96% | ✅ | |
| `promptune/providers/openrouter.py` | 38 | 2 | 95% | ✅ | |
| `promptune/scorer.py` | 254 | 14 | 94% | ✅ | |
| `promptune/setup.py` | 171 | 4 | 98% | ✅ | Optional API key + tier resolver |
| `promptune/shell.py` | 88 | 0 | 100% | ✅ | |
| `promptune/templates.py` | 92 | 6 | 93% | ✅ | aliases for documented template values |
| `promptune/tier0.py` | 152 | 2 | 99% | ✅ | |
| `promptune/tui.py` | 160 | 3 | 98% | ✅ | |
| **TOTAL** | **4240** | **113** | **97.33%** | ✅ | Gate: ≥ 85% |

**Coverage status key:**
- ✅ = ≥ 90% (meets target)
- ❌ = < 90% (needs work, runnable on macOS)
- ⚠️ = platform-specific (linux-only, acceptable gap on macOS CI)

---

## Lint Issues (Ruff)

**All checks pass. Zero errors.**

---

## Known Issues

### -13. PR #21 Codex P2 follow-up after Claude rate limit (2026-06-20) — 2 findings [RESOLVED]

Claude stopped at the rate limit after reading two Codex P2 review comments on
PR #21. Codex resumed from the transcript, confirmed both comments were real,
and fixed them with RED regression tests first, targeted GREEN runs, full
lint/type/actionlint/coverage/warning gates, and subagent review.

- **MED** `engine.py` / `context/__init__.py` — context flags masked disabled
  sources after `collect_context()` had already started every collector, so
  disabled shell/git/stack collectors still read local data and spent latency.
  `collect_context()` now accepts `include_git`, `include_shell`, and
  `include_tech`; the engine passes config flags before collection and disabled
  collectors keep default empty values. Regressions:
  `test_engine_context_respects_individual_disable_flags` and
  `test_collect_context_skips_disabled_collectors`.
- **MED** `mcp/server.py` — public `enhance_prompt` collapsed any negative tier
  to auto before validation, so `tier=-2` silently ran as auto. It now validates
  the raw tool argument through `_validate_tier()` and only maps `-1` to `None`.
  Regression: `test_registered_enhance_tool_rejects_invalid_negative_tier`.
- **LOW** `engine.py` — Gemini's follow-up review flagged the post-collection
  `_context_with_enabled_collectors()` mask as redundant now that
  `collect_context()` skips disabled collectors directly. The redundant helper
  was removed after the P2 fixes were green, keeping the collector-level gating
  as the single source of truth.

### -12. fix/gemini-review-hardening continuation after Codex rate limit (2026-06-20) — 4 findings [RESOLVED]

Claude resumed the `fix/gemini-review-hardening` branch after Codex hit a rate
limit. Codex's unpushed security/robustness round (secret redaction helpers,
`--set-key` hidden prompt, fork-PR gating, IPC/hook guards, context toggles,
word-boundary scoring) was validated green and committed as a checkpoint, then
adversarial multi-agent review rounds ran review→fix→re-review until a round
returned clean. Each behavior fix landed RED-test-first with full
lint/mypy/coverage gates.

- **HIGH** `cli.py` — `daemon restart` called `start_daemon()` but ignored its
  bool return, so a failed start after stop was reported as success (exit 0).
  Now mirrors `daemon start` (exit 1 on failure). Regression:
  `test_daemon_restart_exits_1_when_start_fails`.
- **HIGH** `cli.py` — `_check_tier1()` (the `doctor` tier-1 probe) emitted the
  raw `local_llm` host in both its success and failure messages, leaking
  `user:pass@` userinfo; its sibling `_check_local_llm_connectivity` was already
  redacted but this instance was missed. Now redacted via `redact_url_userinfo`.
  Regressions: `test_check_tier1_redacts_host_userinfo_when_{reachable,unreachable}`.
- **MED** `providers/openrouter.py` — the error path redacted only the api_key,
  not `base_url` userinfo, but httpx errors embed the request URL. Now also
  redacts base_url userinfo, matching the local provider. Regression:
  `test_openrouter_error_redacts_base_url_userinfo`.
- **MED** `providers/__init__.py` — `redact_url_userinfo_in_text()` only
  string-replaced the exact configured URL, so credentials leaked when the HTTP
  library rendered the URL with normalized scheme/host case. It now also redacts
  any `scheme://user:pass@host` directly via a scheme-anchored regex (bounded
  scheme length to avoid O(n²) on large error bodies). Regressions added in
  `tests/test_providers/test_base.py` (case normalization, unhinted URL, bare
  email untouched, linear-time guard).

Also resolved (private-API reliance, flagged across rounds): `_ConfigGroup`
previously reached into Click's private `ctx._protected_args` (later
`getattr`-guarded) to reject a positionally-passed API key without echoing it.
It now overrides the **public** `resolve_command` instead — which fires on the
stray positional before Click's default "No such command '<value>'" error can
echo the secret — so there is no longer any reliance on Click internals or the
deprecated public `protected_args`.

**Codex PR #19 (merged) follow-up — 1 finding [RESOLVED]:** the Codex GitHub
reviewer left a P1 on merged PR #19's `daemon/daemon.py`. When a pip/pipx
console script launches the daemon, `ps -o comm=` can report `promptune` while
`ps -o command=` starts with the python interpreter; the `comm=promptune`
branch only ran `_is_console_script_command()` (which rejects python-prefixed
commands), so a live daemon read as stale — `stop`/`status` missed it and
`start` could launch a duplicate. The branch now also accepts the
python-console-script form (`comm=promptune` is a strong identity signal).
Regression: `test_is_daemon_process_accepts_promptune_comm_python_command`.

**Rejected as false positive:** a reviewer flagged `_dedup_provider_model_routes`
changing `if max_tier >= 2` to `elif` as a dropped cloud route. The `elif` is
deliberate: when local is the enabled/preferred tier, a previously cached cloud
*fallback* result must not be dedup-reused, or after local recovers the user is
served the stale cloud result forever (see
`test_engine_auto_dedup_does_not_reuse_cloud_fallback_when_local_first`). The
full suite caught the attempted "fix" as a regression; it was reverted.

### -11. PR #19 multi-agent continuation after Claude rate limit (2026-06-20) — 5 findings [RESOLVED]

Codex resumed the Claude multi-agent review loop from the clean local branch,
validated the unpushed follow-up commit, then ran daemon-focused review/fix/
re-review cycles until the reviewer reported no remaining issues. Each behavior
fix landed with a RED regression test first, targeted GREEN runs, and full
lint/type/actionlint/coverage/warning gates:

- **HIGH** `daemon/daemon.py` — accepting ABI-suffixed Python process names
  (`python3.13t`, `python3.13d`, `python3.13dm`) re-opened a module-argument
  false positive: a reused PID from a Python worker could include
  `-m promptune daemon start` later in argv and be mistaken for the daemon.
  Module-form detection now binds to the Python executable at command start and
  requires `-m promptune daemon start` immediately after it. Regressions:
  `test_is_daemon_process_rejects_python_worker_reused_pid_module_arg` and
  `test_is_daemon_process_rejects_spaced_python_worker_module_arg`.
- **MEDIUM** `daemon/daemon.py` — `[a-z]*` accepted arbitrary executable names
  like `python3.13foo`. `_is_python_executable()` now accepts only recognized
  ABI/debug/free-threaded suffixes (`t`, `d`, `dm`) while preserving `python`,
  `python3`, and `python3.12`. Regression:
  `test_is_python_executable_accepts_abi_suffixes`.
- **MEDIUM** `daemon/daemon.py` — `stop_daemon()` had the correct pre-SIGKILL
  identity guard, but no regression test for PID reuse during the grace timeout.
  Regression `test_reused_pid_after_grace_timeout_skips_force_kill` proves a PID
  that stops identifying as Promptune after SIGTERM is not SIGKILLed.
- **LOW** `daemon/daemon.py` — the post-timeout path logged `force-killed` even
  when the pre-SIGKILL identity guard failed and no SIGKILL was sent. It now logs
  stale/reused cleanup for that path.
- **LOW** docs/config memory — `.claude/CLAUDE.md` still mentioned removed
  formatter/`format_style` state. The stale Claude-specific references were
  removed.

### -10. PR #19 third repeated Codex validation loop (2026-06-19) — 1 finding [RESOLVED]

The next PR validation plus code scan found one more daemon PID identity edge
case. The fix landed with a RED regression test first, a targeted GREEN run,
then full lint/type/actionlint/coverage/warning gates:

- **HIGH** `daemon/daemon.py` — round--9 restored lowercase
  `python /path/to/promptune daemon start` but still false-negatived a real
  Python shebang console script when the installed path contained spaces, e.g.
  `Python /Users/Jane Doe/Library/Application Support/venv/bin/promptune daemon
  start`. `_is_daemon_process()` now accepts the common spaced venv
  `.../bin/promptune` / `.../Scripts/promptune` form while still rejecting
  Python worker scripts that merely pass promptune-looking args. Regression:
  `test_is_daemon_process_accepts_python_console_script_space_path`.

### -9. PR #19 second repeated Codex validation loop (2026-06-19) — 1 finding [RESOLVED]

The next PR validation plus code scan found one more daemon PID identity edge
case. The fix landed with RED regression tests first, a targeted GREEN run,
then full lint/type/actionlint/coverage/warning gates:

- **HIGH** `daemon/daemon.py` — Python shebang console scripts were still
  ambiguous in `ps -o command=` output. Lowercase `python /path/to/promptune
  daemon start` could false-negative, while capitalized macOS framework
  `Python ... worker.py /tmp/promptune daemon start` could false-positive.
  `_is_daemon_process()` separated non-Python console-script matching from
  Python interpreter wrapper matching: round--10 then extended this to the common
  spaced `.../bin/promptune` console-script path. It rejects arbitrary later
  arguments containing `/tmp/promptune daemon start`. Regressions:
  `test_is_daemon_process_accepts_python_interpreter_console_script` and
  `test_is_daemon_process_rejects_capitalized_python_worker_arg`.

### -8. PR #19 repeated Codex validation loop (2026-06-19) — 2 findings [RESOLVED]

The repeated PR validation plus code scan found two more PID helper flaws. Each
fix landed with RED regression tests first, a targeted GREEN run, then full
lint/type/actionlint/coverage/warning gates:

- **HIGH** `daemon/daemon.py` — the round--7 regex still relied on the
  space-joined `ps -o command=` text, so an unrelated process whose arguments
  contained `/tmp/promptune daemon start` or `python -m promptune daemon start`
  could be mistaken for the daemon if its PID was reused. `_is_daemon_process()`
  now verifies both command shape and the executable basename from
  `ps -o comm=`: console-script form requires `comm=promptune`, Python module
  form requires `comm=python*`, and shebang console scripts launched under
  Python remain accepted. Regressions:
  `test_is_daemon_process_rejects_slash_promptune_argument`,
  `test_is_daemon_process_rejects_python_module_words_as_args`,
  `test_is_daemon_process_accepts_python_comm_console_script`, and
  `test_is_daemon_process_accepts_capitalized_python_comm`.
- **MEDIUM** `daemon/daemon.py` — the PID `ps` helpers caught broad
  `Exception`, hiding unexpected programming/runtime errors as "not a daemon".
  They now catch only `OSError` and `subprocess.SubprocessError`, still
  returning `None` for normal `ps` failures/timeouts while surfacing unexpected
  failures. Regressions:
  `test_process_command_does_not_hide_unexpected_errors`,
  `test_process_name_does_not_hide_unexpected_errors`, and
  `test_process_helpers_return_none_for_ps_failures`.

### -7. PR #19 Codex revalidation scan (2026-06-19) — 3 findings [RESOLVED]

Full PR validation plus another code scan found three follow-up issues. Each fix
landed with a RED regression test first, targeted GREEN run, and full
lint/type/coverage/warning gates:

- **HIGH** `engine.py` / `dedup.py` — `_dedup_provider_model_routes()` used
  `None` for both "no provider/model filter" and "no AI route is possible".
  With `max_tier=0` or `max_tier=1` plus local LLM disabled, dedup could reuse a
  previous cloud/local AI result even though the current config can only produce
  tier 0. The engine now passes an empty route set for tier-0-only configs, so
  non-tier-0 history entries are excluded while true tier-0 entries remain
  universal. Regression:
  `test_engine_auto_dedup_does_not_reuse_ai_result_when_only_tier0_possible`.
- **HIGH** `daemon/daemon.py` — PID identity regex accepted any command line
  containing `-m promptune daemon start`, not just a Python module launch. A
  reused PID from another tool could therefore be treated as the Promptune
  daemon and killed by `stop_daemon()`. This was first tightened to recognized
  console-script/module launch forms; round--8 then added the current
  `ps -o comm=` executable-name boundary. Regression:
  `test_is_daemon_process_rejects_non_python_module_arg`.
- **LOW** docs — formatter removal still left stale current-state wording:
  README's config table advertised provider "format style", and the verification
  report still called the removed format flag a current no-op. README and report
  were corrected, with docs-readiness regressions covering public config docs
  and the stale report phrase.

### -6. Independent multi-agent re-audit (2026-06-19) — 6 findings [5 RESOLVED, 1 documented]

Continuation of the bug hunt (Claude). Running the full suite locally on macOS
first surfaced a **suite-wide hang**, then four parallel read-only review agents
audited the whole codebase by domain. Every fix landed with a RED regression
test first, a targeted GREEN run, then full lint/types/coverage gates.

- **HIGH (test/CI blocker)** `tests/test_daemon/test_daemon.py` — `test_already_running_exits_early`
  wrote the test's own PID to the daemon pidfile expecting an "already running"
  early exit. The round--5 `_is_daemon_process` hardening correctly rejects the
  pytest process (not a `promptune daemon start` argv), so `start_daemon()` fell
  through to a real `get_platform()` + `hotkey.listen()` and **blocked the whole
  suite forever on macOS**. CI only went green because headless Linux raises
  `PlatformError` and bailed early — the suite was never actually runnable on
  macOS. Test now mocks `_is_daemon_process=True` and asserts `get_platform` is
  never called (validates the real early-exit contract, no hang). Production
  code unchanged.
- **HIGH** `daemon/daemon.py` — `_is_daemon_process` false-negatived a real
  daemon whose interpreter/script path contains a space (common on macOS:
  `Library/Application Support`, a user's full name), because `ps -o command=`
  space-joins argv and `shlex.split` then split the path itself. Result: `stop`
  orphaned the live daemon (deleted pidfile/socket without killing) and `start`
  launched a duplicate. Replaced token parsing with path-space-robust command
  shape checks; round--8 added the current `ps -o comm=` executable-name
  boundary so plain arguments containing those words are still rejected.
- **HIGH** `cli.py` — `enhance --format {xml,markdown,plain}` was accepted but
  never written to `cfg["provider"]["format_style"]`, so the documented flag was
  a silent no-op. Initially wired into config; on consolidating PR #18 this was
  superseded by removing the dead formatter feature entirely (see the
  consolidation note below) — the flag, config key, and MCP arg are gone.
- **MEDIUM** `meta_prompt.py` — `detect_stack` over-matched common English via
  the inflection matcher (`nested`→typescript, `nodes`→javascript,
  `pipes`→python, `expressed`→javascript) with no count threshold, injecting a
  wrong tech stack into the LLM system prompt and template domain aliases.
  Collision-prone short keywords (`nest`/`node`/`pip`/`express`) now require an
  exact whole-word match.
- **MEDIUM** `preferences.py` — `_FORMAT_SUFFIXES` required the output-format
  hint at end-of-text, but later tier-0 rules (constraints, the `[Note: …]`
  short-prompt hint) append after it, so for low-quality prompts the hint was
  never at the end → `removes_format` learning was dead. Regex is now
  line-bounded and matches the hint paragraph wherever it sits.
- **LOW** `shell.py` — the Zsh/Bash/Fish IPC widget used `socat - UNIX-CONNECT:~/…`,
  but a mid-argument `~` is expanded by neither the shell nor socat, so CWD
  reports targeted a literal `~` path and never reached the daemon (which binds
  the expanded `$HOME` path). Now uses `$HOME`.
- **MEDIUM [documented, not fixed]** `daemon/daemon.py` / macOS — a SIGTERM from
  `stop_daemon()` may not interrupt `CFRunLoopRun()` (pyobjc rarely returns from
  it on signal delivery), so the in-process `_handle_term` handler may not fire
  and graceful stop falls back to the ~3s SIGKILL path. Impact is a stop delay +
  hard kill, **not** a leak (`stop_daemon` performs `_cleanup()` itself) and the
  SIGKILL fallback bounds it. A proper fix (CFRunLoop signal source / wakeup-fd)
  is macOS-runtime-specific and hard to unit-test; left as a known beta
  limitation.

Agent coverage that found **no** defects: providers / config / history /
context (timeouts, httpx context-managers, malformed-response guards, secret
redaction, SQLite parametrization & pruning, atomic `0o600` config write all
verified sound).

**Re-validation (second sub-agent pass over the round--6 fixes).** Four
read-only agents adversarially re-checked each fix; all five code fixes verified
correct and regression-free. Two further items surfaced:

- **MEDIUM** `meta_prompt.py` — `react` is the same class of English-collision
  keyword as `nest`/`node`/`pip`/`express` (`reacted`/`reacting` matched the
  React stack) but was not in the no-inflect set. Added `react` to
  `_NO_INFLECT_STACK_KEYWORDS` (exact `react`/`react.js` still detect). RED test
  added.
- **HIGH [RESOLVED by removal]** `formatter.py` was orphaned: imported only by
  its own test, never by the engine or providers. `format_style` flowed into
  dedup routing, the history row, and the reported JSON field, but **nothing
  shaped the actual enhanced text by format** — `build_system_prompt` takes no
  format argument and providers receive only `(prompt, system_prompt)`. This is
  the exact dead feature that open **PR #18 (`fix/validation-round5`)** set out
  to remove "per explicit user direction". Resolution (per user): consolidate
  PR #18 into this branch and close it — remove `formatter.py`, the `--format`
  flag, the `[provider] format_style` config key + validation + setup prompt,
  and the MCP `output_format` arg. `EnhanceResult.format_style` is kept as a
  vestigial `"auto"` and the nullable history column is kept (no DB migration).
  Dedup keeps its provider/model route separation (a Claude result is the wrong
  text for OpenAI regardless of format) but drops the now-meaningless
  `format_style` filter dimension. Docs (README, USER_GUIDE, ARCHITECTURE,
  MANUAL_TESTING, CLAUDE.md, config.example.toml) updated — which also fixes the
  P2 Codex-bot review comment on PR #18 about leftover format references in
  public docs.

### Consolidation of PR #18 (formatter removal) — [DONE]

PR #18 also bundled three correct non-formatter fixes, brought in here so closing
it loses nothing, each with a RED regression test:

- **HIGH** auto-enhance gate recorded every gated prompt as a confirmed
  `accept`, polluting dedup/preference learning (it has no accept/reject
  surface). `enhance()` gained `record: bool = True`; the gate calls
  `enhance(record=False)`.
- **HIGH** macOS `paste_result()` always returned `True` even when the synthetic
  Cmd+V was dropped for lack of accessibility trust, so the daemon clobbered the
  clipboard with the user's original. It now checks `check_accessibility()` and
  returns `False` (text stays on the clipboard), mirroring X11/Wayland.
- **LOW** `history.set_decision()` silently no-op'd on a pruned row; now
  debug-logs when `rowcount == 0`.

PR #18's P2 Codex review comment (leftover `output_format`/`format_style` in
README/USER_GUIDE/ARCHITECTURE/config.example.toml) is resolved by the doc
updates above. This branch supersedes PR #18.

### -5. Sub-agent revalidation follow-up (2026-06-19) — 7 findings [RESOLVED]

Independent read-only sub-agent validation found launch-readiness defects in
the round--4 fixes. Each item is now covered by a RED regression test and a
targeted GREEN run, followed by full lint/types/coverage/strict-warning gates:

- **HIGH** `daemon/daemon.py` — PID identity accepted any process command line
  containing the words `promptune` and `daemon`, so a reused PID could still be
  killed. `_is_daemon_process()` now parses argv and accepts only real
  `promptune daemon start` or `python -m promptune daemon start` command forms.
- **MEDIUM** `engine.py` — template aliases did not match doubled-consonant
  inflections such as `debugging`, so documented `intent: debug` templates could
  miss natural prompts. Template keyword matching now mirrors the meta-prompt
  inflection matcher.
- **MEDIUM** `engine.py` / `dedup.py` — auto-format dedup used one static route
  (`local`) even though default routing may record tier-0 or cloud fallback
  results. Dedup now receives the full set of possible AI provider/model routes,
  and true tier-0 entries remain universal by recorded `tier_used == 0`.
- **MEDIUM** `mcp/server.py` — explicit empty `style=""` or `format_style=""`
  bypassed validation. MCP validation now runs for any non-`None` override.
- **MEDIUM** `.coveragerc-linux` — Linux coverage config also omitted shared
  daemon modules (`ipc.py`, `prewarm.py`). Only platform-specific macOS modules
  remain omitted for Linux validation.
- **MEDIUM** `.github/workflows/release.yml` — manual branch dispatch could
  publish artifacts when `PUBLISH_TO_PYPI` was true, and GitHub Release could
  race PyPI publishing. Publish/release jobs are tag-gated, and GitHub Release
  now depends on successful PyPI publish.
- **LOW** `docs/MANUAL_TESTING.md` — auto-enhance manual tests still described
  the old block-and-copy behavior. Docs now match the current hook contract:
  exit 0 plus `additionalContext` JSON for low-quality prompts.

### -4. Beta bug-hunt audit (2026-06-18) — 15 findings [RESOLVED]
Parallel full-codebase audit plus local verification found and fixed launch-
readiness defects across core routing, daemon lifecycle, tests, docs, and CI.
All fixes landed with RED tests first, targeted GREEN runs, full coverage, and
strict warning verification:

- **HIGH** `engine.py` / `dedup.py` — `format_style="auto"` cache hits crossed
  provider/model changes, so a Claude/XML-shaped cached result could be reused
  after switching to OpenAI/Markdown. Auto-format dedup now filters by effective
  provider/model.
- **HIGH** `engine.py` / `templates.py` — documented `.prompts` values such as
  `intent: debug` and `domain: python` never matched because the engine only
  passed coarse `coding/general` labels. Template matching now accepts
  documented intent aliases and stack/domain aliases, and template variables
  reflect matched frontmatter when present.
- **MEDIUM** `cli.py` / `mcp/server.py` — invalid style or format overrides were
  accepted silently, dropping AI guidance. CLI now uses `click.Choice`; MCP tool
  args validate against config vocab before calling the engine.
- **MEDIUM** `tests/test_daemon/test_clipboard.py` — one sleep-duration test
  touched real `pbcopy`/`pbpaste`, mutating the user's clipboard in elevated
  runs. The test now mocks the clipboard write/read boundary.
- **HIGH** `pyproject.toml` / `.coveragerc-linux` / CI — global coverage omit
  hid macOS daemon modules even on macOS, while the report claimed their
  coverage. The global omit is gone; Linux CI uses `.coveragerc-linux` only for
  Linux's macOS-only imports.
- **MEDIUM** `.github/workflows/release.yml` — release validation skipped the
  Xvfb-backed X11 integration job. Release now runs the same X11 smoke matrix
  before build.
- **MEDIUM** `.github/workflows/release.yml` — release built artifacts without
  validating the wheel users install. Build now runs `twine check`, installs the
  built wheel into a temp venv, and smokes `promptune --version` plus
  `python -m promptune --help`.
- **MEDIUM** docs — unquoted `promptune[extra]` install hints broke in zsh.
  README, user docs, manual testing, architecture docs, and MCP error text now
  quote extras.
- **MEDIUM** docs/CI — coverage gate drifted between README (89%) and CI/report
  (85%). Docs/readiness tests now enforce one value.
- **HIGH** `daemon/daemon.py` — `stop_daemon()` trusted a live PID without
  process identity, risking SIGTERM/SIGKILL to an unrelated reused PID. Stop,
  start, and status now verify a live promptune daemon command before trusting
  the PID file.
- **HIGH** `daemon/daemon.py` — a normal `hotkey.listen()` return skipped
  cleanup, leaving PID/socket state and prewarm timer alive. `start_daemon()`
  now cancels prewarm, stops the hotkey backend, and removes runtime files in a
  `finally` block.
- **MEDIUM** `daemon/prewarm.py` — `_RepeatingTimer` let callback exceptions
  kill the daemon thread and surface `PytestUnhandledThreadExceptionWarning`.
  The timer now logs callback failures and continues until cancelled.
- **HIGH** `daemon/hotkey.py` — macOS event taps disabled by timeout/user input
  were never re-enabled, so the global hotkey could silently die. Disabled tap
  events now call `CGEventTapEnable(..., True)`.
- **MEDIUM** `daemon/launchagent.py` — login item install did not create the log
  parent directory referenced by the plist. Install now creates `LOG_FILE.parent`.
- **P2** `daemon/ipc.py` — accurate macOS coverage exposed IPC at 88%, below the
  per-module target. Added timeout, bind-failure, and malformed-response tests;
  module coverage is now 93%.

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
function.

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

### 8. ~~Prewarm timer emits thread exception warnings (P2)~~ [RESOLVED]
**Severity:** Medium
**Test:** `tests/test_daemon/test_prewarm.py::TestStartPrewarmTimer::test_cancel_stops_repeating_chain`
**Symptom:** Full suite passes but emits 4 `PytestUnhandledThreadExceptionWarning` warnings.
**Cause:** A repeating timer can call `prewarm_ollama()` after test cancellation; the test mock leaves `httpx.HTTPStatusError` as a non-exception object in that background path.
**Fixed:** `_RepeatingTimer.run()` now catches/logs callback exceptions and continues until cancelled. Verified with `-W error::pytest.PytestUnhandledThreadExceptionWarning`.

---

## Remaining Work

| Priority | Item | Status | Notes |
|----------|------|--------|-------|
| ~~P2~~ | ~~Dedup provider/model filter mismatch (finding -5/-7)~~ | ✅ Done | Auto-format dedup allows possible AI routes, excludes AI history when only tier 0 is possible, and keeps true tier-0 entries universal |
| ~~P0~~ | ~~Fix 33 ruff lint errors~~ | ✅ Done | 0 errors |
| ~~P0~~ | ~~Improve `cli.py` coverage 67% → ≥90%~~ | ✅ Done | 98% |
| ~~P1~~ | ~~Fix SQLite `ResourceWarning`~~ | ✅ Done | Idempotent close + lifecycle |
| ~~P1~~ | ~~Improve `hotkey.py` 69% → ≥90%~~ | ✅ Done | 100% |
| ~~P1~~ | ~~Improve `ipc.py` 82% → ≥90%~~ | ✅ Done | 93% |
| ~~P1~~ | ~~Improve `daemon.py` 83% → ≥90%~~ | ✅ Done | 95% |
| ~~P2~~ | ~~Improve `engine.py` 86% → ≥90%~~ | ✅ Done | 97% |
| ~~P2~~ | ~~Improve `collectors.py` 85% → ≥90%~~ | ✅ Done | 100% |
| ~~P2~~ | ~~Add `__main__.py` smoke test~~ | ✅ Done | 100% (runpy) |
| ~~P2~~ | ~~Improve `templates.py` 89% → ≥90%~~ | ✅ Done | 93% |
| ~~P1~~ | ~~Improve `gate.py` 69% → ≥90%~~ | ✅ Done | 100% |
| ~~P1~~ | ~~Improve `mcp/server.py` 53% → ≥90%~~ | ✅ Done | 100% |
| P2 | Add missing PARTIAL test scenarios | Deferred | Task #6 |
| ~~P2~~ | ~~Fix prewarm timer thread warning~~ | ✅ Done | Timer callback exceptions contained; strict warning run clean |
| ~~P3~~ | ~~Improve `linux_x11.py` 46% → ≥70%~~ | ✅ Done | 100% mocked + Xvfb CI |
| ~~P3~~ | ~~Improve `linux_wayland.py` 51% → ≥70%~~ | ✅ Done | 96% mocked; hardware sign-off still manual |

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
Coverage gate is enforced with `--cov-fail-under=85` (now passing at 97.38%).
Linux CI uses `.coveragerc-linux` so macOS-only daemon modules are omitted only
on Linux; local macOS coverage includes and measures those modules.
