import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  ScatterChart, Scatter, ZAxis,
} from 'recharts';
import { api } from '../api/client';
import { ChoroplethMap, computeAggregates } from '../components/ChoroplethMap';
import type { District } from '../components/ChoroplethMap';
import { SessionGuard } from '../components/SessionGuard';
import { ChartTooltip } from '../components/ChartTooltip';
import { RankBars, RankRow } from '../components/RankBars';
import { ErrorRetry } from '../components/ErrorRetry';
import { useSession } from '../context/SessionContext';
import { useLang } from '../context/LanguageContext';
import {
  catalogByHome,
  isHistogramBlock,
  isScatterBlock,
} from '../lib/chartCatalog';
import { formatGroupLabel, GroupLabelKey } from '../lib/labels';
import { formatRange } from '../lib/formatNumber';
import { Maximize2, Download } from 'lucide-react';
import { FocusOverlay } from '../components/FocusOverlay';

// ── KPI types ─────────────────────────────────────────────────────────────────

type IndicatorKey = 'stunting' | 'wasting' | 'underweight' | 'overweight';

interface KpiIndicator {
  key: string; label_en: string; label_bm: string;
  actual: number; actual_count: number; total: number;
  npan_target: number; who_target: number | null; gap: number;
  rag: 'Green' | 'Amber' | 'Red';
}
interface KpiGroupRow {
  state?: string; district?: string; gender?: string; group?: string;
  n?: number;
  rates?: Record<string, number>;
  status?: Record<string, string>;
  [k: string]: unknown;
}
interface KpiDashboard {
  overall_status: 'Green' | 'Amber' | 'Red';
  total_children: number;
  indicators: KpiIndicator[];
  by_state: KpiGroupRow[];
  by_daerah?: KpiGroupRow[];
  by_gender: KpiGroupRow[];
  by_income?: KpiGroupRow[];
  by_age: KpiGroupRow[];
}

// ── Risk types ────────────────────────────────────────────────────────────────

interface RiskDistrict { district: string; avg_risk: number; max_risk: number; n_records: number; }
interface RiskResult {
  total_records: number;
  scored_records: number;
  incomplete_count: number;
  flags_used: string[];
  distribution: Record<string, number>;
  avg_risk_score: number;
  high_risk_count: number;
  district_summary: RiskDistrict[] | null;
}

// ── Trajectory types (Feature 16 — benchmarking & target tracking) ──────────────
interface TrajectoryItem {
  district: string;
  kpi_key: string;
  current_rate: number;
  target: number;
  forecast_2027: number;           // projected RATE (back-compat field name)
  forecast_year: number;           // projected calendar year (configurable)
  trajectory_status: string;       // "On Track" | "At Risk" | "Off Track"
  trajectory_status_bm: string;
  narrative: { en: string; bm: string };
}
interface TrajectoryResp {
  narratives: TrajectoryItem[];
  periods: string[];
  has_multiyear: boolean;
}

// ── Chart blocks types ───────────────────────────────────────────────────────
// Shape guards (isHistogramBlock / isScatterBlock / etc) live in the
// shared lib/chartCatalog so QualityPage and DashboardPage can reuse them.

interface HistogramBlock {
  label: string;
  data: { range: string; count: number }[];
}
interface ScatterBlock {
  title: string;
  x_label: string;
  y_label: string;
  points: { x: number; y: number }[];
}
type ChartBlocks = Record<string, unknown>;

// ── Status palette helpers (Navy-Gold-Brick) ─────────────────────────────────

type Status = 'good' | 'watch' | 'critical' | 'neutral';

const STATUS_VAR: Record<Status, string> = {
  good:     'var(--status-good)',
  watch:    'var(--status-watch)',
  critical: 'var(--status-critical)',
  neutral:  'var(--status-neutral)',
};

function ragToStatus(rag?: string): Status {
  const v = (rag || '').toLowerCase();
  if (v === 'red') return 'critical';
  if (v === 'amber') return 'watch';
  if (v === 'green') return 'good';
  return 'neutral';
}

function tierToStatus(tier: string): Status {
  const v = tier.toLowerCase();
  if (v.includes('high') || v.includes('tinggi')) return 'critical';
  if (v.includes('med') || v.includes('sederhana')) return 'watch';
  if (v.includes('low') || v.includes('rendah')) return 'good';
  return 'neutral';
}

