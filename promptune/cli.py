"""CLI entry point for promptune."""

from __future__ import annotations

import json as json_mod
import os
import sys
from pathlib import Path
from typing import Any

import click

from promptune import __version__
from promptune.config import (
    VALID_PROVIDERS,
    ConfigError,
    default_config_path,
    generate_default_config,
    load_config,
)
from promptune.engine import enhance
from promptune.gate import run_gate
from promptune.history import HistoryStore
from promptune.hooks import get_installers
from promptune.mcp.server import run_server as run_mcp_server
from promptune.preferences import (
    analyse_edit_patterns,
    analyse_rule_preferences,
)
from promptune.providers import (
    ProviderError,
    redact_url_userinfo,
    redact_url_userinfo_in_text,
)
from promptune.scorer import score_prompt
from promptune.shell import generate_widget


def _get_config_path() -> Path:
    """Get the config file path."""
    return default_config_path()


def _is_interactive() -> bool:
    """Check if stdin is interactive (TTY)."""
    return sys.stdin.isatty()


class _PromptuneGroup(click.Group):
    """Click group that turns a malformed-config error into a clean message.

    Without this, any command that calls ``load_config`` (config show,
    doctor, history, …) would dump a raw ConfigError traceback when the
    user's config file is invalid.
    """

    def invoke(self, ctx: click.Context) -> object:
        try:
            return super().invoke(ctx)
        except ConfigError as e:
            click.echo(f"Error: {e}", err=True)
            raise SystemExit(1) from e


@click.group(cls=_PromptuneGroup)
@click.version_option(__version__, "-V", "--version", prog_name="promptune")
def main() -> None:
    """Promptune — terminal prompt enhancer."""


@main.command()
def version() -> None:
    """Print the version."""
    click.echo(__version__)


@main.command("enhance")
@click.argument("prompt", required=False)
@click.option(
    "--provider",
    "-p",
    default=None,
    help="Override default provider.",
)
@click.option(
    "--style",
    "-s",
    type=click.Choice(["minimal", "balanced", "detailed"]),
    default=None,
    help="Override default style.",
)
@click.option(
    "--no-tui",
    is_flag=True,
    default=False,
    help="Print enhanced prompt directly.",
)
@click.option(
    "--tier",
    type=click.IntRange(0, 2),
    default=None,
    help="Force specific tier (0/1/2).",
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Output structured JSON.",
)
def enhance_cmd(
    prompt: str | None,
    provider: str | None,
    style: str | None,
    no_tui: bool,
    tier: int | None,
    json_output: bool,
) -> None:
    """Enhance a prompt using AI."""
    if not prompt:
        prompt = (
            sys.stdin.read().strip()
            if not sys.stdin.isatty()
            else ""
        )

    if not prompt:
        click.echo(
            "Error: Empty prompt.", err=True
        )
        raise SystemExit(1)

    try:
        cfg = load_config()

        if provider:
            cfg["provider"]["default"] = provider
        if style:
            cfg["enhancement"]["default_mode"] = style

        result = enhance(
            prompt,
            cfg,
            provider_override=provider,
            tier_override=tier,
        )

        if json_output:
            output = {
                "original": result.original,
                "enhanced": result.enhanced,
                "tier_used": result.tier_used,
                "latency_ms": round(
                    result.latency_ms, 1
                ),
                "score_before": round(
                    result.score_before.total
                ),
                "score_after": round(
                    result.score_after.total
                ),
                "rules_applied": result.rules_applied,
                "rules_explained": [
                    {"rule": name, "reason": desc}
                    for name, desc in result.rules_explained
                ],
            }
            click.echo(json_mod.dumps(output, indent=2))
            return

        if no_tui:
            click.echo(result.enhanced)
            return

        from promptune.tui import display_result

        final = display_result(result)

        # The enhancement was recorded as "accept" by the engine before the user
        # acted. Correct it to the real decision now so dedup never resurfaces a
        # rejected result and preference learning sees true outcomes.
        if result.history_id is not None:
            if final is None:
                _update_history_decision(
                    cfg, result.history_id, "reject", None
                )
            elif final != result.enhanced:
                _update_history_decision(
                    cfg, result.history_id, "edit", final
                )

        if final:
            click.echo(final)
        else:
            raise SystemExit(1)

    except KeyboardInterrupt:
        click.echo("\nCancelled.", err=True)
        raise SystemExit(130) from None
    except (ConfigError, ProviderError) as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1) from e


