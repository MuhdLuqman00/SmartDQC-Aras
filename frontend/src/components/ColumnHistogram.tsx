import React, { useId, useMemo } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { ChartTooltip } from './ChartTooltip';
import { formatCompact } from '../lib/formatNumber';

export function ColumnHistogram({ values, bins = 12 }: { values: number[]; bins?: number }) {
  const gradId = useId().replace(/:/g, '');
  const data = useMemo(() => {
    const nums = values.filter(v => typeof v === 'number' && Number.isFinite(v));
    if (nums.length === 0) return [];
    const min = Math.min(...nums);
    const max = Math.max(...nums);
    if (min === max) return [{ label: String(min), count: nums.length }];
    const width = (max - min) / bins;
    const buckets = Array.from({ length: bins }, (_, i) => ({
      label: (min + i * width).toFixed(1),
      count: 0,
    }));
    for (const n of nums) {
      let idx = Math.floor((n - min) / width);
      if (idx >= bins) idx = bins - 1;
      if (idx < 0) idx = 0;
      buckets[idx].count += 1;
    }
    return buckets;
  }, [values, bins]);

  if (data.length === 0) {
    return (
      <div style={{ fontSize: 12, color: 'var(--text-muted)', padding: '12px 0' }}>
        No numeric values to plot.
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} margin={{ top: 6, right: 8, left: -16, bottom: 0 }}>
        <defs>
          <linearGradient id={`hist-${gradId}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--chart-6)" stopOpacity={1} />
            <stop offset="100%" stopColor="var(--chart-6-deep)" stopOpacity={1} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke="var(--chart-grid)" strokeDasharray="2 4" vertical={false} />
        <XAxis
          dataKey="label"
          tick={{ fontSize: 10, fill: 'var(--chart-axis)' }}
          // Thin ticks (~8 max) and compact-format them so huge IC numbers
          // don't collide; the tooltip header keeps the full bucket value.
          interval={data.length > 8 ? Math.ceil(data.length / 8) - 1 : 0}
          tickFormatter={(v) => formatCompact(Number(v))}
          angle={-30}
          textAnchor="end"
          height={50}
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
        <Bar dataKey="count" fill={`url(#hist-${gradId})`} radius={[4, 4, 0, 0]} isAnimationActive={false} />
      </BarChart>
    </ResponsiveContainer>
  );
}
