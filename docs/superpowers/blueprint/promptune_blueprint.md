# promptune — Complete Product Blueprint
### Version 2.0 | Planning Document for Claude Code

---

## How to Use This Document

This is the single source of truth for promptune's product strategy, technical architecture,
and build plan. It is designed to be shared with Claude Code CLI for deep planning sessions.
Every section is written to be unambiguous — no hand-waving, no "we'll figure it out later."

When using this with Claude Code, reference specific sections by name.
Example: "Let's plan the implementation for the Context Fingerprinting system."

---

## Product in One Sentence

promptune is a **prompt quality layer** that sits underneath every AI tool a developer uses —
enhancing rough prompts into structured, context-rich, provider-optimised prompts before they
ever reach any AI, triggered by a single keystroke, with zero workflow interruption.

---

## Core Philosophy

- **Do one thing exceptionally well.** Enhance prompts. That is it.
- **Zero friction.** One keystroke. No app switching. No copy-paste.
- **Lowest possible cost.** Free by default via rule engine + local model. Cloud API only as escalation.
- **Privacy first.** All data stays local. No telemetry. No cloud sync. SQLite on device.
- **Unix composable.** Works with every other tool. Replaces nothing.
- **Keyboard-only.** No GUI. No web UI. Everything via terminal or OS-level hotkey.

---

## Why Use This Instead of Asking the AI to "Improve My Prompt"?

This question must be answered convincingly before anyone will use the tool.
Here are five concrete, research-backed reasons.

### Reason 1: Context switching destroys flow

A UC Irvine study found developers using browser-based AI tools took 19% longer on tasks even
while believing AI helped them. Gloria Mark's research shows it takes 23 minutes to regain deep
focus after a context switch. The manual "improve my prompt" workflow requires: stop work, open
new tab, describe the prompt, wait, copy, switch back, paste, resume. That is a full
context-switch round trip, repeated dozens of times per day.

promptune eliminates the round trip entirely. The keystroke is Ctrl+E in the terminal (Phase 1)
and Ctrl+Shift+E system-wide (Phase 2). Total interruption: under 2 seconds. The user never
leaves their terminal or IDE.

### Reason 2: The AI improving your prompt knows nothing about your situation

When you ask Claude or ChatGPT to "improve this prompt," it works in a vacuum. It does not know:
- Your current git branch (fix/auth-redirect)
- Your last test failure (TypeError: Cannot read properties of undefined)
- Your tech stack (TypeScript, Next.js App Router, Prisma, pnpm)
- Your team's coding conventions
- What you already tried this session

promptune reads your git state, recent shell commands, project config files, and failure output
automatically. The enhanced prompt includes context the AI could never have if you had asked it
manually.

Without promptune (AI sees):
  "fix the auth redirect bug"

With promptune (AI sees):
  "I'm debugging an authentication redirect issue in a Next.js 14 TypeScript project (pnpm).
   Branch: fix/auth-redirect. Last test failure: TypeError: Cannot read properties of undefined
   (reading 'token') in src/auth/redirect.ts. Recently changed: src/auth/redirect.ts,
   src/middleware/session.ts. The session token appears undefined during post-login redirect.
   Diagnose the root cause and provide a fix using safe optional chaining. Show corrected code
   with a brief explanation of what changed."

Nine words in. Eighty words of precise, actionable context out.

### Reason 3: Provider-specific formatting is too complex to memorise

Each major AI responds measurably better to different structural conventions:

| Provider    | Optimal format                          | Evidence                               |
|-------------|----------------------------------------|----------------------------------------|
| Claude      | XML tags + explicit role assignment    | Anthropic-documented 15% quality gain |
| GPT-4/4.1   | Markdown # headers + numbered lists    | OpenAI GPT-4.1 official prompting guide|
| Gemini      | Instructions placed after data         | Google prompting best practices        |

No developer applies these conventions consistently across every prompt, every session.
promptune applies them automatically based on the configured target provider.

### Reason 4: Structure matters more than word choice

The Prompt Report (meta-analysis of 1,500 papers by researchers from OpenAI, Google, Stanford)
found format and structure matter more than specific word choice. In one documented case, a human
spent 20 hours refining a prompt; an automated system produced a better result in 10 minutes.
promptune applies the same structural principles in under 2 seconds, on every prompt, with no
effort.

### Reason 5: Learning is lost between sessions

Manually improved prompts disappear when the session ends. Next session starts from zero.
promptune stores every enhancement and accept/reject decision in local SQLite, learning personal
style and project conventions over time, biasing future enhancements toward what actually gets
accepted.

---

## Target Users

**Primary (Phase 1 + 2):** CLI-native developers on macOS who use AI tools daily — Aider,
Claude Code, ShellGPT, terminal-based LLM workflows. These users live in the terminal, are
comfortable with shell configuration, and want a tool that feels like a Unix utility: small,
fast, composable.

**Secondary (Phase 2 — OS-level):** macOS developers who also use AI tools in desktop IDEs
(VS Code, Cursor, JetBrains, Zed) or in browsers (Claude.ai, ChatGPT, Replit, Lovable). These
users benefit from the OS-level hotkey that works without any IDE plugin or browser extension.

**Phase 3 (completed):** Linux developers using the same workflows — X11 and Wayland daemon support now implemented.

---

## Honest Context Availability Matrix

Context quality differs depending on where the user invokes promptune. Do not over-promise.

| Context Signal              | Terminal/CLI          | OS Hotkey: Desktop IDE      | OS Hotkey: Browser          |
|-----------------------------|----------------------|-----------------------------|-----------------------------|
| Prompt structure enhancement| Always               | Always                      | Always                      |
| Provider-specific formatting| Config-driven        | Config-driven               | Config-driven               |
| Shell history (last error)  | Full (reads file)    | Full (reads file)           | Full (reads file)           |
| Current git branch          | Full (cwd known)     | Last known repo via daemon  | Last known repo (may stale) |
| Git changed files           | Full (git status)    | If daemon tracks active dir | Not available               |
| Tech stack detection        | Full                 | From last known project     | Not available               |
| Team .prompts/ templates    | Full                 | From last known project     | Not available               |
| Contents of AI chat window  | Never                | Never                       | Never                       |
| Which AI platform is active | Never                | Never                       | Never                       |

Key insight: The tool is valuable at every context level. Even with zero project context (browser
use), Tier 0 + Tier 1 enhancement of "explain kubernetes pods" into a well-structured 80-word
prompt is genuinely useful. Context fingerprinting is a power feature for the terminal — in the
browser it degrades gracefully to still being significantly better than raw prompts.

---

## Three-Tier Enhancement Architecture

Never call an expensive API for every prompt. Route each prompt to the cheapest tier that
produces sufficient quality.

```
User prompt arrives
        |
        v
+-----------------------------+
|   Quality Scorer (<1ms)     |  Heuristic scoring: word count, structure
|   Score 0-100               |  detection, vague-word flags, format check
+-------------+---------------+
              |
    +---------+---------+
    |         |         |
  70-100    40-69     0-39
    |         |         |
    v         v         v
 Tier 0    Tier 1    Tier 2
 Rules     Ollama    Cloud API
 FREE      FREE      ~$0.002
 <10ms     1-3s      2-5s
```

---