// Trajectory status → RAG colour + sort rank (worst first)
function trajToStatus(status: string): Status {
  const v = status.toLowerCase();
  if (v.includes('off')) return 'critical';
  if (v.includes('risk')) return 'watch';
  if (v.includes('track')) return 'good';   // "On Track"
  return 'neutral';
}
function trajRank(status: string): number {
  const v = status.toLowerCase();
  if (v.includes('off')) return 3;
  if (v.includes('risk')) return 2;
  if (v.includes('track')) return 1;
  return 0;
}
const KPI_LABEL: Record<string, string> = {
  stunting_rate:    'Stunting',
  wasting_rate:     'Wasting',
  underweight_rate: 'Underweight',
  overweight_rate:  'Overweight',
};

/* Client-side CSV download (E1c) — builds the file from already-fetched
   analysis data; RFC-4180 quoting so commas/quotes/newlines survive. */
function downloadCsv(filename: string, headers: string[], rows: (string | number)[][]): void {
  const esc = (v: string | number) => {
    const s = String(v ?? '');
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const csv = [headers, ...rows].map(r => r.map(esc).join(',')).join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

/* Shared icon-button style for the panel focus/export controls. */
const panelIconBtn: React.CSSProperties = {
  background: 'var(--surface-2)', border: '1px solid var(--border)',
  borderRadius: 7, padding: '5px 7px', color: 'var(--text-secondary)',
  cursor: 'pointer', display: 'inline-flex', alignItems: 'center',
};

// ── Small atoms ───────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: Status }) {
  const { t } = useLang();
  const label = status === 'good' ? t('Good', 'Baik')
    : status === 'watch' ? t('Moderate', 'Sederhana')
    : status === 'critical' ? t('Critical', 'Kritikal')
    : t('No data', 'Tiada data');
  // Grades (good/watch/critical) are solid status-hue pills with navy text
  // (≥5.5:1). "No data" is an absence, not a grade — render it as a muted tint
  // pill with secondary text (≥6.8:1) so it neither fails contrast nor reads as
  // a status colour.
  const isGrade = status !== 'neutral';
  return (
    <span style={{
      display: 'inline-block', padding: '2px 10px', borderRadius: 6,
      fontSize: 11, fontWeight: 700,
      background: isGrade ? STATUS_VAR[status] : 'var(--surface-2)',
      color: isGrade ? 'var(--primary-dark)' : 'var(--text-secondary)',
      border: isGrade ? 'none' : '0.5px solid var(--border)',
      letterSpacing: '0.04em',
    }}>
      {label}
    </span>
  );
}

function KpiCard({ label, value, status, onClick, isSelected }: {
  label: string; value: number; status: Status;
  onClick?: () => void; isSelected?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        background: isSelected ? 'var(--surface-3)' : 'var(--surface-2)',
        border: isSelected ? '2px solid var(--brand-sky)' : '0.5px solid var(--border)',
        borderRadius: 10, padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 6,
        cursor: onClick ? 'pointer' : 'default', textAlign: 'left', width: '100%',
        transition: 'border-color var(--transition), background var(--transition)',
        boxShadow: isSelected ? 'var(--glow-accent)' : 'none',
      }}
    >
      <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
        {label}
      </div>
      <div style={{ fontSize: 26, fontWeight: 700, color: 'var(--text-primary)' }}>
        {(value * 100).toFixed(1)}%
      </div>
      <StatusBadge status={status} />
    </button>
  );
}

// ── KPI-to-District mapping ───────────────────────────────────────────────────

const STATE_TO_CODE: Record<string, string> = {
  JOHOR: 'jhr', KEDAH: 'kdh', KELANTAN: 'ktn',
  'KUALA LUMPUR': 'kul', LABUAN: 'lbn', MELAKA: 'mlk',
  'NEGERI SEMBILAN': 'nsn', PAHANG: 'phg', PUTRAJAYA: 'pjy',
  PERLIS: 'pls', PENANG: 'png', 'PULAU PINANG': 'png',
  PERAK: 'prk', SABAH: 'sbh', SELANGOR: 'sgr',
  SARAWAK: 'swk', TERENGGANU: 'trg',
};

function toDistricts(k: KpiDashboard | null, ind: IndicatorKey): District[] {
  if (!k) return [];
  return k.by_state.map(row => {
    const rates = (row.rates as Record<string, number>) ?? {};
    const status = (row.status as Record<string, string>) ?? {};
    const stateName = String(row.state ?? '');
    const ragKey = ragToStatus(status[ind] ?? k.overall_status);
    return {
      name: STATE_TO_CODE[stateName.toUpperCase()] ?? stateName.toLowerCase(),
      stunting_rate: Number(rates.stunting ?? 0) / 100,
      wasting_rate: Number(rates.wasting ?? 0) / 100,
      underweight_rate: Number(rates.underweight ?? 0) / 100,
      overweight_rate: Number(rates.overweight ?? 0) / 100,
      risk_rag: (ragKey === 'good' ? 'green' : ragKey === 'watch' ? 'amber' : 'red'),
      vs_target: 0,
    };
  });
}

