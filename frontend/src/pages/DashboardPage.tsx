import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Upload, AlertTriangle, Users, ShieldCheck, X, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { api } from '../api/client';
import { useLang } from '../context/LanguageContext';
import { useSession } from '../context/SessionContext';
import { ChoroplethMap, District, computeAggregates } from '../components/ChoroplethMap';
import { StatCard } from '../components/StatCard';
import { RagBadge, rateToRag } from '../components/RagBadge';
import { EmptyState } from '../components/EmptyState';

/* ── Types ─────────────────────────────────────────────────────────────── */

interface Summary {
  total_children: number;
  avg_quality_score: number;
  session_count: number;
  alerts: number;
  latest_session: { cache_id: string; filename: string; source_type: string; created_at: string } | null;
  source_breakdown: Record<string, number>;
}

interface Session {
  cache_id: string;
  filename: string;
  source_type: string;
  row_count: number;
  quality_score: number;
  created_at: string | null;
}

interface KpiResult {
  districts?: District[];
  age_group_breakdown?: { under_2: number; under_5: number; under_2_pct: number; under_5_pct: number };
  top_issues?: { description: string; count: number }[];
}

/* ── Helpers ────────────────────────────────────────────────────────────── */

function fmt(n: number | null) { return n == null ? '—' : n.toLocaleString(); }
function pct(r: number) { return `${(r * 100).toFixed(1)}%`; }

function TrendArrow({ delta }: { delta: number }) {
  if (delta > 0) return <TrendingUp size={14} style={{ color: 'var(--danger)' }} />;
  if (delta < 0) return <TrendingDown size={14} style={{ color: 'var(--success)' }} />;
  return <Minus size={14} style={{ color: 'var(--text-muted)' }} />;
}

/* ── Component ──────────────────────────────────────────────────────────── */