### Tier 0 — Rule-based linting and auto-fix (FREE, <10ms)

No AI. No network. No cost. Deterministic rules applied under 10ms.

Based on the 26 empirically validated prompting principles (Bsharat et al. 2023, 57.7% quality
improvement validated), Tier 0 applies these rules automatically:

| Rule                        | Detection                                      | Action                                        |
|-----------------------------|------------------------------------------------|-----------------------------------------------|
| No output format            | Format keywords missing                        | Append format instruction (domain-based)      |
| Vague task verbs            | Wordlist: fix, thing, stuff, make it work      | Flag with suggested specificity               |
| Prompt too short (<15 words)| Word count                                     | Flag: "Adding context will improve results"   |
| No constraints              | Missing length/scope/audience markers          | Append constraints (domain-detected)          |
| Contradictory instructions  | "brief" + "detailed" coexist                  | Flag conflict                                 |
| No role assignment          | Absence of "you are", "act as", "as a"         | Prepend role (domain-detected)                |
| Missing code delimiters     | Code-like content without backticks            | Wrap in appropriate code block                |
| Duplicate instructions      | Semantic overlap                               | Flag redundancy                               |
| No audience specification   | No expertise-level indicators                  | Append "for an experienced developer"         |

Before/After — Tier 0:
```
Before: "fix the bug in my code"

After:  "fix the bug in my code. Show the corrected code with a brief
         explanation of what changed and why. Use TypeScript."
```

Tier 0 handles roughly 40% of common developer prompts. Always runs first — its output feeds
into Tier 1/2 if escalation is needed.

---

### Tier 1 — Local model via Ollama (FREE, 1-3 seconds)

Genuine rewriting. No API key. No internet. No cost. Runs entirely on device.

Recommended model: qwen2.5:3b
- 3B parameters, Apache 2.0 licence
- 262K context window
- Best instruction-following in the <4B class

Performance on real hardware:
| Hardware                    | Tokens/second | Typical enhancement time |
|-----------------------------|---------------|--------------------------|
| M1/M2/M3 MacBook Pro        | 35-45 tok/s   | ~2 seconds               |
| M4 MacBook Pro              | 55-70 tok/s   | ~1 second                |
| Intel Core i7 (older Mac)   | 12-18 tok/s   | ~5 seconds               |
| Linux: RTX 4070             | 80-100 tok/s  | ~1 second                |

Cold start issue: First enhancement after daemon launch takes 3-8 seconds (model loads into
memory). The daemon pre-loads the model on startup to eliminate cold start from the user's
perspective.

Before/After — Tier 1:
```
Before: "explain kubernetes pods"

After:  "Explain Kubernetes pods to a developer experienced with Docker
         but new to Kubernetes. Cover: (1) what a pod is and its
         relationship to containers, (2) pod lifecycle states (Pending,
         Running, Succeeded, Failed, CrashLoopBackOff), (3) when to use
         single-container vs multi-container pods, (4) a minimal working
         pod YAML example. Keep the explanation under 400 words. Use
         Docker analogies where helpful."
```

---

### Tier 2 — Cloud API (~$0.002, best quality)

Best quality. For complex prompts needing domain expertise or sophisticated restructuring.
Uses the user's own API key — no promptune account or subscription ever needed.

Cost per enhancement (300 tokens in / 300 tokens out):
| Model                  | Per enhancement | Per 1,000  | Quality   |
|------------------------|-----------------|------------|-----------|
| Gemini 2.0 Flash Lite  | $0.00011        | $0.11      | Good      |
| GPT-4o-mini            | $0.00023        | $0.23      | Good      |
| Claude Haiku 4.5       | $0.00180        | $1.80      | Excellent |

Realistic monthly cost for a power user (1,000 enhancements/month with smart routing):
- 400 x Tier 0:  $0.00
- 350 x Tier 1:  $0.00
- 250 x Tier 2 (Claude Haiku 4.5):  ~$0.45
- Total: under $0.50/month

User config options:
- max_tier: 0  → rule-only, always free, instant
- max_tier: 1  → rule + local model, always free, requires Ollama
- max_tier: 2  → full enhancement, requires API key (default if key configured)

Before/After — Tier 2 (formatted for Claude, XML structure):
```
Before: "write tests for my function"

After:
<instructions>
You are an expert TypeScript engineer.
Write comprehensive unit tests for the function provided below.
</instructions>
<requirements>
  - Happy path: expected inputs produce correct outputs
  - Edge cases: empty inputs, null/undefined, boundary values
  - Error cases: invalid inputs trigger correct exceptions
  - Use Jest with descriptive names: test_<fn>_<scenario>_<expected>
  - One-line comment per test explaining what it validates
</requirements>
<function>
[paste function here]
</function>
```

---

## PEEM Framework Alignment

All enhancements are scored using the PEEM (Prompt Engineering Evaluation Metrics) framework
(arXiv:2603.10477). Validated across 7 benchmarks with Spearman rho ~0.97 correlation to
human judgment. A PEEM-guided rewriting loop improved downstream AI accuracy by up to 11.7
percentage points.

### The 9 PEEM Dimensions

Prompt-level (scored before response — actionable at enhancement time):

| Dimension           | What it measures                                      | Automatable at    |
|---------------------|-------------------------------------------------------|-------------------|
| Clarity & Structure | Unambiguous task? Logical sections? Clear delimiters? | Tier 0 + Tier 1/2 |
| Linguistic Quality  | Grammar correct? Readable? Appropriate register?      | Tier 0 + Tier 1/2 |
| Fairness            | Free of leading language, stereotypes, bias?          | Tier 1/2 only     |

Response-level (scored after AI responds — used for analytics and learning loop):
Accuracy, Coherence, Relevance, Objectivity, Clarity, Conciseness

### PEEM Score Display in TUI

```
promptune — enhancement complete  [Tier 1 · qwen2.5:3b · 1.8s]

  Clarity / Structure   ####......  3 --> ########..  8  (+5)
  Linguistic Quality    ######....  6 --> #########.  9  (+3)
  Specificity           ##........  2 --> #########.  9  (+7)
  Context Provided      #.........  1 --> #######...  7  (+6)
  ----------------------------------------------------------
  Overall               3.0 --> 8.3              Target: Claude

  [A] Accept   [E] Edit   [R] Reject   [?] Switch provider
```

The scores make prompt quality visible and create a learning feedback loop. Over time users
begin writing better initial prompts because they can see what was missing.

---

## Platform Strategy

### Decision: Mac first, then Linux. No Windows. No browser extension (current decision).

Phase 1 + 2: macOS only. Full support — CLI shell widget + OS-level global hotkey daemon.
Phase 3: Linux. Full support — CLI shell widget + OS-level global hotkey daemon (X11 + Wayland). COMPLETED.
Windows: Not in scope. No timeline.

### Why no browser extension (current decision)

The OS-level hotkey approach (Phase 2/4) makes a browser extension redundant. Ctrl+Shift+E
works in Chrome, Safari, Firefox, Arc — any browser — without any extension. The clipboard
pipeline handles text selection and replacement universally. A browser extension would add
maintenance burden (Manifest V3 compliance, per-site DOM injection, React synthetic event quirks)
for marginal UX improvement. Decision: no browser extension unless compelling user feedback
demands it after Phase 2 ships.

