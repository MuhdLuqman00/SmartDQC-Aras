import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api } from '../api/client';
import { ChoroplethMap, computeAggregates } from '../components/ChoroplethMap';
import type { District } from '../components/ChoroplethMap';
import { useLang } from '../context/LanguageContext';
import { useSession } from '../context/SessionContext';

// ── Interfaces ────────────────────────────────────────────────────────────────

interface KpiDashboardResponse {
  districts: District[];
}

interface RiskDistrictAgg {
  avg_score: number;
  high_risk_count: number;
}

interface RiskResponse {
  per_child: { ic: string; risk_score: number; risk_tier: 'Low' | 'Medium' | 'High' }[];
  district_aggregation: Record<string, RiskDistrictAgg>;
}

// ── RAG helpers ───────────────────────────────────────────────────────────────

const RAG_COLOR: Record<'green' | 'amber' | 'red', string> = {
  green: 'var(--success)',
  amber: 'var(--warning)',
  red:   'var(--danger)',
};
const RAG_BG_TOKEN: Record<'green' | 'amber' | 'red', string> = {
  green: 'var(--success-bg)',
  amber: 'var(--warning-bg)',
  red:   'var(--danger-bg)',
};
const RAG_LABEL_MY: Record<'green' | 'amber' | 'red', string> = {
  green: 'Baik',
  amber: 'Sederhana',
  red:   'Kritikal',
};

function RagBadge({ rag }: { rag: 'green' | 'amber' | 'red' }) {
  const { t } = useLang();
  const label = t(
    { green: 'Good', amber: 'Moderate', red: 'Critical' }[rag],
    RAG_LABEL_MY[rag]
  );
  return (
    <span style={{
      display: 'inline-block', padding: '2px 10px', borderRadius: 6,
      fontSize: 11, fontWeight: 700, background: RAG_BG_TOKEN[rag],
      color: RAG_COLOR[rag], border: `0.5px solid ${RAG_COLOR[rag]}`, letterSpacing: '0.04em',
    }}>
      {label}
    </span>
  );
}

function KpiCard({ label, value, rag }: { label: string; value: number; rag: 'green' | 'amber' | 'red' }) {
  return (
    <div style={{
      background: 'var(--surface-2)', border: '0.5px solid var(--border)',
      borderRadius: 10, padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 6,
    }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
        {label}
      </div>
      <div style={{ fontSize: 26, fontWeight: 700, color: 'var(--navy)' }}>
        {(value * 100).toFixed(1)}%
      </div>
      <RagBadge rag={rag} />
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export function GeoPage() {
  const [searchParams] = useSearchParams();
  const { t } = useLang();
  const cacheId = searchParams.get('cache_id') ?? '';

  const [districts, setDistricts] = useState<District[]>([]);
  const [riskData, setRiskData] = useState<RiskResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!cacheId) return;
    setLoading(true);
    setError(null);
    Promise.all([
      api.post<KpiDashboardResponse>(`/kpi/dashboard?cache_id=${cacheId}`),
      api.post<RiskResponse>(`/risk/score?cache_id=${cacheId}`),
    ])
      .then(([kpiRes, riskRes]) => {
        setDistricts(kpiRes.data.districts);
        setRiskData(riskRes.data);
      })
      .catch(() => setError(t('Failed to load data. Please check your Cache ID.', 'Gagal memuatkan data. Sila semak semula Cache ID anda.')))
      .finally(() => setLoading(false));
  }, [cacheId]);

  const agg = computeAggregates(districts);

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 320, color: 'var(--text-secondary)', fontSize: 15 }}>
        {t('Loading...', 'Memuatkan...')}
      </div>
    );
  }

  return (
    <div style={{ padding: '4px 0' }}>
      <h1 style={{ margin: '0 0 20px', fontSize: 22, fontWeight: 700, color: 'var(--text-primary)' }}>
        {t('Geography & Risk Map', 'Peta Geografi & Risiko')}
      </h1>

      {error && (
        <div style={{
          background: 'var(--danger-bg)', color: 'var(--danger)',
          border: '0.5px solid var(--danger)', borderRadius: 8,
          padding: '10px 16px', marginBottom: 20, fontSize: 13,
        }}>
          {error}
        </div>
      )}

      <div style={{ display: 'flex', gap: 20, alignItems: 'flex-start', marginBottom: 24 }}>

        {/* Left 40% — choropleth map */}
        <div style={{
          flex: '0 0 40%', background: 'var(--surface-2)',
          border: '0.5px solid var(--border)', borderRadius: 12,
          overflow: 'hidden', boxSizing: 'border-box',
        }}>
          <ChoroplethMap districts={districts} />
        </div>

        {/* Right 60% — national aggregate KPI cards */}
        <div style={{ flex: '0 0 60%', display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', fontWeight: 500 }}>
            {t('National Average', 'Purata Nasional')}{districts.length > 0 ? ` (${districts.length} ${t('districts', 'daerah')})` : ''}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <KpiCard label={t('Stunting', 'Kelaparan')}        value={agg.stunting}    rag={agg.stuntingRag} />
            <KpiCard label={t('Wasting', 'Kurus')}             value={agg.wasting}     rag={agg.wastingRag} />
            <KpiCard label={t('Underweight', 'Kekurangan Berat')} value={agg.underweight} rag={agg.underweightRag} />
            <KpiCard label={t('Overweight', 'Berlebihan Berat')}  value={agg.overweight}  rag={agg.overweightRag} />
          </div>
        </div>
      </div>

      {/* ── District risk aggregation table ── */}
      <div style={{ background: 'var(--surface)', border: '0.5px solid var(--border)', borderRadius: 12, overflow: 'hidden' }}>
        <div style={{
          padding: '12px 16px', borderBottom: '0.5px solid var(--border)',
          fontSize: 11, fontWeight: 700, color: 'var(--text-secondary)',
          textTransform: 'uppercase', letterSpacing: '0.07em',
        }}>
          {t('District Risk Aggregation', 'Agregasi Risiko Daerah')}
        </div>
        {!riskData ? (
          <div style={{ padding: '24px 16px', color: 'var(--text-muted)', fontSize: 13 }}>{t('No risk data.', 'Tiada data risiko.')}</div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr>
                {[t('District', 'Daerah'), t('Avg Score', 'Skor Purata'), t('High Risk Count', 'Kiraan Berisiko Tinggi'), 'RAG'].map(col => (
                  <th key={col} style={{
                    padding: '10px 16px', background: 'var(--surface-2)',
                    borderBottom: '0.5px solid var(--border)', fontWeight: 600,
                    color: 'var(--text-secondary)', textAlign: 'left',
                    fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.06em',
                  }}>
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {Object.entries(riskData.district_aggregation)
                .sort(([, a], [, b]) => b.avg_score - a.avg_score)
                .map(([dname, dagg]) => {
                  const rag = districts.find(d => d.name === dname)?.risk_rag ?? 'amber';
                  return (
                    <tr key={dname} style={{ borderBottom: '0.5px solid var(--border)', transition: 'all 0.15s ease' }}>
                      <td style={{ padding: '11px 16px', color: 'var(--text-primary)' }}>{dname}</td>
                      <td style={{ padding: '11px 16px', color: 'var(--text-primary)', fontWeight: 600 }}>{dagg.avg_score.toFixed(1)}</td>
                      <td style={{ padding: '11px 16px', color: 'var(--text-primary)' }}>{dagg.high_risk_count.toLocaleString()}</td>
                      <td style={{ padding: '11px 16px' }}><RagBadge rag={rag} /></td>
                    </tr>
                  );
                })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
