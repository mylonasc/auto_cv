# Safe backend tests

Run from the repository root with Python 3.12 or newer:

```sh
python -m pip install -r requirements-test.txt
python -m pytest -q
```

With the existing environment, use `.venv/bin/python -m pytest -q`. Default
discovery is restricted to `tests/`; research and scripts are not collected.

## Isolation guarantees

- `conftest.py` overrides `AUTO_CV_DATA_ROOT` **before collection**, so current
  import-time stores never load the normal runtime data, even if a developer
  exports that environment variable before invoking pytest.
- Every test receives fresh temporary directories, job/config stores, and cache.
  Relative processing files are written inside a per-test temporary CWD.
- Structured-output model calls are deterministic fakes. Production prompts,
  LangChain composition, Pydantic validation, filtering, and API handlers run.
- PDF generation is faked only at the LaTeX process boundary. Template expansion
  still runs; fake PDF files are placeholders, not evidence of successful TeX
  compilation.
- Network connects and subprocess launches fail immediately. Never remove these
  guards just to make a unit test pass. Use an explicit dependency fake instead.
- Temporary compatibility fixtures rebind imported storage aliases until RFK-06
  removes import-time globals. New storage consumers must be added to isolation
  or accept an injected repository; do not point tests at normal data.

Known defects are strict expected failures linked to their owning RFK issue. They
assert intended behavior against production code. When a fix produces an XPASS,
remove the marker in the same change, rather than weakening the assertion.

## Isolated browser checks for CV editing

From `frontend/auto-cv-customizer`, run `npm run test:cv`. This uses its own Vite
server on port 5187 and mocks **all** browser API requests. Unexpected API or
external requests are rejected, so these checks cannot reach your backend data.
They cover preview, visual, and JSON editing with canonical metadata/template
preservation; backend tests independently validate real persistence and migration.
An installed Playwright Chromium browser is required (explicit setup if needed:
`npx playwright install chromium`). The separate legacy `test:e2e` suite is not
API-isolated and is not part of this offline validation command.

## Transport and mapping contracts

Run `.venv/bin/python -B tools/generate_api_types.py --check` from the root to
check that frontend transport types match the authoritative backend schemas.
`npm run test:unit` from the frontend type-checks and runs pure mapping tests
with Node's built-in runner (verified with Node 24). Shared fixtures are also
validated by the real backend HTTP/SSE serializers. See `docs/API_CONTRACTS.md`.

## Opt-in live integration smoke check

Live provider/LaTeX checks are **not** part of the pytest suite. After explicitly
configuring a provider and installing XeLaTeX, run the CLI manually with the
documented arguments in the root README. Use a fresh scratch directory for both
`AUTO_CV_DATA_ROOT` and `--output-dir`, and a read-only source CV input. For example
(substitute the configured model names):

```sh
scratch=$(mktemp -d /tmp/opencode/auto-cv-live.XXXXXX)
AUTO_CV_DATA_ROOT="$scratch/runtime" python tools/autocv.py \
  --candidate-json data/cv_section_data/charilaos_mylonas/master.json \
  --job-posting job_post.txt \
  --output-dir "$scratch/output" \
  --analysis-provider ollama --analysis-model llama3.1:latest \
  --authoring-provider ollama --authoring-model llama3.1:latest \
  --cover-letter-provider ollama --cover-letter-model llama3.1:latest \
  --skip-cover-letter
```

Use another existing scratch parent if `/tmp/opencode` is unavailable. This is an
explicitly networked/manual check: inspect generated PDFs and logs; do not infer
correct rendering from placeholder PDFs in unit tests. The CLI refuses to replace
an existing output directory; choose a fresh path. See `docs/PIPELINE.md` for
shared defaults, effective configuration and entry-point semantics.
