import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useLang } from '../context/LanguageContext';

export function LoginPage() {
  const { login } = useAuth();
  const { t } = useLang();
  const nav = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(username, password);
      nav('/', { replace: true });
    } catch {
      setError(t('Invalid username or password.', 'Nama pengguna atau kata laluan tidak sah.'));
    } finally {
      setLoading(false);
    }
  };

  const inputStyle: React.CSSProperties = {
    width: '100%', padding: '11px 14px',
    background: 'rgba(255,255,255,0.08)',
    border: '1px solid rgba(255,255,255,0.2)',
    borderRadius: 8, color: '#fff',
    fontSize: 14, outline: 'none',
    transition: 'border-color var(--transition)',
    fontFamily: 'Inter, sans-serif',
  };

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: '#002D62',
      backgroundImage: 'repeating-linear-gradient(135deg, transparent, transparent 40px, rgba(255,255,255,0.015) 40px, rgba(255,255,255,0.015) 80px)',
    }}>
      <div style={{
        width: 420, background: 'rgba(255,255,255,0.06)',
        border: '1px solid rgba(255,255,255,0.12)',
        borderRadius: 16, padding: '40px 36px',
        backdropFilter: 'blur(12px)',
        boxShadow: '0 24px 64px rgba(0,0,0,0.4)',
      }}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div style={{
            width: 52, height: 52, borderRadius: 12,
            background: 'var(--kkm-sky)', color: '#fff',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontFamily: "'Plus Jakarta Sans', sans-serif",
            fontWeight: 700, fontSize: 22, margin: '0 auto 14px',
          }}>S</div>
          <div style={{
            fontFamily: "'Plus Jakarta Sans', sans-serif",
            fontWeight: 700, fontSize: 22, color: '#fff',
          }}>
            Smart<span style={{ color: 'var(--kkm-sky)' }}>DQC</span>
          </div>
          <div style={{ color: 'rgba(255,255,255,0.5)', fontSize: 12, marginTop: 4 }}>
            {t('Paediatric Nutrition Data Quality System', 'Sistem Kualiti Data Pemakanan Pediatrik')}
          </div>
        </div>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'rgba(255,255,255,0.6)', marginBottom: 6, letterSpacing: '0.05em' }}>
              {t('USERNAME', 'NAMA PENGGUNA')}
            </label>
            <input
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              placeholder={t('Enter username', 'Masukkan nama pengguna')}
              required
              style={inputStyle}
              onFocus={e => (e.target.style.borderColor = 'var(--kkm-sky)')}
              onBlur={e => (e.target.style.borderColor = 'rgba(255,255,255,0.2)')}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'rgba(255,255,255,0.6)', marginBottom: 6, letterSpacing: '0.05em' }}>
              {t('PASSWORD', 'KATA LALUAN')}
            </label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              style={inputStyle}
              onFocus={e => (e.target.style.borderColor = 'var(--kkm-sky)')}
              onBlur={e => (e.target.style.borderColor = 'rgba(255,255,255,0.2)')}
            />
          </div>

          {error && (
            <div style={{
              background: 'rgba(192,57,43,0.2)', border: '1px solid rgba(192,57,43,0.4)',
              borderRadius: 8, padding: '10px 14px',
              color: '#ff8b7e', fontSize: 13,
            }}>
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            style={{
              marginTop: 6,
              background: loading ? 'rgba(0,114,188,0.6)' : 'var(--kkm-blue)',
              color: '#fff', border: 'none',
              borderRadius: 8, padding: '12px',
              fontFamily: "'Plus Jakarta Sans', sans-serif",
              fontWeight: 700, fontSize: 15,
              transition: 'opacity var(--transition)',
              cursor: loading ? 'not-allowed' : 'pointer',
            }}
          >
            {loading
              ? t('Logging in…', 'Sedang log masuk…')
              : t('Log In', 'Log Masuk')}
          </button>
        </form>
      </div>
    </div>
  );
}
