import React from 'react';
import { useNavigate } from 'react-router-dom';

interface Props {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: { label: string; to: string };
}

export function EmptyState({ icon, title, description, action }: Props) {
  const nav = useNavigate();
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', gap: 14, padding: '72px 32px', textAlign: 'center',
    }}>
      {icon && (
        <div style={{ color: 'var(--text-muted)', opacity: 0.6 }}>{icon}</div>
      )}
      <h3 style={{
        fontFamily: 'var(--font-body)',
        fontWeight: 700, fontSize: 18, color: 'var(--text-primary)',
      }}>
        {title}
      </h3>
      {description && (
        <p style={{ color: 'var(--text-secondary)', maxWidth: 380, fontSize: 14, lineHeight: 1.6 }}>
          {description}
        </p>
      )}
      {action && (
        <button
          onClick={() => nav(action.to)}
          style={{
            marginTop: 4,
            background: 'var(--brand-blue)', color: '#fff',
            border: 'none', borderRadius: 'var(--radius-btn)',
            padding: '10px 22px', fontWeight: 600, fontSize: 14,
            transition: 'opacity var(--transition)',
          }}
          onMouseEnter={e => (e.currentTarget.style.opacity = '0.85')}
          onMouseLeave={e => (e.currentTarget.style.opacity = '1')}
        >
          {action.label}
        </button>
      )}
    </div>
  );
}
