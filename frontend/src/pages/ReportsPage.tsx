import React, { useState } from 'react';
import { FileText, BarChart3, Table, Lock } from 'lucide-react';
import { api } from '../api/client';
import { useLang } from '../context/LanguageContext';
import { useSession } from '../context/SessionContext';

const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) || 'http://localhost:8000';

interface ReportCard {
  id: string;
  icon: React.ReactNode;
  titleEn: string; titleBm: string;
  descEn: string; descBm: string;
  format: string;
  hasKpiToggle: boolean;
  action: (cacheId: string, includeKpi: boolean) => Promise<void> | void;
}

export function ReportsPage() {
  const { t, lang } = useLang();
  const { cacheId } = useSession();
  const [kpiToggles, setKpiToggles] = useState<Record<string, boolean>>({ pptx: true, pdf: true });
  const [progress, setProgress] = useState<Record<string, boolean>>({});

  const triggerDownload = async (url: string, filename: string) => {
    const r = await api.get(url, { responseType: 'blob' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(r.data);
    a.download = filename;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  const cards: ReportCard[] = [
    {
      id: 'pptx',
      icon: <BarChart3 size={28} style={{ color: 'var(--kkm-blue)' }} />,
      titleEn: 'PowerPoint Report', titleBm: 'Laporan PowerPoint',
      descEn: 'Full ministerial-grade slide deck with KPI charts and district breakdown.',
      descBm: 'Dekset slaid peringkat kementerian dengan carta KPI dan pecahan daerah.',
      format: 'PPTX', hasKpiToggle: true,
      action: async (cacheId, includeKpi) => {
        setProgress(p => ({ ...p, pptx: true }));
        try { await triggerDownload(`/report/pptx?cache_id=${cacheId}&include_kpi=${includeKpi}`, 'SmartDQC_Report.pptx'); }
        finally { setProgress(p => ({ ...p, pptx: false })); }
      },
    },
    {
      id: 'pdf',
      icon: <FileText size={28} style={{ color: 'var(--danger)' }} />,
      titleEn: 'PDF Report', titleBm: 'Laporan PDF',
      descEn: 'Printable summary report with quality metrics and recommendations.',
      descBm: 'Laporan ringkasan yang boleh dicetak dengan metrik kualiti dan cadangan.',
      format: 'PDF', hasKpiToggle: true,
      action: async (cacheId, includeKpi) => {
        setProgress(p => ({ ...p, pdf: true }));
        try { await triggerDownload(`/report/pdf?cache_id=${cacheId}&include_kpi=${includeKpi}`, 'SmartDQC_Report.pdf'); }
        finally { setProgress(p => ({ ...p, pdf: false })); }
      },
    },
    {
      id: 'quality',
      icon: <Table size={28} style={{ color: 'var(--kkm-teal)' }} />,
      titleEn: 'Data Quality Report', titleBm: 'Laporan Kualiti Data',
      descEn: '5-tab Excel workbook: summary, issues, cleaning log, column stats, samples.',
      descBm: 'Buku kerja Excel 5-tab: ringkasan, isu, log pembersihan, statistik lajur, sampel.',
      format: 'XLSX', hasKpiToggle: false,
      action: (cacheId) => {
        window.open(`${BASE}/clean/download-report/${cacheId}`, '_blank');
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
        {cards.map(card => (
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

            <button
              disabled={!cacheId || !!progress[card.id]}
              onClick={() => cacheId && card.action(cacheId, kpiToggles[card.id] ?? true)}
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
        ))}
      </div>
    </div>
  );
}
