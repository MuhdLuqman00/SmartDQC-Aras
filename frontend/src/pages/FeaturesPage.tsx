import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FileInput, GitMerge, Brush, Calculator, ShieldCheck, BarChart3,
  PieChart, Download, ScanSearch, Lightbulb, TrendingUp, Wand2,
  MessageSquare, Link2, FileText, Target, ArrowUpRight,
} from 'lucide-react';
import { useLang } from '../context/LanguageContext';

interface Feat {
  n: number;
  icon: React.ReactNode;
  en: string; bm: string;
  descEn: string; descBm: string;
  to: string;
  /* Plain-language "key detail" shown in the card footer. Replaces the raw
     API paths (dev noise for KKM users) the audit flagged (14 · P3). */
  techEn: string; techBm: string;
}

const FEATURES: Feat[] = [
  { n: 1,  icon: <FileInput size={18} />,  en: 'Data Input & Detection', bm: 'Input & Pengesanan Data',
    descEn: 'CSV/XLSX ingest with automatic source-type detection.', descBm: 'Muat naik CSV/XLSX dengan pengesanan jenis sumber automatik.',
    to: '/upload', techEn: 'Auto-detects MyVASS, NCDC & KPM formats', techBm: 'Auto-kesan format MyVASS, NCDC & KPM' },
  { n: 2,  icon: <GitMerge size={18} />,   en: 'Column Mapping (AI)', bm: 'Pemetaan Lajur (AI)',
    descEn: 'Fuzzy + AI schema mapping across 3 drift scenarios.', descBm: 'Pemetaan skema kabur + AI merentas 3 senario.',
    to: '/upload', techEn: 'AI matches your columns to the standard schema', techBm: 'AI memadankan lajur anda ke skema standard' },
  { n: 3,  icon: <Brush size={18} />,      en: 'Data Cleaning', bm: 'Pembersihan Data',
    descEn: 'Source-specific cleaning, IC validation, imputation.', descBm: 'Pembersihan khusus sumber, pengesahan IC, imputasi.',
    to: '/cleaning', techEn: 'Source-specific rules with a full audit trail', techBm: 'Peraturan khusus sumber dengan jejak audit penuh' },
  { n: 4,  icon: <Calculator size={18} />, en: 'Derived Fields', bm: 'Medan Terbitan',
    descEn: 'Age, geo, WHO Z-scores and nutrition indicators.', descBm: 'Umur, geo, Z-skor WHO dan penunjuk pemakanan.',
    to: '/explorer', techEn: 'Computes WHO 2006 nutrition indicators', techBm: 'Mengira penunjuk pemakanan WHO 2006' },
  { n: 5,  icon: <ShieldCheck size={18} />, en: 'Quality Assessment', bm: 'Penilaian Kualiti',
    descEn: '7-dimension quality rubric + 5-tab Excel report.', descBm: 'Rubrik kualiti 7-dimensi + laporan Excel 5-tab.',
    to: '/quality', techEn: '7-dimension scoring with an Excel report', techBm: 'Pemarkahan 7-dimensi dengan laporan Excel' },
  { n: 6,  icon: <BarChart3 size={18} />,  en: 'Statistical Analysis', bm: 'Analisis Statistik',
    descEn: 'Numerical, categorical and indicator statistics.', descBm: 'Statistik berangka, kategori dan penunjuk.',
    to: '/explorer', techEn: 'Per-column and indicator statistics', techBm: 'Statistik setiap lajur dan penunjuk' },
  { n: 7,  icon: <PieChart size={18} />,   en: 'Visualization', bm: 'Visualisasi',
    descEn: 'Choropleth map, KPI charts, column distributions.', descBm: 'Peta koropleth, carta KPI, taburan lajur.',
    to: '/geo', techEn: 'Interactive maps and charts', techBm: 'Peta dan carta interaktif' },
  { n: 8,  icon: <Download size={18} />,   en: 'Export & Integration', bm: 'Eksport & Integrasi',
    descEn: 'Cleaned CSV/XLSX, Tableau aggregation, data dictionary.', descBm: 'CSV/XLSX bersih, agregasi Tableau, kamus data.',
    to: '/reports', techEn: 'Cleaned files, Tableau feed & data dictionary', techBm: 'Fail bersih, suapan Tableau & kamus data' },
  { n: 9,  icon: <ScanSearch size={18} />,   en: 'AI Insight Generation', bm: 'Penjanaan Cerapan AI',
    descEn: 'Bilingual 5W1H executive narrative from the data.', descBm: 'Naratif eksekutif 5W1H dwibahasa daripada data.',
    to: '/ai', techEn: 'Runs on local AI — data stays on the server', techBm: 'Guna AI tempatan — data kekal di pelayan' },
  { n: 10, icon: <Lightbulb size={18} />,  en: 'Smart Recommendations', bm: 'Cadangan Pintar',
    descEn: 'Prioritised action recommendations with reasoning.', descBm: 'Cadangan tindakan keutamaan dengan rasional.',
    to: '/ai', techEn: 'Prioritised actions with plain-language reasoning', techBm: 'Tindakan keutamaan dengan rasional yang jelas' },
  { n: 11, icon: <TrendingUp size={18} />, en: 'Composite Risk Index', bm: 'Indeks Risiko Komposit',
    descEn: 'Severity-aware child-level risk score 0–100.', descBm: 'Skor risiko peringkat kanak-kanak 0–100 mengikut keterukan.',
    to: '/geo', techEn: 'A child-level risk score from 0 to 100', techBm: 'Skor risiko kanak-kanak dari 0 hingga 100' },
  { n: 12, icon: <Wand2 size={18} />,      en: 'Smart Data Correction', bm: 'Pembetulan Data Pintar',
    descEn: 'IsolationForest anomalies + inline cell editing.', descBm: 'Anomali IsolationForest + suntingan sel inline.',
    to: '/quality', techEn: 'Flags outliers and lets you fix cells inline', techBm: 'Tanda pencilan dan baiki sel secara inline' },
  { n: 13, icon: <MessageSquare size={18} />, en: 'Natural Language Querying', bm: 'Pertanyaan Bahasa Tabii',
    descEn: 'Ask questions in BM/EN; get answers + charts.', descBm: 'Tanya soalan BM/EN; dapat jawapan + carta.',
    to: '/ai', techEn: 'Ask in Malay or English', techBm: 'Tanya dalam Bahasa Melayu atau Inggeris' },
  { n: 14, icon: <Link2 size={18} />,      en: 'Entity Resolution', bm: 'Resolusi Entiti',
    descEn: 'Cross-dataset record linkage by IC number.', descBm: 'Pautan rekod merentas dataset mengikut nombor IC.',
    to: '/datasets', techEn: 'Links records across datasets by IC', techBm: 'Pautkan rekod merentas dataset mengikut IC' },
  { n: 15, icon: <FileText size={18} />,   en: 'Automated Reports', bm: 'Laporan Automatik',
    descEn: 'KKM-branded PDF & PPTX with charts.', descBm: 'PDF & PPTX berjenama KKM dengan carta.',
    to: '/reports', techEn: 'KKM-branded PDF and PowerPoint', techBm: 'PDF dan PowerPoint berjenama KKM' },
  { n: 16, icon: <Target size={18} />,     en: 'Benchmarking & Targets', bm: 'Penanda Aras & Sasaran',
    descEn: 'RAG vs NPAN/WHO targets + per-district 2027 trajectory.', descBm: 'RAG vs sasaran NPAN/WHO + trajektori 2027 setiap daerah.',
    to: '/geo', techEn: 'Tracks progress to NPAN & WHO 2027 targets', techBm: 'Jejak kemajuan ke sasaran NPAN & WHO 2027' },
];

