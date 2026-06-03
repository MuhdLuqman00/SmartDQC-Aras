import React from 'react';
import { AlertTriangle, RotateCw } from 'lucide-react';
import { useLang } from '../context/LanguageContext';

/* Designed error state with a recovery path. Drop in wherever an async load
   can fail instead of silently blanking the panel:
       {error ? <ErrorRetry onRetry={reload} /> : <Chart … />}
   `compact` shrinks it for in-card use. */
export function ErrorRetry({
  message,
  onRetry,
  compact = false,
}: {
  message?: string;
  onRetry?: () => void;
  compact?: boolean;
}): JSX.Element {
  const { t } = useLang();
  return (
    <div
      role="alert"
      style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        justifyContent: 'center', gap: 10, textAlign: 'center',
        padding: compact ? '20px 16px' : '40px 24px',
      }}
    >
      <AlertTriangle size={compact ? 22 : 30} style={{ color: 'var(--danger)', opacity: 0.85 }} />
      <div style={{ fontSize: 13, color: 'var(--text-secondary)', maxWidth: 340, lineHeight: 1.55 }}>
        {message || t('Something went wrong loading this.', 'Berlaku ralat semasa memuatkan ini.')}
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          style={{
            display: 'flex', alignItems: 'center', gap: 7,
            background: 'var(--surface-2)', border: '1px solid var(--border)',
            borderRadius: 'var(--radius-btn)', padding: '7px 16px',
            fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', cursor: 'pointer',
          }}
        >
          <RotateCw size={14} /> {t('Retry', 'Cuba semula')}
        </button>
      )}
    </div>
  );
}
