import React, { useEffect, useMemo, useState } from 'react';
import {
  Link2, Download, Play, Filter, AlertTriangle,
  ChevronDown, ChevronRight, AlertCircle, Info, History,
} from 'lucide-react';
import { api } from '../api/client';
import { useLang } from '../context/LanguageContext';
import { EmptyState } from '../components/EmptyState';
import { formatMytDateTime } from '../lib/formatMyt';

interface Dataset {
  id: string;
  filename: string;
  source_type: string | null;
  row_count: number | null;
  created_at: string;
}

interface LinkSource {
  ic?: string;
  name?: string | null;
  dob?: string | null;
  gender?: string | null;
  state?: string | null;
  district?: string | null;
  measure_date?: string | null;
  weight_kg?: number | null;
  height_cm?: number | null;
  bmi?: number | null;
  waz?: number | null;
  haz?: number | null;
  baz?: number | null;
  source_type: string;
  dataset_id: string;
}

interface ConflictEntry {
  field: string;
  severity: 'hard' | 'soft' | 'strong';
  values: { source_type: string; value: string }[];
}

interface TimelineEntry {
  date: string;
  source_type: string;
  weight_kg: number | null;
  height_cm: number | null;
  bmi: number | null;
  waz: number | null;
  haz: number | null;
  baz: number | null;
}

interface LinkProfile {
  ic: string;
  name: string | null;
  dob: string | null;
  confidence: number;
  match_reasons: string[];
  sources: LinkSource[];
  conflicts: ConflictEntry[];
  profile?: {
    canonical: {
      ic?: string | null;
      name?: string | null;
      dob?: string | null;
      gender?: string | null;
      state?: string | null;
      district?: string | null;
    };
    timeline: TimelineEntry[];
  };
}

interface LinkResult {
  total_groups: number;
  linked_groups: number;
  unlinked: number;
  datasets: Array<{
    dataset_id: string;
    filename: string;
    source_type: string | null;
    records: number;
    created_at?: string | null;
  }>;
  profiles: LinkProfile[];
  warning?: string;
}

interface Settings {
  fuzzy_ic: boolean;
  fuzzy_ic_max_distance: number;
  name_dob_boost: boolean;
  name_fuzzy: boolean;
  name_fuzzy_threshold: number;
  dob_tolerance_days: number;
  location_boost: boolean;
  min_confidence: number;
}

const DEFAULT_SETTINGS: Settings = {
  fuzzy_ic: true,
  fuzzy_ic_max_distance: 1,
  name_dob_boost: true,
  name_fuzzy: true,
  name_fuzzy_threshold: 0.85,
  dob_tolerance_days: 1,
  location_boost: true,
  min_confidence: 0,
};

const reasonColor = (r: string): string => {
  if (r === 'exact_ic' || r === 'name+dob' || r === 'same_state') return 'var(--status-good)';
  if (r.startsWith('fuzzy_ic') || r.startsWith('name_fuzzy'))     return 'var(--status-watch)';
  if (r === 'unmatched') return 'var(--text-muted)';
  return 'var(--text-secondary)';
};
const reasonBg = (r: string): string => {
  if (r === 'exact_ic' || r === 'name+dob' || r === 'same_state') return 'var(--status-good-bg)';
  if (r.startsWith('fuzzy_ic') || r.startsWith('name_fuzzy'))     return 'var(--status-watch-bg)';
  return 'var(--surface-2)';
};

const confidenceColor = (c: number): string => {
  if (c >= 0.95) return 'var(--status-good)';
  if (c >= 0.70) return 'var(--status-watch)';
  if (c >  0.00) return 'var(--status-critical)';
  return 'var(--text-muted)';
};

const severityColor = (sev: 'hard' | 'soft' | 'strong'): string =>
  sev === 'soft' ? 'var(--status-watch)' : 'var(--status-critical)';
const severityBg = (sev: 'hard' | 'soft' | 'strong'): string =>
  sev === 'soft' ? 'var(--status-watch-bg)' : 'var(--status-critical-bg)';

