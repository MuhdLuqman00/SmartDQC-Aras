import React, { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useDropzone } from 'react-dropzone';
import { Upload, CheckCircle2, AlertCircle, ChevronRight, ChevronLeft, ChevronDown, RefreshCw } from 'lucide-react';
import { api } from '../api/client';
import { useLang } from '../context/LanguageContext';
import { useSession } from '../context/SessionContext';
import { RagBadge, scoreToRag } from '../components/RagBadge';
import { persistWarning } from '../lib/persistWarning';
import { translateIssue } from '../lib/issueCatalog';
import { suggestFix } from '../lib/issueFix';

/* ── Step types ──────────────────────────────────────────────────────── */

type Step = 1 | 2 | 3 | 4;

interface MappingRow { raw_column: string; standard_field: string; confidence: number; }
interface Issue { code?: string; description: string; severity: 'critical' | 'warning' | 'info'; count: number; field?: string; pct?: number; }
interface Rule { code?: string; description: string; }
interface CleanStats {
  rows_before: number; rows_after: number;
  quality_score: number; rules_applied: string[];
  rules?: Rule[];
  top_issues: Issue[];
}

/* ── Mapping normaliser ──────────────────────────────────────────────────
   The backend is inconsistent: /upload/preview returns auto_mapping as
   { col: { standard, confidence } } while /upload/merge-preview returns it
   as a flat { col: "field" }. This collapses either shape to safe strings so
   an object can never reach the render tree (was causing React #31). */

function parseMapEntry(v: unknown): { standard: string; confidence: number } {
  if (v && typeof v === 'object') {
    const o = v as { standard?: unknown; confidence?: unknown };
    return {
      standard: typeof o.standard === 'string' ? o.standard : '',
      confidence: Number(o.confidence) || 0,
    };
  }
  return { standard: typeof v === 'string' ? v : '', confidence: v ? 0.9 : 0 };
}

/* ── Step indicator ──────────────────────────────────────────────────── */

