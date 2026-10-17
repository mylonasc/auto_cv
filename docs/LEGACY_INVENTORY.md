# RFK-10 pre-cleanup inventory

Read-only inventory on `enhancement/epic-refactor`, after RFK-09. **No files in
this inventory have been authorized for deletion or automatically migrated.**
Counts describe the inspected checkout, not an invariant for future runs.

## Potentially valuable content/runtime records

| Location | Files | Tracked | Policy |
| --- | ---: | ---: | --- |
| `assets/` | 41 | 41 | Retain candidate content, templates, classes, pictures and render examples |
| `data/` | 656 | 30 | Retain all runtime/user content, including untracked records |
| `data/archive/` | 36 | — | Retain historical files |
| `data/artifacts/` | 485 | — | Retain outputs; no sweep by extension or age |
| `data/cache/` | 1 | — | Retain recoverable legacy/cache state |
| `data/cv_section_data/` | 9 | — | Retain versions/backups and legacy input |
| `data/jobs/` | 85 | — | Retain historical records, including malformed records |
| `data/submissions/` | 11 | — | Retain sent application snapshots |
| `data/working_cvs/` | 28 | — | Retain drafts, including nine existing untracked user files |

`assets/experience_fields_oct25.json` is an existing modified user file. The
tracked `.aux`, `.log`, `.out`, `.pdf` and `.tex` files in `assets/cover_letter/`
may be meaningful examples or candidate outputs; generated-looking names do not
authorize removal. Five external sentinels and hashes of all 697 existing
data/assets files were preserved by the RFK-09 safety verification.

## Legacy/inactive code and configuration

- `server_application/frontend/cv-customizer/`: 11 tracked files, a separate
  historical Vite/React scaffold. The active frontend is
  `frontend/auto-cv-customizer/`; Dockerfile.frontend uses the latter. Keep the
  scaffold until its supported/legacy status and references are reviewed. Do not
  conflate it with the active frontend or runtime content.
- `config/llm_defaults.yaml`: retained historical configuration, no longer an
  active workflow default source after RFK-05. `src.config` owns active defaults.
- `config/templates.json` and the assets referenced by it remain active.
- `frontend/auto-cv-customizer/src/types/api.generated.ts` is active generated
  transport source, checked against Pydantic; it is not obsolete build output.
- `dist/`, test traces, Python bytecode and dependency trees are local build/tool
  products, not grounds for broad repository cleanup in a refactor.

## Entry-point/package findings still requiring implementation

- No root `pyproject.toml` exists. Backend modules use top-level `api`, `core`,
  `models`, `services`, `jobs`, `application` and `repositories` imports; path
  injection currently makes those aliases importable.
- `server_application/backend/main.py` and `core/paths.py` still append to
  `sys.path`. Tests/tools also use aliases that must migrate coherently; merely
  changing the production entry point would not complete package cleanup.
- `src/utils.py` mixes documents/rendering and posting analysis;
  `src/utils_cross_analysis.py` mixes cache, prompts/scoring and cover-letter
  authoring. These responsibilities need focused modules with explicit adapters
  for supported entry points, not copied implementations.
- Root and backend requirements duplicate many entries; Docker installs both
  and adds packages separately. Manual README startup changes CWD to backend,
  while the CLI and tests have their own import assumptions. Package/install,
  dependency and path rules must be aligned before claiming RFK-10 complete.
- Docker configuration/static inspection is not a successful container build or
  live XeLaTeX/provider test. Such checks must be reported separately if run.

RFK-10 remains open. Retention is the default; any removal requires specific
evidence, scope rationale and review, not an extension-based cleanup command.
