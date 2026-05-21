import React, { useState } from 'react';
import { FileText, BarChart3, Table, Lock, ChevronDown, ChevronUp, Database, BookOpen } from 'lucide-react';
import { api } from '../api/client';
import { useLang } from '../context/LanguageContext';
import { useSession } from '../context/SessionContext';

const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) || 'http://localhost:8000';

/* Chart catalog — keys MUST match what backend/export/report.py inspects in
   the `charts` set (build_pdf_bytes / build_pptx_bytes). Recommended charts
   are checked by default and get a gold "Recommended" pill. Adding a new
   chart later: append a row here and update report.py to honour the key. */
interface ChartChoice {
  key: string;
  labelEn: string; labelBm: string;
  recommended: boolean;
}
const CHART_CATALOG: ChartChoice[] = [
  { key: 'quality_bar',       labelEn: 'Data Quality Dimensions',  labelBm: 'Dimensi Kualiti Data',       recommended: true },
  { key: 'nutritional_rates', labelEn: 'Indicator Rates by State', labelBm: 'Kadar Penunjuk Mengikut Negeri', recommended: true },
  { key: 'kpi_vs_target',     labelEn: 'KPI vs National Target',   labelBm: 'KPI lwn Sasaran Kebangsaan',   recommended: true },
];
const DEFAULT_SELECTED = new Set(CHART_CATALOG.filter(c => c.recommended).map(c => c.key));

/* Charts derived from KPI data — they can only render when "Include KPI data"
   is on. When it's off they're disabled in the picker and excluded from the
   request, so a chosen chart never silently goes missing. */
const CHART_REQUIRES_KPI = new Set(['nutritional_rates', 'kpi_vs_target']);

interface ReportCard {
  id: string;
  icon: React.ReactNode;
  titleEn: string; titleBm: string;
  descEn: string; descBm: string;
  format: string;
  hasKpiToggle: boolean;
  hasChartPicker: boolean;
  action: (cacheId: string, includeKpi: boolean, charts: Set<string>) => Promise<void> | void;
}

