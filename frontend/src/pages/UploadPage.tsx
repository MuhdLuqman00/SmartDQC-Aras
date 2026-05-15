import React, { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { useLang } from '../context/LanguageContext';

// ── Types ────────────────────────────────────────────────────────────────────
type SourceType = 'myvass' | 'klinik' | 'auto';
type JoinType   = 'inner' | 'left' | 'right' | 'outer' | 'union';

interface MappingEntry { standard: string; confidence: number; }
interface UploadPreviewResponse {
  cache_id: string;
  rows: number;
  columns: string[];
  sample: Record<string, unknown>[];
  auto_mapping: Record<string, MappingEntry>;
  unmapped_columns: string[];
}
interface JoinPreviewResponse {
  preview: Record<string, unknown>[];
  columns: string[];
  shape: [number, number];
  join_stats: Record<string, number>;
}

// ── Constants ────────────────────────────────────────────────────────────────
const STANDARD_FIELDS = [
  'name','dob','ic','gender','district','state','date_visit','weight','height',
  'muac','oedema','stunting','wasting','underweight','overweight','age_months',
  'ethnicity','mother_id','father_id','notes','Abaikan',
];

const ACCEPT = {
  'text/csv': ['.csv'],
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
};

// ── Sub-components ───────────────────────────────────────────────────────────
interface DropZoneProps {
  onFile: (f: File) => void;
  label: string;
  fileName?: string;
}
function DropZone({ onFile, label, fileName }: DropZoneProps) {
  const { t } = useLang();
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: ACCEPT,
    maxFiles: 1,
    onDrop: (fs) => fs[0] && onFile(fs[0]),
  });
  return (
    <div
      {...getRootProps()}
      style={{
        border: `0.5px dashed ${isDragActive ? 'var(--blue)' : 'var(--border-2)'}`,
        borderRadius: 8,
        padding: '28px 20px',
        textAlign: 'center',
        cursor: 'pointer',
        background: isDragActive ? 'var(--blue-light)' : 'var(--surface)',
        transition: 'all 0.15s ease',
      }}
    >
      <input {...getInputProps()} />
      <div style={{ fontSize: 26, color: 'var(--blue)', marginBottom: 8 }}>↑</div>
      <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>{label}</div>
      {fileName
        ? <div style={{ fontSize: 12, color: 'var(--success)', fontWeight: 500 }}>{fileName}</div>
        : <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>CSV / Excel · {t('Drag & drop or click', 'Seret & lepas atau klik')}</div>
      }
    </div>
  );
}

