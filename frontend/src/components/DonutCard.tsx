import React from 'react';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { ChartTooltip } from './ChartTooltip';

/* Renders both pie shapes the backend emits:
     - object form: { label, data: [{label, count}] }   (waz_class_pie, baz_class_pie, ...)
     - array form:  [{label, count}]                     (status_bmi_pie, gender_split, income_split)
   The wrapper page picks `data` accordingly. */

interface Slice { label: string; count: number; }

interface Props {
  title: string;
  data: Slice[];
  /** Optional custom color resolver — defaults to status-good for any label
      containing "normal"/"good", status-watch for "moderate"/"mild",
      status-critical for "severe"/"underweight" etc, else status-neutral. */
  colorFor?: (label: string) => string;
  innerRadiusPct?: number;  // 0 = pie, ~0.55 = donut (default)
}

const DEFAULT_COLOR_RULES: Array<{ test: RegExp; color: string }> = [
  { test: /normal|baik|good|healthy/i,                      color: 'var(--status-good)' },
  { test: /mild|borderline|sederhana|moderate(?!ly\s+sev)/i, color: 'var(--status-watch)' },
  { test: /severe|critical|underweight|overweight|obes|stunted|wasted/i, color: 'var(--status-critical)' },
];

function defaultColorFor(label: string): string {
  for (const r of DEFAULT_COLOR_RULES) if (r.test.test(label)) return r.color;
  return 'var(--status-neutral)';
}

export function DonutCard({ title, data, colorFor = defaultColorFor, innerRadiusPct = 0.55 }: Props): JSX.Element {
  if (!data || data.length === 0) {
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
        <PieChart>
          <Pie
            data={data}
            dataKey="count"
            nameKey="label"
            cx="50%" cy="50%"
            outerRadius="80%"
            innerRadius={`${Math.round(innerRadiusPct * 80)}%`}
            paddingAngle={1}
            isAnimationActive={false}
            stroke="var(--surface)"
          >
            {data.map((s, i) => <Cell key={i} fill={colorFor(s.label)} />)}
          </Pie>
          <Tooltip content={<ChartTooltip />} />
          <Legend
            verticalAlign="bottom" height={28}
            wrapperStyle={{ fontSize: 11, color: 'var(--text-secondary)' }}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
