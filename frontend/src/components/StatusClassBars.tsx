import React from 'react';

/* ── WHO z-score classification bars ──────────────────────────────────────
   The WAZ/HAZ/BAZ class columns are ordinal severity scales (4–6 classes,
   diverging around "normal"). Pies/donuts can't convey that order and the
   old 3-bucket colouring collapsed several classes to one hue. This renders
   each indicator as a compact 100%-stacked horizontal bar — segments ordered
   worst-deficiency → normal → worst-excess — under ONE shared severity key.

   Colours reuse existing tokens only (no new hues): a diverging ramp with
   deficiency on the coral side (--chart-5 family), normal as teal
   (--status-good), and excess on the gold side (--chart-4 family). */

type Lang = 'en' | 'bm';

export interface ClassBar {
  key: string;
  titleEn: string; titleBm: string;
  data: { label: string; count: number }[];
}

/* Raw backend class value → severity tier (−3 worst deficiency … +3 worst
   excess) + bilingual display name. Keys are the exact strings emitted by
   eda/who_zscore.py classify_waz/haz/baz. */
const CLASS_META: Record<string, { tier: number; en: string; bm: string }> = {
  // WAZ — Weight-for-Age
  kurang_berat_badan_teruk:    { tier: -3, en: 'Severely Underweight',  bm: 'Kurang berat badan teruk' },
  kurang_berat_badan:          { tier: -2, en: 'Underweight',           bm: 'Kurang berat badan' },
  risiko_kurang_berat_badan:   { tier: -1, en: 'At-risk Underweight',   bm: 'Risiko kurang berat badan' },
  berat_badan_normal:          { tier:  0, en: 'Normal',                bm: 'Berat badan normal' },
  mungkin_masalah_pertumbuhan: { tier:  3, en: 'Possible growth issue', bm: 'Mungkin masalah pertumbuhan' },
  // HAZ — Height-for-Age
  bantut_teruk:                { tier: -3, en: 'Severely Stunted',      bm: 'Bantut teruk' },
  bantut:                      { tier: -2, en: 'Stunted',              bm: 'Bantut' },
  risiko_bantut:               { tier: -1, en: 'At-risk Stunted',       bm: 'Risiko bantut' },
  normal:                      { tier:  0, en: 'Normal',                bm: 'Normal' },
  mungkin_masalah_endokrin:    { tier:  3, en: 'Possible endocrine issue', bm: 'Mungkin masalah endokrin' },
  // BAZ — BMI-for-Age
  susut_teruk:                 { tier: -3, en: 'Severely Wasted',       bm: 'Susut teruk' },
  susut:                       { tier: -2, en: 'Wasted',               bm: 'Susut' },
  berisiko_susut:              { tier: -1, en: 'At-risk Wasted',        bm: 'Berisiko susut' },
  risiko_lebih_berat_badan:    { tier:  1, en: 'At-risk Overweight',    bm: 'Risiko lebih berat badan' },
  berlebihan_berat_badan:      { tier:  2, en: 'Overweight',            bm: 'Berlebihan berat badan' },
  obes:                        { tier:  3, en: 'Obese',                 bm: 'Obes' },
};

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
    const m = CLASS_META[d.label];
    if (m) present.add(m.tier); else present.add(99);
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
            .map(d => ({ ...d, meta: CLASS_META[d.label] }))
            .sort((a, b) => (a.meta?.tier ?? 99) - (b.meta?.tier ?? 99));
          return (
            <div key={bar.key}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-secondary)', marginBottom: 4 }}>
                <span>{lang === 'en' ? bar.titleEn : bar.titleBm}</span>
                <span style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>{total.toLocaleString()}</span>
              </div>
              <div
                role="img"
                aria-label={`${lang === 'en' ? bar.titleEn : bar.titleBm}: ${segs.map(s => {
                  const name = s.meta ? (lang === 'en' ? s.meta.en : s.meta.bm) : s.label;
                  const pct = total > 0 ? ((Number(s.count) || 0) / total) * 100 : 0;
                  return `${name} ${pct.toFixed(0)}%`;
                }).join(', ')}`}
                style={{ display: 'flex', height: 18, borderRadius: 4, overflow: 'hidden', background: 'var(--surface-2)' }}
              >
                {total > 0 && segs.map((s, i) => {
                  const pct = (Number(s.count) || 0) / total * 100;
                  if (pct <= 0) return null;
                  const color = s.meta ? TIER_COLOR[s.meta.tier] : 'var(--status-neutral)';
                  const name = s.meta ? (lang === 'en' ? s.meta.en : s.meta.bm) : s.label;
                  return (
                    <div
                      key={i}
                      title={`${name} · ${Number(s.count).toLocaleString()} (${pct.toFixed(1)}%)`}
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