export function ReportsPage() {
  const { t, lang } = useLang();
  const { cacheId } = useSession();
  const [kpiToggles, setKpiToggles] = useState<Record<string, boolean>>({ pptx: true, pdf: true });
  const [progress, setProgress] = useState<Record<string, boolean>>({});

  /* Per-card chart selection. Defaults to the recommended set; users can
     toggle on/off in the expander. The keys match backend chart keys. */
  const [chartSelection, setChartSelection] = useState<Record<string, Set<string>>>({
    pptx: new Set(DEFAULT_SELECTED),
    pdf:  new Set(DEFAULT_SELECTED),
  });
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  /* The charts that will actually render: the user's selection minus any
     KPI-derived charts when "Include KPI data" is off for this card. */
  const effectiveCharts = (cardId: string): string[] => {
    const kpiOn = kpiToggles[cardId] ?? true;
    const sel = chartSelection[cardId] || new Set<string>();
    return [...sel].filter(k => kpiOn || !CHART_REQUIRES_KPI.has(k));
  };

  const toggleChart = (cardId: string, key: string) => {
    setChartSelection(prev => {
      const next = { ...prev };
      const set = new Set(next[cardId] || []);
      if (set.has(key)) set.delete(key); else set.add(key);
      next[cardId] = set;
      return next;
    });
  };

  const buildChartsParam = (cardId: string): string => {
    // Always send an explicit list so the backend renders exactly what's
    // selected. An empty selection sends the "none" sentinel (→ no charts)
    // instead of an empty string, which the backend would read as "default".
    const eff = effectiveCharts(cardId);
    return eff.length === 0 ? 'none' : eff.join(',');
  };

  const triggerDownload = async (url: string, filename: string) => {
    try {
      const r = await api.get(url, { responseType: 'blob' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(r.data);
      a.download = filename;
      a.click();
      URL.revokeObjectURL(a.href);
    } catch (err: unknown) {
      const e = err as { response?: { data?: unknown } };
      let detail = '';
      const blob = e?.response?.data;
      if (blob instanceof Blob) {
        try { detail = JSON.parse(await blob.text())?.detail ?? ''; } catch { /* non-JSON error body */ }
      }
      alert(t(`Report generation failed. ${detail}`, `Penjanaan laporan gagal. ${detail}`));
    }
  };

  const cards: ReportCard[] = [
    {
      id: 'pptx',
      icon: <BarChart3 size={28} style={{ color: 'var(--kkm-blue)' }} />,
      titleEn: 'PowerPoint Report', titleBm: 'Laporan PowerPoint',
      descEn: 'Full ministerial-grade slide deck with KPI charts and district breakdown.',
      descBm: 'Dekset slaid peringkat kementerian dengan carta KPI dan pecahan daerah.',
      format: 'PPTX', hasKpiToggle: true, hasChartPicker: true,
      action: async (cacheId, includeKpi, charts) => {
        setProgress(p => ({ ...p, pptx: true }));
        try {
          const chartsParam = buildChartsParam('pptx');
          const qs = `cache_id=${cacheId}&include_kpi=${includeKpi}${chartsParam ? `&charts=${chartsParam}` : ''}`;
          void charts; // already encoded above
          await triggerDownload(`/report/pptx?${qs}`, 'SmartDQC_Report.pptx');
        }
        finally { setProgress(p => ({ ...p, pptx: false })); }
      },
    },
    {
      id: 'pdf',
      icon: <FileText size={28} style={{ color: 'var(--danger)' }} />,
      titleEn: 'PDF Report', titleBm: 'Laporan PDF',
      descEn: 'Printable summary report with quality metrics and recommendations.',
      descBm: 'Laporan ringkasan yang boleh dicetak dengan metrik kualiti dan cadangan.',
      format: 'PDF', hasKpiToggle: true, hasChartPicker: true,
      action: async (cacheId, includeKpi, charts) => {
        setProgress(p => ({ ...p, pdf: true }));
        try {
          const chartsParam = buildChartsParam('pdf');
          const qs = `cache_id=${cacheId}&include_kpi=${includeKpi}${chartsParam ? `&charts=${chartsParam}` : ''}`;
          void charts;
          await triggerDownload(`/report/pdf?${qs}`, 'SmartDQC_Report.pdf');
        }
        finally { setProgress(p => ({ ...p, pdf: false })); }
      },
    },
    {
      id: 'quality',
      icon: <Table size={28} style={{ color: 'var(--kkm-teal)' }} />,
      titleEn: 'Data Quality Report', titleBm: 'Laporan Kualiti Data',
      descEn: '5-tab Excel workbook: summary, issues, cleaning log, column stats, samples.',
      descBm: 'Buku kerja Excel 5-tab: ringkasan, isu, log pembersihan, statistik lajur, sampel.',
      format: 'XLSX', hasKpiToggle: false, hasChartPicker: false,
      action: (cacheId) => {
        window.open(`${BASE}/clean/download-report/${cacheId}`, '_blank');
      },
    },
    {
      id: 'tableau',
      icon: <Database size={28} style={{ color: 'var(--kkm-blue)' }} />,
      titleEn: 'Tableau Aggregation', titleBm: 'Agregasi Tableau',
      descEn: 'Flat aggregated table (geo × age group × indicator × year) for Tableau / BI tools.',
      descBm: 'Jadual agregat rata (geo × kumpulan umur × indikator × tahun) untuk Tableau / alat BI.',
      format: 'CSV', hasKpiToggle: false, hasChartPicker: false,
      action: (cacheId) => {
        window.open(`${BASE}/export/aggregated-cached/${cacheId}?fmt=csv`, '_blank');
      },
    },
    {
      id: 'dictionary',
      icon: <BookOpen size={28} style={{ color: 'var(--kkm-teal)' }} />,
      titleEn: 'Data Dictionary', titleBm: 'Kamus Data',
      descEn: 'Definitions of all derived fields — WHO z-scores, KKM indicators, age bands.',
      descBm: 'Definisi semua medan terbitan — z-skor WHO, indikator KKM, jaluran umur.',
      format: 'JSON', hasKpiToggle: false, hasChartPicker: false,
      action: () => {
        window.open(`${BASE}/data-dictionary`, '_blank');
      },
    },
  ];

  return (
    <div>
      {!cacheId && (
        <div style={{
          background: 'var(--warning-bg)', border: '1px solid var(--warning)',
          borderRadius: 10, padding: '14px 18px', marginBottom: 24,
          display: 'flex', alignItems: 'center', gap: 10, fontSize: 13,
        }}>
          <Lock size={15} style={{ color: 'var(--warning)' }} />
          {t('No active session — reports are disabled.', 'Tiada sesi aktif — laporan dilumpuhkan.')}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 20 }}>
        {cards.map(card => {
          const sel = chartSelection[card.id] || new Set<string>();
          const kpiOn = kpiToggles[card.id] ?? true;
          const effCount = effectiveCharts(card.id).length;
          const isExpanded = !!expanded[card.id];
          return (
            <div key={card.id} style={{
              background: 'var(--surface)', border: '1px solid var(--border)',
              borderRadius: 'var(--radius-card)', padding: '24px',
              boxShadow: 'var(--shadow-card)',
              opacity: cacheId ? 1 : 0.6,
              display: 'flex', flexDirection: 'column', gap: 14,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                {card.icon}
                <div>
                  <div style={{ fontWeight: 700, fontSize: 15, fontFamily: "'Plus Jakarta Sans', sans-serif" }}>
                    {lang === 'en' ? card.titleEn : card.titleBm}
                  </div>
                  <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', letterSpacing: '0.05em' }}>
                    {card.format}
                  </div>
                </div>
              </div>

              <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6, flex: 1 }}>
                {lang === 'en' ? card.descEn : card.descBm}
              </p>

              {card.hasKpiToggle && (
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, cursor: 'pointer', color: 'var(--text-secondary)' }}>
                  <input
                    type="checkbox"
                    checked={kpiToggles[card.id] ?? true}
                    onChange={e => setKpiToggles(prev => ({ ...prev, [card.id]: e.target.checked }))}
                    disabled={!cacheId}
                  />
                  {t('Include KPI data', 'Sertakan data KPI')}
                </label>
              )}

              {card.hasChartPicker && (
                <div>
                  <button
                    type="button"
                    onClick={() => setExpanded(prev => ({ ...prev, [card.id]: !isExpanded }))}
                    disabled={!cacheId}
                    style={{
                      background: 'none', border: 'none', padding: 0, cursor: cacheId ? 'pointer' : 'not-allowed',
                      color: 'var(--kkm-sky)', fontSize: 12, fontWeight: 600,
                      display: 'flex', alignItems: 'center', gap: 4,
                    }}
                  >
                    {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                    {t('Customize charts', 'Sesuaikan carta')}
                    <span style={{ color: 'var(--text-muted)', fontWeight: 500 }}>
                      ({effCount}/{CHART_CATALOG.length})
                    </span>
                  </button>
                  {isExpanded && (
                    <div style={{
                      marginTop: 8, padding: '10px 12px',
                      background: 'var(--surface-2)', border: '1px solid var(--border)',
                      borderRadius: 8, display: 'flex', flexDirection: 'column', gap: 6,
                    }}>
                      {CHART_CATALOG.map(c => {
                        const needsKpiOff = CHART_REQUIRES_KPI.has(c.key) && !kpiOn;
                        const checked = sel.has(c.key) && !needsKpiOff;
                        return (
                          <label key={c.key} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, cursor: needsKpiOff ? 'not-allowed' : 'pointer', color: needsKpiOff ? 'var(--text-muted)' : 'var(--text-primary)' }}>
                            <input
                              type="checkbox"
                              checked={checked}
                              onChange={() => toggleChart(card.id, c.key)}
                              disabled={!cacheId || needsKpiOff}
                            />
                            <span style={{ flex: 1 }}>{lang === 'en' ? c.labelEn : c.labelBm}</span>
                            {needsKpiOff && (
                              <span style={{ fontSize: 9, fontWeight: 600, color: 'var(--text-muted)', fontStyle: 'italic' }}>
                                {t('needs KPI', 'perlu KPI')}
                              </span>
                            )}
                            {c.recommended && (
                              <span style={{
                                fontSize: 9, fontWeight: 700,
                                background: 'var(--gradient-gold)', color: '#0F1B2F',
                                borderRadius: 999, padding: '1px 7px',
                                letterSpacing: '0.04em', textTransform: 'uppercase',
                              }}>
                                {t('Rec.', 'Disyor.')}
                              </span>
                            )}
                          </label>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}

              <button
                disabled={!cacheId || !!progress[card.id]}
                onClick={() => cacheId && card.action(cacheId, kpiToggles[card.id] ?? true, sel)}
                style={{
                  background: cacheId ? 'var(--kkm-blue)' : 'var(--border)',
                  color: cacheId ? '#fff' : 'var(--text-muted)',
                  border: 'none', borderRadius: 'var(--radius-btn)', padding: '10px',
                  fontWeight: 600, fontSize: 14, cursor: cacheId ? 'pointer' : 'not-allowed',
                  opacity: progress[card.id] ? 0.6 : 1,
                  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                }}
              >
                {!cacheId && <Lock size={14} />}
                {progress[card.id]
                  ? t('Generating…', 'Sedang menjana…')
                  : cacheId
                    ? t('Generate', 'Jana')
                    : t('No active session', 'Tiada sesi aktif')}
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
