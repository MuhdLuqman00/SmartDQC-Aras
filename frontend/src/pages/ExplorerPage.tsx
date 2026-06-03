import React, { useState, useMemo, useEffect, useCallback } from 'react';
import { Download, Search } from 'lucide-react';
import { api } from '../api/client';
import { useLang } from '../context/LanguageContext';
import { useSession } from '../context/SessionContext';
import { SessionGuard } from '../components/SessionGuard';
import { ColumnHistogram } from '../components/ColumnHistogram';
import { ErrorRetry } from '../components/ErrorRetry';

const PAGE_SIZE = 50;

export function ExplorerPage() {
  const { t } = useLang();
  const { cacheId, filename, rowCount, preview } = useSession();
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(0);
  const [fetched, setFetched] = useState<Record<string, unknown>[] | null>(null);
  const [serverRowCount, setServerRowCount] = useState<number | null>(null);
  const [editing, setEditing] = useState<{ rowIdx: number; col: string } | null>(null);
  const [editValue, setEditValue] = useState('');
  const [saving, setSaving] = useState(false);
  const [localRows, setLocalRows] = useState<Record<string, unknown>[] | null>(null);
  const [fetchError, setFetchError] = useState(false);
  const [fetchLoading, setFetchLoading] = useState(false);

  const ctxRows = (preview as Record<string, unknown>[] | null) ?? [];

  /* In-memory session.preview is only set by the clean wizard's last step.
     On reopen / refresh / direct nav it's empty — fetch durably by cacheId. */
  const loadPreview = useCallback(() => {
    if (ctxRows.length > 0 || !cacheId) return;
    setFetchLoading(true); setFetchError(false);
    api.get(`/clean/preview-cached/${cacheId}`)
      .then(r => {
        setFetched(Array.isArray(r.data?.rows) ? r.data.rows : []);
        setServerRowCount(
          typeof r.data?.row_count === 'number' ? r.data.row_count : null,
        );
      })
      .catch(() => { setFetched(null); setFetchError(true); })
      .finally(() => setFetchLoading(false));
  }, [cacheId, ctxRows.length]);
  useEffect(() => { loadPreview(); }, [loadPreview]);

  const baseRows = ctxRows.length > 0 ? ctxRows : (fetched ?? []);
  const rows = localRows ?? baseRows;
  const columns = rows.length > 0 ? Object.keys(rows[0]) : [];
  const effectiveRowCount = rowCount ?? serverRowCount;

  const numericColumns = useMemo(
    () => columns.filter(c =>
      rows.some(r => r[c] != null && r[c] !== '' && Number.isFinite(Number(r[c])))
    ),
    [columns, rows],
  );
  const [histCol, setHistCol] = useState<string>('');
  const activeHistCol = histCol || numericColumns[0] || '';
  const histValues = useMemo(
    () => rows
      .map(r => Number(r[activeHistCol]))
      .filter(v => Number.isFinite(v)),
    [rows, activeHistCol],
  );

  const editable = query === '';  // positional identity is only safe unfiltered

  const commitEdit = async () => {
    if (!editing || !cacheId) { setEditing(null); return; }
    setSaving(true);
    try {
      const r = await api.patch<{ row_index: number; row: Record<string, unknown> }>(
        '/clean/cell',
        { cache_id: cacheId, row_index: editing.rowIdx, column: editing.col, value: editValue },
      );
      const next = [...rows];
      next[r.data.row_index] = r.data.row;
      setLocalRows(next);
      setEditing(null);
    } catch {
      setEditing(null);
    } finally {
      setSaving(false);
    }
  };

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
            {effectiveRowCount?.toLocaleString() ?? '—'} {t('rows', 'baris')}
            {rows.length < (effectiveRowCount ?? 0) ? ` · ${t('showing first', 'menunjukkan')} ${rows.length}` : ''}
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

        <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
          {editable
            ? t('Double-click a cell to edit. Enter saves, Esc cancels.',
                'Klik dua kali sel untuk menyunting. Enter simpan, Esc batal.')
            : t('Clear the search to enable editing.',
                'Kosongkan carian untuk membolehkan suntingan.')}
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
          {fetchError ? (
            <ErrorRetry message={t('Could not load the data preview.', 'Tidak dapat memuatkan pratonton data.')} onRetry={loadPreview} />
          ) : fetchLoading && columns.length === 0 ? (
            <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>
              {t('Loading…', 'Memuatkan…')}
            </div>
          ) : columns.length === 0 ? (
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
                    {columns.map(c => {
                      const absIdx = page * PAGE_SIZE + i;
                      const isEditing = editing?.rowIdx === absIdx && editing?.col === c;
                      return (
                        <td
                          key={c}
                          onDoubleClick={() => {
                            if (!editable) return;
                            setEditing({ rowIdx: absIdx, col: c });
                            setEditValue(row[c] == null ? '' : String(row[c]));
                          }}
                          style={{ padding: '9px 14px', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)', whiteSpace: 'nowrap', cursor: editable ? 'cell' : 'default' }}
                        >
                          {isEditing ? (
                            <input
                              autoFocus
                              value={editValue}
                              disabled={saving}
                              onChange={e => setEditValue(e.target.value)}
                              onBlur={commitEdit}
                              onKeyDown={e => {
                                if (e.key === 'Enter') commitEdit();
                                if (e.key === 'Escape') setEditing(null);
                              }}
                              style={{ width: 120, padding: '2px 6px', fontSize: 12, fontFamily: 'var(--font-mono)', border: '1px solid var(--kkm-blue)', borderRadius: 4, background: 'var(--surface)', color: 'var(--text-primary)' }}
                            />
                          ) : (
                            row[c] == null
                              ? <span style={{ color: 'var(--text-muted)' }}>—</span>
                              : String(row[c])
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Column distribution */}
        {numericColumns.length > 0 && (
          <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-card)', padding: '18px 20px', boxShadow: 'var(--shadow-card)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
                {t('Column Distribution', 'Taburan Lajur')}
              </span>
              <select
                value={activeHistCol}
                onChange={e => setHistCol(e.target.value)}
                style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 6, padding: '6px 10px', fontSize: 12, color: 'var(--text-primary)' }}
              >
                {numericColumns.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <ColumnHistogram values={histValues} />
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, justifyContent: 'center' }}>
            <button aria-label={t('Previous page', 'Halaman sebelumnya')} disabled={page === 0} onClick={() => setPage(p => p - 1)} style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 6, padding: '6px 12px', cursor: page === 0 ? 'not-allowed' : 'pointer', opacity: page === 0 ? 0.4 : 1, color: 'var(--text-primary)', fontSize: 13 }}>←</button>
            <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
              {t('Page', 'Halaman')} {page + 1} / {totalPages}
            </span>
            <button aria-label={t('Next page', 'Halaman seterusnya')} disabled={page >= totalPages - 1} onClick={() => setPage(p => p + 1)} style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 6, padding: '6px 12px', cursor: page >= totalPages - 1 ? 'not-allowed' : 'pointer', opacity: page >= totalPages - 1 ? 0.4 : 1, color: 'var(--text-primary)', fontSize: 13 }}>→</button>
          </div>
        )}
      </div>
    </SessionGuard>
  );
}