@main.command("score")
@click.argument("prompt", required=False)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Output structured JSON.",
)
def score_cmd(
    prompt: str | None, json_output: bool
) -> None:
    """Score a prompt across 7 quality dimensions."""
    if not prompt:
        prompt = (
            sys.stdin.read().strip()
            if not sys.stdin.isatty()
            else ""
        )
    if not prompt:
        click.echo("Error: Empty prompt.", err=True)
        raise SystemExit(1)

    result = score_prompt(prompt)

    if json_output:
        output = {
            "total": result.total,
            "intent": result.intent,
            "dimensions": {
                name: {
                    "score": round(dim.score, 3),
                    "weight": dim.max_weight,
                    "suggestion": dim.suggestion,
                }
                for name, dim in result.dimensions.items()
            },
        }
        click.echo(json_mod.dumps(output, indent=2))
        return

    click.echo(f"  PQS: {result.total}/100  [{result.intent}]")
    click.echo()
    for name, dim in result.dimensions.items():
        pct = int(dim.score * 100)
        click.echo(
            f"  {name:<16} {pct:>3}%  — {dim.suggestion}"
        )


@main.command("gate", hidden=True)
def gate_cmd() -> None:
    """Auto-enhance gate hook (reads JSON from stdin)."""
    import json as _json

    try:
        raw = sys.stdin.read()
        data = _json.loads(raw)
        prompt = data.get("prompt", "") if isinstance(data, dict) else ""
    except ValueError:
        raise SystemExit(0) from None

    if not prompt:
        raise SystemExit(0)

    try:
        cfg = load_config()
    except ConfigError:
        raise SystemExit(0) from None

    code = run_gate(prompt, cfg)
    raise SystemExit(code)


@main.command("mcp")
def mcp_cmd() -> None:
    """Start the MCP server (stdio transport for AI tools)."""
    try:
        run_mcp_server()
    except ImportError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1) from e


class _ConfigGroup(click.Group):
    def resolve_command(
        self, ctx: click.Context, args: list[str]
    ) -> tuple[str | None, click.Command | None, list[str]]:
        # A positional token after ``--set-key`` is a misplaced API key value
        # (a subcommand name slot, as far as Click is concerned). Reject it
        # generically *before* Click's default "No such command '<value>'"
        # error can echo the secret. This runs ahead of the group callback,
        # and uses only public Click API (no reliance on Context internals).
        if ctx.params.get("set_key"):
            raise click.UsageError(
                "API keys must be entered at the hidden prompt, "
                "not passed as command arguments."
            )
        return super().resolve_command(ctx, args)


