"""TRF follow-up: deterministic parsing of the curated starter static blocks.

These parsers only ever see the exact fingerprinted entry bytes accepted by
``src.template_import``: unknown or edited layouts are rejected before parsing
is attempted. Every parser returns ``None`` on any shape surprise, and the
caller keeps the block as preserved raw LaTeX instead of guessing.
"""

import re

from .composition import (EducationEntry, EducationSection, ItemGroup,
                          ItemGroupsSection, SkillGroup, SkillsSection)

COMMENT_LINE = re.compile(r"^[ \t]*%[^\n]*$", re.MULTILINE)


def _strip_comments(text: str) -> str:
    return COMMENT_LINE.sub("", text)


def _braced(text: str, start: int) -> tuple[str, int] | None:
    """Read the brace group opening at ``start``; return (inner, end_index)."""
    if start >= len(text) or text[start] != "{":
        return None
    depth = 0
    for index in range(start, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1:index], index + 1
    return None


def _skip_ws(text: str, cursor: int) -> int:
    while cursor < len(text) and text[cursor] in " \t\n":
        cursor += 1
    return cursor


def _environments(text: str, name: str) -> list[tuple[str, int, int]] | None:
    """Split top-level ``\\begin{name}...\\end{name}`` blocks with positions."""
    blocks = []
    cursor = 0
    nested = re.compile(r"\\(begin|end)\{" + re.escape(name) + r"\}")
    while True:
        begin = text.find("\\begin{" + name + "}", cursor)
        if begin < 0:
            return blocks
        inner_start = begin + len(name) + len("\\begin{}")
        depth = 1
        probe = inner_start
        match = None
        while depth:
            match = nested.search(text, probe)
            if match is None:
                return None
            depth += 1 if match.group(1) == "begin" else -1
            probe = match.end()
        assert match is not None
        blocks.append((text[inner_start:match.start()], begin, match.end()))
        cursor = match.end()


def _single_rsection(text: str, title: str) -> tuple[str, str] | None:
    """The (title, body) of the single expected rSection, or None."""
    blocks = _environments(text, "rSection")
    if blocks is None or len(blocks) != 1:
        return None
    inner, begin, end = blocks[0]
    before = _strip_comments(text[:begin])
    # Section-preamble definitions (column types, helper commands, spacing)
    # carry no output of their own and stay behind in the raw fallback world;
    # structured rendering owns its spacing explicitly instead.
    before = re.sub(r"\\(newcolumntype|newcommand|renewcommand|vspace|hspace)[^\n]*", "", before)
    after = _strip_comments(text[end:]).strip()
    if before.strip() not in ("", r"\newpage") or after:
        return None
    marker = "\\begin{rSection}{" + title + "}"
    if not text[begin:].startswith(marker):
        return None
    body = _after_title(inner, title)
    return (title, body) if body is not None else None


def _after_title(inner: str, title: str) -> str | None:
    """Skip the ``{Title}`` argument that follows ``\\begin{rSection}``."""
    cursor = _skip_ws(inner, 0)
    parsed = _braced(inner, cursor)
    if parsed is None or _strip_once(parsed[0]) != title:
        # Fall back to the literal match when braces nest unexpectedly.
        literal = "{" + title + "}"
        if not inner.startswith(literal, cursor):
            return None
        return inner[cursor + len(literal):]
    return inner[parsed[1]:]


