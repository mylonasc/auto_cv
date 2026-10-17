import type { ProcessingState, WorkingCopy } from '../types/view';

export interface DraftState {
  baseline: WorkingCopy;
  value: WorkingCopy;
  revision: number;
  saving: boolean;
  error: string | null;
}
export interface WorkflowState {
  jobs: Record<string, ProcessingState>;
  activeJobId: string | null;
  viewedJobId: string | null;
  exportJobId: string | null;
  drafts: Record<string, DraftState>;
  posting: ProcessingState | null;
  starting: boolean;
  monitorError: string | null;
}
export const initialWorkflow: WorkflowState = {
  jobs: {}, activeJobId: null, viewedJobId: null, drafts: {}, posting: null,
  starting: false, monitorError: null, exportJobId: null,
};
export const isTerminal = (job: ProcessingState) => !['queued', 'processing'].includes(job.status);
export const isDirty = (draft: DraftState) => JSON.stringify([draft.value.personalStatement, draft.value.sections]) !==
  JSON.stringify([draft.baseline.personalStatement, draft.baseline.sections]);
export type WorkflowAction =
  | { type: 'starting'; value: boolean }
  | { type: 'started'; job: ProcessingState }
  | { type: 'snapshot'; job: ProcessingState }
  | { type: 'view'; job: ProcessingState }
  | { type: 'export'; id: string }
  | { type: 'posting'; value: ProcessingState }
  | { type: 'monitorError'; value: string | null }
  | { type: 'loaded'; id: string; value: WorkingCopy }
  | { type: 'edit'; id: string; value: WorkingCopy }
  | { type: 'reset'; id: string }
  | { type: 'saving'; id: string }
  | { type: 'rescored'; id: string; items: Record<string, Pick<WorkingCopy['sections'][number]['items'][number],
      'scoredText' | 'relevanceScore' | 'explanation' | 'postingEvidence'>> }
  | { type: 'saved'; id: string; revision: number; value: WorkingCopy }
  | { type: 'saveFailed'; id: string; error: string };

export function workflowReducer(state: WorkflowState, action: WorkflowAction): WorkflowState {
  switch (action.type) {
    case 'starting': return { ...state, starting: action.value };
    case 'export': return state.jobs[action.id]?.status === 'succeeded' ? { ...state, exportJobId: action.id } : state;
    case 'posting': return { ...state, posting: action.value };
    case 'monitorError': return { ...state, monitorError: action.value };
    case 'started':
    case 'snapshot':
    case 'view': {
      const id = action.job.jobId;
      if (!id) return state;
      const previous = state.jobs[id];
      if (previous && isTerminal(previous) && previous.status !== action.job.status) return state;
      return { ...state, jobs: { ...state.jobs, [id]: action.job },
        viewedJobId: action.type === 'started' || action.type === 'view' ? id : state.viewedJobId,
        activeJobId: action.type === 'started' && !isTerminal(action.job) ? id :
          state.activeJobId === id && isTerminal(action.job) ? null : state.activeJobId,
        monitorError: action.type === 'started' || state.activeJobId === id && isTerminal(action.job) ? null : state.monitorError,
        starting: action.type === 'started' ? false : state.starting };
    }
    case 'loaded':
      if (action.value.jobId !== action.id || state.drafts[action.id]) return state;
      return { ...state, drafts: { ...state.drafts, [action.id]: {
        baseline: action.value, value: action.value, revision: 0, saving: false, error: null,
      } } };
    default: {
      const draft = state.drafts[action.id];
      if (!draft) return state;
      let next = draft;
      switch (action.type) {
        case 'edit':
          if (action.value.jobId !== action.id) return state;
          next = { ...draft, value: action.value, revision: draft.revision + 1, error: null }; break;
        case 'reset': next = { ...draft, value: draft.baseline, revision: draft.revision + 1, error: null }; break;
        case 'saving': next = { ...draft, saving: true, error: null }; break;
        case 'rescored': {
          const apply = (copy: WorkingCopy, baseline: boolean): WorkingCopy => ({ ...copy,
            sections: copy.sections.map(section => ({ ...section, items: section.items.map(item => {
              const update = action.items[item.id];
              return update ? { ...item, ...update, ...(baseline ? { text: update.scoredText ?? item.text } : {}) } : item;
            }) })),
          });
          next = { ...draft, baseline: apply(draft.baseline, true), value: apply(draft.value, false),
            revision: draft.revision + 1, error: null };
          break;
        }
        case 'saveFailed': next = { ...draft, saving: false, error: action.error }; break;
        case 'saved':
          if (action.value.jobId !== action.id) return state;
          next = { ...draft, baseline: action.value,
            value: draft.revision === action.revision ? action.value : draft.value,
            saving: false, error: null }; break;
      }
      return { ...state, drafts: { ...state.drafts, [action.id]: next } };
    }
  }
}
