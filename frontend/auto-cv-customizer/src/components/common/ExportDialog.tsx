import React, { useState } from 'react';
import { useAppState } from '../../contexts/AppStateContext';
import apiService from '../../services/api';
import './ExportDialog.css';

interface ExportDialogProps {
  isOpen: boolean;
  onClose: () => void;
}

const ExportDialog: React.FC<ExportDialogProps> = ({ isOpen, onClose }) => {
  const { state, dispatch } = useAppState();
  const [isExporting, setIsExporting] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleDownload = async (artifactId: string, filename: string) => {
    const jobId = state.processingState?.jobId || state.processingState?.lastSuccessfulJobId;
    if (!jobId) {
      alert('No job ID available. Please process a job first.');
      return;
    }

    setIsExporting(artifactId);
    try {
      await apiService.downloadArtifact(jobId, artifactId, filename);
    } catch (error) {
      console.error('Download error:', error);
      alert('Download failed. Please try again.');
    } finally {
      setIsExporting(null);
    }
  };

  const artifacts = state.processingState?.result?.artifacts || [];
  const hasJob = !!(state.processingState?.jobId || state.processingState?.lastSuccessfulJobId);

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Export & Download</h2>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>
        
        <div className="modal-body">
          {!hasJob ? (
            <div className="no-artifacts">
              <p>No job history found in the current session.</p>
              <button 
                className="btn btn-secondary btn-sm" 
                style={{ marginTop: '12px' }}
                onClick={() => {
                  onClose();
                  dispatch({ type: 'SET_UI_STATE', payload: { activeTab: 'history' } });
                }}
              >
                Go to History →
              </button>
              <p className="hint" style={{ marginTop: '12px' }}>
                If you have previously run an analysis, you can load it from the <strong>History</strong> tab to download its artifacts.
              </p>
            </div>
          ) : (
            <>
              <p>The following artifacts have been generated for your customized CV:</p>
              
              <div className="artifacts-grid">
                {artifacts.length > 0 ? (
                  artifacts.map((artifact: any) => (
                    <div key={artifact.id} className="artifact-card">
                      <div className="artifact-icon">
                        {artifact.kind === 'pdf' ? '📄' : '🛠️'}
                      </div>
                      <div className="artifact-info">
                        <div className="artifact-filename">{artifact.filename}</div>
                        <div className="artifact-meta">{artifact.kind.toUpperCase()} File</div>
                      </div>
                      <button 
                        className="btn btn-primary btn-sm"
                        onClick={() => handleDownload(artifact.id, artifact.filename)}
                        disabled={isExporting === artifact.id}
                      >
                        {isExporting === artifact.id ? 'Downloading...' : 'Download'}
                      </button>
                    </div>
                  ))
                ) : (
                  <div className="no-artifacts">
                    No artifacts generated for the current job.
                  </div>
                )}
              </div>
            </>
          )}
        </div>

        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

export default ExportDialog;
