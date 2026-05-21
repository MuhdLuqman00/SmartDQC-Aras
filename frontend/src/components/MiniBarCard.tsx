import React, { useId, useMemo } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, CartesianGrid, LabelList } from 'recharts';
import { ChartTooltip } from './ChartTooltip';

/* Renders backend payloads of shape `[{<labelKey>, count}]`
   (records_by_negeri, vaccine_distribution) or `[{label, count}]`
   (gender_split, income_split) — pass labelKey accordingly.

   Each bar gets its own categorical color from the `--chart-N` ramp so
   the chart reads as a distribution rather than a wall of one hue. A
   vertical linear-gradient (chart-N → chart-N-deep) gives every bar a
   subtle depth without resorting to neon. */

interface Props {
  title: string;
  data: Record<string, unknown>[];
  labelKey: string;
  /** Top-N truncation in case the backend returns many slices. */
  maxBars?: number;
}

const CHART_VARS = ['--chart-1', '--chart-2', '--chart-3', '--chart-4', '--chart-5', '--chart-6'] as const;
const CHART_DEEP_VARS = ['--chart-1-deep', '--chart-2-deep', '--chart-3-deep', '--chart-4-deep', '--chart-5-deep', '--chart-6-deep'] as const;

export function MiniBarCard({ title, data, labelKey, maxBars = 12 }: Props): JSX.Element {
  const gradId = useId().replace(/:/g, '');
  const rows = useMemo(() =>
    (data || [])
      .filter(d => d && d[labelKey] != null && d.count != null)
      .map(d => ({ label: String(d[labelKey]), count: Number(d.count) }))
      .sort((a, b) => b.count - a.count)
      .slice(0, maxBars),
    [data, labelKey, maxBars]
  );

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
      <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8, color: 'var(--text-primary)' }}>{title}</div>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={rows} margin={{ top: 18, right: 8, left: -12, bottom: 0 }}>
          <defs>
            {CHART_VARS.map((cv, i) => (
              <linearGradient key={i} id={`bar-${gradId}-${i}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={`var(${cv})`} stopOpacity={1} />
                <stop offset="100%" stopColor={`var(${CHART_DEEP_VARS[i]})`} stopOpacity={1} />
              </linearGradient>
            ))}
          </defs>
          <CartesianGrid stroke="var(--chart-grid)" strokeDasharray="2 4" vertical={false} />
          <XAxis
            dataKey="label"
            tick={{ fontSize: 10, fill: 'var(--chart-axis)' }}
            interval={0}
            angle={rows.length > 6 ? -30 : 0}
            textAnchor={rows.length > 6 ? 'end' : 'middle'}
            height={rows.length > 6 ? 50 : 30}
            tickLine={false}
            axisLine={{ stroke: 'var(--chart-grid)' }}
          />
          <YAxis
            tick={{ fontSize: 10, fill: 'var(--chart-axis)' }}
            allowDecimals={false}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip content={<ChartTooltip />} cursor={{ fill: 'var(--chart-track)', opacity: 0.5 }} />
          <Bar dataKey="count" radius={[6, 6, 0, 0]} maxBarSize={48} isAnimationActive={false}>
            {rows.map((_, i) => (
              <Cell key={i} fill={`url(#bar-${gradId}-${i % CHART_VARS.length})`} />
            ))}
            <LabelList
              dataKey="count"
              position="top"
              style={{ fontSize: 10, fill: 'var(--text-secondary)', fontFamily: 'JetBrains Mono, monospace' }}
              formatter={(v: number) => (v >= 1000 ? `${(v / 1000).toFixed(1)}k` : String(v))}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
