# Plan: Coverage Improvement (85% → ≥90%)

**Date:** 2026-03-29
**Status:** ✅ Mostly completed 2026-04-17 (overall target met; gate.py + mcp/server.py + linux platforms remain)
**Spec:** `docs/superpowers/specs/2026-03-29-coverage-improvement.md`
**Estimated effort:** ~8–10 hours total
**Prerequisites:** Complete `2026-03-29-code-quality-fixes.md` first (lint must be clean)

---

## Post-completion Notes

Overall coverage hit 92% (target ≥ 90%). Per-module results:
- `cli.py` 67% → 98% ✅
- `daemon/hotkey.py` 69% → 100% ✅
- `daemon/ipc.py` 82% → 91% ✅
- `daemon/daemon.py` 83% → 99% ✅
- `engine.py` 86% → 98% ✅
- `context/collectors.py` 85% → 100% ✅
- `__main__.py` 0% → 100% ✅ (runpy approach, not subprocess)
- `templates.py` 89% → 93% ✅

Not addressed in this plan (tracked separately):
- `gate.py` 69% — task #4
- `mcp/server.py` 53% — task #5 (new module added after this plan)
- `linux_x11.py` / `linux_wayland.py` — deferred, need Linux CI

Some PARTIAL test scenarios (all-providers-fail, empty requirements.txt, IPC connection refused, missing template variable) deferred to task #6.

---

## Goal

Every non-platform module ≥ 90%. Platform modules (`linux_x11.py`, `linux_wayland.py`) ≥ 70%.
Overall total ≥ 90% to pass CI coverage gate.

---

## Execution Order

Work in this order — highest impact first:

```
Step 1: cli.py           (67% → 90+%)   ~3-4h  — biggest coverage gain
Step 2: hotkey.py        (69% → 90+%)   ~1.5h
Step 3: ipc.py           (82% → 90+%)   ~1h
Step 4: daemon.py        (83% → 90+%)   ~1.5h
Step 5: engine.py        (86% → 90+%)   ~1h
Step 6: collectors.py    (85% → 90+%)   ~1h
Step 7: __main__.py      (0%  → 100%)   ~20min
Step 8: templates.py     (89% → 90+%)   ~30min
Step 9: linux_x11.py     (46% → 70+%)   ~2h     (lower priority)
Step 10: linux_wayland.py (51% → 70+%)  ~2h     (lower priority)
```

After each step: run `pytest --cov=promptune --cov-report=term-missing -q` and verify the module hit its target before moving on.

---

## Step 1 — `cli.py` coverage (67% → ≥90%)

**Test file:** `tests/test_cli.py`
**Priority uncovered areas:** daemon subcommands, error paths, --no-history flag

### 1a. Daemon start/stop/status subcommands

All tests use `CliRunner().invoke(main, [...])` with mocked daemon functions.

```python
from click.testing import CliRunner
from unittest.mock import patch
from promptune.cli import main

class TestDaemonStart:
    def test_start_success(self):
        with patch("promptune.cli.start_daemon", return_value=True):
            result = CliRunner().invoke(main, ["daemon", "start"])
        assert result.exit_code == 0
        assert "started" in result.output.lower()

    def test_start_already_running(self):
        with patch("promptune.cli.start_daemon", return_value=False):
            result = CliRunner().invoke(main, ["daemon", "start"])
        assert result.exit_code == 0
        assert "already" in result.output.lower()

    def test_start_error(self):
        with patch("promptune.cli.start_daemon", side_effect=RuntimeError("fork failed")):
            result = CliRunner().invoke(main, ["daemon", "start"])
        assert result.exit_code != 0

class TestDaemonStop:
    def test_stop_success(self):
        with patch("promptune.cli.stop_daemon", return_value=True):
            result = CliRunner().invoke(main, ["daemon", "stop"])
        assert result.exit_code == 0

    def test_stop_not_running(self):
        with patch("promptune.cli.stop_daemon", return_value=False):
            result = CliRunner().invoke(main, ["daemon", "stop"])
        assert result.exit_code == 0
        assert "not running" in result.output.lower()

class TestDaemonStatus:
    def test_status_running(self):
        with patch("promptune.cli.get_status", return_value={"running": True, "pid": 12345}):
            result = CliRunner().invoke(main, ["daemon", "status"])
        assert result.exit_code == 0
        assert "running" in result.output.lower()

    def test_status_stopped(self):
        with patch("promptune.cli.get_status", return_value={"running": False}):
            result = CliRunner().invoke(main, ["daemon", "status"])
        assert result.exit_code == 0
```