function ConfBadge({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  let bg = 'var(--danger-bg)';
  let color = 'var(--danger)';
  if (pct >= 80) { bg = 'var(--success-bg)'; color = 'var(--success)'; }
  else if (pct >= 60) { bg = 'var(--warning-bg)'; color = 'var(--warning)'; }
  return (
    <span style={{ padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600, background: bg, color }}>
      {pct}%
    </span>
  );
}

// ── Main Page ────────────────────────────────────────────────────────────────
export function UploadPage() {
  const navigate = useNavigate();
  const { t } = useLang();

  // Tab
  const [activeTab, setActiveTab] = useState<0 | 1 | 2>(0);

  // Shared
  const [sourceType, setSourceType] = useState<SourceType>('auto');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Tab 0 — single
  const [preview, setPreview] = useState<UploadPreviewResponse | null>(null);
  const [columnMap, setColumnMap] = useState<Record<string, string>>({});

  // Tab 1 — merge
  const [mergeFileA, setMergeFileA] = useState<File | null>(null);
  const [mergeFileB, setMergeFileB] = useState<File | null>(null);
  const [mergeShape, setMergeShape] = useState<[number, number] | null>(null);

  // Tab 2 — join
  const [joinType, setJoinType] = useState<JoinType>('inner');
  const [keyCols, setKeyCols] = useState<string>('');
  const [joinPreview, setJoinPreview] = useState<JoinPreviewResponse | null>(null);
  const [leftCacheId, setLeftCacheId] = useState<string>('');
  const [rightCacheId, setRightCacheId] = useState<string>('');
  const [leftFileName, setLeftFileName] = useState<string>('');
  const [rightFileName, setRightFileName] = useState<string>('');

  // ── Tab 0 handlers ────────────────────────────────────────────────────────
  const uploadSingle = useCallback(async (file: File): Promise<void> => {
    setLoading(true);
    setError(null);
    setPreview(null);
    try {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('source_type', sourceType);
      const res = await api.post<UploadPreviewResponse>('/upload/preview', fd);
      setPreview(res.data);
      const map: Record<string, string> = {};
      Object.entries(res.data.auto_mapping).forEach(([col, m]) => { map[col] = m.standard; });
      setColumnMap(map);
    } catch {
      setError('Gagal memuat naik fail.');
    } finally { setLoading(false); }
  }, [sourceType]);

  const continueClean = async (): Promise<void> => {
    if (!preview) return;
    setLoading(true);
    try {
      const fd = new FormData();
      fd.append('cache_id', preview.cache_id);
      fd.append('data_type', sourceType);
      await api.post('/clean/run', fd);
      navigate(`/cleaning?cache_id=${preview.cache_id}`);
    } catch {
      setError('Gagal memulakan pembersihan.');
    } finally { setLoading(false); }
  };

  // ── Tab 1 handlers ────────────────────────────────────────────────────────
  const handleMergeFile = useCallback(async (file: File, slot: 'a' | 'b') => {
    const nextA = slot === 'a' ? file : mergeFileA;
    const nextB = slot === 'b' ? file : mergeFileB;
    if (slot === 'a') setMergeFileA(file);
    else setMergeFileB(file);

    if (!nextA || !nextB) return;

    setLoading(true);
    setError(null);
    try {
      const fd = new FormData();
      // Backend expects files as a list
      fd.append('files', nextA);
      fd.append('files', nextB);
      const res = await api.post<{ total_rows: number; total_columns: number; columns: string[]; preview: unknown[]; auto_mapping: Record<string, string> }>('/upload/merge-preview', fd);
      setMergeShape([res.data.total_rows, res.data.total_columns]);
    } catch {
      setError('Gagal pratonton cantuman.');
    } finally { setLoading(false); }
  }, [mergeFileA, mergeFileB, sourceType]);

  // ── Tab 2 handlers ────────────────────────────────────────────────────────
  const uploadJoinFile = useCallback(async (file: File, side: 'left' | 'right'): Promise<void> => {
    setLoading(true);
    setError(null);
    try {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('source_type', 'auto');
      const res = await api.post<UploadPreviewResponse>('/upload/preview', fd);
      if (side === 'left') { setLeftCacheId(res.data.cache_id); setLeftFileName(file.name); }
      else { setRightCacheId(res.data.cache_id); setRightFileName(file.name); }
    } catch {
      setError('Gagal memuat naik fail join.');
    } finally { setLoading(false); }
  }, []);

  const previewJoin = async (): Promise<void> => {
    if (!leftCacheId || !rightCacheId) { setError('Sila muat naik kedua-dua fail terlebih dahulu.'); return; }
    setLoading(true);
    setError(null);
    try {
      const res = await api.post<JoinPreviewResponse>(
        `/join/preview?join_type=${joinType}&key_cols=${encodeURIComponent(keyCols)}&cache_id_left=${leftCacheId}&cache_id_right=${rightCacheId}`
      );
      setJoinPreview(res.data);
    } catch {
      setError('Gagal pratonton join.');
    } finally { setLoading(false); }
  };

  const runJoin = async (): Promise<void> => {
    if (!leftCacheId || !rightCacheId) { setError('Sila muat naik kedua-dua fail terlebih dahulu.'); return; }
    setLoading(true);
    setError(null);
    try {
      const res = await api.post<{ cache_id: string }>(
        `/join/run?join_type=${joinType}&key_cols=${encodeURIComponent(keyCols)}&cache_id_left=${leftCacheId}&cache_id_right=${rightCacheId}`
      );
      navigate(`/cleaning?cache_id=${res.data.cache_id}`);
    } catch {
      setError('Gagal menjalankan join.');
    } finally { setLoading(false); }
  };

  // ── Tab labels ────────────────────────────────────────────────────────────
  const TABS = [
    t('Single File', 'Fail Tunggal'),
    t('Merge (2 Files)', 'Gabungkan (2 Fail)'),
    t('Join', 'Cantumkan (Join)'),
  ] as const;

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div>
      <h1 style={s.h1}>{t('Upload Dataset', 'Muat Naik Dataset')}</h1>

      {/* Tab header */}
      <div style={s.tabBar}>
        {TABS.map((label, i) => (
          <button
            key={i}
            onClick={() => setActiveTab(i as 0 | 1 | 2)}
            style={{
              ...s.tabBtn,
              background: activeTab === i ? 'var(--navy)' : 'var(--surface-2)',
              color: activeTab === i ? '#ffffff' : 'var(--text-secondary)',
              transition: 'all 0.15s ease',
            }}
          >
            {label}
          </button>
        ))}
      </div>

      <div style={s.body}>
        {/* Error banner */}
        {error && (
          <div style={s.errorBanner}>
            <span style={{ fontWeight: 600 }}>{t('Error:', 'Ralat:')}</span> {error}
            <button onClick={() => setError(null)} style={s.errorClose}>×</button>
          </div>
        )}

        {/* ── Tab 0: Fail Tunggal ─────────────────────────────────────────── */}
        {activeTab === 0 && (
          <>
            {/* Source type selector */}
            <div style={s.srcRow}>
              <span style={s.srcLbl}>{t('Source Type:', 'Jenis Sumber:')}</span>
              {(['myvass', 'klinik', 'auto'] as SourceType[]).map(st => (
                <label key={st} style={s.radioLabel}>
                  <input
                    type="radio"
                    value={st}
                    checked={sourceType === st}
                    onChange={() => setSourceType(st)}
                    style={{ marginRight: 5 }}
                  />
                  {st === 'myvass' ? 'MyVASS' : st === 'klinik' ? t('Health Clinic', 'Klinik Kesihatan') : t('Auto-detect', 'Auto-detect')}
                </label>
              ))}
            </div>

            <DropZone label={t('CSV / Excel File', 'Fail CSV / Excel')} onFile={uploadSingle} />

            {loading && <div style={s.loading}>{t('Processing...', 'Memproses...')}</div>}

            {/* Schema mapping table */}
            {preview && (
              <div style={s.card}>
                <div style={s.cardHeader}>
                  <span style={s.cardTitle}>{t('Schema Map', 'Peta Skema')}</span>
                  <span style={s.cardMeta}>
                    {preview.rows.toLocaleString()} {t('rows', 'baris')} · {preview.columns.length} {t('columns', 'lajur')}
                  </span>
                </div>
                <table style={s.table}>
                  <thead>
                    <tr>
                      <th style={s.th}>{t('Your Column', 'Lajur Anda')}</th>
                      <th style={s.th}>{t('Detected Standard Field', 'Medan Standard Dikesan')}</th>
                      <th style={s.th}>{t('Confidence', 'Keyakinan')}</th>
                      <th style={s.th}>{t('Override', 'Ganti')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(preview.auto_mapping).map(([col, m]) => (
                      <tr key={col} style={s.tr}>
                        <td style={s.td}><code style={s.code}>{col}</code></td>
                        <td style={s.td}>{columnMap[col] ?? m.standard}</td>
                        <td style={s.td}><ConfBadge value={m.confidence} /></td>
                        <td style={s.td}>
                          <select
                            value={columnMap[col] ?? m.standard}
                            onChange={e => setColumnMap(prev => ({ ...prev, [col]: e.target.value }))}
                            style={{ ...s.select, transition: 'all 0.15s ease' }}
                          >
                            {STANDARD_FIELDS.map(f => (
                              <option key={f} value={f}>{f}</option>
                            ))}
                          </select>
                        </td>
                      </tr>
                    ))}
                    {/* Unmapped columns */}
                    {(preview.unmapped_columns ?? []).map(col => (
                      <tr key={col} style={{ ...s.tr, background: 'var(--warning-bg)' }}>
                        <td style={s.td}><code style={s.code}>{col}</code></td>
                        <td style={s.td}><span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>{t('Unmapped', 'Tidak dipetakan')}</span></td>
                        <td style={s.td}><ConfBadge value={0} /></td>
                        <td style={s.td}>
                          <select
                            value={columnMap[col] ?? 'Abaikan'}
                            onChange={e => setColumnMap(prev => ({ ...prev, [col]: e.target.value }))}
                            style={{ ...s.select, transition: 'all 0.15s ease' }}
                          >
                            {STANDARD_FIELDS.map(f => (
                              <option key={f} value={f}>{f}</option>
                            ))}
                          </select>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <div style={s.cardFooter}>
                  <button
                    style={{ ...s.primaryBtn, opacity: loading ? 0.7 : 1, transition: 'all 0.15s ease' }}
                    onClick={continueClean}
                    disabled={loading}
                  >
                    {loading ? t('Processing...', 'Memproses...') : t('Continue to Cleaning →', 'Lanjutkan ke Pembersihan →')}
                  </button>
                </div>
              </div>
            )}
          </>
        )}

        {/* ── Tab 1: Merge ───────────────────────────────────────────────── */}
        {activeTab === 1 && (
          <>
            <div style={s.srcRow}>
              <span style={s.srcLbl}>{t('Source Type:', 'Jenis Sumber:')}</span>
              {(['myvass', 'klinik', 'auto'] as SourceType[]).map(st => (
                <label key={st} style={s.radioLabel}>
                  <input
                    type="radio"
                    value={st}
                    checked={sourceType === st}
                    onChange={() => setSourceType(st)}
                    style={{ marginRight: 5 }}
                  />
                  {st === 'myvass' ? 'MyVASS' : st === 'klinik' ? t('Health Clinic', 'Klinik Kesihatan') : t('Auto-detect', 'Auto-detect')}
                </label>
              ))}
            </div>

            <div style={s.twoCol}>
              <DropZone
                label={t('First File', 'Fail Pertama')}
                fileName={mergeFileA?.name}
                onFile={f => handleMergeFile(f, 'a')}
              />
              <DropZone
                label={t('Second File', 'Fail Kedua')}
                fileName={mergeFileB?.name}
                onFile={f => handleMergeFile(f, 'b')}
              />
            </div>

            {loading && <div style={s.loading}>{t('Processing...', 'Memproses...')}</div>}

            {mergeShape && (
              <div style={s.infoBox}>
                <span style={{ fontWeight: 600 }}>{t('Merge Result:', 'Keputusan Cantuman:')}</span>{' '}
                {mergeShape[0].toLocaleString()} {t('rows', 'baris')} · {mergeShape[1]} {t('columns', 'lajur')}
              </div>
            )}
          </>
        )}

        {/* ── Tab 2: Join ────────────────────────────────────────────────── */}
        {activeTab === 2 && (
          <>
            <div style={s.twoCol}>
              <DropZone
                label={t('Left File', 'Fail Kiri')}
                fileName={leftFileName || undefined}
                onFile={f => uploadJoinFile(f, 'left')}
              />
              <DropZone
                label={t('Right File', 'Fail Kanan')}
                fileName={rightFileName || undefined}
                onFile={f => uploadJoinFile(f, 'right')}
              />
            </div>

            <div style={s.joinCfg}>
              <div>
                <div style={s.fieldLabel}>{t('Join Type', 'Jenis Join')}</div>
                <select
                  value={joinType}
                  onChange={e => setJoinType(e.target.value as JoinType)}
                  style={{ ...s.select, marginTop: 6, transition: 'all 0.15s ease' }}
                >
                  {(['inner','left','right','outer','union'] as JoinType[]).map(jt => (
                    <option key={jt} value={jt}>{jt.toUpperCase()}</option>
                  ))}
                </select>
              </div>
              <div style={{ flex: 1 }}>
                <div style={s.fieldLabel}>{t('Key Columns (comma-separated)', 'Lajur Kunci (dipisah koma)')}</div>
                <input
                  style={{ ...s.input, marginTop: 6, transition: 'all 0.15s ease' }}
                  value={keyCols}
                  onChange={e => setKeyCols(e.target.value)}
                  placeholder="Contoh: ic, district"
                />
              </div>
            </div>

            <div style={{ display: 'flex', gap: 10 }}>
              <button
                style={{ ...s.secondaryBtn, transition: 'all 0.15s ease' }}
                onClick={previewJoin}
                disabled={loading || !leftCacheId || !rightCacheId}
              >
                {t('Preview Join', 'Pratonton Join')}
              </button>
              <button
                style={{ ...s.primaryBtn, transition: 'all 0.15s ease', opacity: (!leftCacheId || !rightCacheId || loading) ? 0.6 : 1 }}
                onClick={runJoin}
                disabled={loading || !leftCacheId || !rightCacheId}
              >
                {loading ? t('Processing...', 'Memproses...') : t('Run Join →', 'Jalankan Join →')}
              </button>
            </div>

            {loading && <div style={s.loading}>{t('Processing...', 'Memproses...')}</div>}

            {joinPreview && (
              <div style={s.card}>
                <div style={s.cardHeader}>
                  <span style={s.cardTitle}>{t('Join Preview', 'Pratonton Join')}</span>
                  <span style={s.cardMeta}>
                    {joinPreview.shape[0].toLocaleString()} {t('rows', 'baris')} · {joinPreview.shape[1]} {t('columns', 'lajur')}
                  </span>
                </div>
                {/* Join stats */}
                {Object.keys(joinPreview.join_stats).length > 0 && (
                  <div style={{ display: 'flex', gap: 16, padding: '12px 20px', borderBottom: '0.5px solid var(--border)', flexWrap: 'wrap' }}>
                    {Object.entries(joinPreview.join_stats).map(([k, v]) => (
                      <div key={k} style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                        <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{k}:</span> {v}
                      </div>
                    ))}
                  </div>
                )}
                <div style={{ overflowX: 'auto' }}>
                  <table style={s.table}>
                    <thead>
                      <tr>
                        {joinPreview.columns.map(col => (
                          <th key={col} style={s.th}>{col}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {joinPreview.preview.slice(0, 5).map((row, i) => (
                        <tr key={i} style={s.tr}>
                          {joinPreview.columns.map(col => (
                            <td key={col} style={s.td}>{String(row[col] ?? '')}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

// ── Styles ───────────────────────────────────────────────────────────────────
const s: Record<string, React.CSSProperties> = {
  h1: {
    margin: '0 0 20px',
    fontSize: 22,
    fontWeight: 700,
    color: 'var(--text-primary)',
  },
  tabBar: {
    display: 'flex',
    gap: 0,
    marginBottom: 24,
    borderBottom: '0.5px solid var(--border)',
  },
  tabBtn: {
    padding: '10px 22px',
    border: 'none',
    borderBottom: '0.5px solid var(--border)',
    fontSize: 13,
    fontWeight: 500,
    cursor: 'pointer',
    borderRadius: '4px 4px 0 0',
    marginBottom: -1,
  },
  body: {
    display: 'flex',
    flexDirection: 'column',
    gap: 20,
  },
  errorBanner: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '10px 16px',
    background: 'var(--danger-bg)',
    color: 'var(--danger)',
    borderRadius: 6,
    fontSize: 13,
    border: '0.5px solid var(--danger)',
  },
  errorClose: {
    background: 'none',
    border: 'none',
    color: 'var(--danger)',
    cursor: 'pointer',
    fontSize: 18,
    lineHeight: 1,
    padding: '0 4px',
  },
  srcRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 16,
    flexWrap: 'wrap',
  },
  srcLbl: {
    fontSize: 12,
    fontWeight: 600,
    color: 'var(--text-primary)',
  },
  radioLabel: {
    display: 'flex',
    alignItems: 'center',
    fontSize: 13,
    cursor: 'pointer',
    color: 'var(--text-secondary)',
  },
  twoCol: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: 16,
  },
  joinCfg: {
    display: 'flex',
    gap: 16,
    alignItems: 'flex-end',
    flexWrap: 'wrap',
  },
  fieldLabel: {
    fontSize: 12,
    fontWeight: 600,
    color: 'var(--text-primary)',
  },
  select: {
    border: '0.5px solid var(--border)',
    borderRadius: 4,
    padding: '8px 10px',
    fontSize: 13,
    background: 'var(--surface)',
    color: 'var(--text-primary)',
    display: 'block',
  },
  input: {
    border: '0.5px solid var(--border)',
    borderRadius: 4,
    padding: '8px 10px',
    fontSize: 13,
    width: '100%',
    background: 'var(--surface)',
    color: 'var(--text-primary)',
    display: 'block',
    boxSizing: 'border-box',
  },
  loading: {
    fontSize: 13,
    color: 'var(--text-muted)',
    padding: '8px 0',
  },
  infoBox: {
    padding: '12px 16px',
    background: 'var(--surface-2)',
    border: '0.5px solid var(--border)',
    borderRadius: 6,
    fontSize: 13,
    color: 'var(--text-secondary)',
  },
  card: {
    background: 'var(--surface)',
    border: '0.5px solid var(--border)',
    borderRadius: 8,
    overflow: 'hidden',
  },
  cardHeader: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '14px 20px',
    borderBottom: '0.5px solid var(--border)',
    background: 'var(--surface-2)',
  },
  cardTitle: {
    fontSize: 14,
    fontWeight: 600,
    color: 'var(--text-primary)',
  },
  cardMeta: {
    fontSize: 12,
    color: 'var(--text-muted)',
  },
  cardFooter: {
    padding: '16px 20px',
    borderTop: '0.5px solid var(--border)',
    background: 'var(--surface-2)',
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
    fontSize: 13,
  },
  th: {
    textAlign: 'left',
    padding: '10px 16px',
    fontSize: 11,
    fontWeight: 600,
    color: 'var(--text-muted)',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
    borderBottom: '0.5px solid var(--border)',
    background: 'var(--surface-2)',
    whiteSpace: 'nowrap',
  },
  tr: {
    borderBottom: '0.5px solid var(--border)',
  },
  td: {
    padding: '10px 16px',
    verticalAlign: 'middle',
    color: 'var(--text-secondary)',
  },
  code: {
    fontFamily: 'monospace',
    fontSize: 12,
    background: 'var(--bg)',
    padding: '2px 6px',
    borderRadius: 3,
    color: 'var(--text-primary)',
    border: '0.5px solid var(--border)',
  },
  primaryBtn: {
    padding: '10px 20px',
    background: 'var(--navy)',
    color: '#ffffff',
    border: 'none',
    borderRadius: 6,
    fontSize: 13,
    fontWeight: 600,
    cursor: 'pointer',
  },
  secondaryBtn: {
    padding: '10px 20px',
    background: 'var(--surface-2)',
    color: 'var(--text-primary)',
    border: '0.5px solid var(--border)',
    borderRadius: 6,
    fontSize: 13,
    fontWeight: 500,
    cursor: 'pointer',
  },
};
