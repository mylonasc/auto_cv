import React from 'react';
import { Modal } from './Primitives';
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
    <Modal title={title || 'PDF Preview'} onClose={onClose} className="pdf-preview-modal">
        <div className="pdf-preview-frame-wrap">
          <iframe
            title={title || 'PDF Preview'}
            src={url}
            className="pdf-preview-frame"
          />
        </div>
    </Modal>
  );
};

export default PdfPreviewModal;
