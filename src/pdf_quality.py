"""TRF-05: pure PDF layout-quality analysis; subprocesses are injected at the boundary.

Word boxes come from ``pdftotext -bbox`` XML (namespace tolerant). Overfull and
glyph warnings come from the XeLaTeX transcript. Nothing here touches the
network, the filesystem or a compiler: runners live in the service layer so
offline tests use fakes and only explicit opt-in checks invoke real tools.
"""

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

OVERFULL_RE = re.compile(
    r"Overfull \\([hv])box \(([\d.]+)pt too (?:wide|high)\)[^\n]*?(?:line|lines) (\d+)(?:--(\d+))?"
)
MISSING_CHARACTER_RE = re.compile(r"Missing character: .* in font .*?!")
FONT_WARNING_RE = re.compile(r"LaTeX Font Warning: ([^\n]*)")

MAX_ITEMS = 20


@dataclass(frozen=True)
class Overfull:
    kind: str  # 'hbox' | 'vbox'
    amount_pt: float
    start_line: int
    end_line: int
    excerpt: str


@dataclass(frozen=True)
class WordBox:
    page: int
    x_min: float
    x_max: float
    y_min: float
    y_max: float
    text: str


@dataclass(frozen=True)
class Overlap:
    page: int
    first: str
    second: str
    area: float


@dataclass(frozen=True)
class OutsideWord:
    page: int
    text: str
    edge: str
    amount_pt: float


@dataclass(frozen=True)
class QualityReport:
    input_id: str
    pages: int
    words: int
    overfulls: tuple = ()
    overfull_count: int = 0
    overlaps: tuple = ()
    outside_page: tuple = ()
    missing_glyphs: tuple = ()
    omitted: dict = field(default_factory=dict)


def parse_overfulls(transcript: str, limit: int = MAX_ITEMS) -> tuple[tuple[Overfull, ...], int]:
    """Extract bounded overfull warnings; the total count is preserved separately."""
    found = []
    for match in OVERFULL_RE.finditer(transcript):
        start = int(match.group(3))
        found.append(Overfull(kind=f"{match.group(1)}box", amount_pt=float(match.group(2)),
                              start_line=start, end_line=int(match.group(4) or start),
                              excerpt=match.group(0)[:160]))
    return tuple(found[:limit]), len(found)


def parse_missing_glyphs(transcript: str, limit: int = MAX_ITEMS) -> tuple[str, ...]:
    """Missing characters and font substitutions TeX reported instead of failing."""
    items = [match.group(0)[:160] for match in MISSING_CHARACTER_RE.finditer(transcript)]
    items += [f"LaTeX Font Warning: {match.group(1).strip()[:120]}" for match in FONT_WARNING_RE.finditer(transcript)]
    return tuple(items[:limit])


def parse_word_pages(xml_text: str) -> tuple[list[WordBox], list[tuple[float, float]]]:
    """Parse namespace-tolerant bbox XML into per-page word boxes and page sizes."""
    root = ET.fromstring(xml_text)
    pages: list[list[WordBox]] = []
    sizes: list[tuple[float, float]] = []
    for index, page in enumerate(root.findall(".//{*}page")):
        width, height = float(page.get("width", 0)), float(page.get("height", 0))
        sizes.append((width, height))
        words = []
        for word in page.findall("{*}word"):
            try:
                words.append(WordBox(page=index, x_min=float(word.get("xMin", 0)), x_max=float(word.get("xMax", 0)),
                                     y_min=float(word.get("yMin", 0)), y_max=float(word.get("yMax", 0)),
                                     text="".join(word.itertext())[:80]))
            except (TypeError, ValueError):
                continue
        pages.append(words)
    return pages, sizes


def find_overlaps(pages: list[list[WordBox]], *, min_overlap_pt: float = 1.0,
                  min_area_pt2: float = 4.0, limit: int = MAX_ITEMS) -> tuple[tuple[Overlap, ...], int]:
    """Word pairs whose boxes intersect well beyond touching/kerned neighbours."""
    spots: list[Overlap] = []
    total = 0
    for words in pages:
        for position in range(len(words)):
            first = words[position]
            for other in range(position + 1, len(words)):
                second = words[other]
                # Baselines far apart cannot overlap; skip cheaply before measuring.
                if second.y_min > first.y_max or first.y_min > second.y_max:
                    continue
                x_overlap = min(first.x_max, second.x_max) - max(first.x_min, second.x_min)
                y_overlap = min(first.y_max, second.y_max) - max(first.y_min, second.y_min)
                if x_overlap > min_overlap_pt and y_overlap > min_overlap_pt and x_overlap * y_overlap > min_area_pt2:
                    total += 1
                    if len(spots) < limit:
                        spots.append(Overlap(page=first.page, first=first.text[:40], second=second.text[:40],
                                             area=round(x_overlap * y_overlap, 1)))
    return tuple(spots), total


def find_outside_page(pages: list[list[WordBox]], sizes: list[tuple[float, float]], *,
                      tolerance_pt: float = 0.5, limit: int = MAX_ITEMS) -> tuple[tuple[OutsideWord, ...], int]:
    """Words escaping the physical page box; margin overflows are overfulls, not this."""
    spots: list[OutsideWord] = []
    total = 0
    for words, (width, height) in zip(pages, sizes):
        for word in words:
            for edge, amount in (("left", -word.x_min), ("right", word.x_max - width),
                                 ("top", -word.y_min), ("bottom", word.y_max - height)):
                if amount > tolerance_pt:
                    total += 1
                    if len(spots) < limit:
                        spots.append(OutsideWord(page=word.page, text=word.text[:40],
                                                 edge=edge, amount_pt=round(amount, 1)))
    return tuple(spots), total


def build_report(input_id: str, transcript: str, bbox_xml: str) -> QualityReport:
    """Assemble one bounded report from a transcript and bbox XML document."""
    overfulls, overfull_count = parse_overfulls(transcript)
    pages, sizes = parse_word_pages(bbox_xml)
    overlaps, _overlap_count = find_overlaps(pages)
    outside, _outside_count = find_outside_page(pages, sizes)
    words = sum(len(page) for page in pages)
    omitted = {}
    if overfull_count > len(overfulls):
        omitted["overfulls"] = overfull_count - len(overfulls)
    return QualityReport(input_id=input_id, pages=len(pages), words=words, overfulls=overfulls,
                         overfull_count=overfull_count, overlaps=overlaps, outside_page=outside,
                         missing_glyphs=parse_missing_glyphs(transcript), omitted=omitted)
