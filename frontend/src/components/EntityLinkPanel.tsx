import React, { useState } from 'react';
import { Link2 } from 'lucide-react';
import { api } from '../api/client';
import { useLang } from '../context/LanguageContext';

interface LinkSource { source_type: string; dataset_id: string; name: string; dob: string; }
interface Profile { ic: string; sources: LinkSource[]; }
interface LinkResult {
  total_groups: number;
  linked_groups: number;
  unlinked: number;
  rows_written: number;
  profiles: Profile[];
}

export function EntityLinkPanel({ datasetIds }: { datasetIds: string[] }) {
  const { t } = useLang();
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<LinkResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const canLink = datasetIds.length >= 2;

  const runLink = async () => {
    if (!canLink) return;
    setLoading(true);
    setError(null);
    try {
      const r = await api.post<LinkResult>('/entity/link', { dataset_ids: datasetIds });
      setResult(r.data);
    } catch (e: any) {
      setError(e?.response?.data?.detail || t('Linking failed.', 'Pemautan gagal.'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ marginTop: 24, background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-card)', padding: '18px 20px', boxShadow: 'var(--shadow-card)' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: result ? 16 : 0 }}>
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}>
            <Link2 size={15} /> {t('Cross-Dataset Record Linking', 'Pemautan Rekod Merentas Dataset')}
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
            {t('Link the same child across selected datasets by IC.',
               'Pautkan kanak-kanak yang sama merentas dataset terpilih melalui IC.')}
          </div>
        </div>
        <button
          onClick={runLink}
          disabled={!canLink || loading}
          style={{ background: 'var(--brand-blue)', color: '#fff', border: 'none', borderRadius: 'var(--radius-btn)', padding: '8px 16px', fontSize: 13, fontWeight: 600, cursor: canLink ? 'pointer' : 'not-allowed', opacity: !canLink || loading ? 0.6 : 1 }}
        >
          {loading ? t('Linking…', 'Memaut…') : t('Link Records', 'Paut Rekod')}
        </button>
      </div>

      {!canLink && (
        <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 8 }}>
          {t('Select at least 2 datasets above.', 'Pilih sekurang-kurangnya 2 dataset di atas.')}
        </div>
      )}

      {error && (
        <div style={{ fontSize: 13, color: 'var(--danger)', marginTop: 12 }}>{error}</div>
      )}

      {result && (
        <>
          <div style={{ display: 'flex', gap: 20, marginBottom: 16, fontSize: 13 }}>
            {[
              [t('Total groups', 'Jumlah kumpulan'), result.total_groups],
              [t('Linked', 'Terpaut'), result.linked_groups],
              [t('Unlinked', 'Tidak terpaut'), result.unlinked],
              [t('Rows written', 'Baris ditulis'), result.rows_written],
            ].map(([label, val]) => (
              <div key={String(label)}>
                <div style={{ color: 'var(--text-muted)', fontSize: 11 }}>{label}</div>
                <div style={{ fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{val}</div>
              </div>
            ))}
          </div>

          {result.profiles.length === 0 ? (
            <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>
              {t('No cross-dataset matches found.', 'Tiada padanan merentas dataset dijumpai.')}
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {result.profiles.map((p, i) => (
                <div key={i} style={{ border: '1px solid var(--border)', borderRadius: 8, padding: '10px 14px' }}>
                  <div style={{ fontWeight: 600, fontSize: 13, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', marginBottom: 6 }}>
                    {p.ic || t('(no IC)', '(tiada IC)')}
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                    {p.sources.map((s, j) => (
                      <span key={j} style={{ fontSize: 11, background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 999, padding: '3px 10px', color: 'var(--text-secondary)' }}>
                        {s.source_type}: {s.name || '—'} {s.dob ? `· ${s.dob}` : ''}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
