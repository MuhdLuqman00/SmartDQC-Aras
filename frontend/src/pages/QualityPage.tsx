import React, { useCallback, useEffect, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../api/client';
import { useLang } from '../context/LanguageContext';

/* ── Interfaces ─────────────────────────────────────────────────────────── */

interface QualityColumn {
  name: string;
  null_count: number;
  null_percent: number;
  unique_count: number;
  is_numeric: boolean;
  min?: number;
  max?: number;
  mean?: number;
  sample_values: unknown[];
}

interface QualityResponse {
  total_rows: number;
  total_columns: number;
  overall_completeness: number;
  columns: QualityColumn[];
}

interface AnomalyRow {
  row_index: number;
  reason: string;
}

interface AnomalyResponse {
  anomaly_rows: AnomalyRow[];
  anomaly_rate: number;
}

/* ── ArcGauge ────────────────────────────────────────────────────────────── */

function ArcGauge({ value, label }: { value: number; label: string }): JSX.Element {
  const r = 80;
  const cx = 100;
  const cy = 100;
  const startAngle = -210;
  const endAngle = 30;
  const range = endAngle - startAngle; // 240 degrees
  const arc = (value / 100) * range;

  const toRad = (deg: number) => (deg * Math.PI) / 180;
  const x1 = cx + r * Math.cos(toRad(startAngle));
  const y1 = cy + r * Math.sin(toRad(startAngle));
  const x2 = cx + r * Math.cos(toRad(endAngle));
  const y2 = cy + r * Math.sin(toRad(endAngle));
  const xA = cx + r * Math.cos(toRad(startAngle + arc));
  const yA = cy + r * Math.sin(toRad(startAngle + arc));

  const bgPath = `M ${x1} ${y1} A ${r} ${r} 0 1 1 ${x2} ${y2}`;
  const fgPath = `M ${x1} ${y1} A ${r} ${r} 0 ${arc > 180 ? 1 : 0} 1 ${xA} ${yA}`;

  const colour =
    value >= 80 ? 'var(--success)' : value >= 60 ? 'var(--warning)' : 'var(--danger)';

  return (
    <svg viewBox="0 0 200 160" width={200} height={160}>
      <path
        d={bgPath}
        fill="none"
        stroke="var(--border)"
        strokeWidth={12}
        strokeLinecap="round"
      />
      <path
        d={fgPath}
        fill="none"
        stroke={colour}
        strokeWidth={12}
        strokeLinecap="round"
      />
      <text
        x={cx}
        y={cy + 10}
        textAnchor="middle"
        fontSize={28}
        fontWeight={700}
        fill={colour}
      >
        {value.toFixed(1)}%
      </text>
      <text
        x={cx}
        y={cy + 32}
        textAnchor="middle"
        fontSize={12}
        fill="var(--text-muted)"
      >
        {label}
      </text>
    </svg>
  );
}

/* ── Page ────────────────────────────────────────────────────────────────── */

export function QualityPage(): JSX.Element {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { t } = useLang();

  const [quality, setQuality] = useState<QualityResponse | null>(null);
  const [anomaly, setAnomaly] = useState<AnomalyResponse | null>(null);
  const [cacheId, setCacheId] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [anomalyLoading, setAnomalyLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedRow, setSelectedRow] = useState<string | null>(null);

  /* On mount: read cache_id from URL and run quality check */
  useEffect(() => {
    const id = searchParams.get('cache_id') ?? '';
    setCacheId(id);
    if (!id) return;
    setLoading(true);
    setError(null);
    api
      .post<QualityResponse>('/clean/quality-check', { cache_id: id })
      .then((res) => setQuality(res.data))
      .catch(() => setError('Gagal menjalankan semakan kualiti.'))
      .finally(() => setLoading(false));
  }, [searchParams]);

  /* File upload quality check */
  const runQualityCheck = async (file: File): Promise<void> => {
    setLoading(true);
    setError(null);
    const fd = new FormData();
    fd.append('file', file);
    try {
      const res = await api.post<QualityResponse>('/clean/quality-check', fd);
      setQuality(res.data);
    } catch {
      setError('Gagal menjalankan semakan kualiti.');
    } finally {
      setLoading(false);
    }
  };

  /* Anomaly detection */
  const runAnomalyCheck = async (): Promise<void> => {
    if (!cacheId) return;
    setAnomalyLoading(true);
    try {
      const res = await api.post<AnomalyResponse>(`/ml/suggest?cache_id=${cacheId}`);
      setAnomaly(res.data);
    } catch {
      /* silently fail anomaly */
    } finally {
      setAnomalyLoading(false);
    }
  };

  /* Dropzone */
  const onDrop = useCallback(
    (accepted: File[]) => {
      if (accepted.length > 0) void runQualityCheck(accepted[0]);
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'text/csv': ['.csv'] },
    multiple: false,
  });

  /* Derived */
  const completeness = quality ? quality.overall_completeness : 0;

  return (
    <div style={s.page}>
      <h1 style={s.h1}>{t('Quality Check', 'Semakan Kualiti')}</h1>

      {/* ── Dropzone ── */}
      <div
        {...getRootProps()}
        style={{
          ...s.dropzone,
          borderColor: isDragActive ? 'var(--blue)' : 'var(--border)',
          background: isDragActive ? 'var(--surface-2)' : 'var(--surface)',
        }}
      >
        <input {...getInputProps()} />
        <span style={s.dropText}>
          {isDragActive
            ? t('Drop file here...', 'Lepaskan fail di sini...')
            : t('Drag CSV file or click to upload', 'Seret fail CSV atau klik untuk muat naik')}
        </span>
      </div>

      {error && <div style={s.errorBanner}>{error}</div>}

      {/* ── Gauge row ── */}
      <div style={s.gaugeRow}>
        {quality ? (
          <>
            <ArcGauge value={completeness} label={t('Completeness', 'Kelengkapan')} />
            <div style={s.statsRow}>
              <div style={s.stat}>
                <span style={s.statLabel}>{t('Total Rows', 'Jumlah Baris')}</span>
                <span style={s.statValue}>{quality.total_rows.toLocaleString()}</span>
              </div>
              <div style={s.stat}>
                <span style={s.statLabel}>{t('Total Columns', 'Jumlah Lajur')}</span>
                <span style={s.statValue}>{quality.total_columns}</span>
              </div>
            </div>
          </>
        ) : (
          <div style={s.emptyGauge}>
            {loading ? t('Analysing quality...', 'Menganalisis kualiti...') : t('No data — upload a file', 'Tiada data — muat naik fail')}
          </div>
        )}
      </div>

      {/* ── Two-column content ── */}
      {quality && (
        <div style={s.twoCol}>
          {/* Left 55%: column table */}
          <div style={s.leftCol}>
            <div style={s.card}>
              <div style={s.cardTitle}>{t('Column Breakdown', 'Pecahan Lajur')}</div>
              <table style={s.table}>
                <thead>
                  <tr>
                    <th style={s.th}>{t('Name', 'Nama')}</th>
                    <th style={s.th}>Null%</th>
                    <th style={s.th}>{t('Type', 'Jenis')}</th>
                  </tr>
                </thead>
                <tbody>
                  {quality.columns.map((col) => (
                    <tr
                      key={col.name}
                      style={{
                        ...s.tr,
                        background:
                          selectedRow === col.name
                            ? 'var(--surface-2)'
                            : 'transparent',
                        cursor: 'pointer',
                        transition: 'all 0.15s ease',
                      }}
                      onClick={() =>
                        setSelectedRow(selectedRow === col.name ? null : col.name)
                      }
                    >
                      <td style={s.td}>
                        <code style={s.code}>{col.name}</code>
                      </td>
                      <td style={s.td}>
                        <div style={s.nullBarWrap}>
                          <div style={s.nullBarTrack}>
                            <div
                              style={{
                                ...s.nullBarFill,
                                width: `${Math.min(col.null_percent * 100, 100)}%`,
                                background:
                                  col.null_percent > 0.15
                                    ? 'var(--danger)'
                                    : col.null_percent > 0.05
                                    ? 'var(--warning)'
                                    : 'var(--success)',
                              }}
                            />
                          </div>
                          <span style={s.nullPct}>
                            {(col.null_percent * 100).toFixed(1)}%
                          </span>
                        </div>
                      </td>
                      <td style={s.td}>
                        <span
                          style={{
                            ...s.badge,
                            background: col.is_numeric
                              ? 'rgba(37,99,235,0.1)'
                              : 'var(--surface-2)',
                            color: col.is_numeric
                              ? 'var(--blue)'
                              : 'var(--text-secondary)',
                          }}
                        >
                          {col.is_numeric ? t('Numeric', 'Angka') : t('Text', 'Teks')}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Right 45%: anomaly panel */}
          <div style={s.rightCol}>
            <div style={s.card}>
              <div style={s.cardTitle}>{t('Anomaly Detection', 'Pengesanan Anomali')}</div>

              <button
                style={{
                  ...s.anomalyBtn,
                  opacity: anomalyLoading ? 0.6 : 1,
                  transition: 'all 0.15s ease',
                }}
                onClick={() => void runAnomalyCheck()}
                disabled={anomalyLoading}
              >
                {anomalyLoading ? t('Analysing...', 'Menganalisis...') : t('Run Anomaly', 'Jalankan Anomali')}
              </button>

              {anomaly && (
                <>
                  <div style={s.anomalyRateRow}>
                    <span style={s.anomalyRateLabel}>{t('Anomaly Rate', 'Kadar Anomali')}</span>
                    <span
                      style={{
                        ...s.anomalyRateBadge,
                        background:
                          anomaly.anomaly_rate > 0.1
                            ? 'var(--danger-bg)'
                            : 'var(--warning-bg)',
                        color:
                          anomaly.anomaly_rate > 0.1
                            ? 'var(--danger)'
                            : 'var(--warning)',
                      }}
                    >
                      {(anomaly.anomaly_rate * 100).toFixed(1)}%
                    </span>
                  </div>

                  {anomaly.anomaly_rows.length > 0 ? (
                    <table style={s.table}>
                      <thead>
                        <tr>
                          <th style={s.th}>{t('Row', 'Baris')}</th>
                          <th style={s.th}>{t('Reason', 'Sebab')}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {anomaly.anomaly_rows.map((row) => (
                          <tr key={row.row_index} style={s.tr}>
                            <td style={{ ...s.td, width: 60 }}>
                              <code style={s.code}>#{row.row_index}</code>
                            </td>
                            <td
                              style={{
                                ...s.td,
                                color: 'var(--text-secondary)',
                                fontSize: 12,
                              }}
                            >
                              {row.reason}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : (
                    <div style={s.noAnomaly}>{t('No anomalies detected.', 'Tiada anomali dikesan.')}</div>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── Bottom CTA ── */}
      {quality && (
        <div style={s.ctaRow}>
          <button
            style={{ ...s.cleanBtn, transition: 'all 0.15s ease' }}
            onClick={() => navigate(`/cleaning?cache_id=${cacheId}`)}
          >
            {t('Run Cleaning →', 'Jalankan Pembersihan →')}
          </button>
        </div>
      )}
    </div>
  );
}

/* ── Styles ──────────────────────────────────────────────────────────────── */

const s: Record<string, React.CSSProperties> = {
  page: {
    padding: '24px 0',
    display: 'flex',
    flexDirection: 'column',
    gap: 20,
  },
  h1: {
    margin: 0,
    fontSize: 22,
    fontWeight: 700,
    color: 'var(--text-primary)',
  },

  /* Dropzone */
  dropzone: {
    height: 80,
    border: '0.5px dashed var(--border)',
    borderRadius: 8,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    cursor: 'pointer',
    transition: 'all 0.15s ease',
  },
  dropText: {
    fontSize: 13,
    color: 'var(--text-muted)',
    pointerEvents: 'none',
  },

  /* Error */
  errorBanner: {
    padding: '10px 14px',
    background: 'var(--danger-bg)',
    color: 'var(--danger)',
    borderRadius: 6,
    fontSize: 13,
    border: '0.5px solid var(--danger)',
  },

  /* Gauge */
  gaugeRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 32,
    padding: '8px 0',
  },
  emptyGauge: {
    fontSize: 14,
    color: 'var(--text-muted)',
    padding: '24px 0',
  },
  statsRow: {
    display: 'flex',
    flexDirection: 'column',
    gap: 12,
  },
  stat: {
    display: 'flex',
    flexDirection: 'column',
    gap: 2,
  },
  statLabel: {
    fontSize: 11,
    color: 'var(--text-muted)',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.05em',
  },
  statValue: {
    fontSize: 20,
    fontWeight: 700,
    color: 'var(--text-primary)',
  },

  /* Two-column */
  twoCol: {
    display: 'grid',
    gridTemplateColumns: '55fr 45fr',
    gap: 16,
    alignItems: 'start',
  },
  leftCol: {},
  rightCol: {},

  /* Card */
  card: {
    background: 'var(--surface)',
    border: '0.5px solid var(--border)',
    borderRadius: 8,
    padding: 20,
    display: 'flex',
    flexDirection: 'column',
    gap: 12,
  },
  cardTitle: {
    fontSize: 11,
    fontWeight: 600,
    color: 'var(--text-secondary)',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.06em',
  },

  /* Table */
  table: {
    width: '100%',
    borderCollapse: 'collapse' as const,
    fontSize: 13,
  },
  th: {
    textAlign: 'left' as const,
    padding: '6px 10px',
    fontSize: 11,
    fontWeight: 600,
    color: 'var(--text-muted)',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.05em',
    borderBottom: '0.5px solid var(--border)',
  },
  tr: {
    borderBottom: '0.5px solid var(--border)',
  },
  td: {
    padding: '9px 10px',
    verticalAlign: 'middle' as const,
  },
  code: {
    fontFamily: 'monospace',
    fontSize: 12,
    color: 'var(--text-primary)',
  },

  /* Null bar */
  nullBarWrap: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
  },
  nullBarTrack: {
    width: 56,
    height: 4,
    background: 'var(--border)',
    borderRadius: 2,
    overflow: 'hidden',
  },
  nullBarFill: {
    height: '100%',
    borderRadius: 2,
  },
  nullPct: {
    fontSize: 12,
    color: 'var(--text-secondary)',
    minWidth: 36,
  },

  /* Badge */
  badge: {
    display: 'inline-block',
    padding: '2px 8px',
    borderRadius: 4,
    fontSize: 11,
    fontWeight: 500,
  },

  /* Anomaly */
  anomalyBtn: {
    padding: '8px 16px',
    background: 'var(--navy)',
    color: '#fff',
    border: 'none',
    borderRadius: 6,
    fontSize: 13,
    fontWeight: 600,
    cursor: 'pointer',
    alignSelf: 'flex-start',
  },
  anomalyRateRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
  },
  anomalyRateLabel: {
    fontSize: 13,
    color: 'var(--text-secondary)',
  },
  anomalyRateBadge: {
    padding: '3px 10px',
    borderRadius: 12,
    fontSize: 13,
    fontWeight: 700,
  },
  noAnomaly: {
    fontSize: 13,
    color: 'var(--text-muted)',
    padding: '8px 0',
  },

  /* Bottom CTA */
  ctaRow: {
    display: 'flex',
    justifyContent: 'flex-end',
    paddingTop: 4,
  },
  cleanBtn: {
    padding: '12px 24px',
    background: 'var(--blue)',
    color: '#fff',
    border: 'none',
    borderRadius: 6,
    fontSize: 14,
    fontWeight: 600,
    cursor: 'pointer',
  },
};