### Why no web UI

promptune is a keyboard-driven tool for CLI developers. A web UI contradicts the product
philosophy and adds maintenance burden. Config is via TOML. History and analytics are CLI
commands. Everything is accessible via keyboard.

---

## OS-Level Hotkey Architecture

### The Core Insight

Tools like Espanso (Rust, 25K+ GitHub stars), 1Password, and Alfred work in every application
on macOS without per-app integration. They use OS-native input APIs at the system level —
completely below the IDE and browser layer. promptune uses the same mechanism.

### The Clipboard Pipeline (macOS — Phase 2)

```
User types a prompt in ANY focused application
(VS Code / Claude.ai / JetBrains / Cursor / Replit / anything)
        |
        v
User selects the text (Cmd+A or mouse selection)
        |
        v
User presses Ctrl+Shift+E  <-- global hotkey registered by daemon
        |
        v
Daemon reads selected text
(simulates Cmd+C via CGEventCreate to copy selection to clipboard)
        |
        v
Daemon reads clipboard content via pbpaste
        |
        v
Enhancement engine runs (Tier 0 -> 1 -> 2)
        |
        v
Enhanced text written to clipboard via pbcopy
        |
        v
Daemon simulates Cmd+V via CGEventCreate to paste into active window
        |
        v
Enhanced prompt now in place, exactly where the cursor was
```

### macOS Technical Implementation

```python
from pynput import keyboard
import subprocess
import time

def read_selected_text() -> str:
    # Simulate Cmd+C to copy current selection
    with keyboard.Controller() as k:
        k.press(keyboard.Key.cmd)
        k.press('c')
        k.release('c')
        k.release(keyboard.Key.cmd)
    time.sleep(0.05)  # allow clipboard to update
    return subprocess.run(
        ['pbpaste'], capture_output=True, text=True
    ).stdout

def paste_enhanced_text(text: str) -> None:
    subprocess.run(['pbcopy'], input=text, text=True)
    time.sleep(0.05)
    with keyboard.Controller() as k:
        k.press(keyboard.Key.cmd)
        k.press('v')
        k.release('v')
        k.release(keyboard.Key.cmd)

# Register system-wide hotkey
hotkey_listener = keyboard.GlobalHotKeys({
    '<ctrl>+<shift>+e': on_enhance_hotkey
})
hotkey_listener.start()
```

One-time macOS permission: macOS requires Accessibility access for global hotkey registration
and input simulation. This is a one-time System Settings grant — identical to how 1Password,
Espanso, Alfred, and Raycast work. The installer guides the user through this step with
step-by-step instructions.

### Application Compatibility on macOS

| App category                                     | Works | Notes                                         |
|--------------------------------------------------|-------|-----------------------------------------------|
| Terminal emulators (iTerm2, Warp, kitty, Terminal)| Yes  | Shell widget (Ctrl+E) preferred — more native |
| VS Code / Cursor / Windsurf / Zed                | Yes   | Full clipboard pipeline                       |
| JetBrains (IntelliJ, PyCharm, WebStorm, GoLand)  | Yes   | Full clipboard pipeline                       |
| Chrome / Safari / Firefox / Arc                  | Yes   | Works on Claude.ai, ChatGPT, Replit, Lovable  |
| Electron apps (Slack, Notion, Linear, Discord)   | Yes   | Full clipboard pipeline                       |
| Native macOS apps                                | Yes   | Full clipboard pipeline                       |
| Password fields                                  | No    | Blocked by macOS Secure Input (correct behaviour)|
| Remote desktop / VMs                             | Maybe | Depends on clipboard sharing config           |

### Daemon Non-Terminal TUI Challenge

When invoked from a non-terminal app (VS Code, browser), there is no terminal to display the
Rich TUI with Accept/Edit/Reject. Options evaluated:

1. Silent mode (Phase 2 default): Enhance and replace immediately, no diff shown. User can
   undo with Cmd+Z if unhappy. Simple. Low friction. Ships first.

2. Notification mode: macOS notification shows "Prompt enhanced (+5.3 PEEM). Cmd+Z to undo."
   No approval step needed.

3. Terminal popup (future enhancement): Open a floating terminal window showing the diff.
   Complex to implement correctly. Post-Phase 2.

Decision: Start with silent mode + undo support in Phase 2. Terminal popup is a later
enhancement if users request an approval step outside the terminal.

### Linux Implementation (Phase 3 — COMPLETED)

Linux detects the display server at runtime and uses the appropriate tools via the platform abstraction layer.

X11:
- Read clipboard: xclip -selection clipboard -out
- Write clipboard: xclip -selection clipboard -in
- Simulate Ctrl+C: xdotool key ctrl+c
- Simulate Ctrl+V: xdotool key ctrl+v
- Global hotkey: pynput GlobalHotKeys (uses XRecord)

Wayland:
- Read clipboard: wl-paste
- Write clipboard: wl-copy
- Simulate keys: ydotool key (requires udev rules)
- Global hotkey: swhkd or keyd (compositor-dependent)
- Detection: check $WAYLAND_DISPLAY environment variable

Wayland limitation: Wayland's security model restricts global hotkeys by design. Some
compositors (GNOME, KDE Plasma) support it; others (pure wlroots compositors) may not.
Document this clearly. Fall back to requiring the user to bind the hotkey manually in their
compositor config if automatic registration fails. Always provide clear instructions for
the fallback.

---

## Context Fingerprinting (Terminal Mode)

When invoked from the terminal, the daemon assembles a compact context block automatically.
Hard-capped at 50 tokens to minimise API cost while maximising signal quality.

### What Gets Assembled

```python
def build_context_fingerprint(cwd: str) -> dict:
    return {
        "git_branch":       get_git_branch(cwd),          # "fix/auth-redirect"
        "git_changed_files": get_changed_files(cwd),       # ["src/auth/redirect.ts"]
        "last_shell_error": get_last_shell_error(),        # "TypeError: Cannot read..."
        "tech_stack":       detect_stack(cwd),             # "typescript, nextjs, prisma"
        "pkg_manager":      detect_pkg_manager(cwd),       # "pnpm"
        "os":               "macOS Sequoia",
    }
```

### Stack Detection Rules

| File present                          | Detected stack              |
|---------------------------------------|-----------------------------|
| package.json with "next"              | Next.js (version from file) |
| package.json with "react"             | React                       |
| tsconfig.json                         | TypeScript                  |
| Cargo.toml                            | Rust                        |
| pyproject.toml or setup.py            | Python                      |
| go.mod                                | Go                          |
| pnpm-lock.yaml                        | pnpm (not npm/yarn)         |
| docker-compose.yml                    | Docker Compose              |
| .terraform/                           | Terraform                   |
| pnpm-workspace.yaml or lerna.json     | Monorepo                    |

### Shell History Parsing

Reads last 20 entries from ~/.zsh_history or ~/.bash_history or fish history.
Identifies the most recent failed command:
- zsh extended history format: ": <timestamp>:<exit_code>;<command>"
- bash: exit codes not stored natively — use heuristic pattern matching

Handles gracefully:
- History file does not exist → skip, continue without
- History file not readable → skip, continue without
- No failed commands in last 20 entries → include last command only, no error context
- History file >10MB → read only last 500 lines

