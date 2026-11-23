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

TRF-01 is delivered in `043978d` and #18 is closed. TRF-02 integrates composition
rendering; its verification is recorded below. Subsequent slices retain native
blocking relationships and are not complete merely because foundation types exist.

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

The future TRF-03 operation must save the package before explicitly creating a new
CV version; it must not overwrite the selected original. Importing publications
as raw LaTeX is intentional preservation, not a claim that bibliography entries
have been semantically parsed. Structured publication entries can be authored
without guessing the original markup.

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
