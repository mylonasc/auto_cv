# Template Studio — TRF / RFK follow-up

Parent: [#17](https://github.com/mylonasc/auto_cv/issues/17), label
`template-refactoring`. Target: five developer-days, one experienced developer.
Use `enhancement/epic-refactor`; preserve the existing uncommitted refactor work
and all source/runtime/legacy data.

## Indexed delivery

| Slice | Issue | Goal | Native blocked by |
| --- | --- | --- | --- |
| TRF-01 / RFK-04 | [#18](https://github.com/mylonasc/auto_cv/issues/18) | Composition, managed revisions, recoverable import | None |
| TRF-02 / RFK-04 | [#19](https://github.com/mylonasc/auto_cv/issues/19) | Composed rendering; API/CLI/working-copy integration | #18 |
| TRF-03 / RFK-09 | [#20](https://github.com/mylonasc/auto_cv/issues/20) | Studio UI, content/file editing and authoring APIs | #18, #19 |
| TRF-04 / RFK-07 | [#21](https://github.com/mylonasc/auto_cv/issues/21) | Independent unsaved-draft PDF preview and diagnostics | #19, #20 |
| TRF-05 / RFK-10 | [#22](https://github.com/mylonasc/auto_cv/issues/22) | Integration, compatibility and verification | #21 |

The GitHub bodies contain full acceptance checklists. No issue is complete merely
because its design/types exist. Close only with verified implementation commits.

TRF-01–TRF-04 are implemented on the epic branch: foundation `043978d`, composed
rendering `5595564`, authoring `e1ee1a7`, and preview (verification below).
TRF-05 final epic-wide acceptance remains open; no slice is complete merely
because its design/types exist.

## Try the live preview

With the current backend/frontend running, open **Template Studio**:

1. Select the source CV, choose an unused template ID for a legacy import, and
   click **Load / import draft**. Existing composed CVs load their pinned revision.
2. Edit statement/experience, header, raw sections or any captured template file.
   **Add entries** adds a personal-project section; **Add publications** adds a
   structured publication list. Original publications remain a preserved raw block
   whose **Include section** checkbox can hide it without deletion.
3. Click **Preview PDF**. Neither save is required. The PDF appears beside the
   editors. Further edits mark it outdated; compile errors retain the last PDF.
4. To persist: **Save template revision**, then choose a new CV version ID and
   **Save new CV version**. Select that new CV in Job Description explicitly.

Manual startup, in separate terminals from the checkout root:

```bash
.venv/bin/python -m uvicorn server_application.backend.main:app --host 127.0.0.1 --port 8005
```

```bash
npm --prefix frontend/auto-cv-customizer run dev -- --host 127.0.0.1
```

Open the Vite URL printed by the second command (normally http://127.0.0.1:5173).
XeLaTeX and the existing templates' TeX packages/fonts must be installed on the
backend host; no LLM/provider is needed for Studio. For Docker, rebuild/restart the
backend/frontend using the existing deployment setup so its bundled UI is current.
Docker execution has not been verified for this slice. Starting the normal app
uses normal storage; the implementation's smoke tests used temporary storage only.

## Approved scope and ownership

Template Studio will be a feature in the existing React/FastAPI application, not
a separate service. CV versions own content, section order/inclusion and page
breaks; template revisions own LaTeX files/resources. Distinct CV/template saves;
preview accepts unsaved drafts and does not create normal jobs or submissions.

The workspace will offer section controls (up/down, visibility, duplication,
deletion), structured project/publication lists, existing statement/experience
editing, raw LaTeX blocks/header, text-source file editing and inline PDF preview.
Drafts must survive conditional tab lifetimes or require explicit discard; stale
responses cannot overwrite newer edits or imply that an old PDF is current.

One-week scope deliberately excludes WYSIWYG/arbitrary LaTeX parsing, collaboration,
public deployment/authentication, additional model scoring, bibliography/DOI import,
general asset uploads, a database and a new state/orchestration framework. Raw
LaTeX is the initial editor for less-common legacy sections.

## TRF-01 contracts implemented in the working tree

### CV composition

`src.composition.DocumentComposition` is an optional additive `CVData.document`
field (CV schema v1, composition format v1). Missing/null means the unchanged
legacy representation. `candidate` remains metadata-only.

Every section has `id`, `kind`, `title`, `enabled` and `page_break_before`:

- `statement`, `experience`: bind the existing top-level content; extra embedded
  content is forbidden. At most one of each binding exists, including disabled
  bindings. Omitting/disabling a binding does not delete the source content.
- `entries`: identified projects with name, description, technologies, URL,
  bullets and inclusion flag. New structured content is plain text.
- `publications`: identified author/title/venue/year/URL entries and inclusion
  flags. No invented scoring or bibliography parsing.
- `latex`: complete authored LaTeX. `title` is its outline/editor label; the
  printed heading and existing page breaks remain in its raw source.

`header_latex` preserves the original authored header. IDs are unique across all
sections and their entries; counts and payload sizes are bounded. Raw content is
not escaped or silently converted. Imported raw blocks retain comments and old
formatting as valuable content, including the complete publications block.

Composition and `cv_template.revision` must be supplied together. A managed
reference uses a slug `template_id`, a 64-character SHA-256 revision and a null
`template_path`. The old `experience_section_title` field remains a legacy-only
setting; the composed experience binding owns its title. Reads do not migrate
files; explicit CV saves still retain byte-exact backups via `src.cv_storage`.

### Managed packages and revision storage

`src.template_package.TemplatePackage` owns editable `.tex/.cls/.sty` strings,
named fragment paths and separately encoded binary snapshots. There are no live
external file references. The shell binds `<header>` and `<sections>` exactly
once. Required fragment placeholders are checked without invoking TeX.

The SHA-256 revision covers the complete package value, including its manifest,
source/asset bytes and import provenance. Limits are 64 text files (256 KiB each,
2 MiB total), 32 binary assets (2 MiB each, 8 MiB total), normalized contained
logical names and no file/directory or text/binary collisions.

`src.template_storage.ManagedTemplateRepository(directory)` takes an injected
path; construction, listing an absent store and reads do not create directories.
An explicit save creates:

```text
<directory>/<template_id>/
  .write.lock
  head.json
  revisions/<sha256>.json
```

`save(package, expected_revision=...)` is a compare-and-save operation. `None`
means create-only, not unconditional overwrite. A local filesystem advisory lock
serializes cooperating repository instances; this implementation targets Linux
local storage, not distributed writers/filesystems. Existing revisions are never
rewritten. The complete immutable revision is atomically written first and HEAD
atomically replaced last. If HEAD publication fails, the old HEAD/history survives
and the new orphan revision can be published by retrying the same save. No cleanup
sweeps or revision deletion are performed. Corrupt identities/digests and symlinks
below the injected root fail explicitly instead of being normalized away.

### Explicit built-in import

`src.template_import.import_builtin_template(cv, root=..., new_template_id=...,
name=...)` is a read-only operation returning an `ImportedTemplate` draft:

- Accept only the known entry-file fingerprints for `default_cv` and `template2`.
  Customized/unknown entry layouts and custom explicit paths require a reviewed
  converter; there is no best-effort parser that could lose user content.
- Move the original header and entire static tail into canonical composition.
  Keep existing statements/experience in their original fields. Preserve original
  metadata, alternatives, comments, static sections and publications.
- Build a new shell/fragments without competing factual copies. Snapshot all
  declared layout/class/resource bytes; reject missing required classes, path
  escapes and file collisions. Mutable source class edits are captured, not linked.
- Return independent values with the predicted revision reference. Do not create
  a repository, save a CV, rewrite a registry or touch originals.

The TRF-03 operation saves the package before explicitly creating a new
CV version; it must not overwrite the selected original. Importing publications
as raw LaTeX is intentional preservation, not a claim that bibliography entries
have been semantically parsed. Structured publication entries can be authored
without guessing the original markup.

### Starter templates

Both shipped starters are curated imports and first-class Studio choices:

- `default_cv` (Classic): narrow work-experience rows; bullets start about a
  third of the way across the page inside a two-column role table.
- `template2` (Wide, default in the Studio picker): full-width bullets starting
  at the left margin via the `resume_v2` class override; otherwise the same
  header, sections and static tail.

The Studio **Starter template** dropdown lists every registered `cv_templates`
entry and sends it as `source_template` on `POST /v1/template-studio/import`.
It applies only to legacy CVs; a composed CV already owns its package and must
be cloned instead. Unknown starters and composed-plus-starter requests fail
explicitly. The wide starter's first-bullet position left of the classic one is
locked by an opt-in visual regression (`visual_tests/`).

### Isolated rendering and layout-quality review

All unsaved-draft production flows through `src/render_pipeline.render_draft`
(validate pair, prepare exact-revision LaTeX, bounded compile, input identity).
Studio preview and ordinary job rendering delegate to it instead of composing
compiler calls themselves. `src/pdf_quality` is pure analysis over a transcript
and `pdftotext -bbox` XML: overfull warnings with line/amount, missing glyphs
and font substitutions, word-box overlaps and words outside the physical page.
Subprocess runners are injected at the service boundary, so offline tests use
fakes and only explicit opt-in checks invoke real tools.

`POST /v1/template-studio/preview-report` accepts the same draft as preview
and returns a bounded `StudioPreviewReport` (page/word counts plus capped
overfull/overlap/outside-page/glyph lists with omission counts). It shares the
single compile slot with preview, persists nothing and returns 501 when
`pdftotext` is unavailable (the backend image now installs `poppler-utils`).
The Studio **Check layout quality** button calls it for the current unsaved
draft, marks results outdated on further edits, and never replaces the PDF.

Known findings from real compiles (detection first; fixes are follow-ups, not
silent redesigns): both starters compile successfully with zero word overlaps
and zero words outside the page, but report header `vbox`/`hbox` overfulls and
a ~55pt `hbox` overfull where the Technical Strengths dot row runs into the
right margin (visible on the page PNGs). The classic starter additionally
substitutes the unavailable small-caps bold font. Evidence: `visual_tests/`
JSON reports and page PNGs plus `render-visual.spec.ts` PDF attachments.

Opt-in commands (synthetic CVs and temporary storage only; never part of the
default suite):

```bash
datastore=$(mktemp -d /tmp/opencode/auto_cv_visual.XXXXXX)
AUTO_CV_DATA_ROOT="$datastore" .venv/bin/python -m pytest -q visual_tests/
```

```bash
datastore=$(mktemp -d /tmp/opencode/auto_cv_visual_backend.XXXXXX)
AUTO_CV_DATA_ROOT="$datastore" .venv/bin/python -m uvicorn \
  server_application.backend.main:app --host 127.0.0.1 --port 8005
# then, from frontend/auto-cv-customizer:
npm run test:visual
```

### Generated boundaries and interim limitations

Frontend types include composition/packages/revisions. The JSON editor's generated
schema handles literal-kind discriminators and nested defaults through an explicit
Pydantic/OpenAPI-to-Ajv adapter; actual oneOf/const/ref constraints remain intact.
Cross-field invariants such as global ID uniqueness and paired references remain
authoritatively validated by backend models on save.

TRF-01 alone was foundation work, not a usable Studio UI. TRF-02 now carries
composition and the injected `TemplateCatalog` through document copies, analysis
selection, initial HTTP output, working-copy re-render, CLI/telemetry and immutable
render/submission snapshots. Managed rendering always loads the exact revision,
never mutable HEAD. Missing packages, unpinned composition and incompatible legacy
overrides fail rather than dropping sections. Projects/publications are rendered
but not newly scored. TRF-03 owns workspace/controllers; TRF-04 owns preview.

### TRF-03 authoring workspace

The Template Studio tab now owns its drafts in a provider above conditional tabs.
Load/import is explicit: the curated converter produces unsaved copies, while an
existing composed version loads its exact package revision. All captured text
files, raw header/sections, statement/experience and structured lists are editable.
Section/entry duplication creates fresh IDs; binding duplication is prohibited.
Ordering, visibility and page breaks are canonical CV edits, not template edits.

Save template revision is optimistic compare-and-save. Conflicts keep local edits;
Reload latest saved template explicitly discards only the template draft (with
confirmation) and pins the retained CV draft to that revision. Save new CV version
is a separate create-only operation after the package is saved; Studio never
overwrites master/selected originals or automatically activates a version. A new
version ID is required for each CV save. Delayed responses advance captured
baselines without overwriting newer edits. Full reload warns before losing drafts.

Authoring endpoints live under `/v1/template-studio`: `POST /import`,
`GET /packages`, `GET /packages/{id}?revision=...`, `POST /packages`.
They share generated contracts; callers cannot supply arbitrary filesystem paths.
TRF-03 verification: backend **263 passed**, frontend unit **32 passed**, isolated
Chromium **21 passed**, frontend build/lint and diff checks passed. Preview is
not included in these checks; it remains TRF-04.

### TRF-04 job-independent PDF preview

`POST /v1/template-studio/preview` accepts generated `StudioPreviewRequest`
CV/package drafts, validates both, binds the draft package hash in an independent
CV copy, and invokes the same composed renderer/compiler as saved output. It does
not resolve mutable HEAD, save revisions/CVs, call models or create jobs,
submissions, render records or artifacts. Success is `application/pdf`, `no-store`,
with `X-Preview-Input` identifying the effective input. Compile failures return
JSON detail plus bounded file/line diagnostics; invalid schemas return normal
validation errors. `temp.tex` means the assembled CV, not a writable template file.

One compile per application process is accepted; concurrent previews return 429
with Retry-After. Compilation runs off the event loop and owns its capacity until
the worker actually finishes, even after request cancellation. Preview wall timeout
is 30 seconds (ordinary jobs retain 120); a single-threaded child sets CPU/file
limits before exec, avoiding preexec_fn in a threaded server. Shell escape is
disabled, TeX paranoid file-open settings are enabled, output/transcript files are
capped at 16 MiB each, and only an 8 KiB diagnostic tail is returned. Captured
resources and temporary compiler files are removed with owned scratch lifetimes.
Ordinary job/provider error messages remain sanitized.

The provider owns requests and last-successful PDF across tabs. Edits during a
request reject its late result; later edits mark an older PDF outdated. Failed
compiles preserve the last successful PDF. The reusable PDF frame uses object URLs
revoked on replacement/provider unmount, and blob-mode HTTP errors are decoded as
bounded JSON rather than hiding the compile diagnostics.

Real browser compilation caught empty project/role list environments. Newly
imported project fragments and the shared default role fragment now guard empty
bullet lists. Existing immutable packages are not rewritten; their source remains
editable. Nonempty list appearance is unchanged; empty roles retain their headings.

**Trust boundary:** these are trusted-local authoring controls, not a sandbox for
hostile TeX. No authentication/container isolation/filesystem quota is added. TeX
can still access host-installed packages/fonts and consume resources within the
process limits. Timed-out/failed compilers have their owned process group killed
and reaped, including PDF/font helpers. Disabling shell escape/restricting file opens also applies to
ordinary rendering; custom templates relying on external commands/absolute reads
must be adapted explicitly, not enabled through a preview escape hatch.

TRF-04 verification:

- `.venv/bin/python -m pytest -q`: **280 passed**, including temporary storage,
  unsaved input identity, bounded diagnostics, validation, 429/cancellation capacity,
  compile failure/timeout/missing/empty/invalid/oversize output and scratch cleanup.
- `npm run test:unit`: **33 passed**; `npm run test:cv`: **22 API-isolated Chromium
  checks passed**, including stale preview rejection, tab persistence, old-PDF
  retention, object URL replacement/revocation and JSON blob error decoding.
- Frontend build/full lint, generated-schema drift and diff checks passed.
- Real HTTP/XeLaTeX compilation passed for both built-in imports, including an
  empty role (132165 and 117670 PDF bytes in the final smoke). Real Chromium edits
  compiled a 133176-byte unsaved project/statement PDF, displayed the iframe, then
  displayed deliberate TeX diagnostics while preserving the old PDF. Model creation
  was forbidden; zero external browser requests. The temporary seed store remained
  byte-identical and owned smoke servers were stopped. This is functional smoke
  evidence, not pixel-perfect visual acceptance or Docker verification.
- Independent sandboxed rerun preserved five external sentinels and all **713**
  inventoried data/assets/legacy file hashes (excluding dependency/bytecode trees).
  No real user CV, template package or artifact was saved/migrated.

Both shipped classes require `my_pic.jpeg`; the registry now declares the existing
image as a captured dependency. No original asset was changed. Both imported styles
passed real XeLaTeX compilation with synthetic statement/experience in scratch
space (no model calls or normal runtime writes). This is compilation evidence,
not a claim of pixel-perfect visual review.

## Verification

`tests/test_template_studio_foundation.py` uses real schemas, CV storage/API,
curated imports and repository operations with temporary storage. Coverage includes
duplicate/invalid bindings and IDs, complete static/header preservation for both
built-ins, revision identity, concurrent compare-and-save conflicts, HEAD failure
recovery, corrupted records, logical paths and external-sentinel protection.

Use the standard sandboxed `.venv/bin/python -m pytest -q` and active frontend
`npm run test:unit`, `npm run test:cv`, `npm run build`, `npm run lint`, plus
`.venv/bin/python -B -m tools.generate_api_types --check`. Do not use the legacy
live-backend E2E suite against user data. Real XeLaTeX/provider smoke checks remain
opt-in; no fake PDF is evidence of correct visual layout or untrusted-TeX security.

TRF-01 working-tree verification:

- `.venv/bin/python -m pytest -q`: **255 passed**, including **36** Studio
  foundation cases. No expected failures.
- `npm run test:unit`: **30 passed**, including generated composition validation
  and defaults; `npm run test:cv`: **19** API-isolated Chromium checks passed.
- `npm run build`, `npm run lint`, generated-schema drift and `git diff --check`:
  passed. No actual Studio UI or preview is claimed by these existing UI checks.
- Independent sandboxed suite execution preserved **five external sentinels** and
  the inventory/SHA-256 hashes of **815 data/assets/legacy files**. No user data
  migration, registry rewrite, real provider/TeX execution or Docker run occurred.
