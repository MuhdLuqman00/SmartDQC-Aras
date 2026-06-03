import React, { useEffect, useState } from 'react';
import { Download, Copy, Check } from 'lucide-react';
import { api } from '../api/client';
import { useLang } from '../context/LanguageContext';

/* Audit details are dominated by long cache_id/chat_id strings. Shorten any
   id-like token to first6…last4 for readability; a copy button yields the
   full original, and the title attribute shows it on hover. */
function shortenIds(s: string): string {
  return s.replace(/([A-Za-z0-9_-]{16,})/g, m => `${m.slice(0, 6)}…${m.slice(-4)}`);
}

function DetailCell({ text }: { text: string | null }) {
  const { t } = useLang();
  const [copied, setCopied] = useState(false);
  if (!text) return <span style={{ color: 'var(--text-muted)' }}>—</span>;
  const copy = () => {
    navigator.clipboard?.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    }).catch(() => { /* clipboard unavailable — title still shows full value */ });
  };
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 7, maxWidth: 360 }}>
      <span title={text} style={{ fontFamily: 'var(--font-mono)', fontSize: 11, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {shortenIds(text)}
      </span>
      <button
        onClick={copy}
        aria-label={t('Copy details', 'Salin butiran')}
        title={t('Copy', 'Salin')}
        style={{
          background: 'none', border: 'none', padding: 2, cursor: 'pointer',
          color: copied ? 'var(--success)' : 'var(--text-muted)', display: 'flex', flexShrink: 0,
        }}
      >
        {copied ? <Check size={13} /> : <Copy size={13} />}
      </button>
    </span>
  );
}

interface AuditEntry {
  id: number;
  action: string;
  /** Backend column is `detail` (singular); the prior `details` typo left
      the Details column blank for every row. */
  detail: string | null;
  username: string | null;
  created_at: string;
}

const PAGE_SIZE = 50;

export function AuditPage() {
  const { t } = useLang();
  const [logs, setLogs] = useState<AuditEntry[]>([]);
  const [filtered, setFiltered] = useState<AuditEntry[]>([]);
  const [actionFilter, setActionFilter] = useState('');
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get<AuditEntry[]>('/audit/log?limit=500').then(r => {
      setLogs(r.data); setFiltered(r.data);
    }).finally(() => setLoading(false));
  }, []);

  const uniqueActions = Array.from(new Set(logs.map(l => l.action))).sort();

  const applyFilter = (action: string) => {
    setActionFilter(action);
    setPage(0);
    setFiltered(action ? logs.filter(l => l.action === action) : logs);
  };

  const pageRows = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);

  const exportCsv = () => {
    const header = ['Time', 'Action', 'Details', 'User'].join(',');
    const rows = filtered.map(l => [l.created_at, l.action, `"${(l.detail ?? '').replace(/"/g, '""')}"`, l.username ?? ''].join(','));
    const blob = new Blob([[header, ...rows].join('\n')], { type: 'text/csv' });
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'audit_log.csv'; a.click();
  };

  return (
    <div>
      {/* Controls */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
        <select
          value={actionFilter}
          onChange={e => applyFilter(e.target.value)}
          style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8, padding: '8px 12px', fontSize: 13, color: 'var(--text-primary)', cursor: 'pointer' }}
        >
          <option value="">{t('All actions', 'Semua tindakan')}</option>
          {uniqueActions.map(a => <option key={a} value={a}>{a}</option>)}
        </select>
        <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
          {filtered.length.toLocaleString()} {t('entries', 'entri')}
        </span>
        <div style={{ flex: 1 }} />
        <button
          onClick={exportCsv}
          style={{ display: 'flex', alignItems: 'center', gap: 6, background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-btn)', padding: '7px 14px', fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', cursor: 'pointer' }}
        >
          <Download size={14} /> {t('Export CSV', 'Eksport CSV')}
        </button>
      </div>

      {/* Table */}
      <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-card)', overflow: 'auto', boxShadow: 'var(--shadow-card)' }}>
        {loading ? (
          <div style={{ padding: 40, color: 'var(--text-muted)', textAlign: 'center' }}>{t('Loading…', 'Memuatkan…')}</div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr style={{ background: 'var(--surface-2)', borderBottom: '1px solid var(--border)' }}>
                {[t('Time', 'Masa'), t('Action', 'Tindakan'), t('Details', 'Butiran'), t('User', 'Pengguna')].map(h => (
                  <th key={h} style={{ padding: '10px 16px', textAlign: 'left', fontWeight: 600, fontSize: 11, letterSpacing: '0.06em', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {pageRows.map((entry, i) => (
                <tr key={entry.id} style={{ borderBottom: i < pageRows.length - 1 ? '1px solid var(--border)' : 'none', background: i % 2 === 0 ? 'transparent' : 'var(--surface-2)' }}>
                  <td style={{ padding: '10px 16px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', whiteSpace: 'nowrap' }}>
                    {new Date(entry.created_at).toLocaleString()}
                  </td>
                  <td style={{ padding: '10px 16px' }}>
                    <span style={{ fontSize: 11, fontWeight: 600, background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 999, padding: '2px 8px', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>
                      {entry.action}
                    </span>
                  </td>
                  <td style={{ padding: '10px 16px', color: 'var(--text-secondary)', maxWidth: 360 }}>
                    <DetailCell text={entry.detail} />
                  </td>
                  <td style={{ padding: '10px 16px', color: entry.username ? 'var(--text-primary)' : 'var(--text-muted)', fontWeight: 500 }}>
                    {entry.username ?? t('System', 'Sistem')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div style={{ display: 'flex', gap: 8, justifyContent: 'center', marginTop: 16 }}>
          <button aria-label={t('Previous page', 'Halaman sebelumnya')} disabled={page === 0} onClick={() => setPage(p => p - 1)} style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 6, padding: '6px 14px', cursor: page === 0 ? 'not-allowed' : 'pointer', opacity: page === 0 ? 0.4 : 1, color: 'var(--text-primary)', fontSize: 13 }}>←</button>
          <span style={{ fontSize: 13, color: 'var(--text-secondary)', alignSelf: 'center' }}>
            {page + 1} / {totalPages}
          </span>
          <button aria-label={t('Next page', 'Halaman seterusnya')} disabled={page >= totalPages - 1} onClick={() => setPage(p => p + 1)} style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 6, padding: '6px 14px', cursor: page >= totalPages - 1 ? 'not-allowed' : 'pointer', opacity: page >= totalPages - 1 ? 0.4 : 1, color: 'var(--text-primary)', fontSize: 13 }}>→</button>
        </div>
      )}
    </div>
  );
}
