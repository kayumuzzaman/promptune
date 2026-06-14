# Interactive Config Setup — Design Spec

## Goal

Replace the silent `promptune config init` (which just writes a default TOML file) with an interactive setup wizard that guides users through mandatory configuration — provider selection and API key — so they never need to manually edit the config file to get started.

## Problem

Currently, `promptune config init` creates `~/.config/promptune/config.toml` with empty API keys. The user must then find the file, open it in an editor, and fill in their provider and API key. This is friction that delays the "first enhance" experience.

## Design

### User Flows

#### First-time setup (interactive)

```
$ promptune config init

  Promptune Setup
  ───────────────

  Provider [claude/openai/openrouter] (claude): openai
  OpenAI API key: ****
  ✓ Key format looks valid.

  Configure advanced settings? [y/N]: n

  ✓ Config saved to ~/.config/promptune/config.toml
  Run `promptune doctor` to verify your setup.
```

#### Re-run with existing config (interactive)

```
$ promptune config init

  Promptune Setup
  ───────────────

  Provider [claude/openai/openrouter] (openai): ↵
  OpenAI API key [sk-...4z7x]: ↵
  ✓ Key format looks valid.

  Configure advanced settings? [y/N]: n

  ✓ Config saved to ~/.config/promptune/config.toml
```

Existing values are pre-filled as defaults. User presses Enter to keep them or types new values. For API keys, the existing value is shown masked (last 4 chars visible).

#### Non-interactive (piped / no TTY)

```
$ echo "something" | promptune config init

  No terminal detected. Config file created with defaults at:
    ~/.config/promptune/config.toml
  Edit it manually to set your provider and API key.
```

Creates the default config file and prints instructions to stderr. Exits 0.

#### Mandatory field validation

Empty API key is rejected and re-prompted:

```
  OpenAI API key:
  Error: API key is required for your selected provider.
  OpenAI API key: sk-abc123...
  ✓ Key format looks valid.
```

### Field Classification

#### Mandatory (blocking — must provide)

| Field | Input type | Default | Validation |
|-------|-----------|---------|------------|
| Provider | Choice from registry | `claude` | Must be in `registry.list()` |
| API key | Hidden text | (existing or empty) | Non-empty; format advisory warning |

#### Optional (behind "Configure advanced settings?" y/N gate)

| Field | Input type | Default | Validation |
|-------|-----------|---------|------------|
| Enhancement style | Choice | `balanced` | Must be in `{minimal, balanced, detailed}` |
| Max tier | Integer | `2` | Must be 0, 1, or 2 |
| Format style | Choice | `auto` | Must be in `{auto, xml, markdown, plain}` |

#### Not asked (always defaults)

- Model names per provider
- Local LLM settings
- Context settings
- History settings
- TUI settings

These are written to the config file with default values. Users can edit the file later or re-run `config init` with advanced settings.

### API Key Format Validation

Known prefix patterns:

| Provider | Expected prefix |
|----------|----------------|
| claude | `sk-ant-` |
| openai | `sk-` |
| openrouter | `sk-or-` |

Behavior:
- Empty key → **reject**, re-prompt (mandatory)
- Key doesn't match expected prefix → **warn** but accept: `"Warning: Key doesn't look like a {provider} key. Saving anyway."`
- Unknown provider (no known prefix) → accept any non-empty string, skip format check

Advisory only — key formats can change. The only hard requirement is non-empty.

### Architecture

#### New file: `promptune/setup.py`

Contains all wizard logic, separate from CLI routing.

```
setup.py
├── run_interactive_setup(config_path, registry) → dict
│   ├── _prompt_provider(registry, default) → str
│   ├── _prompt_api_key(provider, existing) → str
│   └── _prompt_optional_settings(defaults) → dict
├── validate_key_format(provider, key) → str | None
├── write_config(config_path, config_dict) → None
├── mask_key(key) → str
└── KEY_PREFIXES: dict[str, str]
```

**`run_interactive_setup(config_path, registry)`** — Main orchestrator.
- Loads existing config (if config_path exists) for pre-filling defaults.
- Calls sub-functions for each section.
- Returns a complete config dict ready to write.

**`_prompt_provider(registry, default)`** — Prompts with `click.prompt()`, choices from `registry.list()`, validates against registry.

