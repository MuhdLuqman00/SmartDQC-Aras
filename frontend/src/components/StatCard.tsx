import React from 'react';

interface Props {
  label: string;
  value: string | number;
  sub?: string;
  accent?: string;
  icon?: React.ReactNode;
}

export function StatCard({ label, value, sub, accent, icon }: Props) {
  return (
    <div style={{
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderTop: accent ? `3px solid ${accent}` : '1px solid var(--border)',
      borderRadius: 'var(--radius-card)',
      padding: '18px 20px',
      boxShadow: 'var(--shadow-card)',
      display: 'flex', flexDirection: 'column', gap: 6,
    }}>
      <div style={{
        fontSize: 11, fontWeight: 600, letterSpacing: '0.07em',
        textTransform: 'uppercase', color: 'var(--text-secondary)',
        display: 'flex', alignItems: 'center', gap: 6,
      }}>
        {icon && <span style={{ opacity: 0.7 }}>{icon}</span>}
        {label}
      </div>
      <div style={{ fontSize: 28, fontWeight: 700, color: 'var(--text-primary)', lineHeight: 1.1 }}>
        {value}
      </div>
      {sub && <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{sub}</div>}
    </div>
  );
}
