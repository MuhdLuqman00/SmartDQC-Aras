import React, { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';

/* Reusable focus/fullscreen overlay for analysis panels (E1b).
   Rendered via createPortal to document.body so position:fixed anchors to
   the true viewport — not to the transformed .page-enter ancestor, which
   establishes a containing block and breaks fixed positioning. */
export function FocusOverlay({ open, onClose, title, children }: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
}): JSX.Element | null {
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    closeRef.current?.focus();
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [open, onClose]);

  if (!open) return null;

  return createPortal(
    <div
      className="modal-backdrop"
      role="dialog" aria-modal="true" aria-label={title}
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, zIndex: 'var(--z-modal)' as React.CSSProperties['zIndex'],
        background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center',
        justifyContent: 'center', padding: 24, paddingLeft: 'calc(var(--sidebar-w, 0px) + 24px)',
      }}
    >
      <div
        className="modal-card"
        onClick={e => e.stopPropagation()}
        style={{
          background: 'var(--surface)', border: '1px solid var(--border)',
          borderRadius: 'var(--radius-card)', boxShadow: 'var(--shadow-lg)',
          width: 'min(1100px, 96vw)', maxHeight: '92vh',
          display: 'flex', flexDirection: 'column', overflow: 'hidden',
        }}
      >
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          gap: 12, padding: '16px 20px', borderBottom: '1px solid var(--border)', flexShrink: 0,
        }}>
          <h2 className="brand-keyline" style={{
            margin: 0, fontFamily: 'var(--font-body)', fontWeight: 700,
            fontSize: 16, color: 'var(--text-primary)',
          }}>
            {title}
          </h2>
          <button
            ref={closeRef}
            onClick={onClose}
            aria-label="Close"
            style={{
              background: 'var(--surface-2)', border: '1px solid var(--border)',
              borderRadius: 8, padding: 6, color: 'var(--text-secondary)',
              cursor: 'pointer', display: 'flex', flexShrink: 0,
            }}
          >
            <X size={16} />
          </button>
        </div>
        <div style={{ padding: '18px 20px', overflowY: 'auto' }}>
          {children}
        </div>
      </div>
    </div>,
    document.body
  );
}
