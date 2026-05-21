import React, { useEffect, useMemo, useState } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  ScatterChart, Scatter, ZAxis,
} from 'recharts';
import { api } from '../api/client';
import { ChoroplethMap, computeAggregates } from '../components/ChoroplethMap';
import type { District } from '../components/ChoroplethMap';
import { SessionGuard } from '../components/SessionGuard';
import { ChartTooltip } from '../components/ChartTooltip';
import { useSession } from '../context/SessionContext';
import { useLang } from '../context/LanguageContext';
import {
  catalogByHome,
  isHistogramBlock,
  isScatterBlock,
} from '../lib/chartCatalog';

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
  by_age: KpiGroupRow[];
}

// ── Risk types ────────────────────────────────────────────────────────────────

interface RiskDistrict { district: string; avg_risk: number; max_risk: number; n_records: number; }
interface RiskSampleRow { IC_NO_PASSPORT?: string; NAMA?: string; risk_score: number; risk_tier: string; [k: string]: unknown; }
interface RiskResult {
  total_records: number;
  flags_used: string[];
  distribution: Record<string, number>;
  avg_risk_score: number;
  high_risk_count: number;
  district_summary: RiskDistrict[] | null;
  high_risk_sample: RiskSampleRow[];
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
const STATUS_BG: Record<Status, string> = {
  good:     'var(--status-good-bg)',
  watch:    'var(--status-watch-bg)',
  critical: 'var(--status-critical-bg)',
  neutral:  'var(--surface-2)',
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

// ── Small atoms ───────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: Status }) {
  const { t } = useLang();
  const label = status === 'good' ? t('Good', 'Baik')
    : status === 'watch' ? t('Moderate', 'Sederhana')
    : status === 'critical' ? t('Critical', 'Kritikal')
    : t('No data', 'Tiada data');
  return (
    <span style={{
      display: 'inline-block', padding: '2px 10px', borderRadius: 6,
      fontSize: 11, fontWeight: 700, background: STATUS_BG[status],
      color: STATUS_VAR[status], border: `0.5px solid ${STATUS_VAR[status]}`,
      letterSpacing: '0.04em',
    }}>
      {label}
    </span>
  );
}

function KpiCard({ label, value, status }: { label: string; value: number; status: Status }) {
  return (
    <div style={{
      background: 'var(--surface-2)', border: '0.5px solid var(--border)',
      borderRadius: 10, padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 6,
    }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
        {label}
      </div>
      <div style={{ fontSize: 26, fontWeight: 700, color: 'var(--text-primary)' }}>
        {(value * 100).toFixed(1)}%
      </div>
      <StatusBadge status={status} />
    </div>
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

// ── Breakdown chart ───────────────────────────────────────────────────────────

const labelKeyForRow = (row: KpiGroupRow, groupKey: string): string =>
  String((row as Record<string, unknown>)[groupKey] ?? '');

function BreakdownChart({
  title, rows, groupKey, indicator,
}: {
  title: string; rows: KpiGroupRow[]; groupKey: 'state' | 'district' | 'gender' | 'group'; indicator: IndicatorKey;
}) {
  const { lang } = useLang();
  const data = useMemo(() => rows.map(r => {
    const rates = (r.rates as Record<string, number>) ?? {};
    const status = (r.status as Record<string, string>) ?? {};
    return {
      label: labelKeyForRow(r, groupKey),
      value: Number(rates[indicator] ?? 0),
      status: ragToStatus(status[indicator]),
      n: Number(r.n ?? 0),
    };
  }), [rows, groupKey, indicator]);
  void lang;
  if (!data.length) return null;
  return (
    <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-card)', padding: '16px 18px', boxShadow: 'var(--shadow-card)' }}>
      <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8 }}>{title}</div>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
          <XAxis dataKey="label" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} interval={0} />
          <YAxis tick={{ fontSize: 10, fill: 'var(--text-muted)' }} unit="%" domain={[0, 'auto']} />
          <Tooltip content={<ChartTooltip valueFormatter={v => typeof v === 'number' ? `${v.toFixed(1)}%` : String(v)} />} cursor={{ fill: 'var(--surface-2)' }} />
          <Bar dataKey="value">
            {data.map((d, i) => <Cell key={i} fill={STATUS_VAR[d.status]} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── Distribution panels (driven by /charts/blocks via chartCatalog) ─────────
// Keys / titles / "recommended" flags now live in lib/chartCatalog.ts so all
// pages stay in lock-step. GeoPage shows every catalog entry whose `home`
// is 'geo' — currently 7 histograms + 5 scatters.

function HistogramPanel({ title, block }: { title: string; block: HistogramBlock }) {
  return (
    <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-card)', padding: '16px 18px', boxShadow: 'var(--shadow-card)' }}>
      <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8 }}>{title}</div>
      <ResponsiveContainer width="100%" height={160}>
        <BarChart data={block.data} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
          <XAxis dataKey="range" tick={{ fontSize: 9, fill: 'var(--text-muted)' }} interval={Math.max(1, Math.floor(block.data.length / 8))} />
          <YAxis tick={{ fontSize: 10, fill: 'var(--text-muted)' }} allowDecimals={false} />
          <Tooltip content={<ChartTooltip />} cursor={{ fill: 'var(--surface-2)' }} />
          <Bar dataKey="count" fill="var(--status-good)" radius={[2, 2, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function ScatterPanel({ title, block }: { title: string; block: ScatterBlock }) {
  return (
    <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-card)', padding: '16px 18px', boxShadow: 'var(--shadow-card)' }}>
      <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8 }}>{title}</div>
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

type RiskTierFilter = 'all' | 'high' | 'medium' | 'low';

export function GeoPage() {
  const { cacheId } = useSession();
  const { t, lang } = useLang();

  const [kpi, setKpi] = useState<KpiDashboard | null>(null);
  const [kpiLoading, setKpiLoading] = useState(false);

  const [risk, setRisk] = useState<RiskResult | null>(null);
  const [riskLoading, setRiskLoading] = useState(false);
  const [riskTier, setRiskTier] = useState<RiskTierFilter>('all');

  const [selectedIndicator, setSelectedIndicator] = useState<IndicatorKey>('stunting');

  const [blocks, setBlocks] = useState<ChartBlocks | null>(null);
  const [blocksLoading, setBlocksLoading] = useState(false);
  const [showAllDist, setShowAllDist] = useState(false);

  useEffect(() => {
    if (!cacheId) return;
    setKpiLoading(true);
    api.post<KpiDashboard>(`/kpi/dashboard?cache_id=${cacheId}`)
      .then(r => setKpi(r.data))
      .catch(() => setKpi(null))
      .finally(() => setKpiLoading(false));
  }, [cacheId]);

  useEffect(() => {
    if (!cacheId) return;
    setBlocksLoading(true);
    api.get<ChartBlocks>(`/charts/blocks?cache_id=${cacheId}`)
      .then(r => setBlocks(r.data))
      .catch(() => setBlocks(null))
      .finally(() => setBlocksLoading(false));
  }, [cacheId]);

  const runRisk = async () => {
    if (!cacheId) return;
    setRiskLoading(true);
    try {
      const r = await api.post<RiskResult>(`/risk/score?cache_id=${cacheId}`);
      setRisk(r.data);
    } catch { setRisk(null); }
    finally { setRiskLoading(false); }
  };

  const districts = toDistricts(kpi, selectedIndicator);
  const agg = computeAggregates(districts);

  // ── Selected indicator label for chart headers ────────────────────────────
  const indMeta = kpi?.indicators.find(i => i.key === selectedIndicator);
  const indLabel = indMeta ? (lang === 'en' ? indMeta.label_en : indMeta.label_bm) : '';

  // ── Risk distribution post-filter ─────────────────────────────────────────
  const filteredDistribution = useMemo(() => {
    if (!risk) return [] as { tier: string; count: number; status: Status }[];
    return Object.entries(risk.distribution)
      .filter(([tier]) => {
        if (riskTier === 'all') return true;
        const v = tier.toLowerCase();
        if (riskTier === 'high') return v.includes('high') || v.includes('tinggi');
        if (riskTier === 'medium') return v.includes('med') || v.includes('sederhana');
        return v.includes('low') || v.includes('rendah');
      })
      .map(([tier, count]) => ({ tier, count, status: tierToStatus(tier) }));
  }, [risk, riskTier]);

  // ── Filtered high-risk sample / district summary ──────────────────────────
  const filteredSample = useMemo(() => {
    if (!risk?.high_risk_sample) return [];
    if (riskTier === 'all') return risk.high_risk_sample;
    return risk.high_risk_sample.filter(r => {
      const v = String(r.risk_tier ?? '').toLowerCase();
      if (riskTier === 'high') return v.includes('high') || v.includes('tinggi');
      if (riskTier === 'medium') return v.includes('med') || v.includes('sederhana');
      return v.includes('low') || v.includes('rendah');
    });
  }, [risk, riskTier]);

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
            {districts.length === 0
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
              <KpiCard label={t('Stunting', 'Kelaparan')}             value={agg.stunting}    status={ragToStatus(agg.stuntingRag)} />
              <KpiCard label={t('Wasting', 'Kurus')}                  value={agg.wasting}     status={ragToStatus(agg.wastingRag)} />
              <KpiCard label={t('Underweight', 'Kekurangan Berat')}   value={agg.underweight} status={ragToStatus(agg.underweightRag)} />
              <KpiCard label={t('Overweight', 'Berlebihan Berat')}    value={agg.overweight}  status={ragToStatus(agg.overweightRag)} />
            </div>
          </div>
        </div>

        {/* Indicators vs NPAN target — themed tooltip + status colors */}
        {kpi && kpi.indicators.length > 0 && (
          <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-card)', padding: '18px 20px', boxShadow: 'var(--shadow-card)', marginTop: 20 }}>
            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>
              {t('Indicators vs National Target', 'Penunjuk vs Sasaran Kebangsaan')}
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
                <Bar dataKey="actual" name={t('Actual', 'Sebenar')}>
                  {kpi.indicators.map((i, idx) => <Cell key={idx} fill={STATUS_VAR[ragToStatus(i.rag)]} />)}
                </Bar>
                <Bar dataKey="target" name={t('Target', 'Sasaran')} fill="var(--text-muted)" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Breakdown charts — filtered by the global indicator selector */}
        {kpi && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 16, marginTop: 16 }}>
            <BreakdownChart title={`${t('By State', 'Mengikut Negeri')} — ${indLabel}`}   rows={kpi.by_state}  groupKey="state"  indicator={selectedIndicator} />
            {(kpi.by_daerah?.length ?? 0) > 0 && (
              <BreakdownChart title={`${t('By Daerah', 'Mengikut Daerah')} — ${indLabel}`} rows={kpi.by_daerah!} groupKey="district" indicator={selectedIndicator} />
            )}
            <BreakdownChart title={`${t('By Gender', 'Mengikut Jantina')} — ${indLabel}`} rows={kpi.by_gender} groupKey="gender" indicator={selectedIndicator} />
            <BreakdownChart title={`${t('By Age', 'Mengikut Umur')} — ${indLabel}`}       rows={kpi.by_age}    groupKey="group"  indicator={selectedIndicator} />
          </div>
        )}

        {/* Predictive risk scoring card (on-demand) */}
        <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-card)', padding: '18px 20px', boxShadow: 'var(--shadow-card)', marginTop: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10, marginBottom: risk ? 16 : 0 }}>
            <div>
              <div style={{ fontSize: 13, fontWeight: 600 }}>{t('Predictive Risk Scoring', 'Pemarkahan Risiko Ramalan')}</div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
                {t('Composite child-level malnutrition risk (0-100)', 'Risiko malnutrisi peringkat kanak-kanak (0-100)')}
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              {risk && (
                <select
                  value={riskTier}
                  onChange={e => setRiskTier(e.target.value as RiskTierFilter)}
                  style={{
                    background: 'var(--surface-2)', border: '1px solid var(--border)',
                    borderRadius: 'var(--radius-btn)', padding: '6px 10px', fontSize: 12,
                    color: 'var(--text-primary)', cursor: 'pointer',
                  }}
                >
                  <option value="all">{t('All tiers', 'Semua tahap')}</option>
                  <option value="high">{t('High risk only', 'Risiko tinggi sahaja')}</option>
                  <option value="medium">{t('Medium only', 'Sederhana sahaja')}</option>
                  <option value="low">{t('Low only', 'Rendah sahaja')}</option>
                </select>
              )}
              {risk === null && (
                <button onClick={runRisk} disabled={riskLoading}
                  style={{ background: 'var(--kkm-blue)', color: '#fff', border: 'none', borderRadius: 'var(--radius-btn)', padding: '8px 16px', fontSize: 13, fontWeight: 600, cursor: 'pointer', opacity: riskLoading ? 0.6 : 1 }}>
                  {riskLoading ? t('Scoring…', 'Memarkah…') : t('Run Risk Scoring', 'Jalankan Pemarkahan')}
                </button>
              )}
            </div>
          </div>

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
                    <div style={{ fontWeight: 700, fontFamily: 'JetBrains Mono, monospace', color: 'var(--text-primary)' }}>{v}</div>
                  </div>
                ))}
              </div>

              <ResponsiveContainer width="100%" height={180}>
                <BarChart data={filteredDistribution} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
                  <XAxis dataKey="tier" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} />
                  <YAxis tick={{ fontSize: 10, fill: 'var(--text-muted)' }} allowDecimals={false} />
                  <Tooltip content={<ChartTooltip />} cursor={{ fill: 'var(--surface-2)' }} />
                  <Bar dataKey="count">
                    {filteredDistribution.map((d, i) => <Cell key={i} fill={STATUS_VAR[d.status]} />)}
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
                        <td style={{ padding: '8px 10px', fontFamily: 'JetBrains Mono, monospace' }}>{d.avg_risk}</td>
                        <td style={{ padding: '8px 10px', fontFamily: 'JetBrains Mono, monospace' }}>{d.max_risk}</td>
                        <td style={{ padding: '8px 10px', fontFamily: 'JetBrains Mono, monospace', color: 'var(--text-muted)' }}>{d.n_records}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}

              {filteredSample.length > 0 && (
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, marginTop: 16 }}>
                  <thead><tr style={{ borderBottom: '1px solid var(--border)' }}>
                    {[t('IC', 'IC'), t('Name', 'Nama'), t('Score', 'Skor'), t('Tier', 'Tahap')].map(h => (
                      <th key={h} style={{ padding: '8px 10px', textAlign: 'left', fontWeight: 600, fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>{h}</th>
                    ))}
                  </tr></thead>
                  <tbody>
                    {filteredSample.map((r, i) => {
                      const st = tierToStatus(String(r.risk_tier));
                      return (
                        <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                          <td style={{ padding: '8px 10px', fontFamily: 'JetBrains Mono, monospace' }}>{r.IC_NO_PASSPORT ?? '—'}</td>
                          <td style={{ padding: '8px 10px', color: 'var(--text-primary)' }}>{r.NAMA ?? '—'}</td>
                          <td style={{ padding: '8px 10px', fontFamily: 'JetBrains Mono, monospace' }}>{r.risk_score}</td>
                          <td style={{ padding: '8px 10px', color: STATUS_VAR[st], fontWeight: 600 }}>{r.risk_tier}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </>
          )}
        </div>

        {/* Distributions & relationships — 12 charts (7 histograms + 5 scatters)
            sourced from chartCatalog. The "Show all" toggle is kept for parity
            with prior UX but recommended already covers the full catalog for
            this page. */}
        {(blocks || blocksLoading) && (
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
            ) : blocks ? (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 14 }}>
                {(() => {
                  // Recommended: every catalog entry whose home === 'geo'.
                  // "Show all": fall back to anything in blocks that matches a
                  // histogram or scatter shape, including future additions.
                  const catalogKeys = catalogByHome('geo').map(e => e.key);
                  const allHistOrScatter = Object.keys(blocks).filter(k => {
                    const b = blocks[k];
                    return isHistogramBlock(b) || isScatterBlock(b);
                  });
                  const keysToRender = showAllDist
                    ? Array.from(new Set([...catalogKeys, ...allHistOrScatter]))
                    : catalogKeys.filter(k => k in blocks);
                  return keysToRender.map(key => {
                    const b = blocks[key];
                    const entry = catalogByHome('geo').find(e => e.key === key);
                    const title = entry
                      ? (lang === 'en' ? entry.titleEn : entry.titleBm)
                      : key;
                    if (isScatterBlock(b))   return <ScatterPanel   key={key} title={title} block={b} />;
                    if (isHistogramBlock(b)) return <HistogramPanel key={key} title={title} block={b} />;
                    return null;
                  });
                })()}
              </div>
            ) : null}
          </div>
        )}
      </div>
    </SessionGuard>
  );
}
