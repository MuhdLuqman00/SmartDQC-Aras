import React from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { ChartTooltip } from './ChartTooltip';

/* Renders backend payloads of shape `[{<labelKey>, count}]`
   (records_by_negeri, vaccine_distribution) or `[{label, count}]`
   (gender_split, income_split) — pass labelKey accordingly. */

interface Props {
  title: string;
  data: Record<string, unknown>[];
  labelKey: string;
  /** Top-N truncation in case the backend returns many slices. */
  maxBars?: number;
}

export function MiniBarCard({ title, data, labelKey, maxBars = 12 }: Props): JSX.Element {
  const rows = (data || [])
    .filter(d => d && d[labelKey] != null && d.count != null)
    .map(d => ({ label: String(d[labelKey]), count: Number(d.count) }))
    .sort((a, b) => b.count - a.count)
    .slice(0, maxBars);

  if (!rows.length) {
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
      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={rows} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
          <XAxis
            dataKey="label"
            tick={{ fontSize: 9, fill: 'var(--text-muted)' }}
            interval={0}
            angle={rows.length > 6 ? -30 : 0}
            textAnchor={rows.length > 6 ? 'end' : 'middle'}
            height={rows.length > 6 ? 50 : 30}
          />
          <YAxis tick={{ fontSize: 10, fill: 'var(--text-muted)' }} allowDecimals={false} />
          <Tooltip content={<ChartTooltip />} cursor={{ fill: 'var(--surface-2)' }} />
          <Bar dataKey="count" fill="var(--status-good)" radius={[2, 2, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