**`_prompt_api_key(provider, existing)`** — Masked input via `click.prompt(hide_input=True)`. When `existing` is non-empty, the masked hint is embedded in the prompt text itself (e.g., `"OpenAI API key [sk-...4z7x]"`) and `default=existing` is passed so Enter keeps the value. When `existing` is empty (first run), no default is set — Click will reject empty input and re-prompt. Calls `validate_key_format()` for advisory warning.

**`_prompt_optional_settings(defaults)`** — Behind `click.confirm("Configure advanced settings?", default=False)`. If yes, prompts for style, max_tier, format_style with current values as defaults.

**`validate_key_format(provider, key)`** — Returns `None` if valid/unknown, or a warning string if prefix doesn't match. Publicly accessible for testing.

**`write_config(config_path, config_dict)`** — Serializes config dict to TOML string using manual string formatting (same approach as `generate_default_config()` — no TOML writer dependency needed) and writes to disk. Creates parent directories if needed.

**`mask_key(key)`** — Returns masked representation: first 2 chars + `"..."` + last 4 chars (e.g., `"sk-...4z7x"`). Returns `""` if key is empty. Short keys (< 8 chars): `"****"` + last 4.

#### Changes to existing files

**`promptune/cli.py`** — Modify `config_init()`:
- Detect TTY via `sys.stdin.isatty()`
- If interactive: import and call `run_interactive_setup()`, then `write_config()`
- If non-interactive: create default config file, print instructions
- Keep `--config-dir` option for backward compatibility (passes custom path to wizard or non-interactive flow)

**`promptune/engine.py`** — Rename `_get_registry()` to `get_registry()` (make public) so `setup.py` can access the provider list without duplicating registration logic. Update internal caller `_create_cloud_provider()` to use the renamed function.

**`promptune/providers/__init__.py`** — No changes.

**`promptune/config.py`** — No changes to existing functions. `load_config()`, `generate_default_config()`, `DEFAULT_CONFIG` all remain as-is.

### Non-interactive Detection

```python
if not sys.stdin.isatty():
    # Non-interactive: create default + print instructions
else:
    # Interactive: run wizard
```

### Config File Writing

The wizard produces a complete config dict (merged with `DEFAULT_CONFIG` for unset fields). `write_config()` serializes to TOML format matching the existing `generate_default_config()` structure, but with user-provided values filled in.

### Ctrl+C Handling

If the user presses Ctrl+C during the wizard, abort cleanly: do not write a partial config, print "Setup cancelled." to stderr, exit with code 130. Matches existing `enhance_cmd` pattern.

### Backward Compatibility

- `promptune config init --config-dir <path>` preserved — passes custom path to wizard or non-interactive flow
- All other `config` subcommands unchanged: `show`, `path`, `--set-key`, `--set-tier`, `--reset`
- `generate_default_config()` unchanged — still used by `--reset`
- Existing tests for `config show`, `config path`, `--reset` must not break

### Testing Strategy (TDD)

#### `tests/test_setup.py` — Unit tests

- `validate_key_format()`: correct prefix passes, wrong prefix returns warning, empty returns error, unknown provider skips check
- `mask_key()`: masks correctly, handles empty, handles short keys
- `_prompt_provider()`: returns valid selection, pre-fills default
- `_prompt_api_key()`: rejects empty, accepts valid, warns on bad prefix
- `_prompt_optional_settings()`: skips on N, collects on Y, validates choices
- `run_interactive_setup()`: full flow, existing config pre-fills
- `write_config()`: writes valid TOML, creates directories, values round-trip through `load_config()`

#### `tests/test_cli.py` — CLI integration

- `config init` interactive: produces config file with correct values
- `config init` with existing config: pre-fills values
- `config init` non-interactive: creates default + prints instructions
- Existing config subcommand tests still pass

#### Gate after each task

```bash
ruff check . && mypy promptune/ && pytest -v
```

### Dependencies

No new dependencies. Uses:
- `click` — `click.prompt()`, `click.confirm()`, `click.echo()`
- `rich` — `Console` for styled header/feedback messages
- Existing `config.py` — `DEFAULT_CONFIG`, `load_config()`, `default_config_path()`
- Existing `providers/__init__.py` — `ProviderRegistry`
- Existing `engine.py` — `get_registry()`
