import { useCallback, useEffect, useLayoutEffect, useRef } from 'react';
import type { Dispatch } from 'react';
import type { WorkflowAction, WorkflowState } from '../domain/workflow';
import { isDirty } from '../domain/workflow';
import type { BackendConfig, ProcessingState, WorkingCopy } from '../types/view';
import type { RenderCVRequestPayload } from '../services/api';
import api from '../services/api';
import { monitorJob } from '../services/jobMonitor';
import type { CVJobResponse } from '../types/api.generated';

const message = (error: unknown) => error instanceof Error ? error.message : 'Operation failed';

/** Application lifetime owns commands and monitoring, never a conditional tab. */
export function useWorkflow(state: WorkflowState, send: Dispatch<WorkflowAction>) {
  const current = useRef(state);
  useLayoutEffect(() => { current.current = state; }, [state]);
  const pending = useRef(new Set<string>());
  const loads = useRef(new Map<string, Promise<void>>());

  useEffect(() => {
    const id = state.activeJobId;
    if (!id) return;
    return monitorJob(id, {
      stream: () => api.createJobStream(id), fetch: () => api.getJob(id),
      decode: value => api.transformJobToProcessingState(value as CVJobResponse),
      snapshot: job => send({ type: 'snapshot', job }),
      error: value => send({ type: 'monitorError', value }),
    });
  }, [state.activeJobId, send]);

  const loadDraft = useCallback((id: string): Promise<void> => {
    if (current.current.drafts[id]) return Promise.resolve();
    const loading = loads.current.get(id);
    if (loading) return loading;
    const promise = api.getWorkingCopy(id).then(value => {
      send({ type: 'loaded', id, value: api.transformWorkingCopyFromBackend(value) });
    }).finally(() => loads.current.delete(id));
    loads.current.set(id, promise);
    return promise;
  }, [send]);

  const saveDraft = useCallback(async (id: string) => {
    const draft = current.current.drafts[id];
    if (!draft) throw new Error('Load this job’s draft before saving.');
    if (pending.current.has(`save:${id}`) || pending.current.has(`rescore:${id}`)) throw new Error('A draft operation is already in progress.');
    pending.current.add(`save:${id}`);
    send({ type: 'saving', id });
    try {
      const value = api.transformWorkingCopyFromBackend(await api.saveWorkingCopy(id, api.transformWorkingCopyToBackend(draft.value)));
      send({ type: 'saved', id, revision: draft.revision, value });
      return value;
    } catch (error) {
      send({ type: 'saveFailed', id, error: message(error) });
      throw error;
    } finally { pending.current.delete(`save:${id}`); }
  }, [send]);

  const start = async (text: string, version: string, config: BackendConfig) => {
    if (current.current.activeJobId || pending.current.has('start')) throw new Error('An analysis is already running.');
    pending.current.add('start'); send({ type: 'starting', value: true });
    try { send({ type: 'started', job: await api.createJob(text, 'charilaos_mylonas', version, config) }); }
    finally { pending.current.delete('start'); send({ type: 'starting', value: false }); }
  };
  const analyzePosting = async (text: string, config: BackendConfig) => {
    if (pending.current.has('posting')) return;
    pending.current.add('posting');
    const base: ProcessingState = { jobId: null, status: 'processing', result: null, error: null,
      progress: 'Analyzing posting…', message: 'Posting preview only; no CV execution started.', jobAnalysis: null };
    send({ type: 'posting', value: base });
    try {
      const result = await api.analyzeJobOnly(text, config);
      send({ type: 'posting', value: { ...base, status: 'succeeded', progress: 'Posting preview complete', jobAnalysis: result.job_analysis } });
    } catch (error) {
      send({ type: 'posting', value: { ...base, status: 'failed', error: message(error) } });
      throw error;
    } finally { pending.current.delete('posting'); }
  };
  const cancel = async () => {
    const id = current.current.activeJobId;
    if (!id) return;
    try { send({ type: 'snapshot', job: await api.cancelJob(id) }); }
    catch (error) { send({ type: 'snapshot', job: await api.getJob(id) }); throw error; }
  };
  const render = async (id: string, options: RenderCVRequestPayload, fromDraft: boolean) => {
    const job = current.current.jobs[id];
    if (job?.status !== 'succeeded') throw new Error('Select a completed analysis first.');
    const copy = fromDraft ? await saveDraft(id) : null;
    const next = await api.renderJobArtifacts(id, { ...options,
      ...(copy ? { working_copy: api.transformWorkingCopyToBackend(copy) } : {}) });
    send({ type: 'snapshot', job: next });
  };
  const rescore = async (id: string, sectionIndex: number, indices?: number[]) => {
    const draft = current.current.drafts[id];
    if (!draft) throw new Error('Load the working copy first.');
    if (pending.current.has(`save:${id}`) || pending.current.has(`rescore:${id}`)) throw new Error('A draft operation is already in progress.');
    const section = draft.value.sections[sectionIndex];
    const selected = indices || section.items.map((_, index) => index);
    pending.current.add(`rescore:${id}`);
    try {
      const result = await api.rescoreWorkingCopyItems(id, { section_index: sectionIndex, item_indices: selected,
        items: selected.map(index => ({ index, text: section.items[index].text })) });
      send({ type: 'rescored', id, items: Object.fromEntries(result.items.map(item => [section.items[item.index].id, {
        scoredText: item.scored_text, relevanceScore: item.relevance_score,
        explanation: item.explanation, postingEvidence: item.posting_evidence,
      }])) });
    } finally { pending.current.delete(`rescore:${id}`); }
  };
  return {
    activeJob: state.activeJobId ? state.jobs[state.activeJobId] : null,
    viewedJob: state.viewedJobId ? state.jobs[state.viewedJobId] : null,
    draft: state.viewedJobId ? state.drafts[state.viewedJobId] : undefined,
    dirty: state.viewedJobId && state.drafts[state.viewedJobId] ? isDirty(state.drafts[state.viewedJobId]) : false,
    loadDraft, saveDraft, start, analyzePosting, cancel, render, rescore,
    editDraft: (value: WorkingCopy) => send({ type: 'edit', id: value.jobId, value }),
    updateDraft: (id: string, update: WorkingCopy | ((previous: WorkingCopy | null) => WorkingCopy | null)) => {
      const previous = current.current.drafts[id]?.value;
      const value = typeof update === 'function' ? update(previous || null) : update;
      if (value) send({ type: 'edit', id, value });
    },
    resetDraft: (id: string) => send({ type: 'reset', id }),
    viewJob: (job: ProcessingState) => send({ type: 'view', job }),
    exportJob: (id: string) => send({ type: 'export', id }),
  };
}