@main.group(
    cls=_ConfigGroup,
    invoke_without_command=True,
    context_settings={
        "ignore_unknown_options": True,
        "allow_extra_args": True,
    },
)
@click.option(
    "--set-key",
    type=str,
    default=None,
    metavar="<provider>",
    help="Set API key via hidden prompt: --set-key <provider>",
)
@click.option(
    "--set-tier",
    type=click.IntRange(0, 2),
    default=None,
    help="Set max tier (0/1/2)",
)
@click.option(
    "--reset",
    is_flag=True,
    help="Reset config to defaults",
)
@click.pass_context
def config(
    ctx: click.Context,
    set_key: str | None,
    set_tier: int | None,
    reset: bool,
) -> None:
    """Manage promptune configuration."""
    if ctx.invoked_subcommand is not None:
        return

    if sum(bool(x) for x in (set_key, set_tier is not None, reset)) > 1:
        raise click.UsageError(
            "--set-key, --set-tier, and --reset are mutually exclusive."
        )

    config_path = _get_config_path()

    if reset:
        if click.confirm("Reset config to defaults?"):
            _secure_write_text(
                config_path, generate_default_config()
            )
            click.echo("Config reset to defaults.")
        return

    if set_key:
        provider_name = set_key
        if provider_name not in VALID_PROVIDERS:
            raise click.UsageError(
                f"Unknown provider '{provider_name}'. "
                f"Valid: {', '.join(sorted(VALID_PROVIDERS))}."
            )
        key_value = click.prompt(
            f"{provider_name} API key",
            hide_input=True,
            confirmation_prompt=False,
        )
        _update_config_value(
            config_path,
            f"api_keys.{provider_name}",
            key_value,
        )
        click.echo(
            f"API key set for {provider_name}."
        )
        return

    if set_tier is not None:
        _update_config_value(
            config_path,
            "enhancement.max_tier",
            set_tier,
        )
        click.echo(f"Max tier set to {set_tier}.")
        return


def _secure_write_text(config_path: Path, text: str) -> None:
    """Atomically write a config file with owner-only (0o600) permissions.

    Config may contain plaintext API keys, so it must never be world/group
    readable. Mirrors the hook installer's secure-write pattern.
    """
    config_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = config_path.with_suffix(config_path.suffix + ".tmp")
    # Create the temp file 0o600 from the start (no world-readable window
    # between write and chmod).
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(text)
    os.chmod(tmp, 0o600)
    os.replace(tmp, config_path)


_TOML_ESCAPES = {
    "\\": "\\\\",
    '"': '\\"',
    "\b": "\\b",
    "\t": "\\t",
    "\n": "\\n",
    "\f": "\\f",
    "\r": "\\r",
}


def _toml_escape(value: str) -> str:
    """Escape a string for a TOML basic string (backslash, quote, controls)."""
    return "".join(_TOML_ESCAPES.get(c, c) for c in value)


def _toml_assignment(field: str, value: object) -> str:
    """Render a single TOML key/value assignment line."""
    if isinstance(value, str):
        return f'{field} = "{_toml_escape(value)}"'
    return f"{field} = {value}"


def _update_config_value(
    config_path: Path, key: str, value: object
) -> None:
    """Update a single config value in TOML file."""
    if not config_path.exists():
        _secure_write_text(config_path, generate_default_config())

    content = config_path.read_text()
    section, field = key.split(".", 1)

    # Simple TOML value update
    lines = content.splitlines()
    in_section = False
    updated = False

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(f"[{section}]"):
            in_section = True
            continue
        if in_section and stripped.startswith("["):
            break
        if in_section and (
            stripped.startswith(f"{field} ")
            or stripped.startswith(f"{field}=")
        ):
            lines[i] = _toml_assignment(field, value)
            updated = True
            break

    if not updated:
        # Insert into an existing [section], or create the section if absent
        # (a partial hand-edited config may omit it entirely).
        section_found = False
        for i, line in enumerate(lines):
            if line.strip().startswith(f"[{section}]"):
                lines.insert(i + 1, _toml_assignment(field, value))
                section_found = True
                break
        if not section_found:
            if lines and lines[-1].strip() != "":
                lines.append("")
            lines.append(f"[{section}]")
            lines.append(_toml_assignment(field, value))

    _secure_write_text(config_path, "\n".join(lines) + "\n")