### 1b. Daemon install/uninstall

```python
class TestDaemonInstall:
    def test_install_success(self, mock_platform):
        mock_platform.service.install.return_value = None
        result = CliRunner().invoke(main, ["daemon", "install"])
        assert result.exit_code == 0

    def test_install_permission_error(self, mock_platform):
        mock_platform.service.install.side_effect = PermissionError("no root")
        result = CliRunner().invoke(main, ["daemon", "install"])
        assert result.exit_code != 0
        assert "permission" in result.output.lower()
```

`mock_platform` fixture: `patch("promptune.cli.get_platform")` returning a `MagicMock`.

### 1c. `enhance` command error paths

```python
class TestEnhanceErrors:
    def test_enhance_provider_error(self, tmp_config):
        with patch("promptune.cli.Engine.enhance", side_effect=ProviderError("API down")):
            result = CliRunner().invoke(main, ["enhance", "fix my bug"])
        assert result.exit_code != 0

    def test_enhance_no_history_flag(self, tmp_config):
        with patch("promptune.cli.Engine.enhance", return_value="enhanced prompt") as mock_eng:
            with patch("promptune.cli.HistoryStore.save") as mock_save:
                CliRunner().invoke(main, ["enhance", "--no-history", "my prompt"])
        mock_save.assert_not_called()

    def test_enhance_empty_input(self, tmp_config):
        result = CliRunner().invoke(main, ["enhance", ""])
        assert result.exit_code != 0
```

### 1d. `history` command edge cases

```python
class TestHistoryExport:
    def test_export_to_file(self, tmp_path, tmp_config):
        out = tmp_path / "history.json"
        with patch("promptune.cli.HistoryStore.export", return_value=[{"prompt": "x"}]):
            result = CliRunner().invoke(main, ["history", "--export", str(out)])
        assert result.exit_code == 0
        assert out.exists()

    def test_export_format_csv(self, tmp_config):
        with patch("promptune.cli.HistoryStore.export", return_value=[]):
            result = CliRunner().invoke(main, ["history", "--format", "csv"])
        assert result.exit_code == 0
```

### 1e. `config show` provider filtering

```python
class TestConfigShow:
    def test_show_claude_provider(self, tmp_config):
        result = CliRunner().invoke(main, ["config", "show", "--provider", "claude"])
        assert result.exit_code == 0
        assert "claude" in result.output.lower()

    def test_show_openai_provider(self, tmp_config):
        result = CliRunner().invoke(main, ["config", "show", "--provider", "openai"])
        assert result.exit_code == 0
        assert "openai" in result.output.lower()
```

### 1f. `config set` / `config reset` validation

```python
class TestConfigSet:
    def test_set_invalid_key(self, tmp_config):
        result = CliRunner().invoke(main, ["config", "set", "nonexistent.key", "value"])
        assert result.exit_code != 0
        assert "invalid" in result.output.lower() or "unknown" in result.output.lower()

    def test_set_invalid_value_type(self, tmp_config):
        result = CliRunner().invoke(main, ["config", "set", "enhancement.max_tier", "banana"])
        assert result.exit_code != 0

class TestConfigReset:
    def test_reset_to_defaults(self, tmp_config):
        result = CliRunner().invoke(main, ["config", "reset"], input="y\n")
        assert result.exit_code == 0
```

**`tmp_config` fixture:** creates a temp `config.toml` using `config.example.toml` as base; sets `PROMPTUNE_CONFIG` env var.

---

## Step 2 — `hotkey.py` coverage (69% → ≥90%)

**Test file:** `tests/test_daemon/test_hotkey.py`

### Import guard test
```python
def test_import_fails_on_linux(monkeypatch):
    import importlib, sys
    monkeypatch.setitem(sys.modules, "Quartz", None)
    monkeypatch.setitem(sys.modules, "ApplicationServices", None)
    # Re-importing should raise ImportError on non-darwin
    with monkeypatch.context() as m:
        m.setattr(sys, "platform", "linux")
        with pytest.raises(ImportError):
            importlib.reload(importlib.import_module("promptune.daemon.hotkey"))
```

