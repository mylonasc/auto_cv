# Template and rendering boundaries (RFK-04/RFK-09/RFK-10 follow-up)

## Responsibilities

`CVData` owns editable statements/experience and portable template references.
Analysis operates without opening templates, including when artifacts are disabled.
`FullCVDocument` is a selected-content adapter, not another CV store.

`src.template_registry` adapts legacy registry entries and resolves explicit
choices. `src.latex_templates` owns validated, one-pass expansion and captures
template/fragment/resource bytes. `src.rendering` compiles those captured inputs
in scratch space. `src.artifacts` expands once and uses that exact LaTeX for PDF
and source output. HTTP and CLI use the same implementations.

No Python document class contains resume-class environments or pagination rules.
The historical `get_latex()` methods delegate to the legacy layout fragments.

## Registering a CV template

`config/templates.json` accepts definitions like:

```json
{
  "cv_templates": {
    "example": {
      "path": "assets/example/main.tex",
      "layout": {
        "section": "assets/example/section.tex",
        "role": "assets/example/role.tex",
        "bullet": "assets/example/bullet.tex",
        "comment": "assets/example/comment.tex"
      },
      "resources": {
        "example.cls": "assets/example/example.cls",
        "images/logo.png": "assets/example/logo.png"
      }
    }
  },
  "motivation_letter_templates": {}
}
```

Source paths are checkout-relative (or explicit absolute paths). Resource keys are
normalized relative **destination filenames in compilation scratch**. Parent
traversal, absolute destinations and compiler input/output collisions are rejected.
Subdirectories are materialized explicitly; the compiler runs with scratch as CWD.
There is no hard-coded class/image copying in the compiler. System-installed TeX
packages/fonts remain environment dependencies, not captured resources.

Templates use these named placeholders:

| File | Required placeholders |
| --- | --- |
| CV entry | `<statement>`, `<experience_section>` |
| Section | `<title>`, `<roles>` |
| Role | `<company>`, `<duration>`, `<position>`, `<comment>`, `<bullets>` |
| Bullet | `<text>`, `<comment>` |
| Comment | `<text>` |
| Education list / entry | `<entries>` / `<institution>`, `<dates>`, `<degree>`, `<details>` |
| Skills wrapper / rated table / rated row / plain table | `<content>` / `<rows>` / `<name>`, `<items>`, `<dots>` / `<name>`, `<items>` |
| Item-groups list / group | `<entries>` / `<title>`, `<items>` |
| Cover-letter entry | `<DATETODAY>`, `<COMPANYNAME>`, `<LETTERCONTENT>`, `<NAME>`, `<PROF_SIGNATURE>` |

All declared placeholders must occur; repeated occurrences are allowed. Unknown
angle-word placeholders fail rather than printing unfinished markup. Substitution
is one pass: placeholder-looking text inside authored CV content is never expanded
again. A different class/layout supplies different fragments; it does not require
editing Python. Pagination belongs entirely to the entry/fragments. The duplicate
Python-inserted page break after experience has been removed; existing entry files
still own their education page break. Visual page layout needs real TeX review.

The public `/v1/cv-data/templates` endpoint retains the ID-to-path catalog shape,
now backed by a declared/generated response type. Internal definitions/resources
are not duplicated into the frontend.
CLI LaTeX exports materialize the same captured resources next to their source
files; they no longer copy hard-coded résumé classes or an unrelated image.
Conflicting resource destinations fail instead of overwriting different content.

## Template file anatomy (what to edit, what to keep stable)

The shipped starters are intentionally explicit rather than DRY: two small
entry files plus one shared class override. Live content is ~140 lines per
starter; dead commented-out alternatives were removed, and render equivalence
(word boxes, page/word counts, overfull profile) is verified before/after any
template cleanup. File ownership:

| File | Owns | Editing rules |
| --- | --- | --- |
| `assets/latex_cv_template_v0.tex` (Classic) | Preamble, header data, section order, static sections, page breaks | Keep the marked import comments, `name`/document/section markers and placeholders; update `BUILTINS` hash after any byte change |
| `assets/latex_cv_template_v2.tex` (Wide) | Same, with `resume_v2` class | Same; differs from Classic only by document class + header spacing |
| `assets/resume.cls` | Header layout, `rSection`, `rSubsection`, `myrSubsection`, `myrSubsectionEmpty2` environments | Snapshotted into managed packages on import; legacy renders read the live file. Unused environments stay out |
| `assets/resume_v2.cls` | Wide work-experience override only | Loads `resume`; keep overrides minimal and commented |
| `assets/templates/resume/*.tex` | Legacy rendering fragments (`role`, `bullet`, `section`, `comment`) | Must keep the documented placeholders; changing them changes legacy output for old jobs |
| `assets/images/my_pic.jpeg` | Header photo resource | Captured as a package asset; do not rename without updating both registry resources |

The curated Studio importer (`src/template_import.py`) depends on exact marker
strings, not on line numbers: the strengths banner pair, the vspace comment
before Other Information, the About/document/experience markers and the closing
`end{document}`. These are flagged with `NOTE: ... import markers` comments in
the entry files. Any byte change to an entry file changes its SHA-256 and must
update `BUILTINS` in the same commit, with the render-equivalence check
(`docs/TEMPLATE_STUDIO.md` visual section) re-run. Managed revisions already
saved keep working unchanged: they snapshot their own bytes and never re-read
the checkout.