@config.command("init")
@click.option(
    "--config-dir",
    type=click.Path(),
    default=None,
    help="Directory to create config in.",
)
def config_init(config_dir: str | None) -> None:
    """Create or update config via interactive setup wizard."""
    config_path = (
        Path(config_dir) / "config.toml"
        if config_dir
        else _get_config_path()
    )

    # Non-interactive: create default + print instructions
    if not _is_interactive():
        config_path.parent.mkdir(
            parents=True, exist_ok=True
        )
        if not config_path.exists():
            _secure_write_text(
                config_path, generate_default_config()
            )
        click.echo(
            f"  No terminal detected. Config file "
            f"created with defaults at:\n"
            f"    {config_path}\n"
            f"  Edit it manually to set your provider "
            f"and API key.",
            err=True,
        )
        return

    # Interactive: run wizard
    try:
        import promptune.setup as _setup_mod
        from promptune.engine import get_registry

        registry = get_registry()
        cfg = _setup_mod.run_interactive_setup(
            config_path, registry
        )
        _setup_mod.write_config(config_path, cfg)
        click.echo()
        click.echo(
            f"  \u2713 Config saved to {config_path}"
        )
        click.echo(
            "  Run `promptune doctor` to verify "
            "your setup."
        )
    except KeyboardInterrupt:
        click.echo("\nSetup cancelled.", err=True)
        raise SystemExit(130) from None


@config.command("show")
@click.option(
    "--config-path",
    type=click.Path(),
    default=None,
    help="Path to config file.",
)
def config_show(config_path: str | None) -> None:
    """Print current configuration."""
    path = (
        Path(config_path)
        if config_path
        else default_config_path()
    )
    from promptune.setup import mask_key

    cfg = load_config(config_path=path)
    for section, values in cfg.items():
        click.echo(f"[{section}]")
        if isinstance(values, dict):
            for key, val in values.items():
                is_secret = section == "api_keys" or (
                    section == "local_llm" and key == "api_key"
                )
                if is_secret and isinstance(val, str) and val:
                    val = mask_key(val)
                click.echo(f"  {key} = {val}")
        click.echo()


@config.command("path")
@click.option(
    "--config-path",
    type=click.Path(),
    default=None,
    help="Path to config file.",
)
def config_path_cmd(config_path: str | None) -> None:
    """Print config file path."""
    path = (
        Path(config_path)
        if config_path
        else default_config_path()
    )
    click.echo(str(path))


@main.command("shell-init")
@click.option(
    "--shell",
    type=click.Choice(["auto", "zsh", "bash", "fish"]),
    default="auto",
    help="Target shell (auto-detects from $SHELL).",
)
@click.option(
    "--key",
    default="ctrl+e",
    help="Keybinding in canonical format (e.g., ctrl+e, alt+e, ctrl+x ctrl+e).",
)
def shell_init(shell: str, key: str) -> None:
    """Output shell widget script for prompt enhancement."""
    try:
        click.echo(generate_widget(shell, key))
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc


@main.command("doctor")
def doctor_cmd() -> None:
    """Run system health check."""
    checks = [
        ("Python", _check_python),
        ("Config", _check_config),
        ("Tier 0", _check_tier0),
        ("Tier 1", _check_tier1),
        ("Tier 2", _check_tier2),
        ("Shell Widget", _check_shell_widget),
    ]

    issues: list[str] = []
    for name, check_fn in checks:
        ok, detail = check_fn()
        symbol = "\u2713" if ok else "\u2717"
        click.echo(f"  {name:<14} {symbol}  {detail}")
        if not ok:
            issues.append(detail)

    # Auto-enhance per tool
    for installer in get_installers():
        detected = installer.detect()
        if not detected:
            click.echo(
                f"  Auto-enhance   \u2717  "
                f"{installer.name} (not detected)"
            )
            continue
        try:
            installed = installer.is_installed()
        except (AttributeError, TypeError):
            # Malformed/hand-edited settings file \u2014 treat as not installed
            # rather than crashing the whole doctor run.
            installed = False
        symbol = "\u2713" if installed else "\u2717"
        cfg = load_config()
        threshold = cfg.get("auto_enhance", {}).get(
            "threshold", 40
        )
        detail = (
            f"{installer.name} (threshold: {threshold})"
            if installed
            else f"{installer.name} (hook not installed"
            f" \u2014 run: promptune config init)"
        )
        click.echo(f"  Auto-enhance   {symbol}  {detail}")
        if not installed:
            issues.append(detail)

    if issues:
        click.echo("\n  Issues:")
        for issue in issues:
            click.echo(f"    - {issue}")