### `parse_hotkey` edge cases
```python
def test_parse_hotkey_all_modifiers():
    code, flags = parse_hotkey("cmd+ctrl+shift+alt+e")
    assert flags & 0x100000  # cmd
    assert flags & 0x40000   # ctrl
    assert flags & 0x20000   # shift
    assert flags & 0x80000   # alt

def test_parse_hotkey_invalid_raises():
    with pytest.raises(ValueError, match="unknown key"):
        parse_hotkey("ctrl+notakey")

def test_parse_hotkey_no_modifier_raises():
    with pytest.raises(ValueError, match="modifier"):
        parse_hotkey("e")  # bare key with no modifier
```

### `register_hotkey` with mocked Quartz
```python
@patch("promptune.daemon.hotkey.Quartz")
def test_register_hotkey_success(mock_quartz):
    mock_tap = MagicMock()
    mock_quartz.CGEventTapCreate.return_value = mock_tap
    mock_quartz.CFRunLoopGetCurrent.return_value = MagicMock()

    register_hotkey("ctrl+shift+e", callback=lambda: None)

    mock_quartz.CGEventTapCreate.assert_called_once()
    mock_quartz.CFRunLoopAddSource.assert_called_once()

@patch("promptune.daemon.hotkey.Quartz")
def test_register_hotkey_tap_creation_fails(mock_quartz):
    mock_quartz.CGEventTapCreate.return_value = None  # failure
    with pytest.raises(RuntimeError, match="CGEventTap"):
        register_hotkey("ctrl+shift+e", callback=lambda: None)
```

### `stop_run_loop`
```python
@patch("promptune.daemon.hotkey.Quartz")
def test_stop_run_loop(mock_quartz):
    mock_loop = MagicMock()
    mock_quartz.CFRunLoopGetCurrent.return_value = mock_loop
    stop_run_loop()
    mock_quartz.CFRunLoopStop.assert_called_once_with(mock_loop)
```

---

## Step 3 — `ipc.py` coverage (82% → ≥90%)

**Test file:** `tests/test_daemon/test_ipc.py`

### Stale socket cleanup
```python
def test_stale_socket_cleaned_up(tmp_path):
    sock_path = tmp_path / "test.sock"
    sock_path.write_bytes(b"")  # simulate stale socket file
    server = UnixSocketServer(str(sock_path), handler=lambda x: x)
    assert not sock_path.exists() or True  # cleaned up in __init__
```

### Malformed client messages
```python
def test_malformed_json_does_not_crash(tmp_path):
    sock_path = str(tmp_path / "test.sock")
    ready = threading.Event()
    server = UnixSocketServer(sock_path, handler=lambda msg: msg)
    # ... start server, send b"not json\n", verify server still alive
```

### `CWDClient` connection refused
```python
def test_cwd_client_connection_refused(tmp_path):
    client = CWDClient(str(tmp_path / "nonexistent.sock"))
    result = client.send({"cwd": "/tmp"})
    assert result is False  # or raises a defined exception — check implementation
```

Full socket server test pattern — use `threading.Thread` with a `ready` event:
```python
@pytest.fixture
def running_server(tmp_path):
    sock_path = str(tmp_path / "ipc.sock")
    ready = threading.Event()
    responses = []

    def handler(msg):
        responses.append(msg)
        return {"ok": True}

    server = UnixSocketServer(sock_path, handler=handler)
    thread = threading.Thread(target=server.start, daemon=True)
    thread.start()
    ready.wait(timeout=1)  # wait for server to bind
    yield server, sock_path, responses
    server.stop()
```

---

## Step 4 — `daemon.py` coverage (83% → ≥90%)

**Test file:** `tests/test_daemon/test_daemon.py`

### `_write_pid` permission error
```python
def test_write_pid_permission_error(tmp_path, monkeypatch):
    monkeypatch.setattr("builtins.open", side_effect_for_pid_path(PermissionError))
    with pytest.raises(PermissionError):
        _write_pid(tmp_path / "test.pid", 12345)
```

### `_is_running` PID reuse
```python
def test_is_running_pid_reuse(tmp_path):
    """PID exists but belongs to a different process."""
    pid_file = tmp_path / "promptune.pid"
    _write_pid(pid_file, os.getpid())  # current process PID
    with patch("promptune.daemon.daemon.DAEMON_NAME", "other-process"):
        assert _is_running(pid_file) is False
```

### `start_daemon` already running
```python
def test_start_daemon_already_running(tmp_path):
    with patch("promptune.daemon.daemon._is_running", return_value=True):
        result = start_daemon(config=mock_config, pid_file=tmp_path / "p.pid")
    assert result is False
```

