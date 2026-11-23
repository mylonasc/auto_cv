# Frontend components and editing (RFK-09)

The application remains one React/Vite frontend; no state or orchestration
framework was added. The template-boundary follow-up uses Ajv to validate JSON
editing against the generated backend CV schema rather than a handwritten copy.

## Boundaries

- `contexts/AppStateContext.tsx`: selected source inputs, saved posting list,
  configuration, navigation and the application-owned workflow reducer.
- `hooks/useWorkflow.ts` and `services/jobMonitor.ts`: execution commands and
  monitoring above conditional tabs. See [FRONTEND_WORKFLOW.md](FRONTEND_WORKFLOW.md).
- `hooks/useProcessingControls.ts`: command-to-UI adaptation, working-copy loading,
  edit/filter commands and operation feedback. Render template overrides are
  application-owned, keyed by job; omission inherits its saved template.
- `hooks/useCVVersion.ts`: shared source-version list/load/save/create/delete
  access for Job Input and CV Data Editor. Request generations reject late loads
  and save responses after selecting another version.
- `hooks/useSourceEditor.ts`: source editor mode/selection/dirty lifecycle,
  version commands and canonical JSON-to-visual synchronization.
- `hooks/useTemplates.ts`: template registry access without view-owned requests.
- `domain/cvEditing.ts`, `workingCopyEditing.ts`, `selection.ts`: pure immutable
  editing/selection operations. Tests freeze input graphs to catch shallow mutation.
- `types/`: generated transport schemas and independent CV/view types; no React
  context dependency in domain/transport types.

`ProcessingTab` composes `WorkingCopyEditor`, its focused section/evidence
controls, `JobStatusPanel` and `PostingAnalysis`. `EditorTab` composes
`SourceVersionList`, `SourceTemplates`, `SourceContent` and `SourceTextEditor`.
Views render controls and forward events; they do not implement SSE, provider
workflows or scoring/selection policies.

## Source editing behavior

Visual changes replace only affected nested objects/arrays and retain candidate
metadata, unrelated content and templates. Structural edits clear index-based
text selection to prevent applying an old edit to a shifted item.

JSON mode retains invalid text with a visible error. Switching to visual mode or
saving/creating a version first parses and checks canonical CV v1 shape; invalid
input cannot silently replace visual data or send a save. Valid JSON changes are
applied before switching modes. Backend Pydantic validation remains authoritative.
Saving disables source editing controls; source-version switching prompts before
discarding dirty changes. Source editing is distinct from a result working copy.
Source drafts remain tab-local, with a shared `useUnsavedNavigation` guard covering
tab/version navigation, page unload, JSON drafts and unapplied text in both source
editing paths. Cancelling navigation retains the draft; accepting explicitly
discards it. Navigation is blocked while a source save is in flight. “Analyze
Saved Version” explicitly opens analysis inputs, not an unsaved draft. Per-result
drafts retain the stronger per-job semantics from RFK-08.

JSON validation/defaults come from generated `CV_DATA_SCHEMA` and Ajv. Unknown
nested/top-level fields fail before entering visual mode or issuing a save.
Missing fields receive backend defaults, including legacy `content_format: latex`.
See [TEMPLATES.md](TEMPLATES.md) for template contracts and text-format compatibility.

## Presentation ownership

`components/common/Primitives.tsx` and `Primitives.css` own shared button, status
badge and modal behavior/style. Export, configuration and PDF preview use the same
modal title/role, keyboard containment, Escape and focus-return behavior. Feature
styles do not supply modal layout through incidental import order.

Tab styles use native CSS `@scope` roots (`.editor-tab`, `.processing-tab`,
`.job-input-tab`, `.results-tab`, `.history-tab`, `.submissions-tab`). Generic
selectors such as `.header-title`, `.items-list` and `.hint` cannot leak outside
the feature. Shared form/base tokens remain in `styles/globals.css`.
This uses modern browser CSS scoping support; deterministic browser verification
is Chromium, not a claim of legacy browser compatibility or pixel parity.

## Verification

From `frontend/auto-cv-customizer`, run `npm run test:unit`, `npm run test:cv`,
`npm run build`, and `npm run lint`. The API-isolated browser suite includes
component-focused evidence/filter/provenance checks, JSON/visual edits, modal
keyboard/focus tests, outside-feature style probes, and navigation/async races.
The Vite API proxy uses typed 600-second incoming/outgoing timeout options.
No legacy live-backend E2E suite is required or run against normal user storage.
