import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  CheckCircle2, ArrowRight, Download, FileSpreadsheet,
  Table2, Sparkles, ArrowDownUp,
} from 'lucide-react';
import { useLang } from '../context/LanguageContext';
import { useSession } from '../context/SessionContext';
import { SessionGuard } from '../components/SessionGuard';
import { RagBadge, scoreToRag } from '../components/RagBadge';

const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) || 'http://localhost:8000';

interface Issue { description: string; severity: 'critical' | 'warning' | 'info'; count: number; }

export function CleaningPage() {
  const { t } = useLang();
  const { cacheId, filename, cleanStats, qualityScore } = useSession();
  const nav = useNavigate();

  const stats = cleanStats as Record<string, unknown> | null;
  const before = Number(stats?.rows_before) || 0;
  const after  = Number(stats?.rows_after) || 0;
  const score  = Number(stats?.quality_score ?? qualityScore) || 0;
  const removed = Math.max(0, before - after);
  const removedPct = before > 0 ? (removed / before) * 100 : 0;
  const rules: string[] = Array.isArray(stats?.rules_applied) ? (stats!.rules_applied as string[]) : [];
  const issues: Issue[] = Array.isArray(stats?.top_issues) ? (stats!.top_issues as Issue[]) : [];

  const card: React.CSSProperties = {
    background: 'var(--surface)', border: '1px solid var(--border)',
    borderRadius: 'var(--radius-card)', boxShadow: 'var(--shadow-card)',
  };
  const sectionHead: React.CSSProperties = {
    fontSize: 11, fontWeight: 700, letterSpacing: '0.08em',
    textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: 14,
  };

  const downloads = [
    { icon: <Download size={15} />,        label: 'CSV',  href: `${BASE}/clean/download-cached/${cacheId}?format=csv` },
    { icon: <FileSpreadsheet size={15} />,  label: 'XLSX', href: `${BASE}/clean/download-cached/${cacheId}?format=xlsx` },
    { icon: <Table2 size={15} />,           label: t('Quality Report', 'Laporan Kualiti'), href: `${BASE}/clean/download-report/${cacheId}` },
  ];

  if (!stats) {
    return (
      <SessionGuard>
        <div style={{ ...card, padding: 36, textAlign: 'center' }}>
          <Sparkles size={40} style={{ color: 'var(--text-muted)', marginBottom: 14 }} />
          <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 8 }}>
            {t('Cleaning summary not in this session', 'Ringkasan pembersihan tiada dalam sesi ini')}
          </h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: 14, maxWidth: 500, margin: '0 auto 20px', lineHeight: 1.6 }}>
            {t('The live cleaning summary is only retained within the active upload wizard. For a reopened dataset, download the archived Quality Report, or re-run the wizard to regenerate it here.',
               'Ringkasan pembersihan langsung hanya disimpan dalam wizard muat naik aktif. Untuk dataset yang dibuka semula, muat turun Laporan Kualiti arkib, atau jalankan semula wizard untuk menjananya di sini.')}
          </p>
          <div style={{ display: 'flex', gap: 10, justifyContent: 'center', flexWrap: 'wrap' }}>
            {cacheId && (
              <a href={`${BASE}/clean/download-report/${cacheId}`} target="_blank" rel="noreferrer"
                style={{
                  background: 'var(--surface-2)', border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-btn)', padding: '11px 20px', fontSize: 14,
                  fontWeight: 600, color: 'var(--text-primary)',
                }}>
                {t('Download Quality Report', 'Muat Turun Laporan Kualiti')}
              </a>
            )}
            <button onClick={() => nav('/upload')} className="btn-primary" style={{ padding: '11px 22px', fontSize: 14 }}>
              {t('Go to Upload', 'Ke Muat Naik')}
            </button>
          </div>
        </div>
      </SessionGuard>
    );
  }

  return (
    <SessionGuard>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

        {/* Hero summary */}
        <div style={{ ...card, padding: 28, background: 'var(--gradient-brand)', color: '#fff', border: 'none' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 18 }}>
            <CheckCircle2 size={26} style={{ color: 'var(--accent-soft)' }} />
            <div>
              <div style={{ fontFamily: "'Plus Jakarta Sans', sans-serif", fontWeight: 800, fontSize: 20 }}>
                {t('Cleaning Complete', 'Pembersihan Selesai')}
              </div>
              <div style={{ fontSize: 13, color: 'rgba(255,255,255,0.7)', marginTop: 2 }}>{filename}</div>
            </div>
            <div style={{ flex: 1 }} />
            <RagBadge rag={scoreToRag(score)} />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 18 }}>
            {[
              { label: t('Rows Before', 'Baris Sebelum'), value: before.toLocaleString() },
              { label: t('Rows After', 'Baris Selepas'),  value: after.toLocaleString() },
              { label: t('Rows Removed', 'Baris Dibuang'), value: `${removed.toLocaleString()} (${removedPct.toFixed(1)}%)` },
              { label: t('Quality Score', 'Skor Kualiti'), value: `${score.toFixed(1)}%` },
            ].map(s => (
              <div key={s.label}>
                <div style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'rgba(255,255,255,0.55)', marginBottom: 6 }}>
                  {s.label}
                </div>
                <div className="mono" style={{ fontSize: 24, fontWeight: 700 }}>{s.value}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Before / After bar */}
        <div style={{ ...card, padding: 24 }}>
          <div style={sectionHead}><ArrowDownUp size={12} style={{ display: 'inline', marginRight: 6 }} />{t('Row Retention', 'Pengekalan Baris')}</div>
          <div style={{ height: 14, background: 'var(--surface-2)', borderRadius: 7, overflow: 'hidden', display: 'flex' }}>
            <div style={{ width: `${before > 0 ? (after / before) * 100 : 0}%`, background: 'var(--gradient-brand)', transition: 'width var(--transition-lg)' }} />
            <div style={{ flex: 1, background: 'var(--danger-bg)' }} />
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8, fontSize: 12, color: 'var(--text-secondary)' }}>
            <span>{t('Retained', 'Dikekalkan')}: <strong className="mono">{after.toLocaleString()}</strong></span>
            <span>{t('Removed', 'Dibuang')}: <strong className="mono" style={{ color: 'var(--danger)' }}>{removed.toLocaleString()}</strong></span>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
          {/* Rules applied */}
          <div style={{ ...card, padding: 24 }}>
            <div style={sectionHead}>{t('Cleaning Rules Applied', 'Peraturan Pembersihan')}</div>
            {rules.length === 0 ? (
              <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>{t('No rules recorded.', 'Tiada peraturan direkodkan.')}</div>
            ) : (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {rules.map(r => (
                  <span key={r} style={{
                    fontSize: 12, background: 'var(--info-bg)', border: '1px solid var(--primary-light)',
                    borderRadius: 'var(--radius-pill)', padding: '5px 12px', color: 'var(--primary-light)', fontWeight: 600,
                  }}>
                    {r}
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Top issues fixed */}
          <div style={{ ...card, padding: 24 }}>
            <div style={sectionHead}>{t('Top Issues Addressed', 'Isu Utama Ditangani')}</div>
            {issues.length === 0 ? (
              <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>{t('No issues recorded.', 'Tiada isu direkodkan.')}</div>
            ) : issues.slice(0, 6).map((iss, i) => (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: 10, padding: '9px 0',
                borderBottom: i < Math.min(6, issues.length) - 1 ? '1px solid var(--border)' : 'none',
              }}>
                <span style={{
                  width: 7, height: 7, borderRadius: '50%', flexShrink: 0,
                  background: iss.severity === 'critical' ? 'var(--danger)' : iss.severity === 'warning' ? 'var(--warning)' : 'var(--info)',
                }} />
                <span style={{ flex: 1, fontSize: 13, color: 'var(--text-primary)' }}>{iss.description}</span>
                <span className="mono" style={{ fontSize: 12, color: 'var(--text-muted)' }}>{Number(iss.count).toLocaleString()}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Downloads + next */}
        <div style={{ ...card, padding: 24, display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', marginRight: 4 }}>
            {t('Download cleaned output', 'Muat turun output bersih')}:
          </div>
          {downloads.map(d => (
            <a key={d.label} href={d.href} target="_blank" rel="noreferrer"
              style={{
                display: 'flex', alignItems: 'center', gap: 7,
                background: 'var(--surface-2)', border: '1px solid var(--border)',
                borderRadius: 'var(--radius-btn)', padding: '9px 16px',
                fontSize: 13, fontWeight: 600, color: 'var(--text-primary)',
                transition: 'all var(--transition)',
              }}
              onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--primary-light)'; }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)'; }}
            >
              {d.icon} {d.label}
            </a>
          ))}
          <div style={{ flex: 1 }} />
          <button onClick={() => nav('/quality')} className="btn-primary"
            style={{ padding: '10px 20px', fontSize: 14, display: 'flex', alignItems: 'center', gap: 7 }}>
            {t('View Quality Report', 'Lihat Laporan Kualiti')} <ArrowRight size={16} />
          </button>
        </div>
      </div>
    </SessionGuard>
  );
}