def _check_python() -> tuple[bool, str]:
    ver = (
        f"{sys.version_info.major}."
        f"{sys.version_info.minor}."
        f"{sys.version_info.micro}"
    )
    return (
        sys.version_info >= (3, 9),
        f"{ver} (>=3.9 required)",
    )


def _check_config() -> tuple[bool, str]:
    path = _get_config_path()
    return path.exists(), str(path)


def _check_tier0() -> tuple[bool, str]:
    return True, "Rule engine ready"


def _check_tier1() -> tuple[bool, str]:
    cfg = load_config()
    if not cfg.get("local_llm", {}).get(
        "enabled", False
    ):
        return False, "Not configured"
    host = cfg["local_llm"].get("host", "")
    safe_host = redact_url_userinfo(host)
    try:
        import httpx

        resp = httpx.get(
            f"{host}/v1/models", timeout=3.0
        )
        return resp.status_code == 200, (
            f"Local LLM at {safe_host}"
        )
    except Exception:
        return False, f"Cannot reach {safe_host}"


def _check_tier2() -> tuple[bool, str]:
    cfg = load_config()
    provider = cfg.get("provider", {}).get(
        "default", "claude"
    )
    api_key = cfg.get("api_keys", {}).get(provider, "")
    if not api_key:
        return False, (
            f"No API key configured for {provider}"
        )
    return True, f"API key set for {provider}"


def _check_shell_widget() -> tuple[bool, str]:
    term = os.environ.get("TERM_PROGRAM", "")
    if term == "WarpTerminal":
        return (
            False,
            "Warp — widget not supported"
            " (use: promptune enhance)",
        )
    return True, "Shell widget compatible"


@main.command("local-llm-status")
def local_llm_status_cmd() -> None:
    """Check local LLM connectivity."""
    ok, detail = _check_local_llm_connectivity()
    symbol = "\u2713" if ok else "\u2717"
    click.echo(f"  Local LLM  {symbol}  {detail}")


def _check_local_llm_connectivity() -> (
    tuple[bool, str]
):
    cfg = load_config()
    host = cfg.get("local_llm", {}).get(
        "host", "http://localhost:11434"
    )
    safe_host = redact_url_userinfo(host)
    model = cfg.get("local_llm", {}).get(
        "model", "unknown"
    )
    try:
        import httpx

        resp = httpx.get(
            f"{host}/v1/models", timeout=3.0
        )
        if resp.status_code == 200:
            return True, (
                f"{model} responding at {safe_host}"
            )
        return False, (
            f"HTTP {resp.status_code} from {safe_host}"
        )
    except Exception as e:
        detail = redact_url_userinfo_in_text(str(e), host)
        return False, f"Cannot reach {safe_host}: {detail}"


