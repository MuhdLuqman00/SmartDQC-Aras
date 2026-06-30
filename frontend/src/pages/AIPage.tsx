import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Send, ScanSearch, Cpu, Plus, Trash2, MessageSquare } from 'lucide-react';
import { api } from '../api/client';
import { useLang } from '../context/LanguageContext';
import { useSession } from '../context/SessionContext';
import { SessionGuard } from '../components/SessionGuard';
import { RagBadge, scoreToRag } from '../components/RagBadge';
import { NarrativePanel, NarrativeRaw } from '../components/NarrativePanel';
import { formatMytDate } from '../lib/formatMyt';

interface Message {
  id: string;
  role: 'ai' | 'user' | 'narrative';
  content: string;
  data?: unknown;
  reasoning?: string;
  codeUsed?: string;
  raw?: NarrativeRaw;
}

interface ChatSummary {
  id: string;
  title: string;
  message_count: number;
  created_at: string;
  updated_at: string;
}

interface ServerMessage {
  id: number;
  role: 'user' | 'ai' | 'narrative';
  content: string;
  data_json: { data?: unknown; chart_b64?: string; reasoning?: string; code_used?: string; [k: string]: unknown } | null;
  created_at: string;
}

interface ServerChatDetail {
  id: string;
  title: string;
  messages: ServerMessage[];
}

/* Unified AI Assistant page — NLQ chat is the primary interface,
   "Generate AI Insight" drops a narrative card into the same thread,
   and a left rail shows every prior chat for the active dataset so the
   user can switch between, rename, or delete them. */