// ── Breakdown → RankBars mapping ────────────────────────────────────────────
// Standardized horizontal ranked-bar list (shared with the Dashboard) replaces
// the cramped vertical recharts bars whose x-axis labels overlapped once a
// dataset had many states/daerah. Values are already 0-100 percentages.

const GROUP_LABEL_KEYS: Record<string, GroupLabelKey> = {
  gender: 'gender', group: 'group', income: 'income',
};

function toRankRows(rows: KpiGroupRow[], groupKey: string, indicator: IndicatorKey, lang: 'en' | 'bm'): RankRow[] {
  const labelKey = GROUP_LABEL_KEYS[groupKey];
  return (rows || []).map(r => {
    const rates = (r.rates as Record<string, number>) ?? {};
    const status = (r.status as Record<string, string>) ?? {};
    const raw = String((r as Record<string, unknown>)[groupKey] ?? '—');
    return {
      // Gender/age/income labels are BM-hardcoded by the backend; translate so
      // they follow the toggle. State/daerah are proper nouns → passthrough.
      label: labelKey ? formatGroupLabel(labelKey, raw, lang) : raw,
      value: Number(rates[indicator] ?? 0),
      status: ragToStatus(status[indicator]),
      n: Number(r.n ?? 0),
    };
  });
}

// ── Distribution panels (driven by /charts/blocks via chartCatalog) ─────────
// Keys / titles / "recommended" flags now live in lib/chartCatalog.ts so all
// pages stay in lock-step. GeoPage shows every catalog entry whose `home`
// is 'geo' — currently 7 histograms + 5 scatters.

