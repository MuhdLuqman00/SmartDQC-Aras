import React, { useState, useRef, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api } from '../api/client';

interface Message { role: 'user' | 'assistant'; text: string; chart_b64?: string | null; }
interface NLQResponse { answer: string; result: unknown; code?: string; chart_b64?: string | null; }
interface NarrativeResponse { insights: string[]; recommendations: string[]; summary: string; }

export function AIPage() {
  const [searchParams] = useSearchParams();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState<string>('');
  const [sessionId, setSessionId] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [narrative, setNarrative] = useState<NarrativeResponse | null>(null);
  const [narrativeLoading, setNarrativeLoading] = useState<boolean>(false);
  const [narrativeOpen, setNarrativeOpen] = useState<boolean>(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const sid = searchParams.get('session_id') ?? '';
    setSessionId(sid);
  }, [searchParams]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendQuery = async (): Promise<void> => {
    const query = input.trim();
    if (!query || !sessionId) return;
    setMessages(m => [...m, { role: 'user', text: query }]);
    setInput('');
    setLoading(true);
    try {
      const res = await api.post<NLQResponse>('/ai/nlq', { query, session_id: sessionId });
      setMessages(m => [...m, { role: 'assistant', text: res.data.answer, chart_b64: res.data.chart_b64 }]);
    } catch {
      setMessages(m => [...m, { role: 'assistant', text: 'Ralat: Tidak dapat memproses pertanyaan.' }]);
    } finally { setLoading(false); }
  };

  const generateNarrative = async (): Promise<void> => {
    setNarrativeLoading(true);
    try {
      const res = await api.post<NarrativeResponse>('/ai/narrative', { eda_result: {}, session_id: sessionId });
      setNarrative(res.data);
      setNarrativeOpen(true);
    } catch { /* silently fail */ }
    finally { setNarrativeLoading(false); }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>

      {/* No session banner */}
      {!sessionId && (
        <div style={{
          margin: '12px 20px',
          padding: '10px 14px',
          background: 'var(--surface-2)',
          border: '0.5px solid var(--border)',
          borderRadius: 8,
          fontSize: 13,
          color: 'var(--text-secondary)',
          flexShrink: 0,
        }}>
          Masukkan session_id dari sesi pembersihan untuk bermula. Tambah <code>?session_id=X</code> ke URL.
        </div>
      )}

      {/* Chat area */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        padding: 20,
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
      }}>
        {messages.map((msg, i) => (
          <div
            key={i}
            style={{
              alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
              maxWidth: '70%',
              padding: '10px 14px',
              borderRadius: msg.role === 'user' ? '12px 0 12px 12px' : '0 12px 12px 12px',
              background: msg.role === 'user' ? 'var(--navy)' : 'var(--surface-2)',
              color: msg.role === 'user' ? '#ffffff' : 'var(--text-primary)',
              fontSize: 14,
              lineHeight: 1.6,
              whiteSpace: 'pre-wrap',
            }}
          >
            {msg.text}
            {msg.chart_b64 && (
              <img
                src={`data:image/png;base64,${msg.chart_b64}`}
                style={{ maxWidth: '100%', borderRadius: 8, marginTop: 8, display: 'block' }}
                alt="Chart"
              />
            )}
          </div>
        ))}

        {/* Loading indicator */}
        {loading && (
          <div style={{
            alignSelf: 'flex-start',
            maxWidth: '70%',
            padding: '10px 14px',
            borderRadius: '0 12px 12px 12px',
            background: 'var(--surface-2)',
            color: 'var(--text-muted)',
            fontSize: 14,
          }}>
            ●●● (sedang memproses)
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Narrative accordion */}
      <div style={{
        flexShrink: 0,
        padding: '0 20px 8px',
        borderTop: '0.5px solid var(--border)',
      }}>
        <button
          onClick={generateNarrative}
          disabled={narrativeLoading}
          style={{
            marginTop: 10,
            padding: '8px 16px',
            background: 'var(--surface)',
            border: '0.5px solid var(--border)',
            borderRadius: 8,
            fontSize: 13,
            color: 'var(--text-primary)',
            cursor: narrativeLoading ? 'not-allowed' : 'pointer',
            opacity: narrativeLoading ? 0.6 : 1,
            transition: 'all 0.15s ease',
          }}
        >
          {narrativeLoading ? 'Jana Naratif...' : 'Jana Naratif'}
        </button>

        {narrativeOpen && narrative && (
          <div style={{
            marginTop: 10,
            padding: '14px 16px',
            background: 'var(--surface)',
            border: '0.5px solid var(--border)',
            borderRadius: 8,
            fontSize: 13,
            color: 'var(--text-primary)',
            lineHeight: 1.6,
          }}>
            <p style={{ margin: '0 0 10px', fontWeight: 600 }}>{narrative.summary}</p>

            {narrative.insights.length > 0 && (
              <>
                <p style={{ margin: '0 0 4px', fontWeight: 600, color: 'var(--text-secondary)' }}>Insights</p>
                <ul style={{ margin: '0 0 10px', paddingLeft: 18 }}>
                  {narrative.insights.map((ins, i) => (
                    <li key={i}>{ins}</li>
                  ))}
                </ul>
              </>
            )}

            {narrative.recommendations.length > 0 && (
              <>
                <p style={{ margin: '0 0 4px', fontWeight: 600, color: 'var(--text-secondary)' }}>Cadangan</p>
                <ul style={{ margin: 0, paddingLeft: 18 }}>
                  {narrative.recommendations.map((rec, i) => (
                    <li key={i}>{rec}</li>
                  ))}
                </ul>
              </>
            )}

            <button
              onClick={() => setNarrativeOpen(false)}
              style={{
                marginTop: 10,
                padding: '4px 10px',
                background: 'transparent',
                border: '0.5px solid var(--border)',
                borderRadius: 6,
                fontSize: 12,
                color: 'var(--text-muted)',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
            >
              Tutup
            </button>
          </div>
        )}
      </div>

      {/* Input bar */}
      <div style={{
        flexShrink: 0,
        borderTop: '0.5px solid var(--border)',
        padding: '12px 20px',
        display: 'flex',
        flexDirection: 'row',
        gap: 10,
        alignItems: 'flex-end',
      }}>
        <textarea
          rows={1}
          placeholder="Taip soalan anda..."
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              sendQuery();
            }
          }}
          style={{
            flex: 1,
            resize: 'none',
            border: '0.5px solid var(--border)',
            borderRadius: 8,
            padding: '10px 12px',
            background: 'var(--surface-2)',
            color: 'var(--text-primary)',
            fontSize: 14,
            outline: 'none',
            fontFamily: 'inherit',
            lineHeight: 1.5,
            transition: 'all 0.15s ease',
          }}
        />
        <button
          onClick={sendQuery}
          disabled={loading || !input.trim()}
          style={{
            padding: '10px 18px',
            background: 'var(--navy)',
            color: '#ffffff',
            border: 'none',
            borderRadius: 8,
            fontSize: 14,
            fontWeight: 600,
            cursor: loading || !input.trim() ? 'not-allowed' : 'pointer',
            opacity: loading || !input.trim() ? 0.5 : 1,
            flexShrink: 0,
            transition: 'all 0.15s ease',
          }}
        >
          Hantar
        </button>
      </div>
    </div>
  );
}