/* Group the 16 capabilities into pipeline-ordered themes so the page stops
   reading as an undifferentiated feature grid (audit 14 · AI-TELL). Declared
   by feature number so the FEATURES list above stays untouched. */
const THEMES: { key: string; en: string; bm: string; ns: number[] }[] = [
  { key: 'ingest',  en: 'Ingest & Map',     bm: 'Masukan & Pemetaan',     ns: [1, 2, 14] },
  { key: 'clean',   en: 'Clean & Derive',   bm: 'Pembersihan & Terbitan', ns: [3, 4, 12] },
  { key: 'analyse', en: 'Assess & Analyse', bm: 'Penilaian & Analisis',   ns: [5, 6, 7, 11, 16] },
  { key: 'intel',   en: 'Intelligence',     bm: 'Kecerdasan AI',          ns: [9, 10, 13] },
  { key: 'output',  en: 'Output',           bm: 'Keluaran',               ns: [8, 15] },
];

export function FeaturesPage() {
  const { t, lang } = useLang();
  const nav = useNavigate();

  const byN: Record<number, Feat> = Object.fromEntries(FEATURES.map(f => [f.n, f]));

  const renderCard = (f: Feat) => (
    <button
      key={f.n}
      onClick={() => nav(f.to)}
      className="card card-hover"
      style={{
        textAlign: 'left', padding: 20, cursor: 'pointer',
        display: 'flex', flexDirection: 'column', gap: 12,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div style={{
          width: 40, height: 40, borderRadius: 11, flexShrink: 0,
          background: 'var(--info-bg)', color: 'var(--primary-light)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          {f.icon}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span className="mono" style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)' }}>
              #{String(f.n).padStart(2, '0')}
            </span>
            <span style={{
              fontSize: 9.5, fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase',
              background: 'var(--success-bg)', color: 'var(--success)',
              borderRadius: 'var(--radius-pill)', padding: '2px 8px',
            }}>
              {t('Live', 'Aktif')}
            </span>
          </div>
          <div style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 15, color: 'var(--text-primary)', marginTop: 3 }}>
            {lang === 'en' ? f.en : f.bm}
          </div>
        </div>
        <ArrowUpRight size={16} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
      </div>
      <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
        {lang === 'en' ? f.descEn : f.descBm}
      </p>
      <div style={{
        fontSize: 12, color: 'var(--text-muted)', paddingTop: 10,
        borderTop: '1px solid var(--border)', lineHeight: 1.5,
      }}>
        {lang === 'en' ? f.techEn : f.techBm}
      </div>
    </button>
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* Hero */}
      <div style={{
        background: 'var(--gradient-brand)', color: '#fff', border: 'none',
        borderRadius: 'var(--radius-card)', boxShadow: 'var(--shadow-md)',
        padding: '32px 34px',
      }}>
        <div style={{
          fontSize: 11, fontWeight: 700, letterSpacing: '0.14em', textTransform: 'uppercase',
          color: 'var(--accent-soft)', marginBottom: 10,
        }}>
          {t('Platform Capabilities', 'Keupayaan Platform')}
        </div>
        <h1 style={{ fontFamily: 'var(--font-display)', fontSize: 28, fontWeight: 800, marginBottom: 10 }}>
          {t('16 Integrated Capabilities', '16 Keupayaan Bersepadu')}
        </h1>
        <p style={{ fontSize: 14, color: 'rgba(255,255,255,0.72)', maxWidth: 620, lineHeight: 1.7 }}>
          {t('Every capability below is built in and ready to use. Select one to jump straight to it.',
             'Setiap keupayaan di bawah tersedia dan sedia digunakan. Pilih satu untuk terus ke sana.')}
        </p>
      </div>

      {/* Themed sections — one gold keyline header per pipeline stage */}
      {THEMES.map(theme => (
        <section key={theme.key}>
          <div className="kkm-keyline" style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: 14 }}>
            {t(theme.en, theme.bm)}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(290px, 1fr))', gap: 16 }}>
            {theme.ns.map(n => byN[n] && renderCard(byN[n]))}
          </div>
        </section>
      ))}
    </div>
  );
}
