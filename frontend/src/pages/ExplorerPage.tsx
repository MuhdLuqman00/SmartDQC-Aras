import React, { useState, useCallback } from 'react';
import { api } from '../api/client';
import { useLang } from '../context/LanguageContext';

interface ColumnProfile {
  name: string;
  null_count: number;
  null_percent: number;
  unique_count: number;
  min: unknown;
  max: unknown;
  mean?: number;
  sample_values: unknown[];
}

interface EDAResponse {
  cache_id: string;
  summary: Record<string, unknown>;
  issues: string[];
  indicators: Record<string, unknown>;
  columns: ColumnProfile[];
}

export function ExplorerPage() {
  const { t } = useLang();
  const [eda, setEda] = useState<EDAResponse | null>(null);
  const [selectedCol, setSelectedCol] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<0 | 1 | 2>(0);
  const [page, setPage] = useState<number>(1);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [dataType, setDataType] = useState<string>('auto');
  const [dragOver, setDragOver] = useState<boolean>(false);

  const runEda = useCallback(
    (file: File) => {
      setError(null);
      setLoading(true);
      setEda(null);
      setSelectedCol(null);
      setPage(1);
      const fd = new FormData();
      fd.append('file', file);
      fd.append('data_type', dataType);
      api
        .post<EDAResponse>('/eda/run', fd)
        .then(r => {
          setEda(r.data);
          setSelectedCol(r.data.columns[0]?.name ?? null);
        })
        .catch(() => setError('Gagal menjalankan analisis.'))
        .finally(() => setLoading(false));
    },
    [dataType],
  );

  const onDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setDragOver(false);
      const f = e.dataTransfer.files[0];
      if (f) runEda(f);
    },
    [runEda],
  );

  const onInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const f = e.target.files?.[0];
      if (f) runEda(f);
    },
    [runEda],
  );

  // ── Tab 0: sample rows ──────────────────────────────────────────────────────
  const sampleRows = React.useMemo<unknown[]>(() => {
    if (!eda) return [];
    const raw = eda.summary['sample'];
    if (Array.isArray(raw)) return raw as unknown[];
    return [];
  }, [eda]);

  const PAGE_SIZE = 50;
  const totalPages = Math.max(1, Math.ceil(sampleRows.length / PAGE_SIZE));
  const pagedRows = sampleRows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  // ── Helpers ─────────────────────────────────────────────────────────────────
  const colProfile = eda?.columns.find(c => c.name === selectedCol) ?? null;

  // ── Render ──────────────────────────────────────────────────────────────────
  return (
    <div style={s.page}>
      <h1 style={s.h1}>{t('Data Explorer', 'Penjelajah Data')}</h1>

      {/* Dropzone */}
      <div
        style={{ ...s.dropzone, ...(dragOver ? s.dropzoneActive : {}) }}
        onDrop={onDrop}
        onDragOver={e => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
      >
        <span style={s.dropText}>
          {t('Drag CSV / Excel here or', 'Seret fail CSV / Excel ke sini atau')}{' '}
          <label style={s.browseLink}>
            <input
              type="file"
              accept=".csv,.xlsx"
              style={{ display: 'none' }}
              onChange={onInputChange}
            />
            {t('browse', 'semak imbas')}
          </label>
        </span>
        <div style={s.dropSub}>
          {t('Data type:', 'Jenis data:')}{' '}
          <select
            value={dataType}
            onChange={e => setDataType(e.target.value)}
            style={s.select}
            onClick={e => e.stopPropagation()}
          >
            <option value="auto">Auto</option>
            <option value="clinical">{t('Clinical', 'Klinikal')}</option>
            <option value="financial">{t('Financial', 'Kewangan')}</option>
            <option value="generic">{t('Generic', 'Generik')}</option>
          </select>
        </div>
      </div>

      {/* Loading */}
      {loading && (
        <div style={s.centred}>
          <span style={s.loadingText}>{t('Loading...', 'Memuatkan...')}</span>
        </div>
      )}

      {/* Error */}
      {error && !loading && (
        <div style={s.errorBanner}>{error}</div>
      )}

      {/* Main layout */}
      {eda && !loading && (
        <div style={s.layout}>
          {/* Left panel — column selector */}
          <div style={s.sidebar}>
            <div style={s.sideTitle}>{t('Columns', 'Lajur')} ({eda.columns.length})</div>
            <div style={s.colList}>
              {eda.columns.map(col => (
                <button
                  key={col.name}
                  style={{
                    ...s.colBtn,
                    ...(selectedCol === col.name ? s.colBtnActive : {}),
                    transition: 'all 0.15s ease',
                  }}
                  onClick={() => setSelectedCol(col.name)}
                >
                  <span style={s.colName}>{col.name}</span>
                  <span style={s.colNull}>{col.null_percent.toFixed(1)}%</span>
                </button>
              ))}
            </div>
          </div>

          {/* Right main area */}
          <div style={s.main}>
            {/* Tabs */}
            <div style={s.tabs}>
              {([t('Raw Data','Data Mentah'), t('Clean Data','Data Bersih'), t('Statistical Profile','Profil Statistik')] as const).map(
                (label, idx) => (
                  <button
                    key={label}
                    style={{
                      ...s.tab,
                      ...(activeTab === idx ? s.tabActive : {}),
                      transition: 'all 0.15s ease',
                    }}
                    onClick={() => setActiveTab(idx as 0 | 1 | 2)}
                  >
                    {label}
                  </button>
                ),
              )}
            </div>

            <div style={s.tabBody}>
              {/* Tab 0 — Data Mentah */}
              {activeTab === 0 && (
                <>
                  {pagedRows.length === 0 ? (
                    <div style={s.emptyMsg}>
                      {t('Raw data not available for display.', 'Data mentah tidak tersedia untuk paparan.')}
                    </div>
                  ) : (
                    <>
                      <div style={s.tableWrap}>
                        <table style={s.table}>
                          <thead>
                            <tr>
                              {eda.columns.map(c => (
                                <th key={c.name} style={s.th}>{c.name}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {pagedRows.map((row, ri) => {
                              const cells = Array.isArray(row)
                                ? (row as unknown[])
                                : eda.columns.map(c => (row as Record<string, unknown>)[c.name]);
                              return (
                                <tr key={ri}>
                                  {cells.map((cell, ci) => (
                                    <td key={ci} style={s.td}>
                                      {cell == null ? '—' : String(cell)}
                                    </td>
                                  ))}
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                      {totalPages > 1 && (
                        <div style={s.pagination}>
                          <button
                            style={{ ...s.pgBtn, transition: 'all 0.15s ease' }}
                            disabled={page === 1}
                            onClick={() => setPage(p => Math.max(1, p - 1))}
                          >
                            ← {t('Prev', 'Sebelum')}
                          </button>
                          <span style={s.pgInfo}>
                            {t('Page', 'Halaman')} {page} / {totalPages}
                          </span>
                          <button
                            style={{ ...s.pgBtn, transition: 'all 0.15s ease' }}
                            disabled={page === totalPages}
                            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                          >
                            {t('Next', 'Seterus')} →
                          </button>
                        </div>
                      )}
                    </>
                  )}
                </>
              )}

              {/* Tab 1 — Clean Data */}
              {activeTab === 1 && (
                <div style={s.infoMsg}>
                  {t('Clean data requires a separate cache_id. Please run cleaning first.', 'Data bersih memerlukan cache_id berasingan. Sila jalankan pembersihan terlebih dahulu.')}
                </div>
              )}

              {/* Tab 2 — Profil Statistik */}
              {activeTab === 2 && (
                <>
                  {colProfile ? (
                    <ProfileCard col={colProfile} />
                  ) : (
                    <>
                      {selectedCol && !colProfile ? (
                        <div style={s.emptyMsg}>{t('Select a column from the left panel.', 'Pilih lajur dari panel kiri.')}</div>
                      ) : !selectedCol ? (
                        <div style={s.emptyMsg}>{t('Select a column from the left panel.', 'Pilih lajur dari panel kiri.')}</div>
                      ) : null}
                      <div style={s.profileGrid}>
                        {eda.columns.map(c => (
                          <ProfileCard key={c.name} col={c} />
                        ))}
                      </div>
                    </>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── ProfileCard ──────────────────────────────────────────────────────────────

function ProfileCard({ col }: { col: ColumnProfile }) {
  const samples = col.sample_values
    .slice(0, 5)
    .map(v => String(v))
    .join(', ');

  const { t } = useLang();
  return (
    <div style={pc.card}>
      <div style={pc.title}>{col.name}</div>
      <div style={pc.grid}>
        <StatBox label={t('Null Count', 'Nilai Null')} value={String(col.null_count)} />
        <StatBox label="% Null" value={`${col.null_percent.toFixed(1)}%`} />
        <StatBox label={t('Unique', 'Unik')} value={String(col.unique_count)} />
        {col.min != null && <StatBox label={t('Min', 'Min')} value={String(col.min)} />}
        {col.max != null && <StatBox label={t('Max', 'Maks')} value={String(col.max)} />}
        {col.mean != null && (
          <StatBox label={t('Mean', 'Purata')} value={col.mean.toFixed(2)} />
        )}
      </div>
      {samples && (
        <div style={pc.samplesRow}>
          <span style={pc.samplesLabel}>{t('Sample: ', 'Sampel: ')}</span>
          <span style={pc.samplesVal}>{samples}</span>
        </div>
      )}
    </div>
  );
}

function StatBox({ label, value }: { label: string; value: string }) {
  return (
    <div style={sb.box}>
      <div style={sb.label}>{label}</div>
      <div style={sb.value}>{value}</div>
    </div>
  );
}

// ── Styles ───────────────────────────────────────────────────────────────────

const s: Record<string, React.CSSProperties> = {
  page: { display: 'flex', flexDirection: 'column', height: '100%', gap: 20 },
  h1: { margin: 0, fontSize: 22, fontWeight: 700, color: 'var(--text-primary)' },

  dropzone: {
    border: '0.5px dashed var(--border)',
    borderRadius: 8,
    padding: '28px 24px',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 10,
    background: 'var(--surface)',
    cursor: 'pointer',
    transition: 'all 0.15s ease',
  },
  dropzoneActive: {
    borderColor: 'var(--blue)',
    background: 'var(--surface-2)',
  },
  dropText: { fontSize: 14, color: 'var(--text-secondary)' },
  browseLink: {
    color: 'var(--blue)',
    fontWeight: 600,
    cursor: 'pointer',
    textDecoration: 'underline',
  },
  dropSub: { fontSize: 12, color: 'var(--text-muted)', display: 'flex', gap: 6, alignItems: 'center' },
  select: {
    fontSize: 12,
    color: 'var(--text-primary)',
    background: 'var(--surface-2)',
    border: '0.5px solid var(--border)',
    borderRadius: 4,
    padding: '2px 6px',
    cursor: 'pointer',
  },

  centred: { display: 'flex', justifyContent: 'center', padding: '40px 0' },
  loadingText: { fontSize: 14, color: 'var(--text-muted)' },

  errorBanner: {
    background: 'var(--danger-bg)',
    color: 'var(--danger)',
    border: '0.5px solid var(--danger)',
    borderRadius: 6,
    padding: '12px 16px',
    fontSize: 13,
  },

  layout: { display: 'flex', gap: 16, flex: 1, minHeight: 0 },

  sidebar: {
    width: 200,
    flexShrink: 0,
    border: '0.5px solid var(--border)',
    borderRadius: 8,
    background: 'var(--surface)',
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
  },
  sideTitle: {
    fontSize: 11,
    fontWeight: 600,
    textTransform: 'uppercase' as const,
    letterSpacing: '0.06em',
    color: 'var(--text-muted)',
    padding: '12px 14px',
    borderBottom: '0.5px solid var(--border)',
    flexShrink: 0,
  },
  colList: { overflowY: 'auto', flex: 1 },
  colBtn: {
    width: '100%',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '9px 14px',
    background: 'none',
    border: 'none',
    borderBottom: '0.5px solid var(--border)',
    fontSize: 13,
    color: 'var(--text-primary)',
    cursor: 'pointer',
    textAlign: 'left' as const,
  },
  colBtnActive: {
    background: 'var(--navy)',
    color: '#fff',
  },
  colName: {
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap' as const,
    maxWidth: 120,
  },
  colNull: {
    fontSize: 10,
    color: 'var(--text-muted)',
    flexShrink: 0,
  },

  main: {
    flex: 1,
    border: '0.5px solid var(--border)',
    borderRadius: 8,
    background: 'var(--surface)',
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
    minWidth: 0,
  },
  tabs: { display: 'flex', borderBottom: '0.5px solid var(--border)', flexShrink: 0 },
  tab: {
    padding: '12px 18px',
    background: 'none',
    border: 'none',
    borderBottom: '2px solid transparent',
    fontSize: 13,
    fontWeight: 500,
    color: 'var(--text-secondary)',
    cursor: 'pointer',
  },
  tabActive: {
    color: 'var(--navy)',
    fontWeight: 700,
    borderBottomColor: 'var(--navy)',
  },
  tabBody: { flex: 1, overflowY: 'auto', padding: 20 },

  emptyMsg: { fontSize: 13, color: 'var(--text-muted)', padding: '20px 0' },
  infoMsg: {
    fontSize: 13,
    color: 'var(--text-secondary)',
    background: 'var(--surface-2)',
    border: '0.5px solid var(--border)',
    borderRadius: 6,
    padding: '16px 18px',
  },

  tableWrap: { overflowX: 'auto' },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: 12 },
  th: {
    padding: '9px 11px',
    background: 'var(--surface-2)',
    borderBottom: '0.5px solid var(--border)',
    fontWeight: 600,
    color: 'var(--text-secondary)',
    textAlign: 'left' as const,
    whiteSpace: 'nowrap' as const,
  },
  td: {
    padding: '7px 11px',
    borderBottom: '0.5px solid var(--border)',
    color: 'var(--text-primary)',
    whiteSpace: 'nowrap' as const,
    maxWidth: 180,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
  },

  pagination: {
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    marginTop: 14,
    justifyContent: 'flex-end',
  },
  pgBtn: {
    padding: '6px 14px',
    background: 'var(--surface-2)',
    border: '0.5px solid var(--border)',
    borderRadius: 5,
    fontSize: 12,
    color: 'var(--text-primary)',
    cursor: 'pointer',
  },
  pgInfo: { fontSize: 12, color: 'var(--text-muted)' },

  profileGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(2, 1fr)',
    gap: 14,
  },
};

const pc: Record<string, React.CSSProperties> = {
  card: {
    border: '0.5px solid var(--border)',
    borderRadius: 8,
    padding: '16px 18px',
    background: 'var(--bg)',
    display: 'flex',
    flexDirection: 'column',
    gap: 12,
  },
  title: { fontSize: 14, fontWeight: 700, color: 'var(--text-primary)' },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 },
  samplesRow: { fontSize: 12, color: 'var(--text-secondary)', wordBreak: 'break-all' as const },
  samplesLabel: { fontWeight: 600 },
  samplesVal: { fontFamily: 'var(--font-mono, monospace)', color: 'var(--text-primary)' },
};

const sb: Record<string, React.CSSProperties> = {
  box: {
    background: 'var(--surface)',
    border: '0.5px solid var(--border)',
    borderRadius: 6,
    padding: '10px 12px',
  },
  label: {
    fontSize: 10,
    fontWeight: 600,
    textTransform: 'uppercase' as const,
    letterSpacing: '0.06em',
    color: 'var(--text-muted)',
    marginBottom: 4,
  },
  value: { fontSize: 18, fontWeight: 700, color: 'var(--navy)' },
};
