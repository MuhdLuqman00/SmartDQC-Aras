import React from 'react';

export type Rag = 'good' | 'warning' | 'critical';

// WS7 consistency: a RagBadge renders a *status grade* (how a metric is doing),
// not an alert/error. It uses the dataviz status family (--status-*) — the same
// trio GeoPage/RankBars/Dashboard/Choropleth use — so "MODERATE" is one amber
// everywhere and "CRITICAL" reads as coral, never the error-red --danger.
// The hue is the SOLID fill with dark-navy text (not hue-on-tint, which fails
// WCAG: amber/coral as text on their pale tints is ~1.9–2.6:1). Navy on the
// status hue is 5.5–11:1 in both themes — and the badge's amber is now the
// literal same amber as the chart bars/map.
const CFG: Record<Rag, { bg: string; color: string; en: string; bm: string }> = {
  good:     { bg: 'var(--status-good)',     color: 'var(--primary-dark)', en: 'GOOD',     bm: 'BAIK'      },
  warning:  { bg: 'var(--status-watch)',    color: 'var(--primary-dark)', en: 'MODERATE', bm: 'SEDERHANA' },
  critical: { bg: 'var(--status-critical)', color: '#FFFFFF',             en: 'CRITICAL', bm: 'KRITIKAL'  },
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
