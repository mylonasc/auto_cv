import React from 'react';
import { useAppState } from '../../contexts/AppStateContext';
import './Sidebar.css';

const Sidebar: React.FC<{ sidebarCollapsed: boolean; onToggleSidebar: () => void }> = 
  ({ sidebarCollapsed, onToggleSidebar }) => {
  const { state, dispatch } = useAppState();

  const handleEditJob = (jobId: string, event: React.MouseEvent) => {
    event.stopPropagation();
    dispatch({ type: 'SET_CURRENT_JOB_DESCRIPTION', payload: jobId });
    dispatch({ type: 'SET_UI_STATE', payload: { activeTab: 'jobInput' } });
  };

  const handleDeleteJob = (jobId: string, event: React.MouseEvent) => {
    event.stopPropagation();
    const confirmed = window.confirm('Delete this saved job posting?');
    if (!confirmed) {
      return;
    }
    const updatedJobs = state.jobDescriptions.filter((job) => job.id !== jobId);
    dispatch({ type: 'SET_JOB_DESCRIPTIONS', payload: updatedJobs });
  };

  return (
    <aside className={`sidebar ${sidebarCollapsed ? 'collapsed' : ''}`}>
      <div className="sidebar-header">
        <h2>Navigation</h2>
        <button className="sidebar-close" onClick={onToggleSidebar} aria-label="Close sidebar">
          ✕
        </button>
      </div>
      
      <nav className="sidebar-nav">
        <ul>
          <li className={state.uiState.activeTab === 'jobInput' ? 'active' : ''}>
            <button onClick={() => dispatch({ type: 'SET_UI_STATE', payload: { activeTab: 'jobInput' } })}>
              <span className="nav-icon">📝</span>
              <span className="nav-text">Job Description</span>
            </button>
          </li>
          <li className={state.uiState.activeTab === 'processing' ? 'active' : ''}>
            <button onClick={() => dispatch({ type: 'SET_UI_STATE', payload: { activeTab: 'processing' } })}>
              <span className="nav-icon">⚙️</span>
              <span className="nav-text">Processing</span>
            </button>
          </li>
          <li className={state.uiState.activeTab === 'results' ? 'active' : ''}>
            <button onClick={() => dispatch({ type: 'SET_UI_STATE', payload: { activeTab: 'results' } })}>
              <span className="nav-icon">📊</span>
              <span className="nav-text">Results</span>
            </button>
          </li>
          <li className={state.uiState.activeTab === 'editor' ? 'active' : ''}>
            <button onClick={() => dispatch({ type: 'SET_UI_STATE', payload: { activeTab: 'editor' } })}>
              <span className="nav-icon">✏️</span>
              <span className="nav-text">Editor</span>
            </button>
          </li>
          <li className={state.uiState.activeTab === 'history' ? 'active' : ''}>
            <button onClick={() => dispatch({ type: 'SET_UI_STATE', payload: { activeTab: 'history' } })}>
              <span className="nav-icon">📜</span>
              <span className="nav-text">History</span>
            </button>
          </li>
        </ul>
      </nav>

      <div className="sidebar-section">
        <h3>Job Descriptions</h3>
        <button 
          className="sidebar-btn"
          onClick={() => dispatch({ type: 'SET_UI_STATE', payload: { showJobDescriptionManager: true } })}
        >
          + New Job
        </button>
        <div className="job-list">
          {state.jobDescriptions.map(job => (
            <div 
              key={job.id} 
              className={`job-item ${state.currentJobDescriptionId === job.id ? 'active' : ''}`}
              onClick={() => dispatch({ type: 'SET_CURRENT_JOB_DESCRIPTION', payload: job.id })}
            >
              <div className="job-item-header">
                <div className="job-title">{job.title || 'Untitled'}</div>
                <div className="job-item-actions">
                  <button
                    className="job-action-btn"
                    onClick={(event) => handleEditJob(job.id, event)}
                    title="Edit job"
                  >
                    ✏️
                  </button>
                  <button
                    className="job-action-btn delete"
                    onClick={(event) => handleDeleteJob(job.id, event)}
                    title="Delete job"
                  >
                    🗑️
                  </button>
                </div>
              </div>
              <div className="job-company">{job.company}</div>
              <div className="job-date">{new Date(job.createdAt).toLocaleDateString()}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="sidebar-section">
        <h3>Configuration</h3>
        <button 
          className="sidebar-btn"
          onClick={() => dispatch({ type: 'SET_UI_STATE', payload: { showConfigurationPanel: true } })}
        >
          ⚙️ Settings
        </button>
      </div>

      <div className="sidebar-footer">
        <div className="processing-status">
          {state.processingState && (
            <div className={`status-badge ${state.processingState.status}`}>
              {state.processingState.status}
            </div>
          )}
          <div className="current-version-tag">
            CV: {state.cvVersions.find(v => v.id === state.currentCVVersionId)?.name || state.currentCVVersionId}
          </div>
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
