# Epic: maintainability refactor of the CV agent stack

## Purpose and scope

Improve the understandability, maintainability, and extensibility of the existing
React/FastAPI CV analysis and editing application. Preserve the current single-CV
scope. This is a behavior-preserving architectural refactor except where explicit
regression tests document the correction of existing defects.

Work on `enhancement/epic-refactor`. Use the RFK identifiers below in issues,
commits, and progress reports. GitHub tracking links will be recorded below once
the epic and its child issues have been published.

Non-goals: multi-user or multi-candidate support, new authoring features,
microservices, a database migration, a generic CV framework, or adoption of a
new agent orchestration/state-management framework merely for its own sake.

## Design analysis

### Overall assessment

The main problem is **unclear ownership of data and workflow state**, not the
single-CV limitation.

There are useful foundations: FastAPI routers, Pydantic models, structured LLM
outputs, a model factory, and a separate API client. However, those boundaries
are frequently bypassed. Understanding a change requires following mutable
objects, loosely typed dictionaries, compatibility fallbacks, and duplicated
logic across several layers.

Keep this a single application and refactor incrementally. Do not introduce
microservices, a generic CV framework, or a more elaborate agent framework.

### 1. The CV has multiple competing sources of truth

**Highest priority.**

`server_application/backend/api/cv_data.py:46` normalizes CV data into a payload
containing both `candidate.personal_statement`, `candidate.experience_sections`,
etc. and top-level copies of those same fields.

The frontend edits the top-level fields, but normalization prefers existing
nested fields. Meanwhile, `candidate_bundle_from_legacy()` in `src/domain.py:49`
reads the top-level fields.

This is not merely confusing: an isolated check of the existing normalizer,
without application imports or writes, showed that a top-level statement changed
from `original` to `edited` becomes `original` again after normalization when the
nested copy remains unchanged.

**Maintenance consequence:** different parts of the application can disagree
about what the CV actually contains. Adding a field requires understanding
undocumented precedence rules.

**Recommended direction:** define one canonical CV schema; make editors,
persistence, and processing use it; support older shapes through an explicit
migration adapter at the storage boundary; and do not return two writable
representations of the same information. Supporting one candidate does not
require supporting several simultaneous CV schemas.

### 2. API contracts exist, but are not authoritative

Several paths work around declared types rather than relying on them:

- `CVProcessor.process()` declares `CVJobResult` but returns a tuple containing
  dictionaries.
- `JobManager.update_job_status()` accepts either a model or a dictionary and
  preserves malformed results when validation fails.
- The frontend receives loosely typed records and reconstructs its own result
  shape.
- Artifacts have competing `kind`/`type` and `filename`/`name` conventions.

There is a concrete transport mismatch:

- `server_application/backend/utils/sse.py:29` emits `job_id`.
- `frontend/auto-cv-customizer/src/services/api.ts:355` reads `job.id`.
- `ProcessingTab` feeds SSE payloads into that transformer.

Consequently, streamed updates produce a null frontend job ID. Completion events
also omit `job_analysis`, unlike the normal job response.

Another mismatch: the processor produces section-level `posting_evidence`, but
`SectionResult` does not declare it, so normal Pydantic parsing drops it.

**Recommended direction:** establish typed request, response, artifact, and SSE
contracts. Either reuse the job response for SSE or define and consume a distinct
event schema. Generate frontend transport types from OpenAPI where practical.
Keep UI-specific mapping explicit and localized. Normalize old persisted records
once, rather than spreading fallback logic through consumers.

The important distinction is between **transport data and UI state**, not between
snake_case and camelCase.

### 3. Analysis, selection, and rendering are entangled

In `src/utils_cross_analysis.py`, `CVCrossAnalyzer` runs LLM calls, manages caching
and concurrency, attaches analysis as document comments, stores results keyed by
Python object identity, mutates the document when filtering, and calculates
metrics.

The backend then filters the CV before creating the persisted result and working
copy. The "analysis result" is already a selected, modified document. Discarded
bullets are absent from the working copy, and retained bullets are all marked
`kept=True`.

**Maintenance consequence:** it is difficult to distinguish original CV content,
analysis of that content, selection decisions, user edits, and rendered output.

Object-keyed analysis depends on retaining the same in-memory objects. Copying,
serializing, or reconstructing the CV breaks that implicit relationship.

There is another hidden behavior: `.copy()` removes scoring comments. Callers use
copying to obtain uncommented rendering, although the name suggests an ordinary
copy.

