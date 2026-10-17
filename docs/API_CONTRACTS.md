# Job, stream and artifact contracts (RFK-03)

`server_application/backend/models/api_models.py` defines validated request and
response contracts. Unknown new fields, malformed results and non-finite scores
fail validation. Job updates validate before touching memory or disk. The
processor returns `ProcessingOutput` (result plus posting analysis), not a tuple
whose runtime shape contradicts its annotation. Posting-only analysis returns
`JobAnalysisResponse`.

## HTTP and SSE

`job_update` and `job_complete` SSE frames contain the **same serialized
`CVJobResponse`** as GET `/v1/cv-jobs/{id}`: `id`, status, timestamps, original
posting, progress/message, result, posting analysis and error. Keepalive comments
are not state updates. A removed job emits `error` with `StreamError` (`id` and
`error`). These event names are unchanged. There is no separate `job_id` alias
for job snapshots. The frontend uses the same mapper for HTTP and SSE.

Result sections and bullets retain `posting_evidence` through persistence,
transport and working-copy conversion. UI result models preserve null/zero
scores and statement text; they do not invent a job ID or a succeeded status for
a standalone result. UI-only title/casing changes live in pure mappings outside
React context.

## Artifacts and historical records

Artifact metadata uses `id`, `kind`, `filename`, and optional `path`, `source`,
`job_id`, and `created_at`. Supported kinds are `pdf`, `latex`, and `json`.
Downloads identify an artifact by its ID, not a guessed kind. Relocated file
resolution uses its saved path/basename and the deterministic job/kind filename;
it cannot serve a PDF as LaTeX through a wildcard fallback.

Historical `type`/`name` aliases are normalized only by
`models/legacy.py` when jobs or submissions are read. Equal aliases collapse;
conflicting aliases fail explicitly. Source files are not rewritten on read.
Malformed historical records remain on disk and are reported by the existing
loader; broader repository diagnostics/recovery are RFK-06 work. New callers
must use canonical fields and receive validation errors for legacy aliases.

## Frontend types and tests

`tools/generate_api_types.py` generates `src/types/api.generated.ts` in the active
frontend directly from the Pydantic JSON Schemas used by FastAPI. It imports only
model definitions, not the application or runtime stores. Serialized model types
include defaults; request `Input` aliases preserve omittable defaults. UI types
live in `src/types/view.ts`; `src/services/mappers.ts` contains pure mappings.

After changing schemas, regenerate the committed types and run:

```sh
.venv/bin/python -B tools/generate_api_types.py --check
.venv/bin/python -m pytest -q
# From frontend/auto-cv-customizer (Node 24 was used for verification):
npm run test:unit
npm run test:cv
npm run build
```

Without `--check`, the generator prints the new TypeScript to stdout. Unit tests
type-check their inputs before using Node's built-in test runner; no new test
framework is required. `tests/fixtures/job-contract.json` is validated against
real Python HTTP/SSE serializers and consumed by frontend mapping tests, so the
two suites cannot independently bless incompatible example payloads.