function HistogramPanel({ title, block, onFocus }: { title: string; block: HistogramBlock; onFocus?: () => void }) {
  return (
    <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-card)', padding: '16px 18px', boxShadow: 'var(--shadow-card)' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
        <div style={{ fontSize: 12, fontWeight: 600 }}>{title}</div>
        {onFocus && (
          <button onClick={onFocus} aria-label="Expand" title="Expand" style={panelIconBtn}>
            <Maximize2 size={13} />
          </button>
        )}
      </div>
      <ResponsiveContainer width="100%" height={176}>
        <BarChart data={block.data} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
          <XAxis
            dataKey="range"
            tick={{ fontSize: 9, fill: 'var(--text-muted)' }}
            interval={block.data.length > 6 ? Math.ceil(block.data.length / 6) - 1 : 0}
            tickFormatter={formatRange}
            angle={-30}
            textAnchor="end"
            height={42}
            tickLine={false}
          />
          <YAxis tick={{ fontSize: 10, fill: 'var(--text-muted)' }} allowDecimals={false} />
          <Tooltip content={<ChartTooltip />} cursor={{ fill: 'var(--surface-2)' }} />
          <Bar dataKey="count" fill="var(--status-good)" radius={[2, 2, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function ScatterPanel({ title, block, onFocus }: { title: string; block: ScatterBlock; onFocus?: () => void }) {
  return (
    <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-card)', padding: '16px 18px', boxShadow: 'var(--shadow-card)' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
        <div style={{ fontSize: 12, fontWeight: 600 }}>{title}</div>
        {onFocus && (
          <button onClick={onFocus} aria-label="Expand" title="Expand" style={panelIconBtn}>
            <Maximize2 size={13} />
          </button>
        )}
      </div>
      <ResponsiveContainer width="100%" height={200}>
        <ScatterChart margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
          <XAxis type="number" dataKey="x" name={block.x_label} tick={{ fontSize: 10, fill: 'var(--text-muted)' }} />
          <YAxis type="number" dataKey="y" name={block.y_label} tick={{ fontSize: 10, fill: 'var(--text-muted)' }} />
          <ZAxis range={[14, 14]} />
          <Tooltip content={<ChartTooltip />} cursor={{ strokeDasharray: '3 3' }} />
          <Scatter data={block.points} fill="var(--status-good)" fillOpacity={0.55} />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export function GeoPage() {
  const { cacheId } = useSession();
  const { t, lang } = useLang();

  const [kpi, setKpi] = useState<KpiDashboard | null>(null);
  const [kpiLoading, setKpiLoading] = useState(false);
  const [kpiError, setKpiError] = useState(false);

  const [risk, setRisk] = useState<RiskResult | null>(null);
  const [riskLoading, setRiskLoading] = useState(false);
  const [riskError, setRiskError] = useState(false);

  const [selectedIndicator, setSelectedIndicator] = useState<IndicatorKey>('stunting');

  const [blocks, setBlocks] = useState<ChartBlocks | null>(null);
  const [blocksLoading, setBlocksLoading] = useState(false);
  const [blocksError, setBlocksError] = useState(false);
  const [showAllDist, setShowAllDist] = useState(false);
  const [trajFocus, setTrajFocus] = useState(false);
  const [focusedChart, setFocusedChart] = useState<string | null>(null);

  const [traj, setTraj] = useState<TrajectoryResp | null>(null);
  const [trajError, setTrajError] = useState(false);

  // Loaders are useCallbacks so the ErrorRetry buttons can re-run the exact
  // fetch that failed (instead of silently leaving a blank panel).
  const loadKpi = useCallback(() => {
    if (!cacheId) return;
    setKpiLoading(true); setKpiError(false);
    api.post<KpiDashboard>(`/kpi/dashboard?cache_id=${cacheId}`)
      .then(r => setKpi(r.data))
      .catch(() => { setKpi(null); setKpiError(true); })
      .finally(() => setKpiLoading(false));
  }, [cacheId]);
  useEffect(() => { loadKpi(); }, [loadKpi]);

  const loadBlocks = useCallback(() => {
    if (!cacheId) return;
    setBlocksLoading(true); setBlocksError(false);
    api.get<ChartBlocks>(`/charts/blocks?cache_id=${cacheId}`)
      .then(r => setBlocks(r.data))
      .catch(() => { setBlocks(null); setBlocksError(true); })
      .finally(() => setBlocksLoading(false));
  }, [cacheId]);
  useEffect(() => { loadBlocks(); }, [loadBlocks]);

  const loadTraj = useCallback(() => {
    if (!cacheId) return;
    setTrajError(false);
    api.post<TrajectoryResp>(`/kpi/trajectory/auto?cache_id=${cacheId}`)
      .then(r => setTraj(r.data))
      .catch(() => { setTraj(null); setTrajError(true); });
  }, [cacheId]);
  useEffect(() => { loadTraj(); }, [loadTraj]);

  const runRisk = async () => {
    if (!cacheId) return;
    setRiskLoading(true); setRiskError(false);
    try {
      const r = await api.post<RiskResult>(`/risk/score?cache_id=${cacheId}`);
      setRisk(r.data);
    } catch { setRisk(null); setRiskError(true); }
    finally { setRiskLoading(false); }
  };

  const districts = toDistricts(kpi, selectedIndicator);
  // NPAN targets come from the KPI response in percent; convert to fractions so
  // the National Average cards grade against the SAME target-relative rule the
  // map and backend use (kpi.py::_rag), instead of fixed absolute thresholds.
  const aggTargets = useMemo(() => {
    const targetFor = (key: string) => {
      const ind = kpi?.indicators.find(i => i.key === key);
      return ind ? Number(ind.npan_target) / 100 : undefined;
    };
    return {
      stunting: targetFor('stunting'),
      wasting: targetFor('wasting'),
      underweight: targetFor('underweight'),
      overweight: targetFor('overweight'),
    };
  }, [kpi]);
  const agg = computeAggregates(districts, aggTargets);

  // ── Selected indicator label for chart headers ────────────────────────────
  const indMeta = kpi?.indicators.find(i => i.key === selectedIndicator);
  const indLabel = indMeta ? (lang === 'en' ? indMeta.label_en : indMeta.label_bm) : '';

  // ── Risk tier distribution for the bar chart ──────────────────────────────
  const distributionData = useMemo(() => {
    if (!risk) return [] as { tier: string; count: number; status: Status }[];
    return Object.entries(risk.distribution)
      .map(([tier, count]) => ({ tier, count, status: tierToStatus(tier) }));
  }, [risk]);

  return (
    <SessionGuard>
      <div style={{ padding: '4px 0' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12, marginBottom: 20 }}>
          <h1 style={{ margin: 0, fontSize: 22, fontWeight: 700, color: 'var(--text-primary)' }}>
            {t('Geography & Risk Map', 'Peta Geografi & Risiko')}
          </h1>
          <select
            value={selectedIndicator}
            onChange={e => setSelectedIndicator(e.target.value as IndicatorKey)}
            style={{
              background: 'var(--surface)', border: '1px solid var(--border)',
              borderRadius: 'var(--radius-btn)', padding: '7px 12px', fontSize: 13,
              color: 'var(--text-primary)', cursor: 'pointer',
            }}
          >
            {(kpi?.indicators ?? []).map(i => (
              <option key={i.key} value={i.key}>{lang === 'en' ? i.label_en : i.label_bm}</option>
            ))}
            {!kpi?.indicators.length && (
              <option value="stunting">{t('Stunting', 'Kelaparan')}</option>
            )}
          </select>
        </div>

        {kpiLoading && (
          <div style={{ color: 'var(--text-secondary)', fontSize: 13, marginBottom: 16 }}>
            {t('Loading KPI data…', 'Memuatkan data KPI…')}
          </div>
        )}

        {/* Choropleth + KPI aggregate cards — map takes 60%, taller for breathing room */}
        <div style={{ display: 'flex', gap: 20, alignItems: 'flex-start', marginBottom: 24, flexWrap: 'wrap' }}>
          <div style={{
            flex: '1 1 540px', minWidth: 360, background: 'var(--surface-2)',
            border: '0.5px solid var(--border)', borderRadius: 12,
            padding: 12, boxSizing: 'border-box',
          }}>
            {kpiError
              ? <ErrorRetry message={t('Could not load KPI data.', 'Tidak dapat memuatkan data KPI.')} onRetry={loadKpi} />
              : districts.length === 0
              ? <div style={{ padding: 32, textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>
                  {t('No KPI data — run cleaning first.', 'Tiada data KPI — jalankan pembersihan dahulu.')}
                </div>
              : <ChoroplethMap districts={districts} />}
          </div>
          <div style={{ flex: '1 1 320px', minWidth: 280, display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div style={{ fontSize: 12, color: 'var(--text-secondary)', fontWeight: 500 }}>
              {t('National Average', 'Purata Nasional')}{districts.length > 0 ? ` (${districts.length} ${t('states', 'negeri')})` : ''}
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <KpiCard label={t('Stunting', 'Kelaparan')}           value={agg.stunting}    status={ragToStatus(agg.stuntingRag)}    onClick={() => setSelectedIndicator('stunting')}    isSelected={selectedIndicator === 'stunting'} />
              <KpiCard label={t('Wasting', 'Kurus')}                value={agg.wasting}     status={ragToStatus(agg.wastingRag)}     onClick={() => setSelectedIndicator('wasting')}     isSelected={selectedIndicator === 'wasting'} />
              <KpiCard label={t('Underweight', 'Kekurangan Berat')} value={agg.underweight} status={ragToStatus(agg.underweightRag)} onClick={() => setSelectedIndicator('underweight')} isSelected={selectedIndicator === 'underweight'} />
              <KpiCard label={t('Overweight', 'Berlebihan Berat')}  value={agg.overweight}  status={ragToStatus(agg.overweightRag)}  onClick={() => setSelectedIndicator('overweight')}  isSelected={selectedIndicator === 'overweight'} />
            </div>
          </div>
        </div>

        {/* Indicators vs NPAN target — themed tooltip + status colors */}
        {kpi && kpi.indicators.length > 0 && (
          <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-card)', padding: '18px 20px', boxShadow: 'var(--shadow-card)', marginTop: 20 }}>
            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>
              {t('Indicators vs National Target', 'Penunjuk lwn Sasaran Kebangsaan')}
            </div>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={kpi.indicators.map(i => ({
                name: lang === 'en' ? i.label_en : i.label_bm,
                actual: i.actual, target: i.npan_target,
                status: ragToStatus(i.rag),
              }))} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
                <XAxis dataKey="name" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} />
                <YAxis tick={{ fontSize: 10, fill: 'var(--text-muted)' }} unit="%" />
                <Tooltip content={<ChartTooltip valueFormatter={v => typeof v === 'number' ? `${v.toFixed(1)}%` : String(v)} />} cursor={{ fill: 'var(--surface-2)' }} />
                <Bar dataKey="actual" name={t('Actual', 'Sebenar')} maxBarSize={44} radius={[6, 6, 0, 0]}>
                  {kpi.indicators.map((i, idx) => <Cell key={idx} fill={STATUS_VAR[ragToStatus(i.rag)]} />)}
                </Bar>
                <Bar dataKey="target" name={t('Target', 'Sasaran')} fill="var(--text-muted)" maxBarSize={44} radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Breakdown ranked bars — filtered by the global indicator selector */}
        {kpi && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 16, marginTop: 16 }}>
            <RankBars title={`${t('By State', 'Mengikut Negeri')} — ${indLabel}`}   rows={toRankRows(kpi.by_state, 'state', selectedIndicator, lang)}      lang={lang} />
            {(kpi.by_daerah?.length ?? 0) > 0 && (
              <RankBars title={`${t('By Daerah', 'Mengikut Daerah')} — ${indLabel}`} rows={toRankRows(kpi.by_daerah!, 'district', selectedIndicator, lang)} lang={lang} />
            )}
            <RankBars title={`${t('By Gender', 'Mengikut Jantina')} — ${indLabel}`} rows={toRankRows(kpi.by_gender, 'gender', selectedIndicator, lang)}    lang={lang} />
            {(kpi.by_income?.length ?? 0) > 0 && (
              <RankBars title={`${t('By Income', 'Mengikut Pendapatan')} — ${indLabel}`} rows={toRankRows(kpi.by_income!, 'income', selectedIndicator, lang)} lang={lang} />
            )}
            <RankBars title={`${t('By Age', 'Mengikut Umur')} — ${indLabel}`}       rows={toRankRows(kpi.by_age, 'group', selectedIndicator, lang)}        lang={lang} />
          </div>
        )}

        {/* Predictive risk scoring card (on-demand) */}
        <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-card)', padding: '18px 20px', boxShadow: 'var(--shadow-card)', marginTop: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10, marginBottom: risk ? 16 : 0 }}>
            <div>
              <div style={{ fontSize: 13, fontWeight: 600 }}>{t('Composite Risk Index', 'Indeks Risiko Komposit')}</div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
                {t('Composite child-level malnutrition risk (0-100)', 'Risiko malnutrisi peringkat kanak-kanak (0-100)')}
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              {risk === null && (
                <button onClick={runRisk} disabled={riskLoading}
                  style={{ background: 'var(--brand-blue)', color: '#fff', border: 'none', borderRadius: 'var(--radius-btn)', padding: '8px 16px', fontSize: 13, fontWeight: 600, cursor: 'pointer', opacity: riskLoading ? 0.6 : 1 }}>
                  {riskLoading ? t('Scoring…', 'Memarkah…') : t('Run Risk Scoring', 'Jalankan Pemarkahan')}
                </button>
              )}
            </div>
          </div>

          {riskError && !risk && (
            <ErrorRetry compact message={t('Risk scoring failed.', 'Pemarkahan risiko gagal.')} onRetry={runRisk} />
          )}

          {risk && (
            <>
              <div style={{ display: 'flex', gap: 24, marginBottom: 16, fontSize: 13, flexWrap: 'wrap' }}>
                {([
                  [t('Records', 'Rekod'), risk.total_records],
                  [t('Avg risk', 'Risiko purata'), risk.avg_risk_score],
                  [t('High risk', 'Risiko tinggi'), risk.high_risk_count],
                ] as [string, number][]).map(([l, v]) => (
                  <div key={l}>
                    <div style={{ color: 'var(--text-muted)', fontSize: 11 }}>{l}</div>
                    <div style={{ fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{v}</div>
                  </div>
                ))}
              </div>

              <ResponsiveContainer width="100%" height={180}>
                <BarChart data={distributionData} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
                  <XAxis dataKey="tier" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} />
                  <YAxis tick={{ fontSize: 10, fill: 'var(--text-muted)' }} allowDecimals={false} />
                  <Tooltip content={<ChartTooltip />} cursor={{ fill: 'var(--surface-2)' }} />
                  <Bar dataKey="count" maxBarSize={44} radius={[6, 6, 0, 0]}>
                    {distributionData.map((d, i) => <Cell key={i} fill={STATUS_VAR[d.status]} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>

              {risk.district_summary && risk.district_summary.length > 0 && (
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, marginTop: 16 }}>
                  <thead><tr style={{ borderBottom: '1px solid var(--border)' }}>
                    {[t('District', 'Daerah'), t('Avg', 'Purata'), t('Max', 'Maks'), t('N', 'N')].map(h => (
                      <th key={h} style={{ padding: '8px 10px', textAlign: 'left', fontWeight: 600, fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>{h}</th>
                    ))}
                  </tr></thead>
                  <tbody>
                    {risk.district_summary.map((d, i) => (
                      <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                        <td style={{ padding: '8px 10px', color: 'var(--text-primary)' }}>{d.district}</td>
                        <td style={{ padding: '8px 10px', fontFamily: 'var(--font-mono)' }}>{d.avg_risk}</td>
                        <td style={{ padding: '8px 10px', fontFamily: 'var(--font-mono)' }}>{d.max_risk}</td>
                        <td style={{ padding: '8px 10px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>{d.n_records}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </>
          )}
        </div>

        {/* Target trajectory (Feature 16 — 2027 benchmarking) */}
        {traj && (() => {
          /* Sort worst-first, then count "off track" from the SAME rendered
             list so the header summary always matches what's on screen (it
             reflects any future filter applied to `rows`, not the raw set). */
          const rows = [...traj.narratives]
            .sort((a, b) => trajRank(b.trajectory_status) - trajRank(a.trajectory_status));
          const offTrack = rows.filter(n => trajToStatus(n.trajectory_status) === 'critical').length;
          // Forecast year is the configured target year (consistent across rows);
          // latest data year comes from periods. The gap drives an honesty note —
          // a projection many years out from a short trend is only indicative.
          const forecastYear = rows.length ? rows[0].forecast_year : null;
          const latestYear = traj.periods.length
            ? Math.max(...traj.periods.map(p => parseInt(p, 10)).filter(Number.isFinite))
            : null;
          const yearsOut = (forecastYear != null && latestYear != null && Number.isFinite(latestYear))
            ? forecastYear - latestYear : null;
          const trajTitle = `${t('Target Trajectory', 'Trajektori Sasaran')}${forecastYear != null ? ` (${forecastYear})` : ''}`;
          const exportTrajectoryCsv = () => downloadCsv(
            `SmartDQC_Trajectory_${forecastYear ?? 'forecast'}.csv`,
            ['District', 'Indicator', 'Current %', 'Forecast %', 'Target %', 'Forecast Year', 'Status'],
            rows.map(n => [
              n.district, KPI_LABEL[n.kpi_key] ?? n.kpi_key, n.current_rate,
              n.forecast_2027, n.target, n.forecast_year, n.trajectory_status,
            ]),
          );
          // One list renderer for both the inline (capped) card and the
          // uncapped focus overlay, so the two never drift.
          const trajList = (capped: boolean) => (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, ...(capped ? { maxHeight: 340, overflowY: 'auto' } : {}) }}>
              {rows.map((n, i) => {
                const st = trajToStatus(n.trajectory_status);
                return (
                  <div key={i} style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-btn)', padding: '10px 12px', background: 'var(--surface-2)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 4 }}>
                      <span style={{ fontWeight: 600, fontSize: 13, color: 'var(--text-primary)' }}>{n.district}</span>
                      <span style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase' }}>{KPI_LABEL[n.kpi_key] ?? n.kpi_key}</span>
                      <span style={{ fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 999, background: STATUS_VAR[st], color: 'var(--primary-dark)' }}>
                        {lang === 'en' ? n.trajectory_status : n.trajectory_status_bm}
                      </span>
                      <span style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginLeft: 'auto' }}>
                        {n.current_rate}% → {n.forecast_2027}% ({t('target', 'sasaran')} {n.target}%)
                      </span>
                    </div>
                    <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                      {lang === 'en' ? n.narrative.en : n.narrative.bm}
                    </div>
                  </div>
                );
              })}
            </div>
          );
          return (
          <>
          <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-card)', padding: '18px 20px', boxShadow: 'var(--shadow-card)', marginTop: 20 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              <div style={{ fontSize: 13, fontWeight: 600 }}>{trajTitle}</div>
              {offTrack > 0 && (
                <span style={{ fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 999, background: STATUS_VAR.critical, color: '#FFFFFF' }}>
                  {offTrack} {t('off track', 'tidak menuju sasaran')}
                </span>
              )}
              {rows.length > 0 && (
                <div style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
                  <button onClick={exportTrajectoryCsv} aria-label={t('Export CSV', 'Eksport CSV')} title={t('Export CSV', 'Eksport CSV')} style={panelIconBtn}>
                    <Download size={14} />
                  </button>
                  <button onClick={() => setTrajFocus(true)} aria-label={t('Expand', 'Kembang')} title={t('Expand', 'Kembang')} style={panelIconBtn}>
                    <Maximize2 size={14} />
                  </button>
                </div>
              )}
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2, marginBottom: yearsOut != null && yearsOut >= 5 ? 8 : 14 }}>
              {t('Projected vs NPAN target per district, based on historical years.',
                 'Unjuran berbanding sasaran NPAN setiap daerah, berdasarkan tahun sejarah.')}
            </div>
            {/* E1a honesty note: a projection many years past the latest data is
                only indicative — say so rather than implying false precision. */}
            {yearsOut != null && yearsOut >= 5 && (
              <div style={{ fontSize: 11, color: 'var(--text-secondary)', background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 8, padding: '7px 11px', marginBottom: 14, display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ width: 8, height: 8, borderRadius: 2, background: 'var(--warning)', flexShrink: 0 }} />
                {t(`Projecting ${yearsOut} years beyond the latest data (${latestYear}) — treat as indicative, not a precise forecast.`,
                   `Unjuran ${yearsOut} tahun selepas data terkini (${latestYear}) — anggap sebagai petunjuk, bukan ramalan tepat.`)}
              </div>
            )}
            {rows.length === 0 ? (
              <div style={{ fontSize: 12, color: 'var(--text-muted)', padding: '8px 0' }}>
                {t('Requires multi-year data (≥2 measurement years per district) to project a trajectory.',
                   'Memerlukan data berbilang tahun (≥2 tahun pengukuran setiap daerah) untuk unjuran trajektori.')}
              </div>
            ) : trajList(true)}
          </div>
          <FocusOverlay open={trajFocus} onClose={() => setTrajFocus(false)} title={trajTitle}>
            {trajList(false)}
          </FocusOverlay>
          </>
          );
        })()}
        {!traj && trajError && (
          <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-card)', boxShadow: 'var(--shadow-card)', marginTop: 20 }}>
            <ErrorRetry compact message={t('Could not load target trajectory.', 'Tidak dapat memuatkan trajektori sasaran.')} onRetry={loadTraj} />
          </div>
        )}

        {/* Distributions & relationships — 12 charts (7 histograms + 5 scatters)
            sourced from chartCatalog. The "Show all" toggle is kept for parity
            with prior UX but recommended already covers the full catalog for
            this page. */}
        {(blocks || blocksLoading || blocksError) && (
          <div style={{ marginTop: 24 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
              <div style={{ fontSize: 13, fontWeight: 600 }}>
                {t('Distributions & relationships', 'Taburan & hubungan')}
              </div>
              {blocks && (
                <button
                  onClick={() => setShowAllDist(s => !s)}
                  style={{ background: 'none', border: 'none', color: 'var(--status-good)', fontWeight: 600, fontSize: 12, cursor: 'pointer' }}
                >
                  {showAllDist ? t('Show recommended only', 'Tunjuk yang disyorkan sahaja') : t('Show all', 'Tunjuk semua')}
                </button>
              )}
            </div>
            {blocksLoading ? (
              <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>{t('Loading distributions…', 'Memuatkan taburan…')}</div>
            ) : blocksError ? (
              <ErrorRetry compact message={t('Could not load distributions.', 'Tidak dapat memuatkan taburan.')} onRetry={loadBlocks} />
            ) : blocks ? (
              <>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 14 }}>
                  {(() => {
                    // "Recommended" = catalog entries with recommended:true (7 histograms).
                    // "Show all" = all catalog entries + any extra histogram/scatter blocks
                    // from the backend that aren't yet in the catalog.
                    const geoCatalog = catalogByHome('geo');
                    const allCatalogKeys = geoCatalog.map(e => e.key);
                    const recommendedKeys = geoCatalog.filter(e => e.recommended).map(e => e.key);
                    const allHistOrScatter = Object.keys(blocks).filter(k => {
                      const b = blocks[k];
                      return isHistogramBlock(b) || isScatterBlock(b);
                    });
                    const keysToRender = showAllDist
                      ? Array.from(new Set([...allCatalogKeys, ...allHistOrScatter]))
                      : recommendedKeys.filter(k => k in blocks);
                    return keysToRender.map(key => {
                      const b = blocks[key];
                      const entry = geoCatalog.find(e => e.key === key);
                      const title = entry
                        ? (lang === 'en' ? entry.titleEn : entry.titleBm)
                        : key;
                      if (isScatterBlock(b))   return <ScatterPanel   key={key} title={title} block={b} onFocus={() => setFocusedChart(key)} />;
                      if (isHistogramBlock(b)) return <HistogramPanel key={key} title={title} block={b} onFocus={() => setFocusedChart(key)} />;
                      return null;
                    });
                  })()}
                </div>
                {focusedChart && (() => {
                  const b = blocks[focusedChart];
                  const entry = catalogByHome('geo').find(e => e.key === focusedChart);
                  const title = entry ? (lang === 'en' ? entry.titleEn : entry.titleBm) : focusedChart;
                  return (
                    <FocusOverlay open onClose={() => setFocusedChart(null)} title={title}>
                      {isHistogramBlock(b) && <HistogramPanel title={title} block={b} />}
                      {isScatterBlock(b)   && <ScatterPanel   title={title} block={b} />}
                    </FocusOverlay>
                  );
                })()}
              </>
            ) : null}
          </div>
        )}
      </div>
    </SessionGuard>
  );
}
