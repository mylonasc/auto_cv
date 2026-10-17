import React, { useState, useEffect } from 'react';
import { useAppState, type WorkingCopy, type SectionFilterConfig } from '../../contexts/AppStateContext';
import apiService from '../../services/api';
import type { TemplateRegistryResponse } from '../../services/api';
import { applySectionFilter as filterSection } from '../../domain/selection';
import './ProcessingTab.css';

const ProcessingTab: React.FC = () => {
  const { state, dispatch, workflow } = useAppState();
  const { viewedJob, activeJob, draft, loadDraft } = workflow;
  const isProcessing = Boolean(activeJob || state.workflow.starting);
  const [isRendering, setIsRendering] = useState(false);
  const [templateRegistry, setTemplateRegistry] = useState<TemplateRegistryResponse>({
    cv_templates: {},
    motivation_letter_templates: {},
  });
  const [selectedTemplateId, setSelectedTemplateId] = useState('default_cv');


  // ── Working Copy State ──
  const localWorkingCopy = draft?.value || null;
  const isLoadingWorkingCopy = Boolean(viewedJob?.result && !draft);
  const isSavingWorkingCopy = draft?.saving || false;
  const [loadError, setLoadError] = useState<string | null>(null);
  const selectedId = viewedJob?.jobId;
  const setLocalWorkingCopy = (update: WorkingCopy | ((previous: WorkingCopy | null) => WorkingCopy | null)) => {
    if (selectedId) workflow.updateDraft(selectedId, update);
  };
  const [isRescoring, setIsRescoring] = useState(false);
  const [expandedAnalysis, setExpandedAnalysis] = useState<Set<string>>(new Set());

  const hasCvAnalysisResult = Boolean(viewedJob?.result);
  const displayState = activeJob || viewedJob;

  const startProcessing = async () => {
    const currentJob = state.jobDescriptions.find(j => j.id === state.currentJobDescriptionId);
    if (!currentJob) {
      alert('Please select a job description first');
      return;
    }

    try {
      await workflow.start(currentJob.content, state.currentCVVersionId || 'master', state.backendConfig);
    } catch (error) {
      console.error('Error starting job:', error);
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
      await workflow.analyzePosting(currentJob.content, state.backendConfig);
    } catch (error) {
      console.error('Error running job analysis:', error);
      alert('Failed to run job analysis.');
    }
  };

  const renderFromCurrentAnalysis = async () => {
    const jobId = viewedJob?.jobId;

    if (!jobId) {
      alert('No analysis jobs found. Run analysis first or load one from History.');
      return;
    }

    try {
      setIsRendering(true);
      await workflow.render(jobId, {
        min_relevance_score: state.backendConfig.rewritePolicy.minRelevanceScore,
        min_section_items_keep: state.backendConfig.rewritePolicy.minSectionItemsKeep,
        max_section_items_keep: state.backendConfig.rewritePolicy.maxSectionItemsKeep,
        cv_template_id: selectedTemplateId,
        cv_template_path: templateRegistry.cv_templates[selectedTemplateId],
        include_latex: state.backendConfig.outputs.includeLaTeX,
        render_pdf: state.backendConfig.outputs.renderPDF,
        include_scoring_comments: state.backendConfig.outputs.includeScoringComments,
      }, false);
      workflow.exportJob(jobId);
      dispatch({ type: 'SET_UI_STATE', payload: { showExportDialog: true } });
    } catch (error) {
      console.error('Error rendering artifacts:', error);
      alert('Failed to render artifacts from current analysis.');
    } finally {
      setIsRendering(false);
    }
  };

  // ── Working Copy Functions ──

  useEffect(() => {
    let disposed = false;
    setLoadError(null);
    if (selectedId && viewedJob?.status === 'succeeded') {
      void loadDraft(selectedId).catch(error => { if (!disposed) setLoadError(String(error)); });
    }
    return () => { disposed = true; };
  }, [selectedId, viewedJob?.status, loadDraft]);

  const applySectionFilter = (sectionIndex: number) => {
    if (!localWorkingCopy) return;
    try {
      const filtered = filterSection(localWorkingCopy.sections[sectionIndex]);
      setLocalWorkingCopy({ ...localWorkingCopy,
        sections: localWorkingCopy.sections.map((section, index) => index === sectionIndex ? filtered : section) });
    } catch (error) {
      alert(error instanceof Error ? error.message : 'Invalid filtering policy');
    }
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
      await workflow.saveDraft(localWorkingCopy.jobId);
    } catch (err) {
      console.error('Failed to save working copy:', err);
      alert('Failed to save working copy');
    }
  };

  const handleRescoreItem = async (sectionIndex: number, itemIndex: number) => {
    if (!localWorkingCopy) return;
    try {
      setIsRescoring(true);
      await workflow.rescore(localWorkingCopy.jobId, sectionIndex, [itemIndex]);
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
      await workflow.rescore(localWorkingCopy.jobId, sectionIndex);
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
      await workflow.render(localWorkingCopy.jobId, {
        min_relevance_score: 0,
        min_section_items_keep: 0,
        max_section_items_keep: 999,
        cv_template_id: selectedTemplateId,
        cv_template_path: templateRegistry.cv_templates[selectedTemplateId],
        include_latex: state.backendConfig.outputs.includeLaTeX,
        render_pdf: state.backendConfig.outputs.renderPDF,
        include_scoring_comments: state.backendConfig.outputs.includeScoringComments,
      }, true);
      workflow.exportJob(localWorkingCopy.jobId);
      dispatch({ type: 'SET_UI_STATE', payload: { showExportDialog: true } });
    } catch (error) {
      console.error('Error rendering from working copy:', error);
      alert('Failed to render from working copy.');
    } finally {
      setIsRendering(false);
    }
  };

  const cancelJob = async () => {
    try {
      await workflow.cancel();
    } catch (error: unknown) {
      console.error('Error cancelling job:', error);
      alert('Could not cancel; job status has been refreshed.');
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
            disabled={state.workflow.posting?.status === 'processing' || !state.currentJobDescriptionId}
          >
            {state.workflow.posting?.status === 'processing' ? 'Running...' : 'Run Job Analysis Only'}
          </button>
        </div>
        {state.workflow.posting && <section aria-label="Posting preview">
          <p role="status">Posting preview: {state.workflow.posting.status}</p>
          {state.workflow.posting.error && <p role="alert">{state.workflow.posting.error}</p>}
          {state.workflow.posting.jobAnalysis && <pre>{JSON.stringify(state.workflow.posting.jobAnalysis, null, 2)}</pre>}
        </section>}
      </div>

      <div className="rewrite-controls-card">
        <h3>Stage 2: CV Analysis + Personal Statement Selection</h3>
        <p className="hint">Run complete posting and CV analysis, statement optimization and configured initial outputs. Stage 1 is an optional preview, not a prerequisite.</p>
        <div className="processing-actions">
          {!activeJob ? (
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
        <p>Result working copy for job: {selectedId || 'none selected'}. Source CVs are edited separately in CV Data Editor.</p>
        {draft && <p role="status">{isSavingWorkingCopy ? 'Saving…' : workflow.dirty ? 'Unsaved changes' : 'All changes saved'}</p>}
        {(draft?.error || loadError) && <p role="alert">{draft?.error || loadError}</p>}
        {draft && <button className="btn btn-secondary" disabled={isSavingWorkingCopy} onClick={() => selectedId && workflow.resetDraft(selectedId)}>Reset to saved working copy</button>}

        {!hasCvAnalysisResult ? (
          <div className="workcpy-empty">
            <p>Run CV analysis (Stage 2) first to create an editable working copy.</p>
          </div>
        ) : loadError ? (
          <button onClick={() => selectedId && loadDraft(selectedId).then(() => setLoadError(null)).catch(error => setLoadError(String(error)))}>Retry loading working copy</button>
        ) : isLoadingWorkingCopy ? (
          <div className="workcpy-empty"><p>Loading working copy...</p></div>
        ) : localWorkingCopy ? (
          <>
            {/* ── Personal Statement Editor ── */}
            <div style={{ marginBottom: '16px' }}>
              <label style={{ fontWeight: 600, fontSize: '14px' }}>Personal Statement</label>
              <textarea
                className="workcpy-statement-textarea"
                aria-label="Working copy personal statement"
                value={localWorkingCopy.personalStatement}
                onChange={(e) => {
                  setLocalWorkingCopy({ ...localWorkingCopy, personalStatement: e.target.value });
                }}
              />
            </div>

            {/* ── Per-Section Editors ── */}
            {localWorkingCopy.sections.map((section, sIdx) => (
              <div key={section.id} className="workcpy-section-card">
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
                    <li key={item.id} className={`workcpy-item-row ${item.kept ? '' : 'removed'}`}>
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
                        {item.relevanceScore != null && item.scoredText !== item.text && ' (stale)'}
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
                if (selectedId) void loadDraft(selectedId).catch(error => setLoadError(String(error)));
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
              aria-label="CV template"
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

      {state.workflow.monitorError && <p role="alert">{state.workflow.monitorError}</p>}
      {displayState && (
        <div className="processing-content">
          <div className="status-card">
            <div className="status-header">
              <span className="status-label">Status:</span>
              <span 
                className={`status-badge ${displayState.status}`}
                style={{ backgroundColor: getStatusColor(displayState.status) }}
              >
                {displayState.status}
              </span>
            </div>
            
            <div className="progress-info">
              <div className="progress-message">{displayState.progress || 'Initializing...'}</div>
              <div className="detail-message">{displayState.message}</div>
            </div>

            {displayState.status === 'processing' && (
              <div className="loader-container">
                <div className="loader"></div>
              </div>
            )}
          </div>

          {displayState.error && (
            <div className="error-card">
              <h3>Error</h3>
              <p>{displayState.error}</p>
            </div>
          )}

          {displayState.jobAnalysis && (
            <div className="job-analysis-details">
              <h3>Job Posting Analysis Results</h3>
              <p className="hint">Extracting key information from the job posting to ground the CV customization.</p>
              
              <div className="analysis-grid">
                {displayState.jobAnalysis.industry_and_position_analysis && (
                  <div className="analysis-card">
                    <h4>Industry & Position</h4>
                    <div className="analysis-item">
                      <strong>Title:</strong> {displayState.jobAnalysis.industry_and_position_analysis.job_title}
                    </div>
                    <div className="analysis-item">
                      <strong>Company:</strong> {displayState.jobAnalysis.industry_and_position_analysis.company_name}
                    </div>
                    <div className="analysis-item">
                      <strong>Industry:</strong> {displayState.jobAnalysis.industry_and_position_analysis.industry}
                    </div>
                    <div className="skill-balance">
                      <div className="balance-row">
                        <span>Hands-on:</span>
                        <div className="mini-bar-bg"><div className="mini-bar-fill" style={{ width: `${(displayState.jobAnalysis.industry_and_position_analysis.hands_on_skills || 0) * 10}%` }}></div></div>
                      </div>
                      <div className="balance-row">
                        <span>Business:</span>
                        <div className="mini-bar-bg"><div className="mini-bar-fill" style={{ width: `${(displayState.jobAnalysis.industry_and_position_analysis.business_skills || 0) * 10}%` }}></div></div>
                      </div>
                    </div>
                  </div>
                )}

                {displayState.jobAnalysis.basic_analysis && (
                  <>
                    <div className="analysis-card">
                      <h4>Extracted Skills</h4>
                      {displayState.jobAnalysis.provenance?.skills?.status === 'fallback' && (
                        <p role="note">Heuristic fallback — {displayState.jobAnalysis.provenance.skills.reason}</p>
                      )}
                      <div className="tags-container">
                        {displayState.jobAnalysis.basic_analysis.skills?.split(';').map((s: string, i: number) => (
                          <span key={i} className="skill-tag">{s.trim()}</span>
                        ))}
                      </div>
                    </div>
                    <div className="analysis-card">
                      <h4>Qualifications</h4>
                      {displayState.jobAnalysis.provenance?.qualifications?.status === 'fallback' && (
                        <p role="note">Heuristic fallback — {displayState.jobAnalysis.provenance.qualifications.reason}</p>
                      )}
                      <ul className="qual-list">
                        {displayState.jobAnalysis.basic_analysis.qualifications?.split(';').map((q: string, i: number) => (
                          <li key={i}>{q.trim()}</li>
                        ))}
                      </ul>
                      {displayState.jobAnalysis.basic_analysis.preferred_qualifications && (
                        <>
                          <h5>Preferred</h5>
                          <ul className="qual-list preferred">
                            {displayState.jobAnalysis.basic_analysis.preferred_qualifications.split(';').map((q: string, i: number) => (
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

      {!displayState && !isProcessing && (
        <div className="no-processing">
          <p>Click "Start Processing" to begin AI analysis using version: <strong>{state.cvVersions.find(v => v.id === state.currentCVVersionId)?.name || state.currentCVVersionId}</strong></p>
        </div>
      )}
    </div>
  );
};

export default ProcessingTab;
