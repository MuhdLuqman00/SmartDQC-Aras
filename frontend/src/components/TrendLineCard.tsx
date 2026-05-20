import React from 'react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend, CartesianGrid } from 'recharts';
import { ChartTooltip } from './ChartTooltip';

/* Renders backend `trend_by_year` payload — list of records with a
   `tahun_ukur` x-axis and a variable set of indicator columns
   (bantut, obes, kurang_berat, susut, plus n_total). We pick a fixed
   set of known indicator columns to plot so the legend stays stable
   across datasets; ones missing in the data are silently skipped. */

interface Props {
  title: string;
  data: Record<string, unknown>[];
  /** Override series; defaults to the four core indicators + n_total. */
  series?: { key: string; labelEn: string; labelBm: string; color: string }[];
  lang: 'en' | 'bm';
}

const DEFAULT_SERIES = [
  { key: 'bantut',        labelEn: 'Stunting',    labelBm: 'Bantut',          color: 'var(--status-critical)' },
  { key: 'obes',          labelEn: 'Obesity',     labelBm: 'Obesiti',         color: 'var(--status-watch)' },
  { key: 'kurang_berat',  labelEn: 'Underweight', labelBm: 'Kurang berat',    color: 'var(--status-watch)' },
  { key: 'susut',         labelEn: 'Wasting',     labelBm: 'Susut',           color: 'var(--status-critical)' },
];

export function TrendLineCard({ title, data, series = DEFAULT_SERIES, lang }: Props): JSX.Element {
  const rows: Record<string, unknown>[] = (data || [])
    .filter(d => d && d.tahun_ukur != null)
    .map(d => ({ ...d, tahun_ukur: String(d.tahun_ukur) }));

  // Only render series that actually have data in the rows — keeps the
  // legend honest and avoids flat-zero lines.
  const activeSeries = series.filter(s =>
    rows.some(r => typeof r[s.key] === 'number' && (r[s.key] as number) !== 0)
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
      <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8 }}>{title}</div>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={rows} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
          <XAxis dataKey="tahun_ukur" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} />
          <YAxis tick={{ fontSize: 10, fill: 'var(--text-muted)' }} allowDecimals={false} />
          <Tooltip content={<ChartTooltip />} />
          <Legend
            verticalAlign="bottom" height={28}
            wrapperStyle={{ fontSize: 11, color: 'var(--text-secondary)' }}
          />
          {activeSeries.map(s => (
            <Line
              key={s.key}
              type="monotone"
              dataKey={s.key}
              name={lang === 'en' ? s.labelEn : s.labelBm}
              stroke={s.color}
              strokeWidth={2}
              dot={{ r: 3, fill: s.color }}
              activeDot={{ r: 5 }}
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
