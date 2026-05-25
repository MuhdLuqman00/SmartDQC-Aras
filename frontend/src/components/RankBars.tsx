import React, { useMemo } from 'react';

/* Shared horizontal "ranking" bar list — the standardized look used for
   By State / By Daerah / By Gender / By Income / By Age across the Dashboard,
   Geo and Risk views. Replaces the cramped vertical recharts bars (whose
   x-axis labels overlapped with many categories) with readable, sorted,
   left-labelled rows. When there are many categories (e.g. all daerah) the
   list scrolls inside a fixed height instead of stretching the page. */

export type RankStatus = 'good' | 'watch' | 'critical' | 'neutral';

const STATUS_VAR: Record<RankStatus, string> = {
  good:     'var(--status-good)',
  watch:    'var(--status-watch)',
  critical: 'var(--status-critical)',
  neutral:  'var(--status-neutral)',
};
const STATUS_BG: Record<RankStatus, string> = {
  good:     'var(--status-good-bg)',
  watch:    'var(--status-watch-bg)',
  critical: 'var(--status-critical-bg)',
  neutral:  'var(--surface-2)',
};

export interface RankRow {
  label: string;
  value: number;       // already a percentage (0-100) by default
  status?: RankStatus;
  n?: number;
}

interface Props {
  title: string;
  rows: RankRow[];
  /** Suffix appended to the value (default '%'). */
  valueSuffix?: string;
  /** Decimal places for the value label (default 2; use 0 for counts). */
  decimals?: number;
  /** Rows beyond this count scroll inside a fixed height (default 8). */
  scrollAfter?: number;
  /** Empty-state message. */
  emptyText?: string;
  lang?: 'en' | 'bm';
}

export function RankBars({
  title, rows, valueSuffix = '%', decimals = 2, scrollAfter = 8, emptyText, lang = 'en',
}: Props): JSX.Element {
  const sorted = useMemo(
    () => [...(rows || [])].sort((a, b) => (b.value ?? 0) - (a.value ?? 0)),
    [rows],
  );
  // Scale bars against the largest value so small-but-real differences are
  // visible (a 4% max would otherwise render as four near-invisible slivers).
  const max = useMemo(
    () => Math.max(1, ...sorted.map(r => r.value ?? 0)),
    [sorted],
  );

  const card: React.CSSProperties = {
    background: 'var(--surface)', border: '1px solid var(--border)',
    borderRadius: 'var(--radius-card)', padding: 20, boxShadow: 'var(--shadow-card)',
  };
  const head: React.CSSProperties = {
    fontSize: 11, fontWeight: 600, letterSpacing: '0.07em', textTransform: 'uppercase',
    color: 'var(--text-secondary)', marginBottom: 14,
  };

  if (!sorted.length) {
    return (
      <div className="card-hover" style={card}>
        <div style={head}>{title}</div>
        <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>
          {emptyText ?? (lang === 'en' ? 'Not available for this dataset.' : 'Tiada untuk dataset ini.')}
        </div>
      </div>
    );
  }

  const scroll = sorted.length > scrollAfter;
  const listStyle: React.CSSProperties = scroll
    ? { maxHeight: scrollAfter * 44, overflowY: 'auto', paddingRight: 6 }
    : {};

  return (
    <div className="card-hover" style={card}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <div style={head}>{title}</div>
        {scroll && (
          <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>
            {sorted.length} {lang === 'en' ? 'items' : 'item'}
          </span>
        )}
      </div>
      <div style={listStyle}>
        {sorted.map((r, i) => {
          const status: RankStatus = r.status ?? 'neutral';
          const pct = Math.max(2, Math.min(100, ((r.value ?? 0) / max) * 100));
          return (
            <div key={`${r.label}-${i}`} style={{ marginBottom: 12 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', fontSize: 12.5, color: 'var(--text-secondary)', marginBottom: 5 }}>
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '62%' }}>{r.label}</span>
                <span style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexShrink: 0 }}>
                  {r.n != null && <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>n={r.n.toLocaleString()}</span>}
                  <span style={{ fontWeight: 700, color: 'var(--text-primary)' }}>{(r.value ?? 0).toFixed(decimals)}{valueSuffix}</span>
                </span>
              </div>
              <div style={{ height: 10, background: STATUS_BG[status], borderRadius: 5 }}>
                <div style={{ height: '100%', width: `${pct}%`, background: STATUS_VAR[status], borderRadius: 5, transition: 'width 0.4s ease' }} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
