import React, { useState, useMemo, useEffect, useCallback, useRef } from 'react';
import { createPortal } from 'react-dom';
import { Download, Search, Pencil, AlertTriangle, Maximize2, Minimize2 } from 'lucide-react';
import { api } from '../api/client';
import { useLang } from '../context/LanguageContext';
import { useSession } from '../context/SessionContext';
import { SessionGuard } from '../components/SessionGuard';
import { ColumnHistogram } from '../components/ColumnHistogram';
import { ErrorRetry } from '../components/ErrorRetry';
import { classifyCell, cellFlagStyle, validateEdit } from '../utils/cellFlags';

// Virtual scroll constants — only ~40 rows mounted at a time so edit re-renders stay fast.
const ROW_HEIGHT       = 38;  // px; keep in sync with td height style below
const CONTAINER_HEIGHT = 560; // px
const SCROLL_BUFFER    = 8;   // extra rows rendered above/below viewport

export function ExplorerPage() {
  const { t } = useLang();
  const { cacheId, filename, rowCount } = useSession();

  // ── Data state ─────────────────────────────────────────────────────────────
  const [allRows, setAllRows]         = useState<Record<string, unknown>[] | null>(null);
  const [serverTotal, setServerTotal] = useState<number | null>(null);
  const [fetchError, setFetchError]   = useState(false);
  const [fetchLoading, setFetchLoading] = useState(false);

  // ── Filter / sort state ────────────────────────────────────────────────────
  const [query,          setQuery]          = useState('');
  const [sortCol,        setSortCol]        = useState('');
  const [sortDir,        setSortDir]        = useState<'asc' | 'desc'>('asc');
  const [showFlaggedOnly, setShowFlaggedOnly] = useState(false);

  // ── Edit state ─────────────────────────────────────────────────────────────
  // editing.rowId = _row_id (stable iloc position) — safe under any sort/filter.
  const [editing,   setEditing]   = useState<{ rowId: number; col: string } | null>(null);
  const [editValue, setEditValue] = useState('');
  const [saving,    setSaving]    = useState(false);
  const [editError, setEditError] = useState('');

  // ── Virtual scroll state ───────────────────────────────────────────────────
  const [scrollTop, setScrollTop] = useState(0);
  const scrollRef = useRef<HTMLDivElement>(null);

  // ── Histogram state ────────────────────────────────────────────────────────
  const [histCol, setHistCol] = useState('');

  // ── Fullscreen state ───────────────────────────────────────────────────────
  // When the table is maximised it renders as a fixed overlay and the virtual
  // scroll window grows to fill the viewport. viewportH tracks window height so
  // the row math stays correct across resizes.
  const [fullscreen, setFullscreen] = useState(false);
  const [viewportH, setViewportH] = useState(
    typeof window !== 'undefined' ? window.innerHeight : 800,
  );
  useEffect(() => {
    if (!fullscreen) return;
    const onResize = () => setViewportH(window.innerHeight);
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setFullscreen(false); };
    onResize();
    window.addEventListener('resize', onResize);
    window.addEventListener('keydown', onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('resize', onResize);
      window.removeEventListener('keydown', onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [fullscreen]);

  // Visible scroll height: fills the viewport (minus toolbar/footer chrome) when
  // maximised, otherwise the fixed inline height.
  const containerHeight = fullscreen ? Math.max(360, viewportH - 150) : CONTAINER_HEIGHT;

  // ── Fetch all rows from the stable-key seam ────────────────────────────────
  const loadRows = useCallback(() => {
    if (!cacheId) return;
    setFetchLoading(true);
    setFetchError(false);
    api.post('/clean/query-cached', { cache_id: cacheId, limit: 50000 })
      .then(r => {
        setAllRows(Array.isArray(r.data?.rows) ? r.data.rows : []);
        setServerTotal(typeof r.data?.total === 'number' ? r.data.total : null);
      })
      .catch(() => { setAllRows(null); setFetchError(true); })
      .finally(() => setFetchLoading(false));
  }, [cacheId]);

  useEffect(() => { loadRows(); }, [loadRows]);

  // Reset scroll to top whenever the filter/sort changes
  useEffect(() => {
    setScrollTop(0);
    if (scrollRef.current) scrollRef.current.scrollTop = 0;
  }, [query, showFlaggedOnly, sortCol, sortDir]);

  // ── Derived values ─────────────────────────────────────────────────────────
  const rows = allRows ?? [];

  // _row_id and _flagged are internal metadata — hide from the visible column list.
  const columns = useMemo(
    () => rows.length > 0
      ? Object.keys(rows[0]).filter(c => c !== '_row_id' && c !== '_flagged')
      : [],
    [rows],
  );

  const effectiveTotal = serverTotal ?? rowCount;
  const isTruncated    = effectiveTotal != null && rows.length < effectiveTotal;

  const flaggedCount = useMemo(
    () => rows.filter(r => !!r['_flagged']).length,
    [rows],
  );

  const numericColumns = useMemo(
    () => columns.filter(c =>
      rows.some(r => r[c] != null && r[c] !== '' && Number.isFinite(Number(r[c])))
    ),
    [columns, rows],
  );
  const activeHistCol = histCol || numericColumns[0] || '';
  const histValues = useMemo(
    () => rows.map(r => Number(r[activeHistCol])).filter(v => Number.isFinite(v)),
    [rows, activeHistCol],
  );

  // ── Filter pipeline: flagged → search → sort ───────────────────────────────
  const flagFiltered = useMemo(
    () => showFlaggedOnly ? rows.filter(r => !!r['_flagged']) : rows,
    [rows, showFlaggedOnly],
  );

  const searchFiltered = useMemo(() => {
    if (!query) return flagFiltered;
    const q = query.toLowerCase();
    return flagFiltered.filter(r =>
      columns.some(c => String(r[c] ?? '').toLowerCase().includes(q))
    );
  }, [flagFiltered, query, columns]);

  const filtered = useMemo(() => {
    if (!sortCol) return searchFiltered;
    return [...searchFiltered].sort((a, b) => {
      const av = a[sortCol], bv = b[sortCol];
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      const na = Number(av), nb = Number(bv);
      if (Number.isFinite(na) && Number.isFinite(nb))
        return sortDir === 'asc' ? na - nb : nb - na;
      return sortDir === 'asc'
        ? String(av).localeCompare(String(bv))
        : String(bv).localeCompare(String(av));
    });
  }, [searchFiltered, sortCol, sortDir]);

  // ── Virtual scroll window ──────────────────────────────────────────────────
  const visStart    = Math.max(0, Math.floor(scrollTop / ROW_HEIGHT) - SCROLL_BUFFER);
  const visEnd      = Math.min(filtered.length, Math.ceil((scrollTop + containerHeight) / ROW_HEIGHT) + SCROLL_BUFFER);
  const visibleRows = filtered.slice(visStart, visEnd);
  const topPad      = visStart * ROW_HEIGHT;
  const bottomPad   = Math.max(0, (filtered.length - visEnd) * ROW_HEIGHT);

  // ── Sort header handler ────────────────────────────────────────────────────
  const handleSort = (col: string) => {
    if (sortCol === col) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortCol(col); setSortDir('asc'); }
  };

  // ── Edit commit (uses _row_id — safe under any filter/sort) ───────────────
  const commitEdit = useCallback(async () => {
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
        { cache_id: cacheId, row_index: editing.rowId, column: editing.col, value: editValue },
      );
      const raw = r.data.row;
      // Recompute _flagged client-side: use Data_Quality_Flag if present (KKM), else clinical bounds.
      const hasDQF   = 'Data_Quality_Flag' in raw;
      const newFlagged = hasDQF
        ? raw['Data_Quality_Flag'] !== 'Valid'
        : Object.keys(raw).some(col => classifyCell(col, raw[col]) !== 'ok');
      const updatedRow = { ...raw, _row_id: r.data.row_index, _flagged: newFlagged };
      setAllRows(prev => (prev ?? []).map(row =>
        (row['_row_id'] as number) === r.data.row_index ? updatedRow : row
      ));
      setEditing(null);
    } catch {
      setEditing(null);
    } finally {
      setSaving(false);
    }
  }, [editing, cacheId, editValue]);

  const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) || 'http://localhost:8000';

  return (
    <SessionGuard>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

        {/* ── Header ─────────────────────────────────────────────────────── */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{
            fontSize: 12, fontWeight: 600, padding: '3px 10px', borderRadius: 'var(--radius-pill)',
            background: 'var(--surface-2)', border: '1px solid var(--border)',
            color: 'var(--text-secondary)',
          }}>
            {filename}
          </span>
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            {effectiveTotal?.toLocaleString() ?? '—'} {t('rows', 'baris')}
          </span>
          <div style={{ flex: 1 }} />
          <a
            href={`${BASE}/clean/download-xlsx/${cacheId}`}
            target="_blank" rel="noreferrer"
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              background: 'var(--kkm-blue)', border: '1px solid var(--kkm-blue)',
              borderRadius: 'var(--radius-btn)', padding: '7px 14px',
              fontSize: 13, fontWeight: 600, color: 'var(--text-on-navy)',
            }}
          >
            <Download size={14} /> {t('Download XLSX', 'Muat Turun XLSX')}
          </a>
          <a
            href={`${BASE}/clean/download-cached/${cacheId}?fmt=csv`}
            target="_blank" rel="noreferrer"
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              background: 'var(--surface-2)', border: '1px solid var(--border)',
              borderRadius: 'var(--radius-btn)', padding: '7px 14px',
              fontSize: 13, fontWeight: 600, color: 'var(--text-primary)',
            }}
          >
            <Download size={14} /> {t('Download CSV', 'Muat Turun CSV')}
          </a>
        </div>

        {/* ── Edit hint ──────────────────────────────────────────────────── */}
        <div id="explorer-edit-hint" style={{ fontSize: 12, color: 'var(--text-muted)' }}>
          {t(
            'Double-click a cell — or focus it and press Enter — to edit. Enter saves, Esc cancels.',
            'Klik dua kali sel — atau fokus dan tekan Enter — untuk menyunting. Enter simpan, Esc batal.',
          )}
        </div>

        {/* ── Search + Flagged toggle ─────────────────────────────────────── */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <div style={{ position: 'relative', maxWidth: 320, flex: '1 1 200px' }}>
            <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
            <input
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder={t('Search all rows…', 'Cari semua baris…')}
              style={{
                width: '100%', padding: '8px 12px 8px 32px',
                background: 'var(--surface)', border: '1px solid var(--border)',
                borderRadius: 'var(--radius-btn)', fontSize: 13, color: 'var(--text-primary)',
              }}
            />
          </div>

          {flaggedCount > 0 && (
            <button
              onClick={() => setShowFlaggedOnly(v => !v)}
              aria-pressed={showFlaggedOnly}
              style={{
                display: 'flex', alignItems: 'center', gap: 6,
                background: showFlaggedOnly ? 'var(--warning)' : 'var(--surface)',
                border: `1px solid ${showFlaggedOnly ? 'var(--warning)' : 'var(--border)'}`,
                borderRadius: 'var(--radius-btn)', padding: '7px 14px',
                fontSize: 13, fontWeight: 600,
                color: showFlaggedOnly ? 'var(--text-on-navy)' : 'var(--warning)',
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

          {filtered.length !== rows.length && (
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
              {filtered.length.toLocaleString()} {t('of', 'daripada')} {rows.length.toLocaleString()} {t('rows shown', 'baris ditunjuk')}
            </span>
          )}
        </div>

        {/* ── Truncation banner ──────────────────────────────────────────── */}
        {isTruncated && (
          <div
            role="alert"
            aria-live="polite"
            style={{
              display: 'flex', alignItems: 'flex-start', gap: 10,
              background: 'var(--warning-bg)', border: '1px solid var(--warning)',
              borderRadius: 'var(--radius-card)', padding: '10px 14px', fontSize: 13,
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
                `Showing first ${rows.length.toLocaleString()} of ${effectiveTotal!.toLocaleString()} rows. Use Download to reach the rest.`,
                `Menunjukkan ${rows.length.toLocaleString()} daripada ${effectiveTotal!.toLocaleString()} baris. Guna Muat Turun untuk selebihnya.`,
              )}
            </span>
          </div>
        )}

        {/* ── Conditional-formatting legend ──────────────────────────────── */}
        {columns.length > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              {t('Cell highlight', 'Sorotan sel')}:
            </span>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, background: 'var(--danger-bg)', border: '1px solid var(--danger)', borderRadius: 'var(--radius-sm)', padding: '2px 8px', fontSize: 11 }}>
              <span style={{ width: 8, height: 8, borderRadius: 2, background: 'var(--danger)', display: 'inline-block', flexShrink: 0 }} aria-hidden />
              <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{t('Impossible value', 'Nilai mustahil')}</span>
            </span>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, background: 'var(--warning-bg)', border: '1px solid var(--warning)', borderRadius: 'var(--radius-sm)', padding: '2px 8px', fontSize: 11 }}>
              <span style={{ width: 8, height: 8, borderRadius: 2, background: 'var(--warning)', display: 'inline-block', flexShrink: 0 }} aria-hidden />
              <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{t('Out of range / missing', 'Di luar julat / tiada nilai')}</span>
            </span>
          </div>
        )}

        {/* ── Column distribution ─────────────────────────────────────────── */}
        {numericColumns.length > 0 && (
          <div style={{
            background: 'var(--surface)', border: '1px solid var(--border)',
            borderRadius: 'var(--radius-card)', padding: '18px 20px', boxShadow: 'var(--shadow-card)',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
                {t('Column Distribution', 'Taburan Lajur')}
              </span>
              <select
                value={activeHistCol}
                onChange={e => setHistCol(e.target.value)}
                style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', padding: '6px 10px', fontSize: 12, color: 'var(--text-primary)' }}
              >
                {numericColumns.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <ColumnHistogram values={histValues} />
          </div>
        )}

        {/* ── Table with virtual scroll. When fullscreen, the panel is rendered
            through a portal to <body> so its position:fixed anchors to the real
            viewport. Rendered inline, fixed positioning resolves against the
            transformed .page-enter ancestor (a containing block), which shrinks
            the overlay to the page content box — same trap FocusOverlay avoids. ── */}
        {(() => {
        const tablePanel = (
        <div style={{
          background: 'var(--surface)', border: '1px solid var(--border)',
          borderRadius: 'var(--radius-card)', boxShadow: 'var(--shadow-card)', overflow: 'hidden',
          ...(fullscreen ? {
            position: 'fixed', inset: 0, zIndex: 1000, borderRadius: 0,
            display: 'flex', flexDirection: 'column',
          } : {}),
        }}>
          {/* ── Table toolbar (fullscreen toggle; search/flagged surfaced in overlay) ── */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap',
            padding: '8px 12px', borderBottom: '1px solid var(--border)',
            background: 'var(--surface-2)', flexShrink: 0,
          }}>
            {fullscreen && (
              <>
                <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)' }}>{filename}</span>
                <div style={{ position: 'relative', maxWidth: 280, flex: '1 1 180px' }}>
                  <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
                  <input
                    value={query}
                    onChange={e => setQuery(e.target.value)}
                    placeholder={t('Search all rows…', 'Cari semua baris…')}
                    style={{
                      width: '100%', padding: '6px 10px 6px 30px',
                      background: 'var(--surface)', border: '1px solid var(--border)',
                      borderRadius: 'var(--radius-btn)', fontSize: 12.5, color: 'var(--text-primary)',
                    }}
                  />
                </div>
                {flaggedCount > 0 && (
                  <button
                    onClick={() => setShowFlaggedOnly(v => !v)}
                    aria-pressed={showFlaggedOnly}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 6,
                      background: showFlaggedOnly ? 'var(--warning)' : 'var(--surface)',
                      border: `1px solid ${showFlaggedOnly ? 'var(--warning)' : 'var(--border)'}`,
                      borderRadius: 'var(--radius-btn)', padding: '6px 12px',
                      fontSize: 12.5, fontWeight: 600,
                      color: showFlaggedOnly ? 'var(--text-on-navy)' : 'var(--warning)',
                      cursor: 'pointer', whiteSpace: 'nowrap', flexShrink: 0,
                    }}
                  >
                    <AlertTriangle size={13} aria-hidden />
                    {showFlaggedOnly
                      ? t(`Flagged only (${flaggedCount})`, `Bermasalah sahaja (${flaggedCount})`)
                      : t(`Show flagged (${flaggedCount})`, `Tunjuk bermasalah (${flaggedCount})`)}
                  </button>
                )}
              </>
            )}
            <div style={{ flex: 1 }} />
            <button
              onClick={() => setFullscreen(v => !v)}
              aria-pressed={fullscreen}
              title={fullscreen ? t('Exit full screen (Esc)', 'Keluar skrin penuh (Esc)') : t('Full screen', 'Skrin penuh')}
              style={{
                display: 'flex', alignItems: 'center', gap: 6,
                background: 'var(--surface)', border: '1px solid var(--border)',
                borderRadius: 'var(--radius-btn)', padding: '6px 12px',
                fontSize: 12.5, fontWeight: 600, color: 'var(--text-primary)',
                cursor: 'pointer', whiteSpace: 'nowrap', flexShrink: 0,
              }}
            >
              {fullscreen ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
              {fullscreen ? t('Exit full screen', 'Keluar skrin penuh') : t('Full screen', 'Skrin penuh')}
            </button>
          </div>
          {fetchError ? (
            <ErrorRetry
              message={t('Could not load the data.', 'Tidak dapat memuatkan data.')}
              onRetry={loadRows}
            />
          ) : fetchLoading && columns.length === 0 ? (
            <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>
              {t('Loading…', 'Memuatkan…')}
            </div>
          ) : columns.length === 0 ? (
            <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>
              {t('No data available.', 'Tiada data tersedia.')}
            </div>
          ) : (
            <>
              {/* Scrollable container — sticky thead + virtual tbody */}
              <div
                ref={scrollRef}
                style={{ height: containerHeight, overflowY: 'auto', overflowX: 'auto' }}
                onScroll={e => setScrollTop((e.currentTarget as HTMLDivElement).scrollTop)}
              >
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                  <thead>
                    <tr style={{ background: 'var(--surface-2)' }}>
                      {columns.map(c => (
                        <th
                          key={c}
                          onClick={() => handleSort(c)}
                          aria-sort={sortCol === c ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'}
                          style={{
                            position: 'sticky', top: 0, zIndex: 2,
                            padding: '10px 14px', textAlign: 'left', fontWeight: 600,
                            fontSize: 11, color: 'var(--text-secondary)', letterSpacing: '0.05em',
                            borderBottom: '1px solid var(--border)', whiteSpace: 'nowrap',
                            cursor: 'pointer', userSelect: 'none',
                            transition: 'background var(--transition)',
                            background: sortCol === c ? 'var(--surface-3)' : 'var(--surface-2)',
                          }}
                        >
                          {c}
                          {sortCol === c && (
                            <span style={{ marginLeft: 4, color: 'var(--kkm-blue)', fontWeight: 700 }} aria-hidden>
                              {sortDir === 'asc' ? '↑' : '↓'}
                            </span>
                          )}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {/* Top spacer for virtual scroll */}
                    {topPad > 0 && (
                      <tr style={{ height: topPad }} aria-hidden>
                        <td colSpan={columns.length} style={{ padding: 0, border: 'none' }} />
                      </tr>
                    )}

                    {visibleRows.map((row) => {
                      const rowId = row['_row_id'] as number;
                      return (
                        <tr
                          key={rowId}
                          style={{
                            height: ROW_HEIGHT,
                            borderBottom: '1px solid var(--border)',
                          }}
                        >
                          {columns.map(c => {
                            const isEditing = editing?.rowId === rowId && editing?.col === c;
                            const flag      = classifyCell(c, row[c]);
                            const isNumeric = numericColumns.includes(c);
                            const flagLabel = flag === 'danger'
                              ? t('Impossible value', 'Nilai mustahil')
                              : flag === 'warn'
                                ? t('Out of range or missing', 'Di luar julat atau tiada nilai')
                                : undefined;
                            return (
                              <td
                                key={c}
                                className={`explorer-cell${!isEditing ? ' editable' : ''}`}
                                tabIndex={!isEditing ? 0 : undefined}
                                aria-describedby={!isEditing ? 'explorer-edit-hint' : undefined}
                                aria-label={flagLabel ? `${c}: ${String(row[c] ?? '')} — ${flagLabel}` : undefined}
                                onDoubleClick={() => {
                                  setEditing({ rowId, col: c });
                                  setEditValue(row[c] == null ? '' : String(row[c]));
                                  setEditError('');
                                }}
                                onKeyDown={e => {
                                  if (isEditing) return;
                                  if (e.key === 'Enter' || e.key === 'F2') {
                                    e.preventDefault();
                                    setEditing({ rowId, col: c });
                                    setEditValue(row[c] == null ? '' : String(row[c]));
                                    setEditError('');
                                  }
                                }}
                                style={{
                                  padding: '0 14px', height: ROW_HEIGHT,
                                  color: 'var(--text-primary)',
                                  fontFamily: 'var(--font-mono)', whiteSpace: 'nowrap',
                                  textAlign: isNumeric ? 'right' : 'left',
                                  verticalAlign: 'middle',
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
                                      aria-describedby={editError ? `edit-err-${rowId}-${c}` : undefined}
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
                                        borderRadius: 'var(--radius-sm)', background: 'var(--surface)', color: 'var(--text-primary)',
                                      }}
                                    />
                                    {editError && (
                                      <span
                                        id={`edit-err-${rowId}-${c}`}
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
                                    <Pencil className="edit-icon" size={11} style={{ color: 'var(--kkm-sky)' }} aria-hidden />
                                  </span>
                                )}
                              </td>
                            );
                          })}
                        </tr>
                      );
                    })}

                    {/* Bottom spacer for virtual scroll */}
                    {bottomPad > 0 && (
                      <tr style={{ height: bottomPad }} aria-hidden>
                        <td colSpan={columns.length} style={{ padding: 0, border: 'none' }} />
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>

              {/* Row count footer */}
              <div style={{
                padding: '6px 14px', borderTop: '1px solid var(--border)',
                fontSize: 11, color: 'var(--text-muted)', background: 'var(--surface-2)',
              }}>
                {filtered.length === rows.length
                  ? t(`${rows.length.toLocaleString()} rows`, `${rows.length.toLocaleString()} baris`)
                  : t(
                    `${filtered.length.toLocaleString()} of ${rows.length.toLocaleString()} rows`,
                    `${filtered.length.toLocaleString()} daripada ${rows.length.toLocaleString()} baris`,
                  )
                }
              </div>
            </>
          )}
        </div>
        );
        return fullscreen ? createPortal(tablePanel, document.body) : tablePanel;
        })()}

      </div>
    </SessionGuard>
  );
}
