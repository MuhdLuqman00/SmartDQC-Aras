import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

export function LoginPage(): JSX.Element {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [username, setUsername] = useState<string>('');
  const [password, setPassword] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent): Promise<void> => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await login(username, password);
      navigate('/');
    } catch {
      setError('Nama pengguna atau kata laluan tidak sah.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', height: '100vh', background: 'var(--bg)' }}>
      {/* Navy left panel */}
      <div style={{
        width: 420, background: 'var(--navy)',
        display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center', gap: 16, padding: 48,
      }}>
        <div style={{
          width: 64, height: 64, borderRadius: 16, background: 'var(--blue)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 28, fontWeight: 700, color: '#fff',
        }}>S</div>
        <div style={{ fontSize: 26, fontWeight: 700, color: '#fff', letterSpacing: '-0.01em' }}>
          Smart<span style={{ color: 'var(--blue-light)' }}>DQC</span>
        </div>
        <div style={{ fontSize: 13, color: 'rgba(255,255,255,0.45)', textAlign: 'center', lineHeight: 1.7 }}>
          Sistem Kualiti Data<br />Kementerian Kesihatan Malaysia
        </div>
      </div>

      {/* Right form panel */}
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{
          width: 420, background: 'var(--surface)',
          borderRadius: 12, border: '0.5px solid var(--border)', padding: 40,
        }}>
          <h2 style={{ fontSize: 20, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 8 }}>
            Log Masuk
          </h2>
          <p style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 28 }}>
            Masukkan kelayakan anda untuk meneruskan.
          </p>

          {error && (
            <div style={{
              background: 'var(--danger-bg)', color: 'var(--danger)',
              border: '0.5px solid var(--danger)', borderRadius: 8,
              padding: '10px 14px', fontSize: 13, marginBottom: 20,
            }}>
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <label style={s.fieldWrap}>
              <span style={s.label}>Nama Pengguna</span>
              <input
                type="text" value={username} required
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setUsername(e.target.value)}
                placeholder="admin" style={s.input}
              />
            </label>
            <label style={s.fieldWrap}>
              <span style={s.label}>Kata Laluan</span>
              <input
                type="password" value={password} required
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setPassword(e.target.value)}
                placeholder="••••••••" style={s.input}
              />
            </label>
            <button
              type="submit" disabled={loading}
              style={{
                background: 'var(--navy)', color: '#fff', border: 'none',
                borderRadius: 8, padding: '12px 0', fontSize: 14, fontWeight: 600,
                marginTop: 8, opacity: loading ? 0.7 : 1, transition: 'all 0.15s ease',
              }}
            >
              {loading ? 'Memproses...' : 'Masuk'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

const s: Record<string, React.CSSProperties> = {
  fieldWrap: { display: 'flex', flexDirection: 'column', gap: 6 },
  label:     { fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', letterSpacing: '0.02em' },
  input:     { padding: '10px 12px', border: '0.5px solid var(--border)', borderRadius: 8, background: 'var(--surface-2)', color: 'var(--text-primary)', fontSize: 14, outline: 'none', transition: 'border-color 0.15s ease', width: '100%' },
};
