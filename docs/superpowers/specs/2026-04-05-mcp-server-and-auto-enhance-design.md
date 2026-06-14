# MCP Server & Auto-Enhance — Design Spec

## Problem

Promptune enhances prompts via CLI, shell widget, and system daemon — but none of these work **inside** AI coding tools (Claude Code, Codex, Gemini CLI, Cursor, etc.). When a user types a prompt to an AI agent, promptune never touches it. The prompt goes straight to the AI unenhanced.

Users need promptune to work where they actually write prompts to AI — inside their AI tools.

## Solution

Two integration mechanisms, both user-controlled:

1. **MCP Server** — exposes `enhance` and `score` tools via the standard MCP protocol. Any MCP-compatible AI tool can call them. The user or the AI can invoke enhancement explicitly.
2. **Auto-Enhance** — automatically intercepts low-quality prompts before they reach the AI, shows the enhanced version, copies it to clipboard. The user pastes to use it or retypes to override. No prompt is ever sent without the user's explicit action.

## Design Principles

- **Simple for users** — "auto-enhance" is the only concept users see. No jargon about hooks, gates, or interceptors.
- **User always has control** — auto-enhance blocks and shows, never sends. The user decides.
- **MCP-first** — one implementation works across all MCP-compatible tools.
- **No new background processes** — MCP server uses stdio transport (AI tools manage the lifecycle). Existing daemon is unchanged.

---

## Component 1: MCP Server

### Module: `promptune/mcp/`

```
promptune/mcp/
├── __init__.py      # Package
└── server.py        # MCP server implementation (stdio transport)
```

### CLI Entry Point

```
promptune mcp
```

Starts the MCP server on stdio. AI tools launch this command and communicate via stdin/stdout using the MCP protocol. The server runs for the lifetime of the AI tool session.

### Tools Exposed

#### `enhance`

Enhances a prompt using the existing 3-tier engine.

**Input parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `prompt` | string | yes | The prompt to enhance |
| `style` | string | no | `minimal` / `balanced` / `detailed` (default: config value) |
| `tier` | integer | no | Force tier: 0 / 1 / 2 (default: auto-route) |
| `format` | string | no | `xml` / `markdown` / `plain` (default: `auto`) |

**Output (JSON):**

```json
{
  "original": "make a todo app",
  "enhanced": "Build a full-stack todo application with...",
  "score_before": 38,
  "score_after": 74,
  "tier_used": 2,
  "rules_applied": ["vague_verbs", "constraints", "output_format"],
  "latency_ms": 1240.5
}
```

**Implementation:** Calls `engine.enhance()` directly. Reuses all existing logic — scoring, tier routing, context fingerprinting, dedup, preferences. Zero duplication.

#### `score`

Scores a prompt without enhancing it.

**Input parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `prompt` | string | yes | The prompt to score |

**Output (JSON):**

```json
{
  "total": 38,
  "intent": "coding",
  "dimensions": {
    "specificity": { "score": 0.25, "weight": 25.0, "suggestion": "Add specific technical terms..." },
    "clarity": { "score": 0.45, "weight": 20.0, "suggestion": "Good clarity" },
    "structure": { "score": 0.10, "weight": 15.0, "suggestion": "Add structure: use headers..." },
    "actionability": { "score": 0.30, "weight": 15.0, "suggestion": "Use specific imperative verbs..." },
    "context": { "score": 0.15, "weight": 10.0, "suggestion": "Add role assignment..." },
    "completeness": { "score": 0.10, "weight": 10.0, "suggestion": "Specify expected output format..." },
    "conciseness": { "score": 0.60, "weight": 5.0, "suggestion": "Good conciseness" }
  }
}
```

**Implementation:** Calls `scorer.score_prompt()` directly.

### MCP Configuration

Users add promptune to their AI tool's MCP config. Example for Claude Code (`~/.claude.json`):

```json
{
  "mcpServers": {
    "promptune": {
      "command": "promptune",
      "args": ["mcp"]
    }
  }
}
```

Similar one-line config for Codex, Gemini CLI, Cursor, etc. — the MCP protocol is standard.

### Dependencies

- `mcp` Python SDK (`mcp[cli]`) — added as optional dependency: `pip install promptune[mcp]`
- No new background processes. AI tools spawn and manage `promptune mcp` lifecycle.

---

## Component 2: Auto-Enhance

### Concept

Auto-enhance silently scores every prompt the user submits. If the score is above the threshold, the prompt passes through untouched. If below, it blocks the submission, shows the enhanced version, and copies it to the clipboard. The user pastes to use the enhanced version, or retypes to send the original.

### User Experience

**When prompt is good (PQS >= threshold):** Nothing happens. Prompt goes through instantly. User never notices.

**When prompt needs improvement (PQS < threshold):**

```
┌─ Auto-enhance ─────────────────────────────┐
│                                             │
│  Your prompt scored 38/100.                 │
│  Enhanced version (copied to clipboard):    │
│                                             │
│  Build a full-stack todo application with   │
│  CRUD operations, persistent storage...     │
│                                             │
│  Score: 38 → 74                             │
│                                             │
│  [Paste] to use · [Retype] to use original  │
└─────────────────────────────────────────────┘
```

**User control:**
- **Use enhanced** → paste (already on clipboard), hit Enter
- **Use original** → retype the same prompt or hit up-arrow, send as-is
- **Modify** → paste, edit the text, then send

No prompt is ever sent without the user's explicit action.

### CLI Entry Point

```
promptune gate "<prompt>"
```

