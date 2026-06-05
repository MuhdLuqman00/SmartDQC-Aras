import React from 'react';

/* ── WHO z-score classification bars ──────────────────────────────────────
   The WAZ/HAZ/BAZ class columns are ordinal severity scales (4–6 classes,
   diverging around "normal"). Pies/donuts can't convey that order and the
   old 3-bucket colouring collapsed several classes to one hue. This renders
   each indicator as a compact 100%-stacked horizontal bar — segments ordered
   worst-deficiency → normal → worst-excess — under ONE shared severity key.

   Class labels vary by source/classifier (English "Severely underweight",
   BM "kurang_berat_badan_teruk", or "Ind susut" forms), so we classify by
   normalised keyword rather than exact string — robust to all variants.

   Colours reuse existing tokens only (no new hues): a diverging ramp with
   deficiency on the coral side (--chart-5 family), normal as teal
   (--status-good), and excess on the gold side (--chart-4 family). */

type Lang = 'en' | 'bm';

export interface ClassBar {
  key: string;
  titleEn: string; titleBm: string;
  data: { label: string; count: number }[];
}

/* Map a raw class label → severity tier (−3 worst deficiency … +3 worst
   excess), or null when it isn't a recognised nutrition class. Matches
   English and BM keyword families plus severe/at-risk modifiers. */
function classifyTier(raw: string): number | null {
  const l = String(raw).toLowerCase().replace(/[_]+/g, ' ').replace(/\s+/g, ' ').trim();
  const severe = /severe|severely|teruk|sangat/.test(l);
  const risk   = /risiko|berisiko|at[\s-]?risk|\brisk\b/.test(l);

  if (/\bnormal\b|healthy|baik/.test(l)) return 0;
  if (/obes/.test(l)) return 3;                                  // obese / obes
  if (/overweight|over weight|berlebihan|lebih/.test(l)) return risk ? 1 : 2;
  if (/\btall\b|tinggi|pertumbuhan|endokrin|growth|endocrine/.test(l)) return 3;
  if (/underweight|under weight|kurang berat|kurang/.test(l)) return severe ? -3 : risk ? -1 : -2;
  if (/stunt|bantut/.test(l)) return severe ? -3 : risk ? -1 : -2;
  if (/wast|susut/.test(l)) return severe ? -3 : risk ? -1 : -2;
  return null;
}

/* Tidy a raw label for the segment tooltip (snake_case → spaced, capitalised). */
function prettyLabel(raw: string): string {
  const s = String(raw).replace(/[_]+/g, ' ').replace(/\s+/g, ' ').trim();
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : s;
}

const TIER_ORDER = [-3, -2, -1, 0, 1, 2, 3];

const TIER_COLOR: Record<number, string> = {
  [-3]: 'var(--chart-5-deep)',     // deep coral — severe deficiency
  [-2]: 'var(--status-critical)',  // coral
  [-1]: 'var(--chart-5-soft)',     // light coral
  [0]:  'var(--status-good)',      // teal — normal
  [1]:  'var(--chart-4-soft)',     // light gold
  [2]:  'var(--chart-4)',          // gold
  [3]:  'var(--chart-4-deep)',     // deep gold — severe excess
};

const TIER_LABEL: Record<number, { en: string; bm: string }> = {
  [-3]: { en: 'Severe deficiency', bm: 'Kekurangan teruk' },
  [-2]: { en: 'Deficiency',        bm: 'Kekurangan' },
  [-1]: { en: 'At risk',           bm: 'Berisiko' },
  [0]:  { en: 'Normal',            bm: 'Normal' },
  [1]:  { en: 'At-risk excess',    bm: 'Risiko lebihan' },
  [2]:  { en: 'Excess',            bm: 'Lebihan' },
  [3]:  { en: 'Severe excess',     bm: 'Lebihan teruk' },
};

export function StatusClassBars({ title, bars, lang }: { title: string; bars: ClassBar[]; lang: Lang }): JSX.Element {
  // Which tiers actually appear (across all bars) → drives the shared legend.
  const present = new Set<number>();
  bars.forEach(b => b.data.forEach(d => {
    const tier = classifyTier(d.label);
    present.add(tier === null ? 99 : tier);
  }));
  const legendTiers = TIER_ORDER.filter(t => present.has(t));
  const hasUnknown = present.has(99);

  return (
    <div className="card" style={{ padding: '16px 18px' }}>
      <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 14, color: 'var(--text-primary)' }}>{title}</div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {bars.map(bar => {
          const total = bar.data.reduce((s, d) => s + (Number(d.count) || 0), 0);
          // Order segments worst-deficiency → normal → worst-excess; unknown last.
          const segs = bar.data
            .map(d => ({ ...d, tier: classifyTier(d.label) }))
            .sort((a, b) => (a.tier ?? 99) - (b.tier ?? 99));
          return (
            <div key={bar.key}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-secondary)', marginBottom: 4 }}>
                <span>{lang === 'en' ? bar.titleEn : bar.titleBm}</span>
                <span style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>{total.toLocaleString()}</span>
              </div>
              <div
                role="img"
                aria-label={`${lang === 'en' ? bar.titleEn : bar.titleBm}: ${segs.map(s => {
                  const pct = total > 0 ? ((Number(s.count) || 0) / total) * 100 : 0;
                  return `${prettyLabel(s.label)} ${pct.toFixed(0)}%`;
                }).join(', ')}`}
                style={{ display: 'flex', height: 18, borderRadius: 4, overflow: 'hidden', background: 'var(--surface-2)' }}
              >
                {total > 0 && segs.map((s, i) => {
                  const pct = (Number(s.count) || 0) / total * 100;
                  if (pct <= 0) return null;
                  const color = s.tier !== null ? TIER_COLOR[s.tier] : 'var(--status-neutral)';
                  return (
                    <div
                      key={i}
                      title={`${prettyLabel(s.label)} · ${Number(s.count).toLocaleString()} (${pct.toFixed(1)}%)`}
                      style={{ width: `${pct}%`, background: color }}
                    />
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>

      {/* Shared severity key — only the tiers that appear. */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px 12px', marginTop: 12, fontSize: 10.5, color: 'var(--text-secondary)' }}>
        {legendTiers.map(t => (
          <span key={t} style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
            <span style={{ width: 9, height: 9, borderRadius: 2, background: TIER_COLOR[t], flexShrink: 0 }} />
            {lang === 'en' ? TIER_LABEL[t].en : TIER_LABEL[t].bm}
          </span>
        ))}
        {hasUnknown && (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
            <span style={{ width: 9, height: 9, borderRadius: 2, background: 'var(--status-neutral)', flexShrink: 0 }} />
            {lang === 'en' ? 'Other' : 'Lain-lain'}
          </span>
        )}
      </div>
    </div>
  );
}