**Recommended direction:** keep analysis separate from document mutation; give
experience entries and bullets stable identifiers; represent selection as flags
or selected IDs without deleting analyzed content; make filtering and metrics
pure functions; and pass rendering options explicitly, including scoring-comment
visibility. A small set of explicit data objects is sufficient.

### 4. There is no single application workflow

Workflow orchestration is spread across:

- `server_application/backend/services/cv_processor.py`
- `server_application/backend/api/cv_jobs.py`
- `tools/autocv.py`
- `tools/autocv-otel.py`

These paths have already diverged:

- The CLI injects configured models; the main backend processor constructs
  analyzers with defaults instead.
- `_create_model_factory()` exists in the processor but is unused.
- Rescoring constructs its own default model directly in the router.
- The telemetry script still calls now-async methods without awaiting them.
- Filtering and artifact generation are implemented in multiple places.

The frontend stage model also differs from execution: "Stage 2" reruns job
analysis and may render artifacts, despite separate job-analysis and rendering
stages in the UI.

**Recommended direction:** create one application-level workflow with explicit
inputs and dependencies:

```text
Analyze posting -> Analyze CV -> Prepare working copy -> Render
```

The HTTP API and CLI should call that implementation. Telemetry should wrap it
rather than duplicate it. Resolve configuration once, then inject selected
models and policies into each stage. Inactive configuration fields should be
removed or clearly excluded from the supported contract, not presented as
effective settings.

### 5. Frontend workflow state is tied to tab lifetimes

`ProcessingTab.tsx` owns the SSE connection, processing flags, working-copy draft,
saving, rescoring, filtering, and rendering. But `MainContent.tsx:16`
conditionally mounts only the active tab. Leaving the workflow tab destroys its
local state and closes its stream while backend work continues.

Working-copy state is duplicated across global `state.workingCopy`, local
`localWorkingCopy`, and the persisted backend working copy. Local edits do not
continuously update the global copy. Loading is guarded by `!localWorkingCopy`,
rather than checking whether the copy belongs to the selected job.

`ProcessingState` combines standalone posting analysis, a running job, viewed
results, and the last successful job. Repeated `jobId || lastSuccessfulJobId`
fallbacks are a symptom of this ambiguity.

**Recommended direction:** separate the selected posting and CV version, active
processing job, viewed completed job, working-copy draft keyed by job ID, and
local presentation state. Own job monitoring above the tab lifecycle. Keep a
draft distinct from its saved baseline with explicit dirty/save behavior.
React context and reducers can support this without another state library.

### 6. Frontend components mix too many responsibilities

The roughly 950-line
`frontend/auto-cv-customizer/src/components/main/ProcessingTab.tsx` contains
transport lifecycle, application commands, selection policy, nested data updates,
and presentation. Its problem is not simply length.

`EditorTab.tsx` combines version management, visual editing, JSON editing,
template configuration, and persistence. Other coupling reinforces this:

- Most frontend types live in `AppStateContext.tsx`, including types imported by
  the API layer.
- Both `JobInputTab` and `EditorTab` independently fetch and edit CV versions.
- Some editor updates shallow-copy the outer object while mutating nested arrays.
- "Edit CV Sections" from results opens the source CV editor, not the result's
  working copy.

**Recommended direction:** organize around existing responsibilities, for example
`useJobRun` for start/monitor/cancel, `useWorkingCopy` for load/edit/save/rescore,
pure selection/update functions, and focused `WorkingCopyEditor`,
`ExperienceSectionEditor`, and `RenderControls` components. Share CV-version
loading and mutation logic. Move domain and transport types out of React context.
Components should render and handle user interaction, not coordinate workflows.

### 7. Persistence and execution lifecycle are implicit

`server_application/backend/api/cv_jobs.py` is not a thin HTTP layer: it also
performs persistence, rendering, prompt construction, LLM calls, and job
orchestration.

Infrastructure is initialized during imports: the global job manager loads
persisted jobs, the global analysis cache loads storage, several modules create
directories, and import-path helpers mutate `sys.path`.

Job state and execution state are not clearly separated. `active_tasks` stores
requests, not running task handles. Cancellation depends on callbacks noticing
the cancelled status, and status changes do not enforce transition rules.

Persisted jobs omit the source CV version and effective processing configuration.
Submission creation consequently reads the current master CV rather than
necessarily the version or working copy used to produce the submitted artifact.

**Recommended direction:** introduce small concrete repositories for jobs, CV
versions, working copies, and submissions. Keep JSON storage initially; a
database is not required. Initialize dependencies through an application
factory/lifespan. Put execution and cancellation ownership in one job runner.
Persist effective inputs needed to interpret a result. Centralize atomic file
writes and related-record lifecycle rules. The goal is explicit ownership, not
an interface for every class.

