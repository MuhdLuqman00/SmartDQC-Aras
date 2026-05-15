import React, { useState, useMemo } from 'react';
import { Download, Search } from 'lucide-react';
import { useLang } from '../context/LanguageContext';
import { useSession } from '../context/SessionContext';
import { SessionGuard } from '../components/SessionGuard';

const PAGE_SIZE = 50;

export function ExplorerPage() {
  const { t } = useLang();
  const { cacheId, filename, rowCount, preview } = useSession();
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(0);

  const rows = (preview as Record<string, unknown>[] | null) ?? [];
  const columns = rows.length > 0 ? Object.keys(rows[0]) : [];

  const filtered = useMemo(() => {
    if (!query) return rows;
    const q = query.toLowerCase();
    return rows.filter(r => columns.some(c => String(r[c] ?? '').toLowerCase().includes(q)));
  }, [rows, query, columns]);

  const pageRows = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);

  const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) || 'http://localhost:8000';

  return (
    <SessionGuard>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{
            fontSize: 12, fontWeight: 600, padding: '3px 10px', borderRadius: 999,
            background: 'var(--surface-2)', border: '1px solid var(--border)',
            color: 'var(--text-secondary)',
          }}>
            {filename}
          </span>
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            {rowCount?.toLocaleString() ?? '—'} {t('rows', 'baris')}
            {rows.length < (rowCount ?? 0) ? ` · ${t('showing first', 'menunjukkan')} ${rows.length}` : ''}
          </span>
          <div style={{ flex: 1 }} />
          <a
            href={`${BASE}/clean/download-cached/${cacheId}?format=csv`}
            target="_blank" rel="noreferrer"
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              background: 'var(--surface-2)', border: '1px solid var(--border)',
              borderRadius: 'var(--radius-btn)', padding: '7px 14px',
              fontSize: 13, fontWeight: 600, color: 'var(--text-primary)',
            }}
          >
            <Download size={14} /> {t('Download Full CSV', 'Muat Turun CSV Penuh')}
          </a>
        </div>

        {/* Search */}
        <div style={{ position: 'relative', maxWidth: 320 }}>
          <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
          <input
            value={query}
            onChange={e => { setQuery(e.target.value); setPage(0); }}
            placeholder={t('Search visible rows…', 'Cari baris yang kelihatan…')}
            style={{
              width: '100%', padding: '8px 12px 8px 32px',
              background: 'var(--surface)', border: '1px solid var(--border)',
              borderRadius: 8, fontSize: 13, color: 'var(--text-primary)',
              outline: 'none',
            }}
          />
        </div>

        {/* Table */}
        <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-card)', overflow: 'auto', boxShadow: 'var(--shadow-card)' }}>
          {columns.length === 0 ? (
            <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>
              {t('No preview data available.', 'Tiada data pratonton.')}
            </div>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr style={{ background: 'var(--surface-2)', position: 'sticky', top: 0, zIndex: 1 }}>
                  {columns.map(c => (
                    <th key={c} style={{
                      padding: '10px 14px', textAlign: 'left', fontWeight: 600,
                      fontSize: 11, color: 'var(--text-secondary)', letterSpacing: '0.05em',
                      borderBottom: '1px solid var(--border)', whiteSpace: 'nowrap',
                    }}>
                      {c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {pageRows.map((row, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid var(--border)', background: i % 2 === 0 ? 'transparent' : 'var(--surface-2)' }}>
                    {columns.map(c => (
                      <td key={c} style={{ padding: '9px 14px', color: 'var(--text-primary)', fontFamily: 'JetBrains Mono, monospace', whiteSpace: 'nowrap' }}>
                        {row[c] == null ? <span style={{ color: 'var(--text-muted)' }}>—</span> : String(row[c])}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, justifyContent: 'center' }}>
            <button disabled={page === 0} onClick={() => setPage(p => p - 1)} style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 6, padding: '6px 12px', cursor: page === 0 ? 'not-allowed' : 'pointer', opacity: page === 0 ? 0.4 : 1, color: 'var(--text-primary)', fontSize: 13 }}>←</button>
            <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
              {t('Page', 'Halaman')} {page + 1} / {totalPages}
            </span>
            <button disabled={page >= totalPages - 1} onClick={() => setPage(p => p + 1)} style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 6, padding: '6px 12px', cursor: page >= totalPages - 1 ? 'not-allowed' : 'pointer', opacity: page >= totalPages - 1 ? 0.4 : 1, color: 'var(--text-primary)', fontSize: 13 }}>→</button>
          </div>
        )}
      </div>
    </SessionGuard>
  );
}
