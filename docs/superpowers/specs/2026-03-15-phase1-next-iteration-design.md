# Promptune Phase 1 Next Iteration — Design Spec
### Version 1.1 | 2026-03-15

---

## Overview

This spec defines the next iteration of promptune, adding intelligent tier-based enhancement, context awareness, quality scoring, and provider-specific formatting on top of the existing CLI + TUI + providers foundation (Steps 0-10 complete).

**Scope:** 11 implementation steps, bottom-up, TDD discipline (RED-GREEN-REFACTOR).

**Out of scope (deferred):** Semantic deduplication, preference learning engine, team `.prompts/` templates, fish/bash shell widgets, Phase 2 daemon.

---

## 1. Config Schema Migration

### Rationale

The current schema (`[general]`, `[providers.*]`, `[tui]`) was designed for "always call cloud provider." It has no room for tiers, local LLM, context, history, or daemon config. Since we're pre-v1 with no external users, a clean break is the right call.

### New Schema

```toml
[provider]
default = "claude"                        # claude | openai | openrouter
format_style = "auto"                     # auto | xml | markdown | plain
model_claude = "claude-haiku-4-5-20251001"
model_openai = "gpt-4o-mini"
model_openrouter = "anthropic/claude-haiku"

[api_keys]
claude = ""
openai = ""
openrouter = ""

[enhancement]
max_tier = 2                              # 0=rules only, 1=+local, 2=+cloud
default_mode = "balanced"                 # minimal | balanced | detailed
max_tokens_output = 400
timeout_seconds = 10

[local_llm]
enabled = true
host = "http://localhost:11434"
model = "qwen2.5:3b"
api_key = ""                              # optional, some tools require dummy key

[context]
use_git = true
use_shell_history = true
use_stack_detection = true
max_context_tokens = 500
shell_history_lines = 20

[history]
enabled = true
max_entries = 10000
db_path = "~/.local/share/promptune/history.db"

[tui]
show_pqs_scores = true
show_tier_used = true
show_latency = true
theme = "dark"
show_diff = true
```

### Resolution Order

CLI flags > env vars (`PROMPTUNE_PROVIDER`, `PROMPTUNE_STYLE`) > config file > defaults.

### Changes from Current

- API keys separated from provider config (SRP — keys are security, models are preference)
- `[enhancement]` section governs tier routing
- `[local_llm]` replaces Ollama-specific config — generic OpenAI-compatible endpoint
- `[context]` controls fingerprinting behavior
- `[history]` controls SQLite storage
- `style` renamed to `default_mode`: `"minimal"` stays, `"balanced"` stays, `"thorough"` renamed to `"detailed"` (all references in code and docs must use `"detailed"`)
- `format_style` added for provider-specific formatting control

### Files Requiring Update in Step 1

| File | Changes needed |
|---|---|
| `config.py` | Full rewrite: new `DEFAULT_CONFIG`, new schema, new validation, new `generate_default_config()` |
| `config.example.toml` | Rewrite to match new schema |
| `engine.py` | Update config key access paths (`config["provider"]["default"]` etc.) |
| `cli.py` | Update config access, add new config subcommands |
| `meta_prompt.py` | Rename `"thorough"` to `"detailed"` in style handling |
| `tests/test_config.py` | Full rewrite: test new schema, new defaults, new validation |
| `tests/test_engine.py` | Update mock config dicts to new schema |
| `tests/test_cli.py` | Update config expectations |
| `CLAUDE.md` | Update Config TOML Schema section |

---

## 2. Quality Scorer

### Purpose

Pure heuristic function that scores raw prompts 0-100 for tier routing decisions. No AI, no network, typically <5ms. Research-backed using information theory and linguistic analysis.

### 7 Scoring Dimensions