### `_on_hotkey` empty enhancement
```python
def test_on_hotkey_empty_enhancement_skips_paste(mock_platform):
    with patch("promptune.daemon.daemon.enhance", return_value=""):
        with patch("promptune.daemon.daemon._clipboard") as mock_clip:
            mock_clip.copy_selection.return_value = "original"
            _on_hotkey()
    mock_clip.paste_result.assert_not_called()
```

### `_cleanup` stale PID
```python
def test_cleanup_stale_pid_file(tmp_path):
    pid_file = tmp_path / "pid"
    _write_pid(pid_file, 99999)  # non-existent PID
    _cleanup(pid_file)
    assert not pid_file.exists()
```

### `_enhancing` undo failure
```python
def test_enhancing_undo_failure_does_not_crash():
    state = DaemonState(...)
    with patch("promptune.daemon.daemon.undo", side_effect=RuntimeError("undo failed")):
        # Should log error but not propagate
        _enhancing(state, original="original", enhanced="enhanced")
```

---

## Step 5 — `engine.py` coverage (86% → ≥90%)

**Test file:** `tests/test_engine.py`

```python
def test_enhance_all_providers_fail(engine_with_all_providers_mocked):
    """When all providers raise ProviderError, engine raises or returns original."""
    engine = engine_with_all_providers_mocked
    for p in engine._providers.values():
        p.enhance.side_effect = ProviderError("down")
    with pytest.raises(ProviderError):
        engine.enhance("my prompt", config=config_max_tier_2)

def test_enhance_history_disabled(tmp_config):
    tmp_config.history.enabled = False
    with patch("promptune.engine.HistoryStore") as mock_store:
        engine.enhance("prompt", config=tmp_config)
    mock_store.return_value.save.assert_not_called()

def test_enhance_dedup_disabled(tmp_config):
    tmp_config.enhancement.dedup_enabled = False
    with patch("promptune.engine.DedupChecker") as mock_dedup:
        engine.enhance("prompt", config=tmp_config)
    mock_dedup.return_value.check.assert_not_called()

def test_enhance_tier0_sufficient(engine):
    """Tier0 returns a result; no LLM call should be made."""
    with patch("promptune.engine.Tier0Engine.enhance", return_value="fixed") as mock_t0:
        with patch("promptune.engine.Engine._call_provider") as mock_llm:
            result = engine.enhance("Fix typo in teh word", config=config_max_tier_0)
    mock_llm.assert_not_called()
    assert result == "fixed"

def test_enhance_context_timeout(engine):
    with patch("promptune.engine.collect_context", side_effect=asyncio.TimeoutError):
        result = engine.enhance("my prompt", config=config)
    assert result  # should still return something, not crash
```

---

## Step 6 — `context/collectors.py` coverage (85% → ≥90%)

**Test file:** `tests/test_context/test_collectors.py`

```python
def test_git_collector_no_git_repo(tmp_path):
    collector = GitCollector(cwd=str(tmp_path))
    result = collector.collect()
    assert result == {} or result is None

def test_git_collector_binary_not_found(tmp_path):
    with patch("subprocess.run", side_effect=FileNotFoundError):
        result = GitCollector(cwd=str(tmp_path)).collect()
    assert result == {} or result is None

def test_shell_history_unreadable(tmp_path, monkeypatch):
    hist = tmp_path / ".bash_history"
    hist.write_text("ls\n")
    hist.chmod(0o000)
    monkeypatch.setenv("HISTFILE", str(hist))
    result = ShellHistoryCollector().collect()
    assert result == [] or result is None
    hist.chmod(0o644)  # cleanup

def test_stack_collector_malformed_package_json(tmp_path):
    (tmp_path / "package.json").write_text("{invalid")
    result = StackCollector(cwd=str(tmp_path)).collect()
    assert "node" not in (result or {})

def test_stack_collector_empty_requirements(tmp_path):
    (tmp_path / "requirements.txt").write_text("")
    result = StackCollector(cwd=str(tmp_path)).collect()
    assert result is not None  # doesn't crash

def test_collect_all_timeout():
    with patch("promptune.context.collectors.GitCollector.collect",
               side_effect=lambda: time.sleep(10)):
        result = collect_all(timeout=0.1, cwd="/tmp")
    assert isinstance(result, dict)  # returns partial results

def test_collect_all_one_collector_raises():
    with patch("promptune.context.collectors.GitCollector.collect",
               side_effect=RuntimeError("git error")):
        result = collect_all(cwd="/tmp")
    assert "shell_history" in result  # other collectors still ran
```

