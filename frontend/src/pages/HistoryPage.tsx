import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, BASE } from '../api/client';
import { useLang } from '../context/LanguageContext';

interface Session {
  cache_id: string;
  filename: string;
  source_type: string;
  row_count: number;
  quality_score: number;
}

type SortField = 'filename' | 'source_type' | 'row_count' | 'quality_score';
type SortDir = 'asc' | 'desc';

function qBadgeStyle(score: number): React.CSSProperties {
  const bg =
    score >= 80
      ? 'var(--success-bg)'
      : score >= 60
        ? 'var(--warning-bg)'
        : 'var(--danger-bg)';
  const color =
    score >= 80
      ? 'var(--success)'
      : score >= 60
        ? 'var(--warning)'
        : 'var(--danger)';
  return {
    background: bg,
    color,
    borderRadius: 12,
    padding: '2px 10px',
    fontSize: 12,
    fontWeight: 700,
  };
}

export function HistoryPage() {
  const navigate = useNavigate();
  const { t } = useLang();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [sourceFilter, setSourceFilter] = useState<string>('');
  const [minQ, setMinQ] = useState<number>(0);
  const [maxQ, setMaxQ] = useState<number>(100);
  const [sortField, setSortField] = useState<SortField>('quality_score');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    api
      .get<Session[]>('/sessions')
      .then((res) => setSessions(res.data))
      .catch(() => setError(t('Failed to load session history', 'Gagal memuatkan sejarah sesi')))
      .finally(() => setLoading(false));
  }, []);

  const uniqueSources = Array.from(new Set(sessions.map((s) => s.source_type)));

  const filtered = sessions
    .filter((s) => !sourceFilter || s.source_type === sourceFilter)
    .filter((s) => s.quality_score >= minQ && s.quality_score <= maxQ)
    .sort((a, b) => {
      const v = sortDir === 'asc' ? 1 : -1;
      return a[sortField] > b[sortField] ? v : -v;
    });

  function handleHeaderClick(field: SortField) {
    if (sortField === field) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDir('desc');
    }
  }

  return (
    <div style={styles.container}>
      <h1 style={styles.h1}>{t('Session History', 'Sejarah Sesi')}</h1>

      {error && <div style={styles.errorBanner}>{error}</div>}

      <div style={styles.filterBar}>
        <select
          style={styles.select}
          value={sourceFilter}
          onChange={(e) => setSourceFilter(e.target.value)}
        >
          <option value="">{t('All Types', 'Semua Jenis')}</option>
          {uniqueSources.map((source) => (
            <option key={source} value={source}>
              {source}
            </option>
          ))}
        </select>

        <div style={styles.inputGroup}>
          <label style={styles.inputLabel}>{t('Min Quality', 'Min Kualiti')}</label>
          <input
            type="number"
            min={0}
            max={100}
            value={minQ}
            onChange={(e) => setMinQ(Number(e.target.value))}
            style={styles.numberInput}
          />
        </div>

        <div style={styles.inputGroup}>
          <label style={styles.inputLabel}>{t('Max Quality', 'Maks Kualiti')}</label>
          <input
            type="number"
            min={0}
            max={100}
            value={maxQ}
            onChange={(e) => setMaxQ(Number(e.target.value))}
            style={styles.numberInput}
          />
        </div>
      </div>

      {loading ? (
        <div style={styles.empty}>{t('Loading history...', 'Memuatkan sejarah...')}</div>
      ) : filtered.length === 0 ? (
        <div style={styles.empty}>{t('No sessions found.', 'Tiada sesi ditemui.')}</div>
      ) : (
        <div style={styles.tableWrap}>
          <table style={styles.table}>
            <thead>
              <tr>
                <th
                  style={{
                    ...styles.th,
                    cursor: 'pointer',
                    userSelect: 'none',
                  }}
                  onClick={() => handleHeaderClick('filename')}
                >
                  {t('File', 'Fail')} {sortField === 'filename' ? (sortDir === 'asc' ? '↑' : '↓') : ''}
                </th>
                <th
                  style={{
                    ...styles.th,
                    cursor: 'pointer',
                    userSelect: 'none',
                  }}
                  onClick={() => handleHeaderClick('source_type')}
                >
                  {t('Type', 'Jenis')}{' '}
                  {sortField === 'source_type' ? (sortDir === 'asc' ? '↑' : '↓') : ''}
                </th>
                <th
                  style={{
                    ...styles.th,
                    cursor: 'pointer',
                    userSelect: 'none',
                  }}
                  onClick={() => handleHeaderClick('row_count')}
                >
                  {t('Rows', 'Baris')} {sortField === 'row_count' ? (sortDir === 'asc' ? '↑' : '↓') : ''}
                </th>
                <th
                  style={{
                    ...styles.th,
                    cursor: 'pointer',
                    userSelect: 'none',
                  }}
                  onClick={() => handleHeaderClick('quality_score')}
                >
                  {t('Quality Score', 'Skor Kualiti')}{' '}
                  {sortField === 'quality_score'
                    ? sortDir === 'asc'
                      ? '↑'
                      : '↓'
                    : ''}
                </th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((session) => (
                <tr key={session.cache_id} style={styles.tr}>
                  <td style={styles.td}>{session.filename}</td>
                  <td style={styles.td}>
                    <span style={styles.sourceBadge}>{session.source_type}</span>
                  </td>
                  <td style={styles.td}>{(session.row_count ?? 0).toLocaleString()}</td>
                  <td style={styles.td}>
                    <span style={qBadgeStyle(session.quality_score)}>
                      {session.quality_score}%
                    </span>
                  </td>
                  <td style={styles.tdActions}>
                    <button
                      style={styles.actionBtn}
                      onClick={() =>
                        navigate(`/cleaning?cache_id=${session.cache_id}`)
                      }
                    >
                      {t('Reopen', 'Buka Semula')}
                    </button>
                    <button
                      style={styles.actionBtnSecondary}
                      onClick={() =>
                        window.open(
                          `${BASE}/clean/export?cache_id=${session.cache_id}`
                        )
                      }
                    >
                      {t('Download', 'Muat Turun')}
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

const styles: Record<string, React.CSSProperties> = {
  container: {
    padding: '0',
  },
  h1: {
    margin: '0 0 16px 0',
    fontSize: 24,
    fontWeight: 700,
    color: 'var(--text-primary)',
  },
  errorBanner: {
    marginBottom: 16,
    padding: '12px 16px',
    background: 'var(--danger-bg)',
    color: 'var(--danger)',
    borderRadius: 8,
    border: '0.5px solid var(--danger)',
    fontSize: 13,
  },
  filterBar: {
    display: 'flex',
    flexDirection: 'row',
    gap: 12,
    marginBottom: 16,
    alignItems: 'flex-end',
    flexWrap: 'wrap',
  },
  select: {
    padding: '8px 12px',
    borderRadius: 6,
    border: '0.5px solid var(--border)',
    fontSize: 13,
    color: 'var(--text-primary)',
    background: 'var(--surface-2)',
    cursor: 'pointer',
    transition: 'all 0.15s ease',
  },
  inputGroup: {
    display: 'flex',
    flexDirection: 'column',
    gap: 4,
  },
  inputLabel: {
    fontSize: 11,
    fontWeight: 600,
    color: 'var(--text-secondary)',
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
  },
  numberInput: {
    padding: '6px 10px',
    borderRadius: 6,
    border: '0.5px solid var(--border)',
    fontSize: 13,
    color: 'var(--text-primary)',
    background: 'var(--surface-2)',
    width: 80,
    transition: 'all 0.15s ease',
  },
  tableWrap: {
    background: 'var(--surface)',
    borderRadius: 8,
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
    background: 'var(--surface-2)',
    borderBottom: '0.5px solid var(--border)',
    fontWeight: 600,
    color: 'var(--text-secondary)',
    textAlign: 'left',
    fontSize: 12,
    transition: 'all 0.15s ease',
  },
  tr: {
    borderBottom: '0.5px solid var(--border)',
  },
  td: {
    padding: '14px 16px',
    color: 'var(--text-primary)',
    fontSize: 13,
  },
  tdActions: {
    padding: '14px 16px',
    display: 'flex',
    gap: 8,
  },
  sourceBadge: {
    background: 'var(--surface)',
    color: 'var(--blue)',
    borderRadius: 6,
    padding: '4px 8px',
    fontSize: 12,
    fontWeight: 600,
    border: '0.5px solid var(--border)',
  },
  actionBtn: {
    padding: '6px 12px',
    background: 'var(--blue)',
    color: '#fff',
    border: 'none',
    borderRadius: 6,
    fontSize: 12,
    fontWeight: 600,
    cursor: 'pointer',
    transition: 'all 0.15s ease',
  },
  actionBtnSecondary: {
    padding: '6px 12px',
    background: 'transparent',
    color: 'var(--blue)',
    border: '0.5px solid var(--blue)',
    borderRadius: 6,
    fontSize: 12,
    fontWeight: 600,
    cursor: 'pointer',
    transition: 'all 0.15s ease',
  },
  empty: {
    fontSize: 14,
    color: 'var(--text-muted)',
    padding: '40px 20px',
    textAlign: 'center',
  },
};