| Dimension | Max Points | Method |
|---|---|---|
| Specificity | 25 | Shannon entropy (word-level), Type-Token Ratio, technical term density, vague word penalty, constraint markers, entity/number presence |
| Clarity | 20 | Flesch-Kincaid grade in ideal range (8-14), sentence length consistency, positive directive ratio (negation penalty), ambiguous pronoun density |
| Structure | 15 | Delimiter detection (###, ---, XML tags, markdown headers), numbered/bulleted lists, code blocks, labeled sections, logical ordering signals |
| Actionability | 15 | Imperative verb detection (verb taxonomy: vague→precise), clear task identification (verb + specific object), step-by-step indicators |
| Context | 10 | Role assignment ("you are a..."), audience specification, domain/tech keywords, background signals |
| Completeness | 10 | Output format specified, examples included, success criteria, acceptance conditions |
| Conciseness | 5 | Shannon entropy (higher = denser), filler word ratio penalty, politeness penalty (per Bsharat principle #1) |

### Research Basis

- **Bsharat et al. 2023** (26 validated principles): Specificity is strongest predictor. Affirmative directives outperform negative. Politeness degrades performance.
- **"The Prompt Report" (Schulhoff et al. 2024)**: Structure matters more than word choice. 58 prompting techniques catalogued.
- **DETAIL paper (arXiv:2512.02246)**: Specificity improves accuracy +0.47 on procedural tasks but can hurt open-ended reasoning.

### Scoring Curves

Diminishing returns via exponential decay:
```python
score = max_points * (1 - exp(-k * raw_count))
```

Sigmoid calibration on overall score to prevent clustering in 40-60 range:
```python
calibrated = 1 / (1 + exp(-steepness * (raw - midpoint)))
```

### Intent-Aware Weight Adjustment

- Coding prompts: specificity +5%, actionability +3%
- Creative/writing prompts: specificity -5%, clarity +5%
- Research prompts: context +5%, actionability -3%

### Routing Thresholds

```
70-100 → Tier 0 (rules only)
40-69  → Tier 1 (local LLM)
0-39   → Tier 2 (cloud API)
```

### Interface

```python
@dataclass
class ScoreResult:
    total: int                              # 0-100 calibrated
    dimensions: dict[str, DimensionScore]   # per-dimension detail
    intent: str                             # detected prompt type

@dataclass
class DimensionScore:
    score: float        # 0-1 raw
    max_weight: float   # dimension weight
    signals: list[str]  # what was detected
    suggestion: str     # actionable fix

def score_prompt(prompt: str) -> ScoreResult
```

---

## 3. Tier 0 Rule Engine

### Purpose

Deterministic text transformations. No AI, no network, <10ms. Augments the prompt — original preserved, additions appended or structural improvements applied.

### Rules (based on Bsharat's 26 validated principles)

| Rule | Trigger | Action |
|---|---|---|
| Missing output format | Completeness score low, no format markers | Append format instruction based on detected intent |
| Vague task verbs | Actionability score low, vague verbs detected | Flag with suggested specific alternatives |
| Too short (<10 words) | Specificity score near zero | Flag: "Adding context will improve results" |
| No constraints | Completeness score low, no constraint markers | Append minimal constraints based on domain |
| Negation-heavy | Clarity penalized for negation | Rewrite negative directives to positive |
| No role assignment | Context score low, no role markers | Prepend role based on detected domain |
| Missing code delimiters | Code-like content without backticks | Wrap in appropriate code block |
| Contradictory instructions | "brief" + "detailed" coexist | Flag conflict to user |
| Politeness removal | Conciseness penalized for politeness | Strip "please", "could you kindly", etc. |

### Architecture

```python
@dataclass
class RuleResult:
    modified_prompt: str
    applied: bool
    description: str

# Each rule is a standalone pure function
def rule_add_output_format(prompt: str, score: ScoreResult) -> RuleResult
def rule_flag_vague_verbs(prompt: str, score: ScoreResult) -> RuleResult
# ... etc

@dataclass
class Tier0Result:
    enhanced: str
    rules_applied: list[str]

def apply_rules(prompt: str, score: ScoreResult) -> Tier0Result
```

Rules are ordered by impact. Each rule receives the scorer breakdown so it only fires when its relevant dimension is weak. Rules chain — output of one feeds input of next.

---

## 4. Tier 1 — Local LLM Provider

### Purpose

Generic OpenAI-compatible HTTP client for any local LLM tool (Ollama, LM Studio, llama.cpp, vLLM, LocalAI, Jan). No vendor lock-in.

### Interface

```python
class LocalProvider(BaseProvider):
    def __init__(self, model: str, host: str, api_key: str = "", **kwargs):
        super().__init__(api_key=api_key, model=model, **kwargs)
        self.host = host

    def enhance(self, prompt: str, system_prompt: str) -> str:
        # POST to {host}/v1/chat/completions
        # OpenAI-compatible format — works with all local tools
```

### BaseProvider Change

`api_key` becomes optional (default `""`):
```python
class BaseProvider(ABC):
    def __init__(self, api_key: str = "", model: str = "", **kwargs) -> None:
```

Existing providers pass `api_key` explicitly — no behavior change. All existing provider tests (`test_anthropic.py`, `test_openai.py`, `test_openrouter.py`) must be verified to still pass after this change.

### Edge Cases

- Host unreachable → fall back to Tier 0, clear error message
- Model not loaded → "Run `ollama pull qwen2.5:3b`" or "Start your local LLM server"
- Cold start (model loading) → spinner, 30s timeout, fall back to Tier 0
- Timeout mid-generation → fall back to Tier 0, notify user

---

## 5. Router (New Engine)

### Purpose

Replaces current `engine.py`. Orchestrates scoring, tier routing, context injection, formatting.

### Flow

```
1. Build context fingerprint (parallel, 400ms budget)
2. Score raw prompt → score
3. Apply Tier 0 rules (always) → tier0_result
4. Re-score tier0_result → post_tier0_score
5. Route:
   - post_tier0_score >= 70 OR max_tier == 0 → return tier0_result
   - max_tier >= 1 AND local LLM reachable → try Tier 1
   - max_tier >= 2 AND API key configured → try Tier 2
   - Fallback: always return tier0_result
6. Format output for target provider
7. Return EnhanceResult with full metadata
```

### Interface

```python
@dataclass
class EnhanceResult:
    original: str
    enhanced: str
    tier_used: int
    latency_ms: float
    score_before: ScoreResult
    score_after: ScoreResult
    rules_applied: list[str]
    context: ContextFingerprint | None
    format_style: str
    provider: str | None              # null for Tier 0
    model: str | None                 # null for Tier 0

def enhance(prompt: str, config: dict, **overrides) -> EnhanceResult
```

**Note:** `EnhanceResult` does not carry the user's decision (accept/reject/edit). The decision happens in the TUI layer, after the router returns. The CLI layer is responsible for composing `HistoryEntry` from `EnhanceResult` + the TUI decision, then recording it to history. See Section 11 for `HistoryEntry` definition.

### Design Principles

- **Graceful degradation**: Network down? Ollama not running? API key invalid? Always falls back to tier below. User always gets something.
- **Strategy pattern**: Router delegates to tier handlers. Adding a future tier means adding a handler, not modifying the router (Open/Closed Principle).
- **`--tier` CLI flag**: Forces specific tier, skips routing logic entirely. Overrides `max_tier` from config — if user explicitly passes `--tier 2`, it attempts Tier 2 even if `max_tier = 1` in config. Rationale: explicit CLI intent overrides config ceiling.

---

## 6. Context Fingerprinting

### Purpose

Automatically gathers environmental context and injects it into prompts before enhancement. Turns "fix the auth bug" into a context-rich prompt.

### Architecture — Collector Pattern

```
ContextFingerprint
├── GitCollector           (branch, commits, diff stats, status, stash)
├── ShellHistoryCollector  (recent commands, error patterns, session intent)
├── TechStackCollector     (marker files, dependency parsing, version managers)
├── EnvironmentCollector   (venv, container, CI, SSH detection)
├── SecretSanitizer        (regex + entropy filtering on ALL output)
└── ContextRanker          (weighted scoring, token budget allocation)
```

### Context Signals (priority order)

| Priority | Signal | Time | Source |
|---|---|---|---|
| 1 | Git branch name | <1ms | `git branch --show-current` |
| 2 | Recent commit messages (last 5) | ~5ms | `git log --format='%h\|%ar\|%s' -5` |
| 3 | Modified files | ~10ms | `git status --porcelain -uno` |
| 4 | Diff stats | ~10ms | `git diff --shortstat` |
| 5 | Tech stack markers | ~5ms | File existence checks |
| 6 | Recent shell commands | ~10ms | Tail of history file |
| 7 | Shell error patterns | ~10ms | Parsed from #6 |
| 8 | Framework details | ~20ms | package.json/pyproject.toml parse |
| 9 | Environment type | <5ms | Env var checks |
| 10 | Stash state | ~5ms | `git stash list` |

### Parallel Execution

All collectors run simultaneously via `concurrent.futures.ThreadPoolExecutor` with a global 400ms timeout. If any collector fails or times out, it's skipped — never blocks.

### Secret Sanitizer

Runs on ALL output before it leaves the system:

- **Known patterns**: `sk-`, `ghp_`, `AKIA`, Bearer tokens, DB connection strings, Slack tokens
- **Entropy detection**: Shannon entropy > 4.5 on base64-like strings
- **Keyword proximity**: `password=`, `api_key:`, `secret=` near values

### Session Intent Detection

| Shell history pattern | Detected intent | Effect |
|---|---|---|
| Repeated test commands with failures | Debugging session | Auto-shift to detailed mode |
| `git checkout -b feature/X` | Starting new feature | Greenfield context |
| `pip install` / `npm install` | Adding dependencies | Integration work context |
| `docker build`, `docker-compose up` | Container work | DevOps context |
| `curl` / `httpie` calls | API testing | API development context |

### Token Budget

500 tokens default (configurable). Compact key-value output, not prose. When trimming, drop from bottom of priority list up.

### Cross-Platform Design

- Git commands via `subprocess` with timeouts — works anywhere git exists
- Shell history: detects zsh/bash/fish by checking which history file exists
- File paths: `Path.home()` + XDG-style, no hardcoded paths
- Each collector is its own module — platform-specific variants easy to add

---

## 7. Prompt Quality Score (PQS)

### Purpose

User-facing quality display — shows 5 dimensions before/after with actionable suggestions. Reuses scorer internals, no duplicate computation.

### Why PQS, Not PEEM

PEEM (arXiv:2603.10477) uses GPT-4o-mini as evaluator (~$0.002/sample, ~1.2s). Cannot replicate in <1ms. PQS is a heuristic approximation inspired by PEEM's dimensions but is its own system.

### 5 Dimensions

| Dimension | Weight | Mapped from scorer | Combination formula |
|---|---|---|---|
| Clarity | 0.25 | Scorer's Clarity sub-score | Direct: `clarity_raw / clarity_max_weight` normalized to 0-100 |
| Specificity | 0.25 | Scorer's Specificity + Completeness | Weighted avg: `(specificity_raw * 25 + completeness_raw * 10) / 35` normalized to 0-100 |
| Context | 0.20 | Scorer's Context sub-score | Direct: `context_raw / context_max_weight` normalized to 0-100 |
| Structure | 0.15 | Scorer's Structure sub-score | Direct: `structure_raw / structure_max_weight` normalized to 0-100 |
| Actionability | 0.15 | Scorer's Actionability + Conciseness | Weighted avg: `(actionability_raw * 15 + conciseness_raw * 5) / 20` normalized to 0-100 |

Combined dimensions use weighted average proportional to each sub-dimension's max weight, ensuring fair normalization regardless of the different raw ranges.

### Interface

```python
@dataclass
class DimensionDisplay:
    score: int          # 0-100 normalized
    color: str          # "red" (0-39), "yellow" (40-69), "green" (70-100)
    bar: str            # Unicode block visualization "████████░░"
    suggestion: str     # Actionable fix from scorer's DimensionScore.suggestion

@dataclass
class PQScore:
    clarity: DimensionDisplay
    specificity: DimensionDisplay
    context: DimensionDisplay
    structure: DimensionDisplay
    actionability: DimensionDisplay
    overall: int                      # weighted composite 0-100

def compute_pqs(score_result: ScoreResult) -> PQScore
```

### Display

Color bands: Red (0-39), Yellow (40-69), Green (70-100). Unicode block characters for bars. Each dimension shows actionable suggestion ("Add output format specification").

Before/after delta is the key UX element — users care about improvement, not absolute numbers.

---

## 8. Provider-Specific Formatting

### Purpose

Same enhanced content wrapped differently depending on target LLM. Auto-detected from model ID.

### FormatStyle Enum

```python
class FormatStyle(Enum):
    XML = "xml"
    MARKDOWN = "markdown"
    PLAIN = "plain"
```

Use this enum throughout (config parsing, formatter selection, `EnhanceResult.format_style`) to avoid string literal errors.

### Three Format Styles

**XML** (Claude, Gemini):
```xml
<instructions>...</instructions>
<context>...</context>
<requirements>...</requirements>
```

**Markdown** (GPT, Mistral large, Grok, DeepSeek chat, Cohere, large models):
```markdown
## Role
...
## Task
...
## Requirements
...
```

**Plain** (DeepSeek R1, all models <7B, Phi, Gemma):
```
Role: ...
Task: ...
Requirements: ...
```

### Auto-Detection Chain

1. Strip provider prefix (OpenRouter `provider/model`, Together AI `Org/Model`, etc.)
2. Regex match against known model families → format style
3. Size-aware fallback: extract parameter count from ID (`70b`, `8b`, `3b`)
   - <7B → plain
   - 7B+ → markdown
4. Completely unknown → markdown (safest universal default)

### Known Model Family Map

```python
# Ordered list of tuples — checked top to bottom, first match wins.
# More specific patterns MUST come before broader ones.
MODEL_FORMAT_MAP: list[tuple[str, str]] = [
    # Plain preference (specific patterns — must match before broader family)
    (r"deepseek[-_/]?(reasoner|r1)", "plain"),
    (r"phi[-_]?\d", "plain"),
    (r"gemma[-_]?\d", "plain"),

    # XML preference
    (r"claude", "xml"),
    (r"gemini", "xml"),

    # Markdown preference
    (r"gpt[-_]?\d", "markdown"),
    (r"o[134][-_]?(mini|preview)?", "markdown"),
    (r"mistral[-_]?(large|medium)|mixtral|magistral", "markdown"),
    (r"codestral|devstral", "markdown"),
    (r"deepseek[-_/]?(chat|v[23]|coder)", "markdown"),
    (r"grok", "markdown"),
    (r"command[-_]?r", "markdown"),
    (r"jamba", "markdown"),
    (r"dbrx", "markdown"),
]

# Size-aware families — checked after MODEL_FORMAT_MAP finds no match
SIZE_AWARE_FAMILIES: list[tuple[str, dict]] = [
    (r"llama", {"threshold": 30, "above": "markdown", "below": "plain"}),
    (r"qwen", {"threshold": 30, "above": "markdown", "below": "plain"}),
    (r"mistral[-_]?(small|tiny)|ministral", {"force": "plain"}),
]
```

### User Override

```toml
[provider]
format_style = "auto"    # auto | xml | markdown | plain
```

CLI: `promptune enhance --format xml "my prompt"`

### Integration with Router

- **Tier 0**: Formatter wraps the rule engine output directly (we control the structure)
- **Tier 1/2**: System prompt instructs the AI to format for target provider. Formatter wraps system prompt, not the AI's output.

---

## 9. TUI Updates

### Default View (clean)

```
promptune  [Tier 0 · rules · 8ms]

┌─ Original ─────────────────┐  ┌─ Enhanced ──────────────────┐
│ fix the bug                │  │ Diagnose and fix the        │
│                            │  │ TypeScript compilation       │
│                            │  │ error in src/auth/redirect. │
└────────────────────────────┘  └─────────────────────────────┘

  [A] Accept   [E] Edit   [R] Reject   [?] More
```

### Toggle Keybindings

All keys trigger instantly on press (no Enter required), powered by `readchar`.

| Key | Action | Default |
|---|---|---|
| A | Accept enhanced prompt | Always visible |
| E | Edit enhanced prompt | Always visible |
| R | Reject, keep original | Always visible |
| ? | Show Q/D/C options | Always visible |
| Q | Toggle quality score breakdown | Hidden until ? |
| D | Toggle rules/details applied | Hidden until ? |
| C | Toggle context fingerprint | Hidden until ? |

### Quality Toggle (Q)

```
  Quality: 11 ──▶ 81  (+70)

  Clarity       ███░░░░░░░  34 ──▶ ████████░░  82  (+48)
  Specificity   ██░░░░░░░░  18 ──▶ █████████░  91  (+73)
  Context       █░░░░░░░░░  12 ──▶ ███████░░░  73  (+61)
  Structure     ████░░░░░░  45 ──▶ ████████░░  78  (+33)
  Actionability ███░░░░░░░  32 ──▶ ████████░░  83  (+51)
```

### Details Toggle (D)

```
  Rules applied: +output format, +constraints, -politeness
```

### Context Toggle (C)

```
  Context: branch=fix/auth-redirect | stack=typescript,nextjs
           last_error=TypeError: Cannot read 'token' | pkg=pnpm
```

### Diff Highlighting

Enhanced panel highlights changes: words added in green, structural additions underlined. Rich `Text` markup.

### Responsive

- Wide terminal (>=100 cols): side-by-side panels
- Narrow terminal (<100 cols): stacked panels
- Very narrow (<60 cols): score bars truncate, dimension names shorten
- Below 40 cols: numbers only, no bars

### `--no-tui` Mode

Prints only enhanced text to stdout. No scores, no panels. Shell widget and pipe usage unaffected.

---

## 10. New CLI Commands

### Enhancement Flags (added to existing `enhance`)

```bash
promptune enhance "text" --tier 0|1|2       # force specific tier
promptune enhance "text" --format xml|markdown|plain
promptune enhance "text" --json             # structured JSON output
```

### Config Subcommands (new)

```bash
promptune config --set-key claude sk-ant-...    # set API key for a provider
promptune config --set-key openai sk-...
promptune config --set-tier 1
promptune config --set-format markdown
promptune config --set-local-host http://localhost:1234
promptune config --set-local-model qwen2.5:3b
promptune config --reset
```

### Diagnostic Commands (new)

```bash
promptune doctor                            # full system health check
promptune local-llm-status                  # check local LLM connectivity
```

### History Commands (new)

```bash
promptune history                           # last 20 enhancements
promptune history --n 50                    # last N
promptune history --stats                   # acceptance rate, tier distribution
promptune history --clear                   # delete all (with confirmation)
```

### `--json` Output Schema

```json
{
  "original": "fix the bug",
  "enhanced": "Diagnose and fix...",
  "tier_used": 1,
  "latency_ms": 1823,
  "score_before": 11,
  "score_after": 81,
  "format_style": "xml",
  "rules_applied": ["output_format", "constraints"]
}
```

### `promptune doctor` Output

```
promptune doctor

  Python        ✓  3.12.1 (>=3.9 required)
  Config        ✓  ~/.config/promptune/config.toml
  Tier 0        ✓  Rule engine ready
  Tier 1        ✓  Local LLM at localhost:11434 (qwen2.5:3b responding)
  Tier 2        ✗  No API key configured for claude
  Format        ✓  Auto-detect (xml for claude)
  History DB    ✓  ~/.local/share/promptune/history.db (142 entries)
  Shell widget  ✓  Zsh widget detected in .zshrc

  Issues:
    - Set a cloud API key for Tier 2: promptune config --set-key claude sk-ant-...
```

Each diagnostic check is its own function — SRP, independently testable. Adding a check = adding a function.

---

## 11. SQLite History

### Purpose

Persistent storage of every enhancement. No learning, no preferences — just a queryable log. Learning loop deferred.

### Schema

```sql
CREATE TABLE enhancements (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    original        TEXT NOT NULL,
    enhanced        TEXT NOT NULL,
    decision        TEXT CHECK(decision IN ('accept', 'reject', 'edit')) NOT NULL,
    edit_result     TEXT,
    tier_used       INTEGER NOT NULL,
    provider        TEXT,
    format_style    TEXT,
    model           TEXT,
    score_before    INTEGER NOT NULL,
    score_after     INTEGER NOT NULL,
    latency_ms      REAL NOT NULL,
    rules_applied   TEXT,
    context_json    TEXT,
    project_root    TEXT,
    created_at      INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
);

CREATE INDEX idx_enhancements_created_at ON enhancements(created_at);
CREATE INDEX idx_enhancements_project ON enhancements(project_root);
```

### Interface

```python
@dataclass
class HistoryEntry:
    original: str
    enhanced: str
    decision: str                      # "accept" | "reject" | "edit"
    edit_result: str | None            # user's edited text if decision="edit"
    tier_used: int
    provider: str | None               # null for Tier 0
    format_style: str | None
    model: str | None                  # null for Tier 0
    score_before: int
    score_after: int
    latency_ms: float
    rules_applied: list[str] | None    # serialized as JSON in DB
    context_json: str | None           # serialized ContextFingerprint
    project_root: str | None

@dataclass
class HistoryStats:
    total: int
    accepted: int
    rejected: int
    edited: int
    acceptance_rate: float             # 0-1
    avg_score_before: float
    avg_score_after: float
    avg_improvement: float
    tier_distribution: dict[int, int]  # {0: 82, 1: 44, 2: 16}

class HistoryStore:
    def __init__(self, db_path: Path): ...
    def record(self, entry: HistoryEntry) -> int: ...
    def recent(self, n: int = 20, project: str | None = None) -> list[HistoryEntry]: ...
    def stats(self) -> HistoryStats: ...
    def clear(self) -> int: ...
```

**Who creates HistoryEntry:** The CLI layer (`cli.py`) composes `HistoryEntry` from `EnhanceResult` (returned by router) + the user's TUI decision. This keeps the router and TUI unaware of history concerns (SRP).

### Schema Versioning

```sql
PRAGMA user_version = 1;
```

On startup, `HistoryStore` checks `PRAGMA user_version`. If it's 0 (new DB), create tables and set version to 1. If it's less than current, run migration steps sequentially. This avoids needing a migration framework while supporting future schema changes.

### Storage

- Location: `~/.local/share/promptune/history.db`
- Created automatically on first enhancement
- SQLite bundled with Python — no extra dependency
- WAL mode for safe concurrent access
- ~500 bytes per entry, ~6 MB per year at heavy usage

### Edge Cases

- First run → auto-create directory + DB + schema
- DB corrupted → `PRAGMA integrity_check`, backup old, create fresh
- DB >100MB → auto-prune to last 10,000 entries
- Disk full → catch `OperationalError`, disable silently, one-time warning
- `history.enabled = false` → no file created, no writes

---

## Build Sequence

| Step | Module | Depends on | Key deliverable |
|---|---|---|---|
| 1 | Config migration | Nothing | New TOML schema, config.py rewrite, all test updates |
| 2 | Quality Scorer | Nothing | scorer.py — 7 dimensions, sigmoid calibration, typically <5ms |
| 3 | Tier 0 Rule Engine | Scorer | tier0.py — 9 rules, each a pure function |
| 4 | Tier 1 Local LLM | Config | providers/local.py — OpenAI-compatible HTTP client |
| 5 | Router | Config, Scorer, Tier 0, Tier 1 | New engine.py — tier routing + integration test. Must include minimal CLI adapter to keep existing `enhance` command working. |
| 6 | Context Fingerprinting | Nothing | context/ — 4 collectors + sanitizer, parallel |
| 7 | Prompt Quality Score | Scorer | pqs.py — 5-dimension display, reuses scorer |
| 8 | Provider Formatting | Config | formatters.py — 3 styles + auto-detect |
| 9 | TUI Updates | PQS, Router | Updated tui.py — header, toggles, color bars |
| 10 | CLI Commands | All above | New flags + doctor + local-llm-status + history |
| 11 | SQLite History | Config | history.py — storage, query, stats, auto-prune |

Each step follows RED → GREEN → REFACTOR. No step depends on something that hasn't been built and tested yet.

---

## Cross-Platform Considerations

| Concern | Approach |
|---|---|
| File paths | `Path.home()` + XDG-style, no hardcoded paths |
| Config | `~/.config/promptune/` (macOS, Linux, WSL) |
| Data | `~/.local/share/promptune/` (XDG standard) |
| Shell history | Detect zsh/bash/fish by history file existence |
| Git | `subprocess` with timeouts, works anywhere git exists |
| Curl install | `install.sh` checks OS/Python/pipx, extensible to Linux |
| Binary dist (future) | Nothing prevents PyInstaller/Homebrew packaging |
| Windows (future) | All deps work on Windows. Platform-specific code isolated |

---

## Engineering Standards

- **TDD**: RED (failing tests) → GREEN (minimal impl) → REFACTOR. Non-negotiable.
- **SOLID**: Single Responsibility (each module/function), Open/Closed (formatters, providers, collectors), Liskov (BaseProvider subtypes), Interface Segregation (small focused interfaces), Dependency Inversion (router depends on abstractions not concretions).
- **Coverage**: Target >=90% maintained throughout.
- **Linting**: `ruff check` must pass.
- **Type checking**: `mypy` strict mode must pass.
- **No heavy dependencies**: CLI must launch fast, stay small. No scikit-learn.
