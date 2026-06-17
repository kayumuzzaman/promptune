"""Team templates tests."""

from __future__ import annotations

from promptune.templates import (
    inject_variables,
    load_templates,
    match_template,
    parse_template,
)


class TestParseTemplate:
    def test_basic_template(self) -> None:
        content = (
            "---\n"
            "intent: debug\n"
            "domain: python\n"
            "---\n"
            "## Bug Context\n"
            "Stack: {{stack}}\n"
        )
        tpl = parse_template(content, "bug.md")
        assert tpl is not None
        assert tpl.intent == "debug"
        assert tpl.domain == "python"
        assert "{{stack}}" in tpl.body

    def test_intent_only(self) -> None:
        content = "---\nintent: coding\n---\nBuild something"
        tpl = parse_template(content, "code.md")
        assert tpl is not None
        assert tpl.intent == "coding"
        assert tpl.domain is None

    def test_domain_only(self) -> None:
        content = "---\ndomain: webdev\n---\nWeb template"
        tpl = parse_template(content, "web.md")
        assert tpl is not None
        assert tpl.intent is None
        assert tpl.domain == "webdev"

    def test_no_frontmatter_returns_none(self) -> None:
        content = "Just text, no frontmatter"
        assert parse_template(content, "bad.md") is None

    def test_empty_frontmatter_returns_none(self) -> None:
        content = "---\n---\nBody text"
        assert parse_template(content, "empty.md") is None

    def test_empty_frontmatter_blank_line(self) -> None:
        """Frontmatter with only blank lines."""
        content = "---\n\n---\nBody text"
        assert parse_template(content, "empty.md") is None

    def test_frontmatter_with_blank_lines(self) -> None:
        """Blank lines in frontmatter are skipped."""
        content = (
            "---\n"
            "intent: debug\n"
            "\n"
            "domain: python\n"
            "---\n"
            "Body"
        )
        tpl = parse_template(content, "gaps.md")
        assert tpl is not None
        assert tpl.intent == "debug"
        assert tpl.domain == "python"

    def test_invalid_frontmatter_returns_none(self) -> None:
        content = "---\nnot: valid: yaml: {{{\n---\nBody"
        assert parse_template(content, "invalid.md") is None

    def test_frontmatter_line_no_colon(self) -> None:
        """Line without colon is malformed."""
        content = "---\nno-colon-here\n---\nBody"
        assert parse_template(content, "bad.md") is None

    def test_filename_stored(self) -> None:
        content = "---\nintent: debug\n---\nBody"
        tpl = parse_template(content, "debug-template.md")
        assert tpl is not None
        assert tpl.filename == "debug-template.md"


class TestLoadTemplates:
    def test_loads_from_directory(self, tmp_path) -> None:
        prompts_dir = tmp_path / ".prompts"
        prompts_dir.mkdir()
        (prompts_dir / "bug.md").write_text(
            "---\nintent: debug\n---\nDebug template"
        )
        (prompts_dir / "code.md").write_text(
            "---\nintent: coding\n---\nCode template"
        )

        templates = load_templates(tmp_path)

        assert len(templates) == 2

    def test_no_prompts_dir_returns_empty(self, tmp_path) -> None:
        templates = load_templates(tmp_path)
        assert templates == []

    def test_empty_dir_returns_empty(self, tmp_path) -> None:
        (tmp_path / ".prompts").mkdir()
        templates = load_templates(tmp_path)
        assert templates == []

    def test_skips_invalid_templates(self, tmp_path) -> None:
        prompts_dir = tmp_path / ".prompts"
        prompts_dir.mkdir()
        (prompts_dir / "valid.md").write_text(
            "---\nintent: debug\n---\nValid"
        )
        (prompts_dir / "invalid.md").write_text(
            "No frontmatter here"
        )

        templates = load_templates(tmp_path)

        assert len(templates) == 1

    def test_skips_non_md_files(self, tmp_path) -> None:
        prompts_dir = tmp_path / ".prompts"
        prompts_dir.mkdir()
        (prompts_dir / "template.md").write_text(
            "---\nintent: debug\n---\nValid"
        )
        (prompts_dir / "notes.txt").write_text("ignore me")

        templates = load_templates(tmp_path)

        assert len(templates) == 1


