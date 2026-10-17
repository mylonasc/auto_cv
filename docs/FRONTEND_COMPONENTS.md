# Frontend components and editing (RFK-09)

The application remains one React/Vite frontend; no state, orchestration or
validation framework was added.

## Boundaries

- `contexts/AppStateContext.tsx`: selected source inputs, saved posting list,
  configuration, navigation and the application-owned workflow reducer.
- `hooks/useWorkflow.ts` and `services/jobMonitor.ts`: execution commands and
  monitoring above conditional tabs. See [FRONTEND_WORKFLOW.md](FRONTEND_WORKFLOW.md).
- `hooks/useProcessingControls.ts`: command-to-UI adaptation, selected render
  template, working-copy loading, edit/filter commands and operation feedback.
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
Source drafts remain tab-local; save before leaving the source editor or reloading
the page. Per-result drafts retain the stronger per-job semantics from RFK-08.

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
