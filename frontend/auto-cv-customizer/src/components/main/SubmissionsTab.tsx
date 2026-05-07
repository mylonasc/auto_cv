import React, { useState, useEffect, useCallback } from 'react';
import { useAppState, type Submission } from '../../contexts/AppStateContext';
import apiService from '../../services/api';
import PdfPreviewModal from '../common/PdfPreviewModal';
import './SubmissionsTab.css';

const RESULT_OPTIONS = ['', 'NO_RESPONSE', 'INTERVIEW', 'REJECTED', 'OFFER', 'WITHDREW'];

const SubmissionsTab: React.FC = () => {
  const { state } = useAppState();
  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewTitle, setPreviewTitle] = useState('PDF Preview');
  const [editingResult, setEditingResult] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  const [editNotes, setEditNotes] = useState('');

  const fetchSubmissions = useCallback(async () => {
    try {
      setIsLoading(true);
      const data = await apiService.listSubmissions();
      setSubmissions(data);
    } catch (err) {
      console.error('Failed to fetch submissions:', err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSubmissions();
  }, [fetchSubmissions]);

  // Refresh when tab becomes active
  useEffect(() => {
    if (state.uiState.activeTab === 'submissions') {
      fetchSubmissions();
    }
  }, [state.uiState.activeTab, fetchSubmissions]);

  const handlePreview = (artifact: { id: string; filename: string }) => {
    const jobId = submissions.find(s => s.artifacts?.some(a => a.id === artifact.id))?.job_id;
    if (!jobId) return;
    setPreviewUrl(apiService.getArtifactPreviewUrl(jobId, artifact.id));
    setPreviewTitle(artifact.filename || 'PDF Preview');
  };

  const handleDownload = async (jobId: string, artifact: { id: string; filename: string }) => {
    try {
      await apiService.downloadArtifact(jobId, artifact.id, artifact.filename);
    } catch (err) {
      console.error('Download failed:', err);
      alert('Download failed.');
    }
  };

  const handleSaveResult = async (submissionId: string) => {
    try {
      const updated = await apiService.updateSubmission(submissionId, {
        result: editValue || undefined,
        notes: editNotes || undefined,
      });
      setSubmissions(prev => prev.map(s => (s.id === submissionId ? updated : s)));
      setEditingResult(null);
    } catch (err) {
      console.error('Failed to update submission:', err);
      alert('Failed to update submission.');
    }
  };

  const startEditing = (submission: Submission) => {
    setEditingResult(submission.id);
    setEditValue(submission.result || '');
    setEditNotes(submission.notes || '');
  };

  const formatDate = (d: string | null | undefined) => {
    if (!d) return '-';
    try {
      return new Date(d).toLocaleDateString();
    } catch {
      return d;
    }
  };

  const scoreColor = (score: number | null | undefined) => {
    if (score == null) return '#999';
    if (score >= 7) return '#34a853';
    if (score >= 4) return '#fbbc04';
    return '#ea4335';
  };

  if (isLoading) {
    return <div className="submissions-tab"><div className="loading">Loading submissions...</div></div>;
  }

  return (
    <div className="submissions-tab">
      <div className="submissions-header">
        <h2>CV Submissions</h2>
        <button className="btn btn-secondary" onClick={fetchSubmissions}>🔄 Refresh</button>
      </div>

      {submissions.length === 0 ? (
        <div className="no-submissions">
          <p>No submissions yet. After rendering a CV, use the <strong>"Create Submission"</strong> button in the Export dialog to record a sent application.</p>
        </div>
      ) : (
        <div className="submissions-list">
          <table className="submissions-table">
            <thead>
              <tr>
                <th>Date Submitted</th>
                <th>Company</th>
                <th>Job Title</th>
                <th>Score</th>
                <th>Result</th>
                <th>Artifacts</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {submissions.map(sub => (
                <React.Fragment key={sub.id}>
                  <tr
                    className={`submission-row ${expandedId === sub.id ? 'expanded' : ''}`}
                    onClick={() => setExpandedId(expandedId === sub.id ? null : sub.id)}
                  >
                    <td>{formatDate(sub.submitted_at)}</td>
                    <td>{sub.company || '-'}</td>
                    <td>{sub.job_title || '-'}</td>
                    <td>
                      {sub.overall_score != null ? (
                        <span className="submission-score" style={{ color: scoreColor(sub.overall_score) }}>
                          {Number(sub.overall_score).toFixed(1)}
                        </span>
                      ) : '-'}
                    </td>
                    <td>
                      {editingResult === sub.id ? (
                        <select
                          value={editValue}
                          onChange={e => setEditValue(e.target.value)}
                          onClick={e => e.stopPropagation()}
                        >
                          {RESULT_OPTIONS.map(r => (
                            <option key={r} value={r}>{r || '(none)'}</option>
                          ))}
                        </select>
                      ) : (
                        <span className={`result-pill ${(sub.result || '').toLowerCase()}`}>
                          {sub.result || '-'}
                        </span>
                      )}
                    </td>
                    <td className="submission-artifacts">
                      {sub.artifacts?.map(art => (
                        <div key={art.id} className="artifact-mini-actions" onClick={e => e.stopPropagation()}>
                          {art.kind === 'pdf' && (
                            <button className="btn-link" onClick={() => handlePreview(art)} title="Preview">👁️</button>
                          )}
                          <button className="btn-link" onClick={() => handleDownload(sub.job_id, art)} title="Download">
                            {art.kind === 'pdf' ? '📄' : '🛠️'}
                          </button>
                          {art.source === 'working_copy' && <span className="wc-badge">WC</span>}
                        </div>
                      ))}
                    </td>
                    <td onClick={e => e.stopPropagation()}>
                      {editingResult === sub.id ? (
                        <div className="edit-result-actions">
                          <button className="btn btn-primary btn-sm" onClick={() => handleSaveResult(sub.id)}>Save</button>
                          <button className="btn btn-secondary btn-sm" onClick={() => setEditingResult(null)}>Cancel</button>
                        </div>
                      ) : (
                        <button className="btn btn-secondary btn-sm" onClick={() => startEditing(sub)}>Edit Result</button>
                      )}
                    </td>
                  </tr>
                  {expandedId === sub.id && (
                    <tr className="submission-detail-row">
                      <td colSpan={7}>
                        <div className="submission-detail">
                          <div className="detail-grid">
                            <div className="detail-item">
                              <strong>Job Entered</strong>
                              <span>{formatDate(sub.job_entered_at)}</span>
                            </div>
                            <div className="detail-item">
                              <strong>Submitted</strong>
                              <span>{formatDate(sub.submitted_at)}</span>
                            </div>
                            <div className="detail-item">
                              <strong>Overall Score</strong>
                              <span>{sub.overall_score != null ? Number(sub.overall_score).toFixed(2) : '-'}</span>
                            </div>
                            <div className="detail-item">
                              <strong>Result</strong>
                              <span>{sub.result || '(not set)'}</span>
                            </div>
                          </div>
                          <div className="detail-section">
                            <strong>Notes</strong>
                            {editingResult === sub.id ? (
                              <textarea
                                className="notes-textarea"
                                value={editNotes}
                                onChange={e => setEditNotes(e.target.value)}
                                rows={3}
                                placeholder="Add notes about this application..."
                              />
                            ) : (
                              <p>{sub.notes || '(none)'}</p>
                            )}
                          </div>
                          <div className="detail-section">
                            <strong>Scoring Snapshot</strong>
                            {sub.scoring_snapshot ? (
                              <pre className="snapshot-pre">
                                {JSON.stringify(sub.scoring_snapshot, null, 2)}
                              </pre>
                            ) : (
                              <p>No scoring data available.</p>
                            )}
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <PdfPreviewModal
        isOpen={!!previewUrl}
        url={previewUrl}
        title={previewTitle}
        onClose={() => setPreviewUrl(null)}
      />
    </div>
  );
};

export default SubmissionsTab;
