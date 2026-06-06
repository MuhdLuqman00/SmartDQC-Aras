import React from 'react';
import { ScrollText, Lightbulb, ListChecks } from 'lucide-react';
import { useLang } from '../context/LanguageContext';

export interface NarrativeRecommendation {
  action_en?: string;
  action_bm?: string;
  /** Legacy single-language action — kept for back-compat with cached narratives. */
  action?: string;
  priority?: string;
  bm?: string;
  en?: string;
  reasoning?: string;
}

export interface NarrativeRaw {
  executive_summary?: { bm?: string; en?: string };
  insights_5w1h?: Record<string, { bm?: string; en?: string }>;
  recommendations?: NarrativeRecommendation[];
}

/* Scaffold/placeholder strings a weak model echoes instead of real content.
   Mirrors the backend guard so already-stored cached narratives (which never
   re-run through the backend) also render clean. */
const REC_PLACEHOLDERS = new Set([
  '', '...',
  'short action title in english',
  'tajuk tindakan ringkas dalam bahasa malaysia',
  'detailed recommendation in english',
  'detailed recommendation in bahasa malaysia',
  'cadangan terperinci dalam bahasa malaysia',
  'why this is recommended based on the data',
]);
const isPlaceholder = (v?: string): boolean => REC_PLACEHOLDERS.has((v ?? '').trim().toLowerCase());
const cleanField = (v?: string): string => (isPlaceholder(v) ? '' : (v ?? ''));
/* A rec is junk when its body is placeholder in BOTH languages. */
const isJunkRec = (r: NarrativeRecommendation): boolean =>
  isPlaceholder(r.bm) && isPlaceholder(r.en);

/* Pick the action title in the active language; fall back to the other
   language, then to the legacy single-string `action`. Placeholders skipped. */
function pickAction(r: NarrativeRecommendation, lang: 'en' | 'bm'): string {
  const en = cleanField(r.action_en), bm = cleanField(r.action_bm), legacy = cleanField(r.action);
  return lang === 'en' ? (en || bm || legacy) : (bm || en || legacy);
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
  /* Scrub placeholders before picking so a templated summary/5W1H field — or a
     stale cached narrative built by the old prompt — never renders as content. */
  const pick = (o?: { bm?: string; en?: string }) => {
    const en = cleanField(o?.en), bm = cleanField(o?.bm);
    return (lang === 'en' ? en : bm) || en || bm || '';
  };

  const summary = pick(raw.executive_summary);
  const insights = raw.insights_5w1h || {};
  const visibleRecs = (raw.recommendations || []).filter(r => !isJunkRec(r));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {summary && (
        <div style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 'var(--radius-card)', padding: '14px 16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8, color: 'var(--kkm-sky)', fontWeight: 600, fontSize: 12 }}>
            <ScrollText size={13} /> {t('Executive Summary', 'Ringkasan Eksekutif')}
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

      {visibleRecs.length > 0 && (
        <div style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 'var(--radius-card)', padding: '14px 16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10, color: 'var(--kkm-sky)', fontWeight: 600, fontSize: 12 }}>
            <ListChecks size={13} /> {t('Recommendations', 'Cadangan')}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {visibleRecs.map((r, i) => {
              const body = lang === 'en'
                ? (cleanField(r.en) || cleanField(r.bm))
                : (cleanField(r.bm) || cleanField(r.en));
              const reasoning = cleanField(r.reasoning);
              return (
                <div key={i} style={{ borderLeft: `3px solid ${prioColor(r.priority)}`, paddingLeft: 12 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                    <span style={{ fontWeight: 600, fontSize: 13, color: 'var(--text-primary)' }}>{pickAction(r, lang)}</span>
                    {r.priority && (
                      <span style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', color: prioColor(r.priority) }}>
                        {r.priority}
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: 13, lineHeight: 1.6, color: 'var(--text-primary)' }}>
                    {body}
                  </div>
                  {reasoning && (
                    <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4, fontStyle: 'italic' }}>
                      {reasoning}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