Internal command used by tool hooks. Not user-facing (not documented in help/user guide). Behavior:

1. Score the prompt via `scorer.score_prompt()`
2. If PQS >= threshold or word count < min_words → exit 0 (pass through)
3. If PQS < threshold → enhance via `engine.enhance()`, copy enhanced to clipboard (pbcopy/xclip/wl-copy), print the auto-enhance block to stderr, exit 1 (block)

Exit codes: 0 = allow, 1 = block. This maps to hook conventions in Claude Code and other tools.

### Tool-Specific Hook Installers

Each AI tool has its own hook mechanism. Auto-enhance installs the appropriate hook format for each detected tool.

#### Claude Code

Hook type: `user-prompt-submit` in `~/.claude/settings.json`

```json
{
  "hooks": {
    "user-prompt-submit": [
      {
        "command": "promptune gate \"$PROMPT\""
      }
    ]
  }
}
```

#### Other Tools

Hook installers for Codex, Gemini CLI, etc. are added as each tool's hook mechanism is confirmed. The `promptune gate` command is universal — only the installer differs per tool.

If a tool has no hook mechanism, auto-enhance is unavailable for that tool. The MCP `enhance` tool still works.

### Auto-Detection During Setup

`promptune config init` detects installed AI tools and offers auto-enhance:

```
Found Claude Code, Gemini CLI.
Auto-enhance prompts in these tools? [Y/n]
```

- If yes → installs hooks for all detected tools
- If no → skips, MCP tools are still available
- Re-running `config init` repairs/updates hooks
- Detection checks: `~/.claude/` (Claude Code), codex config paths, gemini config paths

### Doctor Integration

`promptune doctor` verifies auto-enhance health:

```
  Auto-enhance   ✓  Claude Code (threshold: 60)
  Auto-enhance   ✗  Codex (not detected)
  Auto-enhance   ✓  Gemini CLI (threshold: 60)
```

---

## Component 3: `promptune score` Command

### Purpose

Standalone prompt quality scoring. Used internally by `promptune gate`, also useful for users who want to check prompt quality without enhancing.

### CLI

```bash
# Basic usage
promptune score "make a todo app"
#  PQS: 38/100
#  Specificity:    25%  — Add specific technical terms...
#  Clarity:        45%  — Good clarity
#  Structure:      10%  — Add structure: use headers...
#  Actionability:  30%  — Use specific imperative verbs...
#  Context:        15%  — Add role assignment...
#  Completeness:   10%  — Specify expected output format...
#  Conciseness:    60%  — Good conciseness

# JSON output (used by gate internally)
promptune score --json "make a todo app"
```

### Flags

| Flag | Description |
|------|-------------|
| `--json` | Output structured JSON |

### Implementation

Calls `scorer.score_prompt()` and formats the output. Trivial — the scorer already exists.

---

## Component 4: Config Changes

### New Config Section

```toml
[auto_enhance]
enabled = true
threshold = 60
min_words = 5
```

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `true` | Enable/disable auto-enhance hooks |
| `threshold` | int | `60` | PQS below this triggers enhancement |
| `min_words` | int | `5` | Prompts shorter than this skip scoring |

### Config Init Changes

The setup wizard gains one new step after the existing flow:

```
1. Provider         (existing)
2. API key          (existing)
3. Model            (existing)
4. Advanced settings (existing)
5. Local LLM        (existing, when tier >= 1)
6. Auto-enhance     (NEW — detect AI tools, offer to enable)
```

The auto-enhance step:
- Detects installed AI tools by checking known config paths
- Lists what was found
- Asks y/n to enable
- If yes, installs hooks + writes `[auto_enhance]` config section

---

## Project Structure Changes

```
promptune/
├── mcp/
│   ├── __init__.py          # Package
│   └── server.py            # MCP server (stdio, enhance + score tools)
├── gate.py                  # Auto-enhance gate logic (score → enhance → clipboard → exit code)
├── hooks/
│   ├── __init__.py          # Detection + installer registry
│   ├── claude_code.py       # Claude Code hook installer
│   └── ...                  # Future: codex.py, gemini.py, etc.
└── cli.py                   # New commands: mcp, gate, score
```

---

## Dependencies

| Package | Purpose | Install group |
|---------|---------|---------------|
| `mcp[cli]` | MCP server SDK | `pip install promptune[mcp]` |

No other new dependencies. Clipboard operations reuse existing platform logic from `daemon/clipboard.py` (macOS) and `daemon/platform/` (Linux).

---

## What This Does NOT Change

- Existing CLI (`promptune enhance`) — unchanged
- Shell widget (Ctrl+E) — unchanged
- System daemon (Ctrl+Shift+E) — unchanged
- TUI — unchanged
- All existing tests — unchanged

The MCP server and auto-enhance are additive. They reuse the existing engine, scorer, and config. No refactoring of existing code.

---

## Testing Strategy

- **MCP server:** Mock stdio transport, verify `enhance` and `score` tools return correct JSON structure. Mock `engine.enhance()` and `scorer.score_prompt()` at the boundary.
- **Gate:** Test exit codes (0 for pass, 1 for block), clipboard copy, threshold logic, min_words skip. Mock scorer and engine.
- **Score command:** Test CLI output formatting and JSON mode. Mock scorer.
- **Hook installers:** Test detection logic (config paths exist/don't exist), test generated hook config format. Use tmp_path for config files.
- **Config init integration:** Test auto-enhance step with detected/undetected tools. Mock filesystem checks.

Coverage target: ≥ 90% for new code, matching project standard.
