import React, { useState, useEffect, useMemo } from 'react';
import { AlertCircle, AlertTriangle, Info, ChevronDown, ChevronUp } from 'lucide-react';
import { api } from '../api/client';
import { useLang } from '../context/LanguageContext';
import { useSession } from '../context/SessionContext';
import { SessionGuard } from '../components/SessionGuard';
import { RagBadge, scoreToRag } from '../components/RagBadge';
import { ColumnHistogram } from '../components/ColumnHistogram';
import { DonutCard } from '../components/DonutCard';
import { catalogByHome, isPieArrayBlock, isDonutObjectBlock } from '../lib/chartCatalog';

interface Issue { description: string; severity: 'critical' | 'warning' | 'info'; count: number; samples?: string[]; }
interface AnomalyRow { row_index: number; columns: string[]; suggestion: string; }

function ScoreGauge({ score }: { score: number }) {
  const rag = scoreToRag(score);
  const color = rag === 'good' ? 'var(--success)' : rag === 'warning' ? 'var(--warning)' : 'var(--danger)';
  const r = 54, circ = 2 * Math.PI * r;
  const dash = (score / 100) * circ;
  return (
    <svg width={140} height={140} viewBox="0 0 140 140">
      <circle cx={70} cy={70} r={r} fill="none" stroke="var(--border)" strokeWidth={12} />
      <circle cx={70} cy={70} r={r} fill="none" stroke={color} strokeWidth={12}
        strokeDasharray={`${dash} ${circ}`} strokeLinecap="round"
        transform="rotate(-90 70 70)" style={{ transition: 'stroke-dasharray 0.8s ease' }} />
      <text x={70} y={68} textAnchor="middle" fontSize={24} fontWeight={700} fill="var(--text-primary)" fontFamily="Inter, sans-serif">
        {score.toFixed(0)}
      </text>
      <text x={70} y={85} textAnchor="middle" fontSize={11} fill="var(--text-muted)" fontFamily="Inter, sans-serif">
        / 100
      </text>
    </svg>
  );
}