function StepIndicator({ current }: { current: Step }) {
  const { t } = useLang();
  const steps = [
    { n: 1, en: 'Upload File',      bm: 'Muat Naik Fail'  },
    { n: 2, en: 'Map Columns',      bm: 'Peta Lajur'      },
    { n: 3, en: 'Quality Check',    bm: 'Semak Kualiti'   },
    { n: 4, en: 'Clean & Done',     bm: 'Bersih & Selesai'},
  ];
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 0, marginBottom: 32 }}>
      {steps.map((s, i) => {
        const done = s.n < current;
        const active = s.n === current;
        return (
          <React.Fragment key={s.n}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={{
                width: 28, height: 28, borderRadius: '50%',
                background: done ? 'var(--kkm-teal)' : active ? 'var(--kkm-blue)' : 'var(--border)',
                color: done || active ? '#fff' : 'var(--text-muted)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 12, fontWeight: 700, flexShrink: 0,
              }}>
                {done ? <CheckCircle2 size={14} /> : s.n}
              </div>
              <span style={{
                fontSize: 12, fontWeight: active ? 600 : 400,
                color: active ? 'var(--text-primary)' : done ? 'var(--kkm-teal)' : 'var(--text-muted)',
                whiteSpace: 'nowrap',
              }}>
                {t(s.en, s.bm)}
              </span>
            </div>
            {i < steps.length - 1 && (
              <div style={{ flex: 1, height: 1, background: s.n < current ? 'var(--kkm-teal)' : 'var(--border)', margin: '0 12px' }} />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}

/* ── Main component ──────────────────────────────────────────────────── */

export function UploadPage() {
  const { t, lang } = useLang();
  const { setSession } = useSession();
  const nav = useNavigate();

  const [step, setStep] = useState<Step>(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  /* Step 1 state */
  const [files, setFiles] = useState<File[]>([]);
  /* E2: editable dataset name, defaulted to the uploaded file's name. */
  const [datasetName, setDatasetName] = useState('');
  const [multiMode, setMultiMode] = useState(false);
  const [cacheId, setCacheId] = useState('');
  const [chosenType, setChosenType] = useState('auto');
  const [detectedType, setDetectedType] = useState('');
  const [sheets, setSheets] = useState<string[]>([]);
  const [activeSheet, setActiveSheet] = useState('');
  const [rowCount, setRowCount] = useState(0);
  const [wideFormat, setWideFormat] = useState(false);

  /* Step 2 state */
  const [mapping, setMapping] = useState<MappingRow[]>([]);
  const [availableFields, setAvailableFields] = useState<string[]>([]);
  const [onlyNeedsReview, setOnlyNeedsReview] = useState(false);

  /* Step 3 state */
  const [qualityCheck, setQualityCheck] = useState<{ score: number; issues: Issue[] } | null>(null);
  const [expandedIssue, setExpandedIssue] = useState<number | null>(null);

  /* Step 4 state */
  const [cleanStats, setCleanStats] = useState<CleanStats | null>(null);
  const [persistWarn, setPersistWarn] = useState<string | null>(null);

  /* ── Dropzone ──────────────────────────────────────────────────────── */

  const onDrop = useCallback((accepted: File[]) => {
    setFiles(multiMode ? accepted : [accepted[0]]);
    // Default the dataset name to the file name (single-file mode); the user
    // can edit it before cleaning or just continue.
    setDatasetName(!multiMode && accepted[0] ? accepted[0].name : '');
    setError('');
  }, [multiMode]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'text/csv': ['.csv'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'], 'application/vnd.ms-excel': ['.xls'] },
    multiple: multiMode,
  });

  /* ── Step 1 → 2: upload + preview ─────────────────────────────────── */

  const handlePreview = async (sheetOverride?: string) => {
    if (!files.length) return;
    setLoading(true); setError('');
    try {
      const fd = new FormData();
      const am = (multiMode && files.length > 1)
        ? await (async () => {
            files.forEach(f => fd.append('files', f));
            const r = await api.post('/upload/merge-preview', fd);
            setCacheId(r.data.cache_id);
            setDetectedType(r.data.source_type || 'unknown');
            setRowCount(Number(r.data.total_rows ?? r.data.row_count) || 0);
            return r.data.auto_mapping || {};
          })()
        : await (async () => {
            fd.append('file', files[0]);
            if (chosenType !== 'auto') fd.append('source_type', chosenType);
            const url = sheetOverride
              ? `/upload/preview?sheet=${encodeURIComponent(sheetOverride)}`
              : '/upload/preview';
            const r = await api.post(url, fd);
            setCacheId(r.data.cache_id);
            setDetectedType(r.data.detected_source_type || r.data.source_type || 'unknown');
            setRowCount(Number(r.data.rows ?? r.data.row_count) || 0);
            setWideFormat(r.data.is_wide_format || false);
            setSheets(r.data.sheets || []);
            setActiveSheet(r.data.active_sheet || sheetOverride || '');
            return r.data.auto_mapping || {};
          })();

      const rows: MappingRow[] = Object.keys(am).map((c) => {
        const { standard, confidence } = parseMapEntry(am[c]);
        return { raw_column: c, standard_field: standard, confidence };
      });
      setMapping(rows);
      setAvailableFields(
        Array.from(new Set(rows.map(r => r.standard_field).filter(Boolean))).sort(),
      );
      setStep(2);
    } catch (e: unknown) {
      const err = e as { response?: { status?: number; data?: unknown }; code?: string };
      const status = err.response?.status;
      let msg: string;
      if (status === 413) {
        msg = t('File too large for the server.', 'Fail terlalu besar untuk pelayan.');
      } else if (status === 502 || status === 504 || err.code === 'ECONNABORTED') {
        msg = t(
          'Server is busy or still starting up and timed out. Wait a moment and try again.',
          'Pelayan sibuk atau masih dimulakan dan tamat masa. Tunggu sebentar dan cuba lagi.',
        );
      } else {
        const data = err.response?.data;
        const detail = data && typeof data === 'object'
          ? (data as { detail?: string }).detail
          : undefined;
        msg = detail
          ? t(`Upload failed: ${detail}`, `Muat naik gagal: ${detail}`)
          : t('Upload failed. Check file format.', 'Muat naik gagal. Semak format fail.');
      }
      setError(msg);
    } finally { setLoading(false); }
  };

  /* ── Wide format transform (optional in step 1) ─────────────────────── */

  const handleWideTransform = async () => {
    if (!cacheId) return;
    setLoading(true);
    try {
      await api.post(`/transform/myvass-wide-to-long?cache_id=${cacheId}`);
    } catch { /* non-fatal */ }
    finally { setLoading(false); }
  };

  /* ── Step 2 → 3: validate mapping ─────────────────────────────────── */

  const handleValidateMapping = async () => {
    setLoading(true); setError('');
    try {
      const mappingDict: Record<string, string> = {};
      mapping.forEach(m => { if (m.standard_field) mappingDict[m.raw_column] = m.standard_field; });
      await api.post(`/mapping/validate?cache_id=${cacheId}`, { mapping: mappingDict });
      /* proceed to quality check */
      const qr = await api.post(`/clean/quality-check?cache_id=${cacheId}`, { mapping: mappingDict });
      setQualityCheck({ score: Number(qr.data.quality_score ?? qr.data.completeness_pct) || 0, issues: qr.data.issues || [] });
      setStep(3);
    } catch { setError(t('Validation failed.', 'Pengesahan gagal.')); }
    finally { setLoading(false); }
  };

  /* ── Step 3 → 4: run cleaning ──────────────────────────────────────── */

  const handleClean = async () => {
    setLoading(true); setError('');
    try {
      const mappingDict: Record<string, string> = {};
      mapping.forEach(m => { if (m.standard_field) mappingDict[m.raw_column] = m.standard_field; });
      const r = await api.post(`/clean/run?cache_id=${cacheId}`, {
        mapping: mappingDict,
        dataset_name: datasetName.trim() || undefined,
      });
      setCleanStats({
        rows_before: Number(r.data.rows_before) || rowCount,
        rows_after: Number(r.data.rows_after) || 0,
        quality_score: Number(r.data.quality_score) || 0,
        rules_applied: Array.isArray(r.data.rules_applied) ? r.data.rules_applied : [],
        rules: Array.isArray(r.data.rules) ? r.data.rules : undefined,
        top_issues: Array.isArray(r.data.top_issues) ? r.data.top_issues : [],
      });
      setPersistWarn(persistWarning(r.data, lang));
      setSession({
        cacheId: r.data.cache_id,
        filename: datasetName.trim() || files[0]?.name || 'dataset',
        sourceType: detectedType,
        rowCount: r.data.rows_after || 0,
        qualityScore: r.data.quality_score || 0,
        cleanStats: r.data,
        preview: r.data.preview || null,
      });
      setStep(4);
    } catch { setError(t('Cleaning failed.', 'Pembersihan gagal.')); }
    finally { setLoading(false); }
  };

  /* ── Nav helpers ────────────────────────────────────────────────────── */

  const confidenceColor = (c: number) => c >= 0.8 ? 'var(--success)' : c >= 0.5 ? 'var(--warning)' : 'var(--danger)';

  /* "Needs review" = an actual mapping (non-empty field) under 80% confidence.
     Deliberately-ignored columns are NOT flagged (consistent with the neutral
     dot from WS1). Drives the filter toggle + count on the mapping table. */
  const needsReview = (m: MappingRow) => m.standard_field !== '' && m.confidence < 0.8;

  /* ── Render ─────────────────────────────────────────────────────────── */

  return (
    <div style={{ maxWidth: 860, margin: '0 auto' }}>
      <StepIndicator current={step} />

      {/* ── STEP 1 ── */}
      {/* Two-column workspace: the upload card stays the single primary action;
          a subordinate guide rail fills the empty canvas with real guidance
          (audit 02). Wraps to a single column on narrow widths. */}
      {step === 1 && (
        <div style={{ display: 'flex', gap: 20, alignItems: 'flex-start', flexWrap: 'wrap' }}>
        <div style={{
          flex: '1 1 440px', minWidth: 0,
          background: 'var(--surface)', border: '1px solid var(--border)',
          borderRadius: 'var(--radius-card)', padding: '32px',
          boxShadow: 'var(--shadow-card)',
        }}>
          <h2 style={{ fontFamily: 'var(--font-body)', fontSize: 18, fontWeight: 700, marginBottom: 8 }}>
            {t('Upload File', 'Muat Naik Fail')}
          </h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: 14, marginBottom: 20 }}>
            {t('Accepts CSV, XLSX, and XLS files.', 'Menerima fail CSV, XLSX, dan XLS.')}
          </p>

          {/* Multi-file toggle */}
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16, cursor: 'pointer', fontSize: 13, color: 'var(--text-secondary)' }}>
            <input type="checkbox" checked={multiMode} onChange={e => setMultiMode(e.target.checked)} />
            {t('Merge multiple MyVASS files', 'Gabungkan beberapa fail MyVASS')}
          </label>

          {/* Source-type selector (single-file mode; merge is MyVASS-only) */}
          {!multiMode && (
            <div style={{ marginBottom: 20 }}>
              <label htmlFor="src-type" style={{ display: 'block', fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6 }}>
                {t('Data source schema', 'Skema sumber data')}
              </label>
              <select
                id="src-type"
                value={chosenType}
                onChange={e => setChosenType(e.target.value)}
                style={{
                  width: '100%', maxWidth: 320, background: 'var(--surface-2)',
                  border: '1px solid var(--border)', borderRadius: 'var(--radius-btn)',
                  padding: '8px 12px', fontSize: 14, color: 'var(--text-primary)', cursor: 'pointer',
                }}
              >
                <option value="auto">{t('Auto-detect (recommended)', 'Auto-kesan (disyorkan)')}</option>
                <option value="myvass">{t('MyVASS (TASKA)', 'MyVASS (TASKA)')}</option>
                <option value="ncdc">{t('NCDC (TASKA)', 'NCDC (TASKA)')}</option>
                <option value="kpm">{t('KPM (School)', 'KPM (Sekolah)')}</option>
                <option value="unknown">{t('Other / Unknown', 'Lain-lain / Tidak Diketahui')}</option>
              </select>
              <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 6 }}>
                {t('Leave on Auto-detect unless detection picks the wrong schema. "Other" maps columns by best match across all schemas.',
                   'Biarkan pada Auto-kesan melainkan pengesanan salah. "Lain-lain" memetakan lajur mengikut padanan terbaik merentas semua skema.')}
              </p>
            </div>
          )}

          {/* Dropzone */}
          <div
            {...getRootProps()}
            style={{
              border: `2px dashed ${isDragActive ? 'var(--kkm-sky)' : files.length ? 'var(--kkm-teal)' : 'var(--border)'}`,
              borderRadius: 'var(--radius-card)',
              padding: '40px 24px', textAlign: 'center', cursor: 'pointer',
              background: isDragActive ? 'rgba(0,163,224,0.05)' : 'var(--surface-2)',
              transition: 'all var(--transition)',
            }}
          >
            <input {...getInputProps()} />
            <Upload size={32} style={{ color: 'var(--text-muted)', marginBottom: 12 }} />
            {files.length > 0 ? (
              <div>
                <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>
                  {files.map(f => f.name).join(', ')}
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                  {files.length > 1 ? `${files.length} files` : `${(files[0].size / 1024).toFixed(1)} KB`}
                </div>
              </div>
            ) : (
              <div>
                <div style={{ fontWeight: 500, color: 'var(--text-secondary)', marginBottom: 4 }}>
                  {isDragActive
                    ? t('Drop here…', 'Lepaskan di sini…')
                    : t('Drag & drop or click to browse', 'Seret & lepas atau klik untuk semak imbas')}
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>CSV, XLSX, XLS</div>
              </div>
            )}
          </div>

          {files.length > 0 && !multiMode && (
            <div style={{ marginTop: 20 }}>
              <label htmlFor="dataset-name" style={{ display: 'block', fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6 }}>
                {t('Dataset name', 'Nama dataset')}
              </label>
              <input
                id="dataset-name"
                value={datasetName}
                onChange={e => setDatasetName(e.target.value)}
                placeholder={files[0]?.name}
                style={{ width: '100%', maxWidth: 420, background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 'var(--radius-btn)', padding: '8px 12px', fontSize: 14, color: 'var(--text-primary)', boxSizing: 'border-box' }}
              />
              <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 6 }}>
                {t('Defaults to the file name. This name appears in the Library, History and sessions.',
                   'Lalai kepada nama fail. Nama ini muncul dalam Perpustakaan, Sejarah dan sesi.')}
              </p>
            </div>
          )}

          {error && <div style={{ marginTop: 12, color: 'var(--danger)', fontSize: 13 }}>{error}</div>}

          <div style={{ marginTop: 24, display: 'flex', justifyContent: 'flex-end' }}>
            <button
              onClick={() => handlePreview()}
              disabled={!files.length || loading}
              style={{
                background: 'var(--kkm-blue)', color: '#fff', border: 'none',
                borderRadius: 'var(--radius-btn)', padding: '10px 24px',
                fontWeight: 600, fontSize: 14, cursor: files.length ? 'pointer' : 'not-allowed',
                opacity: !files.length || loading ? 0.5 : 1,
                display: 'flex', alignItems: 'center', gap: 6,
              }}
            >
              {loading ? <RefreshCw size={14} className="spin" /> : null}
              {t('Next', 'Seterusnya')} <ChevronRight size={16} />
            </button>
          </div>
        </div>

        {/* Subordinate guide rail — orientation, not a second action. */}
        <aside style={{
          flex: '1 1 230px', minWidth: 0,
          background: 'var(--surface-2)', border: '1px solid var(--border)',
          borderRadius: 'var(--radius-card)', padding: '24px 22px',
          display: 'flex', flexDirection: 'column', gap: 20,
        }}>
          <div className="kkm-keyline" style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.07em', textTransform: 'uppercase', color: 'var(--text-secondary)' }}>
            {t("What you'll need", 'Apa yang diperlukan')}
          </div>

          <div>
            <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', letterSpacing: '0.04em', textTransform: 'uppercase', marginBottom: 8 }}>
              {t('Accepted formats', 'Format diterima')}
            </div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {['CSV', 'XLSX', 'XLS'].map(f => (
                <span key={f} className="mono" style={{
                  fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)',
                  background: 'var(--surface)', border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-pill)', padding: '2px 9px',
                }}>{f}</span>
              ))}
            </div>
          </div>

          <div>
            <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', letterSpacing: '0.04em', textTransform: 'uppercase', marginBottom: 6 }}>
              {t('Recognised schemas', 'Skema dikenali')}
            </div>
            <p style={{ fontSize: 12.5, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
              {t('MyVASS, NCDC and KPM are detected automatically — pick one manually only if detection is wrong.',
                 'MyVASS, NCDC dan KPM dikesan secara automatik — pilih secara manual hanya jika pengesanan salah.')}
            </p>
          </div>

          <div>
            <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', letterSpacing: '0.04em', textTransform: 'uppercase', marginBottom: 8 }}>
              {t('What happens next', 'Langkah seterusnya')}
            </div>
            <ol style={{ margin: 0, padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 7 }}>
              {[
                t('Upload & detect', 'Muat naik & kesan'),
                t('Map columns', 'Peta lajur'),
                t('Quality check', 'Semak kualiti'),
                t('Clean & download', 'Bersih & muat turun'),
              ].map((label, i) => (
                <li key={i} style={{ display: 'flex', alignItems: 'center', gap: 9, fontSize: 12.5, color: 'var(--text-secondary)' }}>
                  <span className="mono" style={{
                    width: 18, height: 18, flexShrink: 0, borderRadius: '50%',
                    background: 'var(--surface)', border: '1px solid var(--border)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 10, fontWeight: 700, color: 'var(--text-muted)',
                  }}>{i + 1}</span>
                  {label}
                </li>
              ))}
            </ol>
          </div>
        </aside>
        </div>
      )}

      {/* ── STEP 2 ── */}
      {step === 2 && (
        <div style={{
          background: 'var(--surface)', border: '1px solid var(--border)',
          borderRadius: 'var(--radius-card)', padding: '32px',
          boxShadow: 'var(--shadow-card)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
            <h2 style={{ fontFamily: 'var(--font-body)', fontSize: 18, fontWeight: 700 }}>
              {t('Map Columns', 'Peta Lajur')}
            </h2>
            <span style={{
              fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 999,
              background: 'var(--surface-2)', color: 'var(--text-secondary)', textTransform: 'uppercase',
            }}>
              {detectedType}
            </span>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
              {rowCount.toLocaleString()} {t('rows', 'baris')}
            </span>
            {sheets.length > 1 && (
              <label style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--text-secondary)' }}>
                {t('Sheet', 'Helaian')}
                <select
                  value={activeSheet}
                  disabled={loading}
                  onChange={e => handlePreview(e.target.value)}
                  style={{
                    background: 'var(--surface-2)', border: '1px solid var(--border)',
                    borderRadius: 'var(--radius-btn)', padding: '4px 8px', fontSize: 12,
                    color: 'var(--text-primary)', cursor: 'pointer',
                  }}
                >
                  {sheets.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </label>
            )}
          </div>
          <p style={{ color: 'var(--text-secondary)', fontSize: 13, marginBottom: 20 }}>
            {t('Review and adjust column mappings. Confidence below 80% should be verified.', 'Semak dan laraskan pemetaan lajur. Keyakinan di bawah 80% perlu disahkan.')}
          </p>

          {wideFormat && (
            <div style={{
              background: 'var(--warning-bg)', border: '1px solid var(--warning)',
              borderRadius: 8, padding: '12px 16px', marginBottom: 16, fontSize: 13,
              color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: 10,
            }}>
              <AlertCircle size={16} style={{ color: 'var(--warning)', flexShrink: 0 }} />
              {t('MyVASS wide format detected.', 'Format MyVASS lebar dikesan.')}
              <button
                onClick={handleWideTransform}
                disabled={loading}
                style={{
                  marginLeft: 'auto', background: 'var(--warning)', color: '#fff',
                  border: 'none', borderRadius: 6, padding: '4px 12px',
                  fontSize: 12, fontWeight: 600, cursor: 'pointer',
                }}
              >
                {t('Convert to long format', 'Tukar ke format panjang')}
              </button>
            </div>
          )}

          {(() => {
            const reviewCount = mapping.filter(needsReview).length;
            const visible = mapping
              .map((row, idx) => ({ row, idx }))
              .filter(({ row }) => !onlyNeedsReview || needsReview(row));
            return (
          <>
          {/* Filter toolbar — jump straight to the mappings that need a human check. */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10, flexWrap: 'wrap' }}>
            <button
              type="button"
              onClick={() => setOnlyNeedsReview(v => !v)}
              /* Stay enabled while pressed so the user can always toggle back —
                 even after fixing the last flagged column drops the count to 0. */
              disabled={reviewCount === 0 && !onlyNeedsReview}
              aria-pressed={onlyNeedsReview}
              style={{
                display: 'flex', alignItems: 'center', gap: 6,
                background: onlyNeedsReview ? 'var(--warning-bg)' : 'var(--surface-2)',
                border: `1px solid ${onlyNeedsReview ? 'var(--warning)' : 'var(--border)'}`,
                borderRadius: 'var(--radius-pill)', padding: '5px 12px',
                fontSize: 12, fontWeight: 600,
                color: (reviewCount === 0 && !onlyNeedsReview) ? 'var(--text-muted)' : onlyNeedsReview ? 'var(--warning)' : 'var(--text-secondary)',
                cursor: (reviewCount === 0 && !onlyNeedsReview) ? 'not-allowed' : 'pointer',
              }}
            >
              <AlertCircle size={13} />
              {onlyNeedsReview
                ? t('Showing needs-review', 'Menunjukkan perlu disemak')
                : t('Needs review (<80%)', 'Perlu disemak (<80%)')}
              <span style={{ fontFamily: 'var(--font-mono)' }}>{reviewCount}</span>
            </button>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
              {t(`Showing ${visible.length} of ${mapping.length}`, `Menunjukkan ${visible.length} daripada ${mapping.length}`)}
            </span>
          </div>

          <div style={{ border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden' }}>
            <div style={{ maxHeight: 420, overflowY: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: 'var(--surface-2)' }}>
                  {[t('Raw Column', 'Lajur Asal'), t('Standard Field', 'Medan Standard'), t('Confidence', 'Keyakinan')].map(h => (
                    <th key={h} style={{ position: 'sticky', top: 0, zIndex: 1, background: 'var(--surface-2)', borderBottom: '1px solid var(--border)', padding: '10px 14px', textAlign: 'left', fontSize: 11, fontWeight: 600, letterSpacing: '0.06em', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {visible.length === 0 && (
                  <tr>
                    <td colSpan={3} style={{ padding: '24px 14px', textAlign: 'center', fontSize: 13, color: 'var(--text-muted)' }}>
                      {t('No columns need review — every mapping is at or above 80%.',
                         'Tiada lajur perlu disemak — setiap pemetaan 80% ke atas.')}
                    </td>
                  </tr>
                )}
                {visible.map(({ row, idx: i }, pos) => (
                  <tr key={row.raw_column} style={{ borderBottom: pos < visible.length - 1 ? '1px solid var(--border)' : 'none' }}>
                    <td style={{ padding: '10px 14px', fontSize: 13, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
                      {row.raw_column}
                    </td>
                    <td style={{ padding: '10px 14px' }}>
                      <select
                        value={row.standard_field}
                        onChange={e => setMapping(prev => prev.map((m, idx) => idx === i ? { ...m, standard_field: e.target.value } : m))}
                        style={{
                          background: 'var(--surface-2)', border: '1px solid var(--border)',
                          borderRadius: 6, padding: '5px 10px', fontSize: 13,
                          color: 'var(--text-primary)', cursor: 'pointer',
                        }}
                      >
                        <option value="">{t('— Ignore —', '— Abaikan —')}</option>
                        {availableFields.map((f: string) => <option key={f} value={f}>{f}</option>)}
                      </select>
                    </td>
                    <td style={{ padding: '10px 14px' }}>
                      {row.standard_field === '' ? (
                        /* Deliberately ignored column ("— Ignore —"): a neutral
                           state, not an error. Keyed on the empty field — NOT on
                           confidence — so a genuine low-confidence *mapping*
                           (non-empty field below) still reads red/amber. */
                        <div style={{
                          display: 'inline-flex', alignItems: 'center', gap: 6,
                          fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)',
                        }}>
                          <div style={{
                            width: 6, height: 6, borderRadius: '50%',
                            background: 'var(--status-neutral)',
                          }} />
                          {t('Ignored', 'Diabaikan')}
                        </div>
                      ) : (
                        <div style={{
                          display: 'inline-flex', alignItems: 'center', gap: 6,
                          fontSize: 12, fontWeight: 600, color: confidenceColor(row.confidence),
                        }}>
                          <div style={{
                            width: 6, height: 6, borderRadius: '50%',
                            background: confidenceColor(row.confidence),
                          }} />
                          {(Number(row.confidence) * 100).toFixed(0)}%
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          </div>
          </>
            );
          })()}

          {error && <div style={{ marginTop: 12, color: 'var(--danger)', fontSize: 13 }}>{error}</div>}

          <div style={{ marginTop: 24, display: 'flex', justifyContent: 'space-between' }}>
            <button onClick={() => setStep(1)} style={{ background: 'none', border: '1px solid var(--border)', borderRadius: 'var(--radius-btn)', padding: '10px 20px', fontSize: 13, cursor: 'pointer', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: 6 }}>
              <ChevronLeft size={16} /> {t('Back', 'Kembali')}
            </button>
            <button
              onClick={handleValidateMapping}
              disabled={loading}
              style={{ background: 'var(--kkm-blue)', color: '#fff', border: 'none', borderRadius: 'var(--radius-btn)', padding: '10px 24px', fontWeight: 600, fontSize: 14, cursor: 'pointer', opacity: loading ? 0.6 : 1, display: 'flex', alignItems: 'center', gap: 6 }}
            >
              {loading ? <RefreshCw size={14} /> : null}
              {t('Confirm Mapping', 'Sahkan Pemetaan')} <ChevronRight size={16} />
            </button>
          </div>
        </div>
      )}

      {/* ── STEP 3 ── */}
      {step === 3 && !qualityCheck && (
        <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>
          <RefreshCw size={24} className="spin" style={{ marginBottom: 12 }} />
          <div>{t('Loading quality check…', 'Memuatkan semakan kualiti…')}</div>
        </div>
      )}
      {step === 3 && qualityCheck && (
        <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-card)', padding: '32px', boxShadow: 'var(--shadow-card)' }}>
          <h2 style={{ fontFamily: 'var(--font-body)', fontSize: 18, fontWeight: 700, marginBottom: 20 }}>
            {t('Quality Check', 'Semak Kualiti')}
          </h2>

          {/* Score + banner */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: 16,
            background: qualityCheck.score >= 80 ? 'var(--success-bg)' : qualityCheck.score >= 60 ? 'var(--warning-bg)' : 'var(--danger-bg)',
            border: `1px solid ${qualityCheck.score >= 80 ? 'var(--success)' : qualityCheck.score >= 60 ? 'var(--warning)' : 'var(--danger)'}`,
            borderRadius: 10, padding: '16px 20px', marginBottom: 20,
          }}>
            <div style={{ fontSize: 36, fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-body)' }}>
              {Number(qualityCheck.score).toFixed(1)}%
            </div>
            <div>
              <div style={{ fontWeight: 600, fontSize: 14 }}>
                {qualityCheck.score >= 80
                  ? t('Ready for cleaning', 'Sedia untuk dibersih')
                  : qualityCheck.score >= 60
                    ? t('Review recommended', 'Semak disyorkan')
                    : t('Critical issues found', 'Masalah kritikal ditemui')}
              </div>
              <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 2 }}>
                {qualityCheck.issues.length} {t('issues detected', 'isu dikesan')}
              </div>
            </div>
          </div>

          {qualityCheck.issues.slice(0, 5).map((issue, i, arr) => {
            const open = expandedIssue === i;
            const fix = suggestFix(issue, lang);
            const scope = [
              t(`${Number(issue.count).toLocaleString()} rows affected`, `${Number(issue.count).toLocaleString()} baris terjejas`),
              issue.field ? t(`column “${issue.field}”`, `lajur “${issue.field}”`) : null,
              issue.pct != null ? `${issue.pct}% ${t('empty', 'kosong')}` : null,
            ].filter(Boolean).join(' · ');
            const panelId = `qc-issue-${i}`;
            return (
              <div key={i} style={{ borderBottom: i < arr.length - 1 ? '1px solid var(--border)' : 'none' }}>
                <button
                  type="button"
                  onClick={() => setExpandedIssue(open ? null : i)}
                  aria-expanded={open}
                  aria-controls={panelId}
                  style={{
                    width: '100%', display: 'flex', alignItems: 'center', gap: 10,
                    padding: '10px 0', background: 'none', border: 'none', cursor: 'pointer',
                    textAlign: 'left', color: 'var(--text-primary)',
                  }}
                >
                  <AlertCircle size={15} style={{ color: issue.severity === 'critical' ? 'var(--danger)' : 'var(--warning)', flexShrink: 0 }} />
                  <span style={{ flex: 1, fontSize: 13 }}>{translateIssue(issue, lang)}</span>
                  <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>{Number(issue.count).toLocaleString()}</span>
                  <ChevronDown size={15} style={{ color: 'var(--text-muted)', flexShrink: 0, transform: open ? 'rotate(180deg)' : 'none', transition: 'transform var(--transition)' }} />
                </button>
                {open && (
                  <div id={panelId} style={{ padding: '0 0 12px 25px', display: 'flex', flexDirection: 'column', gap: 8 }}>
                    <div>
                      <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 3 }}>
                        {t('Affected', 'Terjejas')}
                      </div>
                      <div style={{ fontSize: 12.5, color: 'var(--text-secondary)' }}>{scope}</div>
                    </div>
                    {fix && (
                      <div>
                        <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 3 }}>
                          {t('Suggested fix', 'Cadangan tindakan')}
                        </div>
                        <div style={{ fontSize: 12.5, color: 'var(--text-secondary)', lineHeight: 1.55 }}>{fix}</div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}

          {error && <div style={{ marginTop: 12, color: 'var(--danger)', fontSize: 13 }}>{error}</div>}

          <div style={{ marginTop: 24, display: 'flex', justifyContent: 'space-between' }}>
            <button onClick={() => setStep(2)} style={{ background: 'none', border: '1px solid var(--border)', borderRadius: 'var(--radius-btn)', padding: '10px 20px', fontSize: 13, cursor: 'pointer', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: 6 }}>
              <ChevronLeft size={16} /> {t('Back', 'Kembali')}
            </button>
            <button
              onClick={handleClean}
              disabled={loading}
              style={{ background: 'var(--kkm-blue)', color: '#fff', border: 'none', borderRadius: 'var(--radius-btn)', padding: '10px 24px', fontWeight: 600, fontSize: 14, cursor: 'pointer', opacity: loading ? 0.6 : 1, display: 'flex', alignItems: 'center', gap: 6 }}
            >
              {loading ? <RefreshCw size={14} /> : <CheckCircle2 size={16} />}
              {t('Clean Data', 'Bersihkan Data')} <ChevronRight size={16} />
            </button>
          </div>
        </div>
      )}

      {/* ── STEP 4 ── */}
      {step === 4 && !cleanStats && (
        <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>
          <RefreshCw size={24} className="spin" style={{ marginBottom: 12 }} />
          <div>{t('Finalising…', 'Memuatkan…')}</div>
        </div>
      )}
      {step === 4 && cleanStats && (
        <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-card)', padding: '32px', boxShadow: 'var(--shadow-card)' }}>
          <div style={{ textAlign: 'center', marginBottom: 28 }}>
            <CheckCircle2 size={44} style={{ color: 'var(--kkm-teal)', marginBottom: 12 }} />
            <h2 style={{ fontFamily: 'var(--font-body)', fontSize: 20, fontWeight: 700 }}>
              {t('Cleaning Complete', 'Pembersihan Selesai')}
            </h2>
            <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginTop: 6 }}>
              {t(
                `${Number(cleanStats.rows_after).toLocaleString()} clean records are ready to explore.`,
                `${Number(cleanStats.rows_after).toLocaleString()} rekod bersih sedia untuk diterokai.`,
              )}
            </p>
          </div>

          {persistWarn && (
            <div style={{
              display: 'flex', alignItems: 'flex-start', gap: 10,
              background: 'var(--danger-bg)', color: 'var(--danger)',
              border: '1px solid var(--danger)', borderRadius: 8,
              padding: '12px 16px', marginBottom: 24, fontSize: 14, fontWeight: 600,
            }}>
              <AlertCircle size={18} style={{ flexShrink: 0, marginTop: 1 }} />
              <span>{persistWarn}</span>
            </div>
          )}

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 24 }}>
            {[
              { label: t('Before', 'Sebelum'), value: Number(cleanStats.rows_before).toLocaleString() },
              { label: t('After', 'Selepas'),  value: Number(cleanStats.rows_after).toLocaleString()  },
              { label: t('Quality Score', 'Skor Kualiti'), value: `${Number(cleanStats.quality_score).toFixed(1)}%` },
            ].map(card => (
              <div key={card.label} style={{ background: 'var(--surface-2)', borderRadius: 8, padding: '14px 16px', textAlign: 'center', border: '1px solid var(--border)' }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 6 }}>{card.label}</div>
                <div style={{ fontSize: 24, fontWeight: 700, color: 'var(--text-primary)' }}>{card.value}</div>
              </div>
            ))}
          </div>

          {(() => {
            // Prefer localisable `rules` (code + description); fall back to the
            // legacy string[] for parity with older responses.
            const ruleList: Rule[] = cleanStats.rules && cleanStats.rules.length
              ? cleanStats.rules
              : cleanStats.rules_applied.map(d => ({ description: d }));
            if (!ruleList.length) return null;
            return (
              <div style={{ marginBottom: 20 }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 8 }}>
                  {t('Rules Applied', 'Peraturan Digunakan')}
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {ruleList.map((r, i) => (
                    <span key={r.code ?? r.description ?? i} style={{ fontSize: 11, background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 999, padding: '3px 10px', color: 'var(--text-secondary)' }}>
                      {translateIssue(r, lang)}
                    </span>
                  ))}
                </div>
              </div>
            );
          })()}

          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 16 }}>
            <a href={`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/clean/download-cached/${cacheId}?format=csv`}
              target="_blank" rel="noreferrer"
              style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 'var(--radius-btn)', padding: '8px 16px', fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
              ↓ CSV
            </a>
            <a href={`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/clean/download-cached/${cacheId}?format=xlsx`}
              target="_blank" rel="noreferrer"
              style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 'var(--radius-btn)', padding: '8px 16px', fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
              ↓ XLSX
            </a>
            <a href={`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/clean/download-report/${cacheId}`}
              target="_blank" rel="noreferrer"
              style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 'var(--radius-btn)', padding: '8px 16px', fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
              ↓ {t('Quality Report (XLSX)', 'Laporan Kualiti (XLSX)')}
            </a>
          </div>

          <button
            onClick={() => nav('/')}
            style={{ width: '100%', background: 'var(--kkm-blue)', color: '#fff', border: 'none', borderRadius: 'var(--radius-btn)', padding: '12px', fontFamily: 'var(--font-body)', fontWeight: 700, fontSize: 15, cursor: 'pointer' }}
          >
            {t('View on Dashboard →', 'Lihat di Papan Pemuka →')}
          </button>
        </div>
      )}
    </div>
  );
}
