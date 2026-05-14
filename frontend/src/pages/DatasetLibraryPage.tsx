import React, { useEffect, useState } from 'react';
import { api } from '../api/client';

interface Dataset {
  id: number;
  cache_id: string;
  filename: string;
  source_type: string;
  row_count: number;
  quality_score: number;
  created_at: string;
}

interface CompareResponse {
  datasets: Dataset[];
  deltas: Record<string, number>;
  trend: Record<string, 'improving' | 'worsening' | 'stable'>;
}

interface EntityProfile {
  ic: string;
  sources: string[];
}

interface EntityLinkResponse {
  total_groups: number;
  linked_groups: number;
  unlinked: number;
  rows_written: number;
  profiles: EntityProfile[];
}

const INDICATORS = ['stunting_rate', 'wasting_rate', 'underweight_rate', 'overweight_rate', 'completeness'];
const TREND_ICON = { improving: '↓', worsening: '↑', stable: '→' };
const TREND_COLOR = { improving: 'var(--success)', worsening: 'var(--danger)', stable: 'var(--text-muted)' };

function qBadge(score: number): React.CSSProperties {
  const color = score >= 80 ? 'var(--success)' : score >= 60 ? 'var(--warning)' : 'var(--danger)';
  return { color, fontWeight: 700, fontSize: 12 };
}

