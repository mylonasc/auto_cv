import React from 'react';
import './PdfPreviewModal.css';

interface PdfPreviewModalProps {
  isOpen: boolean;
  url: string | null;
  title?: string;
  onClose: () => void;
}

const PdfPreviewModal: React.FC<PdfPreviewModalProps> = ({ isOpen, url, title, onClose }) => {
  if (!isOpen || !url) {
    return null;
  }

  return (
    <div className="pdf-preview-overlay" onClick={onClose}>
      <div className="pdf-preview-container" onClick={(e) => e.stopPropagation()}>
        <div className="pdf-preview-header">
          <h3>{title || 'PDF Preview'}</h3>
          <button className="pdf-preview-close" onClick={onClose} aria-label="Close preview">
            ✕
          </button>
        </div>
        <div className="pdf-preview-frame-wrap">
          <iframe
            title={title || 'PDF Preview'}
            src={url}
            className="pdf-preview-frame"
          />
        </div>
      </div>
    </div>
  );
};

export default PdfPreviewModal;