### 8. Failure and cache behavior hide important distinctions

Bullet and section analysis failures are swallowed. Rescoring can return an empty
success response after failures. PDF compilation logs errors without necessarily
failing the operation. Job-analysis fallback can produce generic requirements
without identifying them as fallback output. As a result, "succeeded" does not
clearly mean that all requested work succeeded.

The analysis cache omits model identity, model settings, and actual structured
posting analysis from its keys. Changing a model can therefore reuse results
from another model.

**Recommended direction:** define successful, failed, or intentionally partial
stage outcomes explicitly. Keep fallback provenance separate from ordinary model
output. Cache keys should capture effective analysis inputs, model configuration,
and prompt/schema version. Treat caching as infrastructure around analysis rather
than part of document mutation.

### 9. Tests currently make refactoring riskier than necessary

`tests/test_submissions.py:78` deletes every JSON file in the configured
submissions directory. Working-copy tests also write into application storage.

Core analysis tests depend on live/default models. Some tests reproduce
implementation logic rather than invoke it. E2E tests expect outdated labels such
as "Start Processing". There are no focused frontend reducer, mapping, or
working-copy tests.

**Recommended direction:** before substantial restructuring, isolate every
filesystem test using temporary repositories; inject deterministic fake LLMs;
add CV read/edit/save round-trip tests; test SSE serialization against frontend
consumption; and test job switching, tab navigation during processing, filtering,
and render-source selection. Protect behavior across refactoring instead of
freezing internal helper layouts.

### Smaller cleanup opportunities

- `src/utils.py` contains document models, LaTeX execution, posting analysis,
  prompts, and configuration loading. Split by responsibility.
- Component CSS uses global selectors that collide, such as `.status-badge`;
  configuration modals implicitly reuse styles owned by the export dialog.
- An old frontend, duplicated backend assets/data, tracked generated files, and
  repetitive placeholder docstrings obscure the active implementation.
- Python startup relies on working directories and path manipulation rather than
  a straightforward installable package.

### Recommended order and target outcome

1. Make tests safe and add boundary regression tests.
2. Choose one CV schema and authoritative API/SSE contracts.
3. Separate immutable analysis from selection, edits, and rendering.
4. Consolidate backend workflow and dependency construction.
5. Separate frontend workflow ownership from tab presentation.
6. Clean up legacy paths, styling boundaries, and packaging.

Every change should have an obvious home: **content in CV models, analysis in
analysis services, editing in working copies, execution in the job runner, and
presentation in React components.**

### Review limitations

The original review was source-level plus an isolated normalizer check; the
existing suite was not run because some tests write to or delete application
data. Line references describe the review baseline and will drift during work.
Existing user changes were not part of the review's proposed modifications.

## Prioritized delivery tasks

P0 = safety/data-integrity prerequisite; P1 = core architectural correction;
P2 = structural cleanup after the core boundaries stabilize. Dependencies are
blocking relationships, not merely suggested reading. Priority does not override
a prerequisite. Independent tasks may proceed once their prerequisites are met.

| ID | Priority | Goal | Blocked by |
| --- | --- | --- | --- |
| RFK-01 | P0 | Safe, deterministic regression harness | None |
| RFK-02 | P0 | Canonical CV schema and storage-boundary migration | RFK-01 |
| RFK-03 | P0 | Authoritative HTTP, SSE, and artifact contracts | RFK-01, RFK-02 |
| RFK-04 | P1 | Separate analysis, selection, editing, and rendering data | RFK-02, RFK-03 |
| RFK-05 | P1 | One workflow and effective configuration for API/CLI/telemetry | RFK-04 |
| RFK-06 | P1 | Explicit repositories and job execution lifecycle | RFK-03, RFK-05 |
| RFK-07 | P1 | Explicit failure/fallback outcomes and correct cache identity | RFK-05, RFK-06 |
| RFK-08 | P1 | Frontend state ownership independent of tabs | RFK-03, RFK-04, RFK-06 |
| RFK-09 | P2 | Focused frontend components and scoped presentation | RFK-08 |
| RFK-10 | P2 | Package boundaries, legacy cleanup, and integration verification | RFK-07, RFK-09 |

### RFK-01 — Safe, deterministic regression harness

Replace application-storage fixtures and live-model defaults with isolated
dependencies. Establish the safety net before refactoring production behavior.

Acceptance criteria:

