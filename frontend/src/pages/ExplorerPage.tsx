import React, { useState, useMemo, useEffect, useCallback } from 'react';
import { Download, Search, Pencil, AlertTriangle } from 'lucide-react';
import { api } from '../api/client';
import { useLang } from '../context/LanguageContext';
import { useSession } from '../context/SessionContext';
import { SessionGuard } from '../components/SessionGuard';
import { ColumnHistogram } from '../components/ColumnHistogram';
import { ErrorRetry } from '../components/ErrorRetry';
import { classifyCell, cellFlagStyle, validateEdit } from '../utils/cellFlags';

const PAGE_SIZE = 50;

export function ExplorerPage() {
  const { t } = useLang();
  const { cacheId, filename, rowCount, preview } = useSession();
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(0);
  const [fetched, setFetched] = useState<Record<string, unknown>[] | null>(null);
  const [serverRowCount, setServerRowCount] = useState<number | null>(null);
  const [serverRowFlags, setServerRowFlags] = useState<boolean[] | null>(null);
  const [showFlaggedOnly, setShowFlaggedOnly] = useState(false);
  const [editing, setEditing] = useState<{ rowIdx: number; col: string } | null>(null);
  const [editValue, setEditValue] = useState('');
  const [saving, setSaving] = useState(false);
  const [editError, setEditError] = useState<string>('');
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
        setServerRowFlags(Array.isArray(r.data?.row_flags) ? r.data.row_flags : null);
      })
      .catch(() => { setFetched(null); setFetchError(true); })
      .finally(() => setFetchLoading(false));
  }, [cacheId, ctxRows.length]);
  useEffect(() => { loadPreview(); }, [loadPreview]);

  const baseRows = ctxRows.length > 0 ? ctxRows : (fetched ?? []);
  const rows = localRows ?? baseRows;
  const columns = rows.length > 0 ? Object.keys(rows[0]) : [];
  const effectiveRowCount = rowCount ?? serverRowCount;
  const isTruncated = effectiveRowCount != null && rows.length < effectiveRowCount;

  // Client-side flag fallback for session-context rows (no fetch fired for those).
  const clientRowFlags = useMemo(
    () => rows.map(row => columns.some(c => classifyCell(c, row[c]) !== 'ok')),
    [rows, columns],
  );
  const rowFlags = serverRowFlags ?? clientRowFlags;
  const flaggedCount = rowFlags.filter(Boolean).length;

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

  // Edit disabled under any client-side filter (search OR flagged toggle) because
  // positional identity (absIdx) is only safe when rows are unfiltered.
  // Phase 5's _row_id seam will lift this restriction.
  const editable = query === '' && !showFlaggedOnly;

  const commitEdit = async () => {
    if (!editing || !cacheId) { setEditing(null); return; }
    const validation = validateEdit(editing.col, editValue);
    if (!validation.ok) {
      setEditError(`${validation.messageEN} / ${validation.messageBM}`);
      return;
    }
    setEditError('');
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

  const flagFiltered = useMemo(
    () => showFlaggedOnly ? rows.filter((_, i) => rowFlags[i] === true) : rows,
    [rows, rowFlags, showFlaggedOnly],
  );

  const filtered = useMemo(() => {
    if (!query) return flagFiltered;
    const q = query.toLowerCase();
    return flagFiltered.filter(r => columns.some(c => String(r[c] ?? '').toLowerCase().includes(q)));
  }, [flagFiltered, query, columns]);

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

        <div id="explorer-edit-hint" style={{ fontSize: 12, color: 'var(--text-muted)' }}>
          {editable
            ? t('Double-click a cell — or focus it and press Enter — to edit. Enter saves, Esc cancels.',
                'Klik dua kali sel — atau fokus dan tekan Enter — untuk menyunting. Enter simpan, Esc batal.')
            : showFlaggedOnly
              ? t('Clear the flagged filter to enable editing.',
                  'Kosongkan penapis bermasalah untuk membolehkan suntingan.')
              : t('Clear the search to enable editing.',
                  'Kosongkan carian untuk membolehkan suntingan.')}
        </div>

        {/* Search + Flagged-only toggle */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        <div style={{ position: 'relative', maxWidth: 320, flex: '1 1 200px' }}>
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

        {flaggedCount > 0 && (
          <button
            onClick={() => { setShowFlaggedOnly(v => !v); setPage(0); }}
            aria-pressed={showFlaggedOnly}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              background: showFlaggedOnly ? 'var(--warning)' : 'var(--surface)',
              border: `1px solid ${showFlaggedOnly ? 'var(--warning)' : 'var(--border)'}`,
              borderRadius: 'var(--radius-btn)', padding: '7px 14px',
              fontSize: 13, fontWeight: 600,
              color: showFlaggedOnly ? '#fff' : 'var(--warning)',
              cursor: 'pointer', whiteSpace: 'nowrap', flexShrink: 0,
            }}
          >
            <AlertTriangle size={13} aria-hidden />
            {showFlaggedOnly
              ? t(`Flagged only (${flaggedCount})`, `Bermasalah sahaja (${flaggedCount})`)
              : t(`Show flagged (${flaggedCount})`, `Tunjuk bermasalah (${flaggedCount})`)
            }
          </button>
        )}
        </div>

        {/* Truncation banner — visible when loaded rows < total rows */}
        {isTruncated && (
          <div
            role="alert"
            aria-live="polite"
            style={{
              display: 'flex', alignItems: 'flex-start', gap: 10,
              background: 'var(--warning-bg, #fffbeb)', border: '1px solid var(--warning)',
              borderRadius: 8, padding: '10px 14px', fontSize: 13,
              color: 'var(--text-primary)',
            }}
          >
            <AlertTriangle size={16} style={{ color: 'var(--warning)', flexShrink: 0, marginTop: 1 }} aria-hidden />
            <span>
              <strong style={{ color: 'var(--warning)' }}>
                {t('Partial view', 'Paparan separa')}:
              </strong>
              {' '}
              {t(
                `Showing first ${rows.length.toLocaleString()} of ${effectiveRowCount!.toLocaleString()} rows. Use search or Download to reach the rest.`,
                `Menunjukkan ${rows.length.toLocaleString()} daripada ${effectiveRowCount!.toLocaleString()} baris. Guna carian atau Muat Turun untuk selebihnya.`,
              )}
            </span>
          </div>
        )}

        {/* Conditional-formatting legend */}
        {columns.length > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              {t('Cell highlight', 'Sorotan sel')}:
            </span>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, background: 'var(--danger-bg)', border: '1px solid var(--danger)', borderRadius: 4, padding: '2px 8px', fontSize: 11 }}>
              <span style={{ width: 8, height: 8, borderRadius: 2, background: 'var(--danger)', display: 'inline-block', flexShrink: 0 }} aria-hidden />
              <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{t('Impossible value', 'Nilai mustahil')}</span>
            </span>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, background: 'var(--warning-bg)', border: '1px solid var(--warning)', borderRadius: 4, padding: '2px 8px', fontSize: 11 }}>
              <span style={{ width: 8, height: 8, borderRadius: 2, background: 'var(--warning)', display: 'inline-block', flexShrink: 0 }} aria-hidden />
              <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{t('Out of range / missing', 'Di luar julat / tiada nilai')}</span>
            </span>
          </div>
        )}

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
                      const flag = classifyCell(c, row[c]);
                      const isNumeric = numericColumns.includes(c);
                      const flagLabel = flag === 'danger'
                        ? t('Impossible value', 'Nilai mustahil')
                        : flag === 'warn'
                          ? t('Out of range or missing', 'Di luar julat atau tiada nilai')
                          : undefined;
                      return (
                        <td
                          key={c}
                          className={`explorer-cell${editable && !isEditing ? ' editable' : ''}`}
                          tabIndex={editable && !isEditing ? 0 : undefined}
                          aria-describedby={editable && !isEditing ? 'explorer-edit-hint' : undefined}
                          aria-label={flagLabel ? `${c}: ${String(row[c] ?? '')} — ${flagLabel}` : undefined}
                          onDoubleClick={() => {
                            if (!editable) return;
                            setEditing({ rowIdx: absIdx, col: c });
                            setEditValue(row[c] == null ? '' : String(row[c]));
                            setEditError('');
                          }}
                          onKeyDown={e => {
                            if (!editable || isEditing) return;
                            if (e.key === 'Enter' || e.key === 'F2') {
                              e.preventDefault();
                              setEditing({ rowIdx: absIdx, col: c });
                              setEditValue(row[c] == null ? '' : String(row[c]));
                              setEditError('');
                            }
                          }}
                          style={{
                            padding: '9px 14px', color: 'var(--text-primary)',
                            fontFamily: 'var(--font-mono)', whiteSpace: 'nowrap',
                            textAlign: isNumeric ? 'right' : 'left',
                            ...cellFlagStyle(flag),
                          }}
                        >
                          {isEditing ? (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                              <input
                                autoFocus
                                value={editValue}
                                disabled={saving}
                                aria-invalid={editError ? true : undefined}
                                aria-describedby={editError ? `edit-err-${absIdx}-${c}` : undefined}
                                onChange={e => { setEditValue(e.target.value); setEditError(''); }}
                                onBlur={commitEdit}
                                onKeyDown={e => {
                                  if (e.key === 'Enter') commitEdit();
                                  if (e.key === 'Escape') { setEditing(null); setEditError(''); }
                                }}
                                style={{
                                  width: 120, padding: '2px 6px', fontSize: 12,
                                  fontFamily: 'var(--font-mono)',
                                  border: `1px solid ${editError ? 'var(--danger)' : 'var(--kkm-blue)'}`,
                                  borderRadius: 4, background: 'var(--surface)', color: 'var(--text-primary)',
                                }}
                              />
                              {editError && (
                                <span
                                  id={`edit-err-${absIdx}-${c}`}
                                  role="alert"
                                  style={{ fontSize: 10, color: 'var(--danger)', whiteSpace: 'normal', maxWidth: 160, lineHeight: 1.3 }}
                                >
                                  {editError}
                                </span>
                              )}
                            </div>
                          ) : (
                            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                              {row[c] == null
                                ? <span style={{ color: 'var(--text-muted)' }}>—</span>
                                : String(row[c])}
                              {editable && <Pencil className="edit-icon" size={11} style={{ color: 'var(--kkm-sky)' }} aria-hidden />}
                            </span>
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
            <button aria-label={t('Previous page', 'Halaman sebelumnya')} disabled={page === 0} onClick={() => setPage(p => p - 1)} style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-btn)', padding: '6px 12px', cursor: page === 0 ? 'not-allowed' : 'pointer', opacity: page === 0 ? 0.4 : 1, color: 'var(--text-primary)', fontSize: 13 }}>←</button>
            <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
              {t('Page', 'Halaman')} {page + 1} / {totalPages}
              {isTruncated && (
                <span style={{ color: 'var(--warning)', marginLeft: 6, fontSize: 11, fontWeight: 600 }}>
                  ({t(`first ${rows.length.toLocaleString()} loaded`, `${rows.length.toLocaleString()} baris pertama dimuatkan`)})
                </span>
              )}
            </span>
            <button aria-label={t('Next page', 'Halaman seterusnya')} disabled={page >= totalPages - 1} onClick={() => setPage(p => p + 1)} style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-btn)', padding: '6px 12px', cursor: page >= totalPages - 1 ? 'not-allowed' : 'pointer', opacity: page >= totalPages - 1 ? 0.4 : 1, color: 'var(--text-primary)', fontSize: 13 }}>→</button>
          </div>
        )}
      </div>
    </SessionGuard>
  );
}