const conflictWorstSeverity = (cs: ConflictEntry[]): 'hard' | 'soft' | 'strong' | null => {
  if (!cs.length) return null;
  if (cs.some(c => c.severity === 'strong')) return 'strong';
  if (cs.some(c => c.severity === 'hard'))   return 'hard';
  return 'soft';
};

/* ── Inline sparkline (no chart library) ─────────────────────────────────
   Plots up to 3 series (WAZ/HAZ/BAZ) over a shared x-axis. Skips series
   with <2 datapoints. ~25 LOC. */
function Sparkline({ timeline, width = 96, height = 28 }: {
  timeline: TimelineEntry[]; width?: number; height?: number;
}): JSX.Element | null {
  if (timeline.length < 2) return null;
  const series: { key: 'waz' | 'haz' | 'baz'; color: string }[] = [
    { key: 'waz', color: 'var(--status-good)' },
    { key: 'haz', color: 'var(--status-watch)' },
    { key: 'baz', color: 'var(--status-critical)' },
  ];
  const active = series.filter(s => timeline.filter(t => t[s.key] != null).length >= 2);
  if (active.length === 0) return null;
  const all = active.flatMap(s => timeline.map(t => t[s.key]).filter((v): v is number => v != null));
  const min = Math.min(...all, -3);
  const max = Math.max(...all,  3);
  const range = (max - min) || 1;
  const pad = 2;
  const w = width - pad * 2;
  const h = height - pad * 2;
  return (
    <svg width={width} height={height} style={{ display: 'block' }}>
      {active.map(s => {
        const pts = timeline.map((t, i) => {
          const v = t[s.key];
          if (v == null) return null;
          const x = pad + (timeline.length === 1 ? w / 2 : (i / (timeline.length - 1)) * w);
          const y = pad + h - ((v - min) / range) * h;
          return `${x.toFixed(1)},${y.toFixed(1)}`;
        }).filter((p): p is string => p !== null);
        return (
          <polyline
            key={s.key}
            points={pts.join(' ')}
            fill="none"
            stroke={s.color}
            strokeWidth={1.4}
            strokeLinejoin="round"
            opacity={0.85}
          />
        );
      })}
    </svg>
  );
}