export function QualityPage() {
  const { t, lang } = useLang();
  const { cacheId, qualityScore, cleanStats } = useSession();
  const [anomalies, setAnomalies] = useState<AnomalyRow[] | null>(null);
  const [anomalyLoading, setAnomalyLoading] = useState(false);
  const [expanded, setExpanded] = useState<number | null>(null);

  const score = qualityScore ?? 0;
  const stats = cleanStats as Record<string, unknown> | null;
  const issues: Issue[] = (stats?.top_issues as Issue[]) ?? [];
  const rulesApplied: string[] = (stats?.rules_applied as string[]) ?? [];

  const [previewRows, setPreviewRows] = useState<Record<string, unknown>[]>([]);
  /* Classification breakdown — fetched from the same /charts/blocks
     endpoint Geo uses. Lazy + tolerant of missing columns: if the dataset
     has no WHO z-score classes, the donuts simply render nothing. */
  const [blocks, setBlocks] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    if (!cacheId) return;
    let cancelled = false;
    api.get(`/clean/preview-cached/${cacheId}`)
      .then(r => { if (!cancelled) setPreviewRows(Array.isArray(r.data?.rows) ? r.data.rows : []); })
      .catch(() => { if (!cancelled) setPreviewRows([]); });
    api.get<Record<string, unknown>>(`/charts/blocks?cache_id=${cacheId}`)
      .then(r => { if (!cancelled) setBlocks(r.data); })
      .catch(() => { if (!cancelled) setBlocks(null); });
    return () => { cancelled = true; };
  }, [cacheId]);

  const previewCols = previewRows.length > 0 ? Object.keys(previewRows[0]) : [];
  const numericCols = useMemo(
    () => previewCols.filter(c =>
      previewRows.some(rw => rw[c] != null && rw[c] !== '' && Number.isFinite(Number(rw[c])))
    ),
    [previewCols, previewRows],
  );
  const [distCol, setDistCol] = useState<string>('');
  const activeDistCol = distCol || numericCols[0] || '';
  const distValues = useMemo(
    () => previewRows.map(rw => Number(rw[activeDistCol])).filter(v => Number.isFinite(v)),
    [previewRows, activeDistCol],
  );

  const runAnomalyDetection = async () => {
    if (!cacheId) return;
    setAnomalyLoading(true);
    try {
      const r = await api.post<{ anomalies: AnomalyRow[] }>(`/ml/suggest?cache_id=${cacheId}`);
      setAnomalies(r.data.anomalies ?? []);
    } catch { setAnomalies([]); }
    finally { setAnomalyLoading(false); }
  };

  const sevIcon = (sev: string) => {
    if (sev === 'critical') return <AlertCircle size={15} style={{ color: 'var(--danger)', flexShrink: 0 }} />;
    if (sev === 'warning')  return <AlertTriangle size={15} style={{ color: 'var(--warning)', flexShrink: 0 }} />;
    return <Info size={15} style={{ color: 'var(--kkm-sky)', flexShrink: 0 }} />;
  };

  return (
    <SessionGuard>
      <div style={{ display: 'flex', gap: 24, alignItems: 'flex-start' }}>

        {/* Left: score gauge */}
        <div style={{
          flex: '0 0 260px', background: 'var(--surface)', border: '1px solid var(--border)',
          borderRadius: 'var(--radius-card)', padding: '28px 20px',
          boxShadow: 'var(--shadow-card)', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16,
        }}>
          <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.07em', textTransform: 'uppercase', color: 'var(--text-secondary)' }}>
            {t('Quality Score', 'Skor Kualiti')}
          </div>
          <ScoreGauge score={score} />
          <RagBadge rag={scoreToRag(score)} lang={lang} />

          {stats && (
            <div style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: 8, marginTop: 8 }}>
              {[
                { label: t('Rows before', 'Baris sebelum'), value: (Number(stats.rows_before) || 0).toLocaleString() },
                { label: t('Rows after', 'Baris selepas'),  value: (Number(stats.rows_after) || 0).toLocaleString()  },
              ].map(row => (
                <div key={row.label} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
                  <span style={{ color: 'var(--text-secondary)' }}>{row.label}</span>
                  <span style={{ fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'JetBrains Mono, monospace' }}>{row.value}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right: issues + rules */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 20 }}>

          {/* Issues */}
          <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-card)', boxShadow: 'var(--shadow-card)' }}>
            <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)', fontSize: 13, fontWeight: 600 }}>
              {t('Issues Detected', 'Isu Dikesan')}
            </div>
            {issues.length === 0 ? (
              <div style={{ padding: '24px 20px', color: 'var(--text-muted)', fontSize: 13 }}>
                {t('No issues detected.', 'Tiada isu dikesan.')}
              </div>
            ) : issues.map((issue, i) => (
              <div key={i} style={{ borderBottom: i < issues.length - 1 ? '1px solid var(--border)' : 'none' }}>
                <div
                  style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px 20px', cursor: issue.samples?.length ? 'pointer' : 'default' }}
                  onClick={() => setExpanded(expanded === i ? null : i)}
                >
                  {sevIcon(issue.severity)}
                  <span style={{ flex: 1, fontSize: 13, color: 'var(--text-primary)' }}>{issue.description}</span>
                  <span style={{ fontSize: 12, fontWeight: 600, fontFamily: 'JetBrains Mono, monospace', color: 'var(--text-muted)' }}>
                    {Number(issue.count).toLocaleString()}
                  </span>
                  {issue.samples?.length ? (expanded === i ? <ChevronUp size={14} /> : <ChevronDown size={14} />) : null}
                </div>
                {expanded === i && issue.samples && (
                  <div style={{ padding: '0 20px 12px 44px', fontSize: 12, color: 'var(--text-muted)', fontFamily: 'JetBrains Mono, monospace' }}>
                    {issue.samples.join(', ')}
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Rules applied */}
          {rulesApplied.length > 0 && (
            <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-card)', padding: '18px 20px', boxShadow: 'var(--shadow-card)' }}>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>
                {t('Rules Applied', 'Peraturan Digunakan')}
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {rulesApplied.map((r: string) => (
                  <span key={r} style={{ fontSize: 12, background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 999, padding: '4px 12px', color: 'var(--text-secondary)' }}>
                    {r}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Anomaly detection */}
          <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-card)', padding: '18px 20px', boxShadow: 'var(--shadow-card)' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: anomalies ? 16 : 0 }}>
              <div>
                <div style={{ fontSize: 13, fontWeight: 600 }}>{t('Anomaly Detection', 'Pengesanan Anomali')}</div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
                  {t('IsolationForest — flags statistically unusual rows', 'IsolationForest — mengenal pasti baris yang tidak biasa secara statistik')}
                </div>
              </div>
              {anomalies === null && (
                <button
                  onClick={runAnomalyDetection}
                  disabled={anomalyLoading}
                  style={{ background: 'var(--kkm-blue)', color: '#fff', border: 'none', borderRadius: 'var(--radius-btn)', padding: '8px 16px', fontSize: 13, fontWeight: 600, cursor: 'pointer', opacity: anomalyLoading ? 0.6 : 1 }}
                >
                  {anomalyLoading ? t('Running…', 'Sedang berjalan…') : t('Run Detection', 'Jalankan')}
                </button>
              )}
            </div>

            {anomalies !== null && (
              anomalies.length === 0 ? (
                <div style={{ fontSize: 13, color: 'var(--kkm-teal)' }}>
                  {t('No anomalies detected.', 'Tiada anomali dikesan.')}
                </div>
              ) : (
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border)' }}>
                      {[t('Row', 'Baris'), t('Columns', 'Lajur'), t('Suggestion', 'Cadangan')].map(h => (
                        <th key={h} style={{ padding: '8px 10px', textAlign: 'left', fontWeight: 600, fontSize: 11, color: 'var(--text-secondary)', letterSpacing: '0.05em', textTransform: 'uppercase' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {anomalies.map((a, i) => (
                      <tr key={i} style={{ borderBottom: i < anomalies.length - 1 ? '1px solid var(--border)' : 'none' }}>
                        <td style={{ padding: '8px 10px', fontFamily: 'JetBrains Mono, monospace', color: 'var(--text-muted)' }}>{a.row_index}</td>
                        <td style={{ padding: '8px 10px', fontFamily: 'JetBrains Mono, monospace', color: 'var(--text-secondary)' }}>{a.columns.join(', ')}</td>
                        <td style={{ padding: '8px 10px', color: 'var(--text-primary)' }}>{a.suggestion}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )
            )}
          </div>

          {/* Numeric distribution */}
          <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-card)', padding: '18px 20px', boxShadow: 'var(--shadow-card)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
              <span style={{ fontSize: 13, fontWeight: 600 }}>
                {t('Numeric Distribution', 'Taburan Berangka')}
              </span>
              {numericCols.length > 0 && (
                <select
                  value={activeDistCol}
                  onChange={e => setDistCol(e.target.value)}
                  style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 6, padding: '6px 10px', fontSize: 12, color: 'var(--text-primary)' }}
                >
                  {numericCols.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              )}
            </div>
            {numericCols.length > 0 ? (
              <ColumnHistogram values={distValues} />
            ) : (
              <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>
                {t('No numeric columns available for this dataset.',
                   'Tiada lajur berangka tersedia untuk dataset ini.')}
              </div>
            )}
          </div>
        </div>

        {/* ── Classification breakdown ─────────────────────────────────────
            WHO z-score classes (WAZ/HAZ/BAZ) + BMI status pie. Hidden when
            the dataset has none of these columns. */}
        {blocks && catalogByHome('quality').some(e => e.key in blocks) && (
          <div style={{ marginTop: 24 }}>
            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>
              {t('Classification breakdown', 'Pecahan klasifikasi')}
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 14 }}>
              {catalogByHome('quality').map(entry => {
                const b = blocks[entry.key];
                if (!b) return null;
                const title = lang === 'en' ? entry.titleEn : entry.titleBm;
                if (entry.shape === 'donut_object' && isDonutObjectBlock(b)) {
                  return <DonutCard key={entry.key} title={title} data={b.data} />;
                }
                if (entry.shape === 'pie_array' && isPieArrayBlock(b)) {
                  return <DonutCard key={entry.key} title={title} data={b} />;
                }
                return null;
              })}
            </div>
          </div>
        )}
      </div>
    </SessionGuard>
  );
}
