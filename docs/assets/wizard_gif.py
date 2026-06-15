"""Render the Promptune setup-wizard no-key flow as an animated GIF.

Mirrors the real wizard output: tier overview (Tier 0/1 FREE, Tier 2 PAID),
then the optional API-key prompt left blank to stay in free mode.

One-off rendering script (long literal frame lines); line-length lint disabled.
"""
# ruff: noqa: E501
from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

W, H = 940, 600
BG = (26, 27, 38)
BAR = (32, 33, 46)
FG = (192, 202, 245)
DIM = (86, 95, 137)
GREEN = (158, 206, 106)
YELLOW = (224, 175, 104)
CYAN = (125, 207, 255)
WHITE = (215, 221, 247)

FONT = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 16)
CW = FONT.getlength("M")
LH = 23
X0, Y0 = 26, 46

frames: list[Image.Image] = []
durs: list[int] = []
screen: list[list[tuple[str, tuple[int, int, int]]]] = []


def draw(cursor_col: int | None = None, cursor_line: int | None = None) -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 30], fill=BAR)
    for i, c in enumerate([(247, 118, 142), (224, 175, 104), (158, 206, 106)]):
        d.ellipse([18 + i * 22, 10, 30 + i * 22, 22], fill=c)
    d.text((W / 2 - 60, 7), "promptune setup", font=FONT, fill=DIM)
    y = Y0
    for line in screen:
        x = X0
        for text, color in line:
            d.text((x, y), text, font=FONT, fill=color)
            x += CW * len(text)
        y += LH
    if cursor_col is not None and cursor_line is not None:
        cx = X0 + CW * cursor_col
        cy = Y0 + LH * cursor_line
        d.rectangle([cx, cy + 2, cx + CW - 1, cy + LH - 3], fill=FG)
    return img


def snap(dur: int, cursor_col=None, cursor_line=None) -> None:
    frames.append(draw(cursor_col, cursor_line))
    durs.append(dur)


def type_into(line_idx: int, prefix_segs, text: str, color, per=70) -> None:
    base = sum(len(t) for t, _ in prefix_segs)
    for i in range(1, len(text) + 1):
        screen[line_idx] = list(prefix_segs) + [(text[:i], color)]
        snap(per, cursor_col=base + i, cursor_line=line_idx)


# Header
screen.append([("  Promptune Setup", WHITE)])
screen.append([("  " + "─" * 17, DIM)])
screen.append([("", FG)])
snap(600)

# Tier overview (the key message: 0 & 1 free, 2 paid)
screen.append([("  How Promptune enhances your prompts:", FG)])
screen.append([("    Tier 0  Rule-based rewrite       ", FG), ("FREE", GREEN), ("  · offline, no key", DIM)])
snap(450)
screen.append([("    Tier 1  Local LLM (Ollama, …)    ", FG), ("FREE", GREEN), ("  · private, no key", DIM)])
snap(450)
screen.append([("    Tier 2  Cloud LLM (Claude/GPT)   ", FG), ("PAID", YELLOW), ("  · needs an API key", DIM)])
snap(450)
screen.append([("", FG)])
screen.append([("  Tiers 0 & 1 work with no API key. Tier 2 is optional.", DIM)])
screen.append([("", FG)])
snap(1400)

# Provider prompt -> type claude
prov = [("  Provider ", FG), ("[claude/openai/openrouter]: ", DIM)]
screen.append(list(prov))
pidx = len(screen) - 1
snap(350, cursor_col=sum(len(t) for t, _ in prov), cursor_line=pidx)
type_into(pidx, prov, "claude", CYAN)
snap(500)

# Paid note + key prompt left blank
screen.append([("", FG)])
screen.append([("  Tier 2 (cloud) uses a ", FG), ("PAID", YELLOW), (" API key. Leave blank to skip it.", FG)])
keyp = [("  Claude API key ", FG), ("(blank = free mode): ", DIM)]
screen.append(list(keyp))
kidx = len(screen) - 1
snap(1100, cursor_col=sum(len(t) for t, _ in keyp), cursor_line=kidx)
screen[kidx] = list(keyp) + [("⏎", DIM)]
snap(500)

# Green confirmation: free mode
screen.append([("  ✓ No API key set — free mode: Tier 0 + Tier 1.", GREEN)])
snap(1500)

# Model + advanced, accept defaults
screen.append([("", FG)])
screen.append([("  Claude model [claude-haiku-4-5-20251001]: ", FG), ("⏎", DIM)])
snap(800)
screen.append([("  Configure advanced settings? [y/N]: ", FG), ("⏎", DIM)])
snap(800)

# Done
screen.append([("", FG)])
screen.append(
    [("  ✓ Setup complete — no API key, ", GREEN), ("$0/mo", GREEN), (".", GREEN)]
)
snap(2200)

out = "/Users/kayumuzzaman/Projects/promptune/docs/assets/wizard-nokey.gif"
frames[0].save(
    out, save_all=True, append_images=frames[1:],
    duration=durs, loop=0, optimize=True,
)
print("wrote", out, "frames", len(frames), "size", frames[0].size)
