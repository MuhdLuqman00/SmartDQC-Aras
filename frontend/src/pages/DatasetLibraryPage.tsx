import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BookOpen, GitMerge } from 'lucide-react';
import { api } from '../api/client';
import { useLang } from '../context/LanguageContext';
import { useSession } from '../context/SessionContext';
import { RagBadge, scoreToRag } from '../components/RagBadge';
import { EmptyState } from '../components/EmptyState';
import { JoinWizardModal } from '../components/JoinWizardModal';
import { formatMytDateTime, formatMytDate } from '../lib/formatMyt';

interface Dataset {
  id: string;
  name?: string;
  filename: string;
  source_type: string | null;
  row_count: number | null;
  quality_score: number | null;
  created_at: string;
}

export function DatasetLibraryPage() {
  const { t, lang } = useLang();
  const { setSession } = useSession();
  const nav = useNavigate();
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [comparing, setComparing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [comparison, setComparison] = useState<Record<string, unknown> | null>(null);
  const [compareError, setCompareError] = useState<string | null>(null);
  const [joinOpen, setJoinOpen] = useState(false);

  useEffect(() => {
    api.get<Dataset[]>('/datasets')
      .then(r => setDatasets(r.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const toggleSelect = (id: string) => setSelected(prev => {
    const next = new Set(prev);
    next.has(id) ? next.delete(id) : next.add(id);
    return next;
  });

  const handleCompare = async () => {
    if (selected.size < 2) return;
    setComparing(true);
    setCompareError(null);
    try {
      const r = await api.post('/datasets/compare', { dataset_ids: Array.from(selected) });
      setComparison(r.data);
    } catch {
      // Previously there was no catch, so any backend failure was swallowed
      // and the modal silently never opened. Surface it instead.
      setCompareError(t('Comparison failed. Please try again.', 'Perbandingan gagal. Sila cuba lagi.'));
    } finally { setComparing(false); }
  };

  const handleDelete = async () => {
    if (selected.size < 1) return;
    const ids = Array.from(selected);
    if (!window.confirm(
      t(`Delete ${ids.length} dataset(s)? This cannot be undone.`,
        `Padam ${ids.length} dataset? Tindakan ini tidak boleh dibatalkan.`))) return;
    setDeleting(true);
    try {
      await api.post('/datasets/delete', { dataset_ids: ids });
      const r = await api.get<Dataset[]>('/datasets');
      setDatasets(r.data);
      setSelected(new Set());
    } catch {
      window.alert(t('Delete failed.', 'Padam gagal.'));
    } finally { setDeleting(false); }
  };

  if (loading) return <div style={{ color: 'var(--text-muted)', padding: 40 }}>{t('Loading…', 'Memuatkan…')}</div>;
  if (!datasets.length) return (
    <EmptyState icon={<BookOpen size={48} />} title={t('No datasets yet', 'Tiada dataset lagi')}
      description={t('Upload and clean a dataset to save it here.', 'Muat naik dan bersihkan dataset untuk menyimpannya di sini.')}
      action={{ label: t('Upload Dataset', 'Muat Naik Dataset'), to: '/upload' }} />
  );

  return (
    <div>
      {selected.size >= 1 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20, background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 10, padding: '12px 16px' }}>
          <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{selected.size} {t('selected', 'dipilih')}</span>
          {selected.size >= 2 && (
            <button onClick={handleCompare} disabled={comparing}
              style={{ background: 'var(--brand-blue)', color: '#fff', border: 'none', borderRadius: 6, padding: '7px 16px', fontWeight: 600, fontSize: 13, cursor: 'pointer', opacity: comparing ? 0.6 : 1 }}>
              {comparing ? t('Comparing…', 'Sedang membandingkan…') : t('Compare', 'Bandingkan')}
            </button>
          )}
          {selected.size === 2 && (
            <button onClick={() => setJoinOpen(true)}
              style={{ background: 'var(--brand-teal)', color: '#fff', border: 'none', borderRadius: 6, padding: '7px 16px', fontWeight: 600, fontSize: 13, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}>
              <GitMerge size={14} /> {t('Join', 'Cantum')}
            </button>
          )}
          <button onClick={handleDelete} disabled={deleting}
            style={{ background: 'transparent', color: 'var(--danger)', border: '1px solid var(--danger)', borderRadius: 6, padding: '7px 16px', fontWeight: 600, fontSize: 13, cursor: 'pointer', opacity: deleting ? 0.6 : 1 }}>
            {deleting ? t('Deleting…', 'Sedang memadam…') : t('Delete selected', 'Padam dipilih')}
          </button>
          <button onClick={() => setSelected(new Set())} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: 13 }}>
            {t('Clear', 'Batal')}
          </button>
        </div>
      )}

      {compareError && (
        <div role="alert" style={{ marginBottom: 20, background: 'var(--danger-bg)', border: '1px solid var(--danger)', borderRadius: 8, padding: '10px 14px', fontSize: 13, color: 'var(--danger)' }}>
          {compareError}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 18 }}>
        {datasets.map(ds => {
          const isSelected = selected.has(ds.id);
          return (
            <div key={ds.id} style={{
              background: 'var(--surface)', border: `1px solid ${isSelected ? 'var(--brand-sky)' : 'var(--border)'}`,
              borderRadius: 'var(--radius-card)', padding: '18px 20px',
              boxShadow: 'var(--shadow-card)', cursor: 'pointer',
              transition: 'border-color var(--transition)',
            }}
              onClick={() => toggleSelect(ds.id)}
            >
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 10 }}>
                <input type="checkbox" checked={isSelected} readOnly style={{ marginTop: 2 }} />
                {ds.source_type && (
                  <span style={{ fontSize: 10, fontWeight: 600, background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 999, padding: '2px 8px', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>
                    {ds.source_type}
                  </span>
                )}
              </div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 4 }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', wordBreak: 'break-all', flex: 1, minWidth: 0 }}>{ds.name || ds.filename}</div>
                {/* Short stable id — datasets often share a filename; the id is
                    the only guaranteed-unique distinguisher. */}
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)', flexShrink: 0 }}>
                  #{ds.id.slice(0, 6)}
                </span>
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 10 }}>
                {ds.row_count?.toLocaleString() ?? '—'} {t('rows', 'baris')} · {formatMytDateTime(ds.created_at, lang)}
              </div>
              {ds.quality_score != null && <RagBadge rag={scoreToRag(ds.quality_score)} lang={lang} />}
              <div style={{ marginTop: 14 }}>
                <button
                  onClick={e => {
                    e.stopPropagation();
                    setSession({ cacheId: ds.id, filename: ds.name || ds.filename, sourceType: ds.source_type });
                    nav('/');
                  }}
                  style={{ background: 'var(--brand-blue)', color: '#fff', border: 'none', borderRadius: 6, padding: '6px 14px', fontSize: 12, fontWeight: 600, cursor: 'pointer' }}
                >
                  {t('Load Session', 'Muat Sesi')}
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Comparison modal */}
      {comparison && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
          onClick={() => setComparison(null)}>
          <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 12, padding: 32, maxWidth: 700, width: '90%', maxHeight: '80vh', overflowY: 'auto' }}
            onClick={e => e.stopPropagation()}>
            <h3 style={{ fontFamily: 'var(--font-body)', fontSize: 16, fontWeight: 700, marginBottom: 16 }}>
              {t('Comparison Results', 'Hasil Perbandingan')}
            </h3>
            {(() => {
              const c = comparison as unknown as {
                datasets: Array<{ dataset_id: string; name?: string; source_type?: string | null; quality_score?: number | null; indicators?: Record<string, number | null>; created_at?: string }>;
                deltas: Record<string, number | null>;
                trend: Record<string, string>;
              };
              const METRICS: Array<[string, string]> = [
                ['quality_score', t('Quality Score', 'Skor Kualiti')],
                ['stunting_rate', 'Stunting'],
                ['wasting_rate', 'Wasting'],
                ['underweight_rate', 'Underweight'],
                ['overweight_rate', 'Overweight'],
              ];
              const cell: React.CSSProperties = { padding: '6px 10px', borderBottom: '1px solid var(--border)', fontSize: 12, textAlign: 'left' };
              const num = (m: string, ds: typeof c.datasets[number]) =>
                m === 'quality_score'
                  ? (ds.quality_score == null ? '—' : Number(ds.quality_score).toFixed(1))
                  : (ds.indicators?.[m] == null ? '—' : `${(Number(ds.indicators[m]) * 100).toFixed(1)}%`);
              // WS7: a worsening metric/trend is a "bad-but-not-broken" status
              // signal, not an error — red stays reserved for errors/destructive,
              // so the negative side uses --warning (accessible as text).
              const deltaColor = (m: string, v: number | null) => {
                if (v == null || v === 0) return 'var(--text-muted)';
                const good = m === 'quality_score' ? v > 0 : v < 0;
                return good ? 'var(--brand-teal)' : 'var(--warning)';
              };
              const trendColor = (tr?: string) =>
                tr === 'improving' ? 'var(--brand-teal)' : tr === 'worsening' ? 'var(--warning)' : 'var(--text-muted)';
              const trendLabel = (tr?: string) =>
                tr === 'improving' ? t('Improving', 'Bertambah baik')
                  : tr === 'worsening' ? t('Worsening', 'Bertambah buruk')
                  : tr === 'stable' ? t('Stable', 'Stabil')
                  : (tr ?? '—');
              return (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
                  <table style={{ borderCollapse: 'collapse', width: '100%' }}>
                    <thead><tr>
                      <th style={{ ...cell, fontWeight: 700 }}>{t('Dataset', 'Dataset')}</th>
                      {METRICS.map(([k, lbl]) => <th key={k} style={{ ...cell, fontWeight: 700 }}>{lbl}</th>)}
                    </tr></thead>
                    <tbody>
                      {c.datasets.map((ds, i) => (
                        <tr key={ds.dataset_id ?? i}>
                          <td style={cell}>{ds.name || ds.dataset_id}<div style={{ color: 'var(--text-muted)', fontSize: 11 }}>{formatMytDate(ds.created_at, lang)}</div></td>
                          {METRICS.map(([k]) => <td key={k} style={cell}>{num(k, ds)}</td>)}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 700, marginBottom: 6 }}>
                      {t('Change (latest vs earliest)', 'Perubahan (terkini lwn terawal)')}
                    </div>
                    <table style={{ borderCollapse: 'collapse', width: '100%' }}>
                      <thead><tr>
                        <th style={{ ...cell, fontWeight: 700 }}>{t('Metric', 'Metrik')}</th>
                        <th style={{ ...cell, fontWeight: 700 }}>{t('Delta', 'Delta')}</th>
                        <th style={{ ...cell, fontWeight: 700 }}>{t('Trend', 'Trend')}</th>
                      </tr></thead>
                      <tbody>
                        {METRICS.map(([k, lbl]) => {
                          const d = c.deltas?.[k] ?? null;
                          const unit = k === 'quality_score' ? ' pts' : ' pp';
                          return (
                            <tr key={k}>
                              <td style={cell}>{lbl}</td>
                              <td style={{ ...cell, color: deltaColor(k, d), fontWeight: 600 }}>
                                {d == null ? '—' : `${d > 0 ? '+' : ''}${d}${unit}`}
                              </td>
                              <td style={{ ...cell, color: trendColor(c.trend?.[k]) }}>{trendLabel(c.trend?.[k])}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              );
            })()}
            <button onClick={() => setComparison(null)} style={{ marginTop: 16, background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 6, padding: '8px 16px', cursor: 'pointer', fontSize: 13, color: 'var(--text-primary)' }}>
              {t('Close', 'Tutup')}
            </button>
          </div>
        </div>
      )}

      {/* The v1 entity link panel has moved to the dedicated /linkage page
         (admin-only, with fuzzy IC + name/DOB boost + CSV export). */}

      {/* Join wizard modal — opens when exactly 2 datasets are selected. */}
      {joinOpen && selected.size === 2 && (() => {
        const ids = Array.from(selected);
        const left = datasets.find(d => d.id === ids[0]);
        const right = datasets.find(d => d.id === ids[1]);
        if (!left || !right) return null;
        return (
          <JoinWizardModal
            left={{ id: left.id, filename: left.filename, source_type: left.source_type, row_count: left.row_count }}
            right={{ id: right.id, filename: right.filename, source_type: right.source_type, row_count: right.row_count }}
            onClose={() => setJoinOpen(false)}
            onJoined={() => {
              // Refresh the library so the joined dataset appears.
              api.get<Dataset[]>('/datasets').then(r => setDatasets(r.data)).catch(console.error);
              setSelected(new Set());
            }}
          />
        );
      })()}
    </div>
  );
}
