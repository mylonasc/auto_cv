"""TRF follow-up: deterministic static parsing with raw fallback, never guessing."""

import pytest

from src.static_parse import parse_education, parse_item_groups, parse_skills

EDUCATION = """\\newpage
\\begin{rSection}{Education}
  \\begin{myrSubsectionEmpty2}{{\\bf Example Uni}}{2020 -- 2024}{Ph.D. in \\textsc{Field}
    \\newline
    Advisor: Prof. X}
  \\end{myrSubsectionEmpty2}
  \\vspace{-0.65cm}

  \\begin{myrSubsectionEmpty2}{{\\bf Other Uni}}{2016 -- 2020}{B.Sc.}
  \\end{myrSubsectionEmpty2}

\\end{rSection}
"""

SKILLS = """\\begin{rSection}{Technical Strengths}
  \\begin{tabular}{p{0.2\\linewidth}  p{0.24\\linewidth}  @{\\hspace{4ex}} p{0.50\\linewidth}}
  \\bf{Programming}&  Python & \\bcirc \\bcirc \\bcirc \\bcirc \\bcirc \\bcirc \\\\
  \\end{tabular}
\\newline
\\newline
  \\begin{tabular}{p{0.2\\linewidth}  p{0.76\\linewidth} }
     {\\bf Deep Learning } & Models \\\\
      \\,
   \\end{tabular}
  \\vspace{-10.0pt}

\\end{rSection}
"""

GROUPS = """\\begin{rSection}{Other Information}
  \\begin{rSubsection}{{\\,\\,\\,Teaching}}{}{}{}
    \\item First role.
    \\item Second role.
  \\end{rSubsection}

  \\begin{rSubsection}{Plain}{extra}{args}{here}
    \\item Solo.
  \\end{rSubsection}

\\end{rSection}
"""


def test_education_parses_entries_details_and_page_break():
    section = parse_education(EDUCATION)
    assert section is not None and section.page_break_before is True
    assert [(entry.institution, entry.dates) for entry in section.entries] == [
        ('Example Uni', '2020 -- 2024'), ('Other Uni', '2016 -- 2020')]
    assert section.entries[0].degree == 'Ph.D. in \\textsc{Field}'
    assert section.entries[0].details == ['Advisor: Prof. X']
    assert section.entries[1].degree == 'B.Sc.' and section.entries[1].details == []


def test_education_falls_back_on_shape_surprises():
    assert parse_education('no environments here') is None
    assert parse_education(EDUCATION.replace('{2020 -- 2024}', '')) is None
    assert parse_education(EDUCATION.replace('\\end{myrSubsectionEmpty2}', '', 1)) is None
    assert parse_education(EDUCATION + '\\begin{rSection}{Extra}\\end{rSection}') is None


def test_skills_parses_rated_and_plain_groups():
    section = parse_skills(SKILLS)
    assert section is not None
    assert [(group.name, group.rating) for group in section.groups] == [
        ('Programming', 6), ('Deep Learning', None)]
    assert section.groups[0].items == 'Python'


def test_skills_falls_back_on_bad_dots_or_tables():
    assert parse_skills('nothing tabular here') is None
    assert parse_skills(SKILLS.replace('\\bcirc \\bcirc \\bcirc \\bcirc \\bcirc \\bcirc',
                                      '\\bcirc \\bcirc')) is None
    assert parse_skills(SKILLS.replace('p{0.50\\linewidth}', 'p{0.50\\linewidth')) is None


def test_item_groups_parse_titles_and_items_with_plain_fallback():
    section = parse_item_groups(GROUPS, section_id='other', title='Other Information')
    assert section is not None and section.id == 'other'
    assert [(group.title, len(group.items)) for group in section.groups] == [
        ('Teaching', 2), ('Plain', 1)]
    assert section.groups[0].items == ['First role.', 'Second role.']
    assert parse_item_groups('no groups', section_id='other', title='Other Information') is None
    assert parse_item_groups(GROUPS, section_id='other', title='Wrong Title') is None
    broken = GROUPS.replace('\\end{rSubsection}', '', 1)
    assert parse_item_groups(broken, section_id='other', title='Other Information') is None
