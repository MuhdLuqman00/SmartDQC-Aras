import React, { useState, useMemo, useEffect, useCallback, useRef, useLayoutEffect } from 'react';
import { Download, Search, Pencil, AlertTriangle, Maximize2, Minimize2, ChevronDown, ChevronRight } from 'lucide-react';
import { api } from '../api/client';
import { useLang } from '../context/LanguageContext';
import { useSession } from '../context/SessionContext';
import { SessionGuard } from '../components/SessionGuard';
import { ColumnHistogram } from '../components/ColumnHistogram';
import { ErrorRetry } from '../components/ErrorRetry';
import { CellFlagTooltip } from '../components/CellFlagTooltip';
import { classifyCell, cellFlagStyle, validateEdit, describeCell, isBmiCategoryCol, classifyBmiCategoryCell, describeBmiCategoryCell, type CellReason, type ClinicalThresholds, DEFAULT_CELL_THRESHOLDS } from '../utils/cellFlags';

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
  const [showFlaggedOnly,    setShowFlaggedOnly]    = useState(false);
  const [showAnalyzableOnly, setShowAnalyzableOnly] = useState(false);

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
  const [histCol, setHistCol]   = useState('');
  const [histOpen, setHistOpen] = useState(false);

  // ── Flag tooltip state (hover/focus on a flagged cell) ──────────────────────
  const [cellTip, setCellTip] = useState<{ reason: CellReason; rect: DOMRect } | null>(null);

  // ── Live clinical thresholds from settings API ─────────────────────────────
  const [cellThresholds, setCellThresholds] = useState<ClinicalThresholds>(DEFAULT_CELL_THRESHOLDS);

  // ── Expand state ────────────────────────────────────────────────────────────
  // Expanded keeps the table in normal page flow (sidebar/top-bar stay visible)
  // but grows the scroll window down to the viewport bottom. The height is
  // measured from the scroll container's own top — no fixed overlay, so the
  // transformed .page-enter ancestor never traps it.
  const [expanded, setExpanded] = useState(false);
  const [measuredH, setMeasuredH] = useState(CONTAINER_HEIGHT);

  useLayoutEffect(() => {
    if (!expanded) return;
    const recompute = () => {
      const el = scrollRef.current;
      if (!el) return;
      const top = el.getBoundingClientRect().top;
      // Reserve the footer row (~30px) and a little breathing room at the page bottom.
      setMeasuredH(Math.max(360, Math.floor(window.innerHeight - top - 58)));
    };
    recompute();
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setExpanded(false); };
    window.addEventListener('resize', recompute);
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('resize', recompute);
      window.removeEventListener('keydown', onKey);
    };
  }, [expanded]);

  const containerHeight = expanded ? measuredH : CONTAINER_HEIGHT;

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

  useEffect(() => {
    type RangeEntry = { type: string; effective_min?: number; effective_max?: number; effective_value?: number };
    api.get<Record<string, RangeEntry>>('/config/clinical-ranges').then(r => {
      const d = r.data;
      const pick = (key: string, field: 'effective_min' | 'effective_max' | 'effective_value', fallback: number) =>
        d[key]?.[field] ?? fallback;
      setCellThresholds({
        beratImpossibleLow:   pick('br02_weight_impossible', 'effective_min',  DEFAULT_CELL_THRESHOLDS.beratImpossibleLow),
        beratImpossibleHigh:  pick('br02_weight_impossible', 'effective_max',  DEFAULT_CELL_THRESHOLDS.beratImpossibleHigh),
        beratClinicalLow:     pick('school_weight',          'effective_min',  DEFAULT_CELL_THRESHOLDS.beratClinicalLow),
        beratClinicalHigh:    pick('school_weight',          'effective_max',  DEFAULT_CELL_THRESHOLDS.beratClinicalHigh),
        tinggiImpossibleLow:  pick('br03_height_impossible', 'effective_min',  DEFAULT_CELL_THRESHOLDS.tinggiImpossibleLow),
        tinggiImpossibleHigh: pick('br03_height_impossible', 'effective_max',  DEFAULT_CELL_THRESHOLDS.tinggiImpossibleHigh),
        tinggiClinicalLow:    pick('school_height',          'effective_min',  DEFAULT_CELL_THRESHOLDS.tinggiClinicalLow),
        tinggiClinicalHigh:   pick('school_height',          'effective_max',  DEFAULT_CELL_THRESHOLDS.tinggiClinicalHigh),
        bmiUnderweight:       pick('bmi_underweight',        'effective_value', DEFAULT_CELL_THRESHOLDS.bmiUnderweight),
        bmiObese:             pick('bmi_obese',              'effective_value', DEFAULT_CELL_THRESHOLDS.bmiObese),
      });
    }).catch(() => {}); // silently keep defaults on failure
  }, []);

  // Reset scroll to top whenever the filter/sort changes
  useEffect(() => {
    setScrollTop(0);
    if (scrollRef.current) scrollRef.current.scrollTop = 0;
  }, [query, showFlaggedOnly, showAnalyzableOnly, sortCol, sortDir]);

  // ── Derived values ─────────────────────────────────────────────────────────
  const rows = allRows ?? [];

  // _row_id, _flagged, _exclude_label are internal metadata — hide from visible column list.
  const columns = useMemo(
    () => rows.length > 0
      ? Object.keys(rows[0]).filter(c => !c.startsWith('_'))
      : [],
    [rows],
  );

  const effectiveTotal = serverTotal ?? rowCount;
  const isTruncated    = effectiveTotal != null && rows.length < effectiveTotal;

  const flaggedCount = useMemo(
    () => rows.filter(r => !!r['_flagged']).length,
    [rows],
  );

  const excludedCount = useMemo(
    () => rows.filter(r => r['_exclude_label'] != null).length,
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

  // ── Filter pipeline: flagged → analyzable → search → sort ─────────────────
  const flagFiltered = useMemo(
    () => showFlaggedOnly ? rows.filter(r => !!r['_flagged']) : rows,
    [rows, showFlaggedOnly],
  );

  // 4e: display-only filter; _row_id positions are unchanged so edits stay safe
  const analyzableFiltered = useMemo(
    () => showAnalyzableOnly ? flagFiltered.filter(r => r['_exclude_label'] == null) : flagFiltered,
    [flagFiltered, showAnalyzableOnly],
  );

  const searchFiltered = useMemo(() => {
    if (!query) return analyzableFiltered;
    const q = query.toLowerCase();
    return analyzableFiltered.filter(r =>
      columns.some(c => String(r[c] ?? '').toLowerCase().includes(q))
    );
  }, [analyzableFiltered, query, columns]);

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
    const validation = validateEdit(editing.col, editValue, cellThresholds);
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
        : Object.keys(raw).some(col => classifyCell(col, raw[col], cellThresholds) !== 'ok');
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

        {/* ── Header (hidden in expanded mode to free vertical room) ───────── */}
        {!expanded && (
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
              href={`${BASE}/clean/download-xlsx/${cacheId}?view=full`}
              target="_blank" rel="noreferrer"
              style={{
                display: 'flex', alignItems: 'center', gap: 6,
                background: 'var(--surface-2)', border: '1px solid var(--border)',
                borderRadius: 'var(--radius-btn)', padding: '7px 14px',
                fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)',
              }}
            >
              <Download size={14} /> {t('Full + flagged (XLSX)', 'Penuh + ditanda (XLSX)')}
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
        )}

        {/* ── Truncation banner (hidden in expanded mode) ────────────────── */}
        {!expanded && isTruncated && (
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

        {/* ── Column distribution (collapsible; hidden in expanded mode) ──── */}
        {!expanded && numericColumns.length > 0 && (
          <div style={{
            background: 'var(--surface)', border: '1px solid var(--border)',
            borderRadius: 'var(--radius-card)', boxShadow: 'var(--shadow-card)', overflow: 'hidden',
          }}>
            <button
              onClick={() => setHistOpen(v => !v)}
              aria-expanded={histOpen}
              style={{
                display: 'flex', alignItems: 'center', gap: 8, width: '100%',
                padding: '12px 18px', background: 'transparent', border: 'none',
                cursor: 'pointer', textAlign: 'left',
                fontSize: 13, fontWeight: 600, color: 'var(--text-primary)',
              }}
            >
              {histOpen ? <ChevronDown size={15} aria-hidden /> : <ChevronRight size={15} aria-hidden />}
              {t('Column Distribution', 'Taburan Lajur')}
              {!histOpen && (
                <span style={{ fontSize: 12, fontWeight: 400, color: 'var(--text-muted)' }}>
                  — {activeHistCol}
                </span>
              )}
            </button>
            {histOpen && (
              <div style={{ padding: '0 20px 18px' }}>
                <div style={{ marginBottom: 12 }}>
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
          </div>
        )}

        {/* ── Table panel. Stays in normal page flow in both modes; expanded just
            grows the scroll window down to the viewport bottom (height measured in
            the effect above), so the sidebar/top-bar remain visible. The unified
            toolbar below carries search, flagged filter, the highlight legend and
            the expand toggle so the controls travel with the data, not above it. ── */}
        <div style={{
          background: 'var(--surface)', border: '1px solid var(--border)',
          borderRadius: expanded ? 0 : 'var(--radius-card)',
          boxShadow: expanded ? 'none' : 'var(--shadow-card)', overflow: 'hidden',
        }}>
          {/* ── Unified table toolbar (both modes) ───────────────────────── */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap',
            padding: '8px 12px', borderBottom: '1px solid var(--border)',
            background: 'var(--surface-2)', flexShrink: 0,
          }}>
            <div style={{ position: 'relative', maxWidth: 300, flex: '1 1 180px' }}>
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

            {excludedCount > 0 && (
              <button
                onClick={() => setShowAnalyzableOnly(v => !v)}
                aria-pressed={showAnalyzableOnly}
                style={{
                  display: 'flex', alignItems: 'center', gap: 6,
                  background: showAnalyzableOnly ? 'var(--kkm-blue)' : 'var(--surface)',
                  border: `1px solid ${showAnalyzableOnly ? 'var(--kkm-blue)' : 'var(--border)'}`,
                  borderRadius: 'var(--radius-btn)', padding: '6px 12px',
                  fontSize: 12.5, fontWeight: 600,
                  color: showAnalyzableOnly ? 'var(--text-on-navy)' : 'var(--text-secondary)',
                  cursor: 'pointer', whiteSpace: 'nowrap', flexShrink: 0,
                }}
              >
                {showAnalyzableOnly
                  ? t(`Analyzable only (${rows.length - excludedCount})`, `Boleh analisis sahaja (${rows.length - excludedCount})`)
                  : t(`Hide excluded (${excludedCount})`, `Sembunyikan dikecualikan (${excludedCount})`)}
              </button>
            )}

            {filtered.length !== rows.length && (
              <span style={{ fontSize: 12, color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                {filtered.length.toLocaleString()} / {rows.length.toLocaleString()}
              </span>
            )}

            <div style={{ flex: 1 }} />

            {/* Highlight legend — inline so the meaning of a coloured cell sits
                next to the data instead of in a separate block above it. */}
            {columns.length > 0 && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }} aria-hidden>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 11, color: 'var(--text-secondary)' }}>
                  <span style={{ width: 9, height: 9, borderRadius: 2, background: 'var(--danger)', display: 'inline-block' }} />
                  {t('Impossible', 'Mustahil')}
                </span>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 11, color: 'var(--text-secondary)' }}>
                  <span style={{ width: 9, height: 9, borderRadius: 2, background: 'var(--warning)', display: 'inline-block' }} />
                  {t('Out of range', 'Luar julat')}
                </span>
              </div>
            )}

            <button
              onClick={() => setExpanded(v => !v)}
              aria-pressed={expanded}
              title={expanded ? t('Collapse (Esc)', 'Kuncupkan (Esc)') : t('Expand table', 'Kembangkan jadual')}
              style={{
                display: 'flex', alignItems: 'center', gap: 6,
                background: 'var(--surface)', border: '1px solid var(--border)',
                borderRadius: 'var(--radius-btn)', padding: '6px 12px',
                fontSize: 12.5, fontWeight: 600, color: 'var(--text-primary)',
                cursor: 'pointer', whiteSpace: 'nowrap', flexShrink: 0,
              }}
            >
              {expanded ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
              {expanded ? t('Collapse', 'Kuncup') : t('Expand', 'Kembang')}
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
                      const rowId     = row['_row_id'] as number;
                      const isExcluded = row['_exclude_label'] != null;
                      return (
                        <tr
                          key={rowId}
                          title={isExcluded ? String(row['_exclude_label']) : undefined}
                          style={{
                            height: ROW_HEIGHT,
                            borderBottom: '1px solid var(--border)',
                            opacity: isExcluded ? 0.45 : 1,
                          }}
                        >
                          {columns.map(c => {
                            const isEditing = editing?.rowId === rowId && editing?.col === c;
                            const isBmiCat  = isBmiCategoryCol(c);
                            const flag      = isBmiCat ? classifyBmiCategoryCell(row, cellThresholds)
                                                       : classifyCell(c, row[c], cellThresholds);
                            const reason    = flag === 'ok' ? null
                                            : isBmiCat ? describeBmiCategoryCell(row, cellThresholds)
                                                       : describeCell(c, row[c], cellThresholds);
                            const isNumeric = numericColumns.includes(c);
                            const flagLabel = reason ? t(reason.titleEN, reason.titleBM) : undefined;
                            const showTip = (el: HTMLElement) => {
                              if (reason && !isEditing) setCellTip({ reason, rect: el.getBoundingClientRect() });
                            };
                            return (
                              <td
                                key={c}
                                className={`explorer-cell${!isEditing ? ' editable' : ''}`}
                                tabIndex={!isEditing ? 0 : undefined}
                                aria-describedby={!isEditing ? 'explorer-edit-hint' : undefined}
                                aria-label={flagLabel ? `${c}: ${String(row[c] ?? '')} — ${flagLabel}` : undefined}
                                onMouseEnter={e => showTip(e.currentTarget)}
                                onMouseLeave={() => setCellTip(null)}
                                onFocus={e => showTip(e.currentTarget)}
                                onBlur={() => setCellTip(null)}
                                onDoubleClick={() => {
                                  setCellTip(null);
                                  setEditing({ rowId, col: c });
                                  setEditValue(row[c] == null ? '' : String(row[c]));
                                  setEditError('');
                                }}
                                onKeyDown={e => {
                                  if (isEditing) return;
                                  if (e.key === 'Enter' || e.key === 'F2') {
                                    e.preventDefault();
                                    setCellTip(null);
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

              {/* Footer — edit hint (keeps the #explorer-edit-hint target that
                  cells reference via aria-describedby) + live row count. */}
              <div style={{
                display: 'flex', alignItems: 'center', gap: 12,
                padding: '6px 14px', borderTop: '1px solid var(--border)',
                fontSize: 11, color: 'var(--text-muted)', background: 'var(--surface-2)',
              }}>
                <span id="explorer-edit-hint">
                  {t(
                    'Double-click a cell — or focus it and press Enter — to edit.',
                    'Klik dua kali sel — atau fokus dan tekan Enter — untuk menyunting.',
                  )}
                </span>
                <div style={{ flex: 1 }} />
                <span style={{ whiteSpace: 'nowrap' }}>
                  {filtered.length === rows.length
                    ? t(`${rows.length.toLocaleString()} rows`, `${rows.length.toLocaleString()} baris`)
                    : t(
                      `${filtered.length.toLocaleString()} of ${rows.length.toLocaleString()} rows`,
                      `${filtered.length.toLocaleString()} daripada ${rows.length.toLocaleString()} baris`,
                    )
                  }
                </span>
              </div>
            </>
          )}
        </div>

        {/* Flag explanation tooltip — portaled to <body>, positioned from the
            hovered/focused cell's rect. */}
        {cellTip && (
          <CellFlagTooltip
            reason={cellTip.reason}
            rect={cellTip.rect}
            title={t(cellTip.reason.titleEN, cellTip.reason.titleBM)}
            detail={t(cellTip.reason.detailEN, cellTip.reason.detailBM)}
          />
        )}

      </div>
    </SessionGuard>
  );
}
