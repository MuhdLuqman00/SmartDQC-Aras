import React, { useId, useMemo, useState } from 'react';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend, Sector } from 'recharts';
import { ChartTooltip } from './ChartTooltip';

/* Renders both pie shapes the backend emits:
     - object form: { label, data: [{label, count}] }   (waz_class_pie, baz_class_pie, ...)
     - array form:  [{label, count}]                     (status_bmi_pie, gender_split, income_split)
   The wrapper page picks `data` accordingly.

   Auto-coloring: status-class pies (labels containing normal/mild/severe/...)
   keep the severity palette. Everything else rotates through the categorical
   `--chart-N` tokens — a brand-anchored navy → sky → teal → gold →
   terracotta → periwinkle ramp. */

interface Slice { label: string; count: number; }

interface Props {
  title: string;
  data: Slice[];
  /** Override the auto-detected coloring. */
  colorFor?: (label: string, index: number) => string;
  innerRadiusPct?: number;  // 0 = pie, ~0.55 = donut (default)
}

const STATUS_RULES: Array<{ test: RegExp; color: string }> = [
  { test: /normal|baik|good|healthy/i,                       color: 'var(--status-good)' },
  { test: /mild|borderline|sederhana|moderate(?!ly\s+sev)/i, color: 'var(--status-watch)' },
  { test: /severe|critical|underweight|overweight|obes|stunted|wasted/i, color: 'var(--status-critical)' },
];

const CHART_VARS = ['--chart-1', '--chart-2', '--chart-3', '--chart-4', '--chart-5', '--chart-6'] as const;
const CHART_DEEP_VARS = ['--chart-1-deep', '--chart-2-deep', '--chart-3-deep', '--chart-4-deep', '--chart-5-deep', '--chart-6-deep'] as const;

function isStatusLabel(label: string): boolean {
  return STATUS_RULES.some(r => r.test.test(label));
}

function statusColorFor(label: string): string {
  for (const r of STATUS_RULES) if (r.test.test(label)) return r.color;
  return 'var(--status-neutral)';
}

interface ActiveShapeProps {
  cx?: number; cy?: number; innerRadius?: number; outerRadius?: number;
  startAngle?: number; endAngle?: number; fill?: string;
}

function ActiveSlice(props: ActiveShapeProps): JSX.Element {
  const { cx = 0, cy = 0, innerRadius = 0, outerRadius = 0, startAngle = 0, endAngle = 0, fill } = props;
  return (
    <g>
      <Sector
        cx={cx} cy={cy}
        innerRadius={innerRadius}
        outerRadius={outerRadius + 6}
        startAngle={startAngle} endAngle={endAngle}
        fill={fill}
      />
      <Sector
        cx={cx} cy={cy}
        innerRadius={outerRadius + 8}
        outerRadius={outerRadius + 11}
        startAngle={startAngle} endAngle={endAngle}
        fill={fill}
        opacity={0.35}
      />
    </g>
  );
}

export function DonutCard({ title, data, colorFor, innerRadiusPct = 0.55 }: Props): JSX.Element {
  const gradId = useId().replace(/:/g, '');
  const [activeIndex, setActiveIndex] = useState<number | undefined>(undefined);

  const resolved = useMemo(() => {
    if (!data || data.length === 0) return [];
    const useStatus = data.some(d => isStatusLabel(d.label));
    return data.map((s, i) => ({
      ...s,
      fill: colorFor
        ? colorFor(s.label, i)
        : useStatus
          ? statusColorFor(s.label)
          : `var(${CHART_VARS[i % CHART_VARS.length]})`,
      stop: useStatus || colorFor
        ? undefined
        : `var(${CHART_DEEP_VARS[i % CHART_DEEP_VARS.length]})`,
    }));
  }, [data, colorFor]);

  const total = useMemo(() => resolved.reduce((s, d) => s + (Number(d.count) || 0), 0), [resolved]);

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
      position: 'relative',
    }}>
      <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8, color: 'var(--text-primary)' }}>{title}</div>
      <div style={{ position: 'relative' }}>
        <ResponsiveContainer width="100%" height={220}>
          <PieChart>
            <defs>
              {resolved.map((s, i) => (
                <radialGradient key={i} id={`donut-${gradId}-${i}`} cx="50%" cy="50%" r="65%">
                  <stop offset="0%" stopColor={s.fill} stopOpacity={1} />
                  <stop offset="100%" stopColor={s.stop ?? s.fill} stopOpacity={1} />
                </radialGradient>
              ))}
            </defs>
            <Pie
              data={resolved}
              dataKey="count"
              nameKey="label"
              cx="50%" cy="50%"
              outerRadius="78%"
              innerRadius={`${Math.round(innerRadiusPct * 78)}%`}
              paddingAngle={2}
              cornerRadius={4}
              stroke="var(--surface)"
              strokeWidth={2}
              isAnimationActive={false}
              activeIndex={activeIndex}
              activeShape={ActiveSlice}
              onMouseEnter={(_, i) => setActiveIndex(i)}
              onMouseLeave={() => setActiveIndex(undefined)}
            >
              {resolved.map((s, i) => (
                <Cell key={i} fill={`url(#donut-${gradId}-${i})`} />
              ))}
            </Pie>
            <Tooltip
              content={
                <ChartTooltip
                  valueFormatter={(v) => {
                    const n = Number(v);
                    if (!Number.isFinite(n) || total === 0) return String(v);
                    return `${n.toLocaleString()} (${((n / total) * 100).toFixed(1)}%)`;
                  }}
                />
              }
            />
            <Legend
              verticalAlign="bottom" height={28} iconType="circle" iconSize={8}
              wrapperStyle={{ fontSize: 11, color: 'var(--text-secondary)' }}
            />
          </PieChart>
        </ResponsiveContainer>
        {innerRadiusPct > 0 && total > 0 && (
          <div style={{
            position: 'absolute', inset: 0, display: 'flex',
            flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            pointerEvents: 'none', transform: 'translateY(-14px)',
          }}>
            <div style={{
              fontSize: 18, fontWeight: 700, color: 'var(--text-primary)',
              fontFamily: 'JetBrains Mono, monospace', lineHeight: 1,
            }}>
              {total.toLocaleString()}
            </div>
            <div style={{ fontSize: 9, color: 'var(--text-muted)', letterSpacing: '0.05em', marginTop: 3, textTransform: 'uppercase' }}>
              Total
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
