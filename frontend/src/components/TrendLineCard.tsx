import React, { useId } from 'react';
import {
  ComposedChart, Line, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend, CartesianGrid,
} from 'recharts';
import { ChartTooltip } from './ChartTooltip';

/* Renders backend `trend_by_year` payload — list of records with a
   `tahun_ukur` x-axis and a variable set of indicator columns
   (bantut, obes, kurang_berat, susut, plus n_total). We pick a fixed
   set of known indicator columns to plot so the legend stays stable
   across datasets; ones missing in the data are silently skipped.

   Each indicator gets a distinct categorical color from the
   `--chart-N` ramp (no more two-colour amber/red wall) plus a soft
   area-gradient under its line so the trend is visible even when the
   series cross. */

interface Props {
  title: string;
  data: Record<string, unknown>[];
  /** Override series; defaults to the four core indicators. */
  series?: { key: string; labelEn: string; labelBm: string; color: string; soft: string }[];
  lang: 'en' | 'bm';
}

const DEFAULT_SERIES = [
  { key: 'bantut',       labelEn: 'Stunting',    labelBm: 'Bantut',       color: 'var(--chart-1)', soft: 'var(--chart-1-soft)' },
  { key: 'obes',         labelEn: 'Obesity',     labelBm: 'Obesiti',      color: 'var(--chart-4)', soft: 'var(--chart-4-soft)' },
  { key: 'kurang_berat', labelEn: 'Underweight', labelBm: 'Kurang berat', color: 'var(--chart-5)', soft: 'var(--chart-5-soft)' },
  { key: 'susut',        labelEn: 'Wasting',     labelBm: 'Susut',        color: 'var(--chart-3)', soft: 'var(--chart-3-soft)' },
];

export function TrendLineCard({ title, data, series = DEFAULT_SERIES, lang }: Props): JSX.Element {
  const gradId = useId().replace(/:/g, '');
  const rows: Record<string, unknown>[] = (data || [])
    .filter(d => d && d.tahun_ukur != null)
    .map(d => ({ ...d, tahun_ukur: String(d.tahun_ukur) }));

  // Keep a series if it has any numeric value (incl. all-zeros) — the
  // distinction "no cases this period" vs "key not in payload" matters,
  // and a flat zero-line with a subtitle reads as intentional rather
  // than a render bug.
  const activeSeries = series.filter(s =>
    rows.some(r => typeof r[s.key] === 'number' && Number.isFinite(r[s.key] as number))
  );
  const allZero = activeSeries.length > 0 && activeSeries.every(s =>
    rows.every(r => !r[s.key] || (r[s.key] as number) === 0)
  );

  if (!rows.length || !activeSeries.length) {
    return (
      <div style={{
        background: 'var(--surface)', border: '1px solid var(--border)',
        borderRadius: 'var(--radius-card)', padding: '16px 18px', boxShadow: 'var(--shadow-card)',
      }}>
        <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8 }}>{title}</div>
        <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>—</div>
      </div>
    );
  }

  return (
    <div style={{
      background: 'var(--surface)', border: '1px solid var(--border)',
      borderRadius: 'var(--radius-card)', padding: '16px 18px', boxShadow: 'var(--shadow-card)',
    }}>
      <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 4, color: 'var(--text-primary)' }}>{title}</div>
      {allZero && (
        <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 6, fontStyle: 'italic' }}>
          {lang === 'en'
            ? 'No indicator cases recorded in this dataset.'
            : 'Tiada kes penunjuk direkodkan dalam dataset ini.'}
        </div>
      )}
      <ResponsiveContainer width="100%" height={240}>
        <ComposedChart data={rows} margin={{ top: 8, right: 12, left: -12, bottom: 0 }}>
          <defs>
            {activeSeries.map((s, i) => (
              <linearGradient key={i} id={`trend-${gradId}-${i}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={s.soft} stopOpacity={0.45} />
                <stop offset="100%" stopColor={s.soft} stopOpacity={0} />
              </linearGradient>
            ))}
          </defs>
          <CartesianGrid stroke="var(--chart-grid)" strokeDasharray="2 4" vertical={false} />
          <XAxis
            dataKey="tahun_ukur"
            tick={{ fontSize: 10, fill: 'var(--chart-axis)' }}
            tickLine={false}
            axisLine={{ stroke: 'var(--chart-grid)' }}
          />
          <YAxis
            tick={{ fontSize: 10, fill: 'var(--chart-axis)' }}
            allowDecimals={false}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip content={<ChartTooltip />} cursor={{ stroke: 'var(--chart-grid)', strokeWidth: 1 }} />
          <Legend
            verticalAlign="bottom" height={28} iconType="circle" iconSize={8}
            wrapperStyle={{ fontSize: 11, color: 'var(--text-secondary)' }}
          />
          {activeSeries.map((s, i) => (
            <Area
              key={`area-${s.key}`}
              type="monotone"
              dataKey={s.key}
              stroke="none"
              fill={`url(#trend-${gradId}-${i})`}
              isAnimationActive={false}
              legendType="none"
            />
          ))}
          {activeSeries.map(s => (
            <Line
              key={`line-${s.key}`}
              type="monotone"
              dataKey={s.key}
              name={lang === 'en' ? s.labelEn : s.labelBm}
              stroke={s.color}
              strokeWidth={2.5}
              dot={{ r: 3, fill: s.color, stroke: 'var(--surface)', strokeWidth: 1.5 }}
              activeDot={{ r: 6, fill: s.color, stroke: 'var(--surface)', strokeWidth: 2 }}
              isAnimationActive={false}
            />
          ))}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