def _strip_once(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value.startswith("{") and value.endswith("}"):
        parsed = _braced(value, 0)
        if parsed is not None and parsed[1] == len(value):
            return parsed[0].strip()
    return value


def parse_education(text: str) -> EducationSection | None:
    """Parse the Education rSection body; None keeps the raw block."""
    page_break = r"\newpage" in text
    section = _single_rsection(text, "Education")
    if section is None:
        return None
    _, body = section
    blocks = _environments(body, "myrSubsectionEmpty2")
    if not blocks:
        return None
    entries = []
    for index, (block, _, _) in enumerate(blocks):
        groups = []
        cursor = 0
        while len(groups) < 3:
            cursor = _skip_ws(block, cursor)
            parsed = _braced(block, cursor) if cursor < len(block) else None
            if parsed is None:
                return None
            groups.append(parsed[0])
            cursor = parsed[1]
        if block[cursor:].strip():
            return None
        institution = _strip_once(groups[0])
        if institution.startswith(r"\bf"):
            institution = _strip_once(institution[len(r"\bf"):])
        if not institution:
            return None
        parts = [part.strip() for part in groups[2].split(r"\newline")]
        details = [part for part in (piece.strip() for piece in parts[1:]) if part]
        entries.append(EducationEntry(id=f"education-{index + 1}", institution=institution,
                                      dates=groups[1].strip(), degree=_strip_once(parts[0]),
                                      details=details))
    remainder = _strip_comments(body)
    for _, begin, end in blocks:
        remainder = remainder.replace(body[begin:end], "", 1)
    if re.sub(r"\\vspace\{[^}]*\}", "", remainder).strip():
        return None
    return EducationSection(kind="education", id="education", title="Education",
                            page_break_before=page_break, entries=entries)


def parse_skills(text: str) -> SkillsSection | None:
    """Parse the Technical Strengths tables; None keeps the raw block."""
    section = _single_rsection(text, "Technical Strengths")
    if section is None:
        return None
    _, body = section
    tables = _environments(body, "tabular")
    if not tables:
        return None
    groups: list[SkillGroup] = []
    counter = 0

    def split_row(row: str, cells: int) -> list[str] | None:
        parts = re.split(r"(?<!\\)&", row)
        return parts if len(parts) == cells else None

    for table, _, _ in tables:
        # Column spec ends at the first unbalanced closing brace.
        depth = 0
        spec_close = None
        for index, character in enumerate(table):
            if character == "{":
                depth += 1
            elif character == "}":
                depth -= 1
                if depth == 0:
                    spec_close = index
                    break
        if spec_close is None:
            return None
        rest = spec_close + 1
        # A trailing comment on the \begin{tabular} line (e.g. a dead column
        # alternative) is TeX whitespace; consume it with the spec.
        while rest < len(table) and table[rest] in " \t":
            rest += 1
        if rest < len(table) and table[rest] == "%":
            while rest < len(table) and table[rest] != "\n":
                rest += 1
        spec, rows_text = table[:spec_close + 1], table[rest:]
        rows = [row.strip() for row in re.split(r"(?<!\\)\\\\", rows_text)
                if row.strip() and row.strip() != r"\,"]
        if "@" in spec:
            for row in rows:
                cells = split_row(row, 3)
                name_match = re.search(r"\\bf\{([^}]*)\}", cells[0]) if cells else None
                dots = cells[2].split() if cells else []
                if not cells or not name_match or len(dots) != 6 or any(
                        dot not in (r"\bcirc", r"\wcirc") for dot in dots):
                    return None
                counter += 1
                groups.append(SkillGroup(id=f"skill-{counter}", name=name_match.group(1).strip(),
                                         items=cells[1].strip(), rating=dots.count(r"\bcirc")))
        else:
            for row in rows:
                cells = split_row(row, 2)
                if not cells:
                    return None
                name = _strip_once(cells[0])
                if name.startswith(r"\bf"):
                    name = _strip_once(name[len(r"\bf"):])
                if not name:
                    return None
                counter += 1
                groups.append(SkillGroup(id=f"skill-{counter}", name=name, items=cells[1].strip()))
    if not groups:
        return None
    remainder = _strip_comments(body)
    for _, begin, end in tables:
        remainder = remainder.replace(body[begin:end], "", 1)
    allowed = re.sub(r"\\(vspace|newline|newcolumntype|newcommand|ert)\b[^\n]*", "", remainder)
    if allowed.strip():
        return None
    return SkillsSection(kind="skills", id="skills", title="Technical Strengths", groups=groups)


def parse_item_groups(text: str, *, section_id: str, title: str) -> ItemGroupsSection | None:
    """Parse rSubsection title/item groups; None keeps the raw block."""
    section = _single_rsection(text, title)
    if section is None:
        return None
    _, body = section
    blocks = _environments(body, "rSubsection")
    if not blocks:
        return None
    groups = []
    for index, (block, _, _) in enumerate(blocks):
        cursor = 0
        args = []
        while len(args) < 4:
            cursor = _skip_ws(block, cursor)
            parsed = _braced(block, cursor) if cursor < len(block) else None
            if parsed is None:
                return None
            args.append(parsed[0])
            cursor = parsed[1]
        heading = _strip_once(args[0]).replace(r"\,\,\,", "").strip()
        if not heading:
            return None
        items = [item.strip() for item in re.split(r"\\item(?![a-zA-Z])", block[cursor:])
                 if item.strip()]
        groups.append(ItemGroup(id=f"{section_id}-group-{index + 1}", title=heading, items=items))
    remainder = _strip_comments(body)
    for _, begin, end in blocks:
        remainder = remainder.replace(body[begin:end], "", 1)
    if remainder.strip():
        return None
    return ItemGroupsSection(kind="item_groups", id=section_id, title=title, groups=groups)
