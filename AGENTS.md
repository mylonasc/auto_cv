# Working instructions

## Refactor epic

- Read `EPIC_REFACTOR.md` before working on the refactor. It contains the design
  review, RFK-01 through RFK-10, priorities, dependencies, and acceptance criteria.
- Parent epic: https://github.com/mylonasc/auto_cv/issues/5. Child issues #6–#15
  map to RFK-01–RFK-10; consult native blocked-by relationships before starting.
- Use the single branch `enhancement/epic-refactor` for this epic unless the user
  requests otherwise. Do not implement blocked tasks before their prerequisites.
- Preserve the current single-CV scope. Do not add product features, generic
  candidate frameworks, microservices, databases, or orchestration/state libraries
  without a concrete requirement and user agreement.
- Keep domain content, analysis, selection, working-copy edits, execution,
  persistence, rendering, and presentation responsibilities explicit.

## Safety and testing

- Inspect `git status` first. Preserve existing user changes and untracked CV
  data. Stage only files belonging to the current task; never use broad staging
  or reset/cleanup commands to discard unrelated work.
- Treat CVs, working copies, submissions, caches, artifacts, backups, and legacy
  assets as potentially valuable user data. Inventory before removal/migration;
  never delete broad runtime directories as cleanup.
- Before RFK-01 is complete, do not run the existing pytest suite against normal
  storage: submission fixtures delete JSON files and working-copy tests write
  application data. Inspect fixtures and isolate all storage first.
- Default tests must be deterministic and offline, use temporary storage and
  fake LLM/PDF dependencies, and exercise production code rather than copies.
  Live model/LaTeX checks are explicit opt-in integration tests.
- Add regression tests for corrected behavior. Never bless a known defect as
  intended behavior; track temporary strict expected failures to an RFK issue.
- Report exact checks run and their results. Do not claim unrun tests passed.

## Implementation and compatibility

- Prefer small cohesive changes consistent with surrounding conventions.
- Define canonical schemas and explicit adapters rather than adding distributed
  fallback branches or suppressing validation errors.
- Keep JSON storage initially; centralize atomic writes and repository ownership.
- Resolve configuration once and inject dependencies. Avoid runtime file/network
  side effects during module imports and workflow ownership in tab components.
- Preserve supported legacy data through documented, tested, recoverable
  migrations. Make behavioral corrections and compatibility impacts explicit.
- Keep API/CLI/telemetry behavior aligned through shared application operations.

## GitHub tracking and commits

- Use RFK identifiers in issue titles, commit subjects/bodies, and progress notes.
  Maintain parent/sub-issue links and native blocked-by relationships, with
  readable dependency lists and explicit acceptance criteria in issue bodies.
- Documentation/issue creation does not finish an implementation task. Keep
  issues open until their acceptance criteria are verified.
- Use elaborate commit bodies: explain why, the scope and boundaries changed,
  compatibility/migration effects, tests/results, and `Refs #N` issue links.
- When a task is complete, close its issue with exact implementation commit(s)
  and verification evidence. Use `Closes #N` only for genuinely completed work;
  automatic closure normally happens on merge to the default branch.
- Keep `EPIC_REFACTOR.md` and issue checklists synchronized with actual delivery.