### Context Token Budget

```
git_branch:          ~5 tokens   ("fix/auth-redirect")
changed_files:       ~10 tokens  (up to 3 file paths)
last_error:          ~20 tokens  (first line of error message only)
tech_stack:          ~8 tokens   ("typescript nextjs prisma pnpm")
os:                  ~4 tokens   ("macOS Sequoia")
------------------------------------------------------------
Total fingerprint:   <= 50 tokens  (hard cap, trim in priority order)
```

Full diffs are never included. Full stack traces are truncated to the first meaningful line.
File contents are never included. Full file paths are shortened to basename + parent dir.

Priority order when trimming: git_branch > last_error > tech_stack > changed_files > os

---

## Six Novel Features

### Feature 1: Context Fingerprinting
Covered in detail in the section above.

### Feature 2: Provider-Specific Optimisation

The same prompt intent produces structurally different enhanced prompts depending on the
configured target provider.

User types: "write tests for my authentication middleware"

Enhanced for Claude (XML structure):
```xml
<instructions>
You are an expert Node.js/TypeScript backend engineer.
Write comprehensive unit tests for the authentication middleware below.
</instructions>
<requirements>
  - Happy path: valid JWT -> next() called, user attached to req
  - Invalid token -> 401 returned, next() not called
  - Expired token -> 401 with specific expiry error message
  - Missing Authorization header -> 401 returned
  - Use Jest + supertest. Names: test_<scenario>_<expected>
</requirements>
<context>Express 4.x, TypeScript strict, JWT via jsonwebtoken</context>
```

Enhanced for GPT-4 (Markdown structure):
```markdown
# Role
Expert Node.js/TypeScript backend engineer.

# Task
Write comprehensive unit tests for authentication middleware.

# Requirements
1. Happy path: valid JWT -> next() called, user on req
2. Invalid token -> 401, next() not called
3. Expired token -> 401 with expiry message
4. Missing Authorization header -> 401

# Tech Stack
Express 4.x, TypeScript strict mode, Jest + supertest, jsonwebtoken
```

Provider is set once in config. Auto-detected for common CLI tools (e.g. when Aider is
invoked with --model claude, set target to Claude automatically).

### Feature 3: Prompt Replay and Learning Loop

Local SQLite stores every enhancement session. The system learns preferences and adjusts.

Schema (simplified):
```sql
CREATE TABLE enhancements (
    id           INTEGER PRIMARY KEY,
    original     TEXT NOT NULL,
    enhanced     TEXT NOT NULL,
    decision     TEXT CHECK(decision IN ('accept','reject','edit')),
    edit_result  TEXT,            -- what user changed it to if decision='edit'
    tier_used    INTEGER,
    provider     TEXT,
    peem_before  REAL,
    peem_after   REAL,
    project_root TEXT,
    timestamp    INTEGER
);

CREATE TABLE preferences (
    key          TEXT PRIMARY KEY,  -- e.g. "skip_role_preamble"
    value        TEXT,
    confidence   REAL,              -- 0.0-1.0 based on how many times observed
    updated_at   INTEGER
);
```

Learning in practice:
```
Session 1:  User rejects "You are an expert..." preamble x3
            -> preference: skip_role_preamble = true (confidence: 0.6)

Session 5:  User always accepts numbered structure x8
            -> preference: prefer_numbered_structure = true (confidence: 0.9)

Session 20: User always edits to add "Keep it under 200 words" x12
            -> preference: auto_append_length_constraint = true (confidence: 0.95)

Session 21: Enhancement omits role preamble, uses numbered structure,
            appends length constraint automatically.
            Acceptance rate this week: 91% (was 67%)
```

Preferences only apply when confidence >= 0.7. Users can view preferences with
"promptune history --preferences" and clear them with "promptune history --clear-preferences".

### Feature 4: Team Prompt Sharing via .prompts/ Directory

Version-controlled team prompt templates committed to the repository. New team members
inherit team prompt engineering knowledge immediately.

Directory structure:
```
project-root/
+-- .prompts/
    +-- config.yaml              # Team defaults: provider, mode, constraints
    +-- templates/
    |   +-- code-review.md
    |   +-- bug-fix.md
    |   +-- test-generation.md
    +-- rules/
        +-- team-rules.yaml      # Custom lint rules, banned phrases
```

Example template (templates/bug-fix.md):
```markdown
---
name: bug-fix
trigger: "bug|error|fix|failing|broken|crash|exception"
provider: claude
mode: detailed
---
<instructions>
You are debugging a {{stack}} application.
Provide a specific, root-cause fix — not a symptom patch.
</instructions>
<context>
Repository: {{repo_name}} | Branch: {{branch}}
Recent error: {{last_error}}
Team conventions: named exports, pnpm, strict TypeScript, no `any`
</context>
<task>{{user_input}}</task>
<requirements>
  - Identify root cause, not just symptom
  - Show corrected code with inline comments explaining each change
  - Note if the fix has downstream effects elsewhere in the codebase
  - Suggest a test case that would catch this regression
</requirements>
```

Variables {{branch}}, {{last_error}}, {{repo_name}}, {{stack}} filled automatically from
context fingerprint. {{user_input}} is the user's original prompt.

Template matching: trigger keywords are regex-matched against the user's prompt. If multiple
templates match, use the one with the longest trigger string (most specific). If equal
specificity, use alphabetically first.

### Feature 5: Semantic Deduplication

When a user types something semantically similar to a previous prompt, the system detects the
match and offers the cached enhancement — zero API cost, sub-second response.

Implementation: TF-IDF keyword overlap at Tier 0 (no model needed). Cosine similarity threshold
of 0.85 triggers a cache hit.

TUI display:
```
Lightning bolt: Similar prompt found in history (92% match)
  Matched: "fix TypeScript error"  [3 days ago · accepted · Tier 1]

  Cached enhancement:
  +--------------------------------------------------+
  | Diagnose and fix the TypeScript compilation      |
  | error. Provide: (1) likely cause, (2) specific   |
  | code fix, (3) how to prevent this pattern.       |
  | Show corrected code with brief explanations.     |
  +--------------------------------------------------+

  [A] Accept cached  [F] Enhance fresh  [D] Diff cached vs. fresh
```

### Feature 6: Shell History Integration

Reads ~/.zsh_history / ~/.bash_history / ~/.local/share/fish/fish_history to understand what
the user was doing immediately before typing a prompt.

Scenario: User ran "docker compose up" -> failed: "bind: address already in use (port 5432)."
User types: "help me fix the docker issue"

Without shell history:
  [generic 6-word prompt -> generic advice about Docker]

With shell history:
  "My docker compose up failed with 'bind: address already in use' on port 5432
   (PostgreSQL conflict) on macOS Sequoia. Help me: (1) identify what process owns
   port 5432, (2) stop it or remap docker-compose.yml to use a different host port,
   (3) add a docker-compose override to prevent this permanently. Docker Desktop 4.x."

Six words in. Precise, actionable, complete prompt out.

---

## Token Budget and Cost Discipline

### Token Budget per Tier 2 Enhancement Call

