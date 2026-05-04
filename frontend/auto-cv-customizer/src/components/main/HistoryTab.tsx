import React, { useState, useEffect } from 'react';
import { useAppState } from '../../contexts/AppStateContext';
import apiService from '../../services/api';
import './HistoryTab.css';

const HistoryTab: React.FC = () => {
  const { dispatch } = useAppState();
  const [jobs, setJobs] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const fetchJobs = async () => {
    try {
      setIsLoading(true);
      const data = await apiService.listJobs();
      // Sort by creation date descending
      const sortedJobs = data.sort((a: any, b: any) => 
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      );
      setJobs(sortedJobs);
    } catch (error) {
      console.error('Failed to fetch job history:', error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchJobs();
  }, []);

  const handleLoadJob = async (job: any) => {
    if (job.status !== 'succeeded') {
      alert(`This job cannot be loaded as its status is: ${job.status}`);
      return;
    }

    try {
      // Transform backend job to frontend processing state
      const processingState = apiService.transformJobToProcessingState(job);
      dispatch({ type: 'SET_PROCESSING_STATE', payload: processingState });
      dispatch({ type: 'SET_UI_STATE', payload: { activeTab: 'results' } });
    } catch (error) {
      console.error('Failed to load job results:', error);
      alert('Failed to load job results.');
    }
  };

  const handleDownload = async (jobId: string, artifact: any) => {
    try {
      await apiService.downloadArtifact(jobId, artifact.id, artifact.filename);
    } catch (error) {
      console.error('Download failed:', error);
      alert('Download failed.');
    }
  };

  const getStatusClass = (status: string) => {
    switch (status) {
      case 'succeeded': return 'status-succeeded';
      case 'failed': return 'status-failed';
      case 'processing': return 'status-processing';
      case 'cancelled': return 'status-cancelled';
      default: return '';
    }
  };

  if (isLoading) {
    return <div className="history-tab"><div className="loading">Loading job history...</div></div>;
  }

  return (
    <div className="history-tab">
      <div className="history-header">
        <h2>Analysis History</h2>
        <button className="btn btn-secondary" onClick={fetchJobs}>🔄 Refresh</button>
      </div>

      <div className="history-list">
        {jobs.length === 0 ? (
          <div className="no-jobs">
            <p>No previous analyses found. Start a new one in the Job Description tab!</p>
          </div>
        ) : (
          <table className="history-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Status</th>
                <th>Progress</th>
                <th>Overall Score</th>
                <th>Artifacts</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job) => (
                <tr key={job.id} className="history-row">
                  <td className="job-date">
                    {new Date(job.created_at).toLocaleString()}
                  </td>
                  <td>
                    <span className={`status-pill ${getStatusClass(job.status)}`}>
                      {job.status}
                    </span>
                  </td>
                  <td className="job-progress">{job.progress || '-'}</td>
                  <td className="job-score">
                    {job.result?.overall_score ? job.result.overall_score.toFixed(1) : '-'}
                  </td>
                  <td className="job-artifacts">
                    {job.result?.artifacts?.map((art: any) => (
                      <button 
                        key={art.id} 
                        className="btn-link"
                        onClick={() => handleDownload(job.id, art)}
                        title={`Download ${art.filename}`}
                      >
                        {art.kind === 'pdf' ? '📄' : '🛠️'}
                      </button>
                    ))}
                  </td>
                  <td className="job-actions">
                    <button 
                      className="btn btn-primary btn-sm"
                      onClick={() => handleLoadJob(job)}
                      disabled={job.status !== 'succeeded'}
                    >
                      View Results
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};

export default HistoryTab;
