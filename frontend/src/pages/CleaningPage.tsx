import React, { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { useLang } from '../context/LanguageContext';

interface CleanAction {
  action_type: string;
  count: number;
  detail?: string;
}

interface CleanResponse {
  cache_id: string;
  rows_before: number;
  rows_after: number;
  actions_taken: CleanAction[];
  quality_score: number;
}

function qColor(score: number): string {
  if (score >= 80) return 'var(--success)';
  if (score >= 60) return 'var(--warning)';
  return 'var(--danger)';
}

function qBg(score: number): string {
  if (score >= 80) return 'var(--success-bg)';
  if (score >= 60) return 'var(--warning-bg)';
  return 'var(--danger-bg)';
}

export function CleaningPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { t } = useLang();
  const cacheId = searchParams.get('cache_id') ?? '';

  const ACTION_LABELS: Record<string, string> = {
    missing_imputed:     t('Missing values imputed (median)', 'Nilai hilang diimputasi (median)'),
    duplicate_removed:   t('Duplicate rows removed', 'Baris berganda dibuang'),
    outlier_flagged:     t('Outliers flagged (Z-score > 3)', 'Outlier dibenderakan (Z-score > 3)'),
    ic_corrected:        t('IC numbers normalised', 'Nombor IC dinormalkan'),
    decimal_shift_fixed: t('Decimal shift corrected (×10)', 'Anjakan perpuluhan diperbetulkan (×10)'),
  };

  const [result, setResult] = useState<CleanResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [openActions, setOpenActions] = useState<Set<string>>(new Set());

  const runClean = async (cid: string): Promise<void> => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.post<CleanResponse>('/clean/run', { cache_id: cid });
      setResult(res.data);
    } catch {
      setError(t('Failed to run cleaning.', 'Gagal menjalankan pembersihan.'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!cacheId) return;
    runClean(cacheId);
  }, [cacheId]);

  const toggleAction = (key: string): void => {
    setOpenActions(prev => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const downloadFile = async (url: string, filename: string): Promise<void> => {
    const res = await api.get(url, { responseType: 'blob' });
    const href = URL.createObjectURL(res.data as Blob);
    const a = document.createElement('a');
    a.href = href;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(href);
  };

  // Empty state
  if (!cacheId) {
    return (
      <div style={s.centerMsg}>
        {t('Upload a file to start cleaning.', 'Muat naik fail untuk memulakan pembersihan.')}
      </div>
    );
  }

  // Loading state
  if (loading) {
    return (
      <div style={s.centerMsg}>
        {t('Processing cleaning...', 'Memproses pembersihan...')}
      </div>
    );
  }

  return (
    <div style={s.page}>
      <h1 style={s.h1}>{t('Cleaning Results', 'Hasil Pembersihan')}</h1>

      {/* Error banner */}
      {error && (
        <div style={s.errorBanner}>{error}</div>
      )}

      {result && (
        <>
          {/* Summary card */}
          <div style={s.summaryCard}>
            <div style={s.statsRow}>
              <div style={s.statBlock}>
                <div style={s.statLabel}>{t('Rows Before', 'Baris Sebelum')}</div>
                <div style={s.statValue}>{result.rows_before.toLocaleString()}</div>
              </div>

              <div style={s.statDivider}>→</div>

              <div style={s.statBlock}>
                <div style={s.statLabel}>{t('Rows After', 'Baris Selepas')}</div>
                <div style={s.statValue}>{result.rows_after.toLocaleString()}</div>
              </div>

              {result.rows_before - result.rows_after > 0 && (
                <div style={s.deltaBadge}>
                  −{(result.rows_before - result.rows_after).toLocaleString()} {t('removed', 'dibuang')}
                </div>
              )}

              <div style={s.statDivider}>·</div>

              {/* Quality score */}
              <div style={{ ...s.statBlock, ...s.qualityBlock, background: qBg(result.quality_score) }}>
                <div style={s.statLabel}>{t('Quality Score', 'Skor Kualiti')}</div>
                <div style={{ ...s.statValue, color: qColor(result.quality_score) }}>
                  {result.quality_score.toFixed(1)}%
                </div>
              </div>
            </div>
          </div>

          {/* Actions accordion */}
          <div style={s.card}>
            <div style={s.cardHeader}>
              Tindakan Pembersihan ({result.actions_taken.length})
            </div>

            {result.actions_taken.length === 0 && (
              <div style={s.noActions}>Tiada tindakan — data bersih!</div>
            )}

            {result.actions_taken.map((action, idx) => {
              const key = `${action.action_type}-${idx}`;
              const isOpen = openActions.has(key);
              const label = ACTION_LABELS[action.action_type] ?? action.action_type;

              return (
                <div key={key}>
                  <button
                    style={s.accordionHeader}
                    onClick={() => toggleAction(key)}
                  >
                    <span style={s.actionLabel}>{label}</span>
                    <span style={s.countBadge}>{action.count} rekod</span>
                    <span style={s.caret}>{isOpen ? '▲' : '▼'}</span>
                  </button>

                  {isOpen && action.detail && (
                    <div style={s.accordionBody}>
                      <span style={s.detailText}>{action.detail}</span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Bottom buttons */}
          <div style={s.buttonRow}>
            <button
              style={s.btnPrimary}
              onClick={() =>
                downloadFile(
                  `/clean/download-cached/${result.cache_id}`,
                  `SmartDQC_${result.cache_id.slice(0, 8)}.csv`,
                )
              }
            >
              Muat Turun CSV
            </button>

            <button
              style={s.btnSecondary}
              onClick={() =>
                downloadFile(
                  `/clean/download-report/${result.cache_id}`,
                  `SmartDQC_Report_${result.cache_id.slice(0, 8)}.xlsx`,
                )
              }
            >
              Muat Turun Laporan Excel
            </button>

            <button
              style={s.btnAccent}
              onClick={() => navigate('/reports')}
            >
              Teruskan ke Laporan
            </button>
          </div>
        </>
      )}
    </div>
  );
}

const s: Record<string, React.CSSProperties> = {
  page: {
    padding: '24px 0',
  },
  h1: {
    margin: '0 0 20px',
    fontSize: 22,
    fontWeight: 700,
    color: 'var(--text-primary)',
  },
  centerMsg: {
    fontSize: 14,
    color: 'var(--text-muted)',
    padding: '40px 0',
    textAlign: 'center',
  },
  errorBanner: {
    background: 'var(--danger-bg)',
    color: 'var(--danger)',
    border: '0.5px solid var(--danger)',
    borderRadius: 8,
    padding: '12px 16px',
    fontSize: 14,
    marginBottom: 20,
  },
  summaryCard: {
    background: 'var(--surface)',
    border: '0.5px solid var(--border)',
    borderRadius: 12,
    padding: 24,
    marginBottom: 20,
  },
  statsRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 20,
    flexWrap: 'wrap',
  },
  statBlock: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 4,
    minWidth: 100,
  },
  statLabel: {
    fontSize: 11,
    fontWeight: 600,
    color: 'var(--text-secondary)',
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
  },
  statValue: {
    fontSize: 32,
    fontWeight: 700,
    color: 'var(--text-primary)',
    letterSpacing: '-0.02em',
  },
  statDivider: {
    fontSize: 20,
    color: 'var(--text-muted)',
  },
  deltaBadge: {
    background: 'var(--danger-bg)',
    color: 'var(--danger)',
    fontSize: 12,
    fontWeight: 600,
    padding: '4px 12px',
    borderRadius: 20,
    border: '0.5px solid var(--danger)',
  },
  qualityBlock: {
    borderRadius: 8,
    padding: '8px 16px',
  },
  card: {
    background: 'var(--surface)',
    border: '0.5px solid var(--border)',
    borderRadius: 12,
    marginBottom: 20,
    overflow: 'hidden',
  },
  cardHeader: {
    fontSize: 11,
    fontWeight: 600,
    color: 'var(--text-secondary)',
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
    padding: '14px 20px',
    borderBottom: '0.5px solid var(--border)',
    background: 'var(--surface-2)',
  },
  noActions: {
    padding: 20,
    fontSize: 13,
    color: 'var(--success)',
    textAlign: 'center',
  },
  accordionHeader: {
    width: '100%',
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    padding: '14px 20px',
    background: 'none',
    border: 'none',
    borderBottom: '0.5px solid var(--border)',
    fontSize: 14,
    color: 'var(--text-primary)',
    cursor: 'pointer',
    textAlign: 'left',
    transition: 'all 0.15s ease',
  },
  actionLabel: {
    flex: 1,
    fontSize: 14,
    color: 'var(--text-primary)',
  },
  countBadge: {
    fontSize: 12,
    fontWeight: 600,
    color: 'var(--blue)',
    background: 'var(--surface-2)',
    padding: '2px 10px',
    borderRadius: 10,
    border: '0.5px solid var(--border)',
  },
  caret: {
    fontSize: 10,
    color: 'var(--text-muted)',
  },
  accordionBody: {
    background: 'var(--bg)',
    padding: '12px 20px',
    borderBottom: '0.5px solid var(--border)',
  },
  detailText: {
    fontSize: 12,
    color: 'var(--text-secondary)',
    fontFamily: 'monospace',
  },
  buttonRow: {
    display: 'flex',
    gap: 12,
    flexWrap: 'wrap',
  },
  btnPrimary: {
    flex: 1,
    padding: '12px 20px',
    background: 'var(--navy)',
    color: '#fff',
    border: '0.5px solid var(--navy)',
    borderRadius: 8,
    fontSize: 14,
    fontWeight: 600,
    cursor: 'pointer',
    transition: 'all 0.15s ease',
    minWidth: 160,
  },
  btnSecondary: {
    flex: 1,
    padding: '12px 20px',
    background: 'var(--surface)',
    color: 'var(--blue)',
    border: '0.5px solid var(--blue)',
    borderRadius: 8,
    fontSize: 14,
    fontWeight: 600,
    cursor: 'pointer',
    transition: 'all 0.15s ease',
    minWidth: 160,
  },
  btnAccent: {
    flex: 1,
    padding: '12px 20px',
    background: 'var(--blue)',
    color: '#fff',
    border: '0.5px solid var(--blue)',
    borderRadius: 8,
    fontSize: 14,
    fontWeight: 600,
    cursor: 'pointer',
    transition: 'all 0.15s ease',
    minWidth: 160,
  },
};
