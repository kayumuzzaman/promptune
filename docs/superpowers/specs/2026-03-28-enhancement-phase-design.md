# Enhancement Phase — Design Spec

**Date:** 2026-03-28
**Status:** Approved
**Scope:** Semantic deduplication, preference learning, team templates, Ollama auto-check

## Overview

The Enhancement Phase builds intelligence on top of the stable Phase 1 foundation. Four features ship in order: semantic deduplication, preference learning, team templates, and Ollama auto-check. Each is lightweight, follows TDD, and respects promptune's single-purpose, low-friction philosophy.

**Out of scope:** Linux installer (moved to Phase 3), OS-level daemon (Phase 2), any feature requiring new external dependencies.

---

## Feature 1: Semantic Deduplication

### Purpose

Avoid re-enhancing prompts the user has already enhanced recently in the same project. Returns the cached result instantly, saving API calls and latency.

### Architecture

New module: `promptune/dedup.py`

- Minimal TF-IDF cosine similarity implementation using Python stdlib only (no numpy/sklearn)
- Queries recent enhanced prompts from `HistoryStore` filtered by `project_root`
- Compares input prompt against stored originals
- If similarity exceeds threshold, returns cached enhanced text

### Integration

Early exit in `engine.py` before tier routing:

```
Input prompt
    |
    v
dedup.check(prompt, project_root)
    |
    +-- hit  --> return cached result (flag as "cached")
    +-- miss --> continue to Tier 0/1/2
```

### Dedup Candidate Selection

