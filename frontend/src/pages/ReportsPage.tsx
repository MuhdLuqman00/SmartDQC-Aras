import React, { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api } from '../api/client';
import { useLang } from '../context/LanguageContext';

type ReportFormat = 'pdf' | 'pptx';
type ReportLanguage = 'ms' | 'en';

interface ReportOptions {
  cache_id: string;
  format: ReportFormat;
  include_charts: boolean;
  language: ReportLanguage;
}

export function ReportsPage() {
  const [searchParams] = useSearchParams();
  const { t } = useLang();
  const [options, setOptions] = useState<ReportOptions>({
    cache_id: searchParams.get('cache_id') ?? '',
    format: 'pdf',
    include_charts: true,
    language: 'ms',
  });
  const [generating, setGenerating] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const generate = async (): Promise<void> => {
    setGenerating(true);
    setError(null);
    try {
      const endpoint = options.format === 'pdf' ? '/report/pdf' : '/report/pptx';
      const ext = options.format === 'pdf' ? 'pdf' : 'pptx';
      const res = await api.post(endpoint, options, { responseType: 'blob' });
      const href = URL.createObjectURL(res.data as Blob);
      const a = document.createElement('a');
      a.href = href;
      a.download = `SmartDQC_Report_${Date.now()}.${ext}`;
      a.click();
      URL.revokeObjectURL(href);
    } catch {
      setError(t('Failed to generate report.', 'Gagal menjana laporan.'));
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div style={pg.container}>
      <div style={pg.layout}>
        {/* Left column — ReportOptionsPanel */}
        <div style={pg.optionsCard}>
          <div style={pg.field}>
            <label style={pg.label}>Cache ID</label>
            <input
              style={pg.input}
              placeholder={t('Enter cache_id', 'Masukkan cache_id')}
              value={options.cache_id}
              onChange={e => setOptions({ ...options, cache_id: e.target.value })}
            />
          </div>

          <div style={pg.field}>
            <label style={pg.label}>Format</label>
            <div style={pg.buttonGroup}>
              {(['pdf', 'pptx'] as ReportFormat[]).map(fmt => (
                <button
                  key={fmt}
                  style={{
                    ...pg.formatBtn,
                    ...(options.format === fmt ? pg.formatBtnActive : pg.formatBtnInactive),
                  }}
                  onClick={() => setOptions({ ...options, format: fmt })}
                >
                  {fmt.toUpperCase()}
                </button>
              ))}
            </div>
          </div>

          <div style={pg.field}>
            <label style={pg.label}>{t('Language', 'Bahasa')}</label>
            <div style={pg.buttonGroup}>
              {([
                { code: 'ms', label: 'BM' },
                { code: 'en', label: 'EN' },
              ] as Array<{ code: ReportLanguage; label: string }>).map(lang => (
                <button
                  key={lang.code}
                  style={{
                    ...pg.formatBtn,
                    ...(options.language === lang.code ? pg.formatBtnActive : pg.formatBtnInactive),
                  }}
                  onClick={() => setOptions({ ...options, language: lang.code })}
                >
                  {lang.label}
                </button>
              ))}
            </div>
          </div>

          <div style={pg.field}>
            <label style={pg.checkLabel}>
              <input
                type="checkbox"
                checked={options.include_charts}
                onChange={e => setOptions({ ...options, include_charts: e.target.checked })}
                style={{ marginRight: 8 }}
              />
              {t('Include charts', 'Sertakan carta')}
            </label>
          </div>

          <div style={pg.field}>
            <button
              style={{
                ...pg.generateBtn,
                ...(generating ? pg.generateBtnDisabled : {}),
              }}
              onClick={generate}
              disabled={generating}
            >
              {generating ? t('Generating…', 'Menjana…') : t('Generate Report', 'Jana Laporan')}
            </button>
          </div>

          {error && <div style={pg.errorBanner}>{error}</div>}
        </div>

        {/* Right column — ReportPreviewPane */}
        <div style={pg.previewCard}>
          <div style={pg.previewHeader}>{t('Report Preview', 'Pratonton Laporan')}</div>
          <ol style={pg.chapterList}>
            <li style={pg.chapter}>{t('Executive Summary', 'Ringkasan Eksekutif')}</li>
            <li style={pg.chapter}>{t('Data Quality Overview', 'Gambaran Keseluruhan Kualiti Data')}</li>
            <li style={pg.chapter}>{t('Detailed Column Analysis', 'Analisis Lajur Terperinci')}</li>
            <li style={pg.chapter}>{t('Identified Anomalies & Outliers', 'Anomali dan Pencilan Dikenal Pasti')}</li>
            <li style={pg.chapter}>{t('Cleaning Actions Taken', 'Tindakan Pembersihan Dilakukan')}</li>
            <li style={pg.chapter}>{t('Recommendations & Findings', 'Cadangan dan Penemuan')}</li>
          </ol>
          <div style={pg.previewNote}>{t('Actual preview will be generated after clicking Generate Report', 'Pratonton sebenar akan dijana selepas klik Jana Laporan')}</div>
        </div>
      </div>
    </div>
  );
}

const pg: Record<string, React.CSSProperties> = {
  container: {
    padding: '24px',
  },
  layout: {
    display: 'flex',
    gap: 20,
  },
  optionsCard: {
    width: 300,
    background: 'var(--surface)',
    borderRadius: 12,
    border: '0.5px solid var(--border)',
    padding: 24,
  },
  field: {
    marginBottom: 20,
  },
  label: {
    display: 'block',
    fontSize: 12,
    fontWeight: 600,
    color: 'var(--text-secondary)',
    marginBottom: 8,
    textTransform: 'uppercase',
    letterSpacing: '0.04em',
  },
  input: {
    width: '100%',
    padding: '9px 12px',
    borderRadius: 12,
    border: '0.5px solid var(--border)',
    fontSize: 13,
    color: 'var(--text-primary)',
    background: 'var(--surface-2)',
    boxSizing: 'border-box',
    transition: 'all 0.15s ease',
  },
  buttonGroup: {
    display: 'flex',
    gap: 8,
  },
  formatBtn: {
    flex: 1,
    padding: '8px 12px',
    borderRadius: 12,
    border: '0.5px solid var(--border)',
    fontSize: 12,
    fontWeight: 600,
    cursor: 'pointer',
    transition: 'all 0.15s ease',
  },
  formatBtnActive: {
    background: 'var(--navy)',
    color: '#fff',
    borderColor: 'var(--navy)',
  },
  formatBtnInactive: {
    background: 'var(--surface-2)',
    color: 'var(--text-primary)',
  },
  checkLabel: {
    display: 'flex',
    alignItems: 'center',
    fontSize: 13,
    color: 'var(--text-primary)',
    cursor: 'pointer',
  },
  generateBtn: {
    width: '100%',
    padding: '10px',
    background: 'var(--navy)',
    color: '#fff',
    border: '0.5px solid var(--navy)',
    borderRadius: 12,
    fontSize: 13,
    fontWeight: 700,
    cursor: 'pointer',
    transition: 'all 0.15s ease',
  },
  generateBtnDisabled: {
    opacity: 0.6,
    cursor: 'not-allowed',
  },
  errorBanner: {
    padding: '10px 12px',
    background: 'var(--danger-bg)',
    color: 'var(--danger)',
    borderRadius: 12,
    fontSize: 13,
    border: '0.5px solid var(--danger)',
  },
  previewCard: {
    flex: 1,
    background: 'var(--surface)',
    borderRadius: 12,
    border: '0.5px solid var(--border)',
    overflow: 'hidden',
    display: 'flex',
    flexDirection: 'column',
  },
  previewHeader: {
    background: 'var(--navy)',
    color: '#fff',
    padding: '12px 24px',
    fontSize: 14,
    fontWeight: 700,
  },
  chapterList: {
    flex: 1,
    listStyle: 'decimal',
    margin: 0,
    padding: '24px 24px 24px 40px',
    color: 'var(--text-primary)',
  },
  chapter: {
    fontSize: 13,
    marginBottom: 12,
    lineHeight: 1.5,
  },
  previewNote: {
    padding: '12px 24px',
    fontSize: 12,
    color: 'var(--text-muted)',
    fontStyle: 'italic',
    borderTop: '0.5px solid var(--border)',
    background: 'var(--surface-2)',
  },
};
