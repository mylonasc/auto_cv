import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useAppState, type BackendJob, type WorkingCopy, type SectionFilterConfig } from '../../contexts/AppStateContext';
import apiService from '../../services/api';
import type { TemplateRegistryResponse } from '../../services/api';
import './ProcessingTab.css';

const ProcessingTab: React.FC = () => {
  const { state, dispatch } = useAppState();
  const [isProcessing, setIsProcessing] = useState(false);
  const [isRendering, setIsRendering] = useState(false);
  const [templateRegistry, setTemplateRegistry] = useState<TemplateRegistryResponse>({
    cv_templates: {},
    motivation_letter_templates: {},
  });
  const [selectedTemplateId, setSelectedTemplateId] = useState('default_cv');
  const eventSourceRef = useRef<EventSource | null>(null);
  const stage1ProgressTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);


  // ── Working Copy State ──
  const [localWorkingCopy, setLocalWorkingCopy] = useState<WorkingCopy | null>(null);
  const [isLoadingWorkingCopy, setIsLoadingWorkingCopy] = useState(false);
  const [isSavingWorkingCopy, setIsSavingWorkingCopy] = useState(false);
  const [isRescoring, setIsRescoring] = useState(false);
  const [expandedAnalysis, setExpandedAnalysis] = useState<Set<string>>(new Set());

  const hasCvAnalysisResult = Boolean(state.processingState?.result);

  const stopStage1ProgressTicker = () => {
    if (stage1ProgressTimerRef.current) {
      clearInterval(stage1ProgressTimerRef.current);
      stage1ProgressTimerRef.current = null;
    }
  };

  const startStage1ProgressTicker = () => {
    stopStage1ProgressTicker();
    const startedAt = Date.now();
    const messages = [
      'Preparing job analysis request...',
      'Extracting role and company context...',
      'Identifying required skills...',
      'Extracting qualifications and preferences...',
      'Finalizing structured analysis...',
    ];

    let index = 0;
    stage1ProgressTimerRef.current = setInterval(() => {
      const elapsedSeconds = Math.floor((Date.now() - startedAt) / 1000);
      const msg = `${messages[index % messages.length]} (${elapsedSeconds}s)`;
      dispatch({
        type: 'SET_PROCESSING_STATE',
        payload: {
          jobId: null,
          status: 'processing',
          progress: msg,
          message: 'Running Stage 1: Job analysis only',
          error: null,
          result: null,
          jobAnalysis: state.processingState?.jobAnalysis || null,
          lastSuccessfulJobId: state.processingState?.lastSuccessfulJobId || null,
        },
      });
      index += 1;
    }, 2000);
  };

  const startProcessing = async () => {
    const currentJob = state.jobDescriptions.find(j => j.id === state.currentJobDescriptionId);
    if (!currentJob) {
      alert('Please select a job description first');
      return;
    }

    try {
      setIsProcessing(true);
      const jobResponse = await apiService.createJob(
        currentJob.content, 
        'charilaos_mylonas',
        state.currentCVVersionId || 'master',
        state.backendConfig
      );

      dispatch({ 
        type: 'SET_PROCESSING_STATE', 
        payload: jobResponse 
      });

      startListeningToJob(jobResponse.jobId!);
    } catch (error) {
      console.error('Error starting job:', error);
      setIsProcessing(false);
      alert('Failed to start processing');
    }
  };

  const runJobAnalysisOnly = async () => {
    const currentJob = state.jobDescriptions.find(j => j.id === state.currentJobDescriptionId);
    if (!currentJob) {
      alert('Please select a job description first');
      return;
    }
    try {
      setIsProcessing(true);
      dispatch({
        type: 'SET_PROCESSING_STATE',
        payload: {
          jobId: null,
          status: 'processing',
          progress: 'Starting job analysis...',
          message: 'Running Stage 1: Job analysis only',
          result: null,
          jobAnalysis: state.processingState?.jobAnalysis || null,
          error: null,
          lastSuccessfulJobId: state.processingState?.lastSuccessfulJobId || null,
        },
      });
      startStage1ProgressTicker();

      const response = await apiService.analyzeJobOnly(currentJob.content, state.backendConfig);
      stopStage1ProgressTicker();
      dispatch({
        type: 'SET_PROCESSING_STATE',
        payload: {
          jobId: null,
          status: 'succeeded',
          progress: 'Job analysis complete',
          message: 'Job requirements extracted successfully',
          result: null,
          jobAnalysis: response.job_analysis,
          error: null,
          lastSuccessfulJobId: state.processingState?.lastSuccessfulJobId || null,
        },
      });
    } catch (error) {
      stopStage1ProgressTicker();
      console.error('Error running job analysis:', error);
      dispatch({
        type: 'SET_PROCESSING_STATE',
        payload: {
          jobId: null,
          status: 'failed',
          progress: 'Job analysis failed',
          message: 'Stage 1 failed before completion',
          result: null,
          jobAnalysis: state.processingState?.jobAnalysis || null,
          error: error instanceof Error ? error.message : 'Unknown error',
          lastSuccessfulJobId: state.processingState?.lastSuccessfulJobId || null,
        },
      });
      alert('Failed to run job analysis.');
    } finally {
      stopStage1ProgressTicker();
      setIsProcessing(false);
    }
  };

  const renderFromCurrentAnalysis = async () => {
    let jobId = state.processingState?.jobId || state.processingState?.lastSuccessfulJobId;

    if (!jobId) {
      try {
        const jobs = await apiService.listJobs();
        const latestSucceeded = [...jobs]
          .filter((j: BackendJob) => j.status === 'succeeded')
          .sort((a: BackendJob, b: BackendJob) => {
            const ta = new Date((a.updated_at || a.created_at || a.createdAt || 0) as string | number).getTime();
            const tb = new Date((b.updated_at || b.created_at || b.createdAt || 0) as string | number).getTime();
            return tb - ta;
          })[0];

        if (latestSucceeded?.id) {
          jobId = latestSucceeded.id;
          const stateFromHistory = apiService.transformJobToProcessingState(latestSucceeded);
          dispatch({ type: 'SET_PROCESSING_STATE', payload: stateFromHistory });
        }
      } catch (error) {
        console.error('Failed to load job history for rendering:', error);
      }
    }

    if (!jobId) {
      alert('No analysis jobs found. Run analysis first or load one from History.');
      return;
    }

    try {
      setIsRendering(true);
      const nextState = await apiService.renderJobArtifacts(jobId, {
        min_relevance_score: state.backendConfig.rewritePolicy.minRelevanceScore,
        min_section_items_keep: state.backendConfig.rewritePolicy.minSectionItemsKeep,
        max_section_items_keep: state.backendConfig.rewritePolicy.maxSectionItemsKeep,
        cv_template_id: selectedTemplateId,
        cv_template_path: templateRegistry.cv_templates[selectedTemplateId],
        include_latex: state.backendConfig.outputs.includeLaTeX,
        render_pdf: state.backendConfig.outputs.renderPDF,
      });
      dispatch({ type: 'SET_PROCESSING_STATE', payload: nextState });
      dispatch({ type: 'SET_UI_STATE', payload: { showExportDialog: true } });
    } catch (error) {
      console.error('Error rendering artifacts:', error);
      alert('Failed to render artifacts from current analysis.');
    } finally {
      setIsRendering(false);
    }
  };

  // ── Working Copy Functions ──

  const loadWorkingCopy = useCallback(async (jobId: string) => {
    try {
      setIsLoadingWorkingCopy(true);
      const data = await apiService.getWorkingCopy(jobId);
      const wc = apiService.transformWorkingCopyFromBackend(data as Record<string, unknown>);
      setLocalWorkingCopy(wc);
      dispatch({ type: 'SET_WORKING_COPY', payload: wc });
    } catch (err) {
      console.error('Failed to load working copy:', err);
    } finally {
      setIsLoadingWorkingCopy(false);
    }
  }, [dispatch]);

  // Auto-load working copy when analysis completes
  useEffect(() => {
    const jobId = state.processingState?.jobId || state.processingState?.lastSuccessfulJobId;
    if (jobId && state.processingState?.status === 'succeeded' && !localWorkingCopy) {
      loadWorkingCopy(jobId);
    }
  }, [state.processingState?.jobId, state.processingState?.status, state.processingState?.lastSuccessfulJobId, loadWorkingCopy, localWorkingCopy]);

  const applySectionFilter = (sectionIndex: number) => {
    setLocalWorkingCopy(prev => {
      if (!prev) return prev;
      const sections = prev.sections.map((s, si) => {
        if (si !== sectionIndex) return s;
        const fc = s.filterConfig;
        const scoredItems = s.items.map((it, ii) => ({ ...it, _origIdx: ii }));
        scoredItems.sort((a, b) => (b.relevanceScore ?? 0) - (a.relevanceScore ?? 0));

        let keptCount = 0;
        const keptFlags = new Array(s.items.length).fill(false);
        for (const sii of scoredItems) {
          const score = sii.relevanceScore ?? 0;
          if (keptCount < fc.minItemsKeep || (keptCount < fc.maxItemsKeep && score >= fc.minRelevanceScore)) {
            keptFlags[sii._origIdx] = true;
            keptCount++;
          }
        }

        return {
          ...s,
          items: s.items.map((it, ii) => ({ ...it, kept: keptFlags[ii] })),
        };
      });
      return { ...prev, sections };
    });
  };

  const toggleItem = (sectionIndex: number, itemIndex: number) => {
    setLocalWorkingCopy(prev => {
      if (!prev) return prev;
      const sections = prev.sections.map((s, si) => {
        if (si !== sectionIndex) return s;
        const items = s.items.map((it, ii) => (ii !== itemIndex ? it : { ...it, kept: !it.kept }));
        return { ...s, items };
      });
      return { ...prev, sections };
    });
  };

  const editItemText = (sectionIndex: number, itemIndex: number, text: string) => {
    setLocalWorkingCopy(prev => {
      if (!prev) return prev;
      const sections = prev.sections.map((s, si) => {
        if (si !== sectionIndex) return s;
        const items = s.items.map((it, ii) => (ii !== itemIndex ? it : { ...it, text }));
        return { ...s, items };
      });
      return { ...prev, sections };
    });
  };

  const updateSectionFilter = (sectionIndex: number, field: keyof SectionFilterConfig, value: number) => {
    setLocalWorkingCopy(prev => {
      if (!prev) return prev;
      const sections = prev.sections.map((s, si) => {
        if (si !== sectionIndex) return s;
        return { ...s, filterConfig: { ...s.filterConfig, [field]: value } };
      });
      return { ...prev, sections };
    });
  };

  const toggleAnalysis = (key: string) => {
    setExpandedAnalysis(prev => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const handleSaveWorkingCopy = async () => {
    if (!localWorkingCopy) return;
    try {
      setIsSavingWorkingCopy(true);
      const backendData = apiService.transformWorkingCopyToBackend(localWorkingCopy);
      await apiService.saveWorkingCopy(localWorkingCopy.jobId, backendData);
      dispatch({ type: 'SET_WORKING_COPY', payload: localWorkingCopy });
    } catch (err) {
      console.error('Failed to save working copy:', err);
      alert('Failed to save working copy');
    } finally {
      setIsSavingWorkingCopy(false);
    }
  };

  const handleRescoreItem = async (sectionIndex: number, itemIndex: number) => {
    if (!localWorkingCopy) return;
    try {
      setIsRescoring(true);
      const item = localWorkingCopy.sections[sectionIndex].items[itemIndex];
      const result = await apiService.rescoreWorkingCopyItems(localWorkingCopy.jobId, {
        section_index: sectionIndex,
        item_indices: [itemIndex],
        items: [{ index: itemIndex, text: item.text }],
      });
      if (result.items.length > 0) {
        const ri = result.items[0];
        setLocalWorkingCopy(prev => {
          if (!prev) return prev;
          const sections = prev.sections.map((s, si) => {
            if (si !== sectionIndex) return s;
            const items = s.items.map((it, ii) => {
              if (ii !== itemIndex) return it;
              return {
                ...it,
                relevanceScore: ri.relevance_score,
                explanation: ri.explanation,
                postingEvidence: ri.posting_evidence,
              };
            });
            return { ...s, items };
          });
          return { ...prev, sections };
        });
      }
    } catch (err) {
      console.error('Failed to rescore item:', err);
      alert('Failed to rescore item');
    } finally {
      setIsRescoring(false);
    }
  };

  const handleRescoreSection = async (sectionIndex: number) => {
    if (!localWorkingCopy) return;
    try {
      setIsRescoring(true);
      const section = localWorkingCopy.sections[sectionIndex];
      const items = section.items.map((it, ii) => ({ index: ii, text: it.text }));
      const result = await apiService.rescoreWorkingCopyItems(localWorkingCopy.jobId, {
        section_index: sectionIndex,
        item_indices: section.items.map((_, ii) => ii),
        items,
      });
      if (result.items.length > 0) {
        setLocalWorkingCopy(prev => {
          if (!prev) return prev;
          const sections = prev.sections.map((s, si) => {
            if (si !== sectionIndex) return s;
            const newItems = s.items.map((it, ii) => {
              const ri = result.items.find((r) => r.index === ii);
              if (!ri) return it;
              return {
                ...it,
                relevanceScore: ri.relevance_score,
                explanation: ri.explanation,
                postingEvidence: ri.posting_evidence,
              };
            });
            return { ...s, items: newItems };
          });
          return { ...prev, sections };
        });
      }
    } catch (err) {
      console.error('Failed to rescore section:', err);
      alert('Failed to rescore section');
    } finally {
      setIsRescoring(false);
    }
  };

  const renderFromWorkingCopy = async () => {
    if (!localWorkingCopy) {
      alert('No working copy to render from. Load or create one first.');
      return;
    }
    if (!localWorkingCopy.jobId) {
      alert('No job ID associated with this working copy.');
      return;
    }

    try {
      setIsRendering(true);
      await handleSaveWorkingCopy();
      const backendWC = apiService.transformWorkingCopyToBackend(localWorkingCopy);
      const nextState = await apiService.renderJobArtifacts(localWorkingCopy.jobId, {
        min_relevance_score: 0,
        min_section_items_keep: 0,
        max_section_items_keep: 999,
        cv_template_id: selectedTemplateId,
        cv_template_path: templateRegistry.cv_templates[selectedTemplateId],
        include_latex: state.backendConfig.outputs.includeLaTeX,
        render_pdf: state.backendConfig.outputs.renderPDF,
        working_copy: backendWC as Record<string, unknown>,
      });
      dispatch({ type: 'SET_PROCESSING_STATE', payload: nextState });
      dispatch({ type: 'SET_UI_STATE', payload: { showExportDialog: true } });
    } catch (error) {
      console.error('Error rendering from working copy:', error);
      alert('Failed to render from working copy.');
    } finally {
      setIsRendering(false);
    }
  };

  const startListeningToJob = (jobId: string) => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const eventSource = apiService.createJobStream(jobId);
    eventSourceRef.current = eventSource;

    eventSource.addEventListener('job_update', (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
        const processingState = apiService.transformJobToProcessingState(data);
        dispatch({ 
          type: 'SET_PROCESSING_STATE', 
          payload: { 
            ...processingState,
            result: state.processingState?.result || processingState.result
          } 
        });
      } catch (e) {
        console.error('Error parsing job_update:', e);
      }
    });

    eventSource.addEventListener('job_complete', (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
        const processingState = apiService.transformJobToProcessingState(data);
        
        dispatch({ 
          type: 'SET_PROCESSING_STATE', 
          payload: processingState
        });

        if (data.status === 'succeeded') {
          dispatch({ type: 'SET_UI_STATE', payload: { activeTab: 'results', isLoading: false } });
        } else {
          dispatch({ type: 'SET_UI_STATE', payload: { isLoading: false } });
        }

        eventSource.close();
        eventSourceRef.current = null;
        setIsProcessing(false);
      } catch (e) {
        console.error('Error parsing job_complete:', e);
      }
    });

    eventSource.onerror = (err) => {
      console.error('SSE Error:', err);
      eventSource.close();
      eventSourceRef.current = null;
      setIsProcessing(false);
    };
  };

  const cancelJob = async () => {
    if (!state.processingState?.jobId) return;
    try {
      await apiService.cancelJob(state.processingState.jobId);
      dispatch({
        type: 'SET_PROCESSING_STATE',
        payload: {
          ...state.processingState,
          status: 'cancelled',
          message: 'Job was cancelled by user'
        }
      });

      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      setIsProcessing(false);
    } catch (error: unknown) {
      console.error('Error cancelling job:', error);
      if (typeof error === 'object' && error !== null && 'response' in error &&
          typeof (error as { response?: { status?: number } }).response?.status === 'number' &&
          (error as { response?: { status?: number } }).response?.status === 400) {
        try {
          const job = await apiService.getJob(state.processingState.jobId);
          dispatch({ type: 'SET_PROCESSING_STATE', payload: job });
          if (job.status === 'succeeded') {
            dispatch({ type: 'SET_UI_STATE', payload: { activeTab: 'results' } });
          }
        } catch (e) {
          console.error('Error fetching job after cancel failure:', e);
        }
      }
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'queued': return '#ffa500';
      case 'processing': return '#1e90ff';
      case 'succeeded': return '#32cd32';
      case 'failed': return '#ff4500';
      case 'cancelled': return '#808080';
      default: return '#000';
    }
  };

  useEffect(() => {
    const loadTemplates = async () => {
      try {
        const registry = await apiService.getTemplateRegistry();
        setTemplateRegistry(registry);
        if (Object.keys(registry.cv_templates).length > 0 && !registry.cv_templates[selectedTemplateId]) {
          setSelectedTemplateId(Object.keys(registry.cv_templates)[0]);
        }
      } catch (error) {
        console.error('Failed to load template registry:', error);
      }
    };
    loadTemplates();

    return () => {
      stopStage1ProgressTicker();
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, [selectedTemplateId]);

  return (
    <div className="processing-tab">
      <div className="processing-header">
        <h2>Guided CV Workflow</h2>
      </div>

      <div className="rewrite-controls-card">
        <h3>Stage 1: Job Analysis</h3>
        <p className="hint">Analyze the selected job posting and extract requirements.</p>
        <div className="processing-actions">
          <button
            className="btn btn-primary"
            onClick={runJobAnalysisOnly}
            disabled={isProcessing || !state.currentJobDescriptionId}
          >
            {isProcessing ? 'Running...' : 'Run Job Analysis Only'}
          </button>
        </div>
      </div>

      <div className="rewrite-controls-card">
        <h3>Stage 2: CV Analysis + Personal Statement Selection</h3>
        <p className="hint">Run this after Stage 1 to produce section/bullet relevance scores and statement optimization.</p>
        <div className="processing-actions">
          {!state.processingState || ['succeeded', 'failed', 'cancelled'].includes(state.processingState.status) ? (
            <button
              className="btn btn-primary"
              onClick={startProcessing}
              disabled={isProcessing || !state.currentJobDescriptionId}
            >
              {isProcessing ? 'Initializing...' : 'Run CV Analysis'}
            </button>
          ) : (
            <button className="btn btn-danger" onClick={cancelJob}>
              Cancel Running Analysis
            </button>
          )}
            <button
              className="btn btn-secondary"
              onClick={() => dispatch({ type: 'SET_UI_STATE', payload: { activeTab: 'results' } })}
              disabled={!hasCvAnalysisResult}
            >
              Open Analysis Results
            </button>
        </div>
      </div>

      <div className="rewrite-controls-card">
        <h3>Stage 3: Edit & Review CV (Working Copy)</h3>
        <p className="hint">Edit the AI-rewritten personal statement, toggle/adjust bullet points, and set per-section filters before rendering.</p>

        {!hasCvAnalysisResult ? (
          <div className="workcpy-empty">
            <p>Run CV analysis (Stage 2) first to create an editable working copy.</p>
          </div>
        ) : isLoadingWorkingCopy ? (
          <div className="workcpy-empty"><p>Loading working copy...</p></div>
        ) : localWorkingCopy ? (
          <>
            {/* ── Personal Statement Editor ── */}
            <div style={{ marginBottom: '16px' }}>
              <label style={{ fontWeight: 600, fontSize: '14px' }}>Personal Statement</label>
              <textarea
                className="workcpy-statement-textarea"
                value={localWorkingCopy.personalStatement}
                onChange={(e) => {
                  setLocalWorkingCopy({ ...localWorkingCopy, personalStatement: e.target.value });
                }}
              />
            </div>

            {/* ── Per-Section Editors ── */}
            {localWorkingCopy.sections.map((section, sIdx) => (
              <div key={sIdx} className="workcpy-section-card">
                <div className="workcpy-section-header">
                  <span>{section.company} — {section.position}</span>
                  <span className="workcpy-section-score">
                    {section.duration} · Score: {section.sectionScore != null ? Number(section.sectionScore).toFixed(1) : 'N/A'}/10
                  </span>
                  <button
                    className="workcpy-btn-link"
                    onClick={() => toggleAnalysis(`section-${sIdx}`)}
                    title="Show/hide LLM analysis for this section"
                  >
                    {expandedAnalysis.has(`section-${sIdx}`) ? 'Hide Analysis' : 'Show Analysis'}
                  </button>
                </div>

                {/* Section analysis panel */}
                {expandedAnalysis.has(`section-${sIdx}`) && (
                  <div className="workcpy-analysis-panel">
                    {section.sectionExplanation && (
                      <div className="workcpy-analysis-field">
                        <strong>Explanation:</strong>
                        <p>{section.sectionExplanation}</p>
                      </div>
                    )}
                    {section.sectionPostingEvidence && (
                      <div className="workcpy-analysis-field">
                        <strong>Posting Evidence:</strong>
                        <p>{section.sectionPostingEvidence}</p>
                      </div>
                    )}
                    {!section.sectionExplanation && !section.sectionPostingEvidence && (
                      <p className="workcpy-analysis-empty">No analysis data available for this section.</p>
                    )}
                  </div>
                )}

                {/* Per-section filter controls */}
                <div className="workcpy-filter-row">
                  <label>
                    Min score:
                    <input
                      type="number" min={0} max={10}
                      value={section.filterConfig.minRelevanceScore}
                      onChange={(e) => updateSectionFilter(sIdx, 'minRelevanceScore', parseInt(e.target.value, 10) || 0)}
                    />
                  </label>
                  <label>
                    Min items:
                    <input
                      type="number" min={0} max={20}
                      value={section.filterConfig.minItemsKeep}
                      onChange={(e) => updateSectionFilter(sIdx, 'minItemsKeep', parseInt(e.target.value, 10) || 0)}
                    />
                  </label>
                  <label>
                    Max items:
                    <input
                      type="number" min={0} max={20}
                      value={section.filterConfig.maxItemsKeep}
                      onChange={(e) => updateSectionFilter(sIdx, 'maxItemsKeep', parseInt(e.target.value, 10) || 0)}
                    />
                  </label>
                  <button
                    className="workcpy-btn-small"
                    onClick={() => applySectionFilter(sIdx)}
                    style={{ background: 'var(--primary-color)', color: 'white', borderColor: 'var(--primary-color)' }}
                  >
                    Apply Filter
                  </button>
                </div>

                {/* Items */}
                <ul className="workcpy-items-list">
                  {section.items.map((item, iIdx) => (
                    <li key={iIdx} className={`workcpy-item-row ${item.kept ? '' : 'removed'}`}>
                      <input
                        type="checkbox"
                        className="workcpy-item-checkbox"
                        checked={item.kept}
                        onChange={() => toggleItem(sIdx, iIdx)}
                      />
                      <textarea
                        className="workcpy-item-text"
                        value={item.text}
                        onChange={(e) => editItemText(sIdx, iIdx, e.target.value)}
                        rows={Math.max(2, Math.ceil(item.text.length / 60))}
                      />
                      <span className="workcpy-item-score">
                        {item.relevanceScore != null ? `${Number(item.relevanceScore).toFixed(1)}` : 'N/A'}
                      </span>
                      <div className="workcpy-item-actions">
                        <button
                          className="workcpy-btn-small"
                          onClick={() => handleRescoreItem(sIdx, iIdx)}
                          disabled={isRescoring}
                          title="Re-run AI scoring on this bullet"
                        >
                          Rescore
                        </button>
                        <button
                          className="workcpy-btn-link"
                          onClick={() => toggleAnalysis(`item-${sIdx}-${iIdx}`)}
                          title="Show/hide LLM analysis for this bullet"
                        >
                          {expandedAnalysis.has(`item-${sIdx}-${iIdx}`) ? 'Hide' : 'Analysis'}
                        </button>
                      </div>
                      {/* Item analysis panel */}
                      {expandedAnalysis.has(`item-${sIdx}-${iIdx}`) && (
                        <div className="workcpy-analysis-panel inline">
                          {item.explanation && (
                            <div className="workcpy-analysis-field">
                              <strong>Explanation:</strong>
                              <p>{item.explanation}</p>
                            </div>
                          )}
                          {item.postingEvidence && (
                            <div className="workcpy-analysis-field">
                              <strong>Posting Evidence:</strong>
                              <p>{item.postingEvidence}</p>
                            </div>
                          )}
                          {!item.explanation && !item.postingEvidence && (
                            <p className="workcpy-analysis-empty">No analysis data available for this bullet.</p>
                          )}
                        </div>
                      )}
                    </li>
                  ))}
                </ul>

                {/* Section-level actions */}
                <div className="workcpy-section-actions">
                  <button
                    className="workcpy-btn-small"
                    onClick={() => handleRescoreSection(sIdx)}
                    disabled={isRescoring}
                  >
                    Rescore All Items in Section
                  </button>
                </div>
              </div>
            ))}

            {/* ── Working Copy Action Buttons ── */}
            <div className="workcpy-editor-actions">
              <button
                className="btn btn-primary"
                onClick={handleSaveWorkingCopy}
                disabled={isSavingWorkingCopy}
              >
                {isSavingWorkingCopy ? 'Saving...' : 'Save Working Copy'}
              </button>
              <button
                className="btn btn-primary"
                onClick={renderFromWorkingCopy}
                disabled={isRendering}
                style={{ background: 'var(--success-color, #2e7d32)' }}
              >
                {isRendering ? 'Rendering...' : 'Render CV from Working Copy'}
              </button>
              <button
                className="btn btn-secondary"
                onClick={() => dispatch({ type: 'SET_UI_STATE', payload: { activeTab: 'results' } })}
              >
                Inspect Scores & Explanations
              </button>
            </div>
          </>
        ) : (
          <div className="workcpy-empty">
            <p>Working copy not loaded.</p>
            <button
              className="btn btn-secondary"
              onClick={() => {
                const jobId = state.processingState?.jobId || state.processingState?.lastSuccessfulJobId;
                if (jobId) loadWorkingCopy(jobId);
              }}
              disabled={isLoadingWorkingCopy}
            >
              {isLoadingWorkingCopy ? 'Loading...' : 'Load Working Copy'}
            </button>
          </div>
        )}
      </div>

      <div className="rewrite-controls-card">
        <h3>Stage 4: CV PDF Rendering</h3>
        <p className="hint">Render new artifacts from existing analysis using current filtering and selected template.</p>
        <div className="rewrite-controls-grid">
          <label>
            CV template
            <select
              value={selectedTemplateId}
              onChange={(e) => setSelectedTemplateId(e.target.value)}
            >
              {Object.keys(templateRegistry.cv_templates).map((templateId) => (
                <option key={templateId} value={templateId}>{templateId}</option>
              ))}
            </select>
          </label>
        </div>
        <div style={{ marginTop: '12px' }}>
          <button
            className="btn btn-primary"
            onClick={renderFromCurrentAnalysis}
            disabled={isRendering || !hasCvAnalysisResult}
          >
            {isRendering ? 'Rendering...' : 'Render CV Artifacts'}
          </button>
        </div>
      </div>

      {state.processingState && (
        <div className="processing-content">
          <div className="status-card">
            <div className="status-header">
              <span className="status-label">Status:</span>
              <span 
                className={`status-badge ${state.processingState.status}`}
                style={{ backgroundColor: getStatusColor(state.processingState.status) }}
              >
                {state.processingState.status}
              </span>
            </div>
            
            <div className="progress-info">
              <div className="progress-message">{state.processingState.progress || 'Initializing...'}</div>
              <div className="detail-message">{state.processingState.message}</div>
            </div>

            {state.processingState.status === 'processing' && (
              <div className="loader-container">
                <div className="loader"></div>
              </div>
            )}
          </div>

          {state.processingState.error && (
            <div className="error-card">
              <h3>Error</h3>
              <p>{state.processingState.error}</p>
            </div>
          )}

          {state.processingState.jobAnalysis && (
            <div className="job-analysis-details">
              <h3>Job Posting Analysis Results</h3>
              <p className="hint">Extracting key information from the job posting to ground the CV customization.</p>
              
              <div className="analysis-grid">
                {state.processingState.jobAnalysis.industry_and_position_analysis && (
                  <div className="analysis-card">
                    <h4>Industry & Position</h4>
                    <div className="analysis-item">
                      <strong>Title:</strong> {state.processingState.jobAnalysis.industry_and_position_analysis.job_title}
                    </div>
                    <div className="analysis-item">
                      <strong>Company:</strong> {state.processingState.jobAnalysis.industry_and_position_analysis.company_name}
                    </div>
                    <div className="analysis-item">
                      <strong>Industry:</strong> {state.processingState.jobAnalysis.industry_and_position_analysis.industry}
                    </div>
                    <div className="skill-balance">
                      <div className="balance-row">
                        <span>Hands-on:</span>
                        <div className="mini-bar-bg"><div className="mini-bar-fill" style={{ width: `${(state.processingState.jobAnalysis.industry_and_position_analysis.hands_on_skills || 0) * 10}%` }}></div></div>
                      </div>
                      <div className="balance-row">
                        <span>Business:</span>
                        <div className="mini-bar-bg"><div className="mini-bar-fill" style={{ width: `${(state.processingState.jobAnalysis.industry_and_position_analysis.business_skills || 0) * 10}%` }}></div></div>
                      </div>
                    </div>
                  </div>
                )}

                {state.processingState.jobAnalysis.basic_analysis && (
                  <>
                    <div className="analysis-card">
                      <h4>Extracted Skills</h4>
                      <div className="tags-container">
                        {state.processingState.jobAnalysis.basic_analysis.skills?.split(';').map((s: string, i: number) => (
                          <span key={i} className="skill-tag">{s.trim()}</span>
                        ))}
                      </div>
                    </div>
                    <div className="analysis-card">
                      <h4>Qualifications</h4>
                      <ul className="qual-list">
                        {state.processingState.jobAnalysis.basic_analysis.qualifications?.split(';').map((q: string, i: number) => (
                          <li key={i}>{q.trim()}</li>
                        ))}
                      </ul>
                      {state.processingState.jobAnalysis.basic_analysis.preferred_qualifications && (
                        <>
                          <h5>Preferred</h5>
                          <ul className="qual-list preferred">
                            {state.processingState.jobAnalysis.basic_analysis.preferred_qualifications.split(';').map((q: string, i: number) => (
                              <li key={i}>{q.trim()}</li>
                            ))}
                          </ul>
                        </>
                      )}
                    </div>
                  </>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {!state.processingState && !isProcessing && (
        <div className="no-processing">
          <p>Click "Start Processing" to begin AI analysis using version: <strong>{state.cvVersions.find(v => v.id === state.currentCVVersionId)?.name || state.currentCVVersionId}</strong></p>
        </div>
      )}
    </div>
  );
};

export default ProcessingTab;