## Reference precedence and compatibility

- Initial outputs use the saved source-CV reference.
- Re-render requests without a template override inherit the immutable job source
  snapshot's reference (historical jobs without one use the default).
- An explicit ID replaces the saved ID **and clears its old path**. An explicit
  path takes precedence over the selected ID. CLI uses the same override rules.
- Unknown IDs and missing entry files fail explicitly; registry order is never a
  fallback policy. Template-authoring errors return actionable HTTP 422 errors.
- Registry selections in the source editor store an ID with a null path, not a
  duplicated registry path. Custom paths remain supported and visible.
- Render overrides live in the application workflow, keyed by job, and survive
  tab/job switching. The empty selection means “use saved template.”

Existing string registry entries and unregistered custom `.tex` paths explicitly
adapt to the legacy resume layout/resources. To use a different contract, register
a definition or place a `<template.tex>.json` sidecar containing `layout` and
`resources` alongside an explicit custom path. Its entry `path` is taken from the
explicit reference; its source paths still follow the checkout-relative rule.
When several registered definitions share an entry file, the matching ID selects
their layout/resources; an ambiguous path with no matching ID fails.

No source CV, working copy, registry backup or artifact is automatically migrated
or deleted. Existing artifacts remain downloadable. Invalid persisted working
copies now fail validation rather than having scores clamped or IDs silently
reassigned; preserve the file and resolve the reported field explicitly.

## Text format

CV schema v1 and working copies have an additive `content_format` field:

- `latex` (default for missing/legacy fields): retain authored LaTeX unchanged.
- `plain_text`: escape statements, experience metadata/bullets and the experience
  heading exactly once at the rendering boundary.

Analysis comments are always plain text and independently escaped. Format follows
the source through analysis, working copies, copies, render/submission snapshots
and frontend mappings. The editor exposes the choice, but switching it **does not
convert existing text**. The default intentionally does not reinterpret or escape
existing authored CVs. New data fields should explicitly define their text policy.
Older clients with closed schemas need regenerated types for this additive field.

## Provenance and publication

New render records retain a manifest with the requested template ID, effective
entry path, SHA-256 hashes of entry/fragments/resources, destination-resource
hashes, expanded-LaTeX hash, content format, comment and output/source options.
Resources are captured before compilation, so changing their files while a render
runs cannot change that operation's inputs. PDF and optional `.tex` output use one
expansion. Publication failure does not append artifacts; fresh files from a
failed multi-output operation are removed without sweeping historical outputs.

This is **fingerprinted provenance, not a complete archival bundle**. If source
output was disabled, the record does not contain expanded LaTeX, and historical
resource/template bytes are not archived. Existing PDFs remain the authoritative
visual artifact; fonts, TeX environment, and system packages are not fingerprinted.

## Structured sections and remaining raw content

Education, Technical Strengths and Other Information import as structured,
editable `education`/`skills`/`item_groups` sections rendered through
template-owned fragments (`docs/TEMPLATE_STUDIO.md` has the field contracts).
The curated import parses only the exact fingerprinted starter bytes and keeps
any unrecognized block as preserved raw LaTeX instead of guessing; older saved
revisions stay readable and render their existing sections unchanged. Reads
never migrate raw sections to structured ones.

Selected Publications stay raw by design (no bibliography parsing); author new
structured `publications` rows or hide the raw block without deleting it. The
contact header stays raw `header_latex`. Canonicalizing contact fields remains
a separate content-schema follow-up in technical debt #16, not a waived
criterion: do not create parallel writable copies under `candidate.profile` or
introduce a generic section framework.

## Verification and trust boundary

`tests/test_templates.py` exercises unknown/missing inputs, custom layouts,
one-pass expansion, escaping, resources, render inheritance, manifests and strict
working-copy validation through production code. The compiler adapter is tested
with a fake process; default tests do not run TeX or providers. Frontend unit and
API-isolated browser tests cover selection persistence, JSON-schema validation,
nullable scores and unsaved source-navigation protection.

Use the opt-in smoke instructions in `tests/README.md` for real XeLaTeX/provider
checks. This remains a trusted local application: resource checks are correctness
guards, **not a sandbox for untrusted LaTeX**. Deployment security remains #16.

Verified on the working tree:

| Command | Result |
| --- | --- |
| `.venv/bin/python -m pytest -q` | 219 passed |
| `npm run test:unit` (active frontend) | 29 passed, including TypeScript checking |
| `npm run test:cv` (active frontend) | 19 API-isolated Chromium checks passed |
| `npm run build` / `npm run lint` (active frontend) | passed |
| `.venv/bin/python -B -m tools.generate_api_types --check` | passed |
| `git diff --check` | passed |

An independent backend-suite run with an externally configured data root preserved
five external store sentinels and the inventory/SHA-256 hashes of 815 existing
data/assets/legacy files. Real providers, XeLaTeX visual output and Docker image
execution were not exercised; fake PDFs are not rendering-quality evidence.
