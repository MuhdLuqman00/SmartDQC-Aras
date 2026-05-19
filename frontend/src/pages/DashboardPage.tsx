import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Upload, X } from 'lucide-react';
import { api } from '../api/client';
import { useLang } from '../context/LanguageContext';
import { useSession } from '../context/SessionContext';
import { ChoroplethMap, District } from '../components/ChoroplethMap';

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
  state?: string; gender?: string; group?: string;
  n: number;
  rates: Partial<Record<IndicatorKey, number>>;
  status: Partial<Record<IndicatorKey, Rag>>;
}
interface KpiResult {
  overall_status: Rag;
  total_children: number;
  indicators: IndicatorKpi[];
  by_state: GroupRow[];
  by_gender: GroupRow[];
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
  labelKey: 'gender' | 'group';
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

/* Shared RAG palette — kept in sync with ChoroplethMap so list bars
   and the map read the same. `track` is the same hue at low alpha so a
   0%-rate "green/good" row is still visibly green even with no fill. */
const RAG_HEX: Record<'green' | 'amber' | 'red', string> = {
  green: '#00b5a5', amber: '#e0a13c', red: '#d9534f',
};
const ragSolid = (r?: Rag): string => RAG_HEX[ragToLower(r)];
/* Track tint per RAG (8-digit hex incl. alpha). Green uses a brighter
   hue at higher opacity so a 0%-rate "good" row — where the track is
   the whole signal (no fill on top) — reads as clearly bright green.
   Amber/red stay ~40% since they sit behind a solid fill. */
const RAG_TRACK_HEX: Record<'green' | 'amber' | 'red', string> = {
  green: '#2fe3c2cc', amber: '#e0a13c66', red: '#d9534f66',
};
const ragTrack = (r?: Rag): string => RAG_TRACK_HEX[ragToLower(r)];

/* Backend returns data-driven gender values and BM-hardcoded age buckets.
   Normalise then translate so labels follow the chosen UI language. */
function formatGroupLabel(labelKey: 'gender' | 'group', raw: string, lang: 'en' | 'bm'): string {
  const v = raw.trim().toLowerCase();
  if (labelKey === 'gender') {
    if (['lelaki', 'l', 'male', 'm'].includes(v)) return lang === 'en' ? 'Male' : 'Lelaki';
    if (['perempuan', 'p', 'female', 'f'].includes(v)) return lang === 'en' ? 'Female' : 'Perempuan';
    return raw;
  }
  if (v === 'bawah 2 tahun') return lang === 'en' ? 'Under 2 Years' : 'Bawah 2 Tahun';
  if (v === '2-5 tahun' || v === '2–5 tahun') return lang === 'en' ? '2–5 Years' : '2-5 Tahun';
  return raw;
}

/* ── Component ──────────────────────────────────────────────────────────── */

export function DashboardPage() {
  const { t, lang } = useLang();
  const { cacheId, setSession } = useSession();
  const nav = useNavigate();

  const [summary, setSummary] = useState<Summary | null>(null);
  const [kpi, setKpi] = useState<KpiResult | null>(null);
  const [selectedDistrict, setSelectedDistrict] = useState<string | null>(null);
  const [selectedIndicator, setSelectedIndicator] = useState<IndicatorKey>('stunting');
  const [kpiError, setKpiError] = useState(false);
  const [loading, setLoading] = useState(true);

  /* fetch summary (always-on) */
  useEffect(() => {
    api.get<Summary>('/dashboard/summary')
      .then(s => setSummary(s.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  /* fetch kpi for current/latest session */
  const activeCacheId = cacheId || summary?.latest_session?.cache_id;

  const fetchKpi = useCallback(async (district?: string | null) => {
    if (!activeCacheId) return;
    try {
      const params: Record<string, string> = { cache_id: activeCacheId };
      if (district) params.district = district;
      const r = await api.post<KpiResult>(`/kpi/dashboard?${new URLSearchParams(params)}`);
      setKpi(r.data);
      setKpiError(false);
    } catch {
      setKpiError(true);
    }
  }, [activeCacheId]);

  useEffect(() => { fetchKpi(); }, [fetchKpi]);

  const handleDistrictClick = (d: string | null) => {
    setSelectedDistrict(d);
    fetchKpi(d);
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
          fontFamily: "'Plus Jakarta Sans', sans-serif", fontWeight: 700, fontSize: 22,
        }}>S</div>
        <h2 style={{ fontFamily: "'Plus Jakarta Sans', sans-serif", fontSize: 24, fontWeight: 700, color: 'var(--text-primary)' }}>
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
            fontFamily: "'Plus Jakarta Sans', sans-serif", fontWeight: 700, fontSize: 15,
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

  const sortedStates = [...(kpi?.by_state ?? [])].sort(
    (a, b) => Number(b.rates[selectedIndicator] ?? 0) - Number(a.rates[selectedIndicator] ?? 0),
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

      {kpiError && (
        <div style={{
          background: 'var(--warning-bg)', border: '1px solid var(--warning)',
          borderRadius: 'var(--radius-card)', padding: '12px 16px', fontSize: 13,
          color: 'var(--text-primary)',
        }}>
          {t('No analysed dataset — run cleaning first.', 'Tiada dataset dianalisis — jalankan pembersihan dahulu.')}
        </div>
      )}

      {/* ── Header + indicator selector ─────────────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        <h1 style={{ fontFamily: "'Plus Jakarta Sans', sans-serif", fontSize: 20, fontWeight: 700, margin: 0 }}>
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
            {t('Last updated', 'Dikemaskini')}: {new Date(summary.latest_session.created_at).toLocaleDateString()}
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

      {/* ── Indicator cards ─────────────────────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16 }}>
        {indicators.map(ind => {
          const sel = ind.key === selectedIndicator;
          const ragColor = ind.rag === 'Green' ? 'var(--success)'
            : ind.rag === 'Amber' ? 'var(--warning)' : 'var(--danger)';
          return (
            <div key={ind.key}
              onClick={() => setSelectedIndicator(ind.key)}
              style={{
                background: 'var(--surface)', border: '1px solid var(--border)',
                outline: sel ? '2px solid var(--kkm-blue)' : 'none',
                borderRadius: 'var(--radius-card)', padding: '16px 18px',
                boxShadow: 'var(--shadow-card)', cursor: 'pointer',
              }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <span style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--text-secondary)' }}>
                  {lang === 'en' ? ind.label_en : ind.label_bm}
                </span>
                <span style={{ fontSize: 10, fontWeight: 700, color: '#fff', background: ragColor, borderRadius: 999, padding: '2px 8px' }}>
                  {ind.rag}
                </span>
              </div>
              <div style={{ fontSize: 26, fontWeight: 700, color: 'var(--text-primary)' }}>
                {Number(ind.actual).toFixed(2)}%
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
                {t('Target', 'Sasaran')} {Number(ind.npan_target).toFixed(0)}%
                {ind.who_target != null ? ` · WHO ${Number(ind.who_target).toFixed(0)}%` : ''}
                {' · '}
                <span style={{ color: ind.gap > 0 ? 'var(--danger)' : 'var(--success)' }}>
                  {ind.gap > 0 ? '▲' : '▼'} {Math.abs(Number(ind.gap)).toFixed(2)}
                </span>
              </div>
            </div>
          );
        })}
        {indicators.length === 0 && (
          <div style={{ gridColumn: '1 / -1', color: 'var(--text-muted)', fontSize: 13, padding: 20, textAlign: 'center' }}>
            {t('No indicator data — run cleaning first.', 'Tiada data penunjuk — jalankan pembersihan dahulu.')}
          </div>
        )}
      </div>

      {/* ── Map + By-State ──────────────────────────────────────────────── */}
      <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap' }}>
        <div style={{
          flex: '1 1 360px', background: 'var(--surface)', border: '1px solid var(--border)',
          borderRadius: 'var(--radius-card)', padding: 20, boxShadow: 'var(--shadow-card)',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <span style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.07em', textTransform: 'uppercase', color: 'var(--text-secondary)' }}>
              {t('State Risk Map', 'Peta Risiko Negeri')}
            </span>
            {selectedDistrict && (
              <button onClick={() => handleDistrictClick(null)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 6, background: 'rgba(0,163,224,0.12)',
                  border: '1px solid var(--kkm-sky)', borderRadius: 999, padding: '4px 12px',
                  fontSize: 12, fontWeight: 600, color: 'var(--kkm-sky)', cursor: 'pointer',
                }}>
                {selectedDistrict} <X size={12} />
              </button>
            )}
          </div>
          {mapDistricts.length === 0
            ? <div style={{ padding: 32, textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>
                {t('No state data for this dataset.', 'Tiada data negeri untuk dataset ini.')}
              </div>
            : <ChoroplethMap districts={mapDistricts} selectedDistrict={selectedDistrict} onDistrictClick={handleDistrictClick} />}
        </div>

        <div style={{
          flex: '1 1 360px', background: 'var(--surface)', border: '1px solid var(--border)',
          borderRadius: 'var(--radius-card)', padding: 20, boxShadow: 'var(--shadow-card)',
        }}>
          <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.07em', textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: 14 }}>
            {t('By State', 'Mengikut Negeri')}
            {selInd ? ` — ${lang === 'en' ? selInd.label_en : selInd.label_bm}` : ''}
          </div>
          {sortedStates.map(s => {
            const v = Number(s.rates[selectedIndicator] ?? 0);
            return (
              <div key={s.state} style={{ marginBottom: 8 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: 'var(--text-secondary)', marginBottom: 3 }}>
                  <span>{s.state}</span><span style={{ fontWeight: 600 }}>{v.toFixed(2)}%</span>
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
        </div>
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
      </div>
    </div>
  );
}
