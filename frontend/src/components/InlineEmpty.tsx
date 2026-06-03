import React from 'react';

/* Compact, card-sized empty state — an icon + one line — for in-card "nothing
   here yet" cases (vs the full-page EmptyState used for whole-route empties).
   Gives flat "No rules recorded" text a designed treatment. */
export function InlineEmpty({
  icon,
  text,
}: {
  icon?: React.ReactNode;
  text: string;
}): JSX.Element {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', gap: 8, padding: '24px 16px',
      textAlign: 'center', color: 'var(--text-muted)',
    }}>
      {icon && <div style={{ opacity: 0.5, display: 'flex' }}>{icon}</div>}
      <div style={{ fontSize: 13, lineHeight: 1.5 }}>{text}</div>
    </div>
  );
}
