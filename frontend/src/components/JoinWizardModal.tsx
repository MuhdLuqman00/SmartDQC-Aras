import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { X, ArrowRight, ArrowLeft, GitMerge, AlertTriangle, CheckCircle2 } from 'lucide-react';
import { api } from '../api/client';
import { useLang } from '../context/LanguageContext';
import { useSession } from '../context/SessionContext';

/* Backend contract: /join/preview and /join/run accept five join_types.
   Union is the vertical operation; the others are horizontal (require key). */
export type JoinType = 'inner' | 'left' | 'right' | 'outer' | 'union';

interface JoinDataset {
  id: string;
  filename: string;
  source_type: string | null;
  row_count: number | null;
}

interface JoinPreviewResponse {
  preview: Record<string, unknown>[];
  columns: string[];
  left_columns: string[];
  right_columns: string[];
  shape: { rows: number; cols: number };
  left_shape: { rows: number; cols: number };
  right_shape: { rows: number; cols: number };
  join_stats: {
    matched_keys?: number;
    left_only_keys?: number;
    right_only_keys?: number;
    duplicates_removed?: number;
    result_rows?: number;
  };
}

interface JoinRunResponse {
  cache_id: string;
  shape: { rows: number; cols: number };
  join_stats: JoinPreviewResponse['join_stats'];
}

interface Props {
  left: JoinDataset;
  right: JoinDataset;
  onClose: () => void;
  /** Called after a successful join — parent should refresh the dataset list. */
  onJoined?: (newCacheId: string) => void;
}

