import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { LineChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { api } from '../api/client';
import { theme } from '../theme';

interface Session {
  cache_id: string;
  filename: string;
  source_type: string;
  row_count: number;
  quality_score: number;
}

interface SparkPoint { i: number; q: number; }

// ── KPI Card ────────────────────────────────────────────────────────────────
interface KpiCardProps {
  title: string;
  value: string | number;
  icon: string;
  borderColor: string;
}

function KpiCard({ title, value, icon, borderColor }: KpiCardProps) {
  return (
    <div style={{
      background: 'var(--surface)',
      border: '0.5px solid var(--border)',
      borderLeft: `3px solid ${borderColor}`,
      borderRadius: 12,
      padding: '16px 20px',
      display: 'flex',
      flexDirection: 'column',
      gap: 6,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{
          fontSize: 10,
          fontWeight: 600,
          textTransform: 'uppercase' as const,
          letterSpacing: '0.07em',
          color: 'var(--text-secondary)',
        }}>
          {title}
        </div>
        <div style={{ fontSize: 18, opacity: 0.7 }}>{icon}</div>
      </div>
      <div style={{ fontSize: 24, fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>
        {value}
      </div>
    </div>
  );
}

// ── Quality badge ────────────────────────────────────────────────────────────
function QBadge({ score }: { score: number }) {
  const bg   = score >= 80 ? 'var(--success-bg)'  : score >= 60 ? 'var(--warning-bg)'  : 'var(--danger-bg)';
  const text = score >= 80 ? 'var(--success)'     : score >= 60 ? 'var(--warning)'     : 'var(--danger)';
  return (
    <span style={{
      background: bg,
      color: text,
      borderRadius: 4,
      padding: '2px 8px',
      fontSize: 11,
      fontWeight: 600,
    }}>
      {score.toFixed(1)}%
    </span>
  );
}

// ── Main page ────────────────────────────────────────────────────────────────
export function DashboardPage() {
  const navigate = useNavigate();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState(false);

  useEffect(() => {
    setLoading(true);
    api.get<Session[]>('/sessions')
      .then(r => { setSessions(r.data); setLoading(false); })
      .catch(() => { setError(true); setLoading(false); });
  }, []);

  // ── derived ──────────────────────────────────────────────────────────────
  const avgQ: number = sessions.length
    ? sessions.reduce((a, s) => a + s.quality_score, 0) / sessions.length
    : 0;
  const totalRows: number = sessions.reduce((a, s) => a + s.row_count, 0);
  const alertCount: number = sessions.filter(s => s.quality_score < 60).length;
  const sparkData: SparkPoint[] = sessions.slice(-10).map((s, i) => ({ i, q: s.quality_score }));

  // ── states ───────────────────────────────────────────────────────────────
  if (loading) {
    return <div style={st.center}>Memuatkan...</div>;
  }
  if (error) {
    return <div style={st.center}>Gagal memuatkan sesi.</div>;
  }

  return (
    <div>
      <h1 style={st.h1}>Papan Pemuka</h1>

      {/* ── KPI row ── */}
      <div style={st.kpiGrid}>
        <KpiCard title="Sesi Aktif"     value={sessions.length}             icon="📁" borderColor={theme.blue} />
        <KpiCard title="Purata Kualiti" value={`${avgQ.toFixed(1)}%`}       icon="📊" borderColor={theme.success} />
        <KpiCard title="Jumlah Baris"   value={totalRows.toLocaleString()}  icon="🗄️" borderColor={theme.purple} />
        <KpiCard title="Amaran (<60)"   value={alertCount}                  icon="⚠️" borderColor={theme.danger} />
      </div>

      {/* ── Sparkline ── */}
      <div style={st.card}>
        <div style={st.cardTitle}>Trend Kualiti (10 Sesi Terkini)</div>
        <ResponsiveContainer width="100%" height={120}>
          <LineChart data={sparkData}>
            <XAxis dataKey="i" hide />
            <YAxis domain={[0, 100]} hide />
            <Tooltip formatter={(v: number) => [`${v.toFixed(1)}%`, 'Kualiti']} />
            <Line
              type="monotone"
              dataKey="q"
              stroke={theme.blue}
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* ── Sessions table ── */}
      <div style={{ ...st.card, marginBottom: 20 }}>
        <div style={st.cardTitle}>Sesi Terkini</div>
        {sessions.length === 0 ? (
          <div style={st.empty}>Tiada sesi lagi.</div>
        ) : (
          <table style={st.table}>
            <thead>
              <tr>
                {(['Fail', 'Jenis', 'Baris', 'Skor', 'Tindakan'] as const).map(h => (
                  <th key={h} style={st.th}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sessions.slice(0, 8).map(sess => (
                <tr key={sess.cache_id} style={st.tr}>
                  <td style={st.td}>{sess.filename}</td>
                  <td style={st.td}>
                    <span style={st.srcBadge}>{sess.source_type}</span>
                  </td>
                  <td style={st.td}>{sess.row_count.toLocaleString()}</td>
                  <td style={st.td}><QBadge score={sess.quality_score} /></td>
                  <td style={st.td}>
                    <button
                      style={st.openBtn}
                      onClick={() => navigate(`/quality?cache_id=${sess.cache_id}`)}
                      onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.background = 'var(--surface-2)'; }}
                      onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.background = 'transparent'; }}
                    >
                      Buka
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* ── Quick actions ── */}
      <div style={st.actionGrid}>
        {([
          { label: 'Muat Naik Baru', path: '/upload' },
          { label: 'Jana Laporan',   path: '/reports' },
          { label: 'Tanya AI',       path: '/ai' },
        ] as { label: string; path: string }[]).map(a => (
          <button
            key={a.path}
            style={st.actionBtn}
            onClick={() => navigate(a.path)}
            onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.background = 'var(--surface-2)'; }}
            onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.background = 'var(--surface)'; }}
          >
            {a.label}
          </button>
        ))}
      </div>
    </div>
  );
}

// ── Styles ───────────────────────────────────────────────────────────────────
const st: Record<string, React.CSSProperties> = {
  center: {
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    height: 200, color: 'var(--text-secondary)', fontSize: 14,
  },
  h1: { margin: '0 0 20px', fontSize: 22, fontWeight: 700, color: 'var(--text-primary)' },
  kpiGrid: {
    display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 20,
  },
  card: {
    background: 'var(--surface)',
    border: '0.5px solid var(--border)',
    borderRadius: 12,
    padding: 20,
    marginBottom: 20,
  },
  cardTitle: {
    fontSize: 11, fontWeight: 600, textTransform: 'uppercase' as const,
    letterSpacing: '0.07em', color: 'var(--text-secondary)', marginBottom: 16,
  },
  table:  { width: '100%', borderCollapse: 'collapse' as const, fontSize: 13 },
  th: {
    textAlign: 'left' as const, padding: '6px 8px',
    fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)',
    textTransform: 'uppercase' as const, letterSpacing: '0.05em',
    borderBottom: '0.5px solid var(--border)',
  },
  tr: { borderBottom: '0.5px solid var(--border)' },
  td: { padding: '8px', color: 'var(--text-primary)', verticalAlign: 'middle' as const },
  srcBadge: {
    background: 'var(--surface)',
    border: '0.5px solid var(--border)',
    borderRadius: 4, padding: '2px 6px', fontSize: 11,
    color: 'var(--text-secondary)',
  },
  openBtn: {
    background: 'transparent',
    border: '0.5px solid var(--border)',
    borderRadius: 4, padding: '4px 12px', fontSize: 12,
    cursor: 'pointer', color: 'var(--text-primary)', fontWeight: 500,
    transition: 'all 0.15s ease',
  },
  empty: {
    color: 'var(--text-secondary)', fontSize: 13,
    padding: '20px 0', textAlign: 'center' as const,
  },
  actionGrid: { display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 },
  actionBtn: {
    background: 'var(--surface)',
    border: '0.5px solid var(--border)',
    borderRadius: 8, padding: 16,
    fontSize: 14, fontWeight: 500,
    cursor: 'pointer', color: 'var(--text-primary)',
    transition: 'all 0.15s ease',
  },
};
