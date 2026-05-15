import React, { useState, useRef, useEffect } from 'react';
import { Send, Sparkles, Cpu } from 'lucide-react';
import { api } from '../api/client';
import { useLang } from '../context/LanguageContext';
import { useSession } from '../context/SessionContext';
import { SessionGuard } from '../components/SessionGuard';
import { RagBadge, scoreToRag } from '../components/RagBadge';

interface Message {
  id: string;
  role: 'ai' | 'user' | 'narrative';
  content: string;
  data?: unknown;
}

export function AIPage() {
  const { t, lang } = useLang();
  const { cacheId, filename, sourceType, rowCount, qualityScore } = useSession();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [narrativeLoading, setNarrativeLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  const addMessage = (msg: Omit<Message, 'id'>) =>
    setMessages(prev => [...prev, { ...msg, id: `${Date.now()}-${Math.random()}` }]);

  const handleNarrative = async () => {
    if (!cacheId) return;
    setNarrativeLoading(true);
    try {
      const r = await api.post<{ narrative: string }>(`/ai/narrative?cache_id=${cacheId}`);
      addMessage({ role: 'narrative', content: r.data.narrative || String(r.data) });
    } catch { addMessage({ role: 'ai', content: t('Failed to generate narrative.', 'Gagal menjana naratif.') }); }
    finally { setNarrativeLoading(false); }
  };

  const handleSend = async () => {
    if (!input.trim() || !cacheId) return;
    const question = input.trim();
    setInput('');
    addMessage({ role: 'user', content: question });
    setLoading(true);
    try {
      const r = await api.post<{ answer: string; data?: unknown }>(`/ai/nlq?cache_id=${cacheId}`, { question });
      addMessage({ role: 'ai', content: r.data.answer || String(r.data), data: r.data.data });
    } catch { addMessage({ role: 'ai', content: t('No response. Is Ollama running?', 'Tiada respons. Adakah Ollama berjalan?') }); }
    finally { setLoading(false); }
  };

  return (
    <SessionGuard>
      <div style={{ display: 'flex', gap: 20, height: 'calc(100vh - 160px)', minHeight: 500 }}>

        {/* Left panel */}
        <div style={{
          flex: '0 0 300px', display: 'flex', flexDirection: 'column', gap: 16,
        }}>
          {/* Session card */}
          <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-card)', padding: '18px 20px', boxShadow: 'var(--shadow-card)' }}>
            <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.07em', textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: 12 }}>
              {t('Active Session', 'Sesi Aktif')}
            </div>
            <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 6, wordBreak: 'break-all' }}>{filename}</div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {sourceType && (
                <span style={{ fontSize: 11, background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 999, padding: '2px 8px', color: 'var(--text-secondary)', textTransform: 'uppercase', fontWeight: 600 }}>
                  {sourceType}
                </span>
              )}
              {rowCount && (
                <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                  {rowCount.toLocaleString()} {t('rows', 'baris')}
                </span>
              )}
              {qualityScore != null && <RagBadge rag={scoreToRag(qualityScore)} lang={lang} />}
            </div>
          </div>

          {/* Narrative button */}
          <button
            onClick={handleNarrative}
            disabled={narrativeLoading}
            style={{
              background: 'var(--kkm-blue)', color: '#fff', border: 'none',
              borderRadius: 'var(--radius-btn)', padding: '12px 16px',
              fontWeight: 600, fontSize: 14, cursor: 'pointer',
              opacity: narrativeLoading ? 0.6 : 1,
              display: 'flex', alignItems: 'center', gap: 8,
            }}
          >
            <Sparkles size={16} />
            {narrativeLoading ? t('Generating…', 'Sedang menjana…') : t('Generate AI Narrative', 'Jana Naratif AI')}
          </button>

          {/* Model info */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--text-muted)', padding: '8px 0' }}>
            <Cpu size={13} />
            Ollama · Local inference
          </div>
        </div>

        {/* Chat panel */}
        <div style={{
          flex: 1, background: 'var(--surface)', border: '1px solid var(--border)',
          borderRadius: 'var(--radius-card)', boxShadow: 'var(--shadow-card)',
          display: 'flex', flexDirection: 'column', overflow: 'hidden',
        }}>
          {/* Thread */}
          <div style={{ flex: 1, overflowY: 'auto', padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 16 }}>
            {messages.length === 0 && (
              <div style={{ color: 'var(--text-muted)', fontSize: 13, textAlign: 'center', margin: 'auto' }}>
                {t('Ask a question about your data or generate a narrative.', 'Tanya soalan tentang data anda atau jana naratif.')}
              </div>
            )}
            {messages.map(msg => (
              <div key={msg.id} style={{
                alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
                maxWidth: '85%',
              }}>
                {msg.role === 'user' ? (
                  <div style={{ background: 'var(--kkm-blue)', color: '#fff', borderRadius: '12px 12px 2px 12px', padding: '10px 14px', fontSize: 13 }}>
                    {msg.content}
                  </div>
                ) : msg.role === 'narrative' ? (
                  <div style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: '2px 12px 12px 12px', padding: '14px 16px', fontSize: 13, lineHeight: 1.7, whiteSpace: 'pre-wrap' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8, color: 'var(--kkm-sky)', fontWeight: 600, fontSize: 12 }}>
                      <Sparkles size={13} /> {t('AI Narrative', 'Naratif AI')}
                    </div>
                    {msg.content}
                  </div>
                ) : (
                  <div style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: '2px 12px 12px 12px', padding: '10px 14px', fontSize: 13, lineHeight: 1.7, whiteSpace: 'pre-wrap' }}>
                    {msg.content}
                  </div>
                )}
              </div>
            ))}
            {loading && (
              <div style={{ alignSelf: 'flex-start', display: 'flex', gap: 4, padding: '10px 14px', background: 'var(--surface-2)', borderRadius: '2px 12px 12px 12px', border: '1px solid var(--border)' }}>
                {[0,1,2].map(i => (
                  <div key={i} style={{ width: 7, height: 7, borderRadius: '50%', background: 'var(--text-muted)', animation: `pulse 1.2s ease-in-out ${i * 0.2}s infinite` }} />
                ))}
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div style={{ padding: '14px 20px', borderTop: '1px solid var(--border)', display: 'flex', gap: 10 }}>
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && !e.shiftKey && handleSend()}
              placeholder={t('Ask about your data…', 'Tanya tentang data anda…')}
              style={{
                flex: 1, padding: '10px 14px',
                background: 'var(--surface-2)', border: '1px solid var(--border)',
                borderRadius: 8, fontSize: 14, color: 'var(--text-primary)', outline: 'none',
              }}
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || loading}
              style={{
                background: 'var(--kkm-blue)', color: '#fff', border: 'none',
                borderRadius: 8, padding: '10px 16px', cursor: 'pointer',
                opacity: !input.trim() || loading ? 0.5 : 1,
                display: 'flex', alignItems: 'center',
              }}
            >
              <Send size={16} />
            </button>
          </div>
        </div>
      </div>
      <style>{`@keyframes pulse { 0%,100%{opacity:0.3;transform:scale(0.8)} 50%{opacity:1;transform:scale(1)} }`}</style>
    </SessionGuard>
  );
}
