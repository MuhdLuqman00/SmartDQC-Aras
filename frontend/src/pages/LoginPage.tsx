import React, { useRef, useState } from 'react';
import { ShieldCheck, User as UserIcon, ArrowRight } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useLang } from '../context/LanguageContext';
import { BRAND } from '../config/brand';

export function LoginPage() {
  // Anonymous named-identity: no password. The user types a name; it is stored
  // and sent as X-User so their dataset library / history is scoped to them and
  // follows them across devices. Access is controlled at the network layer.
  const { identify } = useAuth();
  const { t } = useLang();
  const [name, setName] = useState('');
  const [fieldErr, setFieldErr] = useState<string | undefined>();
  const nameRef = useRef<HTMLInputElement>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setFieldErr(t('Your name is required.', 'Nama anda diperlukan.'));
      nameRef.current?.focus();
      return;
    }
    setFieldErr(undefined);
    identify(name);
    // Full reload (not SPA nav) so all in-memory state — notably SessionContext's
    // cacheId — resets for the new identity. Otherwise a stale cacheId from the
    // previous name would keep driving the dashboard/Explorer after switching.
    window.location.assign('/');
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
        {/* Gold lattice — a subtle brand signature filling the lower panel
            (audit 01). Decorative only: aria-hidden, faded upward,
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
              {t(BRAND.orgNameEn, BRAND.orgNameBm)}
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
            {t('Smart Data Quality', 'Kualiti Data')}<br />
            {t('Check', 'Semakan Pintar')}
          </h1>
          <p style={{ fontSize: 14.5, lineHeight: 1.75, color: 'rgba(255,255,255,0.82)', maxWidth: 440, marginBottom: 28 }}>
            {t('Secure data validation, automated cleaning, and district-level nutrition reporting.',
               'Pengesahan data selamat, pembersihan automatik, dan pelaporan pemakanan peringkat daerah.')}
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
          <span>© {new Date().getFullYear()} {t(BRAND.orgNameEn, BRAND.orgNameBm)}</span>
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
            {t('Welcome', 'Selamat Datang')}
          </h2>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 28 }}>
            {t('Enter your name to continue. Your datasets and history are saved under this name across devices.',
               'Masukkan nama anda untuk teruskan. Set data dan sejarah anda disimpan di bawah nama ini merentas peranti.')}
          </p>

          <form onSubmit={handleSubmit} noValidate style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
            {field(<UserIcon size={15} />, {
              type: 'text', value: name,
              onChange: e => { setName(e.target.value); if (fieldErr) setFieldErr(undefined); },
              placeholder: t('e.g. your name or email', 'cth. nama atau emel anda'), required: true, autoComplete: 'name', autoFocus: true,
            }, t('Your name', 'Nama anda'), { id: 'login-name', error: fieldErr, inputRef: nameRef })}

            <button type="submit" className="btn-primary"
              style={{ marginTop: 4, padding: '13px 16px', fontSize: 14.5, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
              {t('Continue', 'Teruskan')} <ArrowRight size={16} />
            </button>
          </form>

          <div style={{
            marginTop: 26, paddingTop: 18, borderTop: '1px solid var(--border)',
            fontSize: 11, color: 'var(--text-secondary)', textAlign: 'center', letterSpacing: '0.02em',
          }}>
            {t('Access is restricted to the internal network.', 'Akses terhad kepada rangkaian dalaman.')}
          </div>
        </div>
      </div>
    </div>
  );
}
