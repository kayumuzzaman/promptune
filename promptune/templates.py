"""Team .prompts/ templates — load, match, inject."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Template:
    """A parsed prompt template."""

    intent: str | None
    domain: str | None
    body: str
    filename: str

    @property
    def specificity(self) -> int:
        """How specific is the match condition? Higher is better."""
        count = 0
        if self.intent:
            count += 1
        if self.domain:
            count += 1
        return count


def parse_template(content: str, filename: str) -> Template | None:
    """Parse a template file with YAML-like frontmatter.

    Returns None if frontmatter is missing, empty, or invalid.
    Uses simple regex parsing to avoid a PyYAML dependency.
    """
    match = re.match(
        r"^---\s*\n(.*?)\n---\s*\n(.*)",
        content,
        re.DOTALL,
    )
    if not match:
        return None

    frontmatter_text = match.group(1).strip()
    body = match.group(2).strip()

    if not frontmatter_text:
        return None

    fields: dict[str, str] = {}
    try:
        for line in frontmatter_text.split("\n"):
            line = line.strip()
            if not line:
                continue
            parts = line.split(":", 1)
            if len(parts) != 2:
                return None
            key = parts[0].strip()
            value = _unquote_scalar(parts[1].strip())
            fields[key] = value
    except Exception:
        return None

    intent = fields.get("intent") or None
    domain = fields.get("domain") or None

    if not intent and not domain:
        return None

    return Template(
        intent=intent,
        domain=domain,
        body=body,
        filename=filename,
    )


def _unquote_scalar(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def load_templates(project_root: Path | str) -> list[Template]:
    """Load all valid templates from .prompts/ directory."""
    prompts_dir = Path(project_root) / ".prompts"
    if not prompts_dir.is_dir():
        return []

    templates: list[Template] = []
    for path in sorted(prompts_dir.glob("*.md")):
        try:
            content = path.read_text()
            tpl = parse_template(content, path.name)
            if tpl is not None:
                templates.append(tpl)
        except Exception:
            continue

    return templates


def match_template(
    project_root: Path | str,
    intent: str,
    domain: str,
    intent_aliases: Iterable[str] | None = None,
    domain_aliases: Iterable[str] | None = None,
) -> Template | None:
    """Find the best matching template for the given intent/domain."""
    templates = load_templates(project_root)
    if not templates:
        return None

    intents = _nonempty_values([intent, *(intent_aliases or [])])
    domains = _nonempty_values([domain, *(domain_aliases or [])])
    candidates: list[Template] = []

    for tpl in templates:
        if tpl.intent and tpl.domain:
            if tpl.intent in intents and tpl.domain in domains:
                candidates.append(tpl)
        elif tpl.intent:
            if tpl.intent in intents:
                candidates.append(tpl)
        elif tpl.domain and tpl.domain in domains:
            candidates.append(tpl)

    if not candidates:
        return None

    candidates.sort(key=lambda t: (-t.specificity, t.filename))
    return candidates[0]


def _nonempty_values(values: Iterable[str]) -> set[str]:
    """Return the set of non-empty values (deduplicated)."""
    return {value for value in values if value}


_PLACEHOLDER_RE = re.compile(r"\{\{([^{}]+)\}\}")


def inject_variables(body: str, variables: dict[str, str]) -> str:
    """Replace {{variable}} placeholders with values.

    Single-pass substitution: a value that itself looks like a placeholder is
    not re-expanded. Unknown variables are left as-is.
    """

    def _replace(match: re.Match[str]) -> str:
        key = match.group(1).strip()
        return variables.get(key, match.group(0))

    return _PLACEHOLDER_RE.sub(_replace, body)
