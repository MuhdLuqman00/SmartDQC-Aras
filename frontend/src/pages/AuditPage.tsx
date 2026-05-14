import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { useLang } from '../context/LanguageContext';

interface AuditEntry {
  id: number; action: string; dataset_id?: number;
  detail: string; user_id?: number; created_at: string;
}

type ActionCategory = 'upload' | 'clean' | 'report' | 'other';

function actionCategory(action: string): ActionCategory {
  if (action.startsWith('upload')) return 'upload';
  if (action.startsWith('clean'))  return 'clean';
  if (action.startsWith('report')) return 'report';
  return 'other';
}

const catColor: Record<ActionCategory, string> = {
  upload: 'var(--info-bg)',
  clean:  'var(--success-bg)',
  report: 'var(--purple-bg)',
  other:  'var(--surface-2)',
};

const catTextColor: Record<ActionCategory, string> = {
  upload: 'var(--info)',
  clean:  'var(--success)',
  report: 'var(--purple)',
  other:  'var(--text-muted)',
};

export function AuditPage() {
  const { t } = useLang();
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [datasetFilter, setDatasetFilter] = useState<string>('');
  const [actionFilter, setActionFilter] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    api.get<AuditEntry[]>('/audit/log', { params: { limit: 100 } })
      .then(r => setEntries(r.data || []))
      .catch(() => {
        setError(t('Failed to load audit log.', 'Gagal memuat log audit.'));
        setEntries([]);
      })
      .finally(() => setLoading(false));
  }, []);

  const filtered = entries.filter(e => {
    const matchDs = !datasetFilter || String(e.dataset_id) === datasetFilter;
    const matchAct = !actionFilter || actionCategory(e.action) === actionFilter;
    return matchDs && matchAct;
  });

  function truncateDetail(detail: string, maxLen: number = 80): string {
    return detail.length > maxLen ? detail.slice(0, maxLen) + '…' : detail;
  }

  function formatMasa(iso: string): string {
    try {
      return new Date(iso).toLocaleString('ms-MY');
    } catch { return iso; }
  }

  return (
    <div>
      <h1 style={pg.h1}>{t('Audit Log', 'Log Audit')}</h1>

      <div style={pg.filterBar}>
        <input
          type="text"
          style={pg.input}
          placeholder={t('Dataset ID', 'ID Dataset')}
          value={datasetFilter}
          onChange={e => setDatasetFilter(e.target.value)}
        />
        <select
          style={pg.select}
          value={actionFilter}
          onChange={e => setActionFilter(e.target.value)}
        >
          <option value="">{t('All Actions', 'Semua Tindakan')}</option>
          <option value="upload">upload</option>
          <option value="clean">clean</option>
          <option value="report">report</option>
          <option value="other">other</option>
        </select>
      </div>

      {error && (
        <div style={pg.errorBanner}>
          {error}
        </div>
      )}

      {loading ? (
        <div style={pg.empty}>{t('Loading audit log…', 'Memuatkan log audit…')}</div>
      ) : filtered.length === 0 ? (
        <div style={pg.empty}>{t('No audit records.', 'Tiada rekod audit.')}</div>
      ) : (
        <div style={pg.tableWrap}>
          <table style={pg.table}>
            <thead>
              <tr>
                <th style={pg.th}>ID</th>
                <th style={pg.th}>{t('Time', 'Masa')}</th>
                <th style={pg.th}>{t('Action', 'Tindakan')}</th>
                <th style={pg.th}>{t('Detail', 'Detail')}</th>
                <th style={pg.th}>{t('User', 'Pengguna')}</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(e => {
                const cat = actionCategory(e.action);
                return (
                  <tr key={e.id} style={pg.tr}>
                    <td style={pg.td}>{e.id}</td>
                    <td style={pg.td}>{formatMasa(e.created_at)}</td>
                    <td style={pg.td}>
                      <span style={{
                        ...pg.badge,
                        backgroundColor: catColor[cat],
                        color: catTextColor[cat],
                      }}>
                        {e.action}
                      </span>
                    </td>
                    <td style={pg.tdDetail}>{truncateDetail(e.detail)}</td>
                    <td style={pg.td}>{e.user_id ?? '—'}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

const pg: Record<string, React.CSSProperties> = {
  h1: {
    margin: '0 0 16px',
    fontSize: 24,
    fontWeight: 700,
    color: 'var(--text-primary)',
  },
  filterBar: {
    display: 'flex',
    gap: 12,
    marginBottom: 16,
  },
  input: {
    padding: '8px 12px',
    borderRadius: 4,
    border: '0.5px solid var(--border)',
    fontSize: 13,
    color: 'var(--text-primary)',
    backgroundColor: 'var(--surface)',
    transition: 'all 0.15s ease',
  },
  select: {
    padding: '8px 12px',
    borderRadius: 4,
    border: '0.5px solid var(--border)',
    fontSize: 13,
    color: 'var(--text-primary)',
    backgroundColor: 'var(--surface)',
    transition: 'all 0.15s ease',
  },
  tableWrap: {
    backgroundColor: 'var(--surface)',
    borderRadius: 4,
    border: '0.5px solid var(--border)',
    overflow: 'hidden',
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
    fontSize: 13,
  },
  th: {
    padding: '12px 16px',
    backgroundColor: 'var(--surface)',
    borderBottom: '0.5px solid var(--border)',
    fontWeight: 600,
    color: 'var(--text-secondary)',
    textAlign: 'left',
    fontSize: 12,
  },
  tr: {
    borderBottom: '0.5px solid var(--border)',
    transition: 'all 0.15s ease',
  },
  td: {
    padding: '12px 16px',
    color: 'var(--text-primary)',
    fontSize: 12,
  },
  tdDetail: {
    padding: '12px 16px',
    color: 'var(--text-primary)',
    fontSize: 12,
    maxWidth: 400,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
  badge: {
    borderRadius: 9999,
    padding: '3px 10px',
    fontSize: 12,
    fontWeight: 600,
    display: 'inline-block',
    transition: 'all 0.15s ease',
  },
  empty: {
    fontSize: 14,
    color: 'var(--text-muted)',
    padding: '40px 0',
    textAlign: 'center',
  },
  errorBanner: {
    marginBottom: 16,
    padding: '12px 16px',
    backgroundColor: 'var(--danger-bg)',
    color: 'var(--danger)',
    borderRadius: 4,
    border: '0.5px solid var(--danger)',
    fontSize: 13,
  },
};
