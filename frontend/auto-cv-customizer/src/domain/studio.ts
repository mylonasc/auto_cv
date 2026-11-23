/** TRF-03: draft/baseline transitions independent of tab and request lifetimes. */
import type { StudioDraft, TemplatePackage, TemplateRevision, CVData } from '../types/api.generated.ts';

export interface StudioState {
  draft: StudioDraft | null;
  cvBaseline: CVData | null;
  packageBaseline: TemplatePackage | null;
  expected: string | null;
  edit: number;
  generation: number;
}
export const initialStudio: StudioState = { draft: null, cvBaseline: null, packageBaseline: null, expected: null, edit: 0, generation: 0 };
export type StudioAction =
  | { type: 'load'; draft: StudioDraft; saved: boolean; edit: number }
  | { type: 'cv'; cv: CVData }
  | { type: 'package'; package: TemplatePackage }
  | { type: 'templateReload'; value: TemplateRevision; generation: number; edit: number }
  | { type: 'templateSaved'; value: TemplateRevision; generation: number }
  | { type: 'cvSaved'; cv: CVData; generation: number };
export const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);
export function studioReducer(state: StudioState, action: StudioAction): StudioState {
  if (action.type === 'load') {
    if (state.edit !== action.edit) return state;
    return { draft: action.draft, cvBaseline: action.saved ? action.draft.cv : null,
      packageBaseline: action.saved ? action.draft.package : null,
      expected: action.saved ? action.draft.cv.cv_template.revision : null, edit: state.edit + 1, generation: state.generation + 1 };
  }
  if (!state.draft) return state;
  if (action.type === 'cv') return { ...state, edit: state.edit + 1, draft: { ...state.draft, cv: action.cv } };
  if (action.type === 'package') return { ...state, edit: state.edit + 1, draft: { ...state.draft, package: action.package } };
  if (action.generation !== state.generation) return state;
  if (action.type === 'templateReload') {
    if (action.edit !== state.edit) return state;
    return { ...state, edit: state.edit + 1, expected: action.value.revision, packageBaseline: action.value.package,
      draft: { cv: { ...state.draft.cv, cv_template: { ...state.draft.cv.cv_template, revision: action.value.revision } }, package: action.value.package } };
  }
  if (action.type === 'cvSaved') return { ...state, cvBaseline: action.cv };
  return { ...state, expected: action.value.revision, packageBaseline: action.value.package,
    draft: { ...state.draft, cv: { ...state.draft.cv,
      cv_template: { ...state.draft.cv.cv_template, template_id: action.value.package.template_id, template_path: null, revision: action.value.revision } } } };
}
export function move<T>(items: T[], index: number, delta: number): T[] {
  const next = index + delta;
  if (next < 0 || next >= items.length) return items;
  const result = [...items];
  [result[index], result[next]] = [result[next], result[index]];
  return result;
}
export function duplicateSection(section: NonNullable<CVData['document']>['sections'][number], id: () => string) {
  if (section.kind === 'statement' || section.kind === 'experience') throw new Error('Bindings cannot be duplicated');
  const copy = { ...section, id: id(), title: `${section.title} copy` };
  if ('entries' in section) return { ...copy, entries: section.entries.map(entry => ({ ...entry, id: id() })) } as typeof section;
  if ('groups' in section) return { ...copy, groups: section.groups.map(group => ({ ...group, id: id() })) } as typeof section;
  return copy as typeof section;
}

const STARTER_LABELS: Record<string, string> = {
  default_cv: 'Classic — narrow work-experience rows',
  template2: 'Wide — full-width work-experience rows (recommended)',
};

export function starterLabel(id: string): string {
  return STARTER_LABELS[id] ? `${id} — ${STARTER_LABELS[id]}` : id;
}

export function defaultStarter(cvTemplateId: string | undefined, registry: string[]): string {
  if (cvTemplateId && registry.includes(cvTemplateId)) return cvTemplateId;
  if (registry.includes('template2')) return 'template2';
  return registry[0] ?? 'template2';
}
