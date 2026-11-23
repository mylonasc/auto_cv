import React from 'react';
import { Modal } from './Primitives';
import './PdfPreviewModal.css';
import { PdfFrame } from './PdfFrame';

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
          <PdfFrame title={title || 'PDF Preview'} url={url} />
        </div>
    </Modal>
  );
};

export default PdfPreviewModal;