| Component                      | Tokens    | Notes                                              |
|--------------------------------|-----------|----------------------------------------------------|
| System prompt (7 rules)        | ~95       | Cached after first call (90% cost reduction)       |
| Context fingerprint            | ~40       | Hard-capped, never exceeds 50                      |
| User's prompt                  | ~50-150   | Varies                                             |
| Total input                    | ~185-285  |                                                    |
| Max output (max_tokens=400)    | 400       | Hard ceiling                                       |
| Total round-trip               | ~585-685  |                                                    |

### Cost Optimisation Rules

1. System prompt caching: Anthropic, OpenAI, Google all support it. 90% cost reduction after
   first call in a session.
2. 50-token fingerprint cap: always trimmed. Priority order: branch > error > stack > files.
3. No full diffs: never include git diff output. Changed file paths only.
4. No file contents: never read and include source files in context.
5. Tier routing first: 75% of prompts handled by Tier 0 or Tier 1 at zero API cost.
6. max_tier config: user can hard-cap at Tier 1 (fully free) or Tier 0 (instant + free).

---

## Build Phases

### Current State (as of this document)

From the original promptune CLI Build Guide (Steps 0-10), the following are COMPLETED:
- Step 0: Project scaffold
- Step 1: Config layer (~/.config/promptune/config.toml)
- Step 2: API base layer (BaseProvider abstract class)
- Step 3: Claude provider
- Step 4: OpenAI + OpenRouter providers
- Step 5: Core enhancement logic (PromptEnhancer, meta-prompt)
- Step 6: TUI layer (Rich panels, spinner, Accept/Edit/Reject)
- Step 7: CLI entry point (Click, stdout/stderr separation)
- Step 8: Shell widgets (shell/promptune.zsh + shell/promptune.bash)
- Step 9: Installer
- Step 10: Integration tests

NOTE: The rename from "promptsmith" to "promptune" has been completed across the entire codebase.

---

### Phase 1 — Terminal / CLI (Mac + Linux) — NEXT PHASE

Core product for CLI developers on any Unix system. Shell widget approach — no daemon, no OS
permissions required. Everything runs inside the terminal session.

How it works: User types a prompt, presses Ctrl+E in terminal, the shell widget captures
$BUFFER (zsh) or $READLINE_LINE (bash) or commandline (fish), passes to "promptune enhance",
TUI shows diff with PEEM scores, accepted text is injected back into the shell buffer.

Shell widget pattern (zsh — already implemented, keep this approach):
```bash
_promptune_enhance() {
    if [[ -z "$BUFFER" ]]; then return; fi
    local enhanced
    enhanced=$(promptune enhance "$BUFFER" --stdout-only 2>/dev/null)
    if [[ $? -eq 0 && -n "$enhanced" ]]; then
        BUFFER="$enhanced"
        CURSOR=${#BUFFER}
    fi
}
zle -N _promptune_enhance
bindkey "^E" _promptune_enhance
```

Feature checklist for Phase 1:
- [x] Rename throughout codebase: promptsmith -> promptune
- [x] Tier 0 rule-based engine (9-rule pipeline in tier0.py)
- [x] Tier 1: Ollama HTTP client integration (local.py, OpenAI-compatible)
- [x] Tier 2: existing Claude/OpenAI/OpenRouter providers
- [x] Smart tier routing (quality scorer 0-100, threshold at 70)
- [x] PQS scoring display in TUI (5-dimension color-coded bars in pqs.py)
- [x] Context fingerprinting module (git, shell history, stack detection, env)
- [x] Provider-specific formatting (XML/Markdown/Plain auto-detection in formatter.py)
- [x] Shell history parser (~/.zsh_history, ~/.bash_history, fish history)
- [x] SQLite history (history.py with WAL mode, auto-pruning)
- [x] zsh widget — Ctrl+E (ZLE + bindkey)
- [x] bash widget — Ctrl+E (bind -x + READLINE_LINE)
- [x] fish shell widget — Ctrl+E (commandline + bind)
- [x] "promptune enhance [text]" — direct argument invocation
- [x] "promptune enhance" — read from stdin
- [x] echo "prompt" | promptune enhance — pipe support
- [x] --style minimal|balanced|detailed flag
- [x] --provider claude|openai|openrouter flag
- [x] --tier 0|1|2 flag (force specific tier)
- [x] --no-tui flag (no TUI, for shell widget use)
- [x] --json flag (structured output for scripting)
- [x] --format xml|markdown|plain flag
- [x] "promptune config show"
- [x] "promptune config --set-key <provider> <key>"
- [x] "promptune config --set-tier <0|1|2>"
- [x] "promptune config --reset"
- [x] "promptune config init" — interactive setup wizard with masked API key input
- [x] "promptune history" — last 20 enhancements
- [x] "promptune history --n <N>" — last N enhancements
- [x] "promptune history --stats" — acceptance rate, avg score improvement
- [x] "promptune history --clear" — clear all history (with confirmation)
- [x] "promptune local-llm-status" — check local LLM connectivity
- [x] "promptune doctor" — full system check (Python, config, tiers, shell widget)
- [x] macOS installer (install.sh)
- [x] Coverage >= 90%
- [x] Context secret sanitization (API keys, tokens, high-entropy strings)
- [x] Warp Terminal detection and warning

**Moved to Enhancement Phase (see below):**
- Preference learning from history
- Semantic deduplication (TF-IDF cache)
- Team .prompts/ template detection and variable injection
- `history --preferences` / `--clear-preferences` commands
- Linux installer (install-linux.sh)
- Ollama auto-check in installer

---

### Enhancement Phase — Smart Features & Platform Expansion

Builds on the completed Phase 1 foundation. Adds intelligence (learning, dedup, templates)
and platform reach (Linux). These features were originally in Phase 1 but deferred to allow
shipping a complete, stable core product first.

Feature checklist for Enhancement Phase:
- [x] Preference learning engine — analyze accepted/rejected/edited history to adapt future
      enhancements (e.g., user always removes role assignment → stop adding it)
- [x] "promptune history --preferences" — show learned preferences and confidence scores
- [ ] "promptune history --clear-preferences" — reset learned preferences only
- [x] Semantic deduplication — TF cosine similarity cache lookup before calling AI tiers; skip
      enhancement if a similar prompt was recently enhanced (configurable similarity threshold)
- [x] Team .prompts/ template detection — scan for .prompts/ directory in project root,
      load templates, apply variable injection (e.g., {{stack}}, {{branch}})
- [ ] Linux installer (install-linux.sh) — adapt from macOS version with apt/dnf/pacman detection
- [x] Ollama auto-check in installer — detect if Ollama is installed, offer to install if missing

---

### Phase 2 — OS-Level Hotkey Daemon (macOS only)

Extends promptune to work in any macOS application without IDE plugins or browser extensions.

Architecture:
```
promptune daemon (background process on macOS)
    |
    +-- Registers Ctrl+Shift+E as global hotkey via CGEventTap
    |
    +-- On hotkey press:
    |     +-- Simulate Cmd+C (copy selection to clipboard)
    |     +-- Read clipboard via pbpaste
    |     +-- Run enhancement engine (same Tier 0/1/2 as Phase 1)
    |     +-- Write result to clipboard via pbcopy
    |     +-- Simulate Cmd+V (paste result into active window)
    |
    +-- Tracks last active terminal CWD via IPC socket
    |   (shell widget reports its CWD to daemon on each enhancement)
    |
    +-- Keeps Ollama model warm (pre-loads qwen2.5:3b on startup)
    |
    +-- IPC: Unix socket at ~/.local/share/promptune/promptune.sock
    |
    +-- Logs to ~/.local/share/promptune/daemon.log
```