class TestMatchTemplate:
    def test_matches_intent_and_domain(self, tmp_path) -> None:
        prompts_dir = tmp_path / ".prompts"
        prompts_dir.mkdir()
        (prompts_dir / "python-debug.md").write_text(
            "---\nintent: debug\ndomain: python\n---\nPython debug"
        )
        (prompts_dir / "generic-debug.md").write_text(
            "---\nintent: debug\n---\nGeneric debug"
        )

        result = match_template(tmp_path, intent="debug", domain="python")

        assert result is not None
        assert result.domain == "python"

    def test_matches_intent_only(self, tmp_path) -> None:
        prompts_dir = tmp_path / ".prompts"
        prompts_dir.mkdir()
        (prompts_dir / "debug.md").write_text(
            "---\nintent: debug\n---\nDebug template"
        )

        result = match_template(tmp_path, intent="debug", domain="general")

        assert result is not None
        assert result.intent == "debug"

    def test_no_match_returns_none(self, tmp_path) -> None:
        prompts_dir = tmp_path / ".prompts"
        prompts_dir.mkdir()
        (prompts_dir / "debug.md").write_text(
            "---\nintent: debug\n---\nDebug template"
        )

        result = match_template(tmp_path, intent="writing", domain="general")

        assert result is None

    def test_both_fields_must_match_when_both_specified(self, tmp_path) -> None:
        prompts_dir = tmp_path / ".prompts"
        prompts_dir.mkdir()
        (prompts_dir / "python-debug.md").write_text(
            "---\nintent: debug\ndomain: python\n---\nPython debug"
        )

        result = match_template(tmp_path, intent="debug", domain="webdev")

        assert result is None

    def test_tie_broken_alphabetically(self, tmp_path) -> None:
        prompts_dir = tmp_path / ".prompts"
        prompts_dir.mkdir()
        (prompts_dir / "b-debug.md").write_text(
            "---\nintent: debug\n---\nB template"
        )
        (prompts_dir / "a-debug.md").write_text(
            "---\nintent: debug\n---\nA template"
        )

        result = match_template(tmp_path, intent="debug", domain="general")

        assert result is not None
        assert result.filename == "a-debug.md"

    def test_no_prompts_dir_returns_none(self, tmp_path) -> None:
        result = match_template(tmp_path, intent="debug", domain="general")
        assert result is None


class TestInjectVariables:
    def test_replaces_known_variables(self) -> None:
        body = "Stack: {{stack}} | Branch: {{branch}}"
        result = inject_variables(
            body,
            variables={"stack": "python, flask", "branch": "main"},
        )
        assert result == "Stack: python, flask | Branch: main"

    def test_unknown_variables_left_as_is(self) -> None:
        body = "Stack: {{stack}} | Unknown: {{foo}}"
        result = inject_variables(
            body,
            variables={"stack": "python"},
        )
        assert result == "Stack: python | Unknown: {{foo}}"

    def test_empty_variables(self) -> None:
        body = "No vars here"
        result = inject_variables(body, variables={})
        assert result == "No vars here"

    def test_multiple_same_variable(self) -> None:
        body = "{{stack}} and {{stack}}"
        result = inject_variables(body, variables={"stack": "python"})
        assert result == "python and python"

    def test_injected_value_is_not_re_expanded(self) -> None:
        """A value that looks like a placeholder is not re-expanded."""
        body = "{{a}} {{b}}"
        result = inject_variables(
            body, variables={"a": "{{b}}", "b": "X"}
        )
        assert result == "{{b}} X"