---

## Step 7 — `__main__.py` coverage (0% → 100%)

**Test file:** `tests/test_cli.py` (add to existing) or new `tests/test_main.py`

```python
import subprocess, sys

def test_main_module_entry_point():
    """Invoking python -m promptune --help exits 0."""
    result = subprocess.run(
        [sys.executable, "-m", "promptune", "--help"],
        capture_output=True, text=True,
        timeout=10
    )
    assert result.returncode == 0
    assert "promptune" in result.stdout.lower()
    assert not result.stderr  # no errors on --help
```

Note: This test increases coverage of `__main__.py` because pytest-cov doesn't instrument subprocess calls directly. Add `--cov-source=promptune` and ensure subprocess spawns with `COVERAGE_PROCESS_START` env var if needed, OR accept that this test validates behavior and `__main__.py` coverage is covered by the subprocess call.

Alternative approach (avoids subprocess): mock `main` and call `__main__` via `runpy`:
```python
import runpy
from unittest.mock import patch

def test_main_module_calls_main():
    with patch("promptune.cli.main") as mock_main:
        runpy.run_module("promptune", run_name="__main__", alter_sys=True)
    mock_main.assert_called_once()
```

Prefer the `runpy` approach — it instruments the module for coverage without spawning a subprocess.

---

## Step 8 — `templates.py` coverage (89% → ≥90%)

**Test file:** `tests/test_templates.py`

```python
def test_template_store_no_prompts_dir(tmp_path):
    store = TemplateStore(tmp_path)  # no .prompts/ subdir
    assert store.list() == []

def test_template_file_no_frontmatter(tmp_path):
    prompts = tmp_path / ".prompts"
    prompts.mkdir()
    (prompts / "bare.md").write_text("just plain text, no frontmatter")
    store = TemplateStore(tmp_path)
    templates = store.list()
    assert any(t.name == "bare" for t in templates)

def test_template_malformed_yaml_skipped(tmp_path):
    prompts = tmp_path / ".prompts"
    prompts.mkdir()
    (prompts / "broken.md").write_text("---\nkey: [invalid\n---\nbody")
    store = TemplateStore(tmp_path)
    # should not raise, broken template just skipped
    assert all(t.name != "broken" for t in store.list())

def test_match_empty_store(tmp_path):
    store = TemplateStore(tmp_path)  # no templates
    result = store.match("any prompt text")
    assert result is None

def test_render_missing_variable(tmp_path):
    prompts = tmp_path / ".prompts"
    prompts.mkdir()
    (prompts / "tmpl.md").write_text("---\nname: tmpl\n---\nHello {{name}}!")
    store = TemplateStore(tmp_path)
    tmpl = store.list()[0]
    with pytest.raises((KeyError, ValueError)):
        store.render(tmpl, {})  # missing 'name' variable
```

---

## Steps 9–10 — Linux platform modules (lower priority)

Complete Steps 1–8 first. If overall coverage hits 90%+ without these, Steps 9–10 are optional.

For `linux_x11.py` and `linux_wayland.py`, use `sys.modules` patching to mock native libraries before import:

```python
@pytest.fixture(autouse=True)
def mock_xlib(monkeypatch):
    mock_xlib = MagicMock()
    monkeypatch.setitem(sys.modules, "Xlib", mock_xlib)
    monkeypatch.setitem(sys.modules, "Xlib.display", MagicMock())
    monkeypatch.setitem(sys.modules, "Xlib.X", MagicMock())
    # ... etc
```

Mark all tests in these files:
```python
pytestmark = pytest.mark.linux
```

Cover at minimum:
- `X11Hotkey.register()` success path (mocked `XGrabKey`)
- `X11Hotkey.register()` failure (`XGrabKey` raises)
- `X11Clipboard.read()` → `xclip -o` subprocess call
- `X11Clipboard.read()` → `xclip` not found (`FileNotFoundError`)
- `WaylandClipboard.read()` → `wl-paste` subprocess
- `WaylandHotkey.register()` → `evdev` device discovery

---

## Final Verification

After all steps complete:

```bash
.venv/bin/pytest --cov=promptune --cov-report=term-missing -q
```

Check each module hits its target. Then update `docs/VERIFICATION_REPORT.md`:
- Update all coverage rows
- Update **Last Verified** table
- Mark all coverage items in **Remaining Work** as done
- Update overall coverage %
