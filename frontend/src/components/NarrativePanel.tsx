import React from 'react';
import { Sparkles, Lightbulb, ListChecks } from 'lucide-react';
import { useLang } from '../context/LanguageContext';

export interface NarrativeRaw {
  executive_summary?: { bm?: string; en?: string };
  insights_5w1h?: Record<string, { bm?: string; en?: string }>;
  recommendations?: Array<{
    action?: string;
    priority?: string;
    bm?: string;
    en?: string;
    reasoning?: string;
  }>;
}

const W5H1_ORDER = ['who', 'what', 'when', 'where', 'why', 'how'] as const;
const W5H1_LABEL: Record<string, [string, string]> = {
  who:   ['Who', 'Siapa'],   what:  ['What', 'Apa'],
  when:  ['When', 'Bila'],   where: ['Where', 'Di mana'],
  why:   ['Why', 'Mengapa'], how:   ['How', 'Bagaimana'],
};

function prioColor(p?: string): string {
  if (p === 'high')   return 'var(--danger)';
  if (p === 'medium') return 'var(--warning)';
  return 'var(--kkm-teal)';
}

export function NarrativePanel({ raw }: { raw: NarrativeRaw }) {
  const { t, lang } = useLang();
  const pick = (o?: { bm?: string; en?: string }) =>
    (lang === 'en' ? o?.en : o?.bm) || o?.en || o?.bm || '';

  const summary = pick(raw.executive_summary);
  const insights = raw.insights_5w1h || {};
  const recs = raw.recommendations || [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {summary && (
        <div style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 'var(--radius-card)', padding: '14px 16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8, color: 'var(--kkm-sky)', fontWeight: 600, fontSize: 12 }}>
            <Sparkles size={13} /> {t('Executive Summary', 'Ringkasan Eksekutif')}
          </div>
          <div style={{ fontSize: 13, lineHeight: 1.7, color: 'var(--text-primary)' }}>{summary}</div>
        </div>
      )}

      {W5H1_ORDER.some(k => pick(insights[k])) && (
        <div style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 'var(--radius-card)', padding: '14px 16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10, color: 'var(--kkm-sky)', fontWeight: 600, fontSize: 12 }}>
            <Lightbulb size={13} /> {t('Insights (5W1H)', 'Wawasan (5W1H)')}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {W5H1_ORDER.filter(k => pick(insights[k])).map(k => (
              <div key={k} style={{ fontSize: 13, lineHeight: 1.6 }}>
                <span style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>
                  {lang === 'en' ? W5H1_LABEL[k][0] : W5H1_LABEL[k][1]}:
                </span>{' '}
                <span style={{ color: 'var(--text-primary)' }}>{pick(insights[k])}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {recs.length > 0 && (
        <div style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 'var(--radius-card)', padding: '14px 16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10, color: 'var(--kkm-sky)', fontWeight: 600, fontSize: 12 }}>
            <ListChecks size={13} /> {t('Recommendations', 'Cadangan')}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {recs.map((r, i) => (
              <div key={i} style={{ borderLeft: `3px solid ${prioColor(r.priority)}`, paddingLeft: 12 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                  <span style={{ fontWeight: 600, fontSize: 13, color: 'var(--text-primary)' }}>{r.action}</span>
                  {r.priority && (
                    <span style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', color: prioColor(r.priority) }}>
                      {r.priority}
                    </span>
                  )}
                </div>
                <div style={{ fontSize: 13, lineHeight: 1.6, color: 'var(--text-primary)' }}>
                  {(lang === 'en' ? r.en : r.bm) || r.en || r.bm}
                </div>
                {r.reasoning && (
                  <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4, fontStyle: 'italic' }}>
                    {r.reasoning}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
