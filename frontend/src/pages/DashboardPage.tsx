import React, { useEffect, useState, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Upload, X, ChevronDown, ChevronUp, TrendingUp, Maximize2 } from 'lucide-react';
import { api } from '../api/client';
import { useLang } from '../context/LanguageContext';
import { useSession } from '../context/SessionContext';
import { ChoroplethMap, District } from '../components/ChoroplethMap';
import { FocusOverlay } from '../components/FocusOverlay';
import { RagBadge, type Rag as RagLevel } from '../components/RagBadge';
import { DonutCard } from '../components/DonutCard';
import { MiniBarCard } from '../components/MiniBarCard';
import { TrendLineCard } from '../components/TrendLineCard';
import {
  catalogByHome,
  isPieArrayBlock,
  isBarLabeledBlock,
  isTrendRecordsBlock,
} from '../lib/chartCatalog';
import { formatGroupLabel } from '../lib/labels';
import { formatMytDate } from '../lib/formatMyt';

/* ── Types ─────────────────────────────────────────────────────────────── */

interface Summary {
  total_children: number;
  avg_quality_score: number;
  session_count: number;
  alerts: number;
  latest_session: { cache_id: string; filename: string; source_type: string; created_at: string } | null;
  source_breakdown: Record<string, number>;
}

type IndicatorKey = 'stunting' | 'wasting' | 'underweight' | 'overweight';
type Rag = 'Green' | 'Amber' | 'Red';

interface IndicatorKpi {
  key: IndicatorKey;
  label_en: string; label_bm: string;
  actual: number; actual_count: number; total: number;
  npan_target: number; who_target: number | null;
  gap: number; rag: Rag;
}
interface GroupRow {
  state?: string; district?: string; gender?: string; group?: string; income?: string;
  n: number;
  rates: Partial<Record<IndicatorKey, number>>;
  status: Partial<Record<IndicatorKey, Rag>>;
}
interface KpiResult {
  overall_status: Rag;
  total_children: number;
  indicators: IndicatorKpi[];
  by_state: GroupRow[];
  by_daerah?: GroupRow[];
  by_gender: GroupRow[];
  by_income?: GroupRow[];
  by_age: GroupRow[];
}

/* ── Helpers ────────────────────────────────────────────────────────────── */

const STATE_TO_CODE: Record<string, string> = {
  JOHOR: 'jhr', KEDAH: 'kdh', KELANTAN: 'ktn',
  'KUALA LUMPUR': 'kul', LABUAN: 'lbn', MELAKA: 'mlk',
  'NEGERI SEMBILAN': 'nsn', PAHANG: 'phg', PUTRAJAYA: 'pjy',
  PERLIS: 'pls', PENANG: 'png', 'PULAU PINANG': 'png',
  PERAK: 'prk', SABAH: 'sbh', SELANGOR: 'sgr',
  SARAWAK: 'swk', TERENGGANU: 'trg',
};

const STATE_CODES = new Set(Object.values(STATE_TO_CODE));

/* Canonical state names for backend filter + tooltip display.
   "Pulau Pinang" is preferred over "Penang" (matches KKM/MOH usage). */
const CODE_TO_STATE_NAME: Record<string, string> = {
  jhr: 'Johor',
  kdh: 'Kedah',
  ktn: 'Kelantan',
  kul: 'Kuala Lumpur',
  lbn: 'Labuan',
  mlk: 'Melaka',
  nsn: 'Negeri Sembilan',
  pjy: 'Putrajaya',
  pls: 'Perlis',
  png: 'Pulau Pinang',
  prk: 'Perak',
  phg: 'Pahang',
  sbh: 'Sabah',
  sgr: 'Selangor',
  swk: 'Sarawak',
  trg: 'Terengganu',
};

const codeToStateName = (code: string): string =>
  CODE_TO_STATE_NAME[code.trim().toLowerCase()] || code.toUpperCase();

/* Map a backend `state` string to a 3-letter geo code, tolerant of
   whitespace, punctuation, federal-territory prefixes, or a value that
   is already an abbreviation/code (e.g. "SBH", " Sabah ", "W.P. Labuan").
   Returns '' when nothing plausibly matches so it just renders no-data
   rather than mis-colouring. */
