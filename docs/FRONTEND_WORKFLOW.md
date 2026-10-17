# Frontend workflow ownership (RFK-08)

`AppStateProvider` owns the workflow reducer and `useWorkflow` command/monitoring
hook for the whole application lifetime. Conditional tab components do not own
execution handles or authoritative copies of result drafts.

## Distinct identities

- Selected job description and source CV version are inputs for the next run.
- `activeJobId` identifies the one running analysis started in this app session.
  Its snapshots live in `jobs`; terminal status clears the active handle without
  changing the viewed result or navigating away from another tab.
- `viewedJobId` identifies the analysis being inspected/edited. Starting a run
  initially views it; opening History explicitly selects a fresh server snapshot.
  Loading History while another job runs never changes execution ownership.
- `posting` is a separate optional posting-only preview, including its own
  status/error. It cannot erase a CV result or act as a CV execution handle.
- `exportJobId` pins the export dialog to an explicit completed analysis. Rendering
  never searches for the newest successful history record. Changing the viewed
  result during a render does not retarget its export dialog.

## Monitoring

`jobMonitor` subscribes to job-update/completion events and reconciles an initial
HTTP snapshot. Native EventSource reconnection stays enabled after connection
errors; a non-overlapping HTTP poll every two seconds reconciles missed terminal
events while disconnected. A visible monitoring warning is separate from server
job status: loss of connection is not job failure or cancellation.

Events and responses must match the owned job ID. Foreign events, late responses
after completion/disposal, and transitions away from a known terminal status are
ignored. Terminal state or provider disposal closes the stream and clears polling.
Tab changes, template choices, posting previews and history navigation do not.
Full-page reload does not restore execution monitoring automatically; persisted
backend jobs remain in History. This task preserves tab navigation, not a new
cross-browser/session execution framework.

## Draft/save/reset semantics

Each job has one `drafts[id]` record containing a saved `baseline`, editable
`value`, revision, save status and error. Dirty comparison concerns editable
statement/sections, not server timestamps. Loading a different job never displays
the old job's draft while its request is pending. Late load responses populate
only their keyed record and cannot overwrite an existing draft.

Successful saves advance the baseline from the actual server response. If the
user edited while the save was pending, their newer value remains dirty rather
than being replaced by the response. Failures retain the draft and baseline,
display an error, and propagate to callers. Rendering a draft requires its save
to succeed and uses that exact saved snapshot; failure sends no render request.
Overlapping saves/rescores of the same job are rejected, not silently raced.

Reset restores that job's last acknowledged saved baseline, never a source CV or
another job. Rescore updates its acknowledged persisted bullet scores/text while
retaining unrelated draft changes and newer text; `scoredText` still exposes a
stale assessment when the user edited after the request. Drafts are in-memory
across tab/job switches; saving is required before a full page reload.

The result action is **Edit Result Working Copy** in Workflow Stages. **CV Data
Editor** explicitly edits source versions for future runs, not result drafts.

## Deterministic checks

From `frontend/auto-cv-customizer`:

- `npm run test:unit`: typed mapping/selection/workflow reducer and monitor tests.
- `npm run test:cv`: API-isolated Chromium editing/navigation/race checks, with
  controlled fake SSE and delayed HTTP responses; no backend/user data access.
- `npm run build` and `npx eslint src tests/unit/workflow.test.ts tests/workflow.spec.ts`.

Component decomposition, shared source-version hooks, editing primitives and
style isolation are the follow-on RFK-09 scope; package-wide cleanup is RFK-10.