export function LinkagePage() {
  const { t, lang } = useLang();
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [datasetsLoading, setDatasetsLoading] = useState(true);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const [settings, setSettings] = useState<Settings>({ ...DEFAULT_SETTINGS });
  const [showOnlyLinked,    setShowOnlyLinked]    = useState(true);
  const [showOnlyConflicts, setShowOnlyConflicts] = useState(false);

  const [result, setResult] = useState<LinkResult | null>(null);
  const [running, setRunning] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [expandedTab, setExpandedTab] = useState<Record<string, 'sources' | 'timeline'>>({});

  useEffect(() => {
    api.get<Dataset[]>('/datasets')
      .then(r => setDatasets(r.data))
      .catch(() => setDatasets([]))
      .finally(() => setDatasetsLoading(false));
  }, []);

  const canRun = selected.size >= 2;

  const toggleSelect = (id: string) => setSelected(prev => {
    const next = new Set(prev);
    next.has(id) ? next.delete(id) : next.add(id);
    return next;
  });

  const runLinkage = async () => {
    if (!canRun) return;
    setRunning(true); setError(null); setExpanded(new Set());
    try {
      const r = await api.post<LinkResult>('/entity/link/v2', {
        dataset_ids: Array.from(selected),
        ...settings,
      });
      setResult(r.data);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      setError(err.response?.data?.detail || t('Linkage failed.', 'Pemautan gagal.'));
    } finally {
      setRunning(false);
    }
  };

  const exportCsv = async () => {
    if (!canRun) return;
    setExporting(true);
    try {
      const r = await api.post('/entity/link/v2/export',
        { dataset_ids: Array.from(selected), ...settings },
        { responseType: 'blob' },
      );
      const blob = r.data as Blob;
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = 'SmartDQC_Linkage.csv';
      a.click();
      URL.revokeObjectURL(a.href);
    } catch {
      setError(t('CSV export failed.', 'Eksport CSV gagal.'));
    } finally {
      setExporting(false);
    }
  };

  /* AND-combined filters: "cross-dataset" AND "has conflicts" when both on. */
  const visibleProfiles = useMemo(() => {
    if (!result) return [];
    return result.profiles.filter(p => {
      if (showOnlyLinked    && p.sources.length <= 1)    return false;
      if (showOnlyConflicts && p.conflicts.length === 0) return false;
      return true;
    });
  }, [result, showOnlyLinked, showOnlyConflicts]);

  const datasetLookup = useMemo(() => {
    if (!result) return new Map<string, string>();
    return new Map(result.datasets.map(d => [d.dataset_id, d.filename]));
  }, [result]);

  const toggleExpand = (key: string) => setExpanded(prev => {
    const next = new Set(prev);
    next.has(key) ? next.delete(key) : next.add(key);
    return next;
  });

  /* ── shared atoms ── */
  const sectionCard: React.CSSProperties = {
    background: 'var(--surface)', border: '1px solid var(--border)',
    borderRadius: 'var(--radius-card)', padding: '18px 20px',
    boxShadow: 'var(--shadow-card)',
  };

  if (datasetsLoading) {
    return <div style={{ color: 'var(--text-muted)', padding: 40 }}>{t('Loading…', 'Memuatkan…')}</div>;
  }
  if (!datasets.length) {
    return (
      <EmptyState
        icon={<Link2 size={48} />}
        title={t('No datasets to link', 'Tiada dataset untuk dipautkan')}
        description={t('Upload at least 2 datasets to use cross-dataset linkage.', 'Muat naik sekurang-kurangnya 2 dataset untuk pemautan.')}
        action={{ label: t('Upload Dataset', 'Muat Naik Dataset'), to: '/upload' }}
      />
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      <h1 style={{ margin: 0, fontSize: 22, fontWeight: 700, color: 'var(--text-primary)' }}>
        {t('Cross-Dataset Linkage', 'Pemautan Merentas Dataset')}
      </h1>

      {/* ── 1. Dataset picker ── */}
      <div style={sectionCard}>
        <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 12 }}>
          {t('1 — Select datasets', '1 — Pilih dataset')}
          <span style={{ marginLeft: 8, color: 'var(--text-muted)', fontWeight: 500, textTransform: 'none', letterSpacing: 0 }}>
            ({selected.size} {t('selected', 'dipilih')})
          </span>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 10 }}>
          {datasets.map(ds => {
            const sel = selected.has(ds.id);
            return (
              <label key={ds.id} style={{
                display: 'flex', alignItems: 'flex-start', gap: 10,
                padding: '10px 12px', borderRadius: 8, cursor: 'pointer',
                border: `1px solid ${sel ? 'var(--status-good)' : 'var(--border)'}`,
                background: sel ? 'var(--status-good-bg)' : 'var(--surface-2)',
                transition: 'all var(--transition)',
              }}>
                <input type="checkbox" checked={sel} onChange={() => toggleSelect(ds.id)} style={{ marginTop: 3 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1, minWidth: 0 }}>
                      {ds.filename}
                    </div>
                    {/* Short stable id — datasets frequently share a filename. */}
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)', flexShrink: 0 }}>
                      #{ds.id.slice(0, 6)}
                    </span>
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                    {ds.source_type && <span style={{ textTransform: 'uppercase', fontWeight: 600, marginRight: 6 }}>{ds.source_type}</span>}
                    {ds.row_count?.toLocaleString() ?? '—'} {t('rows', 'baris')}
                    {ds.created_at && <> · {formatMytDateTime(ds.created_at, lang)}</>}
                  </div>
                </div>
              </label>
            );
          })}
        </div>
      </div>

      {/* ── 2. Settings + Run ── */}
      <div style={sectionCard}>
        <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 12 }}>
          {t('2 — Matching settings', '2 — Tetapan padanan')}
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 14, marginBottom: 14 }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, cursor: 'pointer' }}>
            <input
              type="checkbox" checked={settings.fuzzy_ic}
              onChange={e => setSettings(s => ({ ...s, fuzzy_ic: e.target.checked }))}
            />
            <span style={{ display: 'flex', flexDirection: 'column' }}>
              <span>{t('Fuzzy IC match', 'Padanan IC kabur')}</span>
              <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>
                {t('(tolerates a single typo)', '(tolak satu salah taip)')}
              </span>
            </span>
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, cursor: 'pointer' }}>
            <input
              type="checkbox" checked={settings.name_fuzzy}
              onChange={e => setSettings(s => ({ ...s, name_fuzzy: e.target.checked }))}
            />
            <span style={{ display: 'flex', flexDirection: 'column' }}>
              <span>{t('Fuzzy name match', 'Padanan nama kabur')}</span>
              <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>
                {t('(strips BIN/BINTI, tolerates typos)', '(buang BIN/BINTI, tolak salah taip)')}
              </span>
            </span>
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, cursor: 'pointer' }}>
            <input
              type="checkbox" checked={settings.location_boost}
              onChange={e => setSettings(s => ({ ...s, location_boost: e.target.checked }))}
            />
            <span style={{ display: 'flex', flexDirection: 'column' }}>
              <span>{t('Location boost', 'Tampin lokasi')}</span>
              <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>
                {t('(+0.10 when negeri agrees)', '(+0.10 apabila negeri sama)')}
              </span>
            </span>
          </label>
          {/* Stack label above a full-width control so the value can never
              abut the next grid cell's label (the `0.85DOB tolerance`
              collision) and the row stays readable on narrow widths. */}
          <label style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 13 }}>
            <span style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 8 }}>
              <span>{t('Name threshold', 'Ambang nama')}</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-secondary)' }}>
                {settings.name_fuzzy_threshold.toFixed(2)}
              </span>
            </span>
            <input
              type="range" min={0.5} max={0.95} step={0.01}
              value={settings.name_fuzzy_threshold}
              onChange={e => setSettings(s => ({ ...s, name_fuzzy_threshold: parseFloat(e.target.value) }))}
              style={{ width: '100%', accentColor: 'var(--status-good)' }}
            />
          </label>
          <label style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 13 }}>
            <span>{t('DOB tolerance (days)', 'Toleransi tarikh lahir (hari)')}</span>
            <input
              type="number" min={0} max={7} step={1}
              value={settings.dob_tolerance_days}
              onChange={e => setSettings(s => ({ ...s, dob_tolerance_days: Math.max(0, Math.min(7, parseInt(e.target.value || '0', 10))) }))}
              style={{ width: 80, background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 6, padding: '5px 8px', fontSize: 12, color: 'var(--text-primary)' }}
            />
          </label>
          <label style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 13 }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <Filter size={13} style={{ color: 'var(--text-muted)' }} />
              {t('Min confidence', 'Keyakinan min')}
            </span>
            <select
              value={settings.min_confidence}
              onChange={e => setSettings(s => ({ ...s, min_confidence: parseFloat(e.target.value) }))}
              style={{ width: '100%', background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 6, padding: '5px 8px', fontSize: 12, color: 'var(--text-primary)' }}
            >
              <option value={0.0}>{t('Show all', 'Tunjuk semua')}</option>
              <option value={0.6}>0.60+</option>
              <option value={0.7}>0.70+</option>
              <option value={0.85}>0.85+</option>
              <option value={0.95}>0.95+ ({t('exact only', 'tepat sahaja')})</option>
            </select>
          </label>
        </div>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          <button
            onClick={runLinkage}
            disabled={!canRun || running}
            style={{
              background: 'var(--kkm-blue)', color: '#fff', border: 'none',
              borderRadius: 'var(--radius-btn)', padding: '9px 18px',
              fontWeight: 600, fontSize: 13, cursor: canRun ? 'pointer' : 'not-allowed',
              opacity: !canRun || running ? 0.6 : 1,
              display: 'flex', alignItems: 'center', gap: 6,
            }}
          >
            <Play size={14} />
            {running ? t('Linking…', 'Memaut…') : t('Run Linkage', 'Jalankan Pemautan')}
          </button>
          <button
            onClick={exportCsv}
            disabled={!canRun || exporting || !result}
            style={{
              background: 'var(--surface-2)', color: 'var(--text-primary)',
              border: '1px solid var(--border)', borderRadius: 'var(--radius-btn)',
              padding: '9px 16px', fontWeight: 500, fontSize: 13,
              cursor: (!canRun || !result) ? 'not-allowed' : 'pointer',
              opacity: (!canRun || !result || exporting) ? 0.5 : 1,
              display: 'flex', alignItems: 'center', gap: 6,
            }}
          >
            <Download size={14} />
            {exporting ? t('Exporting…', 'Mengeksport…') : t('Export CSV', 'Eksport CSV')}
          </button>
          <button
            onClick={() => setSettings({ ...DEFAULT_SETTINGS })}
            style={{
              background: 'none', border: 'none', color: 'var(--text-muted)',
              fontSize: 12, cursor: 'pointer',
            }}
          >
            {t('Reset settings', 'Pulihkan tetapan')}
          </button>
          {!canRun && (
            <span style={{ alignSelf: 'center', fontSize: 12, color: 'var(--text-muted)' }}>
              {t('Select at least 2 datasets above.', 'Pilih sekurang-kurangnya 2 dataset di atas.')}
            </span>
          )}
        </div>
      </div>

      {error && (
        <div style={{ background: 'var(--danger-bg)', border: '1px solid var(--danger)', borderRadius: 8, padding: '10px 14px', display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: 'var(--danger)' }}>
          <AlertTriangle size={15} /> {error}
        </div>
      )}

      {/* ── 3. Results ── */}
      {result && (
        <div style={sectionCard}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10, marginBottom: 14 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              {t('3 — Results', '3 — Hasil')}
            </div>
            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'center' }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, cursor: 'pointer', color: 'var(--text-secondary)' }}>
                <input
                  type="checkbox"
                  checked={showOnlyLinked}
                  onChange={e => setShowOnlyLinked(e.target.checked)}
                />
                {t('Cross-dataset only', 'Merentas dataset sahaja')}
              </label>
              <label
                title={t('Show only people whose linked records disagree on an identity field.',
                         'Tunjuk hanya orang yang rekod terpautnya bercanggah pada medan identiti.')}
                style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, cursor: 'pointer', color: 'var(--text-secondary)' }}>
                <input
                  type="checkbox"
                  checked={showOnlyConflicts}
                  onChange={e => setShowOnlyConflicts(e.target.checked)}
                />
                {t('Conflicts only', 'Konflik sahaja')}
                <Info size={12} style={{ color: 'var(--text-muted)' }} />
              </label>
            </div>
          </div>

          {/* B1 clarity: explain what a conflict is + the severity colour key
             (matches the cell highlights and the row pill) so "2 konflik" and
             coloured cells are self-explaining. Shown only when the result
             actually contains conflicts. */}
          {result.profiles.some(p => p.conflicts.length > 0) && (
            <div style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 8, padding: '8px 12px', marginBottom: 14, display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '4px 14px', fontSize: 11, color: 'var(--text-secondary)' }}>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                <Info size={12} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
                {t('Conflicts = linked records that disagree on an identity field (gender, state, district, DOB or name).',
                   'Konflik = rekod terpaut yang bercanggah pada medan identiti (jantina, negeri, daerah, tarikh lahir atau nama).')}
              </span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
                <span style={{ width: 8, height: 8, borderRadius: 2, background: 'var(--status-watch)', flexShrink: 0 }} />
                {t('Soft — minor, likely the same person', 'Lembut — kecil, mungkin orang sama')}
              </span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
                <span style={{ width: 8, height: 8, borderRadius: 2, background: 'var(--status-critical)', flexShrink: 0 }} />
                {t('Hard / Strong — clear disagreement, review the match', 'Keras / Kuat — percanggahan jelas, semak padanan')}
              </span>
            </div>
          )}

          {result.warning && (
            <div style={{ background: 'var(--warning-bg)', border: '1px solid var(--warning)', borderRadius: 8, padding: '10px 14px', display: 'flex', alignItems: 'flex-start', gap: 8, fontSize: 13, color: 'var(--text-primary)', marginBottom: 14 }}>
              <AlertTriangle size={15} style={{ color: 'var(--warning)', flexShrink: 0, marginTop: 2 }} />
              {result.warning}
            </div>
          )}

          <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', marginBottom: 16, fontSize: 13 }}>
            {[
              [t('Total groups', 'Jumlah kumpulan'),    result.total_groups],
              [t('Cross-dataset matches', 'Padanan merentas dataset'), result.linked_groups],
              [t('Single-source only', 'Sumber tunggal sahaja'), result.unlinked],
              [t('Groups with conflicts', 'Kumpulan dengan konflik'),
                result.profiles.filter(p => p.conflicts.length > 0).length],
              [t('Datasets compared', 'Dataset dibandingkan'), result.datasets.length],
            ].map(([l, v]) => (
              <div key={String(l)}>
                <div style={{ color: 'var(--text-muted)', fontSize: 11 }}>{l}</div>
                <div style={{ fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{v}</div>
              </div>
            ))}
          </div>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 8 }}>
            {result.datasets.map(d => (
              <span key={d.dataset_id} style={{ fontSize: 11, color: 'var(--text-secondary)', background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 999, padding: '3px 10px' }}>
                {d.filename} · <span style={{ color: 'var(--text-muted)' }}>{d.records.toLocaleString()} {t('rows', 'baris')}</span>
              </span>
            ))}
          </div>

          {/* Filter caption so an empty result reads as "filtered out", not "broken" */}
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 14 }}>
            {t(
              `Showing ${visibleProfiles.length} of ${result.profiles.length} group(s).`,
              `Menunjukkan ${visibleProfiles.length} daripada ${result.profiles.length} kumpulan.`
            )}
          </div>

          {visibleProfiles.length === 0 ? (
            <div style={{ fontSize: 13, color: 'var(--text-muted)', padding: 16, textAlign: 'center' }}>
              {showOnlyLinked || showOnlyConflicts
                ? t('No groups match the current filters.', 'Tiada kumpulan padan dengan tapisan semasa.')
                : t('No groups returned.', 'Tiada kumpulan dikembalikan.')}
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {visibleProfiles.map((p, i) => {
                const key = `${p.ic}-${i}`;
                const isOpen = expanded.has(key);
                const tab = expandedTab[key] ?? 'sources';
                const worst = conflictWorstSeverity(p.conflicts);
                const canonical = p.profile?.canonical ?? {};
                return (
                  <div key={key} style={{ border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden' }}>
                    {/* ── Row header ── */}
                    <div
                      onClick={() => toggleExpand(key)}
                      style={{
                        display: 'flex', alignItems: 'center', gap: 10,
                        padding: '10px 14px', cursor: 'pointer',
                        background: isOpen ? 'var(--surface-2)' : 'transparent',
                      }}
                    >
                      {isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                      <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, fontSize: 13, color: 'var(--text-primary)', minWidth: 130 }}>
                        {p.ic || t('(no IC)', '(tiada IC)')}
                      </span>
                      <span style={{ fontSize: 13, color: 'var(--text-primary)', flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {canonical.name || p.name || <span style={{ color: 'var(--text-muted)' }}>—</span>}
                      </span>
                      <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                        {canonical.dob || p.dob || ''}
                      </span>

                      {/* Conflict pill */}
                      {worst && (
                        <span title={p.conflicts.map(c => `${c.field} (${c.severity})`).join(', ')}
                          style={{
                            display: 'inline-flex', alignItems: 'center', gap: 4,
                            fontSize: 10, fontWeight: 700,
                            background: severityBg(worst), color: severityColor(worst),
                            border: `1px solid ${severityColor(worst)}`,
                            borderRadius: 999, padding: '2px 8px',
                            textTransform: 'uppercase', letterSpacing: '0.04em',
                          }}>
                          <AlertCircle size={10} />
                          {p.conflicts.length} {t('conflict', 'konflik')}
                        </span>
                      )}

                      {/* Reason chips */}
                      <span style={{ display: 'flex', gap: 4, flexShrink: 0, flexWrap: 'wrap' }}>
                        {p.match_reasons.map(r => (
                          <span key={r} style={{
                            fontSize: 10, fontWeight: 700,
                            background: reasonBg(r), color: reasonColor(r),
                            border: `1px solid ${reasonColor(r)}`,
                            borderRadius: 999, padding: '2px 8px',
                            textTransform: 'uppercase', letterSpacing: '0.04em',
                          }}>
                            {r}
                          </span>
                        ))}
                      </span>
                      <span style={{
                        fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: 12,
                        color: confidenceColor(p.confidence), minWidth: 50, textAlign: 'right',
                      }}>
                        {(p.confidence * 100).toFixed(0)}%
                      </span>
                      <span style={{ fontSize: 11, color: 'var(--text-muted)', minWidth: 60, textAlign: 'right' }}>
                        {p.sources.length}× {t('src', 'sumber')}
                      </span>
                    </div>

                    {/* ── Expanded view: Identity strip + tabs ── */}
                    {isOpen && (
                      <div style={{ background: 'var(--surface)', borderTop: '1px solid var(--border)' }}>
                        {/* Identity strip — always visible */}
                        <div style={{ padding: '10px 14px', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 12, background: 'var(--surface-2)', borderBottom: '1px solid var(--border)' }}>
                          {[
                            ['IC',                                 canonical.ic       || p.ic],
                            [t('Name', 'Nama'),                    canonical.name     || p.name],
                            [t('DOB', 'Tarikh lahir'),             canonical.dob      || p.dob],
                            [t('Gender', 'Jantina'),               canonical.gender],
                            [t('State', 'Negeri'),                 canonical.state],
                            [t('District', 'Daerah'),              canonical.district],
                          ].map(([label, val]) => (
                            <div key={String(label)}>
                              <div style={{ fontSize: 9, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                                {label}
                              </div>
                              <div style={{ fontSize: 12, fontWeight: 600, color: val ? 'var(--text-primary)' : 'var(--text-muted)' }}>
                                {val || '—'}
                              </div>
                            </div>
                          ))}
                        </div>

                        {/* Tab switcher */}
                        <div style={{ display: 'flex', gap: 0, borderBottom: '1px solid var(--border)', background: 'var(--surface)' }}>
                          {(['sources', 'timeline'] as const).map(name => {
                            const active = tab === name;
                            const label = name === 'sources'
                              ? t('Sources', 'Sumber')
                              : t('Timeline', 'Garis masa');
                            const Icon  = name === 'sources' ? Info : History;
                            return (
                              <button
                                key={name}
                                onClick={() => setExpandedTab(s => ({ ...s, [key]: name }))}
                                style={{
                                  background: 'none', border: 'none',
                                  borderBottom: `2px solid ${active ? 'var(--status-good)' : 'transparent'}`,
                                  color: active ? 'var(--text-primary)' : 'var(--text-muted)',
                                  fontWeight: active ? 600 : 500, fontSize: 12,
                                  padding: '8px 14px', cursor: 'pointer',
                                  display: 'flex', alignItems: 'center', gap: 6,
                                }}
                              >
                                <Icon size={12} /> {label}
                              </button>
                            );
                          })}
                        </div>

                        {/* Sources tab */}
                        {tab === 'sources' && (
                          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
                            <thead>
                              <tr style={{ background: 'var(--surface-2)' }}>
                                {[t('Source', 'Sumber'), 'IC', t('Name', 'Nama'), t('DOB', 'Tarikh lahir'),
                                  t('Gender', 'Jantina'), t('State', 'Negeri'), t('District', 'Daerah'),
                                  t('Dataset', 'Dataset')].map(h => (
                                  <th key={h} style={{ padding: '6px 10px', textAlign: 'left', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>{h}</th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {p.sources.map((s, j) => {
                                /* Highlight cells whose field is in conflicts. */
                                const conflictBy: Record<string, ConflictEntry> = {};
                                for (const c of p.conflicts) conflictBy[c.field] = c;
                                const cellStyle = (field: string): React.CSSProperties => {
                                  const c = conflictBy[field];
                                  if (!c) return { padding: '6px 10px' };
                                  return {
                                    padding: '6px 10px',
                                    background: severityBg(c.severity),
                                    color: severityColor(c.severity),
                                    fontWeight: 600,
                                  };
                                };
                                return (
                                  <tr key={j} style={{ borderTop: '1px solid var(--border)' }}>
                                    <td style={{ padding: '6px 10px', fontWeight: 600, color: 'var(--text-primary)', textTransform: 'uppercase' }}>{s.source_type}</td>
                                    <td style={{ padding: '6px 10px', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{s.ic || '—'}</td>
                                    <td style={cellStyle('name')}>{s.name || '—'}</td>
                                    <td style={cellStyle('dob')}>{s.dob || '—'}</td>
                                    <td style={cellStyle('gender')}>{s.gender || '—'}</td>
                                    <td style={cellStyle('state')}>{s.state || '—'}</td>
                                    <td style={cellStyle('district')}>{s.district || '—'}</td>
                                    <td style={{ padding: '6px 10px', fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)' }}>
                                      {datasetLookup.get(s.dataset_id) ?? s.dataset_id.slice(0, 8) + '…'}
                                    </td>
                                  </tr>
                                );
                              })}
                            </tbody>
                          </table>
                        )}

                        {/* Timeline tab */}
                        {tab === 'timeline' && (
                          (() => {
                            const tl = p.profile?.timeline ?? [];
                            if (!tl.length) {
                              return (
                                <div style={{ padding: 16, fontSize: 12, color: 'var(--text-muted)', textAlign: 'center' }}>
                                  {t('No measurement dates found across sources.', 'Tiada tarikh pengukuran dijumpai merentas sumber.')}
                                </div>
                              );
                            }
                            return (
                              <>
                                <div style={{ padding: '10px 14px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--border)' }}>
                                  <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                                    {t('Z-score trajectory across all sources', 'Trajektori z-skor merentas semua sumber')}
                                  </div>
                                  <Sparkline timeline={tl} width={140} height={32} />
                                </div>
                                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
                                  <thead>
                                    <tr style={{ background: 'var(--surface-2)' }}>
                                      {[t('Date', 'Tarikh'), t('Source', 'Sumber'),
                                        t('Weight (kg)', 'Berat (kg)'), t('Height (cm)', 'Tinggi (cm)'),
                                        'BMI', 'WAZ', 'HAZ', 'BAZ'].map(h => (
                                        <th key={h} style={{ padding: '6px 10px', textAlign: 'left', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>{h}</th>
                                      ))}
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {tl.map((m, j) => (
                                      <tr key={j} style={{ borderTop: '1px solid var(--border)' }}>
                                        <td style={{ padding: '6px 10px', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{m.date}</td>
                                        <td style={{ padding: '6px 10px', fontWeight: 600, textTransform: 'uppercase' }}>{m.source_type}</td>
                                        <td style={{ padding: '6px 10px', fontFamily: 'var(--font-mono)' }}>{m.weight_kg ?? '—'}</td>
                                        <td style={{ padding: '6px 10px', fontFamily: 'var(--font-mono)' }}>{m.height_cm ?? '—'}</td>
                                        <td style={{ padding: '6px 10px', fontFamily: 'var(--font-mono)' }}>{m.bmi ?? '—'}</td>
                                        <td style={{ padding: '6px 10px', fontFamily: 'var(--font-mono)' }}>{m.waz ?? '—'}</td>
                                        <td style={{ padding: '6px 10px', fontFamily: 'var(--font-mono)' }}>{m.haz ?? '—'}</td>
                                        <td style={{ padding: '6px 10px', fontFamily: 'var(--font-mono)' }}>{m.baz ?? '—'}</td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </>
                            );
                          })()
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