- [ ] Every filesystem test uses temporary storage; no fixture deletes or writes
  configured user/runtime data. Sentinel files outside test storage survive.
- [ ] Default unit/API tests use fake LLMs and fake PDF execution; no network,
  credentials, Ollama service, or LaTeX installation is required.
- [ ] Characterization/regression tests cover CV save round trips, SSE identity,
  evidence preservation, working-copy selection, and render-source selection.
  Known defects may start as strict expected failures tied to their RFK issue.
- [ ] Tests invoke production code rather than reimplementing its algorithms.
- [ ] Test commands and opt-in live integration checks are documented.

### RFK-02 — Canonical CV schema and migration

Choose one representation for CV content and template references. Move support
for historical flat/nested/list shapes to a documented storage-boundary adapter.

Acceptance criteria:

- [ ] One typed CV representation is used by persistence, editing, and processing;
  API payloads do not contain competing writable copies of content.
- [ ] Fixtures for all currently supported legacy shapes migrate deterministically
  and idempotently, with explicit conflict precedence and validation failures.
- [ ] Read/edit/save/reload preserves statements, alternatives, experience bullets,
  candidate metadata, and template choices through both editor paths.
- [ ] Migration is non-destructive: original data is preserved or backed up and
  recovery behavior is documented; ambiguous conflicts are not silently lost.
- [ ] The existing supported CV and templates still load and render.

### RFK-03 — Authoritative HTTP, SSE, and artifact contracts

Replace unvalidated transport dictionaries and distributed compatibility logic
with explicit schemas and frontend transport types outside React context.

Acceptance criteria:

- [ ] Request/response types match real service return values, including the
  processor's result and posting-analysis output.
- [ ] SSE progress/completion events have a declared schema; frontend consumption
  preserves job identity, terminal status, result, errors, and posting analysis.
- [ ] Section and bullet evidence survive validation, persistence, HTTP, and
  frontend mapping.
- [ ] Artifact fields use one convention; older records are normalized at a
  boundary, not guessed by each consumer.
- [ ] Malformed new results fail validation instead of being retained as an
  arbitrary dictionary. Frontend mappings are typed and contract-tested;
  OpenAPI-derived types are preferred if practical.

### RFK-04 — Separate analysis, selection, editing, and rendering

Introduce stable entry/bullet identity and distinguish immutable source/analysis
from editable working-copy text and selection decisions.

Acceptance criteria:

- [ ] Analysis can be serialized and reconstructed without Python object-key
  identity; stable IDs remain associated after copy and round trip.
- [ ] Full analyzed content is retained, including deselected bullets; a working
  copy can toggle them without reloading source data or rerunning analysis.
- [ ] Filtering and metrics are deterministic pure functions with boundary tests
  for missing scores, ties, empty sections, and min/max policies.
- [ ] Analysis does not mutate document text or attach rendering comments as a
  side effect; stale scores after edits have an explicit representation/policy.
- [ ] Rendering receives explicit content, selection, template, and comment
  options. Ordinary copying does not secretly remove annotations.

### RFK-05 — Shared application workflow and configuration

Move orchestration out of adapters into one application workflow. Keep distinct
posting analysis, CV analysis, working-copy preparation, and rendering stages.

Acceptance criteria:

- [ ] API, CLI, and telemetry invoke the same stage implementations; telemetry
  wraps execution and awaits async calls rather than copying the pipeline.
- [ ] Analysis, statement editing, and rescoring receive resolved model/policy
  dependencies explicitly; requested settings are verified using fake providers.
- [ ] Defaults are resolved in one place; supported configuration is effective,
  and unsupported/inactive options are not misleadingly presented as effective.
- [ ] Standalone versus combined stages have explicit inputs/outputs; UI labels
  match actual execution, including when analysis or rendering is repeated.
- [ ] One filtering/rendering path serves the existing entry points, with parity
  tests for equivalent API and CLI inputs.

### RFK-06 — Repositories and job execution lifecycle

Separate file persistence, execution ownership, and HTTP routing. Keep JSON
storage and one application process as the initial operating model.

Acceptance criteria:

- [ ] Concrete repositories own CV versions, jobs, working copies, submissions,
  and artifact metadata; routers delegate application operations.
- [ ] App factory/lifespan constructs dependencies. Importing domain/service
  modules does not read runtime stores or create runtime directories.
- [ ] JSON writes are atomic; update serialization/concurrency rules and
  deletion/related-record policies are documented and tested.
- [ ] A job runner owns actual execution handles and legal status transitions;
  cancellation cannot later become success. Restart/shutdown behavior is explicit.
