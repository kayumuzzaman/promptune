#!/usr/bin/env python3
"""Generate looping animated-terminal GIFs demoing promptune's usage paths.

Renders authentic-style Claude Code and Codex TUI chrome (input composer box,
tool-call rendering, status footer) plus plain-shell scenes. Zero runtime deps
beyond Pillow. Run: python3 gen_demo_gifs.py

Outputs: option-a.gif (shell), option-b.gif (Claude Code MCP),
option-c.gif (Codex gate), option-settings.gif (config wizard).

NOTE: the Claude Code / Codex frames are faithful recreations, not screen
captures (a live ratatui/TUI can't be captured headlessly). Wizard text is the
literal prompt strings from promptune/setup.py.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).parent

# --- theme (GitHub dark) ---
BG = (13, 17, 23)
CHROME = (22, 27, 34)
WHITE = (230, 237, 243)
GREEN = (63, 185, 80)
DIM = (139, 148, 158)
FAINT = (88, 96, 105)
BLUE = (88, 166, 255)
ORANGE = (240, 142, 53)
RED = (255, 95, 86)
YELLOW = (255, 189, 46)
CURSOR = (230, 237, 243)
BORDER = (74, 84, 96)

FONT_PATH = "/System/Library/Fonts/Menlo.ttc"
FSIZE = 18
LINE_H = 27
PAD_X = 24
CHROME_H = 40
PAD_TOP = CHROME_H + 14
BOT_PAD = 16

font = ImageFont.truetype(FONT_PATH, FSIZE)
title_font = ImageFont.truetype(FONT_PATH, 13)
CHAR_W = font.getlength("M")


def _ramp(fg, steps=5):
    out = []
    for i in range(steps):
        t = i / (steps - 1)
        out.append(tuple(round(fg[c] * (1 - t) + BG[c] * t) for c in range(3)))
    return out


_PAL_COLORS = [BG, CHROME]
for _c in (WHITE, GREEN, DIM, FAINT, BLUE, ORANGE, RED, YELLOW, CURSOR, BORDER):
    _PAL_COLORS += _ramp(_c)
_flat = []
for _c in _PAL_COLORS:
    _flat += list(_c)
_flat += [0, 0, 0] * (256 - len(_PAL_COLORS))
_PAL_IMG = Image.new("P", (1, 1))
_PAL_IMG.putpalette(_flat)


def _chrome(img, width, title):
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, width, CHROME_H], fill=CHROME)
    for i, col in enumerate((RED, YELLOW, GREEN)):
        cx = 20 + i * 20
        d.ellipse([cx - 6, CHROME_H // 2 - 6, cx + 6, CHROME_H // 2 + 6], fill=col)
    tw = title_font.getlength(title)
    d.text(((width - tw) / 2, CHROME_H / 2 - 7), title, font=title_font, fill=DIM)


def _text(d, x, y, s, color):
    d.text((x, y), s, font=font, fill=color)


def _cursor(d, x, y):
    d.rectangle([x + 1, y + 3, x + 1 + CHAR_W, y + FSIZE + 3], fill=CURSOR)


def _box(d, x, y, n_inner, color=BORDER):
    """Draw a rounded composer box: top border, 1 content row, bottom border."""
    top = "╭" + "─" * n_inner + "╮"
    bot = "╰" + "─" * n_inner + "╯"
    _text(d, x, y, top, color)
    _text(d, x, y + LINE_H, "│", color)
    _text(d, x + CHAR_W * (n_inner + 1), y + LINE_H, "│", color)
    _text(d, x, y + LINE_H * 2, bot, color)


def render(width, height, title, body, *, banner=None, active=None,
           composer=None, footer=None, compose_y=None):
    img = Image.new("RGB", (width, height), BG)
    _chrome(img, width, title)
    d = ImageDraw.Draw(img)
    y = PAD_TOP
    if banner is not None:
        _text(d, PAD_X, y, banner[0], banner[1])
        y += LINE_H + 6
    body_top = y
    for item in body:
        indent, s, color = item
        _text(d, PAD_X + indent * CHAR_W, y, s, color)
        y += LINE_H
    if active is not None:
        indent, s, color = active
        ax = PAD_X + indent * CHAR_W
        _text(d, ax, y, s, color)
        _cursor(d, ax + font.getlength(s), y)
    if composer is not None:
        n_inner = int((width - 2 * PAD_X) / CHAR_W) - 2
        cy = compose_y
        _box(d, PAD_X, cy, n_inner)
        prompt, ctext, placeholder, cactive = composer
        tx = PAD_X + CHAR_W * 2
        ty = cy + LINE_H
        if ctext or cactive:
            _text(d, tx, ty, prompt + ctext, WHITE)
            if cactive:
                _cursor(d, tx + font.getlength(prompt + ctext), ty)
        else:
            _text(d, tx, ty, prompt + placeholder, FAINT)
        if footer is not None:
            _text(d, PAD_X + 2, cy + LINE_H * 3 + 4, footer, FAINT)
    elif footer is not None:
        _text(d, PAD_X, height - BOT_PAD - LINE_H, footer, FAINT)
    return img.quantize(palette=_PAL_IMG, dither=Image.Dither.NONE)


def build(title, script, out_name, *, mode="plain", banner=None, footer=None,
          placeholder="", prompt="> "):
    # Pre-pass: max body rows.
    body_rows = 0
    cur = 0
    for ev in script:
        k = ev[0]
        if k in ("line", "qa", "type", "submit"):
            cur += 1 if k != "type" or mode == "plain" else 0
            if k == "submit":
                pass
            body_rows = max(body_rows, cur)
    body_rows += 1

    width = 880
    banner_h = (LINE_H + 6) if banner else 0
    if mode == "chat":
        compose_block = LINE_H * 3 + (LINE_H if footer else 0) + 6
        height = PAD_TOP + banner_h + body_rows * LINE_H + 14 + compose_block + BOT_PAD
        compose_y = height - BOT_PAD - LINE_H * 3 - (LINE_H if footer else 0)
    else:
        height = PAD_TOP + banner_h + body_rows * LINE_H + BOT_PAD + (
            LINE_H if footer else 0)
        compose_y = None

    frames, durs = [], []
    body = []
    compose = ""

    def push(active=None, comp=None, ms=380):
        frames.append(render(width, height, title, list(body), banner=banner,
                             active=active, composer=comp, footer=footer,
                             compose_y=compose_y))
        durs.append(ms)

    def comp_state(text, act):
        if mode != "chat":
            return None
        return (prompt, text, placeholder, act)

    for ev in script:
        k = ev[0]
        if k == "type":  # plain: type a line, then commit
            _, text, color = ev
            for i in range(1, len(text) + 1):
                push(active=(0, text[:i], color), comp=comp_state("", False), ms=30)
            push(active=(text, 0, color)[::-1] if False else (0, text, color),
                 comp=comp_state("", False), ms=320)
            body.append((0, text, color))
        elif k == "qa":  # plain: question prefix + typed answer
            _, q, ans, color = ev
            for i in range(1, len(ans) + 1):
                push(active=(0, q + ans[:i], color), ms=34)
            push(active=(0, q + ans, color), ms=300)
            body.append((0, q + ans, color))
        elif k == "ctype":  # chat: type into composer box
            _, text = ev
            for i in range(1, len(text) + 1):
                push(comp=comp_state(text[:i], True), ms=34)
            push(comp=comp_state(text, True), ms=360)
            compose = text
        elif k == "submit":  # chat: move composer text up into transcript
            _, color = ev
            body.append((0, prompt + compose, color))
            compose = ""
            push(comp=comp_state("", False), ms=320)
        elif k == "line":
            _, indent, text, color = ev[:4]
            body.append((indent, text, color))
            push(comp=comp_state(compose, False), ms=ev[4] if len(ev) > 4 else 430)
        elif k == "pause":
            push(comp=comp_state(compose, False), ms=ev[1])

    out = OUT / out_name
    frames[0].save(out, save_all=True, append_images=frames[1:], duration=durs,
                   loop=0, disposal=2, optimize=False)
    print(f"wrote {out.name}  ({len(frames)} frames, {out.stat().st_size // 1024} KB)")


# ============================================================
# Option A — plain shell, `promptune enhance --no-tui`
# ============================================================
build(
    "promptune  —  Option A · shell  (you run it, every time)",
    [
        ("type", '$ promptune enhance "write tests for parser" --no-tui', GREEN),
        ("line", 0, "", WHITE),
        ("line", 0, "Write unit tests for my parser module.", WHITE),
        ("line", 0, "", WHITE),
        ("line", 0, "Requirements:", DIM),
        ("line", 0, "  1. Cover valid, malformed, and empty input", DIM),
        ("line", 0, "  2. Assert return values AND raised errors", DIM),
        ("line", 0, "  3. Match the project's test framework", DIM),
        ("line", 0, "", WHITE),
        ("line", 0, "→ printed to stdout. pipe it anywhere.", BLUE),
        ("pause", 2200),
    ],
    "option-a.gif",
)

# ============================================================
# Option B — Claude Code TUI, MCP enhance tool
# ============================================================
build(
    "Claude Code  —  Option B · promptune MCP tool",
    [
        ("ctype", "enhance then solve: speed up my api"),
        ("submit", WHITE),
        ("line", 0, "", WHITE),
        ("line", 0, "● promptune - enhance (MCP)", GREEN),
        ("line", 2, "└ Profile and optimize my REST API latency.", DIM),
        ("line", 4, "Find bottlenecks (N+1, queries, serialize),", DIM),
        ("line", 4, "propose fixes with trade-offs.", DIM),
        ("line", 0, "", WHITE),
        ("line", 0, "● I'll start by profiling the hot endpoints…", WHITE),
        ("pause", 2400),
    ],
    "option-b.gif",
    mode="chat",
    banner=("✱ Welcome to Claude Code", DIM),
    footer="? for shortcuts                                  Enter to send",
    placeholder="Try \"edit <filepath>\" or ask a question",
    prompt="> ",
)

# ============================================================
# Option C — Codex TUI, gate hook (auto, silent)
# ============================================================
build(
    "Codex  —  Option C · promptune gate hook (auto, silent)",
    [
        ("ctype", "fix login bug"),
        ("submit", WHITE),
        ("line", 0, "", WHITE),
        ("line", 0, ". promptune: enhanced 24 → 81", FAINT),
        ("line", 0, "", WHITE),
        ("line", 0, "● Debugging the authentication failure in your", GREEN),
        ("line", 2, "login flow. Root cause first…", WHITE),
        ("pause", 1500),
        ("line", 0, "", WHITE),
        ("ctype", "!fix login bug"),
        ("submit", WHITE),
        ("line", 2, "(sent raw — bypass prefix)", FAINT),
        ("pause", 2400),
    ],
    "option-c.gif",
    mode="chat",
    banner=("› OpenAI Codex   v0.139.0   gpt-5", DIM),
    footer="Enter send   Shift+Enter newline            gpt-5 · 98% context left",
    placeholder="Ask Codex to do something",
    prompt="› ",
)

# ============================================================
# Settings — promptune config init (literal prompts from setup.py)
# ============================================================
build(
    "promptune  —  Settings · config init  (setup wizard)",
    [
        ("type", "$ promptune config init", GREEN),
        ("line", 0, "", WHITE),
        ("line", 0, "  Promptune Setup", WHITE),
        ("line", 0, "  ─────────"
                    "──────", DIM),
        ("line", 0, "", WHITE),
        ("qa", "  Provider [claude/openai/openrouter]: ", "claude", WHITE),
        ("qa", "  Claude API key: ", "••••••••••", WHITE),
        ("line", 0, "  ✓ Key format looks valid.", GREEN),
        ("qa", "  Claude model [claude-haiku-4-5]: ", "", WHITE),
        ("line", 0, "", WHITE),
        ("qa", "  Configure advanced settings? [y/N]: ", "y", WHITE),
        ("qa", "  Max tier (0=rules,1=+local,2=+cloud) [0/1/2]: ", "2", WHITE),
        ("line", 0, "", WHITE),
        ("line", 0, "  Found: Claude Code, Codex", DIM),
        ("qa", "  Auto-enhance prompts in these tools? [Y/n]: ", "y", WHITE),
        ("line", 0, "  ✓ Hook installed for Claude Code", GREEN),
        ("line", 0, "  ✓ MCP server registered for Claude Code", GREEN),
        ("line", 0, "  ✓ Hook installed for Codex", GREEN),
        ("line", 0, "", WHITE),
        ("line", 0, "  ✓ Config saved to ~/.config/promptune/config.toml", BLUE),
        ("pause", 2600),
    ],
    "option-settings.gif",
)
