import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Clock } from 'lucide-react';
import { api } from '../api/client';
import { useLang } from '../context/LanguageContext';
import { useSession } from '../context/SessionContext';
import { RagBadge, scoreToRag } from '../components/RagBadge';
import { EmptyState } from '../components/EmptyState';

interface Session {
  cache_id: string; filename: string; source_type: string | null;
  row_count: number; quality_score: number; created_at: string | null;
}

function groupByMonth(sessions: Session[]): Record<string, Session[]> {
  const groups: Record<string, Session[]> = {};
  for (const s of sessions) {
    const key = s.created_at
      ? new Date(s.created_at).toLocaleDateString('default', { year: 'numeric', month: 'long' })
      : 'Unknown';
    (groups[key] ||= []).push(s);
  }
  return groups;
}

export function HistoryPage() {
  const { t, lang } = useLang();
  const { setSession } = useSession();
  const nav = useNavigate();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get<Session[]>('/sessions').then(r => setSessions(r.data)).finally(() => setLoading(false));
  }, []);

  if (loading) return <div style={{ color: 'var(--text-muted)', padding: 40 }}>{t('Loading…', 'Memuatkan…')}</div>;
  if (!sessions.length) return (
    <EmptyState icon={<Clock size={48} />} title={t('No history yet', 'Tiada sejarah lagi')}
      description={t('Completed sessions will appear here.', 'Sesi yang selesai akan muncul di sini.')}
      action={{ label: t('Upload Dataset', 'Muat Naik Dataset'), to: '/upload' }} />
  );

  const groups = groupByMonth(sessions);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 28 }}>
      {Object.entries(groups).map(([month, group]) => (
        <div key={month}>
          <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.08em', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 12 }}>
            {month}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
            {group.map((s, i) => (
              <div key={s.cache_id} style={{
                background: 'var(--surface)', border: '1px solid var(--border)',
                borderRadius: i === 0 ? '10px 10px 0 0' : i === group.length - 1 ? '0 0 10px 10px' : 0,
                padding: '14px 20px',
                display: 'flex', alignItems: 'center', gap: 16,
              }}>
                <Clock size={16} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--text-primary)' }}>{s.filename}</div>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
                    {s.source_type && <span style={{ textTransform: 'uppercase', fontWeight: 600, marginRight: 8 }}>{s.source_type}</span>}
                    {s.row_count.toLocaleString()} {t('rows', 'baris')}
                    {s.created_at && <> · {new Date(s.created_at).toLocaleString()}</>}
                  </div>
                </div>
                <RagBadge rag={scoreToRag(s.quality_score)} lang={lang} />
                <button
                  onClick={() => {
                    setSession({ cacheId: s.cache_id, filename: s.filename, sourceType: s.source_type, rowCount: s.row_count, qualityScore: s.quality_score });
                    nav('/');
                  }}
                  style={{ background: 'var(--kkm-blue)', color: '#fff', border: 'none', borderRadius: 6, padding: '6px 14px', fontSize: 12, fontWeight: 600, cursor: 'pointer', whiteSpace: 'nowrap' }}
                >
                  {t('Reopen', 'Buka Semula')}
                </button>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