- [ ] Jobs retain source version/snapshot and effective configuration; submission
  snapshots refer to the actual selected render input, not today's master CV.
- [ ] Repositories and runner can be injected into isolated tests without
  mutating process-global application stores.

### RFK-07 — Failure outcomes, fallback provenance, and cache identity

Make incomplete analysis and failed rendering distinguishable from successful
work, and isolate caching from content/document mutation.

Acceptance criteria:

- [ ] Stages explicitly distinguish success, failure, and permitted partial
  results; bullet/section/rescore failures are surfaced with context.
- [ ] PDF process failure or missing output cannot publish a successful artifact.
- [ ] Heuristic/default posting analysis is labeled as fallback with provenance.
- [ ] Cache keys include effective content/posting analysis, provider/model,
  relevant model settings, and prompt/schema versions; changing any relevant
  input invalidates the cache in tests.
- [ ] Cache failures follow a documented policy; corrupt/legacy entries cannot
  silently masquerade as fresh valid analysis.
- [ ] Failure/cancellation tests confirm truthful terminal status and cleanup.

### RFK-08 — Frontend workflow and draft ownership

Separate active execution, viewed result, selected inputs, persisted baseline,
and editable draft. Own monitoring above conditional tab components.

Acceptance criteria:

- [ ] Leaving/reopening tabs during execution neither loses monitoring nor
  changes the active job identity; stream cleanup/reconnection rules are tested.
- [ ] Switching between jobs never displays or saves another job's draft.
- [ ] One authoritative draft per job has explicit dirty/save/reset semantics;
  save failure is propagated and cannot be mistaken for successful persistence.
- [ ] Posting-only analysis and viewed completed results do not overwrite active
  execution identity; rendering/export do not guess the latest successful job.
- [ ] Editing a source CV versus editing a result's working copy is explicit in
  navigation and actions. Frontend reducer/hook tests cover these transitions.

### RFK-09 — Focused frontend components and presentation

Extract application hooks, shared CV-version access, pure editing operations,
and small view components from the current tab implementations.

Acceptance criteria:

- [ ] Processing/editor views compose focused controls and editors; SSE, workflow
  commands, and selection policies are not implemented in view components.
- [ ] Shared CV-version load/save behavior serves Job Input and CV Data Editor;
  domain/transport types do not depend on React context.
- [ ] Nested edits are immutable and covered by tests; visual and JSON modes have
  explicit synchronization and validation behavior.
- [ ] Shared modal/button/status primitives own shared styling; feature styles
  are scoped so unrelated tabs cannot override each other's selectors.
- [ ] Existing capabilities remain accessible; build, lint, component tests,
  and updated deterministic navigation/editing E2E checks pass.

### RFK-10 — Package boundaries, legacy cleanup, and verification

Finish the structural cleanup only after the new boundaries are established.
Inventory legacy assets and runtime data before removing anything.

Acceptance criteria:

- [ ] Python modules are grouped by responsibility rather than catch-all utils;
  supported entry points work without ad hoc `sys.path` edits or CWD assumptions.
- [ ] The active frontend/backend/core layout and commands are documented;
  dependency declarations are consistent and placeholder docstrings are replaced
  with meaningful contracts or removed.
- [ ] Obsolete frontend/code/assets/generated files are inventoried. Removal is
  justified and reviewed; user CV data/artifacts are not silently discarded.
- [ ] Docker and manual/CLI startup use the same configuration/path rules.
- [ ] Isolated backend tests, frontend unit/component/E2E tests, build, and lint
  pass with reproducible commands. An optional live CV render smoke test is
  documented separately from deterministic CI.
- [ ] All linked RFK acceptance criteria are verified and this document reflects
  the delivered architecture, known limitations, and any remaining follow-ups.

## Completion policy

Each task must have a GitHub child issue attached to the parent epic and native
blocking dependencies matching the table. Keep a readable dependency list in
each issue as well. Check acceptance criteria only when evidence exists.

Documentation and issue creation do not complete the implementation tasks.
Close a task only after its acceptance criteria are met and reference the exact
implementation commit(s) in its closing comment. Because work stays on one
branch, use `Refs #N` while work is ongoing; close explicitly with commit/test
evidence when appropriate. Reserve `Closes #N` for changes that actually complete
the issue, noting GitHub's default-branch merge behavior for automatic closure.

Commits should explain the RFK goal, changed boundaries/behavior, compatibility
and migration implications, and verification performed. Do not combine unrelated
tasks or include pre-existing user modifications.
