import React, { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ShieldCheck, Lock, User as UserIcon, ArrowRight } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useLang } from '../context/LanguageContext';

export function LoginPage() {
  const { login } = useAuth();
  const { t } = useLang();
  const nav = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [fieldErr, setFieldErr] = useState<{ username?: string; password?: string }>({});
  const [loading, setLoading] = useState(false);
  const userRef = useRef<HTMLInputElement>(null);
  const passRef = useRef<HTMLInputElement>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    /* Field-level validation first: empty fields get an inline message and
       focus moves to the first offender (rather than relying on the native
       required-bubble, which the form suppresses via noValidate). */
    const errs: { username?: string; password?: string } = {};
    if (!username.trim()) errs.username = t('Username is required.', 'Nama pengguna diperlukan.');
    if (!password) errs.password = t('Password is required.', 'Kata laluan diperlukan.');
    if (errs.username || errs.password) {
      setFieldErr(errs);
      (errs.username ? userRef : passRef).current?.focus();
      return;
    }
    setFieldErr({}); setError(''); setLoading(true);
    try {
      await login(username, password);
      nav('/', { replace: true });
    } catch {
      setError(t('Invalid username or password.', 'Nama pengguna atau kata laluan tidak sah.'));
      userRef.current?.focus();
    } finally { setLoading(false); }
  };

  const field = (
    icon: React.ReactNode,
    props: React.InputHTMLAttributes<HTMLInputElement>,
    label: string,
    opts: { id: string; error?: string; inputRef?: React.RefObject<HTMLInputElement> },
  ) => {
    const errId = `${opts.id}-error`;
    return (
      <div>
        <label htmlFor={opts.id} style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 7 }}>
          {label}
        </label>
        <div style={{ position: 'relative' }}>
          <span style={{ position: 'absolute', left: 13, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)', display: 'flex' }}>
            {icon}
          </span>
          <input
            {...props}
            id={opts.id}
            ref={opts.inputRef}
            aria-invalid={!!opts.error}
            aria-describedby={opts.error ? errId : undefined}
            style={{
              width: '100%', padding: '12px 14px 12px 40px',
              background: 'var(--surface-2)',
              border: `1px solid ${opts.error ? 'var(--danger)' : 'var(--border)'}`,
              borderRadius: 'var(--radius-btn)', color: 'var(--text-primary)',
              fontSize: 14, outline: 'none', transition: 'border-color var(--transition), box-shadow var(--transition)',
            }}
            onFocus={e => { e.target.style.borderColor = 'var(--primary-light)'; e.target.style.boxShadow = 'var(--glow-accent)'; }}
            onBlur={e => { e.target.style.borderColor = opts.error ? 'var(--danger)' : 'var(--border)'; e.target.style.boxShadow = 'none'; }}
          />
        </div>
        {opts.error && (
          <div id={errId} style={{ fontSize: 12, fontWeight: 600, color: 'var(--danger)', marginTop: 6 }}>
            {opts.error}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="login-layout" style={{ minHeight: '100vh', display: 'flex', background: 'var(--bg)' }}>

      {/* Brand panel */}
      <div className="login-brand-panel" style={{
        flex: '0 0 46%', background: 'var(--gradient-brand)', color: '#fff',
        padding: '52px 60px', display: 'flex', flexDirection: 'column',
        justifyContent: 'space-between', position: 'relative', overflow: 'hidden',
      }}>
        <div style={{
          position: 'absolute', top: -120, right: -120, width: 380, height: 380,
          borderRadius: '50%', background: 'radial-gradient(circle, rgba(200,150,46,0.18), transparent 70%)',
        }} />
        {/* Songket-inspired gold lattice — a subtle KKM signature filling the
            lower panel (audit 01). Decorative only: aria-hidden, faded upward,
            non-interactive; a crosshatch echo of the gold keyline motif. */}
        <div aria-hidden style={{
          position: 'absolute', left: 0, right: 0, bottom: 0, height: '44%',
          backgroundImage: 'repeating-linear-gradient(135deg, rgba(200,150,46,0.07) 0 1.5px, transparent 1.5px 15px), repeating-linear-gradient(45deg, rgba(200,150,46,0.07) 0 1.5px, transparent 1.5px 15px)',
          maskImage: 'linear-gradient(to top, #000, transparent)',
          WebkitMaskImage: 'linear-gradient(to top, #000, transparent)',
          pointerEvents: 'none',
        }} />
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, position: 'relative' }}>
          <div style={{
            width: 46, height: 46, borderRadius: 13, background: 'var(--gradient-gold)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontFamily: 'var(--font-body)', fontWeight: 800, fontSize: 20, color: '#0F1B2F',
            boxShadow: '0 8px 22px rgba(200,150,46,0.4)',
          }}>S</div>
          <div>
            <div style={{ fontSize: 10, letterSpacing: '0.15em', textTransform: 'uppercase', color: 'rgba(255,255,255,0.8)', marginBottom: 3 }}>
              {t('Ministry of Health Malaysia', 'Kementerian Kesihatan Malaysia')}
            </div>
            <div style={{ fontFamily: 'var(--font-body)', fontWeight: 800, fontSize: 16 }}>
              Smart<span style={{ color: 'var(--accent-soft)' }}>DQC</span>
            </div>
          </div>
        </div>

        <div style={{ position: 'relative' }}>
          <h1 style={{
            fontFamily: 'var(--font-body)', fontWeight: 800, fontSize: 36,
            lineHeight: 1.2, marginBottom: 20,
          }}>
            {t('Data Quality &', 'Kualiti Data &')}<br />
            {t('Clinical Analytics', 'Analitik Klinikal')}
          </h1>
          <p style={{ fontSize: 14.5, lineHeight: 1.75, color: 'rgba(255,255,255,0.82)', maxWidth: 440, marginBottom: 28 }}>
            {t('Secure data validation, automated cleaning, and district-level nutrition reporting for the Ministry of Health Malaysia.',
               'Pengesahan data selamat, pembersihan automatik, dan pelaporan pemakanan peringkat daerah untuk Kementerian Kesihatan Malaysia.')}
          </p>
          <div style={{ display: 'flex', gap: 22, flexWrap: 'wrap' }}>
            {[
              { v: '16', l: t('Capabilities', 'Keupayaan') },
              { v: '46+', l: t('API Endpoints', 'Titik Akhir') },
              { v: 'BM·EN', l: t('Bilingual', 'Dwibahasa') },
            ].map(s => (
              <div key={s.l}>
                <div style={{ fontFamily: 'var(--font-body)', fontWeight: 800, fontSize: 22, color: 'var(--accent-soft)' }}>{s.v}</div>
                <div style={{ fontSize: 11.5, color: 'rgba(255,255,255,0.78)' }}>{s.l}</div>
              </div>
            ))}
          </div>
        </div>

        <div style={{
          fontSize: 11, color: 'rgba(255,255,255,0.65)', position: 'relative',
          borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: 20,
          display: 'flex', justifyContent: 'space-between',
        }}>
          <span>© {new Date().getFullYear()} Kementerian Kesihatan Malaysia</span>
          <span>v3.0</span>
        </div>
      </div>

      {/* Form panel */}
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 40 }}>
        <div className="card" style={{ width: '100%', maxWidth: 400, padding: '40px 38px', animation: 'fadeUp 0.5s ease both' }}>
          <div style={{
            width: 44, height: 44, borderRadius: 12, background: 'var(--info-bg)',
            color: 'var(--primary-light)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 20,
          }}>
            <ShieldCheck size={22} />
          </div>
          <h2 style={{ fontFamily: 'var(--font-body)', fontWeight: 800, fontSize: 24, color: 'var(--text-primary)', marginBottom: 6 }}>
            {t('Sign In', 'Log Masuk')}
          </h2>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 28 }}>
            {t('Enter your credentials to access the system.', 'Masukkan maklumat akaun anda untuk akses sistem.')}
          </p>

          <form onSubmit={handleSubmit} noValidate style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
            {field(<UserIcon size={15} />, {
              type: 'text', value: username,
              onChange: e => { setUsername(e.target.value); if (fieldErr.username) setFieldErr(f => ({ ...f, username: undefined })); },
              placeholder: t('Enter username', 'Masukkan nama pengguna'), required: true, autoComplete: 'username',
            }, t('Username', 'Nama Pengguna'), { id: 'login-username', error: fieldErr.username, inputRef: userRef })}

            {field(<Lock size={15} />, {
              type: 'password', value: password,
              onChange: e => { setPassword(e.target.value); if (fieldErr.password) setFieldErr(f => ({ ...f, password: undefined })); },
              placeholder: '••••••••', required: true, autoComplete: 'current-password',
            }, t('Password', 'Kata Laluan'), { id: 'login-password', error: fieldErr.password, inputRef: passRef })}

            {error && (
              <div role="alert" style={{
                background: 'var(--danger-bg)', border: '1px solid var(--danger)',
                borderRadius: 'var(--radius-btn)', padding: '10px 14px', color: 'var(--danger)', fontSize: 13,
              }}>
                {error}
              </div>
            )}

            <button type="submit" disabled={loading} className="btn-primary"
              style={{ marginTop: 4, padding: '13px 16px', fontSize: 14.5, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
              {loading ? t('Signing in…', 'Sedang log masuk…') : <>{t('Sign In', 'Log Masuk')} <ArrowRight size={16} /></>}
            </button>
          </form>

          <div style={{
            marginTop: 26, paddingTop: 18, borderTop: '1px solid var(--border)',
            /* --text-secondary (not --text-muted): muted-grey on the white card
               fails 4.5:1. Local fix only; the token-wide question is WS7. */
            fontSize: 11, color: 'var(--text-secondary)', textAlign: 'center', letterSpacing: '0.02em',
          }}>
            {t('Authorised users only.', 'Pengguna yang sah sahaja.')}
          </div>
        </div>
      </div>
    </div>
  );
}
