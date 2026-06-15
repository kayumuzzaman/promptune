# Promptune Manual Testing Guide

This document provides a comprehensive, step-by-step manual testing plan for every feature of promptune. It is intended for the first full manual test of the tool.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Installation](#2-installation)
3. [Config Init (Interactive Wizard)](#3-config-init-interactive-wizard)
4. [Config Management](#4-config-management)
5. [Enhance Command (Basic)](#5-enhance-command-basic)
6. [Tier 0 Rule Engine (9 Rules)](#6-tier-0-rule-engine-9-rules)
7. [Tier 1 (Local LLM via Ollama)](#7-tier-1-local-llm-via-ollama)
8. [Tier 2 (Cloud API)](#8-tier-2-cloud-api)
9. [Tier Routing Logic](#9-tier-routing-logic)
10. [Scoring and PQS](#10-scoring-and-pqs)
11. [Doctor Command](#11-doctor-command)
12. [History Command](#12-history-command)
13. [Context Fingerprinting](#13-context-fingerprinting)
14. [Provider-Specific Formatting](#14-provider-specific-formatting)
15. [Semantic Deduplication](#15-semantic-deduplication)
16. [Preference Learning](#16-preference-learning)
17. [Team Templates](#17-team-templates)
18. [TUI (Accept/Edit/Reject)](#18-tui-accepteditreject)
19. [Shell Widget](#19-shell-widget)
20. [Shell-Init Command](#20-shell-init-command)
21. [Config Edge Cases and Error Handling](#21-config-edge-cases-and-error-handling)
22. [Error Handling](#22-error-handling)
23. [Score Command](#23-score-command)
24. [Auto-Enhance Gate](#24-auto-enhance-gate)
25. [MCP Server](#25-mcp-server)
23. [Installer Script](#23-installer-script)
24. [Daemon — Lifecycle](#24-daemon--lifecycle)
25. [Daemon — Hotkey and Enhancement Pipeline](#25-daemon--hotkey-and-enhancement-pipeline)
26. [Daemon — Notifications and IPC](#26-daemon--notifications-and-ipc)
27. [Daemon — LaunchAgent and Diagnostics](#27-daemon--launchagent-and-diagnostics)
28. [Linux Daemon (Phase 3)](#28-linux-daemon-phase-3)
29. [Regression Checklist](#29-regression-checklist)

---

## 1. Prerequisites

### Environment Setup

- [ ] macOS or Linux (X11 or Wayland) machine available
- [ ] Python 3.9+ installed (`python3 --version`)
- [ ] Git installed (`git --version`)
- [ ] Zsh, Bash, or Fish shell available for shell widget testing
- [ ] Terminal that supports keybindings (iTerm2, Terminal.app, Kitty, etc. -- NOT Warp)

**Linux-only prerequisites (for daemon testing):**
- [ ] Display server type known: `echo $XDG_SESSION_TYPE` (x11 or wayland)
- [ ] X11: `xclip` and `xdotool` installed (`sudo apt install xclip xdotool`)
- [ ] Wayland: `wl-clipboard` and `ydotool` installed (`sudo apt install wl-clipboard ydotool`)
- [ ] Optional: `notify-send` for desktop notifications (`sudo apt install libnotify-bin`)
- [ ] Python Linux extras installed: `pip install promptune[linux-daemon]`
- [ ] (Wayland evdev fallback) User in `input` group: `groups | grep input`

### API Keys (needed for Tier 2 tests)

Have at least one of the following ready:
- [ ] Claude API key (`sk-ant-...`) from https://console.anthropic.com/
- [ ] OpenAI API key (`sk-...`) from https://platform.openai.com/api-keys
- [ ] OpenRouter API key (`sk-or-...`) from https://openrouter.ai/keys

### Local LLM (needed for Tier 1 tests)

- [ ] Ollama installed from https://ollama.com/download
- [ ] Ollama server running (`ollama serve`)
- [ ] Model pulled (`ollama pull qwen2.5:3b`)

### Project Setup

```bash
git clone https://github.com/kayumuzzaman/promptune.git
cd promptune
```

---

## 2. Installation

### 2.1 Dev Install

```bash
pip install -e ".[dev]"
```

- [ ] Command completes without errors
- [ ] All dependencies install (click, rich, prompt_toolkit, anthropic, openai, httpx, readchar, etc.)

### 2.2 Verify Binary Available

```bash
promptune version
```

- [ ] Prints version string (e.g., `0.1.0`)
- [ ] Exit code is 0

### 2.3 Verify Module Execution

```bash
python -m promptune version
```

- [ ] Prints the same version string as `promptune version`

### 2.4 Help Text

```bash
promptune --help
```

- [ ] Lists all commands: `enhance`, `config`, `shell-init`, `doctor`, `history`, `local-llm-status`, `version`
- [ ] No import errors or tracebacks

```bash
promptune enhance --help
```

- [ ] Lists all flags: `--provider`/`-p`, `--style`/`-s`, `--no-tui`, `--tier`, `--format`, `--json`

### 2.5 Edge Case: Wrong Python Version

If you can test with Python 3.8:

- [ ] `pip install -e .` fails or warns about version incompatibility

---

## 3. Config Init (Interactive Wizard)

### 3.1 First-Time Setup

Delete any existing config first:

```bash
rm -f ~/.config/promptune/config.toml
promptune config init
```

Expected flow:

```
  Promptune Setup
  ---------------

  Provider [claude/openai/openrouter] (claude):
```

- [ ] Wizard header displays with "Promptune Setup" and separator line
- [ ] Provider prompt appears with choices and `claude` as default
- [ ] Press Enter to accept default `claude`

Before the key prompt, a tier overview is printed:

```
  How Promptune enhances your prompts:
    Tier 0  Rule-based rewrite       FREE  · offline, no key
    Tier 1  Local LLM (Ollama, …)    FREE  · private, no key
    Tier 2  Cloud LLM (Claude/GPT)   PAID  · needs an API key
```

- [ ] Tier overview lists Tier 0 & 1 as FREE and Tier 2 as PAID

Next prompt:

```
  Tier 2 (cloud) uses a PAID API key. Leave blank to skip it and
  use the free tiers (rules + local LLM) only.
  Claude API key (blank = free mode):
```

- [ ] API key input is masked (hidden characters)
- [ ] Entering a valid `sk-ant-...` key prints: `Key format looks valid.`
- [ ] Pressing Enter with empty input accepts free mode and prints: `✓ No API key set — free mode: Tier 0 (rules) + Tier 1 (local LLM).`

Next prompt:

```
  Configure advanced settings? [y/N]:
```

- [ ] Pressing Enter or `n` skips advanced settings
- [ ] Final message prints: `Config saved to ~/.config/promptune/config.toml`
- [ ] Config file actually exists at `~/.config/promptune/config.toml`
- [ ] Config file contains the provider and API key you entered

### 3.2 Re-Run with Existing Config

```bash
promptune config init
```

- [ ] Previous values are pre-filled as defaults
- [ ] API key prompt shows masked existing key (e.g., `[sk-...4z7x]`)
- [ ] Pressing Enter keeps the existing value
- [ ] Changing provider to `openai` prompts for OpenAI API key

### 3.3 Advanced Settings Flow

```bash
promptune config init
```

Accept provider and key, then answer `y` to advanced settings:

- [ ] Enhancement style prompt appears with choices `minimal/balanced/detailed`, default `balanced`
- [ ] Max tier prompt appears with choices `0/1/2`, default `2`
- [ ] Format style prompt appears with choices `auto/xml/markdown/plain`, default `auto`
- [ ] All chosen values are written to config file

### 3.4 Each Provider Path

Test config init selecting each provider:

- [ ] Select `claude`: prompts for Claude API key, validates `sk-ant-` prefix
- [ ] Select `openai`: prompts for OpenAI API key, validates `sk-` prefix
- [ ] Select `openrouter`: prompts for OpenRouter API key, validates `sk-or-` prefix

### 3.5 Invalid API Key Prefix Warning

```bash
promptune config init
```

Select `claude`, then enter a key like `sk-not-a-claude-key`:

- [ ] Warning displays: `Warning: Key doesn't look like a claude key (expected prefix 'sk-ant-'). Saving anyway.`
- [ ] Key is saved despite the warning

### 3.6 Non-Interactive Mode

```bash
echo "test" | promptune config init
```

- [ ] Does NOT launch the interactive wizard
- [ ] Creates a default config file if none exists
- [ ] Prints to stderr: `No terminal detected. Config file created with defaults at: ...`

### 3.7 Ctrl+C Cancellation

Start `promptune config init`, then press Ctrl+C at any prompt:

- [ ] Prints `Setup cancelled.` to stderr
- [ ] No partial config file is written (or existing config is unchanged)
- [ ] Exit code is 130

### 3.8 Custom Config Directory

```bash
promptune config init --config-dir /tmp/promptune-test
```

- [ ] Config file created at `/tmp/promptune-test/config.toml`
- [ ] Parent directory created if it did not exist

---

## 4. Config Management

### 4.1 Config Show

```bash
promptune config show
```

- [ ] Prints all config sections: `[provider]`, `[api_keys]`, `[enhancement]`, `[local_llm]`, `[context]`, `[history]`, `[tui]`
- [ ] Values match what was set during `config init`

### 4.2 Config Path

```bash
promptune config path
```

- [ ] Prints `~/.config/promptune/config.toml` (expanded path)

### 4.3 Set API Key

```bash
promptune config --set-key claude sk-ant-test-key-12345
```

- [ ] Prints: `API key set for claude.`
- [ ] Config file now contains `claude = "sk-ant-test-key-12345"` under `[api_keys]`

### 4.4 Set Max Tier

```bash
promptune config --set-tier 1
```

- [ ] Prints: `Max tier set to 1.`
- [ ] Config file now contains `max_tier = 1` under `[enhancement]`

### 4.5 Reset Config

```bash
promptune config --reset
```

- [ ] Prompts for confirmation: `Reset config to defaults?`
- [ ] Answering `y` resets the config file
- [ ] All API keys are now empty in the config
- [ ] Default values restored (provider=claude, max_tier=2, default_mode=balanced, etc.)

---

## 5. Enhance Command (Basic)

### 5.1 Basic Enhancement (No TUI)

First, ensure you have a valid config. For Tier 0 only testing:

```bash
promptune config --set-tier 0
```

```bash
promptune enhance --no-tui "make a todo app"
```

- [ ] Prints an enhanced version of the prompt to stdout
- [ ] Enhanced prompt is longer/more structured than the input
- [ ] Exit code is 0

### 5.2 Empty Prompt

```bash
promptune enhance --no-tui ""
```

- [ ] Prints `Error: Empty prompt.` to stderr
- [ ] Exit code is 1

### 5.3 No Prompt Argument (No Pipe)

```bash
promptune enhance --no-tui
```

- [ ] Prints `Error: Empty prompt.` to stderr
- [ ] Exit code is 1

### 5.4 Piped Input

```bash
echo "build a REST API" | promptune enhance --no-tui
```

- [ ] Reads prompt from stdin
- [ ] Prints enhanced prompt to stdout

### 5.5 JSON Output

```bash
promptune enhance --json "make a todo app"
```

- [ ] Output is valid JSON
- [ ] Contains fields: `original`, `enhanced`, `tier_used`, `latency_ms`, `score_before`, `score_after`, `format_style`, `rules_applied`
- [ ] `tier_used` is `0` when max_tier is set to 0
- [ ] `rules_applied` is a list of rule names

### 5.6 Style Override

```bash
promptune enhance --no-tui -s minimal "build a payment system"
promptune enhance --no-tui -s detailed "build a payment system"
```

- [ ] Both commands succeed
- [ ] `detailed` style enhancement is more comprehensive than `minimal`

### 5.7 Tier Override

```bash
promptune enhance --no-tui --tier 0 "make a todo app"
```

- [ ] Uses only Tier 0 rules (check with `--json` that `tier_used` is 0)

### 5.8 Format Override

```bash
promptune enhance --no-tui --format xml "explain kubernetes networking"
promptune enhance --no-tui --format markdown "explain kubernetes networking"
promptune enhance --no-tui --format plain "explain kubernetes networking"
```

- [ ] All three commands succeed
- [ ] JSON output shows the corresponding `format_style`

### 5.9 Provider Override

```bash
promptune enhance --no-tui -p openai "optimize this SQL query"
```

- [ ] If OpenAI key is set: Uses OpenAI for enhancement
- [ ] If OpenAI key is NOT set: Falls back gracefully or shows error

### 5.10 Combined Flags

```bash
promptune enhance -s detailed --format xml --no-tui --tier 0 "design a caching layer"
```

- [ ] All flags work together without conflict

### 5.11 Clipboard Pipeline (macOS)

```bash
promptune enhance --no-tui "refactor the user service" | pbcopy
pbpaste
```

- [ ] Enhanced prompt is in clipboard

### 5.12 Environment Variable Override

```bash
PROMPTUNE_PROVIDER=openai promptune enhance --json --tier 0 "hello world"
```

- [ ] Provider in config is respected or overridden (check behavior)

---

## 6. Tier 0 Rule Engine (9 Rules)

For all tests below, force Tier 0 only and use JSON output to inspect:

```bash
promptune config --set-tier 0
```

### 6.1 Rule: Politeness Removal

Input with politeness phrases:

```bash
promptune enhance --json "could you please kindly help me write a function to sort a list"
```

- [ ] `rules_applied` contains `"politeness_removal"`
- [ ] Enhanced prompt has "could you please kindly" removed
- [ ] Words like "help" may also be replaced by vague verb rule

### 6.2 Rule: Negation Rewrite

Input with negative directives:

```bash
promptune enhance --json "don't use global variables and never use eval in the code, do not forget error handling"
```

- [ ] `rules_applied` contains `"negation_rewrite"`
- [ ] "don't use" becomes "avoid using"
- [ ] "never use" becomes "avoid"
- [ ] "do not forget" becomes "remember to" (or "avoid")

### 6.3 Rule: Vague Verbs

Input with vague verbs:

```bash
promptune enhance --json "make a thing to handle user data and fix the login"
```

- [ ] `rules_applied` contains `"vague_verbs"`
- [ ] "make" replaced with "create"
- [ ] "handle" replaced with "process"
- [ ] "fix" replaced with "diagnose and fix"

### 6.4 Rule: Role Assignment

Input with no role context:

```bash
promptune enhance --json "sort an array of integers"
```

- [ ] `rules_applied` contains `"role_assignment"`
- [ ] Enhanced prompt starts with a role like "You are an experienced software developer."

### 6.5 Rule: Output Format

Input lacking output format specification:

```bash
promptune enhance --json "explain how garbage collection works in Java"
```

- [ ] `rules_applied` contains `"output_format"`
- [ ] Enhanced prompt has an appended format instruction (e.g., "Provide a structured explanation with key points.")

### 6.6 Rule: Constraints

Input lacking constraints:

```bash
promptune enhance --json "build a REST API for users"
```

- [ ] `rules_applied` contains `"constraints"`
- [ ] Enhanced prompt has appended constraints (e.g., "Consider edge cases, error handling, and performance.")

### 6.7 Rule: Code Delimiters

Input with code-like content not wrapped in backticks:

```bash
promptune enhance --json "review this code:
def calculate(x, y):
    return x + y
class Calculator:
    pass"
```

- [ ] `rules_applied` contains `"code_delimiters"`
- [ ] Code-like lines are wrapped in triple backtick code blocks

### 6.8 Rule: Contradictory Instructions

Input with contradictory terms:

```bash
promptune enhance --json "give me a brief but detailed explanation of quantum computing with a short but comprehensive overview"
```

- [ ] `rules_applied` contains `"contradictions"`
- [ ] Enhanced prompt includes a warning: `[Warning: Contradictory instructions detected -- consider clarifying scope.]`

### 6.9 Rule: Too Short

Very short input:

```bash
promptune enhance --json "todo"
```

- [ ] `rules_applied` contains `"too_short"`
- [ ] Enhanced prompt includes: `[Note: Adding more context and detail will improve results.]`

### 6.10 Multiple Rules Chaining

Input that triggers multiple rules:

```bash
promptune enhance --json "please help me do something with the API"
```

- [ ] `rules_applied` contains multiple entries (likely: `politeness_removal`, `vague_verbs`, `role_assignment`, `output_format`, `constraints`, `too_short`)
- [ ] Rules chain in order: politeness first, then negation, vague verbs, role, format, constraints, code delimiters, contradictions, too_short

### 6.11 Well-Formed Prompt (No Rules Trigger)

Input that should score well and trigger few/no rules:

```bash
promptune enhance --json "You are a senior Python developer. Implement a REST API endpoint using Flask that accepts POST requests to /api/users with JSON body containing name and email fields. Validate inputs, return 201 on success with the created user object as JSON, and return 400 with error details on invalid input. Include proper error handling and type hints."
```

- [ ] `rules_applied` is empty or contains very few rules
- [ ] `score_before` is relatively high (likely 50+)
- [ ] Enhanced prompt is similar to the original

---

## 7. Tier 1 (Local LLM via Ollama)

### Prerequisites

```bash
ollama serve   # in a separate terminal
ollama pull qwen2.5:3b
```

### 7.1 Local LLM Status Check

```bash
promptune local-llm-status
```

- [ ] If Ollama running: `Local LLM  [checkmark]  qwen2.5:3b responding at http://localhost:11434`
- [ ] If Ollama not running: `Local LLM  [X]  Cannot reach http://localhost:11434: ...`

### 7.2 Force Tier 1

```bash
promptune config --set-tier 1
promptune enhance --no-tui --tier 1 "build a simple calculator in Python"
```

- [ ] Enhancement uses local LLM (verify with `--json` that `tier_used` is 1)
- [ ] Enhanced prompt is more comprehensive than Tier 0 output
- [ ] `latency_ms` is typically 1000-10000ms depending on hardware

### 7.3 Tier 1 Fallback When Ollama Not Running

Stop Ollama, then:

```bash
promptune enhance --no-tui "build a calculator"
```

- [ ] Falls back to Tier 0 (does not crash)
- [ ] JSON output shows `tier_used: 0`

---

## 8. Tier 2 (Cloud API)

### 8.1 Force Tier 2 with Claude

```bash
promptune config --set-key claude YOUR_ACTUAL_CLAUDE_KEY
promptune config --set-tier 2
promptune enhance --no-tui --tier 2 "build a simple calculator in Python"
```

- [ ] Enhancement uses cloud API (verify with `--json` that `tier_used` is 2)
- [ ] Response is higher quality than Tier 0/1
- [ ] `provider` shows `"claude"` in JSON output

### 8.2 Force Tier 2 with OpenAI

```bash
promptune config --set-key openai YOUR_ACTUAL_OPENAI_KEY
promptune enhance --no-tui -p openai --tier 2 "build a simple calculator in Python"
```

- [ ] `tier_used` is 2, `provider` is `"openai"` in JSON output

### 8.3 Force Tier 2 with OpenRouter

```bash
promptune config --set-key openrouter YOUR_ACTUAL_OPENROUTER_KEY
promptune enhance --no-tui -p openrouter --tier 2 "build a simple calculator in Python"
```

- [ ] `tier_used` is 2, `provider` is `"openrouter"` in JSON output

### 8.4 Missing API Key for Tier 2

```bash
promptune config --set-key claude ""
promptune enhance --no-tui --tier 2 "build a calculator"
```

- [ ] Error message about missing API key
- [ ] If not forced tier, falls back to Tier 0

---

## 9. Tier Routing Logic

### 9.1 Score-Based Routing

The router uses score thresholds: score >= 70 stays at Tier 0, score < 70 escalates.

Test with a high-quality prompt (should stay Tier 0):

```bash
promptune config --set-tier 2
promptune enhance --json "You are a senior backend engineer. Implement a rate limiter middleware for Express.js that limits requests to 100 per minute per IP address. Use a sliding window algorithm. Store counters in Redis. Return HTTP 429 with a Retry-After header when the limit is exceeded. Include TypeScript type definitions and unit tests."
```

- [ ] `score_before` is likely >= 70 (well-formed prompt)
- [ ] `tier_used` is 0 (stays at Tier 0 because score is high enough)

Test with a low-quality prompt (should escalate):

```bash
promptune enhance --json "fix bug"
```

- [ ] `score_before` is very low (likely < 40)
- [ ] `tier_used` is 1 or 2 (escalated to higher tier)
- [ ] If no higher tier available, falls back to Tier 0

### 9.2 Forced Tier Overrides Max Tier Config

```bash
promptune config --set-tier 0
promptune enhance --json --tier 2 "fix bug"
```

- [ ] `tier_used` is 2 despite `max_tier = 0` in config (CLI `--tier` overrides config ceiling)

### 9.3 Graceful Degradation Chain

With Ollama stopped and no cloud API key:

```bash
promptune config --set-tier 2
promptune config --set-key claude ""
promptune config --set-key openai ""
promptune config --set-key openrouter ""
```

```bash
promptune enhance --no-tui "fix the bug"
```

- [ ] Falls back to Tier 0 (does not crash)
- [ ] Enhanced prompt has Tier 0 rule improvements applied

---

## 10. Scoring and PQS

### 10.1 Score Display in JSON

```bash
promptune enhance --json "hello"
```

- [ ] `score_before` is a number 0-100
- [ ] `score_after` is >= `score_before` (enhancement should improve score)

### 10.2 Score Improvement

Compare scores for prompts of varying quality:

```bash
promptune enhance --json --tier 0 "do stuff"
```

- [ ] `score_before` should be very low (< 30)

```bash
promptune enhance --json --tier 0 "Implement a user authentication system using JWT tokens with refresh token rotation, storing sessions in Redis with a 15-minute access token TTL"
```

- [ ] `score_before` should be much higher (50+)

### 10.3 Seven Dimensions Verified

The scorer computes: specificity, clarity, structure, actionability, context, completeness, conciseness. These are internal but reflected in the total score. Verify indirectly:

```bash
# High specificity (tech terms, constraints)
promptune enhance --json --tier 0 "Build a PostgreSQL REST API with JWT auth, rate limiting at 100 req/min"
```

- [ ] Score is notably higher than a vague prompt

```bash
# High structure (markdown headers, lists)
promptune enhance --json --tier 0 "## Task
Build a login page
## Requirements
- Email validation
- Password strength check
- OAuth support"
```

- [ ] Score reflects the structural elements

### 10.4 Intent Detection

```bash
# Coding intent
promptune enhance --json --tier 0 "implement a REST API endpoint"
```

- [ ] Intent is detected as "coding" (role assigned as "software developer")

```bash
# Writing intent
promptune enhance --json --tier 0 "write a blog post about machine learning"
```

- [ ] Intent is detected as "writing" (role assigned as "technical writer")

```bash
# Research intent
promptune enhance --json --tier 0 "explain how neural networks work"
```

- [ ] Intent is detected as "research" (role assigned as "research analyst")

---

## 11. Doctor Command

### 11.1 Basic Doctor Output

```bash
promptune doctor
```

- [ ] Displays all check categories: Python, Config, Tier 0, Tier 1, Tier 2, Shell Widget
- [ ] Each line shows a checkmark or X with a detail message
- [ ] Python check shows version and `(>=3.9 required)`
- [ ] Config check shows the config file path
- [ ] Tier 0 always shows: `Rule engine ready`

### 11.2 Doctor with Full Setup

With config, API key, and Ollama running:

- [ ] Python: checkmark
- [ ] Config: checkmark
- [ ] Tier 0: checkmark
- [ ] Tier 1: checkmark (shows local LLM host)
- [ ] Tier 2: checkmark (shows `API key set for <provider>`)
- [ ] Shell Widget: checkmark (if not in Warp)

### 11.3 Doctor with Missing Config

```bash
rm ~/.config/promptune/config.toml
promptune doctor
```

- [ ] Config check shows X
- [ ] Other checks may show errors due to missing config but command does not crash

### 11.4 Doctor in Warp Terminal

Set `TERM_PROGRAM=WarpTerminal`:

```bash
TERM_PROGRAM=WarpTerminal promptune doctor
```

- [ ] Shell Widget check shows X with message about Warp not supporting the widget

### 11.5 Issues Summary

When there are failures:

- [ ] An "Issues:" section appears at the bottom listing all failing checks

---

## 12. History Command

### 12.1 Empty History

Clear history first (or use a fresh database):

```bash
promptune history --clear
```

Then:

```bash
promptune history
```

- [ ] Prints: `No history yet.`

### 12.2 Generate History Entries

Run several enhancements through the TUI to generate Accept/Reject/Edit decisions:

```bash
promptune enhance "make a todo app"
# Press A to accept

promptune enhance "fix the login bug"
# Press R to reject

promptune enhance "build a REST API"
# Press E to edit, make a change, then confirm
```

### 12.3 List Recent History

```bash
promptune history
```

- [ ] Shows up to 20 recent entries
- [ ] Each entry shows: `[tier] original_prompt_truncated... -> score_before -> score_after`

```bash
promptune history --n 5
```

- [ ] Shows only 5 entries

### 12.4 History Stats

```bash
promptune history --stats
```

- [ ] Shows: Total, Accepted (with %), Rejected, Edited
- [ ] Shows: Avg before, Avg after, Avg improve
- [ ] Numbers are consistent with the entries you created

### 12.5 History Preferences

```bash
promptune history --preferences
```

- [ ] If fewer than `preference_min_samples` entries: `No preferences learned yet.`
- [ ] If enough entries exist: Shows rule preferences and edit patterns with confidence scores

### 12.6 Clear History

```bash
promptune history --clear
```

- [ ] Prompts for confirmation: `Delete all history?`
- [ ] Answering `y` deletes entries and shows count
- [ ] Answering `n` cancels

### 12.7 History Disabled

Set `history.enabled = false` in config, then:

```bash
promptune history
```

- [ ] Prints: `History is disabled.`

---

## 13. Context Fingerprinting

Context is collected automatically during enhancement. To verify:

### 13.1 Git Context

From inside a git repository:

```bash
cd /path/to/a/git/repo
promptune enhance "fix the auth bug"
```

In the TUI, press `?` then `C` to toggle context display:

- [ ] Shows `branch=<current_branch>`
- [ ] Shows recent commit information
- [ ] Shows modified files (if any)

### 13.2 No Git Context

From a non-git directory:

```bash
cd /tmp
promptune enhance --no-tui "fix the auth bug"
```

- [ ] Does not crash
- [ ] Context is minimal or empty

### 13.3 Tech Stack Detection

From the promptune project root (which has `pyproject.toml`):

```bash
promptune enhance "fix the auth bug"
```

- [ ] Context shows Python-related stack detection

### 13.4 Context Disabled

Set all context options to false in config:

```
[context]
use_git = false
use_shell_history = false
use_stack_detection = false
```

```bash
promptune enhance --json "fix a bug"
```

- [ ] Enhancement still works (no crash)
- [ ] Context is null or empty in the result

---

## 14. Provider-Specific Formatting

### 14.1 Auto-Detection

With `format_style = "auto"` in config:

```bash
# Claude provider (should auto-detect XML)
promptune enhance --json -p claude --tier 2 "build an API"
```

- [ ] `format_style` is `"auto"` (the format is applied internally)

### 14.2 Forced XML

```bash
promptune enhance --no-tui --format xml --tier 0 "build an API"
```

- [ ] Output may reflect XML-style structuring if applied by Tier 0/AI

### 14.3 Forced Markdown

```bash
promptune enhance --no-tui --format markdown --tier 0 "build an API"
```

- [ ] Format style set in result metadata

### 14.4 Forced Plain

```bash
promptune enhance --no-tui --format plain --tier 0 "build an API"
```

- [ ] Format style set in result metadata

---

## 15. Semantic Deduplication

### 15.1 Basic Dedup (Cache Hit)

Ensure dedup is enabled and history is enabled:

```bash
# Verify config
promptune config show
# Should show: dedup_enabled = True, history.enabled = True
```

First, accept an enhancement to populate history:

```bash
promptune enhance "build a REST API with authentication"
# Press A to accept in the TUI
```

Now enhance an identical or near-identical prompt:

```bash
promptune enhance --json "build a REST API with authentication"
```

- [ ] `tier_used` is `-1` (cache hit)
- [ ] `enhanced` matches the previously accepted result
- [ ] `latency_ms` is very low (sub-100ms expected)

### 15.2 Near-Duplicate Detection

```bash
promptune enhance --json "build a REST API with user authentication"
```

- [ ] If similarity >= 0.85 threshold, `tier_used` is `-1`
- [ ] Returned enhancement is from the cached result

### 15.3 Rejected Prompts Excluded

Reject an enhancement:

```bash
promptune enhance "create a Python web scraper"
# Press R to reject in the TUI
```

Then enhance the same prompt again:

```bash
promptune enhance --json "create a Python web scraper"
```

- [ ] `tier_used` is NOT `-1` (rejected entries are excluded from dedup candidates)
- [ ] Enhancement runs fresh through the tier system

### 15.4 Edited Result Used as Cache

Edit an enhancement:

```bash
promptune enhance "write a function to sort a list"
# Press E, modify the text, confirm
```

Then enhance the same prompt:

```bash
promptune enhance --json "write a function to sort a list"
```

- [ ] `tier_used` is `-1` (cache hit)
- [ ] `enhanced` matches your EDITED version (not the original AI output)

### 15.5 Short Prompts Skip Dedup

```bash
promptune enhance --json "hi"
```

- [ ] Dedup is skipped for prompts with fewer than 3 words
- [ ] `tier_used` is 0 (or higher), not `-1`

### 15.6 Dedup Disabled

Set `dedup_enabled = false` in config:

```bash
promptune enhance --json "build a REST API with authentication"
```

- [ ] `tier_used` is NOT `-1` even if an identical prompt is in history

---

## 16. Preference Learning

### 16.1 Prerequisites

You need at least `preference_min_samples` (default 5) history entries where a specific rule was applied and you made accept/reject decisions.

### 16.2 Generate Training Data

Repeatedly enhance prompts that trigger the `role_assignment` rule, and consistently reject them:

```bash
# Run these 6 times, pressing R (reject) each time:
promptune enhance "sort an array"
promptune enhance "reverse a string"
promptune enhance "parse a CSV file"
promptune enhance "merge two lists"
promptune enhance "count word frequency"
promptune enhance "find duplicates"
```

- [ ] Each enhancement triggers `role_assignment` rule

### 16.3 Check Learned Preferences

```bash
promptune history --preferences
```

- [ ] Shows `role_assignment` with action `skip` and confidence > 0.6
- [ ] Sample count is >= 5

### 16.4 Preferences Applied

After learning:

```bash
promptune enhance --json "calculate a hash"
```

- [ ] `rules_applied` does NOT contain `"role_assignment"` (rule is now skipped)

### 16.5 Edit Patterns

If you consistently edit out role prefixes (starting with "You are a..."):

```bash
promptune history --preferences
```

- [ ] Shows an edit pattern: `User consistently removes role assignment`

### 16.6 Insufficient Samples

With fewer than `preference_min_samples` entries:

```bash
promptune history --preferences
```

- [ ] Prints: `No preferences learned yet.`

---

## 17. Team Templates

### 17.1 Create Template Directory

From the project root:

```bash
mkdir -p .prompts
```

### 17.2 Create a Template

```bash
cat > .prompts/debug-python.md << 'EOF'
---
intent: coding
domain: coding
---
## Debug Context
Stack: {{stack}}
Branch: {{branch}}

Focus on identifying the root cause before suggesting fixes.
Provide step-by-step debugging instructions.
EOF
```

### 17.3 Template Matching

```bash
promptune enhance --json "debug the authentication module crashing on login"
```

- [ ] Template is matched (intent=coding, domain=coding)
- [ ] Template body is injected into the system prompt (visible in Tier 1/2 enhancements)
- [ ] Variables like `{{branch}}` are replaced with actual values

### 17.4 No Template Match

```bash
cat > .prompts/writing-only.md << 'EOF'
---
intent: writing
---
Follow the team's style guide.
EOF
```

```bash
promptune enhance --json "implement a sorting algorithm"
```

- [ ] `writing-only.md` is NOT matched for a coding prompt
- [ ] Enhancement proceeds normally without template injection

### 17.5 Template Specificity Ranking

Create two competing templates:

```bash
cat > .prompts/broad-coding.md << 'EOF'
---
intent: coding
---
General coding template.
EOF

cat > .prompts/specific-coding-python.md << 'EOF'
---
intent: coding
domain: coding
---
Python-specific coding template.
EOF
```

```bash
promptune enhance --json "implement a REST API in Python"
```

- [ ] More specific template (intent+domain) is preferred over intent-only template

### 17.6 No .prompts Directory

Remove the directory:

```bash
rm -rf .prompts
```

```bash
promptune enhance --no-tui "build an app"
```

- [ ] Enhancement works normally with zero overhead

### 17.7 Template with Invalid Frontmatter

```bash
mkdir -p .prompts
cat > .prompts/bad-template.md << 'EOF'
No frontmatter here.
Just body text.
EOF
```

- [ ] Template is silently ignored (no crash)

### 17.8 Unknown Variables

```bash
cat > .prompts/with-unknown-var.md << 'EOF'
---
intent: coding
---
User: {{unknown_variable}}
Stack: {{stack}}
EOF
```

- [ ] `{{unknown_variable}}` is left as-is in the output
- [ ] `{{stack}}` is replaced with the detected stack

---

## 18. TUI (Accept/Edit/Reject)

### 18.1 TUI Launch

```bash
promptune enhance "make a todo app"
```

- [ ] TUI displays with two panels: "Original" and "Enhanced"
- [ ] Header shows tier, latency info (e.g., `[Tier 0 . rules . 8ms]`)
- [ ] Action bar visible: `[A] Accept   [E] Edit   [R] Reject   [?] More`

### 18.2 Accept

Press `A`:

- [ ] Enhanced prompt is printed to stdout
- [ ] TUI exits
- [ ] Exit code is 0
- [ ] Entry recorded in history with `decision=accept`

### 18.3 Reject

Press `R`:

- [ ] TUI exits
- [ ] Exit code is 1 (non-zero)
- [ ] Entry recorded in history with `decision=reject`

### 18.4 Edit

Press `E`:

- [ ] Multiline editor opens with enhanced prompt pre-filled
- [ ] You can modify the text
- [ ] Press Esc then Enter to finish editing
- [ ] Edited text is printed to stdout
- [ ] Entry recorded in history with `decision=edit` and the edit captured

### 18.5 More Options

Press `?`:

- [ ] Additional options revealed: `[Q] Quality   [D] Details   [C] Context`

### 18.6 Quality Toggle (Q)

Press `?` then `Q`:

- [ ] Quality score breakdown appears
- [ ] Shows before/after scores for each PQS dimension (Clarity, Specificity, Context, Structure, Actionability)
- [ ] Color-coded bars: red (0-39), yellow (40-69), green (70-100)
- [ ] Delta values shown (e.g., `+48`)

Press `Q` again:

- [ ] Quality section hides (toggle behavior)

### 18.7 Details Toggle (D)

Press `?` then `D`:

- [ ] Shows rules applied (e.g., `+output format, +constraints, -politeness`)

### 18.8 Context Toggle (C)

Press `?` then `C`:

- [ ] Shows context fingerprint (branch, stack, recent errors, etc.)

### 18.9 Responsive Layout

In a wide terminal (>= 100 columns):

- [ ] Panels display side by side

In a narrow terminal (< 100 columns):

- [ ] Panels stack vertically

### 18.10 Diff Highlighting

- [ ] Enhanced panel highlights added words in green
- [ ] Structural additions are underlined

---

## 19. Shell Widget

### 19.1 Zsh Widget Installation

```bash
eval "$(promptune shell-init)"
```

- [ ] No errors printed
- [ ] Widget is now active in the current shell session

### 19.2 Zsh Widget Usage

Type a prompt on the command line (do NOT press Enter):

```
make a todo app
```

Press Ctrl+E:

- [ ] The text on the command line is replaced with the enhanced prompt
- [ ] Cursor moves to end of new text
- [ ] Original text is preserved if enhancement fails

### 19.3 Zsh Widget with Empty Line

Press Ctrl+E with nothing typed:

- [ ] Nothing happens (empty input guard)

### 19.4 Bash Widget

```bash
bash
eval "$(promptune shell-init --shell bash)"
```

Type a prompt and press Ctrl+E:

- [ ] Enhancement works the same as in Zsh

### 19.5 Fish Widget

```bash
fish
promptune shell-init --shell fish | source
```

Type a prompt and press Ctrl+E:

- [ ] Enhancement works

### 19.6 Custom Keybinding

```bash
eval "$(promptune shell-init --key 'alt+e')"
```

- [ ] Alt+E now triggers enhancement (Ctrl+E may no longer work)

### 19.7 Chord Keybinding

```bash
eval "$(promptune shell-init --key 'ctrl+x ctrl+e')"
```

- [ ] Ctrl+X followed by Ctrl+E triggers enhancement

### 19.8 Permanent Installation

Add to `~/.zshrc`:

```bash
echo 'eval "$(promptune shell-init)"' >> ~/.zshrc
source ~/.zshrc
```

- [ ] Widget persists across new shell sessions

### 19.9 Warp Terminal Warning

```bash
TERM_PROGRAM=WarpTerminal promptune shell-init
```

- [ ] Output contains a warning comment about Warp Terminal at the top of the script
- [ ] Script still generates (but binding will not work in Warp)

---

## 20. Shell-Init Command

### 20.1 Auto-Detection

```bash
promptune shell-init
```

- [ ] Output matches your current `$SHELL` (zsh/bash/fish)

### 20.2 Force Zsh

```bash
promptune shell-init --shell zsh
```

- [ ] Output contains `zle`, `bindkey`, `$BUFFER`
- [ ] Key is `'^E'` by default

### 20.3 Force Bash

```bash
promptune shell-init --shell bash
```

- [ ] Output contains `bind -x`, `READLINE_LINE`, `READLINE_POINT`
- [ ] Key is `"\C-e"` by default

### 20.4 Force Fish

```bash
promptune shell-init --shell fish
```

- [ ] Output contains `commandline`, `bind`, `$status`
- [ ] Key is `\ce` by default

### 20.5 Custom Key Translation

```bash
promptune shell-init --shell zsh --key "ctrl+e"
```

- [ ] Key translated to `'^E'`

```bash
promptune shell-init --shell bash --key "alt+e"
```

- [ ] Key translated to `"\ee"`

```bash
promptune shell-init --shell fish --key "ctrl+x ctrl+e"
```

- [ ] Key translated to `\cx \ce`

### 20.6 Raw Shell-Native Key Passthrough

```bash
promptune shell-init --shell zsh --key "^X"
```

- [ ] Key passed through verbatim (no `+` detected, so no translation)

---

## 21. Config Edge Cases and Error Handling

### 21.1 Missing Config File

```bash
rm -f ~/.config/promptune/config.toml
promptune enhance --no-tui --tier 0 "hello"
```

- [ ] Uses default config values
- [ ] Does not crash

### 21.2 Invalid Provider in Config

Manually edit config to set `default = "invalid_provider"`:

```bash
promptune enhance --no-tui "hello"
```

- [ ] Error message about invalid provider
- [ ] Does not crash with a raw traceback

### 21.3 Invalid Style in Config

Manually edit config to set `default_mode = "nonexistent"`:

```bash
promptune enhance --no-tui --tier 0 "hello"
```

- [ ] Either uses default or shows clear error

### 21.4 Missing API Keys Section

Manually remove `[api_keys]` section from config:

```bash
promptune enhance --no-tui --tier 0 "hello"
```

- [ ] Tier 0 works fine (no API key needed)
- [ ] Tier 2 shows appropriate error

### 21.5 Corrupted TOML

Write invalid TOML to config:

```bash
echo "not valid toml [[[" > ~/.config/promptune/config.toml
promptune enhance --no-tui "hello"
```

- [ ] Error message about config parsing
- [ ] Does not crash with a raw traceback

### 21.6 Config Resolution Order

Test that CLI flags override config:

```bash
# Config says max_tier = 0
promptune config --set-tier 0
# CLI says tier 2
promptune enhance --json --tier 2 "hello"
```

- [ ] `tier_used` is 2 (CLI wins)

Test that env vars override config:

```bash
PROMPTUNE_PROVIDER=openai promptune enhance --json --tier 0 "hello"
```

- [ ] Provider behavior may reflect the env var override

---

## 22. Error Handling

### 22.1 No Internet (Cloud Provider)

Disconnect from internet or use a firewall:

```bash
promptune enhance --no-tui --tier 2 "hello"
```

- [ ] If forced tier 2: Error message about connection
- [ ] If not forced: Falls back to Tier 0

### 22.2 Ollama Not Running

Stop Ollama:

```bash
promptune enhance --no-tui --tier 1 "hello"
```

- [ ] Error or fallback to Tier 0 (depending on forced vs. auto routing)

### 22.3 Invalid API Key

Set a fake API key:

```bash
promptune config --set-key claude fake-key-12345
promptune enhance --no-tui --tier 2 "hello"
```

- [ ] API returns auth error
- [ ] Error message is user-friendly, not a raw traceback

### 22.4 Keyboard Interrupt During Enhancement

Start an enhancement and press Ctrl+C:

```bash
promptune enhance "hello"
# Press Ctrl+C
```

- [ ] Prints `Cancelled.` to stderr
- [ ] Exit code is 130
- [ ] No partial output or corrupted state

### 22.5 Very Long Prompt

```bash
python3 -c "print('word ' * 10000)" | promptune enhance --no-tui --tier 0
```

- [ ] Handles long prompt without crashing
- [ ] May take slightly longer for scoring

---

## 23. Installer Script

### 23.1 Basic Execution

```bash
bash install.sh
```

- [ ] Checks OS (macOS required)
- [ ] Checks not running as root
- [ ] Checks Python version (3.9+)
- [ ] Installs pipx if not present
- [ ] Installs promptune via pipx
- [ ] Verifies installation
- [ ] Prints next steps
- [ ] Runs Ollama status check

### 23.2 Root Detection

```bash
PROMPTUNE_FAKE_EUID=0 bash install.sh
```

- [ ] Error: `Do not run this installer as root.`
- [ ] Exits with code 1

### 23.3 Ollama Status in Installer

With Ollama installed and running:

- [ ] Shows: `OK: Ollama found at /path/to/ollama`
- [ ] Shows: `OK: Ollama server running`
- [ ] Shows: `OK: Model qwen2.5:3b available` (if pulled)

Without Ollama:

- [ ] Shows: `MISS: Ollama not found`
- [ ] Shows install instructions

With Ollama installed but server not running:

- [ ] Shows: `MISS: Ollama server not running`

With Ollama running but model not pulled:

- [ ] Shows: `MISS: Model qwen2.5:3b not available`

### 23.4 Non-macOS

The `install.sh` script is macOS-focused. For Linux, install via pip/pipx directly:

```bash
pip install -e ".[dev]"
# For Linux daemon support:
pip install -e ".[dev,linux-daemon]"
```

- [ ] Install completes without error
- [ ] `promptune version` works
- [ ] `promptune daemon status` works (shows "not running" on Linux)

---

## 24. Daemon — Lifecycle

### Prerequisites (macOS)

- [ ] macOS with Accessibility permission granted to your terminal app
- [ ] Promptune installed and configured (`promptune config show` works)

### Prerequisites (Linux)

- [ ] System dependencies installed (see Section 1 Linux prerequisites)
- [ ] `pip install promptune[linux-daemon]` completed
- [ ] Not running under WSL (WSL is unsupported)

### Start / Stop / Status

- [ ] `promptune daemon start --foreground` starts the daemon in the foreground
  - Expected: "Daemon running (PID XXXXX)" message, process stays alive
  - Press Ctrl+C to stop
- [ ] `promptune daemon start` starts the daemon in the background
  - Expected: "Daemon started (PID XXXXX)" message, returns to shell
- [ ] `promptune daemon status` shows running state
  - Expected: shows PID, uptime, enhancement count, socket status
  - macOS: also shows accessibility status
- [ ] `promptune daemon stop` stops a running daemon
  - Expected: "Daemon stopped" message
- [ ] `promptune daemon status` after stop shows not running
- [ ] `promptune daemon restart` stops and starts the daemon
- [ ] Starting when already running shows appropriate message

### Edge Cases

- [ ] `promptune daemon stop` when no daemon is running shows "not running" message
- [ ] `promptune daemon start` twice does not create duplicate processes
- [ ] On Linux under WSL: `promptune daemon start` shows "Unsupported platform: WSL" error

---

## 25. Daemon — Hotkey and Enhancement Pipeline

### Hotkey Registration (macOS)

- [ ] With daemon running in foreground, open a text editor (TextEdit, VS Code, etc.)
- [ ] Type a rough prompt, select it
- [ ] Press Ctrl+Shift+E
  - Expected: selected text is replaced with an enhanced version
- [ ] Press Cmd+Z to undo
  - Expected: original text is restored

### Hotkey Registration (Linux X11)

- [ ] With daemon running in foreground (`XDG_SESSION_TYPE=x11`), open a text editor
- [ ] Type a rough prompt, select it
- [ ] Press Ctrl+Shift+E
  - Expected: selected text is replaced with an enhanced version
- [ ] Press Ctrl+Z to undo
  - Expected: original text is restored

### Hotkey Registration (Linux Wayland)

- [ ] With daemon running in foreground (`XDG_SESSION_TYPE=wayland`), open a text editor
- [ ] Type a rough prompt, select it
- [ ] Press Ctrl+Shift+E
  - Expected: selected text is replaced with an enhanced version
  - Note: Portal GlobalShortcuts path requires a compatible compositor (GNOME 43+, KDE 5.27+)
  - If portal unavailable: daemon falls back to evdev (requires `input` group membership)
- [ ] Press Ctrl+Z to undo

### Enhancement Pipeline

- [ ] Select short text ("fix bugs") → hotkey → text is enhanced
- [ ] Select longer text (paragraph) → hotkey → text is enhanced
- [ ] Select text, switch to a different app before enhancement completes
  - Expected: notification says "copied to clipboard" instead of pasting
- [ ] Press hotkey with no text selected
  - Expected: notification says "No text selected"

### Clipboard Safety

- [ ] Copy something to clipboard, then use the hotkey on different text
  - Expected: after enhancement, original clipboard content is NOT lost (daemon saves/restores)

---

## 26. Daemon — Notifications and IPC

### Notifications (macOS)

- [ ] After successful enhancement, macOS notification appears
  - Expected: shows score improvement (e.g., "40 → 65")
- [ ] After error (no text selected), error notification appears
- [ ] With `notify = false` in config, no notifications appear
- [ ] With `notify_sound = false`, notifications appear but silent

### Notifications (Linux)

- [ ] With `notify-send` installed: desktop notification appears after successful enhancement
- [ ] Without `notify-send`: enhancement still completes silently (no crash)
- [ ] With `notify = false` in config, no notifications appear

### IPC (CWD Tracking)

- [ ] With daemon running, use the shell widget (Ctrl+E in terminal)
- [ ] Check daemon status — should show the shell's CWD as last reported directory
- [ ] The shell widget still works normally (enhances the command line)

### Ollama Prewarm

- [ ] With Ollama running and `ollama_prewarm = true`:
  - Start daemon → check Ollama logs → model should receive keep-alive pings
- [ ] With `ollama_prewarm = false`: no prewarm pings sent

---

## 27. Daemon — LaunchAgent and Diagnostics

### LaunchAgent (macOS)

- [ ] `promptune daemon install-login-item` creates plist file
  - Expected: `~/Library/LaunchAgents/dev.promptune.daemon.plist` exists
  - Expected: file contains valid XML plist with correct paths
- [ ] `promptune daemon uninstall-login-item` removes plist file
  - Expected: plist file is removed
- [ ] After install, log out and back in → daemon should auto-start
- [ ] `promptune daemon install` — same as install-login-item, cross-platform alias
- [ ] `promptune daemon uninstall` — same as uninstall-login-item, cross-platform alias

### Service Management (Linux)

- [ ] `promptune daemon install` creates systemd user service
  - Expected: `~/.config/systemd/user/promptune.service` exists
  - Expected: file contains `ExecStart=... -m promptune daemon start --foreground`
  - Expected: `systemctl --user status promptune` shows "enabled"
- [ ] `promptune daemon uninstall` disables and removes service
  - Expected: service file removed, systemctl reports "not found"
- [ ] `promptune daemon purge` removes all daemon files
  - Expected: service, socket, PID file, undo buffer, and log all removed
  - Expected: `~/.local/share/promptune/` is empty (or does not exist)

### Diagnostics

- [ ] `promptune daemon diagnose` runs all platform-specific checks
  - macOS: reports on accessibility, secure input, daemon running state, socket, config
  - Linux: reports on session type, tool availability (xclip/xdotool or wl-paste/ydotool)
- [ ] `promptune daemon setup` walks through setup for current platform
  - macOS: guides accessibility permission grant
  - Linux: checks tool availability, shows install command for missing packages

### Config

- [ ] Change `hotkey` in config to a different combo (e.g., `ctrl+shift+p`)
  - Restart daemon → new hotkey should work, old one should not
- [ ] Change `clipboard_settle_ms` to a higher value → enhancement still works (just slower)

---

## 28. Linux Daemon (Phase 3)

### 28.1 Platform Detection

```bash
promptune daemon status
```

- [ ] On macOS: no platform error; shows macOS daemon state
- [ ] On Linux X11 (`XDG_SESSION_TYPE=x11`): no platform error; uses X11 backend
- [ ] On Linux Wayland (`XDG_SESSION_TYPE=wayland`): no platform error; uses Wayland backend
- [ ] On WSL: shows `Unsupported platform: WSL` error, exits cleanly

Test session type detection directly:

```bash
# Override session type
XDG_SESSION_TYPE=x11 promptune daemon start --foreground
XDG_SESSION_TYPE=wayland promptune daemon start --foreground
```

- [ ] X11 session: logs show X11 backend loaded
- [ ] Wayland session: logs show Wayland backend loaded

### 28.2 Linux X11 Backend

*Requires: Linux X11 desktop, xclip, xdotool, python-xlib*

```bash
pip install promptune[linux-daemon]
XDG_SESSION_TYPE=x11 promptune daemon start --foreground
```

- [ ] Daemon starts without errors
- [ ] Hotkey `Ctrl+Shift+E` is registered (log shows "Daemon started")
- [ ] Open a text editor, type "make a todo app", select it, press Ctrl+Shift+E
  - Expected: text replaced with enhanced version
- [ ] Open terminal, check `promptune daemon status` → shows running

Active window detection:

```bash
XDG_SESSION_TYPE=x11 promptune daemon start --foreground
```

- [ ] Switch focus to a different app during enhancement
  - Expected: result placed on clipboard with "paste manually" notification

### 28.3 Linux Wayland Backend

*Requires: Linux Wayland desktop, wl-clipboard, ydotool*

```bash
pip install promptune[linux-daemon]
XDG_SESSION_TYPE=wayland promptune daemon start --foreground
```

**Portal GlobalShortcuts path (GNOME 43+, KDE 5.27+):**

- [ ] Daemon starts and registers shortcut via XDG Desktop Portal
- [ ] Hotkey fires when Ctrl+Shift+E is pressed
- [ ] Enhancement completes and text is pasted back

**evdev fallback (when portal unavailable):**

- [ ] Daemon logs "Portal GlobalShortcuts unavailable, falling back to evdev"
- [ ] User is in `input` group (`groups | grep input`)
- [ ] Hotkey still fires via evdev listener

**Active window detection:**

- [ ] GNOME: `gdbus call` correctly identifies focused window
- [ ] KDE: `qdbus` correctly identifies focused window
- [ ] sway: `swaymsg -t get_tree` correctly identifies focused node
- [ ] Unknown DE: returns empty string without crash

### 28.4 Linux Dependency Checker

```bash
promptune daemon setup
```

With all X11 tools installed:

- [ ] Shows `xclip ✓`, `xdotool ✓`, `notify-send ✓` (or `✗` if not installed)
- [ ] No install command shown when all required tools present

With missing tools (e.g., uninstall xclip):

- [ ] Shows `xclip ✗` with install command
- [ ] Install command matches your package manager (apt/dnf/pacman/zypper)
- [ ] Optional tools (`notify-send`) missing shows warning but no error

```bash
promptune daemon diagnose
```

- [ ] Shows session type (x11 or wayland)
- [ ] Shows which required tools are available
- [ ] Shows daemon running state

### 28.5 Linux systemd Service

*Requires: systemd user session (`systemctl --user status`)*

```bash
promptune daemon install
```

- [ ] `~/.config/systemd/user/promptune.service` created
- [ ] Service file contains correct `ExecStart` with full Python path
- [ ] `systemctl --user status promptune` shows "enabled"

```bash
systemctl --user start promptune
systemctl --user status promptune
```

- [ ] Daemon starts via systemd
- [ ] Hotkey works as expected (same as manual start)

```bash
promptune daemon uninstall
```

- [ ] Service disabled and file removed
- [ ] `systemctl --user status promptune` shows "not found" or "inactive"

```bash
promptune daemon purge
```

- [ ] All files removed: `~/.local/share/promptune/promptune.sock`, `daemon.pid`, `undo.txt`, `daemon.log`
- [ ] Service also removed if installed

### 28.6 Linux: install-login-item commands blocked

```bash
promptune daemon install-login-item
promptune daemon uninstall-login-item
```

On Linux:

- [ ] Both commands print a clear error: `macOS-only. Use 'daemon install' instead.`
- [ ] Exit code is 1

---

## 29. Regression Checklist

Quick sanity checks to run after fixing any bug. Each should pass in under 60 seconds total.

- [ ] `promptune version` prints version without error
- [ ] `promptune --help` lists all commands
- [ ] `promptune config show` prints config without error
- [ ] `promptune config path` prints a path
- [ ] `promptune doctor` runs all checks without crashing
- [ ] `promptune enhance --no-tui --tier 0 "make a todo app"` produces output
- [ ] `promptune enhance --json --tier 0 "hello"` produces valid JSON
- [ ] `echo "test" | promptune enhance --no-tui --tier 0` reads from pipe
- [ ] `promptune enhance --no-tui --tier 0 ""` shows error for empty prompt
- [ ] `promptune shell-init --shell zsh` outputs zsh widget script
- [ ] `promptune shell-init --shell bash` outputs bash widget script
- [ ] `promptune shell-init --shell fish` outputs fish widget script
- [ ] `promptune history` does not crash (shows entries or "No history yet.")
- [ ] `promptune history --stats` does not crash
- [ ] `promptune local-llm-status` does not crash
- [ ] `promptune daemon status` does not crash (shows status or "not running")
- [ ] `promptune daemon diagnose` does not crash
- [ ] `promptune daemon install` — installs service (systemd on Linux, LaunchAgent on macOS)
- [ ] `promptune daemon uninstall` — uninstalls service without error
- [ ] `promptune daemon purge` — removes all daemon files without error
- [ ] On Linux: `promptune daemon install-login-item` shows macOS-only error
---

## 23. Score Command

**Purpose:** Verify `promptune score` displays quality scores correctly.

### Test Steps

1. Run `promptune score "make a todo app"` — expect PQS total (0-100), intent, and 7 per-dimension breakdowns
2. Run `promptune score --json "build a REST API with auth"` — expect valid JSON with `total`, `intent`, `dimensions` keys
3. Run `promptune score` with no argument — expect exit code 1 with "Error: Empty prompt."
4. Run `echo "fix the login bug" | promptune score` — expect score output from piped input

### Pass Criteria

- [ ] Text output shows PQS total and all 7 dimensions
- [ ] JSON output is parseable and contains required keys
- [ ] Empty prompt produces error exit
- [ ] Piped input works

---

## 24. Auto-Enhance Gate

**Purpose:** Verify the auto-enhance hook intercepts low-quality prompts and copies the enhanced version to clipboard.

### Prerequisites

- `[auto_enhance]` section in config with `enabled = true`, `threshold = 40`
- Claude Code installed (or another supported AI tool)

### Test Steps

1. Run `echo '{"prompt": "fix bug"}' | promptune gate` — expect exit 0 (below min_words, passes through)
2. Run `echo '{"prompt": "make a simple todo app thing"}' | promptune gate` — expect exit 1 if PQS < 40 (enhanced, copied to clipboard)
3. Run `echo '{"prompt": "Build a full-stack REST API with JWT authentication, PostgreSQL database, rate limiting, and comprehensive error handling"}' | promptune gate` — expect exit 0 (high-quality prompt passes through)
4. Run `echo 'invalid json' | promptune gate` — expect exit 0 (graceful degradation)
5. Run `promptune doctor` — expect "Auto-enhance" line showing Claude Code hook status

### Edge Cases to Verify Manually

- Prompt exactly at threshold (PQS = 40) should pass through
- Config with `enabled = false` should always pass through
- Missing clipboard tool (e.g. on headless server) should warn but not crash

### Pass Criteria

- [ ] Short prompts pass through (exit 0)
- [ ] Low-quality prompts are blocked (exit 1) and enhanced version is on clipboard
- [ ] High-quality prompts pass through (exit 0)
- [ ] Invalid input is handled gracefully (exit 0)
- [ ] Doctor shows hook status

---

## 25. MCP Server

**Purpose:** Verify the MCP server starts and exposes tools correctly.

### Prerequisites

- `pip install promptune[mcp]` (installs `mcp>=1.0`)

### Test Steps

1. Run `promptune mcp` — expect server to start on stdio (will wait for input; Ctrl+C to stop)
2. Without mcp installed: `promptune mcp` — expect error message "MCP support requires: pip install promptune[mcp]" and exit 1
3. Add to Claude Code MCP config and verify both tools appear: `enhance_prompt`, `score_prompt_quality`

### Pass Criteria

- [ ] Server starts without error when mcp is installed
- [ ] Clear error message when mcp is not installed
- [ ] Tools are usable from Claude Code or another MCP client

---

- [ ] `ruff check .` passes
- [ ] `mypy promptune/` passes
- [ ] `pytest --cov=promptune --cov-report=term-missing -v` passes with >= 85% coverage (Linux system call code excluded from macOS runs)
