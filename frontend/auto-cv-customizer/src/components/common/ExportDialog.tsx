import React from 'react';
import { useAppState } from '../../contexts/AppStateContext';
import './ExportDialog.css';

interface ExportDialogProps {
  isOpen: boolean;
  onClose: () => void;
}

const ExportDialog: React.FC<ExportDialogProps> = ({ isOpen, onClose }) => {
  const { state } = useAppState();
  const [exportFormat, setExportFormat] = React.useState<string[]>(['pdf']);
  const [includeComments, setIncludeComments] = React.useState(false);
  const [includeCoverLetter, setIncludeCoverLetter] = React.useState(true);
  const [isExporting, setIsExporting] = React.useState(false);

  if (!isOpen) return null;

  const handleExport = async () => {
    if (!state.processingState?.jobId) {
      alert('No job ID available. Please process a job first.');
      return;
    }

    setIsExporting(true);
    try {
      // In a real implementation, this would call the API to get the ZIP
      // For now, simulate download
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      // Simulate file download
      const link = document.createElement('a');
      link.href = '#'; // Would be actual blob URL
      link.download = 'cv_export.zip';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      
      alert('Export completed! (Simulation)');
      onClose();
    } catch (error) {
      console.error('Export error:', error);
      alert('Export failed. Please try again.');
    } finally {
      setIsExporting(false);
    }
  };

  const toggleFormat = (format: string) => {
    if (exportFormat.includes(format)) {
      setExportFormat(exportFormat.filter(f => f !== format));
    } else {
      setExportFormat([...exportFormat, format]);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Export CV</h2>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>
        
        <div className="modal-body">
          <div className="form-group">
            <label>Export Format</label>
            <div className="checkbox-group">
              <label>
                <input 
                  type="checkbox" 
                  checked={exportFormat.includes('pdf')} 
                  onChange={() => toggleFormat('pdf')} 
                />
                PDF (Customized CV)
              </label>
              <label>
                <input 
                  type="checkbox" 
                  checked={exportFormat.includes('latex')} 
                  onChange={() => toggleFormat('latex')} 
                />
                LaTeX Sources
              </label>
              <label>
                <input 
                  type="checkbox" 
                  checked={exportFormat.includes('zip')} 
                  onChange={() => toggleFormat('zip')} 
                />
                ZIP Bundle (All files)
              </label>
            </div>
          </div>

          <div className="form-group">
            <label>Options</label>
            <div className="checkbox-group">
              <label>
                <input 
                  type="checkbox" 
                  checked={includeComments} 
                  onChange={e => setIncludeComments(e.target.checked)} 
                />
                Include Scoring Comments
              </label>
              <label>
                <input 
                  type="checkbox" 
                  checked={includeCoverLetter} 
                  onChange={e => setIncludeCoverLetter(e.target.checked)} 
                />
                Include Cover Letter
              </label>
            </div>
          </div>

          {state.processingState?.result?.artifacts && (
            <div className="artifacts-list">
              <h3>Available Artifacts</h3>
              {state.processingState.result.artifacts.map((artifact: any, idx: number) => (
                <div key={idx} className="artifact-item">
                  <span className="artifact-name">{artifact.filename}</span>
                  <span className="artifact-type">{artifact.kind}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button 
            className="btn btn-primary" 
            onClick={handleExport}
            disabled={isExporting || exportFormat.length === 0}
          >
            {isExporting ? 'Exporting...' : 'Export'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ExportDialog;