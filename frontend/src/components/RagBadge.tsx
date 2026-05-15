import React from 'react';

export type Rag = 'good' | 'warning' | 'critical';

const CFG: Record<Rag, { bg: string; color: string; en: string; bm: string }> = {
  good:     { bg: 'var(--success-bg)', color: 'var(--success)',  en: 'GOOD',     bm: 'BAIK'      },
  warning:  { bg: 'var(--warning-bg)', color: 'var(--warning)',  en: 'MODERATE', bm: 'SEDERHANA' },
  critical: { bg: 'var(--danger-bg)',  color: 'var(--danger)',   en: 'CRITICAL', bm: 'KRITIKAL'  },
};

export function RagBadge({ rag, lang = 'bm' }: { rag: Rag; lang?: 'en' | 'bm' }) {
  const c = CFG[rag];
  return (
    <span style={{
      background: c.bg, color: c.color,
      padding: '2px 8px', borderRadius: 999,
      fontSize: 10, fontWeight: 700, letterSpacing: '0.06em',
      whiteSpace: 'nowrap',
    }}>
      {c[lang]}
    </span>
  );
}

export function scoreToRag(score: number): Rag {
  if (score >= 80) return 'good';
  if (score >= 60) return 'warning';
  return 'critical';
}

export function rateToRag(rate: number): Rag {
  if (rate > 0.15) return 'critical';
  if (rate > 0.08) return 'warning';
  return 'good';
}
