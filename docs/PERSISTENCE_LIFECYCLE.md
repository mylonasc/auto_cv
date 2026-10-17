# Persistence and execution (RFK-06)

`application.create_app()` defines routes without opening stores. Its FastAPI
lifespan constructs `ApplicationServices` using `StoragePaths.from_env()` or
explicit paths. Services accept concrete repository instances, a processor
factory and a runner factory. Each app owns its configuration, cache, repositories
and execution handles; importing domain/services does not initialize stores.
`main:app` remains the supported Uvicorn adapter.

## JSON ownership and concurrency

- CVRepository owns version lookup, legacy adaptation, backups and canonical
  saves through `src.cv_storage`. Existing CV recovery rules remain in
  [CV_SCHEMA.md](CV_SCHEMA.md).
- JobManager owns validated jobs and returns deep copies. WorkingCopyRepository
  and SubmissionRepository own their records. ArtifactRepository owns file lookup
  and immutable render metadata under `render_records/`.
- JSON replacement uses one `src.storage` primitive: serialize before writing,
  write a unique sibling temporary file, flush/fsync, atomically replace, and
  remove only that temporary file on failure. Job memory publishes after disk.
- Per-repository reentrant locks serialize read/modify/write within **one
  process**; artifact appends and rescore updates do not overwrite unrelated
  updates. This is not a multi-worker database or a cross-record transaction.
  Working-copy PUT is last-writer-wins. Rescore checks changed bullet identities
  and text before applying its results, retaining unrelated edits.
- Malformed historical records are retained and reported via repository
  `load_errors` and logging. Read adapters do not migrate files in place.
- Multi-record publication writes working/render records before marking success.
  A write failure can leave conservative unreferenced files, not a successful
  job missing its required provenance. No automatic sweep deletes these files.

## Jobs, cancellation and restart

JobRunner owns actual asyncio Tasks, not request dictionaries. Queued jobs can
enter processing or a terminal state; processing cannot return to the queue.
Terminal states cannot change to another status. Success publication has a final
cancellation gate and then no await between related writes and terminal status.
Cancellation therefore cannot be followed by late success, even if a provider
suppresses `CancelledError`.

Shutdown marks active jobs cancelled, cancels and awaits all owned handles.
Startup marks persisted queued/processing jobs failed with an interruption
message; requests are **not** automatically replayed. Create a new job to retry.
Cancellation cannot forcibly stop an already-running synchronous provider or
render thread; that thread may finish an unreferenced output, but cannot publish
it as successful job output. Shutdown awaits asyncio handles, not arbitrary
external process termination. Failure classification/PDF subprocess checks are
the separate RFK-07 deliverable.

## Snapshots and deletion

Jobs persist candidate, selected version, an independent source CV snapshot and
non-secret effective settings at creation. Processing never reloads that version
after the job is accepted. Each render gets immutable CV/selection/scoring
provenance; submission snapshots come from the selected render, not current
master/source/working-copy data. Artifacts from different renders cannot be
combined in one submission. With no artifact IDs, the latest render's artifacts
are selected. Historical artifacts lacking provenance require a new render;
existing historical submissions remain readable and are not rewritten.

Working-copy operations require an existing succeeded job, including PUT.
Delete requires a terminal job, and removes only job history. Working copies,
artifacts, render records, submissions and CV backups are deliberately retained.
Deleting a submission removes only its record; deleting a non-master source
version does not alter captured job/render/submission inputs. Master deletion is
rejected. Automatic cascading cleanup is not authorized by these operations.

Regression tests: `tests/test_repositories.py`, `tests/test_lifecycle.py`, and the
working-copy/API/storage suites. They run offline against injected temporary
repositories and fake model/PDF boundaries.