export function AIPage() {
  const { t, lang } = useLang();
  const { cacheId, filename, sourceType, rowCount, qualityScore, chatId, setChatId } = useSession();

  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [narrativeLoading, setNarrativeLoading] = useState(false);
  const [chats, setChats] = useState<ChatSummary[]>([]);
  const [chatsLoading, setChatsLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  /* ── server → local message shape ── */
  const toLocal = (m: ServerMessage): Message => ({
    id: `srv-${m.id}`,
    role: m.role,
    content: m.content,
    data: m.data_json?.data,
    reasoning: m.data_json?.reasoning,
    codeUsed: m.data_json?.code_used,
    raw: m.role === 'narrative'
      ? ((m.data_json as unknown) as NarrativeRaw)
      : undefined,
  });

  /* ── chat list + active-chat hydration ── */
  const reloadChats = useCallback(async (): Promise<ChatSummary[]> => {
    if (!cacheId) return [];
    setChatsLoading(true);
    try {
      const r = await api.get<ChatSummary[]>(`/chats?dataset_id=${cacheId}`);
      setChats(r.data);
      return r.data;
    } catch {
      setChats([]);
      return [];
    } finally {
      setChatsLoading(false);
    }
  }, [cacheId]);

  const loadChat = useCallback(async (id: string) => {
    try {
      const r = await api.get<ServerChatDetail>(`/chats/${id}`);
      setMessages(r.data.messages.map(toLocal));
      setChatId(id);
    } catch {
      setMessages([]);
    }
  }, [setChatId]);

  // On dataset mount: refresh chat list and hydrate the active chat.
  useEffect(() => {
    if (!cacheId) { setChats([]); setMessages([]); return; }
    let cancelled = false;
    (async () => {
      const list = await reloadChats();
      if (cancelled) return;
      if (!list.length) { setMessages([]); return; }
      // Always hydrate a chat on mount. `chatId` lives in SessionContext
      // (above this route) so it survives an AIPage unmount, but `messages`
      // is local state that resets on remount — so without re-hydrating, a
      // revisit (or a cold reopen the next day) would show the active chat
      // EMPTY even though it's in the list. Prefer the persisted chatId when
      // it's still present; otherwise fall back to the most recent chat.
      const target = (chatId && list.some(c => c.id === chatId)) ? chatId : list[0].id;
      loadChat(target);
    })();
    return () => { cancelled = true; };
    // chatId read at mount only — we re-run on dataset change, not on every
    // chatId update (loadChat/newChat handle in-session switches directly).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cacheId]);

  /* ── helpers ── */
  const addLocalMessage = (msg: Omit<Message, 'id'>) =>
    setMessages(prev => [...prev, { ...msg, id: `${Date.now()}-${Math.random()}` }]);

  // Lazy-create the chat session on the first interaction so opening the
  // page doesn't spam empty chats. Returns the id to use for this turn.
  const ensureChatId = useCallback(async (): Promise<string | null> => {
    if (!cacheId) return null;
    if (chatId) return chatId;
    try {
      const r = await api.post<{ id: string; title: string }>(`/chats?dataset_id=${cacheId}`);
      setChatId(r.data.id);
      // Optimistic insert at the top of the list; reloadChats() races
      // anyway but this avoids the visible flicker.
      setChats(prev => [
        { id: r.data.id, title: r.data.title, message_count: 0, created_at: new Date().toISOString(), updated_at: new Date().toISOString() },
        ...prev,
      ]);
      return r.data.id;
    } catch {
      return null;
    }
  }, [cacheId, chatId, setChatId]);

  const newChat = async () => {
    if (!cacheId) return;
    try {
      const r = await api.post<{ id: string; title: string }>(`/chats?dataset_id=${cacheId}`);
      setChatId(r.data.id);
      setMessages([]);
      await reloadChats();
    } catch { /* swallow — UI stays on previous chat */ }
  };

  const deleteChat = async (id: string) => {
    if (!window.confirm(t('Delete this chat? This cannot be undone.', 'Padam perbualan ini? Tindakan ini tidak boleh dibatalkan.'))) return;
    try {
      await api.delete(`/chats/${id}`);
      const wasActive = id === chatId;
      const list = await reloadChats();
      if (wasActive) {
        if (list.length) {
          loadChat(list[0].id);
        } else {
          setChatId(null);
          setMessages([]);
        }
      }
    } catch { /* swallow */ }
  };

  /* ── narrative + nlq ── */
  const handleNarrative = async () => {
    if (!cacheId) return;
    setNarrativeLoading(true);
    try {
      const activeChat = await ensureChatId();
      const url = activeChat
        ? `/ai/narrative?cache_id=${cacheId}&chat_id=${activeChat}`
        : `/ai/narrative?cache_id=${cacheId}`;
      const r = await api.post<{ narrative: string; raw?: NarrativeRaw }>(url);
      const narrativeText = typeof r.data?.narrative === 'string' && r.data.narrative
        ? r.data.narrative
        : t('No narrative was produced.', 'Tiada naratif dihasilkan.');
      addLocalMessage({ role: 'narrative', content: narrativeText, raw: r.data?.raw });
      // Refresh chat list metadata (updated_at) for sidebar ordering.
      if (activeChat) reloadChats();
    } catch {
      addLocalMessage({ role: 'ai', content: t('Failed to generate narrative.', 'Gagal menjana naratif.') });
    } finally { setNarrativeLoading(false); }
  };

  const handleSend = async () => {
    if (!input.trim() || !cacheId) return;
    const question = input.trim();
    setInput('');
    addLocalMessage({ role: 'user', content: question });
    setLoading(true);
    try {
      const activeChat = await ensureChatId();
      const url = activeChat
        ? `/ai/nlq?cache_id=${cacheId}&chat_id=${activeChat}`
        : `/ai/nlq?cache_id=${cacheId}`;
      const r = await api.post<{ answer: string; data?: unknown; reasoning?: string; code_used?: string }>(url, { question });
      const answerText = typeof r.data?.answer === 'string' && r.data.answer
        ? r.data.answer
        : t('No answer was returned.', 'Tiada jawapan dikembalikan.');
      addLocalMessage({ role: 'ai', content: answerText, data: r.data?.data, reasoning: r.data?.reasoning, codeUsed: r.data?.code_used });
      if (activeChat) reloadChats();
    } catch {
      addLocalMessage({ role: 'ai', content: t('No response. Is Ollama running?', 'Tiada respons. Adakah Ollama berjalan?') });
    } finally { setLoading(false); }
  };

  /* ── render ── */
  const railWidth = 240;

  return (
    <SessionGuard>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16, height: 'calc(100vh - 160px)', minHeight: 520 }}>

        {/* ── Header strip: session info + Generate Insight ── */}
        <div style={{
          background: 'var(--surface)', border: '1px solid var(--border)',
          borderRadius: 'var(--radius-card)', padding: '14px 18px',
          boxShadow: 'var(--shadow-card)',
          display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {filename}
            </div>
            {sourceType && (
              <span style={{ fontSize: 11, background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 999, padding: '2px 8px', color: 'var(--text-secondary)', textTransform: 'uppercase', fontWeight: 600 }}>
                {sourceType}
              </span>
            )}
            {rowCount != null && (
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                {rowCount.toLocaleString()} {t('rows', 'baris')}
              </span>
            )}
            {qualityScore != null && <RagBadge rag={scoreToRag(qualityScore)} lang={lang} />}
          </div>
          <button
            onClick={handleNarrative}
            disabled={narrativeLoading || !cacheId}
            style={{
              background: 'var(--brand-blue)', color: '#fff', border: 'none',
              borderRadius: 'var(--radius-btn)', padding: '9px 16px',
              fontWeight: 600, fontSize: 13, cursor: 'pointer',
              opacity: (narrativeLoading || !cacheId) ? 0.6 : 1,
              display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0,
            }}
          >
            <ScanSearch size={15} />
            {narrativeLoading ? t('Generating…', 'Sedang menjana…') : t('Generate AI Insight', 'Jana Cerapan AI')}
          </button>
        </div>

        {/* ── Body: chat rail + chat panel ── */}
        <div style={{ flex: 1, display: 'flex', gap: 12, minHeight: 0 }}>

          {/* Left rail — chat list */}
          <aside style={{
            width: railWidth, flexShrink: 0,
            background: 'var(--surface)', border: '1px solid var(--border)',
            borderRadius: 'var(--radius-card)', boxShadow: 'var(--shadow-card)',
            display: 'flex', flexDirection: 'column', overflow: 'hidden',
          }}>
            <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--border)' }}>
              <button
                onClick={newChat}
                disabled={!cacheId}
                style={{
                  width: '100%', background: 'var(--surface-2)',
                  border: '1px solid var(--border)', color: 'var(--text-primary)',
                  borderRadius: 'var(--radius-btn)', padding: '8px 12px',
                  fontWeight: 600, fontSize: 13, cursor: cacheId ? 'pointer' : 'not-allowed',
                  opacity: cacheId ? 1 : 0.5,
                  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                }}
              >
                <Plus size={14} /> {t('New chat', 'Perbualan baru')}
              </button>
            </div>
            <div style={{ flex: 1, overflowY: 'auto', padding: '6px 6px' }}>
              {chatsLoading ? (
                <div style={{ padding: 14, fontSize: 12, color: 'var(--text-muted)' }}>{t('Loading…', 'Memuatkan…')}</div>
              ) : chats.length === 0 ? (
                <div style={{ padding: 14, fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.6 }}>
                  {t('No chats yet for this dataset.', 'Tiada perbualan untuk dataset ini lagi.')}
                </div>
              ) : (
                chats.map(c => {
                  const active = c.id === chatId;
                  return (
                    <div
                      key={c.id}
                      onClick={() => !active && loadChat(c.id)}
                      style={{
                        position: 'relative',
                        padding: '8px 10px', margin: '2px 0', borderRadius: 8,
                        background: active ? 'var(--surface-2)' : 'transparent',
                        border: `1px solid ${active ? 'var(--brand-sky)' : 'transparent'}`,
                        cursor: active ? 'default' : 'pointer',
                        transition: 'background var(--transition)',
                      }}
                      onMouseEnter={e => { if (!active) (e.currentTarget.style.background = 'var(--surface-2)'); }}
                      onMouseLeave={e => { if (!active) (e.currentTarget.style.background = 'transparent'); }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, paddingRight: 22 }}>
                        <MessageSquare size={12} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
                        <div style={{
                          fontSize: 12.5, fontWeight: active ? 600 : 500,
                          color: 'var(--text-primary)',
                          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                          flex: 1, minWidth: 0,
                        }}>
                          {c.title}
                        </div>
                      </div>
                      <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 3, marginLeft: 18 }}>
                        {c.message_count} {t('msgs', 'mesej')} · {formatMytDate(c.updated_at, lang)}
                      </div>
                      <button
                        onClick={e => { e.stopPropagation(); deleteChat(c.id); }}
                        aria-label="Delete chat"
                        style={{
                          position: 'absolute', top: 6, right: 6,
                          background: 'none', border: 'none', padding: 4,
                          cursor: 'pointer', color: 'var(--text-muted)',
                          display: 'flex', borderRadius: 4,
                        }}
                        onMouseEnter={e => { e.currentTarget.style.color = 'var(--danger)'; e.currentTarget.style.background = 'var(--danger-bg)'; }}
                        onMouseLeave={e => { e.currentTarget.style.color = 'var(--text-muted)'; e.currentTarget.style.background = 'none'; }}
                      >
                        <Trash2 size={12} />
                      </button>
                    </div>
                  );
                })
              )}
            </div>
          </aside>

          {/* Right: chat panel */}
          <div style={{
            flex: 1, background: 'var(--surface)', border: '1px solid var(--border)',
            borderRadius: 'var(--radius-card)', boxShadow: 'var(--shadow-card)',
            display: 'flex', flexDirection: 'column', overflow: 'hidden',
          }}>
            {/* Thread */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 16 }}>
              {messages.length === 0 && (
                <div style={{ color: 'var(--text-muted)', fontSize: 13, textAlign: 'center', margin: 'auto', maxWidth: 460, lineHeight: 1.6 }}>
                  {t(
                    'Ask a question about your data, or generate an AI insight to begin.',
                    'Tanya soalan tentang data anda, atau jana cerapan AI untuk bermula.'
                  )}
                </div>
              )}
              {messages.map(msg => (
                <div key={msg.id} style={{
                  alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
                  maxWidth: '85%',
                }}>
                  {msg.role === 'user' ? (
                    <div style={{ background: 'var(--brand-blue)', color: '#fff', borderRadius: '12px 12px 2px 12px', padding: '10px 14px', fontSize: 13 }}>
                      {msg.content}
                    </div>
                  ) : msg.role === 'narrative' ? (
                    <div style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: '2px 12px 12px 12px', padding: '14px 16px', fontSize: 13, lineHeight: 1.7 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8, color: 'var(--brand-sky)', fontWeight: 600, fontSize: 12 }}>
                        <ScanSearch size={13} /> {t('AI Insight', 'Cerapan AI')}
                      </div>
                      {msg.raw
                        ? <NarrativePanel raw={msg.raw} />
                        : <div style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</div>}
                    </div>
                  ) : (
                    <div style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: '2px 12px 12px 12px', padding: '10px 14px', fontSize: 13, lineHeight: 1.7 }}>
                      <div style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</div>
                      {msg.reasoning && (
                        <div style={{
                          marginTop: 8, paddingTop: 8, borderTop: '1px dashed var(--border)',
                          fontSize: 12, color: 'var(--text-secondary)', fontStyle: 'italic', lineHeight: 1.6,
                        }}>
                          {t('How this was computed: ', 'Cara ia dikira: ')}{msg.reasoning}
                        </div>
                      )}
                      {msg.codeUsed && (
                        <details style={{ marginTop: 8 }}>
                          <summary style={{ cursor: 'pointer', fontSize: 11, color: 'var(--text-muted)', fontWeight: 600 }}>
                            {t('Technical details', 'Butiran teknikal')}
                          </summary>
                          <pre style={{
                            margin: '6px 0 0', padding: '8px 10px', background: 'var(--surface)',
                            border: '1px solid var(--border)', borderRadius: 6,
                            fontSize: 11.5, lineHeight: 1.5, overflowX: 'auto',
                            fontFamily: 'var(--font-mono, monospace)', color: 'var(--text-secondary)',
                            whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                          }}>
                            {msg.codeUsed}
                          </pre>
                        </details>
                      )}
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

            {/* Input + Ollama footer line */}
            <div style={{ padding: '14px 20px 10px', borderTop: '1px solid var(--border)', display: 'flex', flexDirection: 'column', gap: 6 }}>
              <div style={{ display: 'flex', gap: 10 }}>
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
                  disabled={!input.trim() || loading || !cacheId}
                  style={{
                    background: 'var(--brand-blue)', color: '#fff', border: 'none',
                    borderRadius: 8, padding: '10px 16px', cursor: 'pointer',
                    opacity: !input.trim() || loading || !cacheId ? 0.5 : 1,
                    display: 'flex', alignItems: 'center',
                  }}
                >
                  <Send size={16} />
                </button>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: 'var(--text-muted)' }}>
                <Cpu size={11} />
                Ollama · Local inference
              </div>
            </div>
          </div>
        </div>
      </div>
      <style>{`@keyframes pulse { 0%,100%{opacity:0.3;transform:scale(0.8)} 50%{opacity:1;transform:scale(1)} }`}</style>
    </SessionGuard>
  );
}
