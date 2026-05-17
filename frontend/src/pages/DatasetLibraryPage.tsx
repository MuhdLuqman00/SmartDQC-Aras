import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BookOpen } from 'lucide-react';
import { api } from '../api/client';
import { useLang } from '../context/LanguageContext';
import { useSession } from '../context/SessionContext';
import { RagBadge, scoreToRag } from '../components/RagBadge';
import { EmptyState } from '../components/EmptyState';
import { EntityLinkPanel } from '../components/EntityLinkPanel';

interface Dataset {
  id: string;
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
    try {
      const r = await api.post('/datasets/compare', { dataset_ids: Array.from(selected) });
      setComparison(r.data);
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
              style={{ background: 'var(--kkm-blue)', color: '#fff', border: 'none', borderRadius: 6, padding: '7px 16px', fontWeight: 600, fontSize: 13, cursor: 'pointer', opacity: comparing ? 0.6 : 1 }}>
              {comparing ? t('Comparing…', 'Sedang membandingkan…') : t('Compare', 'Bandingkan')}
            </button>
          )}
          <button onClick={handleDelete} disabled={deleting}
            style={{ background: 'var(--danger)', color: '#fff', border: 'none', borderRadius: 6, padding: '7px 16px', fontWeight: 600, fontSize: 13, cursor: 'pointer', opacity: deleting ? 0.6 : 1 }}>
            {deleting ? t('Deleting…', 'Sedang memadam…') : t('Delete selected', 'Padam dipilih')}
          </button>
          <button onClick={() => setSelected(new Set())} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: 13 }}>
            {t('Clear', 'Batal')}
          </button>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 18 }}>
        {datasets.map(ds => {
          const isSelected = selected.has(ds.id);
          return (
            <div key={ds.id} style={{
              background: 'var(--surface)', border: `1px solid ${isSelected ? 'var(--kkm-sky)' : 'var(--border)'}`,
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
              <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4, wordBreak: 'break-all' }}>{ds.filename}</div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 10 }}>
                {ds.row_count?.toLocaleString() ?? '—'} {t('rows', 'baris')} · {new Date(ds.created_at).toLocaleDateString()}
              </div>
              {ds.quality_score != null && <RagBadge rag={scoreToRag(ds.quality_score)} lang={lang} />}
              <div style={{ marginTop: 14 }}>
                <button
                  onClick={e => {
                    e.stopPropagation();
                    setSession({ cacheId: ds.id, filename: ds.filename, sourceType: ds.source_type });
                    nav('/');
                  }}
                  style={{ background: 'var(--kkm-blue)', color: '#fff', border: 'none', borderRadius: 6, padding: '6px 14px', fontSize: 12, fontWeight: 600, cursor: 'pointer' }}
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
            <h3 style={{ fontFamily: "'Plus Jakarta Sans', sans-serif", fontSize: 16, fontWeight: 700, marginBottom: 16 }}>
              {t('Comparison Results', 'Hasil Perbandingan')}
            </h3>
            <pre style={{ fontSize: 12, color: 'var(--text-secondary)', fontFamily: 'JetBrains Mono, monospace', whiteSpace: 'pre-wrap' }}>
              {JSON.stringify(comparison, null, 2)}
            </pre>
            <button onClick={() => setComparison(null)} style={{ marginTop: 16, background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 6, padding: '8px 16px', cursor: 'pointer', fontSize: 13, color: 'var(--text-primary)' }}>
              {t('Close', 'Tutup')}
            </button>
          </div>
        </div>
      )}

      <EntityLinkPanel datasetIds={Array.from(selected)} />
    </div>
  );
}