Feature checklist for Phase 2:
- [x] "promptune daemon start" — start background daemon, write PID file
- [x] "promptune daemon stop" — graceful shutdown
- [x] "promptune daemon status" — running/stopped, PID, uptime, enhancement count
- [x] "promptune daemon restart" — stop + start
- [x] "promptune daemon setup" — walk through Accessibility permission (step-by-step)
- [x] "promptune daemon install-login-item" — register LaunchAgent for auto-start
- [x] "promptune daemon uninstall-login-item" — remove LaunchAgent
- [x] "promptune daemon diagnose" — check LaunchAgent, permissions, socket, binary path
- [x] macOS: global hotkey registration via CGEventTap
- [x] macOS: Cmd+C simulation via CGEventCreate
- [x] macOS: pbpaste for reading clipboard text
- [x] macOS: pbcopy for writing clipboard text
- [x] macOS: Cmd+V simulation via CGEventCreate
- [x] Detect if Accessibility permission granted; prompt user if not
- [x] Handle macOS Secure Input (password fields) — detect and skip gracefully
- [x] Hotkey conflict detection on startup — warn user if Ctrl+Shift+E is taken
- [x] Allow hotkey customisation in config (hotkey: "ctrl+shift+e")
- [x] LaunchAgent plist: ~/Library/LaunchAgents/dev.promptune.daemon.plist
- [x] LaunchAgent: KeepAlive true (auto-restart on crash)
- [x] Ollama model pre-warm on daemon startup
- [x] IPC Unix socket: shell widget reports CWD to daemon
- [x] Daemon tracks last known git repo and project root from IPC reports
- [x] Silent mode (default for non-terminal invocations):
      enhance and replace immediately, no TUI, user can Ctrl+Z/Cmd+Z to undo
- [x] macOS notification on completion with score improvement
- [x] Store original text to temp file before enhancement (enable undo)
- [x] Detect focused app at hotkey press; if different app focused before paste,
      paste to clipboard only and show notification "Enhanced text in clipboard — paste manually"
- [x] Handle empty clipboard after Cmd+C simulation — show notification
- [x] Handle non-text clipboard content — show notification "Select text first"
- [ ] macOS version testing: Monterey (12+), Ventura (13), Sonoma (14), Sequoia (15)

---

### Phase 3 — Linux OS-Level Hotkey Daemon — COMPLETED

Port Phase 2 daemon to Linux via platform abstraction layer, combining CLI and daemon support for both X11 and Wayland. (Blueprint Phases 3+4 merged into one implementation phase.)

Feature checklist:
- [x] Platform abstraction layer: `daemon/platform/` package with 6 ABCs
- [x] `get_platform()` factory: runtime detection (macOS / Linux X11 / Linux Wayland / WSL block)
- [x] Detect display server: `XDG_SESSION_TYPE` with `WAYLAND_DISPLAY`/`DISPLAY` fallback
- [x] WSL detection: blocked with clear `PlatformError`
- [x] macOS adapter: wraps existing hotkey.py, clipboard.py, notify.py, launchagent.py
- [x] X11: xclip for clipboard read/write
- [x] X11: xdotool key ctrl+c / ctrl+v for copy/paste simulation
- [x] X11: python-xlib XGrabKey for hotkey registration
- [x] X11: `_NET_ACTIVE_WINDOW` for active window detection
- [x] Wayland: wl-paste / wl-copy for clipboard
- [x] Wayland: ydotool for key simulation
- [x] Wayland: XDG Desktop Portal GlobalShortcuts (dbus-next) for hotkey
- [x] Wayland fallback: evdev hotkey listener (requires `input` group)
- [x] Wayland active window: GNOME Shell gdbus / KDE KWin qdbus / sway IPC
- [x] Dependency checker with package manager detection (apt/dnf/pacman/zypper)
- [x] `get_install_command()` shows exact install command for missing tools
- [x] systemd user service: `~/.config/systemd/user/promptune.service`
- [x] `promptune daemon install` — cross-platform service install (systemd on Linux, LaunchAgent on macOS)
- [x] `promptune daemon uninstall` — cross-platform service removal
- [x] `promptune daemon purge` — remove all daemon files (service, socket, PID, undo, logs)
- [x] `daemon.py` refactored to use platform factory (no direct macOS imports)
- [x] `promptune daemon setup` dispatches to platform-specific setup
- [x] `promptune daemon diagnose` uses platform factory for checks
- [x] `pyproject.toml`: `linux-daemon` optional dep group (python-xlib, dbus-next, evdev)
- [x] 83 platform tests across 7 test files, full TDD coverage
- [ ] Test on GNOME (X11 + Wayland), KDE Plasma (X11 + Wayland) — manual testing pending
- [ ] Test on Ubuntu 22.04, 24.04; Fedora 40; Arch Linux — manual testing pending
- [ ] Handle Snap/Flatpak sandboxed apps (clipboard may be restricted)
- [ ] Linux installer (install-linux.sh) — apt/dnf/pacman detection

---

## Comprehensive Edge Cases

Every known edge case and expected handling. Use this during implementation.

### Enhancement Engine

| Edge case | Expected behaviour |
|---|---|
| Empty prompt | Show: "Nothing to enhance." Return immediately. |
| Single word prompt | Tier 0 flags "too short". Offer minimal structure. |
| Prompt already well-structured (PEEM >= 70) | "Prompt looks good (score: 74). Minor improvements only." |
| Prompt longer than 2,000 characters | Warn: "Long prompt — enhancement may be slow." Use max_tokens=600. |
| Prompt contains code blocks (triple backtick) | Treat code blocks as opaque. Only enhance surrounding description text. |
| Prompt not in English | Detect language. Apply structural enhancement in same language. No translation. |
| Prompt contains sensitive data (API keys, passwords) | Detect patterns (sk-, Bearer, password=). Warn and offer Tier 0/1 only. |
| Enhancement shorter than original | Flag as potential quality issue. Show diff. Never silently downgrade. |
| Enhancement changes meaning (intent drift) | Mitigated by system prompt: "preserve original intent exactly." User can reject. |
| Tier 1 model returns hallucinated content | Check key noun/verb overlap (>70% required). If fails, fall back to Tier 0 result and flag. |
| Tier 2 API returns malformed JSON | Catch parse error. Fall back to Tier 1 result. Log error. |
| Tier 2 API rate-limited (429) | Retry once after 5 seconds. If still limited, fall back to Tier 1. Notify user. |
| Network offline (Tier 2 fails) | Auto-fall-back to Tier 1. Show: "Offline — used local model." |
| Ollama not installed | Clear install instructions: brew install ollama && ollama pull qwen2.5:3b |
| Ollama installed, model not pulled | Show: "Model not found. Run: ollama pull qwen2.5:3b" |
| Ollama cold start (model loading) | Show spinner. Wait up to 30s. Timeout -> fall back to Tier 0. |
| No API key configured (Tier 2 needed) | Show: "No API key. Using local model. Run: promptune config --set-key claude sk-..." |
| Invalid API key (401) | Show: "Invalid API key. Run: promptune test-connection to diagnose." |
| Enhancement timeout (>10 seconds) | Fall back to tier below. Notify user which tier was used. |
| User presses Ctrl+C during enhancement | Graceful exit. Restore original to buffer. No partial text left. |

