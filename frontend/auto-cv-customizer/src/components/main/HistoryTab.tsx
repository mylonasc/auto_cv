import React, { useState, useEffect, useMemo } from 'react';
import { useAppState, type BackendJob, type Artifact } from '../../contexts/AppStateContext';
import apiService from '../../services/api';
import PdfPreviewModal from '../common/PdfPreviewModal';
import './HistoryTab.css';

type JobSort = 'created_desc' | 'created_asc' | 'score_desc' | 'score_asc' | 'status';

const HistoryTab: React.FC = () => {
  const { dispatch } = useAppState();
  const [jobs, setJobs] = useState<BackendJob[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [sortBy, setSortBy] = useState<JobSort>('created_desc');
  const [showArchived, setShowArchived] = useState(false);
  const [mutatingJobId, setMutatingJobId] = useState<string | null>(null);
  const [expandedJobId, setExpandedJobId] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewTitle, setPreviewTitle] = useState<string>('PDF Preview');

  const getJobTitle = (job: BackendJob): string =>
    job?.job_analysis?.industry_and_position_analysis?.job_title || '';

  const getCompanyName = (job: BackendJob): string =>
    job?.job_analysis?.industry_and_position_analysis?.company_name || '';

  const getCreatedTimestamp = (job: BackendJob): number =>
    new Date(job.created_at || job.createdAt || 0).getTime();

  const getOverallScore = (job: BackendJob): number => {
    const score = job?.result?.overall_score;
    return typeof score === 'number' ? score : -1;
  };

  const getJobDescription = (job: BackendJob): string =>
    typeof job?.job_description === 'string' ? job.job_description : '';

  const fetchJobs = async () => {
    try {
      setIsLoading(true);
      const data = await apiService.listJobs();
      setJobs(data);
    } catch (error) {
      console.error('Failed to fetch job history:', error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchJobs();
  }, []);

  const handleLoadJob = async (job: BackendJob) => {
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

  const handleDownload = async (jobId: string, artifact: Artifact) => {
    try {
      await apiService.downloadArtifact(jobId, artifact.id, artifact.filename);
    } catch (error) {
      console.error('Download failed:', error);
      alert('Download failed.');
    }
  };

  const handlePreview = (jobId: string, artifactId: string, filename: string) => {
    setPreviewUrl(apiService.getArtifactPreviewUrl(jobId, artifactId));
    setPreviewTitle(filename || 'PDF Preview');
  };

  const handleArchiveToggle = async (job: BackendJob) => {
    try {
      setMutatingJobId(job.id);
      if (job.archived) {
        await apiService.unarchiveJob(job.id);
      } else {
        await apiService.archiveJob(job.id);
      }
      await fetchJobs();
    } catch (error) {
      console.error('Failed to update archive status:', error);
      alert('Failed to update archive status.');
    } finally {
      setMutatingJobId(null);
    }
  };

  const handleDelete = async (job: BackendJob) => {
    const confirmed = window.confirm('Delete this analysis permanently? This action cannot be undone.');
    if (!confirmed) {
      return;
    }
    try {
      setMutatingJobId(job.id);
      await apiService.deleteJob(job.id);
      await fetchJobs();
    } catch (error) {
      console.error('Failed to delete analysis:', error);
      alert('Failed to delete analysis.');
    } finally {
      setMutatingJobId(null);
    }
  };

  const visibleJobs = useMemo(() => {
    const query = searchTerm.trim().toLowerCase();

    const filtered = jobs.filter((job) => {
      const isArchived = !!job.archived;
      if (!showArchived && isArchived) {
        return false;
      }

      if (statusFilter !== 'all' && job.status !== statusFilter) {
        return false;
      }

      if (!query) {
        return true;
      }

      const companyName = getCompanyName(job).toLowerCase();
      const jobTitle = getJobTitle(job).toLowerCase();
      return companyName.includes(query) || jobTitle.includes(query);
    });

    filtered.sort((a, b) => {
      if (sortBy === 'created_asc') {
        return getCreatedTimestamp(a) - getCreatedTimestamp(b);
      }
      if (sortBy === 'created_desc') {
        return getCreatedTimestamp(b) - getCreatedTimestamp(a);
      }
      if (sortBy === 'score_asc') {
        return getOverallScore(a) - getOverallScore(b);
      }
      if (sortBy === 'score_desc') {
        return getOverallScore(b) - getOverallScore(a);
      }
      return (a.status || '').localeCompare(b.status || '');
    });

    return filtered;
  }, [jobs, searchTerm, statusFilter, showArchived, sortBy]);

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

      <div className="history-controls">
        <input
          type="text"
          className="history-search"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          placeholder="Search by company or job title"
        />
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="all">All statuses</option>
          <option value="queued">Queued</option>
          <option value="processing">Processing</option>
          <option value="succeeded">Succeeded</option>
          <option value="failed">Failed</option>
          <option value="cancelled">Cancelled</option>
        </select>
        <select value={sortBy} onChange={(e) => setSortBy(e.target.value as JobSort)}>
          <option value="created_desc">Newest first</option>
          <option value="created_asc">Oldest first</option>
          <option value="score_desc">Top score first</option>
          <option value="score_asc">Lowest score first</option>
          <option value="status">Status (A-Z)</option>
        </select>
        <label className="archived-toggle">
          <input
            type="checkbox"
            checked={showArchived}
            onChange={(e) => setShowArchived(e.target.checked)}
          />
          Show archived
        </label>
      </div>

      <div className="history-meta">
        Showing {visibleJobs.length} of {jobs.length} analyses
      </div>

      <div className="history-list">
        {visibleJobs.length === 0 ? (
          <div className="no-jobs">
            <p>No analyses match the selected filters.</p>
          </div>
        ) : (
          <table className="history-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Company</th>
                <th>Job Title</th>
                <th>Job Posting</th>
                <th>Status</th>
                <th>Progress</th>
                <th>Overall Score</th>
                <th>Artifacts</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {visibleJobs.map((job) => (
                <tr key={job.id} className={`history-row ${job.archived ? 'archived' : ''}`}>
                  <td className="job-date">
                    {job.created_at || job.createdAt
                      ? new Date((job.created_at || job.createdAt) as string).toLocaleString()
                      : '-'}
                  </td>
                  <td className="job-company">{getCompanyName(job) || '-'}</td>
                  <td className="job-title">{getJobTitle(job) || '-'}</td>
                  <td className="job-posting">
                    {getJobDescription(job) ? (
                      <>
                        <div className={`job-posting-preview ${expandedJobId === job.id ? 'expanded' : ''}`}>
                          {expandedJobId === job.id
                            ? getJobDescription(job)
                            : `${getJobDescription(job).slice(0, 180)}${getJobDescription(job).length > 180 ? '...' : ''}`}
                        </div>
                        {getJobDescription(job).length > 180 && (
                          <button
                            className="btn-link posting-toggle"
                            onClick={() => setExpandedJobId(expandedJobId === job.id ? null : job.id)}
                          >
                            {expandedJobId === job.id ? 'Show less' : 'Show more'}
                          </button>
                        )}
                      </>
                    ) : '-'}
                  </td>
                  <td>
                    <span className={`status-pill ${getStatusClass(job.status)}`}>
                      {job.status}
                    </span>
                    {job.archived && <span className="archived-pill">Archived</span>}
                  </td>
                  <td className="job-progress">{job.progress || '-'}</td>
                  <td className="job-score">
                    {job.result?.overall_score ? job.result.overall_score.toFixed(1) : '-'}
                  </td>
                  <td className="job-artifacts">
                    {job.result?.artifacts?.map((art: Artifact) => (
                      <div key={art.id} className="artifact-mini-actions">
                        {art.kind === 'pdf' && (
                          <button
                            className="btn-link"
                            onClick={() => handlePreview(job.id, art.id, art.filename)}
                            title={`Preview ${art.filename}`}
                          >
                            👁️
                          </button>
                        )}
                        <button 
                          className="btn-link"
                          onClick={() => handleDownload(job.id, art)}
                          title={`Download ${art.filename}`}
                        >
                          {art.kind === 'pdf' ? '📄' : '🛠️'}
                        </button>
                      </div>
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
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={() => handleArchiveToggle(job)}
                      disabled={mutatingJobId === job.id}
                    >
                      {job.archived ? 'Unarchive' : 'Archive'}
                    </button>
                    <button
                      className="btn btn-danger btn-sm"
                      onClick={() => handleDelete(job)}
                      disabled={mutatingJobId === job.id}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      <PdfPreviewModal
        isOpen={!!previewUrl}
        url={previewUrl}
        title={previewTitle}
        onClose={() => setPreviewUrl(null)}
      />
    </div>
  );
};

export default HistoryTab;
