import React, { useState, useEffect, useRef } from 'react';
import { useAppState } from '../../contexts/AppStateContext';
import apiService from '../../services/api';
import './ProcessingTab.css';

const ProcessingTab: React.FC = () => {
  const { state, dispatch } = useAppState();
  const [logs, setLogs] = useState<string[]>([]);
  const eventSourceRef = useRef<EventSource | null>(null);

  // Cleanup EventSource on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  const startProcessing = async () => {
    if (!state.currentJobDescriptionId) {
      alert('Please select or create a job description first');
      return;
    }

    const currentJob = state.jobDescriptions.find(j => j.id === state.currentJobDescriptionId);
    if (!currentJob) return;

    try {
      dispatch({ type: 'SET_UI_STATE', payload: { isLoading: true } });
      
      // Create job via API
      const processingState = await apiService.createJob(currentJob.content);
      
      dispatch({ 
        type: 'SET_PROCESSING_STATE', 
        payload: processingState
      });

      // Start listening to SSE stream
      startListeningToJob(processingState.jobId!);
      
    } catch (error) {
      console.error('Error starting processing:', error);
      dispatch({ 
        type: 'SET_PROCESSING_STATE', 
        payload: { 
          jobId: null,
          status: 'failed',
          progress: null,
          message: null,
          result: null,
          error: 'Failed to start processing'
        } 
      });
      dispatch({ type: 'SET_UI_STATE', payload: { isLoading: false } });
    }
  };

  const startListeningToJob = (jobId: string) => {
    // Close existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const eventSource = apiService.createJobStream(jobId);
    eventSourceRef.current = eventSource;

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setLogs(prev => [...prev, `${new Date().toLocaleTimeString()}: ${data.status} - ${data.progress || ''}`]);
      } catch (e) {
        console.error('Error parsing SSE message:', e);
      }
    };

    eventSource.addEventListener('job_update', (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
        dispatch({ 
          type: 'SET_PROCESSING_STATE', 
          payload: { 
            jobId,
            status: data.status,
            progress: data.progress,
            message: data.message,
            result: state.processingState?.result || null,
            error: null
          } 
        });
      } catch (e) {
        console.error('Error parsing job_update:', e);
      }
    });

    eventSource.addEventListener('job_complete', (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
        dispatch({ 
          type: 'SET_PROCESSING_STATE', 
          payload: { 
            jobId,
            status: data.status,
            progress: data.progress,
            message: data.message,
            result: data.result || null,
            error: data.error || null
          } 
        });

        if (data.status === 'succeeded') {
          dispatch({ type: 'SET_UI_STATE', payload: { activeTab: 'results', isLoading: false } });
        } else {
          dispatch({ type: 'SET_UI_STATE', payload: { isLoading: false } });
        }

        eventSource.close();
        eventSourceRef.current = null;
      } catch (e) {
        console.error('Error parsing job_complete:', e);
      }
    });

    eventSource.onerror = (error) => {
      console.error('SSE Error:', error);
      setLogs(prev => [...prev, `${new Date().toLocaleTimeString()}: Connection error`]);
      
      // Attempt to reconnect or poll as fallback
      setTimeout(() => {
        if (eventSourceRef.current === eventSource) {
          pollJobStatus(jobId);
        }
      }, 5000);
    };
  };

  const pollJobStatus = async (jobId: string) => {
    try {
      const status = await apiService.getJob(jobId);
      dispatch({ 
        type: 'SET_PROCESSING_STATE', 
        payload: { 
          ...state.processingState,
          ...status
        } 
      });

      setLogs(prev => [...prev, `${new Date().toLocaleTimeString()}: Status - ${status.status}`]);

      if (status.status === 'succeeded' || status.status === 'failed') {
        if (status.status === 'succeeded') {
          const result = await apiService.getJobResult(jobId);
          dispatch({ 
            type: 'SET_PROCESSING_STATE', 
            payload: { 
              ...state.processingState,
              result,
              status: 'succeeded'
            } 
          });
          dispatch({ type: 'SET_UI_STATE', payload: { activeTab: 'results' } });
        }
        dispatch({ type: 'SET_UI_STATE', payload: { isLoading: false } });
      } else {
        setTimeout(() => pollJobStatus(jobId), 2000);
      }
    } catch (error) {
      console.error('Error polling job status:', error);
      setLogs(prev => [...prev, `${new Date().toLocaleTimeString()}: Error polling status`]);
      setTimeout(() => pollJobStatus(jobId), 5000);
    }
  };

  const cancelJob = async () => {
    if (!state.processingState?.jobId) return;    
    try {
      await apiService.cancelJob(state.processingState.jobId);
      dispatch({ 
        type: 'SET_PROCESSING_STATE', 
        payload: { 
          ...state.processingState,
          status: 'cancelled'
        } 
      });
      
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    } catch (error) {
      console.error('Error cancelling job:', error);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'queued': return '#ffa500';
      case 'processing': return '#1e90ff';
      case 'succeeded': return '#32cd32';
      case 'failed': return '#ff0000';
      case 'cancelled': return '#808080';
      default: return '#000000';
    }
  };

  return (
    <div className="processing-tab">
      <div className="processing-header">
        <h2>CV Processing</h2>
        {!state.processingState && (
          <button 
            className="btn btn-primary"
            onClick={startProcessing}
            disabled={!state.currentJobDescriptionId || state.uiState.isLoading}
          >
            Start Processing
          </button>
        )}
      </div>

      {state.processingState && (
        <div className="processing-content">
          <div className="status-card">
            <div className="status-header">
              <h3>Job Status</h3>
              <span 
                className="status-badge"
                style={{ backgroundColor: getStatusColor(state.processingState.status) }}
              >
                {state.processingState.status}
              </span>
            </div>
             
            <div className="progress-bar-container">
              <div 
                className="progress-bar"
                style={{ 
                  width: state.processingState.status === 'succeeded' ? '100%' : 
                         state.processingState.status === 'processing' ? '60%' :
                         state.processingState.status === 'queued' ? '20%' : '0%'
                }}
              />
            </div>

            <div className="status-details">
              <p><strong>Progress:</strong> {state.processingState.progress || 'N/A'}</p>
              <p><strong>Message:</strong> {state.processingState.message || 'N/A'}</p>
              {state.processingState.error && (
                <p className="error"><strong>Error:</strong> {state.processingState.error}</p>
              )}
            </div>

            {state.processingState.status === 'queued' || state.processingState.status === 'processing' ? (
              <button className="btn btn-secondary" onClick={cancelJob}>
                Cancel Job
              </button>
            ) : null}
          </div>

          <div className="logs-section">
            <h3>Processing Logs</h3>
            <div className="logs-container">
              {logs.map((log, index) => (
                <div key={index} className="log-entry">{log}</div>
              ))}
              {logs.length === 0 && <p>No logs yet...</p>}
            </div>
          </div>

          {state.processingState.status === 'succeeded' && (
            <div className="success-actions">
              <button 
                className="btn btn-primary"
                onClick={() => dispatch({ type: 'SET_UI_STATE', payload: { activeTab: 'results' } })}
              >
                View Results →
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ProcessingTab;