export function DatasetLibraryPage() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [selected, setSelected] = useState<number[]>([]);
  const [comparison, setComparison] = useState<CompareResponse | null>(null);
  const [entityResult, setEntityResult] = useState<EntityLinkResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [comparing, setComparing] = useState<boolean>(false);
  const [linking, setLinking] = useState<boolean>(false);
  const [entityOpen, setEntityOpen] = useState<boolean>(false);

  useEffect(() => {
    api
      .get<Dataset[]>('/datasets')
      .then(r => setDatasets(r.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const compare = async (): Promise<void> => {
    setComparing(true);
    try {
      const res = await api.post<CompareResponse>('/datasets/compare', { dataset_ids: selected });
      setComparison(res.data);
    } catch {
      // error handling
    } finally {
      setComparing(false);
    }
  };

  const linkEntities = async (): Promise<void> => {
    setLinking(true);
    try {
      const res = await api.post<EntityLinkResponse>('/entity/link', { dataset_ids: selected });
      setEntityResult(res.data);
      setEntityOpen(true);
    } catch {
      // error handling
    } finally {
      setLinking(false);
    }
  };

  const toggleSelect = (id: number): void => {
    setSelected(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    );
  };

  const closeEntity = (): void => {
    setEntityOpen(false);
  };

  return (
    <div style={pg.container}>
      <h1 style={pg.h1}>Perpustakaan Dataset</h1>

      <div style={pg.layout}>
        {/* Left Panel */}
        <div style={pg.sidePanel}>
          <div style={pg.sidePanelTitle}>Senarai Dataset</div>

          {loading ? (
            <div style={pg.loadingText}>Memuatkan…</div>
          ) : datasets.length === 0 ? (
            <div style={pg.emptyText}>Tiada dataset ditemui.</div>
          ) : (
            <div style={pg.datasetList}>
              {datasets.map(d => (
                <div
                  key={d.id}
                  style={{
                    ...pg.datasetItem,
                    ...(selected.includes(d.id) ? pg.datasetItemSelected : {}),
                  }}
                  onClick={() => toggleSelect(d.id)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={e => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      toggleSelect(d.id);
                    }
                  }}
                >
                  <div style={pg.datasetCheckRow}>
                    <span style={pg.checkbox}>{selected.includes(d.id) ? '☑' : '☐'}</span>
                    <span style={pg.datasetFilename}>{d.filename}</span>
                  </div>
                  <div style={pg.datasetMeta}>
                    <span style={pg.sourceTypeBadge}>{d.source_type}</span>
                    <span style={qBadge(d.quality_score)}>{d.quality_score}%</span>
                  </div>
                </div>
              ))}
            </div>
          )}

          <div style={pg.sidePanelActions}>
            <button
              style={{
                ...pg.compareBtn,
                opacity: selected.length < 2 ? 0.5 : 1,
              }}
              disabled={selected.length < 2 || comparing}
              onClick={compare}
            >
              {comparing ? 'Membandingkan…' : 'Bandingkan'}
            </button>
            <button
              style={{
                ...pg.linkBtn,
                opacity: selected.length < 2 ? 0.5 : 1,
              }}
              disabled={selected.length < 2 || linking}
              onClick={linkEntities}
            >
              {linking ? 'Memautkan…' : 'Pautan Rekod Entiti'}
            </button>
          </div>
        </div>

        {/* Right Main Area */}
        <div style={pg.main}>
          {!comparison && !entityOpen && (
            <div style={pg.empty}>Tiada data untuk dipaparkan.</div>
          )}

          {comparison && (
            <div style={pg.comparisonCard}>
              <div style={pg.cardHeader}>Perbandingan Indikator</div>
              <div style={pg.tableWrapper}>
                <table style={pg.table}>
                  <thead>
                    <tr>
                      <th style={pg.th}>Penunjuk</th>
                      {comparison.datasets.map(d => (
                        <th key={d.id} style={pg.th}>
                          {d.filename}
                        </th>
                      ))}
                      <th style={pg.th}>Delta</th>
                    </tr>
                  </thead>
                  <tbody>
                    {INDICATORS.map(indicator => {
                      const delta = comparison.deltas[indicator];
                      const trend = comparison.trend[indicator];
                      const deltaColor =
                        delta > 0
                          ? 'var(--danger)'
                          : delta < 0
                            ? 'var(--success)'
                            : 'var(--text-muted)';

                      return (
                        <tr key={indicator} style={pg.tr}>
                          <td style={pg.td}>{indicator.replace(/_/g, ' ')}</td>
                          {comparison.datasets.map(d => (
                            <td key={d.id} style={pg.td}>
                              {(d as any)[indicator] != null
                                ? `${(((d as any)[indicator] as number) * 100).toFixed(1)}%`
                                : '—'}
                            </td>
                          ))}
                          <td style={{ ...pg.td, fontWeight: 700, color: deltaColor }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                              <span>
                                {delta != null
                                  ? `${delta > 0 ? '+' : ''}${delta.toFixed(1)}pp`
                                  : '—'}
                              </span>
                              {trend && (
                                <span
                                  style={{
                                    fontSize: 11,
                                    fontWeight: 600,
                                    padding: '2px 6px',
                                    borderRadius: 4,
                                    backgroundColor:
                                      trend === 'improving'
                                        ? 'var(--success-bg)'
                                        : trend === 'worsening'
                                          ? 'var(--danger-bg)'
                                          : 'var(--surface)',
                                    color:
                                      trend === 'improving'
                                        ? 'var(--success)'
                                        : trend === 'worsening'
                                          ? 'var(--danger)'
                                          : 'var(--text-muted)',
                                  }}
                                >
                                  {TREND_ICON[trend]}{' '}
                                  {trend === 'improving'
                                    ? 'Lebih baik'
                                    : trend === 'worsening'
                                      ? 'Memburuk'
                                      : 'Stabil'}
                                </span>
                              )}
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {entityOpen && entityResult && (
            <div style={pg.entityCard}>
              <div style={pg.entityCardHeader}>
                <div style={pg.cardHeader}>Pautan Rekod Entiti</div>
                <button style={pg.closeBtn} onClick={closeEntity}>
                  Tutup
                </button>
              </div>

              <div style={pg.entityStats}>
                <StatPill label="Jumlah Kumpulan" value={entityResult.total_groups} />
                <StatPill label="Berjaya Dipautkan" value={entityResult.linked_groups} />
                <StatPill label="Tidak Dipautkan" value={entityResult.unlinked} />
                <StatPill label="Baris Ditulis" value={entityResult.rows_written} />
              </div>

              <div style={pg.profilesContainer}>
                {entityResult.profiles.slice(0, 20).map(profile => (
                  <div key={profile.ic} style={pg.profileRow}>
                    <span style={pg.profileIc}>{profile.ic}</span>
                    <span style={pg.profileSources}>{profile.sources.join(', ')}</span>
                  </div>
                ))}
                {entityResult.profiles.length > 20 && (
                  <div style={pg.moreProfiles}>
                    … dan {entityResult.profiles.length - 20} profil lagi
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function StatPill({ label, value }: { label: string; value: number }) {
  return (
    <div style={pg.statPill}>
      <div style={pg.statLabel}>{label}</div>
      <div style={pg.statValue}>{value.toLocaleString()}</div>
    </div>
  );
}

const pg: Record<string, React.CSSProperties> = {
  container: { padding: '20px' },
  h1: { margin: '0 0 20px', fontSize: 22, fontWeight: 700, color: 'var(--text-primary)' },
  layout: { display: 'grid', gridTemplateColumns: '250px 1fr', gap: 20 },

  // Left Panel
  sidePanel: {
    background: 'var(--surface)',
    borderRadius: 'var(--radius-lg)',
    border: '0.5px solid var(--border)',
    display: 'flex',
    flexDirection: 'column',
    height: 'fit-content',
  },
  sidePanelTitle: {
    fontSize: 12,
    fontWeight: 700,
    color: 'var(--text-primary)',
    padding: '14px 16px',
    borderBottom: '0.5px solid var(--border)',
  },
  loadingText: { padding: '20px 16px', fontSize: 13, color: 'var(--text-muted)', textAlign: 'center' },
  emptyText: { padding: '20px 16px', fontSize: 13, color: 'var(--text-muted)', textAlign: 'center' },
  datasetList: { flex: 1, overflowY: 'auto' as const },
  datasetItem: {
    padding: '12px 16px',
    borderBottom: '0.5px solid var(--border)',
    cursor: 'pointer',
    transition: 'all 0.15s ease',
    userSelect: 'none',
  },
  datasetItemSelected: { background: 'var(--navy)' },
  datasetCheckRow: { display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 },
  checkbox: { fontSize: 16, color: 'var(--blue)', fontWeight: 700 },
  datasetFilename: {
    fontSize: 12,
    fontWeight: 600,
    color: 'var(--text-primary)',
    fontFamily: 'var(--font-mono)',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
  datasetMeta: { display: 'flex', gap: 8, alignItems: 'center', paddingLeft: 24 },
  sourceTypeBadge: {
    background: 'var(--surface-2)',
    color: 'var(--text-secondary)',
    borderRadius: 4,
    padding: '2px 6px',
    fontSize: 10,
    fontWeight: 600,
  },
  sidePanelActions: {
    padding: '12px 16px',
    borderTop: '0.5px solid var(--border)',
    display: 'flex',
    flexDirection: 'column',
    gap: 10,
  },
  compareBtn: {
    padding: '10px 12px',
    background: 'var(--blue)',
    color: '#fff',
    border: 'none',
    borderRadius: 'var(--radius-md)',
    fontSize: 13,
    fontWeight: 600,
    cursor: 'pointer',
    transition: 'all 0.15s ease',
  },
  linkBtn: {
    padding: '10px 12px',
    background: 'transparent',
    color: 'var(--blue)',
    border: '0.5px solid var(--blue)',
    borderRadius: 'var(--radius-md)',
    fontSize: 13,
    fontWeight: 600,
    cursor: 'pointer',
    transition: 'all 0.15s ease',
  },

  // Main Area
  main: { flex: 1 },
  empty: { fontSize: 14, color: 'var(--text-muted)', padding: '60px 20px', textAlign: 'center' },

  // Comparison Card
  comparisonCard: {
    background: 'var(--surface)',
    borderRadius: 'var(--radius-lg)',
    border: '0.5px solid var(--border)',
    overflow: 'hidden',
  },
  cardHeader: {
    fontSize: 12,
    fontWeight: 700,
    color: 'var(--text-primary)',
    padding: '14px 20px',
    borderBottom: '0.5px solid var(--border)',
    background: 'var(--surface-2)',
  },
  tableWrapper: { overflowX: 'auto' as const },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: 13 },
  th: {
    padding: '10px 14px',
    background: 'var(--surface-2)',
    borderBottom: '0.5px solid var(--border)',
    fontWeight: 600,
    color: 'var(--text-primary)',
    textAlign: 'left' as const,
    fontSize: 11,
  },
  tr: { borderBottom: '0.5px solid var(--border)' },
  td: { padding: '12px 14px', color: 'var(--text-primary)' },

  // Entity Card
  entityCard: {
    background: 'var(--surface)',
    borderRadius: 'var(--radius-lg)',
    border: '0.5px solid var(--border)',
    overflow: 'hidden',
    marginTop: 20,
  },
  entityCardHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '14px 20px',
    borderBottom: '0.5px solid var(--border)',
    background: 'var(--surface-2)',
  },
  closeBtn: {
    padding: '6px 12px',
    background: 'transparent',
    color: 'var(--text-secondary)',
    border: '0.5px solid var(--border)',
    borderRadius: 'var(--radius-md)',
    fontSize: 12,
    fontWeight: 600,
    cursor: 'pointer',
    transition: 'all 0.15s ease',
  },
  entityStats: {
    display: 'grid',
    gridTemplateColumns: 'repeat(4, 1fr)',
    gap: 12,
    padding: '16px 20px',
    borderBottom: '0.5px solid var(--border)',
  },
  statPill: {
    background: 'var(--surface-2)',
    borderRadius: 'var(--radius-md)',
    border: '0.5px solid var(--border)',
    padding: '12px 16px',
    textAlign: 'center' as const,
  },
  statLabel: {
    fontSize: 10,
    color: 'var(--text-secondary)',
    fontWeight: 600,
    textTransform: 'uppercase' as const,
    letterSpacing: '0.06em',
    marginBottom: 6,
  },
  statValue: {
    fontSize: 18,
    fontWeight: 700,
    color: 'var(--blue)',
  },
  profilesContainer: { padding: '0 20px' },
  profileRow: {
    display: 'flex',
    gap: 12,
    padding: '10px 0',
    borderBottom: '0.5px solid var(--border)',
    alignItems: 'flex-start',
  },
  profileIc: {
    fontFamily: 'var(--font-mono)',
    fontSize: 12,
    color: 'var(--blue)',
    fontWeight: 600,
    whiteSpace: 'nowrap' as const,
    minWidth: 80,
  },
  profileSources: {
    fontSize: 12,
    color: 'var(--text-secondary)',
  },
  moreProfiles: {
    padding: '10px 0 16px',
    fontSize: 12,
    color: 'var(--text-muted)',
    fontStyle: 'italic' as const,
  },
};