- Only prompts with `decision = 'accept'` or `decision = 'edit'` are candidates
- Rejected prompts are excluded (user didn't want that enhancement)
- For edited prompts, use `edit_result` as the cached output (user's preferred version)
- Falls back to `enhanced` if `edit_result` is null

### Config

```toml
[enhancement]
dedup_enabled = true
dedup_threshold = 0.85      # cosine similarity, 0.0-1.0
dedup_window = 50           # compare against last N enhancements per project
```

### Edge Cases

| Case | Behaviour |
|------|-----------|
| Empty history | No dedup, pass through |
| All recent entries rejected | No candidates, pass through |
| Threshold = 1.0 | Only exact matches |
| Threshold = 0.0 | Everything matches (not useful, but valid) |
| Prompt shorter than 3 words | Skip dedup (too short for meaningful similarity) |

---

## Feature 2: Preference Learning Engine

### Purpose

Analyse accept/reject/edit history to learn what the user likes and dislikes, then adapt future enhancements accordingly. No external dependencies, no separate database.

### Architecture

New module: `promptune/preferences.py`

Preferences are computed on-demand from history — no separate storage. Cached in memory for the session.

### Pattern Detection

Three types of patterns, kept deliberately simple:

**1. Rule rejection patterns:**
- Query history entries where a specific Tier 0 rule appears in `rules_applied`
- If that rule correlates with `decision = 'reject'` more than 60% of the time (with at least `preference_min_samples` data points), flag the rule as disliked

**2. Edit patterns:**
- Diff `enhanced` vs `edit_result` across entries with `decision = 'edit'`
- Look for repeated removals using basic string matching:
  - Lines starting with "You are a..." consistently removed -> "skip role assignment"
  - Output format sections consistently removed -> "skip output format"
  - Bullet points consistently changed to prose or vice versa

**3. Acceptance patterns:**
- Rules/tiers consistently accepted reinforce confidence
- Used to maintain positive preferences, not just negative ones

### Integration

`engine.py` loads preferences before enhancement:
- Tier 0: skips rules the user has shown they dislike
- Tier 1/2: includes a "user preferences" section in the prompt sent to the LLM (e.g., "Do not add role assignment. Keep responses concise.")

### CLI

- `promptune history --preferences` — show learned preferences with confidence scores

### Config

```toml
[enhancement]
preference_learning = true
preference_min_samples = 5    # minimum data points before learning a preference
```

### Edge Cases

| Case | Behaviour |
|------|-----------|
| Fewer than min_samples entries | No preferences learned, enhance normally |
| Conflicting signals (50/50 accept/reject for same rule) | No preference learned for that rule |
| No edit_result stored | Skip edit pattern analysis for that entry |
| All history cleared | Preferences reset (they are derived, not stored) |

---

## Feature 3: Team `.prompts/` Templates

### Purpose

Allow teams to define project-level prompt templates that automatically apply when the user's prompt matches the template's intent/domain. Zero-friction — presence of `.prompts/` directory is the opt-in.

### Architecture

New module: `promptune/templates.py`

### Template Format

```markdown
---
intent: debug
domain: python
---
## Bug Context
Stack: {{stack}} | Branch: {{branch}}

## Steps to Reproduce

## Expected vs Actual
```

- Frontmatter declares match conditions: `intent`, `domain`, or both
- Body contains template text with `{{variable}}` placeholders
- Files must be `.md` in the `.prompts/` directory at project root

### Matching Rules

1. On enhancement, check if `project_root/.prompts/` exists
2. Load all `.md` files, parse frontmatter
3. Match against detected intent/domain from `meta_prompt.py`
4. If both `intent` and `domain` are specified in frontmatter, both must match
5. If only one field specified, that one suffices
6. Multiple matches: most specific wins (intent+domain beats single field)
7. No match: enhance normally, zero overhead

### Variable Injection

Available variables (all sourced from existing modules):

| Variable | Source |
|----------|--------|
| `{{stack}}` | `context/collectors.py` — tech stack detection |
| `{{branch}}` | `context/collectors.py` — git branch |
| `{{intent}}` | `meta_prompt.py` — detected intent |
| `{{domain}}` | `meta_prompt.py` — detected domain |
| `{{project_root}}` | `context/collectors.py` — project root path |

Undefined variables are left as-is (not removed, not errored).

### Integration

Between meta_prompt detection and tier routing in `engine.py`:

```
Input prompt
    |
    v
meta_prompt.detect(prompt) -> intent, domain
    |
    v
templates.match(project_root, intent, domain)
    |
    +-- match found  --> prepend template to context for Tier 1/2
    +-- no match     --> continue normally
    |
    v
Tier 0/1/2 enhancement (Tier 0 rules still apply on top)
```

### Edge Cases

| Case | Behaviour |
|------|-----------|
| No `.prompts/` directory | Skip entirely, zero overhead |
| Empty `.prompts/` directory | Skip, no templates to load |
| Template with no frontmatter | Ignored (no match conditions) |
| Template with invalid frontmatter | Ignored with warning logged |
| Unknown `{{variable}}` | Left as-is in output |
| Multiple templates tie on specificity | Alphabetically first wins |

---

## Feature 4: Ollama Auto-Check in Installer

### Purpose

Inform the user about Ollama availability during installation. Detect-and-inform only — never installs anything automatically.

### Implementation

Addition to `install.sh`, runs at the end after main installation.

### Checks

1. Is `ollama` binary on PATH?
2. If yes, is Ollama server running? (`curl -s http://localhost:11434/api/tags`)
3. If running, is the configured model (`qwen2.5:3b`) available?

### Output

```
--- Ollama Status ---
OK:   Ollama found at /usr/local/bin/ollama
OK:   Ollama server running
OK:   Model qwen2.5:3b available
```

```
--- Ollama Status ---
MISS: Ollama not found
      Install: https://ollama.com/download
      Then run: ollama pull qwen2.5:3b
```

```
--- Ollama Status ---
OK:   Ollama found at /usr/local/bin/ollama
MISS: Model qwen2.5:3b not available
      Run: ollama pull qwen2.5:3b
```

### Constraints

- Informational only — never blocks installation
- Never installs Ollama or pulls models automatically
- Runs after all other install steps complete
- Failure to check (e.g., curl not available) is silently skipped

---

## Build Order

1. **Semantic deduplication** — self-contained, touches history + engine
2. **Preference learning** — builds on same history data, adds analysis layer
3. **Team templates** — new subsystem, integrates with meta_prompt + engine
4. **Ollama auto-check** — small installer change, independent

## Development Approach

- **TDD** — tests first for every feature
- **Ralph Loop** — practice during development
- **Lightweight** — stdlib only for dedup (no numpy/sklearn), no new database tables for preferences
- **Per-project** — dedup and preferences scoped to `project_root`

## Config Summary (additions to config.toml)

```toml
[enhancement]
dedup_enabled = true
dedup_threshold = 0.85
dedup_window = 50
preference_learning = true
preference_min_samples = 5
```

## New Files

| File | Purpose |
|------|---------|
| `promptune/dedup.py` | TF-IDF similarity checker |
| `promptune/preferences.py` | Preference learning from history |
| `promptune/templates.py` | Team template loading and matching |
| `tests/test_dedup.py` | Dedup tests |
| `tests/test_preferences.py` | Preference learning tests |
| `tests/test_templates.py` | Template tests |

## Modified Files

| File | Change |
|------|--------|
| `promptune/engine.py` | Add dedup early-exit, preference loading, template injection |
| `promptune/config.py` | Add new config keys with defaults |
| `promptune/cli.py` | Add `--preferences` flag to history command |
| `install.sh` | Add Ollama detection at end |
| `tests/test_engine.py` | Test integration of new features |
| `tests/test_cli.py` | Test `--preferences` flag |
| `tests/test_install.sh` | Test Ollama check output |
