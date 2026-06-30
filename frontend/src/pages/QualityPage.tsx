import React, { useState, useEffect, useMemo } from 'react';
import { AlertCircle, AlertTriangle, Info, ChevronDown, ChevronUp, ShieldCheck } from 'lucide-react';
import { api } from '../api/client';
import { useLang } from '../context/LanguageContext';
import { useSession } from '../context/SessionContext';
import { SessionGuard } from '../components/SessionGuard';
import { RagBadge, scoreToRag } from '../components/RagBadge';
import { ColumnHistogram } from '../components/ColumnHistogram';
import { DonutCard } from '../components/DonutCard';
import { StatusClassBars } from '../components/StatusClassBars';
import { catalogByHome, isPieArrayBlock, isDonutObjectBlock } from '../lib/chartCatalog';
import { translateIssue, translateRule } from '../lib/issueCatalog';
import { ErrorRetry } from '../components/ErrorRetry';
import { InlineEmpty } from '../components/InlineEmpty';

interface Issue { code?: string; description: string; severity: 'critical' | 'warning' | 'info'; count: number; samples?: string[]; field?: string; pct?: number; }
interface Rule { code?: string; description: string; }
interface RuleEvaluated { code: string; count: number; fired: boolean; }
interface AnomalyRow { row_index: number; columns: string[]; suggestion: string; }
interface DimEntry { score: number; max: number; }

/* 7-dimension quality breakdown labels (bilingual). Keys + order match the
   backend rubric in eda/quality.py and export/charts.py. */
const DIM_LABELS: Record<string, { en: string; bm: string }> = {
  field_coverage:   { en: 'Field Coverage',        bm: 'Liputan Medan' },
  ic_validity:      { en: 'IC Validity',           bm: 'Kesahihan IC' },
  missing_critical: { en: 'Critical Completeness', bm: 'Kelengkapan Kritikal' },
  duplicates:       { en: 'Uniqueness',            bm: 'Keunikan' },
  bmi_consistency:  { en: 'BMI Consistency',       bm: 'Konsistensi BMI' },
  spelling:         { en: 'Spelling',              bm: 'Ejaan' },
  zscore_coverage:  { en: 'Z-score Coverage',      bm: 'Liputan Z-skor' },
};
const DIM_ORDER = Object.keys(DIM_LABELS);

/* Diverging colour for the BMI-status donut so deficiency (coral) and excess
   (gold) are distinguishable instead of both collapsing to the same coral the
   3-bucket default produces. Reuses existing tokens only. */
const bmiStatusColor = (label: string): string => {
  const l = label.toLowerCase();
  if (/normal|baik|healthy/.test(l)) return 'var(--status-good)';
  if (/obes|over|lebih|gemuk/.test(l)) return 'var(--chart-4)';
  if (/under|kurang|susut|thin|wast/.test(l)) return 'var(--status-critical)';
  return 'var(--status-neutral)';
};