### Context Fingerprinting

| Edge case | Expected behaviour |
|---|---|
| Not in a git repository | Skip all git context. Continue with shell history + stack only. |
| Git repo with no commits | Skip git context entirely. |
| Git status is slow (>500ms) | Timeout git status call. Skip git context. |
| Git not installed | Skip all git context silently. |
| Shell history file does not exist | Skip shell history silently. |
| Shell history file not readable | Skip shell history silently. |
| Shell history file >10MB | Read only last 500 lines. |
| No recognisable tech stack | Skip stack detection. Proceed without. |
| Multiple package.json in subdirectories | Use the one closest to cwd. |
| Monorepo (pnpm-workspace.yaml, lerna.json) | Report as "monorepo" + detect active package from cwd. |
| Python virtualenv active | Detect $VIRTUAL_ENV or $CONDA_DEFAULT_ENV. Include in stack. |
| Context fingerprint exceeds 50 tokens | Trim in priority order: branch > error > stack > files. |

### Shell Widget

| Edge case | Expected behaviour |
|---|---|
| $BUFFER empty (zsh) | Widget does nothing. |
| $READLINE_LINE empty (bash) | Widget does nothing. |
| promptune binary not in PATH | Inline error: "promptune not found. Check installation." Does not crash shell. |
| promptune exits non-zero | Restore original buffer. Show error inline. |
| Non-interactive shell | Guard with [[ $- == *i* ]] — widget not loaded in non-interactive shells. |
| Terminal too narrow (<60 cols) | TUI truncates and wraps. Test minimum 40 cols. |
| No colour support ($TERM=dumb or $NO_COLOR) | Fall back to plain text output. |
| fish shell | Use "commandline" API. Separate fish widget implementation. |

### OS Hotkey Daemon (macOS)

| Edge case | Expected behaviour |
|---|---|
| Accessibility permission not granted | Detect on start. Open System Settings to correct pane. Show step-by-step. |
| Accessibility permission revoked while running | Detect error on next press. Show notification with fix instructions. |
| Hotkey conflicts with existing app | Detect on startup (check symbolichotkeys plist). Warn + suggest alternative. |
| macOS Secure Input mode (password field) | Detect SecureInputIsEnabled(). Show: "Cannot enhance in secure input field." |
| Clipboard empty after Cmd+C simulation | Show: "Select text first, then press Ctrl+Shift+E." |
| Clipboard has non-text content | Detect non-text type. Show: "Select text to enhance." |
| Another app overwrites clipboard during enhancement | Detect clipboard change between copy and paste. Warn. Fall back to clipboard-only (no auto-paste). |
| User switches app during enhancement | Track focused app at hotkey press. If different app when pasting, paste to clipboard only. Notify. |
| App in fullscreen mode | CGEventCreate works in fullscreen. Test explicitly per app. |
| LaunchAgent not loading on login | "promptune daemon diagnose" checks plist, permissions, binary path. |
| Daemon crashes mid-enhancement | LaunchAgent KeepAlive:true restarts it. Original text stored in temp file pre-enhancement. |
| Two terminal sessions simultaneously | Both use same daemon via IPC socket. Last-writer-wins for CWD. SQLite WAL handles concurrent reads. |

### OS Hotkey Daemon (Linux)

| Edge case | Expected behaviour |
|---|---|
| xclip not installed | Show: "xclip required. Run: sudo apt install xclip" (adapt for distro). |
| xdotool not installed | Show: "xdotool required. Run: sudo apt install xdotool". |
| wl-clipboard not installed | Show: "wl-clipboard required. Run: sudo apt install wl-clipboard". |
| ydotool permissions missing | Show instructions to add udev rule for ydotool. |
| Wayland compositor does not support global hotkeys | Fall back: show manual binding instructions for GNOME/KDE/Sway. |
| SSH session with no display | Detect missing $DISPLAY and $WAYLAND_DISPLAY. Use terminal-only mode. No daemon. |
| Flatpak/Snap app clipboard restriction | Detect failure. Notify user that sandboxed apps may block clipboard access. |

### SQLite / History

| Edge case | Expected behaviour |
|---|---|
| Database does not exist (first run) | Create automatically with schema migrations. |
| Database corrupted | Run PRAGMA integrity_check. If fails, back up and create fresh. Never crash. |
| Database >100MB | Auto-prune: keep last 10,000 entries. Log pruning. |
| Concurrent writes (shell widget + daemon) | Use WAL mode (PRAGMA journal_mode=WAL). |
| Disk full | Catch OperationalError. Disable history silently. Show one-time warning. |

### Config

| Edge case | Expected behaviour |
|---|---|
| Config file missing | Create at ~/.config/promptune/config.toml with defaults on first run. |
| Config file malformed TOML | Show parse error with line number. Fall back to defaults. Offer --reset. |
| API key is empty string | Treat as missing. Fall back to lower tier. |
| max_tier: 2 but no API key | Fall back to max_tier: 1 automatically. Warn user. |
| Template has invalid frontmatter | Skip that template. Log warning. Continue with others. |
| Template variable {{branch}} with no git context | Replace with empty string. Do not error. |
| Two templates match same trigger | Use longest trigger string (most specific). Tie -> alphabetically first. |

---

## Technical Architecture

### Module Structure

```
promptune/
+-- promptune/
|   +-- __init__.py
|   +-- cli.py              # Click entry point — all CLI commands
|   +-- config.py           # Config loading/saving (TOML)
|   +-- core.py             # PromptEnhancer — orchestrates tier routing
|   +-- tui.py              # Rich TUI — diff view, PEEM scores, A/E/R
|   +-- scorer.py           # Quality scorer (0-100 heuristic)
|   +-- peem.py             # PEEM dimension scoring
|   +-- context.py          # Context fingerprinting (git, shell, stack)
|   +-- history.py          # SQLite history + learning loop
|   +-- dedup.py            # Semantic deduplication (TF-IDF)
|   +-- templates.py        # .prompts/ scanner + template engine
|   +-- tier0.py            # Rule-based linting + auto-fix engine
|   +-- tier1.py            # Ollama HTTP client (qwen2.5:3b)
|   +-- daemon.py           # OS-level hotkey daemon (Phase 2/4)
|   +-- clipboard.py        # Platform-specific clipboard read/write
|   +-- hotkey.py           # Platform-specific global hotkey registration
|   +-- ipc.py              # Unix socket IPC (shell widget <-> daemon)
|   +-- notifications.py    # macOS/Linux desktop notifications
|   +-- api/
|       +-- __init__.py
|       +-- base.py         # Abstract BaseProvider
|       +-- claude.py       # Anthropic SDK provider
|       +-- openai.py       # OpenAI SDK provider
|       +-- openrouter.py   # OpenRouter via httpx
+-- shell/
|   +-- promptune.zsh       # zsh widget (Ctrl+E)
|   +-- promptune.bash      # bash widget (Ctrl+E)
|   +-- promptune.fish      # fish widget (Ctrl+E) — Phase 1
+-- tests/
|   +-- test_config.py
|   +-- test_core.py
|   +-- test_tier0.py
|   +-- test_tier1.py
|   +-- test_context.py
|   +-- test_history.py
|   +-- test_dedup.py
|   +-- test_templates.py
|   +-- test_peem.py
|   +-- test_scorer.py
|   +-- test_daemon.py      # Phase 2
|   +-- test_clipboard.py   # Phase 2
|   +-- test_ipc.py         # Phase 2
|   +-- test_tui.py
|   +-- test_cli.py
|   +-- test_shell_widget.sh
|   +-- test_integration.py
+-- .prompts/               # promptune's own team templates (dogfood)
|   +-- templates/
|       +-- bug-fix.md
+-- CLAUDE.md               # Claude Code context file (update per phase)
+-- pyproject.toml
+-- install.sh              # macOS installer (Phase 1+2)
+-- install-linux.sh        # Linux installer (Phase 3+4)
+-- config.example.toml
```

