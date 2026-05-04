import React, { useState, useEffect, useRef } from 'react';
import { useAppState } from '../../contexts/AppStateContext';
import apiService from '../../services/api';
import './ProcessingTab.css';

const ProcessingTab: React.FC = () => {
  const { state, dispatch } = useAppState();
  const [isProcessing, setIsProcessing] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);

  const updateRewritePolicy = (field: 'minRelevanceScore' | 'minSectionItemsKeep' | 'maxSectionItemsKeep', value: number) => {
    const safeValue = Number.isFinite(value) ? value : 0;
    const current = state.backendConfig.rewritePolicy;
    const next = {
      ...current,
      [field]: safeValue,
    };

    if (field === 'minSectionItemsKeep' && safeValue > next.maxSectionItemsKeep) {
      next.maxSectionItemsKeep = safeValue;
    }
    if (field === 'maxSectionItemsKeep' && safeValue < next.minSectionItemsKeep) {
      next.minSectionItemsKeep = safeValue;
    }

    dispatch({
      type: 'SET_BACKEND_CONFIG',
      payload: {
        ...state.backendConfig,
        rewritePolicy: next,
      },
    });
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
    } catch (error: any) {
      console.error('Error cancelling job:', error);
      if (error.response?.status === 400) {
        try {
          const job = await apiService.getJob(state.processingState.jobId);
          const processingState = apiService.transformJobToProcessingState(job);
          dispatch({ type: 'SET_PROCESSING_STATE', payload: processingState });
          if (processingState.status === 'succeeded') {
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
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  return (
    <div className="processing-tab">
      <div className="processing-header">
        <h2>CV Processing</h2>
        <div className="processing-actions">
          {!state.processingState || ['succeeded', 'failed', 'cancelled'].includes(state.processingState.status) ? (
            <button 
              className="btn btn-primary"
              onClick={startProcessing}
              disabled={isProcessing || !state.currentJobDescriptionId}
            >
              {isProcessing ? 'Initializing...' : 'Start Processing'}
            </button>
          ) : (
            <button className="btn btn-danger" onClick={cancelJob}>
              Cancel Job
            </button>
          )}
        </div>
      </div>

      <div className="rewrite-controls-card">
        <h3>Rewrite Cut-offs</h3>
        <p className="hint">These values apply to the next processing run.</p>
        <div className="rewrite-controls-grid">
          <label>
            Minimum relevance score
            <input
              type="number"
              min={0}
              max={10}
              value={state.backendConfig.rewritePolicy.minRelevanceScore}
              onChange={(e) => updateRewritePolicy('minRelevanceScore', parseInt(e.target.value, 10))}
            />
          </label>
          <label>
            Minimum bullets per section
            <input
              type="number"
              min={0}
              max={20}
              value={state.backendConfig.rewritePolicy.minSectionItemsKeep}
              onChange={(e) => updateRewritePolicy('minSectionItemsKeep', parseInt(e.target.value, 10))}
            />
          </label>
          <label>
            Maximum bullets per section
            <input
              type="number"
              min={0}
              max={20}
              value={state.backendConfig.rewritePolicy.maxSectionItemsKeep}
              onChange={(e) => updateRewritePolicy('maxSectionItemsKeep', parseInt(e.target.value, 10))}
            />
          </label>
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
                        <div className="mini-bar-bg"><div className="mini-bar-fill" style={{ width: `${state.processingState.jobAnalysis.industry_and_position_analysis.hands_on_skills * 10}%` }}></div></div>
                      </div>
                      <div className="balance-row">
                        <span>Business:</span>
                        <div className="mini-bar-bg"><div className="mini-bar-fill" style={{ width: `${state.processingState.jobAnalysis.industry_and_position_analysis.business_skills * 10}%` }}></div></div>
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