export function JoinWizardModal({ left, right, onClose, onJoined }: Props): JSX.Element {
  const { t } = useLang();
  const { setSession } = useSession();
  const nav = useNavigate();

  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [joinType, setJoinType] = useState<JoinType>('inner');
  const [dedup, setDedup] = useState(true);
  const [selectedKeys, setSelectedKeys] = useState<string[]>([]);
  const [preview, setPreview] = useState<JoinPreviewResponse | null>(null);
  const [running, setRunning] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isUnion = joinType === 'union';

  /* Step 2 needs the intersection of column names so we can offer real
     join keys. Fetched lazily by the /join/preview call (it returns
     left_columns and right_columns). Until we have a preview, fall back
     to a sensible default suggestion via a tiny dry-run call. */
  useEffect(() => {
    if (step !== 2 || isUnion || preview) return;
    setPreviewLoading(true);
    setError(null);
    // Dry-run preview with no keys just to learn the column lists. Backend
    // rejects horizontal joins without keys, so we ask for a union dry-run
    // to learn the shapes/columns, then the real preview happens in step 3.
    const url = `/join/preview?cache_id_left=${left.id}&cache_id_right=${right.id}&join_type=union&dedup=false`;
    api.post<JoinPreviewResponse>(url)
      .then(r => setPreview(r.data))
      .catch(e => setError(e?.response?.data?.detail || 'Failed to read column lists.'))
      .finally(() => setPreviewLoading(false));
  }, [step, isUnion, preview, left.id, right.id]);

  const sharedKeys = useMemo(() => {
    if (!preview) return [];
    const r = new Set(preview.right_columns.map(c => c.toLowerCase()));
    return preview.left_columns.filter(c => r.has(c.toLowerCase()));
  }, [preview]);

  // Default join key: IC if both sides have it, else first shared column.
  useEffect(() => {
    if (isUnion || selectedKeys.length > 0 || sharedKeys.length === 0) return;
    const ic = sharedKeys.find(k => /ic[_ ]?no|ic[_ ]?passport/i.test(k));
    setSelectedKeys([ic ?? sharedKeys[0]]);
  }, [sharedKeys, selectedKeys.length, isUnion]);

  const toggleKey = (col: string) =>
    setSelectedKeys(prev => prev.includes(col) ? prev.filter(k => k !== col) : [...prev, col]);

  const runPreview = async () => {
    setPreviewLoading(true);
    setError(null);
    const params = new URLSearchParams({
      cache_id_left: left.id,
      cache_id_right: right.id,
      join_type: joinType,
      dedup: String(dedup),
    });
    if (!isUnion && selectedKeys.length) params.set('key_cols', selectedKeys.join(','));
    try {
      const r = await api.post<JoinPreviewResponse>(`/join/preview?${params}`);
      setPreview(r.data);
      setStep(3);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      setError(err.response?.data?.detail || 'Preview failed.');
    } finally {
      setPreviewLoading(false);
    }
  };

  const runJoin = async () => {
    setRunning(true);
    setError(null);
    const params = new URLSearchParams({
      cache_id_left: left.id,
      cache_id_right: right.id,
      join_type: joinType,
      dedup: String(dedup),
    });
    if (!isUnion && selectedKeys.length) params.set('key_cols', selectedKeys.join(','));
    try {
      const r = await api.post<JoinRunResponse>(`/join/run?${params}`);
      // Activate the joined dataset as the current session and navigate to
      // Explorer so the user sees it immediately.
      setSession({
        cacheId: r.data.cache_id,
        filename: `${left.filename} ${isUnion ? '∪' : '⨝'} ${right.filename}`,
        sourceType: 'joined',
        rowCount: r.data.shape.rows,
      });
      onJoined?.(r.data.cache_id);
      onClose();
      nav('/explorer');
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      setError(err.response?.data?.detail || 'Join failed.');
    } finally {
      setRunning(false);
    }
  };

  const canContinueStep2 = isUnion || selectedKeys.length > 0;

  /* ── shared atoms ── */
  const cardBg: React.CSSProperties = {
    background: 'var(--surface)', border: '1px solid var(--border)',
    borderRadius: 12, padding: 24, width: '92%', maxWidth: 760, maxHeight: '88vh',
    overflowY: 'auto', boxShadow: '0 20px 48px rgba(0,0,0,0.4)',
  };
  const stepDot = (n: number): React.CSSProperties => ({
    width: 26, height: 26, borderRadius: '50%',
    background: n <= step ? 'var(--kkm-blue)' : 'var(--surface-2)',
    color: n <= step ? '#fff' : 'var(--text-muted)',
    border: `1px solid ${n <= step ? 'var(--kkm-blue)' : 'var(--border)'}`,
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    fontSize: 12, fontWeight: 700,
  });
  const btnPrimary: React.CSSProperties = {
    background: 'var(--kkm-blue)', color: '#fff', border: 'none',
    borderRadius: 'var(--radius-btn)', padding: '9px 18px',
    fontWeight: 600, fontSize: 13, cursor: 'pointer',
    display: 'flex', alignItems: 'center', gap: 6,
  };
  const btnSecondary: React.CSSProperties = {
    background: 'var(--surface-2)', color: 'var(--text-primary)',
    border: '1px solid var(--border)', borderRadius: 'var(--radius-btn)',
    padding: '9px 16px', fontWeight: 500, fontSize: 13, cursor: 'pointer',
    display: 'flex', alignItems: 'center', gap: 6,
  };

  return (
    <div
      style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)', zIndex: 1100, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
      onClick={onClose}
    >
      <div style={cardBg} onClick={e => e.stopPropagation()}>
        {/* ── Header ── */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 18 }}>
          <GitMerge size={20} style={{ color: 'var(--kkm-blue)' }} />
          <h3 style={{ fontFamily: "'Plus Jakarta Sans', sans-serif", fontSize: 17, fontWeight: 700, margin: 0, flex: 1 }}>
            {t('Join Datasets', 'Cantum Set Data')}
          </h3>
          <button onClick={onClose} aria-label="Close" style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: 4 }}>
            <X size={18} />
          </button>
        </div>

        {/* ── Stepper ── */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 18, fontSize: 11, color: 'var(--text-secondary)' }}>
          {[
            [1, t('Type', 'Jenis')],
            [2, t('Keys', 'Kunci')],
            [3, t('Preview', 'Pratonton')],
          ].map(([n, label], i, arr) => (
            <React.Fragment key={n}>
              <div style={stepDot(n as number)}>{n}</div>
              <span style={{ fontWeight: step === n ? 700 : 500, color: step >= (n as number) ? 'var(--text-primary)' : 'var(--text-muted)' }}>{label}</span>
              {i < arr.length - 1 && <span style={{ flex: 0, color: 'var(--text-muted)', margin: '0 4px' }}>—</span>}
            </React.Fragment>
          ))}
        </div>

        {/* ── Source pills ── */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 16, fontSize: 12, color: 'var(--text-secondary)' }}>
          <span style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 8, padding: '6px 10px', flex: 1, minWidth: 0 }}>
            <strong style={{ color: 'var(--text-primary)', display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {left.filename}
            </strong>
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{left.row_count?.toLocaleString() ?? '?'} {t('rows', 'baris')}</span>
          </span>
          <span style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 8, padding: '6px 10px', flex: 1, minWidth: 0 }}>
            <strong style={{ color: 'var(--text-primary)', display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {right.filename}
            </strong>
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{right.row_count?.toLocaleString() ?? '?'} {t('rows', 'baris')}</span>
          </span>
        </div>

        {/* ── Step 1: Join type ── */}
        {step === 1 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <JoinTypeOption
              selected={joinType === 'union'}
              onSelect={() => setJoinType('union')}
              titleEn="Stack rows (Union)" titleBm="Susun baris (Union)"
              descEn="Append all rows from both datasets. Use when both sides have the same columns."
              descBm="Tambah semua baris dari kedua-dua dataset. Guna apabila kedua-dua dataset mempunyai lajur sama."
            />
            <JoinTypeOption
              selected={joinType === 'inner'}
              onSelect={() => setJoinType('inner')}
              titleEn="Inner join" titleBm="Inner join"
              descEn="Keep only rows that match on the chosen key (drop unmatched)."
              descBm="Simpan hanya baris yang sepadan pada kunci yang dipilih (buang yang tak sepadan)."
            />
            <JoinTypeOption
              selected={joinType === 'left'}
              onSelect={() => setJoinType('left')}
              titleEn="Left join" titleBm="Left join"
              descEn="Keep every row from the left dataset; attach right when matched."
              descBm="Simpan setiap baris dari dataset kiri; lampirkan kanan apabila sepadan."
            />
            <JoinTypeOption
              selected={joinType === 'right'}
              onSelect={() => setJoinType('right')}
              titleEn="Right join" titleBm="Right join"
              descEn="Keep every row from the right dataset; attach left when matched."
              descBm="Simpan setiap baris dari dataset kanan; lampirkan kiri apabila sepadan."
            />
            <JoinTypeOption
              selected={joinType === 'outer'}
              onSelect={() => setJoinType('outer')}
              titleEn="Outer (full) join" titleBm="Outer (full) join"
              descEn="Keep every row from both sides; unmatched cells are left blank."
              descBm="Simpan setiap baris dari kedua-dua belah; sel tak sepadan dibiarkan kosong."
            />

            {isUnion && (
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 8, fontSize: 13, color: 'var(--text-primary)', cursor: 'pointer' }}>
                <input type="checkbox" checked={dedup} onChange={e => setDedup(e.target.checked)} />
                {t('Remove duplicate rows after stacking', 'Buang baris duplikat selepas susun')}
              </label>
            )}
          </div>
        )}

        {/* ── Step 2: Keys (horizontal joins only) ── */}
        {step === 2 && (
          <div>
            {isUnion ? (
              <div style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 8, padding: '14px 16px', fontSize: 13, color: 'var(--text-secondary)' }}>
                {t('Union joins do not need a key — rows from both datasets are stacked. Click Preview to continue.',
                  'Union join tidak memerlukan kunci — baris dari kedua-dua dataset disusun. Klik Pratonton untuk teruskan.')}
              </div>
            ) : previewLoading ? (
              <div style={{ color: 'var(--text-muted)', fontSize: 13, padding: 16 }}>{t('Loading columns…', 'Memuatkan lajur…')}</div>
            ) : sharedKeys.length === 0 ? (
              <div style={{ background: 'var(--warning-bg)', border: '1px solid var(--warning)', borderRadius: 8, padding: '14px 16px', display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                <AlertTriangle size={16} style={{ color: 'var(--warning)', flexShrink: 0, marginTop: 2 }} />
                <div style={{ fontSize: 13 }}>
                  {t('These datasets share no column names. A horizontal join needs at least one matching column on both sides.',
                    'Kedua-dua dataset tidak mempunyai nama lajur yang sama. Join horizontal memerlukan sekurang-kurangnya satu lajur sepadan.')}
                </div>
              </div>
            ) : (
              <>
                <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 10, lineHeight: 1.6 }}>
                  {t('Pick one or more columns that exist in BOTH datasets. Rows will be matched when these values are equal.',
                    'Pilih satu atau lebih lajur yang wujud dalam KEDUA-DUA dataset. Baris akan dipadankan apabila nilai-nilai ini sama.')}
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 8, maxHeight: 260, overflowY: 'auto', padding: 2 }}>
                  {sharedKeys.map(col => {
                    const sel = selectedKeys.includes(col);
                    return (
                      <label key={col} style={{
                        display: 'flex', alignItems: 'center', gap: 8,
                        padding: '8px 12px', borderRadius: 8,
                        border: `1px solid ${sel ? 'var(--kkm-blue)' : 'var(--border)'}`,
                        background: sel ? 'rgba(0,163,224,0.08)' : 'var(--surface-2)',
                        cursor: 'pointer', fontSize: 13,
                      }}>
                        <input type="checkbox" checked={sel} onChange={() => toggleKey(col)} />
                        <span style={{ color: 'var(--text-primary)', fontFamily: 'JetBrains Mono, monospace', fontSize: 12 }}>{col}</span>
                      </label>
                    );
                  })}
                </div>
              </>
            )}
          </div>
        )}

        {/* ── Step 3: Preview & confirm ── */}
        {step === 3 && preview && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: 10 }}>
              <Stat label={t('Result rows', 'Baris hasil')} value={preview.shape.rows.toLocaleString()} accent />
              <Stat label={t('Result cols', 'Lajur hasil')} value={preview.shape.cols.toLocaleString()} />
              {!isUnion && (
                <>
                  <Stat label={t('Matched keys', 'Kunci sepadan')} value={(preview.join_stats.matched_keys ?? 0).toLocaleString()} />
                  <Stat label={t('Left only', 'Kiri sahaja')} value={(preview.join_stats.left_only_keys ?? 0).toLocaleString()} />
                  <Stat label={t('Right only', 'Kanan sahaja')} value={(preview.join_stats.right_only_keys ?? 0).toLocaleString()} />
                </>
              )}
              {isUnion && preview.join_stats.duplicates_removed !== undefined && (
                <Stat label={t('Duplicates removed', 'Duplikat dibuang')} value={preview.join_stats.duplicates_removed.toLocaleString()} />
              )}
            </div>

            <div style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 8, overflow: 'auto', maxHeight: 280 }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
                <thead>
                  <tr style={{ background: 'var(--surface)', borderBottom: '1px solid var(--border)' }}>
                    {preview.columns.slice(0, 12).map(c => (
                      <th key={c} style={{ padding: '6px 10px', textAlign: 'left', fontWeight: 600, color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>{c}</th>
                    ))}
                    {preview.columns.length > 12 && (
                      <th style={{ padding: '6px 10px', color: 'var(--text-muted)' }}>+{preview.columns.length - 12}</th>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {preview.preview.slice(0, 12).map((row, i) => (
                    <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                      {preview.columns.slice(0, 12).map(c => (
                        <td key={c} style={{ padding: '5px 10px', color: 'var(--text-primary)', whiteSpace: 'nowrap', maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          {row[c] == null ? '—' : String(row[c])}
                        </td>
                      ))}
                      {preview.columns.length > 12 && <td />}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
              {t(`Showing first ${Math.min(12, preview.preview.length)} of ${preview.shape.rows.toLocaleString()} rows.`,
                `Menunjukkan ${Math.min(12, preview.preview.length)} daripada ${preview.shape.rows.toLocaleString()} baris pertama.`)}
            </div>
          </div>
        )}

        {/* ── Error ── */}
        {error && (
          <div style={{ marginTop: 14, background: 'var(--danger-bg)', border: '1px solid var(--danger)', borderRadius: 8, padding: '10px 14px', fontSize: 13, color: 'var(--danger)' }}>
            {error}
          </div>
        )}

        {/* ── Footer / nav ── */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 20, paddingTop: 14, borderTop: '1px solid var(--border)' }}>
          <button onClick={onClose} style={btnSecondary}>{t('Cancel', 'Batal')}</button>
          <div style={{ display: 'flex', gap: 8 }}>
            {step > 1 && (
              <button onClick={() => setStep((step - 1) as 1 | 2 | 3)} style={btnSecondary}>
                <ArrowLeft size={14} /> {t('Back', 'Kembali')}
              </button>
            )}
            {step === 1 && (
              <button
                onClick={() => { if (isUnion) runPreview(); else setStep(2); }}
                disabled={previewLoading}
                style={{ ...btnPrimary, opacity: previewLoading ? 0.5 : 1 }}
              >
                {previewLoading ? t('Loading…', 'Memuatkan…') : t('Next', 'Seterusnya')} <ArrowRight size={14} />
              </button>
            )}
            {step === 2 && (
              <button onClick={runPreview} disabled={!canContinueStep2 || previewLoading} style={{ ...btnPrimary, opacity: (!canContinueStep2 || previewLoading) ? 0.5 : 1 }}>
                {previewLoading ? t('Previewing…', 'Memuatkan…') : t('Preview', 'Pratonton')} <ArrowRight size={14} />
              </button>
            )}
            {step === 3 && (
              <button onClick={runJoin} disabled={running} style={{ ...btnPrimary, opacity: running ? 0.5 : 1 }}>
                <CheckCircle2 size={14} />
                {running ? t('Joining…', 'Sedang cantum…') : t('Run Join', 'Jalankan Join')}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── tiny inline atoms ─────────────────────────────────────────────── */

function JoinTypeOption({ selected, onSelect, titleEn, titleBm, descEn, descBm }: {
  selected: boolean; onSelect: () => void;
  titleEn: string; titleBm: string; descEn: string; descBm: string;
}) {
  const { t } = useLang();
  return (
    <div
      onClick={onSelect}
      style={{
        padding: '12px 14px', borderRadius: 10, cursor: 'pointer',
        border: `1px solid ${selected ? 'var(--kkm-blue)' : 'var(--border)'}`,
        background: selected ? 'rgba(0,163,224,0.08)' : 'var(--surface-2)',
        transition: 'all var(--transition)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
        <span style={{
          width: 14, height: 14, borderRadius: '50%',
          border: `2px solid ${selected ? 'var(--kkm-blue)' : 'var(--border)'}`,
          background: selected ? 'var(--kkm-blue)' : 'transparent',
          flexShrink: 0,
        }} />
        <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{t(titleEn, titleBm)}</span>
      </div>
      <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5, paddingLeft: 22 }}>
        {t(descEn, descBm)}
      </div>
    </div>
  );
}

function Stat({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div style={{
      background: 'var(--surface-2)', border: '1px solid var(--border)',
      borderRadius: 8, padding: '8px 12px',
    }}>
      <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 18, fontWeight: 700, color: accent ? 'var(--kkm-blue)' : 'var(--text-primary)', fontFamily: 'JetBrains Mono, monospace' }}>{value}</div>
    </div>
  );
}
