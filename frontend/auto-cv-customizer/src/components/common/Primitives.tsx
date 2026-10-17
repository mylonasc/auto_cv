import { useEffect, useId, useRef } from 'react';
import type { ButtonHTMLAttributes, ReactNode } from 'react';
import './Primitives.css';

export function Button({ variant = 'secondary', className = '', type = 'button', ...props }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'danger' | 'success' }) {
  return <button type={type} className={`btn btn-${variant} ${className}`} {...props} />;
}

export function StatusBadge({ status }: { status: string }) {
  return <span className={`cv-status cv-status-${status}`}>{status}</span>;
}

export function Modal({ title, onClose, children, className = '' }:
  { title: string; onClose: () => void; children: ReactNode; className?: string }) {
  const id = useId();
  const dialog = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const previous = document.activeElement;
    dialog.current?.focus();
    return () => { if (previous instanceof HTMLElement && previous.isConnected) previous.focus(); };
  }, []);
  return <div className="cv-modal-overlay" onClick={onClose}>
    <div className={`cv-modal ${className}`} role="dialog" aria-modal="true" aria-labelledby={id}
      ref={dialog} tabIndex={-1} onClick={event => event.stopPropagation()} onKeyDown={event => {
        if (event.key === 'Escape') { event.stopPropagation(); onClose(); }
        if (event.key === 'Tab') {
          const controls = dialog.current?.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), a[href], iframe');
          if (!controls?.length) { event.preventDefault(); return; }
          const first = controls[0], last = controls[controls.length - 1];
          if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog.current)) {
            event.preventDefault(); last.focus();
          } else if (!event.shiftKey && (document.activeElement === last || document.activeElement === dialog.current)) {
            event.preventDefault(); first.focus();
          }
        }
      }}>
      <header className="cv-modal-header"><h2 id={id}>{title}</h2>
        <Button aria-label={`Close ${title}`} onClick={onClose}>✕</Button></header>
      {children}
    </div>
  </div>;
}