export function DashboardPage() {
  const { t, lang } = useLang();
  const { cacheId, setSession } = useSession();
  const nav = useNavigate();

  const [summary, setSummary] = useState<Summary | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [kpi, setKpi] = useState<KpiResult | null>(null);
  const [selectedDistrict, setSelectedDistrict] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  /* fetch summary + sessions (always-on) */
  useEffect(() => {
    Promise.all([
      api.get<Summary>('/dashboard/summary'),
      api.get<Session[]>('/sessions'),
    ]).then(([s, sess]) => {
      setSummary(s.data);
      setSessions(sess.data.slice(0, 5));
    }).catch(console.error).finally(() => setLoading(false));
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
    } catch { /* cache miss — no active data */ }
  }, [activeCacheId]);

  useEffect(() => { fetchKpi(); }, [fetchKpi]);

  const handleDistrictClick = (d: string | null) => {
    setSelectedDistrict(d);
    fetchKpi(d);
  };

  const districts = kpi?.districts ?? [];
  const agg = computeAggregates(districts);

  /* ── Empty state ─────────────────────────────────────────────────────── */
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
        <div style={{ display: 'flex', gap: 40, color: 'var(--text-muted)', fontSize: 13 }}>
          {[
            { n: '①', label: t('Upload', 'Muat Naik') },
            { n: '②', label: t('Clean', 'Bersih') },
            { n: '③', label: t('Analyse', 'Analisis') },
          ].map(step => (
            <div key={step.n} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}>
              <span style={{ fontSize: 24 }}>{step.n}</span>
              <span>{step.label}</span>
            </div>
          ))}
        </div>
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
  const indicators = [
    { key: 'stunting',    enLabel: 'Stunting',    bmLabel: 'Bantut',        rate: agg.stunting,    rag: agg.stuntingRag    },
    { key: 'wasting',     enLabel: 'Wasting',     bmLabel: 'Susut',         rate: agg.wasting,     rag: agg.wastingRag     },
    { key: 'underweight', enLabel: 'Underweight', bmLabel: 'Kurang Berat',  rate: agg.underweight, rag: agg.underweightRag },
    { key: 'overweight',  enLabel: 'Overweight',  bmLabel: 'Berlebihan',    rate: agg.overweight,  rag: agg.overweightRag  },
  ];

  const accentMap: Record<string, string> = {
    stunting: 'var(--danger)', wasting: 'var(--warning)',
    underweight: 'var(--warning)', overweight: 'var(--kkm-teal)',
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>

      {/* ── Header row ──────────────────────────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div style={{ flex: 1 }} />

        {/* District chip */}
        {selectedDistrict ? (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 6,
            background: 'rgba(0,163,224,0.12)', border: '1px solid var(--kkm-sky)',
            borderRadius: 999, padding: '4px 12px', fontSize: 12,
            fontWeight: 600, color: 'var(--kkm-sky)',
          }}>
            Malaysia — {selectedDistrict}
            <button
              onClick={() => handleDistrictClick(null)}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--kkm-sky)', display: 'flex', alignItems: 'center', padding: 0 }}
            >
              <X size={12} />
            </button>
          </div>
        ) : (
          <div style={{
            fontSize: 12, color: 'var(--text-muted)',
            border: '1px solid var(--border)', borderRadius: 999, padding: '4px 12px',
          }}>
            {t('Malaysia — All Districts', 'Malaysia — Semua Daerah')}
          </div>
        )}

        {summary?.latest_session && (
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            {t('Last updated', 'Dikemaskini')}: {new Date(summary.latest_session.created_at).toLocaleDateString()}
          </span>
        )}
      </div>

      {/* ── Hero row: Map + Indicators ──────────────────────────────── */}
      <div style={{ display: 'flex', gap: 20, alignItems: 'stretch' }}>

        {/* Map */}
        <div style={{
          flex: '0 0 62%', background: 'var(--surface)',
          border: '1px solid var(--border)', borderRadius: 'var(--radius-card)',
          padding: 20, boxShadow: 'var(--shadow-card)',
        }}>
          <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.07em', color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: 12 }}>
            {t('District Risk Map', 'Peta Risiko Daerah')}
          </div>
          <ChoroplethMap
            districts={districts}
            selectedDistrict={selectedDistrict}
            onDistrictClick={handleDistrictClick}
          />
        </div>

        {/* Indicator tiles */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 10 }}>
          {indicators.map(ind => (
            <div key={ind.key} style={{
              background: 'var(--surface)',
              border: '1px solid var(--border)',
              borderLeft: `3px solid ${accentMap[ind.key]}`,
              borderRadius: 'var(--radius-card)',
              padding: '14px 16px',
              boxShadow: 'var(--shadow-card)',
              flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
                <span style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.06em', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>
                  {lang === 'en' ? ind.enLabel : ind.bmLabel}
                </span>
                <RagBadge rag={ind.rag === 'green' ? 'good' : ind.rag === 'amber' ? 'warning' : 'critical'} lang={lang} />
              </div>
              <div style={{ fontSize: 26, fontWeight: 700, color: 'var(--text-primary)' }}>
                {pct(ind.rate)}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ── KPI strip ────────────────────────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16 }}>
        <StatCard
          label={t('Children Processed', 'Kanak-kanak Diproses')}
          value={fmt(summary?.total_children ?? null)}
          accent="var(--kkm-blue)"
          icon={<Users size={14} />}
        />
        <StatCard
          label={t('Avg Quality Score', 'Purata Skor Kualiti')}
          value={summary ? `${summary.avg_quality_score}%` : '—'}
          accent="var(--kkm-teal)"
          icon={<ShieldCheck size={14} />}
        />
        <StatCard
          label={t('Sessions', 'Sesi')}
          value={fmt(summary?.session_count ?? null)}
          accent="var(--kkm-sky)"
        />
        <StatCard
          label={t('Alerts', 'Amaran')}
          value={fmt(summary?.alerts ?? null)}
          accent={summary && summary.alerts > 0 ? 'var(--danger)' : 'var(--success)'}
          icon={<AlertTriangle size={14} />}
        />
      </div>

      {/* ── Secondary row ─────────────────────────────────────────────── */}
      {kpi && (
        <div style={{ display: 'flex', gap: 20 }}>

          {/* Age group split */}
          {kpi.age_group_breakdown && (
            <div style={{
              flex: '0 0 58%', background: 'var(--surface)',
              border: '1px solid var(--border)', borderRadius: 'var(--radius-card)',
              padding: '18px 20px', boxShadow: 'var(--shadow-card)',
            }}>
              <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.07em', color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: 14 }}>
                {t('Age Group Distribution', 'Taburan Kumpulan Umur')}
              </div>
              {[
                { label: t('Under 2 Years', 'Bawah 2 Tahun'), pct: kpi.age_group_breakdown.under_2_pct, n: kpi.age_group_breakdown.under_2, color: 'var(--kkm-blue)' },
                { label: t('Under 5 Years', 'Bawah 5 Tahun'), pct: kpi.age_group_breakdown.under_5_pct, n: kpi.age_group_breakdown.under_5, color: 'var(--kkm-sky)' },
              ].map(row => (
                <div key={row.label} style={{ marginBottom: 12 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6, fontSize: 13, color: 'var(--text-secondary)' }}>
                    <span>{row.label}</span>
                    <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                      {(row.pct * 100).toFixed(1)}% &nbsp; ({row.n.toLocaleString()})
                    </span>
                  </div>
                  <div style={{ height: 8, background: 'var(--surface-2)', borderRadius: 4, overflow: 'hidden' }}>
                    <div style={{
                      height: '100%', width: `${row.pct * 100}%`,
                      background: row.color, borderRadius: 4,
                      transition: 'width 0.6s ease',
                    }} />
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Top quality issues */}
          {kpi.top_issues && kpi.top_issues.length > 0 && (
            <div style={{
              flex: 1, background: 'var(--surface)',
              border: '1px solid var(--border)', borderRadius: 'var(--radius-card)',
              padding: '18px 20px', boxShadow: 'var(--shadow-card)',
            }}>
              <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.07em', color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: 14 }}>
                {t('Top Quality Issues', 'Isu Kualiti Utama')}
              </div>
              {kpi.top_issues.slice(0, 3).map((issue, i) => (
                <div
                  key={i}
                  onClick={() => nav('/quality')}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 10,
                    padding: '9px 0', cursor: 'pointer',
                    borderBottom: i < 2 ? '1px solid var(--border)' : 'none',
                  }}
                >
                  <AlertTriangle size={14} style={{ color: 'var(--warning)', flexShrink: 0 }} />
                  <span style={{ flex: 1, fontSize: 13, color: 'var(--text-primary)' }}>{issue.description}</span>
                  <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', fontFamily: 'JetBrains Mono, monospace' }}>
                    {issue.count.toLocaleString()}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Recent sessions table ─────────────────────────────────────── */}
      {sessions.length > 0 && (
        <div style={{
          background: 'var(--surface)', border: '1px solid var(--border)',
          borderRadius: 'var(--radius-card)', boxShadow: 'var(--shadow-card)',
        }}>
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '16px 20px', borderBottom: '1px solid var(--border)',
          }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
              {t('Recent Sessions', 'Sesi Terkini')}
            </span>
            <button
              onClick={() => nav('/history')}
              style={{ background: 'none', border: 'none', color: 'var(--kkm-blue)', fontSize: 12, fontWeight: 600, cursor: 'pointer' }}
            >
              {t('View all →', 'Lihat semua →')}
            </button>
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                {[
                  t('File', 'Fail'), t('Type', 'Jenis'), t('Rows', 'Baris'),
                  t('Score', 'Skor'), t('Date', 'Tarikh'), t('Action', 'Tindakan'),
                ].map(h => (
                  <th key={h} style={{
                    padding: '10px 20px', textAlign: 'left',
                    fontSize: 11, fontWeight: 600, letterSpacing: '0.06em',
                    textTransform: 'uppercase', color: 'var(--text-secondary)',
                  }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sessions.map((s, i) => (
                <tr
                  key={s.cache_id}
                  style={{ borderBottom: i < sessions.length - 1 ? '1px solid var(--border)' : 'none' }}
                >
                  <td style={{ padding: '12px 20px', fontSize: 13, color: 'var(--text-primary)', fontWeight: 500 }}>
                    {s.filename}
                  </td>
                  <td style={{ padding: '12px 20px' }}>
                    <span style={{
                      fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 999,
                      background: 'var(--surface-2)', color: 'var(--text-secondary)',
                      textTransform: 'uppercase',
                    }}>
                      {s.source_type || '—'}
                    </span>
                  </td>
                  <td style={{ padding: '12px 20px', fontSize: 13, color: 'var(--text-secondary)', fontFamily: 'JetBrains Mono, monospace' }}>
                    {s.row_count.toLocaleString()}
                  </td>
                  <td style={{ padding: '12px 20px' }}>
                    <RagBadge rag={s.quality_score >= 80 ? 'good' : s.quality_score >= 60 ? 'warning' : 'critical'} lang={lang} />
                  </td>
                  <td style={{ padding: '12px 20px', fontSize: 12, color: 'var(--text-muted)' }}>
                    {s.created_at ? new Date(s.created_at).toLocaleDateString() : '—'}
                  </td>
                  <td style={{ padding: '12px 20px' }}>
                    <button
                      onClick={() => {
                        setSession({ cacheId: s.cache_id, filename: s.filename, sourceType: s.source_type });
                        nav('/quality');
                      }}
                      style={{
                        background: 'var(--kkm-blue)', color: '#fff', border: 'none',
                        borderRadius: 'var(--radius-btn)', padding: '5px 12px',
                        fontSize: 12, fontWeight: 600, cursor: 'pointer',
                      }}
                    >
                      {t('Open', 'Buka')}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