function ScoreGauge({ score }: { score: number }) {
  const rag = scoreToRag(score);
  // WS7: gauge arc is a status grade (matches the RagBadge shown for the same
  // score) → dataviz status family, not the alert family.
  const color = rag === 'good' ? 'var(--status-good)' : rag === 'warning' ? 'var(--status-watch)' : 'var(--status-critical)';
  const r = 54, circ = 2 * Math.PI * r;
  const dash = (score / 100) * circ;
  return (
    <svg width={140} height={140} viewBox="0 0 140 140">
      <circle cx={70} cy={70} r={r} fill="none" stroke="var(--border)" strokeWidth={12} />
      <circle cx={70} cy={70} r={r} fill="none" stroke={color} strokeWidth={12}
        strokeDasharray={`${dash} ${circ}`} strokeLinecap="round"
        transform="rotate(-90 70 70)" style={{ transition: 'stroke-dasharray 0.8s ease' }} />
      <text x={70} y={70} textAnchor="middle" fontSize={32} fontWeight={600} fill="var(--text-primary)" fontFamily="var(--font-body)">
        {score.toFixed(0)}
      </text>
      <text x={70} y={88} textAnchor="middle" fontSize={11} fill="var(--text-muted)" fontFamily="var(--font-body)">
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
  const [anomalyError, setAnomalyError] = useState(false);
  const [expanded, setExpanded] = useState<number | null>(null);

  const score = qualityScore ?? 0;
  const stats = cleanStats as Record<string, unknown> | null;
  const _isDistrib = (code?: string | null) =>
    !!code && (code.startsWith('ind_') || code.startsWith('gender_'));

  const issues: Issue[] = ((stats?.top_issues as Issue[]) ?? [])
    .filter(i => !_isDistrib(i.code));
  // `rules_evaluated` is the full check set (fired + passed) from fresh runs.
  // Fall back to the fired-only `rules` for older cached sessions.
  const rulesEvaluated: RuleEvaluated[] | null = Array.isArray(stats?.rules_evaluated)
    ? (stats!.rules_evaluated as RuleEvaluated[])
    : null;
  const rulesApplied: Rule[] = (Array.isArray(stats?.rules)
    ? (stats!.rules as Rule[])
    : ((stats?.rules_applied as string[]) ?? []).map((d): Rule => ({ description: d }))
  ).filter(r => !_isDistrib(r.code));

  const [previewRows, setPreviewRows] = useState<Record<string, unknown>[]>([]);
  /* Classification breakdown — fetched from the same /charts/blocks
     endpoint Geo uses. Lazy + tolerant of missing columns: if the dataset
     has no WHO z-score classes, the donuts simply render nothing. */
  const [blocks, setBlocks] = useState<Record<string, unknown> | null>(null);
  /* 7-dimension breakdown — fetched by cache_id so it resolves for reopened
     sessions too (the score-only /clean/run response doesn't carry it). */
  const [breakdown, setBreakdown] = useState<Record<string, DimEntry> | null>(null);

  useEffect(() => {
    if (!cacheId) return;
    let cancelled = false;
    api.get(`/clean/preview-cached/${cacheId}`)
      .then(r => { if (!cancelled) setPreviewRows(Array.isArray(r.data?.rows) ? r.data.rows : []); })
      .catch(() => { if (!cancelled) setPreviewRows([]); });
    api.get<Record<string, unknown>>(`/charts/blocks?cache_id=${cacheId}`)
      .then(r => { if (!cancelled) setBlocks(r.data); })
      .catch(() => { if (!cancelled) setBlocks(null); });
    api.get<{ breakdown?: Record<string, DimEntry> }>(`/quality/breakdown?cache_id=${cacheId}`)
      .then(r => { if (!cancelled) setBreakdown(r.data?.breakdown ?? null); })
      .catch(() => { if (!cancelled) setBreakdown(null); });
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
    setAnomalyLoading(true); setAnomalyError(false);
    try {
      const r = await api.post<{ anomalies: AnomalyRow[] }>(`/ml/suggest?cache_id=${cacheId}`);
      setAnomalies(r.data.anomalies ?? []);
    } catch { setAnomalies(null); setAnomalyError(true); }
    finally { setAnomalyLoading(false); }
  };

  const sevIcon = (sev: string) => {
    if (sev === 'critical') return <AlertCircle size={15} style={{ color: 'var(--danger)', flexShrink: 0 }} />;
    if (sev === 'warning')  return <AlertTriangle size={15} style={{ color: 'var(--warning)', flexShrink: 0 }} />;
    return <Info size={15} style={{ color: 'var(--brand-sky)', flexShrink: 0 }} />;
  };

  return (
    <SessionGuard>
      <div className="quality-layout" style={{ display: 'flex', gap: 24, alignItems: 'flex-start' }}>

        {/* Left: score gauge */}
        <div className="quality-left-col" style={{
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
                  <span style={{ fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>{row.value}</span>
                </div>
              ))}
            </div>
          )}

          {/* Quality by dimension — fills the left-column void with the real
              reason behind the score (audit 08). Bar length conveys strength;
              the score/max text means colour is never the sole signal. */}
          {breakdown && DIM_ORDER.some(k => breakdown[k]) && (
            <div style={{ width: '100%', marginTop: 4 }}>
              <div className="kkm-keyline" style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.07em', textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: 16 }}>
                {t('Quality by dimension', 'Kualiti mengikut dimensi')}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 11 }}>
                {DIM_ORDER.map(key => {
                  const d = breakdown[key];
                  if (!d || typeof d.score !== 'number' || !d.max) return null;
                  const pct = Math.max(0, Math.min(100, Math.round((d.score / d.max) * 100)));
                  const lab = DIM_LABELS[key];
                  return (
                    <div key={key}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 8, marginBottom: 4 }}>
                        <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{lang === 'en' ? lab.en : lab.bm}</span>
                        <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>{d.score}/{d.max}</span>
                      </div>
                      <div style={{ height: 6, background: 'var(--surface-3)', borderRadius: 3, overflow: 'hidden' }} aria-hidden>
                        <div style={{ width: `${pct}%`, height: '100%', background: 'var(--chart-6)', borderRadius: 3 }} />
                      </div>
                    </div>
                  );
                })}
              </div>
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
              <InlineEmpty icon={<ShieldCheck size={26} />} text={t('No issues detected — this dataset looks clean.', 'Tiada isu dikesan — dataset ini kelihatan bersih.')} />
            ) : issues.map((issue, i) => (
              <div key={i} style={{ borderBottom: i < issues.length - 1 ? '1px solid var(--border)' : 'none' }}>
                <div
                  style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px 20px', cursor: issue.samples?.length ? 'pointer' : 'default' }}
                  onClick={() => setExpanded(expanded === i ? null : i)}
                >
                  {sevIcon(issue.severity)}
                  <span style={{ flex: 1, fontSize: 13, color: 'var(--text-primary)' }}>{translateIssue(issue, lang)}</span>
                  <span style={{ fontSize: 12, fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                    {Number(issue.count).toLocaleString()}
                  </span>
                  {issue.samples?.length ? (expanded === i ? <ChevronUp size={14} /> : <ChevronDown size={14} />) : null}
                </div>
                {expanded === i && issue.samples && (
                  <div style={{ padding: '0 20px 12px 44px', fontSize: 12, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                    {issue.samples.join(', ')}
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Rules applied — prefer the full evaluated set (fired + passed);
              fall back to fired-only for older cached sessions */}
          {(rulesEvaluated ?? rulesApplied).length > 0 && (
            <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-card)', padding: '18px 20px', boxShadow: 'var(--shadow-card)' }}>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>
                {t('Rules Applied', 'Peraturan Digunakan')}
              </div>
              {rulesEvaluated && (
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 12 }}>
                  {t('All checks evaluated — dimmed rules found no issues.', 'Semua semakan dinilai — peraturan redup tiada isu ditemui.')}
                </div>
              )}
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {rulesEvaluated
                  ? [...rulesEvaluated]
                    // Active (fired) rules first so they sit next to the Issues
                    // Detected list; within each group, higher counts lead. Passed
                    // checks drop to the end as dimmed pills.
                    .sort((a, b) => (Number(b.fired) - Number(a.fired)) || (b.count - a.count))
                    .map((r) => (
                    <span key={r.code} style={{
                      fontSize: 12,
                      background: r.fired ? 'var(--surface-2)' : 'transparent',
                      border: `1px solid ${r.fired ? 'var(--border)' : 'var(--border)'}`,
                      borderRadius: 999,
                      padding: '4px 12px',
                      color: r.fired ? 'var(--text-secondary)' : 'var(--text-muted)',
                      opacity: r.fired ? 1 : 0.55,
                    }}>
                      {translateRule(r, lang)}
                      {!r.fired && (
                        <span style={{ marginLeft: 5, fontSize: 10, color: 'var(--text-muted)' }}>✓</span>
                      )}
                    </span>
                  ))
                  : rulesApplied.map((r, i) => (
                    <span key={r.code ?? r.description ?? i} style={{ fontSize: 12, background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 999, padding: '4px 12px', color: 'var(--text-secondary)' }}>
                      {translateRule(r, lang)}
                    </span>
                  ))
                }
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
                  style={{ background: 'var(--brand-blue)', color: '#fff', border: 'none', borderRadius: 'var(--radius-btn)', padding: '8px 16px', fontSize: 13, fontWeight: 600, cursor: 'pointer', opacity: anomalyLoading ? 0.6 : 1 }}
                >
                  {anomalyLoading ? t('Running…', 'Sedang berjalan…') : t('Run Detection', 'Jalankan')}
                </button>
              )}
            </div>

            {anomalyError && (
              <ErrorRetry compact message={t('Anomaly detection failed.', 'Pengesanan anomali gagal.')} onRetry={runAnomalyDetection} />
            )}

            {anomalies !== null && (
              anomalies.length === 0 ? (
                <div style={{ fontSize: 13, color: 'var(--brand-teal)' }}>
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
                        <td style={{ padding: '8px 10px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>{a.row_index}</td>
                        <td style={{ padding: '8px 10px', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>{a.columns.join(', ')}</td>
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

          {/* ── Classification breakdown ─────────────────────────────────────
              WHO z-score classes (WAZ/HAZ/BAZ) are ordinal severity scales, so
              they render as one stacked-bar card with a shared severity key
              (C1 — same-coloured pie slices were unreadable). The BMI status
              split stays a donut but with a diverging colour map so deficiency
              and excess don't both read coral. Hidden when the dataset has none
              of these columns. Lives inside the right column (not a stray third
              flex column) so it flows full-width beneath the cards above. */}
          {blocks && catalogByHome('quality').some(e => e.key in blocks) && (() => {
            const classBars = catalogByHome('quality')
              .filter(e => e.shape === 'donut_object' && isDonutObjectBlock(blocks[e.key]))
              .map(e => {
                const b = blocks[e.key] as { label: string; data: { label: string; count: number }[] };
                return { key: e.key, titleEn: e.titleEn, titleBm: e.titleBm, data: b.data };
              });
            const bmiEntry = catalogByHome('quality')
              .find(e => e.shape === 'pie_array' && isPieArrayBlock(blocks[e.key]));
            return (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                <div style={{ fontSize: 13, fontWeight: 600 }}>
                  {t('Classification breakdown', 'Pecahan klasifikasi')}
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 14, alignItems: 'start' }}>
                  {classBars.length > 0 && (
                    <StatusClassBars
                      title={t('WHO nutrition status (WAZ / HAZ / BAZ)', 'Status pemakanan WHO (WAZ / HAZ / BAZ)')}
                      bars={classBars}
                      lang={lang}
                    />
                  )}
                  {bmiEntry && (
                    <DonutCard
                      title={lang === 'en' ? bmiEntry.titleEn : bmiEntry.titleBm}
                      data={blocks[bmiEntry.key] as { label: string; count: number }[]}
                      colorFor={bmiStatusColor}
                    />
                  )}
                </div>
              </div>
            );
          })()}
        </div>
      </div>
    </SessionGuard>
  );
}