### Data Flow (complete)

```
User input (terminal buffer or OS clipboard)
        |
        v
context.py: build_context_fingerprint(cwd)
        |
        v
templates.py: check .prompts/ for trigger match
  +-- match found -> load template, inject variables
  +-- no match -> continue with raw prompt
        |
        v
dedup.py: TF-IDF similarity check against history
  +-- hit (>85% similarity) -> offer cached result
  +-- miss -> continue
        |
        v
scorer.py: compute quality score (0-100)
        |
        v
tier0.py: apply rule-based fixes (ALWAYS runs first)
        |
    score check
    +-- >= 70 -> return Tier 0 result
    +-- 40-69 -> tier1.py (Ollama qwen2.5:3b)
    +-- < 40  -> api/ (Claude/OpenAI/OpenRouter)
        |
        v
peem.py: score before + after (3 prompt-level dimensions)
        |
        v
tui.py: show diff + PEEM scores + A/E/R (terminal mode)
  OR
notifications.py: silent replace + macOS notification (daemon mode)
        |
        v
history.py: store result + decision + PEEM scores
        |
        v
history.py: update preference model if decision is consistent
        |
        v
Output: enhanced prompt to shell buffer OR clipboard
```

---

## Config Schema (TOML)

Location: ~/.config/promptune/config.toml

```toml
[provider]
default = "claude"
model_claude = "claude-haiku-4-5-20251001"
model_openai = "gpt-4o-mini"
model_openrouter = "anthropic/claude-haiku"

[api_keys]
claude = ""
openai = ""
openrouter = ""

[enhancement]
max_tier = 2                  # 0=rules only, 1=+local, 2=+cloud
default_mode = "balanced"     # minimal | balanced | detailed
max_tokens_output = 400
timeout_seconds = 10

[ollama]
enabled = true
model = "qwen2.5:3b"
host = "http://localhost:11434"
prewarm = true

[context]
use_git = true
use_shell_history = true
use_stack_detection = true
max_context_tokens = 50
shell_history_lines = 20

[daemon]
hotkey = "ctrl+shift+e"
silent_mode = true            # paste immediately, no TUI (non-terminal invocations)
auto_start = false            # toggled to true by install-login-item command

[history]
enabled = true
max_entries = 10000
db_path = "~/.local/share/promptune/history.db"

[tui]
show_peem_scores = true
show_tier_used = true
show_latency = true
colour = true

[auto_enhance]
enabled = true                # auto-enhance in AI tools
threshold = 40                # PQS score below which to enhance
min_words = 5                 # skip prompts shorter than this
```

---

## CLI Command Reference

```
Enhancement:
  promptune enhance "text"              enhance from argument
  promptune enhance                     read from stdin
  echo "text" | promptune enhance       pipe support
  promptune enhance --mode minimal      minimal|balanced|detailed
  promptune enhance --provider openai   override provider for one call
  promptune enhance --tier 1            force specific tier
  promptune enhance --stdout-only       no TUI, plain output (for shell widget)
  promptune enhance --json              structured JSON output (for scripting)

Config:
  promptune config --show               show config, mask API keys
  promptune config --set-key claude sk-...
  promptune config --set-provider openai
  promptune config --set-tier 1
  promptune config --reset              restore all defaults

Scoring:
  promptune score "text"                score prompt (7 dimensions, 0-100)
  promptune score --json "text"         structured JSON output

MCP Server:
  promptune mcp                         start MCP server (stdio transport)

Auto-Enhance (internal, used by hooks):
  promptune gate                        read JSON stdin, score, enhance if needed

Diagnostics:
  promptune test-connection             test all configured API keys
  promptune test-connection --provider claude
  promptune ollama-status               check Ollama + model availability
  promptune doctor                      full system check (+ auto-enhance status)

History:
  promptune history                     last 20 enhancements
  promptune history --n 50
  promptune history --stats             acceptance rate, avg PEEM improvement
  promptune history --preferences       show learned preferences
  promptune history --clear             clear all history (with confirmation)
  promptune history --clear-preferences reset learned preferences only

Daemon (Phase 2 — macOS):
  promptune daemon start
  promptune daemon stop
  promptune daemon status
  promptune daemon restart
  promptune daemon setup                Accessibility permission wizard
  promptune daemon install-login-item   auto-start on login
  promptune daemon uninstall-login-item remove auto-start
  promptune daemon diagnose             check LaunchAgent, perms, socket
```

---

## What promptune Is Not

- Not an AI assistant. It does not answer questions or have conversations.
- Not a prompt manager. History is automatic. No manual saving or tagging.
- Not an IDE plugin. OS-level hotkey (Phase 2/4) covers all IDEs without per-IDE code.
- Not a browser extension. OS hotkey works in browsers without one.
- Not a web app or SaaS. No accounts. No cloud. Everything local.
- Not an agent. One input, one output. No multi-step execution.
- Not a replacement for any AI. It enhances prompts going to Claude, GPT-4, Gemini, Llama.

Unix philosophy: do one thing, do it exceptionally well, compose cleanly with everything else.

---

## Delivery Summary

```
Phase 1 — Terminal/CLI (Mac + Linux)
  Shell widget: zsh, bash, fish  |  Ctrl+E
  Full enhancement engine: Tier 0 + 1 + 2 + smart routing
  PEEM scoring  |  Context fingerprinting  |  Provider formatting
  Shell history  |  SQLite learning loop  |  Deduplication  |  Templates
  All CLI commands  |  macOS + Linux installers

Phase 2 — OS-Level Daemon (macOS only)
  Global Ctrl+Shift+E in any macOS application
  Clipboard pipeline: CGEventCreate + pbpaste/pbcopy
  Silent mode (paste immediately) + Cmd+Z undo support
  LaunchAgent auto-start  |  Accessibility permission wizard
  IPC: shell widget reports CWD to daemon

Phase 3 — Linux OS-Level Daemon (COMPLETED)
  X11: xclip + xdotool + python-xlib (XGrabKey)
  Wayland: wl-clipboard + ydotool + Portal GlobalShortcuts / evdev fallback
  Systemd user service  |  GNOME + KDE + sway active window detection
  Platform abstraction layer (ABCs + factory)  |  WSL detection + block

Future (not scheduled):
  Browser extension — only if OS hotkey approach has meaningful gaps
```