function toStateCode(stateRaw: string | undefined | null): string {
  const norm = String(stateRaw ?? '')
    .toUpperCase()
    .replace(/[^A-Z\s]/g, ' ')
    .replace(/\bW\s*P\b|WILAYAH PERSEKUTUAN/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  if (STATE_TO_CODE[norm]) return STATE_TO_CODE[norm];
  const compact = norm.replace(/\s/g, '').toLowerCase();
  if (STATE_CODES.has(compact)) return compact;
  return '';
}

function fmt(n: number | string | null | undefined) { return n == null ? '—' : Number(n).toLocaleString(); }

function GroupBars({ title, rows, labelKey, indicator, notAvail, lang }: {
  title: string;
  rows: GroupRow[];
  labelKey: 'gender' | 'group' | 'income';
  indicator: IndicatorKey;
  notAvail: string;
  lang: 'en' | 'bm';
}) {
  const wrap: React.CSSProperties = {
    flex: '1 1 360px', background: 'var(--surface)', border: '1px solid var(--border)',
    borderRadius: 'var(--radius-card)', padding: 20, boxShadow: 'var(--shadow-card)',
  };
  const head: React.CSSProperties = {
    fontSize: 11, fontWeight: 600, letterSpacing: '0.07em', textTransform: 'uppercase',
    color: 'var(--text-secondary)', marginBottom: 14,
  };
  if (!rows || rows.length === 0) {
    return (
      <div style={wrap}>
        <div style={head}>{title}</div>
        <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>{notAvail}</div>
      </div>
    );
  }
  return (
    <div style={wrap}>
      <div style={head}>{title}</div>
      {rows.map((r, i) => {
        const v = Number(r.rates[indicator] ?? 0);
        const raw = String(r[labelKey] ?? '—');
        const label = formatGroupLabel(labelKey, raw, lang);
        return (
          <div key={i} style={{ marginBottom: 10 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: 'var(--text-secondary)', marginBottom: 3 }}>
              <span>{label} <span style={{ color: 'var(--text-muted)' }}>(n={r.n ?? 0})</span></span><span style={{ fontWeight: 600 }}>{v.toFixed(2)}%</span>
            </div>
            <div style={{ height: 8, background: ragTrack(r.status[indicator]), borderRadius: 4 }}>
              <div style={{ height: '100%', width: `${Math.min(100, v)}%`, background: ragSolid(r.status[indicator]), borderRadius: 4 }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

const ragToLower = (r?: Rag): 'green' | 'amber' | 'red' =>
  r === 'Amber' ? 'amber' : r === 'Red' ? 'red' : 'green';

/* Status palette — migrated to KKM Navy-Gold-Brick. Tokens live in
   tokens.css (--status-good / --status-watch / --status-critical) and
   stay in sync with ChoroplethMap. The track variants are slightly
   tinted backgrounds for the bar's empty portion so a 0%-rate "good"
   row still reads as a positive signal even with no fill on top. */
const RAG_VAR: Record<'green' | 'amber' | 'red', string> = {
  green: 'var(--status-good)',
  amber: 'var(--status-watch)',
  red:   'var(--status-critical)',
};
const RAG_TRACK_VAR: Record<'green' | 'amber' | 'red', string> = {
  green: 'var(--status-good-bg)',
  amber: 'var(--status-watch-bg)',
  red:   'var(--status-critical-bg)',
};
const ragSolid = (r?: Rag): string => RAG_VAR[ragToLower(r)];
const ragTrack = (r?: Rag): string => RAG_TRACK_VAR[ragToLower(r)];

/* Always-legible target marker for value-vs-target bars. A high-contrast
   notch wrapped in a thin surface-coloured halo so it reads against BOTH the
   filled (status colour) and unfilled (surface-3) segments, in light and dark
   mode — the bare 2px tick was invisible on short "good" bars. The parent bar
   must be position:relative. `leftPct` is where the target sits on the track. */
function TargetTick({ leftPct = 70 }: { leftPct?: number }) {
  return (
    <div aria-hidden style={{
      position: 'absolute', left: `${leftPct}%`, top: '50%',
      transform: 'translate(-50%, -50%)',
      width: 3, height: 'calc(100% + 7px)',
      background: 'var(--text-primary)', borderRadius: 1,
      boxShadow: '0 0 0 1.5px var(--surface)',
    }} />
  );
}

/* When a state is drilled into on the map, the right-hand panel shows ALL four
   indicators, each as its own sub-section with that state's areas/daerah ranked
   by the sub-section's indicator. Same data source as the single-indicator view
   (kpi.by_daerah rows already carry rates+status for every indicator), just
   rendered four times. `dense` shrinks sizing for the narrow inline panel; the
   FocusOverlay passes dense={false} for the roomier expanded view. Iterates the
   present-only `indicators` list (same source the top KPI cards use) so a dataset
   missing an indicator simply omits that section rather than rendering a raw key
   heading at 0%. */
function DaerahByIndicators({ rows, indicators, lang, unknownArea, dense }: {
  rows: GroupRow[];
  indicators: IndicatorKpi[];
  lang: 'en' | 'bm';
  unknownArea: string;
  dense: boolean;
}) {
  return (
    <>
      {indicators.map((ind, idx) => {
        const key = ind.key;
        const heading = lang === 'en' ? ind.label_en : ind.label_bm;
        const sorted = [...rows].sort(
          (a, b) => Number(b.rates[key] ?? 0) - Number(a.rates[key] ?? 0),
        );
        return (
          <div key={key} style={{ marginBottom: idx < indicators.length - 1 ? (dense ? 18 : 24) : 0 }}>
            <div style={{
              fontSize: dense ? 11 : 12.5, fontWeight: 700, color: 'var(--text-primary)',
              marginBottom: dense ? 8 : 10,
            }}>
              {heading}
            </div>
            {sorted.map(s => {
              const v = Number(s.rates[key] ?? 0);
              const label = s.district || unknownArea;
              return (
                <div key={`${key}:${label}`} style={{ marginBottom: dense ? 8 : 10 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: dense ? 12 : 13, color: 'var(--text-secondary)', marginBottom: dense ? 3 : 4 }}>
                    <span>{label}</span>
                    <span style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
                      <span style={{ fontSize: dense ? 10 : 11, color: 'var(--text-muted)' }}>n={s.n.toLocaleString()}</span>
                      <span style={{ fontWeight: 600 }}>{v.toFixed(2)}%</span>
                    </span>
                  </div>
                  <div style={{ height: dense ? 8 : 10, background: ragTrack(s.status[key]), borderRadius: dense ? 4 : 5 }}>
                    <div style={{ height: '100%', width: `${Math.min(100, v)}%`, background: ragSolid(s.status[key]), borderRadius: dense ? 4 : 5 }} />
                  </div>
                </div>
              );
            })}
          </div>
        );
      })}
    </>
  );
}

/* Demographic-label localisation now lives in lib/labels.ts so the Dashboard
   and Geo & Risk breakdowns translate identically. */

/* ── Component ──────────────────────────────────────────────────────────── */

export function DashboardPage() {
  const { t, lang } = useLang();
  const { cacheId, setSession } = useSession();
  const nav = useNavigate();

  const [summary, setSummary] = useState<Summary | null>(null);
  const [kpi, setKpi] = useState<KpiResult | null>(null);
  /* selectedStateCode is the 3-letter geo code (e.g. 'jhr'); converted to a
     canonical state name before being sent to the backend filter. */
  const [selectedStateCode, setSelectedStateCode] = useState<string | null>(null);
  const [selectedIndicator, setSelectedIndicator] = useState<IndicatorKey>('stunting');
  const [kpiError, setKpiError] = useState(false);
  const [loading, setLoading] = useState(true);
  /* Population breakdown — fetched lazily from /charts/blocks. Collapsed
     by default so the dashboard stays scannable on first paint. */
  const [blocks, setBlocks] = useState<Record<string, unknown> | null>(null);
  const [popOpen, setPopOpen] = useState(false);
  const [panelFocus, setPanelFocus] = useState(false);
  const [stateFilter, setStateFilter] = useState('');

  /* Pin the By-State panel to the map card's *measured* height so the two
     cards always line up exactly, at any viewport width. (Previously the
     panel used a hand-tuned maxHeight:320 that only approximated the map's
     fluid SVG height — see the layout comment on the panel card below.) */
  const mapCardRef = useRef<HTMLDivElement>(null);
  const [panelHeight, setPanelHeight] = useState<number | null>(null);
  useEffect(() => {
    const el = mapCardRef.current;
    if (!el || typeof ResizeObserver === 'undefined') return;
    const ro = new ResizeObserver(() => {
      // offsetHeight is the border-box height (includes padding + border), so
      // the panel card matches the map card's *outer* box exactly.
      setPanelHeight(el.offsetHeight);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  /* fetch summary (always-on) */
  useEffect(() => {
    api.get<Summary>('/dashboard/summary')
      .then(s => setSummary(s.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  /* fetch kpi for current/latest session */
  const activeCacheId = cacheId || summary?.latest_session?.cache_id;

  const fetchKpi = useCallback(async (stateCode?: string | null) => {
    if (!activeCacheId) return;
    try {
      const params: Record<string, string> = { cache_id: activeCacheId };
      if (stateCode) params.state = codeToStateName(stateCode);
      const r = await api.post<KpiResult>(`/kpi/dashboard?${new URLSearchParams(params)}`);
      setKpi(r.data);
      setKpiError(false);
    } catch {
      setKpiError(true);
    }
  }, [activeCacheId]);

  useEffect(() => { fetchKpi(); }, [fetchKpi]);

  /* Population breakdown blocks — only fetched once we have a cache id. */
  useEffect(() => {
    if (!activeCacheId) { setBlocks(null); return; }
    let cancelled = false;
    api.get<Record<string, unknown>>(`/charts/blocks?cache_id=${activeCacheId}`)
      .then(r => { if (!cancelled) setBlocks(r.data); })
      .catch(() => { if (!cancelled) setBlocks(null); });
    return () => { cancelled = true; };
  }, [activeCacheId]);

  const handleStateClick = (code: string | null) => {
    setSelectedStateCode(code);
    fetchKpi(code);
  };

  useEffect(() => {
    setStateFilter(selectedStateCode ? codeToStateName(selectedStateCode) : '');
  }, [selectedStateCode]);

  const handleFilterChange = (val: string) => {
    setStateFilter(val);
    const match = Object.entries(CODE_TO_STATE_NAME).find(
      ([, name]) => name.toLowerCase() === val.trim().toLowerCase()
    );
    if (match) handleStateClick(match[0]);
    else if (val === '') handleStateClick(null);
  };

  /* ── Welcome / empty state ───────────────────────────────────────────── */
  if (!loading && summary?.session_count === 0) {
    return (
      <div style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        justifyContent: 'center', minHeight: '70vh', gap: 24, textAlign: 'center',
      }}>
        <div style={{
          width: 56, height: 56, borderRadius: 14,
          background: 'var(--kkm-sky)', color: '#fff',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontFamily: 'var(--font-body)', fontWeight: 700, fontSize: 22,
        }}>S</div>
        <h2 style={{ fontFamily: 'var(--font-body)', fontSize: 24, fontWeight: 700, color: 'var(--text-primary)' }}>
          {t('Welcome to SmartDQC', 'Selamat datang ke SmartDQC')}
        </h2>
        <p style={{ color: 'var(--text-secondary)', maxWidth: 440, lineHeight: 1.7 }}>
          {t(
            'Start by uploading a paediatric nutrition dataset. SmartDQC will clean, analyse, and visualise your data.',
            'Mulakan dengan memuat naik dataset pemakanan pediatrik. SmartDQC akan membersih, menganalisis, dan menggambarkan data anda.',
          )}
        </p>
        <button
          onClick={() => nav('/upload')}
          style={{
            background: 'var(--kkm-blue)', color: '#fff', border: 'none',
            borderRadius: 'var(--radius-btn)', padding: '12px 28px',
            fontFamily: 'var(--font-body)', fontWeight: 700, fontSize: 15,
            display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer',
          }}
        >
          <Upload size={17} />
          {t('Upload New Dataset', 'Muat Naik Dataset Baru')}
        </button>
      </div>
    );
  }

  /* ── Loaded state ────────────────────────────────────────────────────── */
  const indicators = kpi?.indicators ?? [];
  const selInd = indicators.find(i => i.key === selectedIndicator);

  const mapDistricts: District[] = (kpi?.by_state ?? []).map(s => ({
    name: toStateCode(s.state),
    stunting_rate: Number(s.rates.stunting ?? 0) / 100,
    wasting_rate: Number(s.rates.wasting ?? 0) / 100,
    underweight_rate: Number(s.rates.underweight ?? 0) / 100,
    overweight_rate: Number(s.rates.overweight ?? 0) / 100,
    risk_rag: ragToLower(s.status[selectedIndicator]),
    vs_target: 0,
  }));

  /* When a state is selected and the backend returned a daerah
     breakdown, swap the right-hand panel from "By State" to
     "By Daerah — {state}". When unfiltered, keep the by-state list. */
  const drilledToDaerah = !!selectedStateCode && !!kpi?.by_daerah?.length;
  const breakdownRows = drilledToDaerah ? (kpi!.by_daerah ?? []) : (kpi?.by_state ?? []);
  const breakdownKey: 'state' | 'district' = drilledToDaerah ? 'district' : 'state';
  const sortedStates = [...breakdownRows].sort(
    (a, b) => Number(b.rates[selectedIndicator] ?? 0) - Number(a.rates[selectedIndicator] ?? 0),
  );

  /* Right-panel modes:
     · showStateIndicators — a state is selected but the dataset has no daerah
       column to drill into, so fall back to that state's 4 indicators vs target.
     · drilledToDaerah     — state selected AND daerah data exists → per-AREA
       ranked breakdown of the selected indicator (the top KPI cards already
       carry the state's 4-vs-target view, so this never duplicates them).
     · neither             — national view → per-STATE ranked breakdown of the
       selected indicator. */
  const showStateIndicators = !!selectedStateCode && !drilledToDaerah && indicators.length > 0;
  const indicatorLabel = selInd ? (lang === 'en' ? selInd.label_en : selInd.label_bm) : '';
  const panelTitle = showStateIndicators
    ? `${codeToStateName(selectedStateCode!)} · ${t('All Indicators', 'Semua Penunjuk')}`
    : drilledToDaerah
      ? `${codeToStateName(selectedStateCode!)} · ${t('By Area', 'Mengikut Kawasan')} · ${t('All Indicators', 'Semua Penunjuk')}`
      : `${t('By State', 'Mengikut Negeri')}${indicatorLabel ? ` · ${indicatorLabel}` : ''}`;
  const unknownArea = t('Unknown', 'Tidak diketahui');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

      {kpiError && (
        <div style={{
          background: 'var(--warning-bg)', border: '1px solid var(--warning)',
          borderRadius: 'var(--radius-card)', padding: '12px 16px', fontSize: 13,
          color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap',
        }}>
          <span style={{ flex: 1, minWidth: 200 }}>
            {t('No analysed dataset, or the dashboard data could not be loaded.',
               'Tiada dataset dianalisis, atau data papan pemuka tidak dapat dimuatkan.')}
          </span>
          <button
            onClick={() => fetchKpi(selectedStateCode)}
            style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-btn)', padding: '6px 14px', fontSize: 12.5, fontWeight: 600, color: 'var(--text-primary)', cursor: 'pointer', flexShrink: 0 }}
          >
            {t('Retry', 'Cuba semula')}
          </button>
        </div>
      )}

      {/* ── Header + indicator selector ─────────────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        <h1 style={{ fontFamily: 'var(--font-body)', fontSize: 20, fontWeight: 700, margin: 0 }}>
          {t('Child Nutrition Status (Under 5 Years Old)', 'Status Pemakanan Kanak-Kanak Bawah 5 Tahun')}
        </h1>
        <div style={{ flex: 1 }} />
        <select
          value={selectedIndicator}
          onChange={e => setSelectedIndicator(e.target.value as IndicatorKey)}
          style={{
            background: 'var(--surface-2)', border: '1px solid var(--border)',
            borderRadius: 'var(--radius-btn)', padding: '6px 10px', fontSize: 13,
            color: 'var(--text-primary)', cursor: 'pointer',
          }}
        >
          {indicators.map(i => (
            <option key={i.key} value={i.key}>{lang === 'en' ? i.label_en : i.label_bm}</option>
          ))}
        </select>
        {summary?.latest_session && (
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            {t('Last updated', 'Dikemaskini')}: {formatMytDate(summary.latest_session.created_at, lang)}
          </span>
        )}
      </div>

      {/* ── Compact DQ-ops strip ────────────────────────────────────────── */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 18, flexWrap: 'wrap',
        background: 'var(--surface)', border: '1px solid var(--border)',
        borderRadius: 'var(--radius-card)', padding: '10px 16px',
        fontSize: 13, color: 'var(--text-secondary)', boxShadow: 'var(--shadow-card)',
      }}>
        <span><strong style={{ color: 'var(--text-primary)' }}>{fmt(summary?.total_children ?? null)}</strong> {t('children', 'kanak-kanak')}</span>
        <span><strong style={{ color: 'var(--text-primary)' }}>{summary ? `${summary.avg_quality_score}%` : '—'}</strong> {t('quality', 'kualiti')}</span>
        <span><strong style={{ color: 'var(--text-primary)' }}>{fmt(summary?.session_count ?? null)}</strong> {t('sessions', 'sesi')}</span>
        <span style={{ color: summary && summary.alerts > 0 ? 'var(--danger)' : 'var(--success)' }}>
          <strong>{fmt(summary?.alerts ?? null)}</strong> {t('alerts', 'amaran')}
        </span>
        <div style={{ flex: 1 }} />
        {summary?.latest_session && (
          <button
            onClick={() => {
              setSession({
                cacheId: summary.latest_session!.cache_id,
                filename: summary.latest_session!.filename,
                sourceType: summary.latest_session!.source_type,
              });
              nav('/quality');
            }}
            style={{ background: 'none', border: 'none', color: 'var(--kkm-blue)', fontSize: 12, fontWeight: 600, cursor: 'pointer' }}
          >
            {t('Resume', 'Sambung')} {summary.latest_session.filename} →
          </button>
        )}
        <button
          onClick={() => nav('/history')}
          style={{ background: 'none', border: 'none', color: 'var(--kkm-blue)', fontSize: 12, fontWeight: 600, cursor: 'pointer' }}
        >
          {t('History', 'Sejarah')} →
        </button>
      </div>

      {/* ── Indicator status board (dossier panel) ──────────────────────────
          One framed panel under a Songket-Gold keyline, not four loose cards.
          All indicators stay equal-width with a value-vs-target bar (target
          tick fixed at 70% → fill past the tick = above target), so an analyst
          compares all four at a glance. The SELECTED indicator elevates by
          emphasis only — gold inset rule, faint fill, larger serif numeral —
          never by hiding the others. Segments are real buttons (keyboard-
          selectable, visible focus). */}
      <div style={{
        background: 'var(--surface)', border: '1px solid var(--border)',
        borderRadius: 'var(--radius-card)', boxShadow: 'var(--shadow-card)', overflow: 'hidden',
      }}>
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 12, padding: '14px 18px 2px' }}>
          <span className="kkm-keyline" style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-secondary)' }}>
            {t('Indicators vs Target', 'Penunjuk vs Sasaran')}
          </span>
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            {t('Select an indicator to update the map below', 'Pilih penunjuk untuk kemas kini peta di bawah')}
          </span>
        </div>

        {indicators.length === 0 ? (
          <div style={{ color: 'var(--text-muted)', fontSize: 13, padding: '20px', textAlign: 'center' }}>
            {t('No indicator data — run cleaning first.', 'Tiada data penunjuk — jalankan pembersihan dahulu.')}
          </div>
        ) : (
          <div className="kpi-indicator-grid" style={{ display: 'grid', gridTemplateColumns: `repeat(${indicators.length}, minmax(0, 1fr))` }}>
            {indicators.map((ind, i) => {
              const sel = ind.key === selectedIndicator;
              // WS7: this fills the value-vs-target bar — a status grade, so it
              // uses the dataviz status family in lock-step with RAG_VAR above
              // (the same file's ranked bars) and the RagBadge beside it.
              const ragColor = ind.rag === 'Green' ? 'var(--status-good)'
                : ind.rag === 'Amber' ? 'var(--status-watch)' : 'var(--status-critical)';
              /* Map the dashboard's Green/Amber/Red enum to the app-wide
                 RagBadge level so the status reads bilingually (GOOD/BAIK,
                 MODERATE/SEDERHANA, CRITICAL/KRITIKAL) — never a raw "Green". */
              const ragLevel: RagLevel = ind.rag === 'Green' ? 'good'
                : ind.rag === 'Amber' ? 'warning' : 'critical';
              /* Delta COLOUR encodes good/bad, not up/down. All four indicators
                 (stunting/wasting/underweight/overweight) are prevalence rates
                 where lower-is-better, and gap = actual − npan_target (backend
                 eda/kpi.py:192). So gap > 0 (above target) is bad → red. The
                 arrow still shows raw direction. If a higher-is-better indicator
                 is ever added, gate `isBad` on its direction, not the raw sign. */
              const lowerIsBetter = true;
              const isBad = lowerIsBetter ? ind.gap > 0 : ind.gap < 0;
              const target = Number(ind.npan_target) || 0;
              const value = Number(ind.actual) || 0;
              const TICK = 70; // target sits at 70% of the track
              const fillPct = target > 0 ? Math.min(100, (value / target) * TICK) : 0;
              return (
                <button
                  key={ind.key}
                  type="button"
                  className="kpi-seg"
                  onClick={() => setSelectedIndicator(ind.key)}
                  aria-pressed={sel}
                  style={{
                    textAlign: 'left', cursor: 'pointer', color: 'inherit',
                    /* Background AND the selected gold index-rail are intentionally
                       NOT set inline — they live in globals.css under
                       .kpi-seg:hover and .kpi-seg[aria-pressed="true"] so the
                       hover/selected feedback wins and, in dark mode, the gold
                       rail can be dialled back (full-strength gold read too hot). */
                    border: 'none',
                    borderLeft: i === 0 ? 'none' : '1px solid var(--border)',
                    padding: '12px 18px 16px',
                    display: 'flex', flexDirection: 'column', gap: 7,
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--text-secondary)' }}>
                      {lang === 'en' ? ind.label_en : ind.label_bm}
                    </span>
                    <RagBadge rag={ragLevel} lang={lang} />
                  </div>
                  {/* Fixed-height number row so the value-vs-target bars below stay
                      on ONE shared baseline whether or not a column is selected
                      (selected uses a larger serif numeral). */}
                  <div style={{ minHeight: 38, display: 'flex', alignItems: 'flex-end' }}>
                    <span style={{
                      fontFamily: 'var(--font-body)',
                      fontSize: sel ? 32 : 25, fontWeight: 700, color: 'var(--text-primary)',
                      fontVariantNumeric: 'tabular-nums', lineHeight: 1,
                    }}>
                      {value.toFixed(2)}%
                    </span>
                  </div>
                  {/* value-vs-target bar — tick = target; fill beyond it = above target (worse) */}
                  <div style={{ position: 'relative', height: 6, background: 'var(--surface-3)', borderRadius: 3, marginTop: 1, marginBottom: 18 }} aria-hidden>
                    <div style={{ position: 'absolute', left: 0, top: 0, height: '100%', width: `${fillPct}%`, background: ragColor, borderRadius: 3 }} />
                    <TargetTick leftPct={TICK} />
                    <div style={{ position: 'absolute', left: `${TICK}%`, top: 14, transform: 'translateX(-50%)', fontSize: 9, fontWeight: 700, letterSpacing: '0.04em', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                      {t('Target', 'Sasaran')}
                    </div>
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                    {t('Target', 'Sasaran')} {target.toFixed(0)}%
                    {ind.who_target != null ? ` · WHO ${Number(ind.who_target).toFixed(0)}%` : ''}
                  </div>
                  {/* WS7: an off-target delta is a "bad-but-not-broken" watch
                      signal, not a system error — red is reserved for errors, so
                      the negative side uses --warning (also ≥4.5:1 as text, which
                      the coral fill token is not). */}
                  <div style={{ fontSize: 12, fontWeight: 600, color: isBad ? 'var(--warning)' : 'var(--success)' }}>
                    {ind.gap > 0 ? '▲' : '▼'} {Math.abs(Number(ind.gap)).toFixed(2)} {t('vs target', 'vs sasaran')}
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* ── Map + By-State ──────────────────────────────────────────────── */}
      <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap', alignItems: 'flex-start' }}>
        <div ref={mapCardRef} style={{
          flex: '1 1 360px', background: 'var(--surface)', border: '1px solid var(--border)',
          borderRadius: 'var(--radius-card)', padding: 20, boxShadow: 'var(--shadow-card)',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <span style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.07em', textTransform: 'uppercase', color: 'var(--text-secondary)' }}>
              {t('State Risk Map', 'Peta Risiko Negeri')}
            </span>
            {selectedStateCode && (
              <button onClick={() => handleStateClick(null)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 6, background: 'rgba(0,163,224,0.12)',
                  border: '1px solid var(--kkm-sky)', borderRadius: 999, padding: '4px 12px',
                  fontSize: 12, fontWeight: 600, color: 'var(--kkm-sky)', cursor: 'pointer',
                }}>
                {codeToStateName(selectedStateCode)} <X size={12} />
              </button>
            )}
          </div>
          {mapDistricts.length > 0 && (
            <div style={{ marginBottom: 8 }}>
              <input
                type="text"
                list="dash-state-filter"
                value={stateFilter}
                onChange={e => handleFilterChange(e.target.value)}
                placeholder={t('Filter by state…', 'Tapis mengikut negeri…')}
                style={{
                  width: '100%', padding: '6px 10px', fontSize: 12,
                  background: 'var(--surface-2)', border: '1px solid var(--border)',
                  borderRadius: 8, color: 'var(--text-primary)', outline: 'none',
                  fontFamily: 'var(--font-body)',
                }}
              />
              <datalist id="dash-state-filter">
                {Object.entries(CODE_TO_STATE_NAME).map(([code, name]) => (
                  <option key={code} value={name} />
                ))}
              </datalist>
            </div>
          )}
          {mapDistricts.length === 0
            ? <div style={{ padding: 32, textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>
                {t('No state data for this dataset.', 'Tiada data negeri untuk dataset ini.')}
              </div>
            : <ChoroplethMap districts={mapDistricts} selectedDistrict={selectedStateCode} onDistrictClick={handleStateClick} />}
        </div>

        <div style={{
          flex: '1 1 360px', background: 'var(--surface)', border: '1px solid var(--border)',
          borderRadius: 'var(--radius-card)', padding: 20, boxShadow: 'var(--shadow-card)',
          /* Height is pinned to the map card's *measured* border-box height
             (panelHeight, via ResizeObserver above) so the two cards line up
             exactly at any viewport width. The list inside scrolls when it
             overflows. 320 is only the first-paint fallback, before the
             observer has measured the map. */
          display: 'flex', flexDirection: 'column',
          height: panelHeight ?? undefined, maxHeight: panelHeight ?? 320,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
            <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.07em', textTransform: 'uppercase', color: 'var(--text-secondary)' }}>
              {panelTitle}
            </div>
            {(showStateIndicators ? indicators.length > 0 : sortedStates.length > 0) && (
              <button
                onClick={() => setPanelFocus(true)}
                aria-label={t('Expand panel', 'Kembangkan panel')}
                title={t('Expand', 'Kembang')}
                style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 7, padding: '5px 7px', color: 'var(--text-secondary)', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', flexShrink: 0 }}
              >
                <Maximize2 size={14} />
              </button>
            )}
          </div>
          {/* Scrollable content: caps the 16-state list so it no longer drives
             the flex-row height and stretches the map card. Header stays pinned. */}
          <div style={{ flex: 1, minHeight: 0, overflowY: 'auto' }}>
          {showStateIndicators ? (
            indicators.map(ind => {
              const rl: RagLevel = ind.rag === 'Green' ? 'good' : ind.rag === 'Amber' ? 'warning' : 'critical';
              const rc = ind.rag === 'Green' ? 'var(--status-good)' : ind.rag === 'Amber' ? 'var(--status-watch)' : 'var(--status-critical)';
              const val = Number(ind.actual);
              const tgt = Number(ind.npan_target) || 0;
              const fp = tgt > 0 ? Math.min(100, (val / tgt) * 70) : 0;
              return (
                <div key={ind.key} style={{ marginBottom: 12 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                    <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                      {lang === 'en' ? ind.label_en : ind.label_bm}
                    </span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span style={{ fontSize: 13, fontWeight: 700, fontVariantNumeric: 'tabular-nums', color: 'var(--text-primary)' }}>
                        {val.toFixed(2)}%
                      </span>
                      <RagBadge rag={rl} lang={lang} />
                    </div>
                  </div>
                  <div style={{ position: 'relative', height: 6, background: 'var(--surface-3)', borderRadius: 3 }}>
                    <div style={{ height: '100%', width: `${fp}%`, background: rc, borderRadius: 3 }} />
                    <TargetTick leftPct={70} />
                  </div>
                </div>
              );
            })
          ) : drilledToDaerah ? (
            <DaerahByIndicators rows={breakdownRows} indicators={indicators} lang={lang} unknownArea={unknownArea} dense />
          ) : (
            <>
              {sortedStates.map(s => {
                const v = Number(s.rates[selectedIndicator] ?? 0);
                const label = breakdownKey === 'district' ? (s.district || unknownArea) : s.state;
                return (
                  <div key={`${breakdownKey}:${label}`} style={{ marginBottom: 8 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: 'var(--text-secondary)', marginBottom: 3 }}>
                      <span>{label}</span>
                      <span style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
                        <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>n={s.n.toLocaleString()}</span>
                        <span style={{ fontWeight: 600 }}>{v.toFixed(2)}%</span>
                      </span>
                    </div>
                    <div style={{ height: 8, background: ragTrack(s.status[selectedIndicator]), borderRadius: 4 }}>
                      <div style={{ height: '100%', width: `${Math.min(100, v)}%`, background: ragSolid(s.status[selectedIndicator]), borderRadius: 4 }} />
                    </div>
                  </div>
                );
              })}
              {sortedStates.length === 0 && (
                <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>
                  {t('Not available for this dataset.', 'Tiada untuk dataset ini.')}
                </div>
              )}
            </>
          )}
          </div>
        </div>
        <FocusOverlay
          open={panelFocus}
          onClose={() => setPanelFocus(false)}
          title={panelTitle}
        >
          {showStateIndicators ? (
            indicators.map(ind => {
              const rl: RagLevel = ind.rag === 'Green' ? 'good' : ind.rag === 'Amber' ? 'warning' : 'critical';
              const rc = ind.rag === 'Green' ? 'var(--status-good)' : ind.rag === 'Amber' ? 'var(--status-watch)' : 'var(--status-critical)';
              const val = Number(ind.actual);
              const tgt = Number(ind.npan_target) || 0;
              const fp = tgt > 0 ? Math.min(100, (val / tgt) * 70) : 0;
              return (
                <div key={ind.key} style={{ marginBottom: 16 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                    <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                      {lang === 'en' ? ind.label_en : ind.label_bm}
                    </span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ fontSize: 15, fontWeight: 700, fontVariantNumeric: 'tabular-nums', color: 'var(--text-primary)' }}>
                        {val.toFixed(2)}%
                      </span>
                      <RagBadge rag={rl} lang={lang} />
                    </div>
                  </div>
                  <div style={{ position: 'relative', height: 8, background: 'var(--surface-3)', borderRadius: 4 }}>
                    <div style={{ height: '100%', width: `${fp}%`, background: rc, borderRadius: 4 }} />
                    <TargetTick leftPct={70} />
                  </div>
                </div>
              );
            })
          ) : drilledToDaerah ? (
            <DaerahByIndicators rows={breakdownRows} indicators={indicators} lang={lang} unknownArea={unknownArea} dense={false} />
          ) : (
            <>
              {sortedStates.map(s => {
                const v = Number(s.rates[selectedIndicator] ?? 0);
                const label = breakdownKey === 'district' ? (s.district || unknownArea) : s.state;
                return (
                  <div key={`${breakdownKey}:${label}`} style={{ marginBottom: 10 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, color: 'var(--text-secondary)', marginBottom: 4 }}>
                      <span>{label}</span>
                      <span style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
                        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>n={s.n.toLocaleString()}</span>
                        <span style={{ fontWeight: 600 }}>{v.toFixed(2)}%</span>
                      </span>
                    </div>
                    <div style={{ height: 10, background: ragTrack(s.status[selectedIndicator]), borderRadius: 5 }}>
                      <div style={{ height: '100%', width: `${Math.min(100, v)}%`, background: ragSolid(s.status[selectedIndicator]), borderRadius: 5 }} />
                    </div>
                  </div>
                );
              })}
              {sortedStates.length === 0 && (
                <div style={{ color: 'var(--text-muted)', fontSize: 14 }}>
                  {t('Not available for this dataset.', 'Tiada untuk dataset ini.')}
                </div>
              )}
            </>
          )}
        </FocusOverlay>
      </div>

      {/* ── By-Gender + By-Age ──────────────────────────────────────────── */}
      <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap' }}>
        <GroupBars
          title={t('By Gender', 'Mengikut Jantina')}
          rows={kpi?.by_gender ?? []}
          labelKey="gender"
          indicator={selectedIndicator}
          notAvail={t('Not available for this dataset.', 'Tiada untuk dataset ini.')}
          lang={lang}
        />
        <GroupBars
          title={t('By Age Group', 'Mengikut Kumpulan Umur')}
          rows={kpi?.by_age ?? []}
          labelKey="group"
          indicator={selectedIndicator}
          notAvail={t('Not available for this dataset.', 'Tiada untuk dataset ini.')}
          lang={lang}
        />
        {(kpi?.by_income?.length ?? 0) > 0 && (
          <GroupBars
            title={t('By Income Group', 'Mengikut Kumpulan Pendapatan')}
            rows={kpi?.by_income ?? []}
            labelKey="income"
            indicator={selectedIndicator}
            notAvail={t('Not available for this dataset.', 'Tiada untuk dataset ini.')}
            lang={lang}
          />
        )}
      </div>

      {/* ── Indicator trend by year (standalone, full-width) ────────────────
          Pulled out of the population-breakdown grid so it gets the full row
          width its time axis needs. Always visible when blocks are present. */}
      {blocks && (() => {
        const trendEntry = catalogByHome('dashboard').find(e => e.shape === 'trend_records');
        const b = trendEntry ? blocks[trendEntry.key] : undefined;
        if (trendEntry && isTrendRecordsBlock(b)) {
          return (
            <TrendLineCard
              title={lang === 'en' ? trendEntry.titleEn : trendEntry.titleBm}
              data={b}
              lang={lang}
            />
          );
        }
        // Designed empty state instead of a silent gap / bare "—".
        return (
          <div style={{
            background: 'var(--surface)', border: '1px solid var(--border)',
            borderRadius: 'var(--radius-card)', boxShadow: 'var(--shadow-card)',
            padding: '20px 22px', display: 'flex', alignItems: 'center', gap: 14,
          }}>
            <div style={{
              width: 38, height: 38, borderRadius: 'var(--radius-sm)', flexShrink: 0,
              background: 'var(--surface-2)', color: 'var(--text-muted)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <TrendingUp size={18} />
            </div>
            <div>
              <div style={{ fontFamily: 'var(--font-body)', fontWeight: 700, fontSize: 14, color: 'var(--text-primary)' }}>
                {t('Indicator trend by year', 'Trend penunjuk mengikut tahun')}
              </div>
              <div style={{ fontSize: 12.5, color: 'var(--text-secondary)', marginTop: 2 }}>
                {t('Not enough data yet — needs ≥2 measurement years to plot a trend.',
                   'Data belum mencukupi — perlukan ≥2 tahun pengukuran untuk memaparkan trend.')}
              </div>
            </div>
          </div>
        );
      })()}

      {/* ── Population breakdown (collapsed by default) ─────────────────────
          Cohort splits (gender / state / income / vaccine) driven by
          /charts/blocks via the shared chart catalog. The trend chart is
          rendered separately above. Hidden entirely when the dataset emits
          none of these blocks. */}
      {blocks && catalogByHome('dashboard').some(e => e.shape !== 'trend_records' && e.key in blocks) && (
        <div style={{
          background: 'var(--surface)', border: '1px solid var(--border)',
          borderRadius: 'var(--radius-card)', boxShadow: 'var(--shadow-card)',
          overflow: 'hidden',
        }}>
          <button
            onClick={() => setPopOpen(o => !o)}
            style={{
              width: '100%', background: 'none', border: 'none', cursor: 'pointer',
              padding: '14px 20px', display: 'flex', alignItems: 'center', gap: 8,
              color: 'var(--text-primary)', fontWeight: 600, fontSize: 13,
            }}
          >
            {popOpen ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
            {t('Population breakdown', 'Pecahan populasi')}
            <span style={{ color: 'var(--text-muted)', fontWeight: 500, fontSize: 12 }}>
              ({catalogByHome('dashboard').filter(e => e.shape !== 'trend_records' && e.key in blocks).length})
            </span>
          </button>
          {popOpen && (
            <div style={{ padding: '0 20px 20px', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 14 }}>
              {catalogByHome('dashboard').filter(e => e.shape !== 'trend_records').map(entry => {
                const b = blocks[entry.key];
                if (!b) return null;
                const title = lang === 'en' ? entry.titleEn : entry.titleBm;
                if (entry.shape === 'pie_array' && isPieArrayBlock(b)) {
                  return <DonutCard key={entry.key} title={title} data={b} />;
                }
                if (entry.shape === 'bar_labeled' && entry.labelKey && isBarLabeledBlock(b, entry.labelKey)) {
                  return <MiniBarCard key={entry.key} title={title} data={b} labelKey={entry.labelKey} />;
                }
                return null;
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
