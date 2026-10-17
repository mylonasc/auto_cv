# Analysis, selection and rendering (RFK-04)

`src/analysis.py` defines frozen assessments, bullets, roles and snapshots.
Snapshots serialize as ordinary JSON with string IDs, not dictionaries keyed by
Python objects. A new source-document instance receives unique role/bullet IDs;
those IDs persist through its analysis, copies, document JSON and working copy.
Rebuilding a different source document starts a new analysis identity. Legacy
working copies without IDs receive deterministic job/position-derived IDs on
read without rewriting their source files.

## Ownership

- The canonical CV is source content (`src/domain.py`), not a scored/editable result.
- `CVCrossAnalyzer.source_cv` is a private copy used as analysis input.
- `AnalysisSnapshot` retains **all** source bullets and optional assessments.
  Missing assessments remain explicit; RFK-07 owns complete partial/failure policy.
- Selection is a set of bullet IDs. Selecting content builds a new document and
  never changes source text, comments or the snapshot. Equal scores preserve
  source-order ties; selected output retains source order. Duplicate IDs fail.
- Job results and working copies retain deselected bullets with `kept=false`.
  Older jobs already persisted after destructive filtering cannot recover lost
  bullets from that result; rerun analysis from the original CV when needed.
- `scored_text` records the exact text used for a working-copy score. Editing text
  makes that score stale until rescored. Historical scores without provenance
  remain visible but are treated as stale, not guessed fresh. Automatic filtering
  ignores their score; explicit manual selection remains available.

## Metrics and rendering

Selection and metrics are pure functions. Metrics describe original role scores,
weighted by selected plain content; they do not claim an LLM has rescored edited
text. Empty/unscored selections produce null metrics, not NaN or fabricated zero.
Analysis metadata and PDF comments never affect weights or model prompts.

Rendering receives explicit selection/content/template and comment options.
`render_document(include_scoring_comments=True)` constructs a rendering copy with
source-score annotations. `make_latex`/`render_pdf` also require an explicit
`include_scoring_comments=True` to emit them. Plain-text annotations are escaped
for LaTeX separately from source CV content, which may intentionally contain TeX.
Stale bullet scores are never emitted as current annotations.

`copy()` is now an ordinary deep content copy: IDs, comments and parent links are
preserved, and template metadata is independent. Copying is no longer a hidden
instruction to remove scoring comments. CLI artifact names now distinguish
original source, selected annotated output and selected unannotated output.

Working-copy selection in the browser is a pure function in
`src/domain/selection.ts`. Frontend unit tests cover identity/order preservation,
stale scores, invalid limits and non-mutation. Backend tests cover snapshot
immutability/serialization, policy boundaries, metrics, legacy IDs, rendering
options, rescoring provenance, and retention of deselected content end to end.
