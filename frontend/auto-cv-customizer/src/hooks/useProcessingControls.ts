import { useEffect, useState } from 'react';
import { useAppState } from '../contexts/AppStateContext';
import { useTemplates } from './useTemplates';
import { editWorkingItem, editWorkingFilter, filterWorkingSection } from '../domain/workingCopyEditing';
import type { SectionFilterConfig, WorkingCopyItem } from '../types/view';

/** UI command adapter: views supply events, not workflow or selection policy. */
export function useProcessingControls() {
  const { state, dispatch, workflow } = useAppState();
  const { registry, error: templateError } = useTemplates();
  const [template, setTemplate] = useState('default_cv');
  const [error, setError] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [rendering, setRendering] = useState(false);
  const [rescoring, setRescoring] = useState(false);
  const { viewedJob, activeJob, draft, loadDraft } = workflow;
  const id = viewedJob?.jobId;
  const status = viewedJob?.status;
  useEffect(() => {
    let disposed = false;
    setLoadError(null);
    if (id && status === 'succeeded') void loadDraft(id).catch(failure => { if (!disposed) setLoadError(String(failure)); });
    return () => { disposed = true; };
  }, [id, status, loadDraft]);
  const run = async (command: () => Promise<unknown>) => {
    setError(null);
    try { await command(); } catch (failure) { setError(String(failure)); }
  };
  const posting = state.jobDescriptions.find(job => job.id === state.currentJobDescriptionId);
  const selectedTemplate = registry.cv_templates[template] ? template : Object.keys(registry.cv_templates)[0] || template;
  const showResults = () => dispatch({ type: 'SET_UI_STATE', payload: { activeTab: 'results' } });
  const render = (fromDraft: boolean) => run(async () => {
    if (!id) throw new Error('Select a completed analysis first.');
    setRendering(true);
    try {
      await workflow.render(id, { cv_template_id: selectedTemplate, cv_template_path: registry.cv_templates[selectedTemplate],
        min_relevance_score: state.backendConfig.rewritePolicy.minRelevanceScore,
        min_section_items_keep: state.backendConfig.rewritePolicy.minSectionItemsKeep,
        max_section_items_keep: state.backendConfig.rewritePolicy.maxSectionItemsKeep,
        include_latex: state.backendConfig.outputs.includeLaTeX, render_pdf: state.backendConfig.outputs.renderPDF,
        include_scoring_comments: state.backendConfig.outputs.includeScoringComments }, fromDraft);
      workflow.exportJob(id);
      dispatch({ type: 'SET_UI_STATE', payload: { showExportDialog: true } });
    } finally { setRendering(false); }
  });
  const rescore = (section: number, indices?: number[]) => run(async () => {
    if (!id) return;
    setRescoring(true);
    try { await workflow.rescore(id, section, indices); } finally { setRescoring(false); }
  });
  return { viewedJob, activeJob, draft, dirty: workflow.dirty, id, registry, template: selectedTemplate,
    setTemplate, rendering, rescoring, posting: state.workflow.posting,
    starting: state.workflow.starting, hasPosting: Boolean(posting),
    error: draft?.error || loadError || error || templateError || state.workflow.monitorError,
    loading: Boolean(viewedJob?.result && !draft && !loadError),
    start: () => run(async () => { if (!posting) throw new Error('Select a posting first.');
      await workflow.start(posting.content, state.currentCVVersionId || 'master', state.backendConfig); }),
    preview: () => run(async () => { if (!posting) throw new Error('Select a posting first.');
      await workflow.analyzePosting(posting.content, state.backendConfig); }),
    cancel: () => run(workflow.cancel), showResults,
    save: () => run(async () => { if (id) await workflow.saveDraft(id); }),
    reset: () => { if (id) { workflow.resetDraft(id); setError(null); } },
    retry: () => run(async () => { if (id) { await loadDraft(id); setLoadError(null); } }), render, rescore,
    statement: (value: string) => { if (id) workflow.updateDraft(id, copy => copy && { ...copy, personalStatement: value }); },
    item: (section: number, index: number, patch: Partial<WorkingCopyItem>) => {
      if (id) workflow.updateDraft(id, copy => copy && editWorkingItem(copy, section, index, patch));
    },
    filter: (section: number, patch: Partial<SectionFilterConfig>) => {
      if (id) workflow.updateDraft(id, copy => copy && editWorkingFilter(copy, section, patch));
    },
    applyFilter: (section: number) => run(async () => {
      if (id) workflow.updateDraft(id, copy => copy && filterWorkingSection(copy, section));
    }),
  };
}
export type ProcessingControls = ReturnType<typeof useProcessingControls>;