@main.command("history")
@click.option(
    "--n",
    "count",
    type=int,
    default=20,
    help="Number of entries",
)
@click.option(
    "--stats",
    is_flag=True,
    help="Show statistics",
)
@click.option(
    "--clear",
    is_flag=True,
    help="Delete all history",
)
@click.option(
    "--preferences",
    is_flag=True,
    help="Show learned preferences",
)
def history_cmd(
    count: int, stats: bool, clear: bool, preferences: bool
) -> None:
    """View enhancement history."""
    store = _get_history_store()
    if store is None:
        click.echo("History is disabled.")
        return

    try:
        if clear:
            if click.confirm("Delete all history?"):
                deleted = store.clear()
                click.echo(f"Deleted {deleted} entries.")
            return

        if preferences:
            cfg = load_config()
            min_samples = cfg.get("enhancement", {}).get(
                "preference_min_samples", 5
            )
            rule_prefs = analyse_rule_preferences(
                store, min_samples=min_samples
            )
            edit_pats = analyse_edit_patterns(
                store, min_samples=min_samples
            )

            if not rule_prefs and not edit_pats:
                click.echo("No preferences learned yet.")
                return

            if rule_prefs:
                click.echo("  Rule preferences:")
                for p in rule_prefs:
                    click.echo(
                        f"    {p.rule_name:<20} {p.action:<6} "
                        f"({p.confidence:.0%} confidence, "
                        f"n={p.sample_count})"
                    )

            if edit_pats:
                click.echo("  Edit patterns:")
                for ep in edit_pats:
                    click.echo(
                        f"    {ep.description} "
                        f"({ep.frequency:.0%}, n={ep.sample_count})"
                    )
            return

        if stats:
            s = store.stats()
            click.echo(f"  Total:       {s.total}")
            click.echo(
                f"  Accepted:    {s.accepted} "
                f"({s.acceptance_rate:.0%})"
            )
            click.echo(f"  Rejected:    {s.rejected}")
            click.echo(f"  Edited:      {s.edited}")
            click.echo(
                f"  Avg before:  {s.avg_score_before:.0f}"
            )
            click.echo(
                f"  Avg after:   {s.avg_score_after:.0f}"
            )
            click.echo(
                f"  Avg improve: +{s.avg_improvement:.0f}"
            )
            return

        entries = store.recent(n=count)
        if not entries:
            click.echo("No history yet.")
            return

        for entry in entries:
            click.echo(
                f"  [{entry.tier_used}] "
                f"{entry.original[:50]}... "
                f"\u2192 {entry.score_before}"
                f"\u2192{entry.score_after}"
            )
    finally:
        store.close()


def _update_history_decision(
    cfg: dict[str, Any],
    entry_id: int,
    decision: str,
    edit_result: str | None,
) -> None:
    """Correct a recorded enhancement's decision (best-effort)."""
    history_cfg = cfg.get("history", {})
    if not history_cfg.get("enabled", True):
        return
    try:
        with HistoryStore(
            db_path=Path(
                history_cfg.get(
                    "db_path", "~/.local/share/promptune/history.db"
                )
            ).expanduser(),
            max_entries=history_cfg.get("max_entries", 10000),
        ) as store:
            store.set_decision(entry_id, decision, edit_result)
    except Exception:
        pass


def _get_history_store() -> HistoryStore | None:
    """Get history store instance."""
    cfg = load_config()
    history_cfg = cfg.get("history", {})
    if not history_cfg.get("enabled", True):
        return None
    return HistoryStore(
        db_path=Path(
            history_cfg.get(
                "db_path", "~/.local/share/promptune/history.db"
            )
        ).expanduser(),
        max_entries=history_cfg.get("max_entries", 10000),
    )


# --- Daemon command group ---


@main.group()
def daemon() -> None:
    """Manage the promptune background daemon."""


def _get_daemon_status() -> Any:
    """Import and call get_status. Separate for test mockability."""
    from promptune.daemon.daemon import get_status

    return get_status()


@daemon.command()
@click.option(
    "--foreground",
    is_flag=True,
    help="Run in foreground (debug mode)",
)
def start(foreground: bool) -> None:
    """Start the background daemon."""
    from promptune.daemon.daemon import start_daemon

    if start_daemon(foreground=foreground) is False:
        raise SystemExit(1)


@daemon.command()
def stop() -> None:
    """Stop the running daemon."""
    from promptune.daemon.daemon import stop_daemon

    stop_daemon()


@daemon.command()
def restart() -> None:
    """Restart the daemon."""
    from promptune.daemon.daemon import (
        start_daemon,
        stop_daemon,
    )

    stop_daemon()
    if start_daemon() is False:
        raise SystemExit(1)


@daemon.command("report-cwd", hidden=True)
@click.option("--cwd", required=True)
@click.option("--project-root", default="")
def report_cwd(cwd: str, project_root: str) -> None:
    """Report shell cwd to the daemon IPC socket."""
    from promptune.daemon.ipc import send_ipc_message

    send_ipc_message({
        "action": "report_cwd",
        "cwd": cwd,
        "project_root": project_root,
    })


@daemon.command()
def status() -> None:
    """Show daemon status."""
    s = _get_daemon_status()
    if s.running:
        uptime = ""
        if s.uptime_seconds is not None:
            mins = int(s.uptime_seconds // 60)
            hours = mins // 60
            mins = mins % 60
            uptime = f" (uptime {hours}h{mins:02d}m)"
        click.echo(f"Daemon running (pid {s.pid}){uptime}")
        click.echo(f"  Enhancements: {s.enhancement_count}")
        click.echo(
            f"  Socket: {'exists' if s.socket_exists else 'missing'}"
        )
    else:
        click.echo("Daemon not running")
    click.echo(
        f"  Accessibility: {'granted' if s.accessibility_granted else 'denied'}"
    )


@daemon.command()
def setup() -> None:
    """Guide through daemon setup (permissions, dependencies)."""
    if sys.platform == "darwin":
        _setup_macos()
    elif sys.platform == "linux":
        _setup_linux()
    else:
        click.echo("Unsupported platform.", err=True)
        raise SystemExit(1)


def _setup_macos() -> None:
    """macOS Accessibility permission setup."""
    import subprocess as sp
    import time as t

    from promptune.daemon.hotkey import (
        check_accessibility,
        request_accessibility,
    )

    if check_accessibility():
        click.echo("Accessibility permission already granted.")
        return

    click.echo("Accessibility permission required for global hotkey.")
    click.echo("Opening System Settings...")
    sp.run(
        [
            "open",
            "x-apple.systempreferences:"
            "com.apple.preference.security?"
            "Privacy_Accessibility",
        ]
    )
    click.echo("Add your terminal app to the Accessibility list.")
    click.echo("Waiting for permission (60s timeout)...")
    request_accessibility()

    for _ in range(60):
        if check_accessibility():
            click.echo("Accessibility permission granted!")
            return
        t.sleep(1)
    click.echo("Timeout. Grant permission manually and retry.")


def _setup_linux() -> None:
    """Linux dependency check and group membership guidance."""
    from promptune.daemon.platform.linux_service import LinuxDependencyChecker

    checker = LinuxDependencyChecker()
    results = checker.check()

    click.echo("Checking daemon dependencies...\n")
    missing = []
    for dep in results:
        symbol = "\u2713" if dep.installed else "\u2717"
        label = "required" if dep.required else "optional"
        click.echo(f"  {dep.name:<16} {symbol}  ({label})")
        if not dep.installed and dep.required:
            missing.append(dep.name)

    if missing:
        cmd = checker.get_install_command(missing)
        click.echo(f"\nInstall missing tools:\n  {cmd}")
    else:
        click.echo("\nAll dependencies satisfied.")

    # Check input group for Wayland
    import os

    session = os.environ.get("XDG_SESSION_TYPE", "")
    if session == "wayland":
        import grp
        import pwd

        try:
            input_group = grp.getgrnam("input")
            username = pwd.getpwuid(os.getuid()).pw_name
            if username not in input_group.gr_mem:
                click.echo(
                    "\nFor Wayland hotkey support, add yourself to the input group:"
                )
                click.echo(f"  sudo usermod -aG input {username}")
                click.echo(
                    "  (Log out and back in for the change to take effect)"
                )
        except KeyError:
            pass


@daemon.command()
def diagnose() -> None:
    """Run diagnostic checks on daemon health."""
    from promptune.daemon.platform import PlatformError, get_platform

    try:
        platform = get_platform()
    except PlatformError as exc:
        click.echo(f"Platform: {exc}", err=True)
        raise SystemExit(1) from exc

    s = _get_daemon_status()
    installed = platform.service.is_installed()

    def _check(label: str, ok: bool, detail: str = "") -> None:
        mark = "\u2713" if ok else "\u2717"
        click.echo(f"  {label:<20} {mark}  {detail}")

    click.echo("promptune daemon diagnose\n")
    _check("Platform", True, sys.platform)
    _check(
        "Daemon PID",
        s.running,
        f"pid {s.pid}" if s.running else "Not running",
    )
    _check("Socket", s.socket_exists)
    _check("Service", installed)

    if sys.platform == "darwin":
        _check("Accessibility", s.accessibility_granted)
    elif sys.platform == "linux":
        from promptune.daemon.platform.linux_service import LinuxDependencyChecker

        checker = LinuxDependencyChecker()
        deps = checker.check()
        for dep in deps:
            _check(dep.name, dep.installed, "required" if dep.required else "optional")

    issues: list[str] = []
    if not s.running:
        issues.append("Start daemon: promptune daemon start")
    if not installed:
        issues.append("Install service: promptune daemon install")
    if issues:
        click.echo("\n  Issues:")
        for issue in issues:
            click.echo(f"    - {issue}")


@daemon.command("install")
def daemon_install() -> None:
    """Install daemon service and check dependencies."""
    from promptune.daemon.platform import PlatformError, get_platform

    try:
        platform = get_platform()
    except PlatformError as exc:
        click.echo(f"Error: {exc}", err=True)
        raise SystemExit(1) from exc

    # Run dependency check on Linux
    if sys.platform == "linux":
        from promptune.daemon.platform.linux_service import LinuxDependencyChecker

        checker = LinuxDependencyChecker()
        results = checker.check()
        missing = [r.name for r in results if not r.installed and r.required]
        if missing:
            click.echo("Missing required dependencies:")
            for r in results:
                symbol = "\u2713" if r.installed else "\u2717"
                label = "required" if r.required else "optional"
                click.echo(f"  {r.name:<16} {symbol}  ({label})")
            cmd = checker.get_install_command(missing)
            click.echo(f"\nInstall with:\n  {cmd}")
            raise SystemExit(1)

    platform.service.install()
    click.echo("Daemon service installed.")


@daemon.command("uninstall")
def daemon_uninstall() -> None:
    """Remove daemon service."""
    from promptune.daemon.platform import PlatformError, get_platform

    try:
        platform = get_platform()
    except PlatformError as exc:
        click.echo(f"Error: {exc}", err=True)
        raise SystemExit(1) from exc

    platform.service.uninstall()
    click.echo("Daemon service removed.")


@daemon.command("purge")
def daemon_purge() -> None:
    """Remove all daemon files (service, socket, PID, undo, logs)."""
    from promptune.daemon.platform import PlatformError, get_platform

    if not click.confirm("Remove all daemon files?"):
        return

    try:
        platform = get_platform()
    except PlatformError as exc:
        click.echo(f"Error: {exc}", err=True)
        raise SystemExit(1) from exc

    platform.service.purge()
    click.echo("All daemon files removed.")
    click.echo(
        "Note: History database preserved at ~/.local/share/promptune/history.db"
    )


# macOS-specific legacy commands (kept for backward compatibility)


@daemon.command("install-login-item")
def install_login_item() -> None:
    """Install LaunchAgent for auto-start on login (macOS only)."""
    if sys.platform != "darwin":
        click.echo(
            "Error: install-login-item is macOS-only. "
            "Use 'daemon install' instead.",
            err=True,
        )
        raise SystemExit(1)
    from promptune.daemon.launchagent import (
        install_login_item as _install,
    )

    _install()
    click.echo("LaunchAgent installed. Daemon will start on login.")


@daemon.command("uninstall-login-item")
def uninstall_login_item() -> None:
    """Remove LaunchAgent (macOS only)."""
    if sys.platform != "darwin":
        click.echo(
            "Error: uninstall-login-item is macOS-only. "
            "Use 'daemon uninstall' instead.",
            err=True,
        )
        raise SystemExit(1)
    from promptune.daemon.launchagent import (
        uninstall_login_item as _uninstall,
    )

    _uninstall()
    click.echo("LaunchAgent removed.")
