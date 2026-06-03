import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Sun, Moon, LogOut, FileText, ChevronRight } from 'lucide-react';
import { useTheme } from '../context/ThemeContext';
import { useLang } from '../context/LanguageContext';
import { useAuth } from '../context/AuthContext';
import { useSession } from '../context/SessionContext';

const PAGE_TITLES: Record<string, { en: string; bm: string }> = {
  '/':         { en: 'Dashboard',       bm: 'Papan Pemuka'    },
  '/features': { en: 'Capabilities',    bm: 'Keupayaan'       },
  '/upload':   { en: 'Upload & Map',    bm: 'Muat Naik'       },
  '/explorer': { en: 'Data Explorer',   bm: 'Penjelajah'      },
  '/quality':  { en: 'Quality Report',  bm: 'Laporan Kualiti' },
  '/cleaning': { en: 'Cleaning',        bm: 'Pembersihan'     },
  '/geo':      { en: 'Geo & Risk',      bm: 'Geo & Risiko'    },
  '/ai':       { en: 'AI Assistant',    bm: 'Pembantu AI'     },
  '/reports':  { en: 'Reports',         bm: 'Laporan'         },
  '/datasets': { en: 'Dataset Library', bm: 'Perpustakaan'    },
  '/linkage':  { en: 'Linkage',         bm: 'Pemautan'        },
  '/history':  { en: 'History',         bm: 'Sejarah'         },
  '/settings': { en: 'Settings',        bm: 'Tetapan'         },
  '/audit':    { en: 'Audit Log',       bm: 'Log Audit'       },
};

export function TopBar() {
  const { theme, toggleTheme } = useTheme();
  const { lang, setLang, t } = useLang();
  const { user, logout } = useAuth();
  const { filename } = useSession();
  const location = useLocation();
  const nav = useNavigate();

  const page = PAGE_TITLES[location.pathname] || { en: 'SmartDQC', bm: 'SmartDQC' };

  const iconBtn: React.CSSProperties = {
    background: 'var(--surface-2)', border: '1px solid var(--border)',
    borderRadius: 9, padding: 8, color: 'var(--text-secondary)',
    display: 'flex', alignItems: 'center',
    transition: 'transform var(--transition), color var(--transition), border-color var(--transition), background var(--transition)',
  };

  return (
    <header className="glass" style={{
      height: 64, borderBottom: '1px solid var(--border)',
      display: 'flex', alignItems: 'center', padding: '0 28px', gap: 14,
      flexShrink: 0, position: 'sticky', top: 0, zIndex: 'var(--z-sticky)' as React.CSSProperties['zIndex'],
    }}>
      {/* Breadcrumb */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
        <span style={{ fontSize: 12, color: 'var(--text-muted)', fontWeight: 600 }}>SmartDQC</span>
        <ChevronRight size={13} style={{ color: 'var(--text-muted)' }} />
        {/* Signature: gold "letterhead" keyline under the page title — the
           one distinctive detail carried across all 14 routes. */}
        <h1 className="kkm-keyline" style={{
          fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 16,
          color: 'var(--text-primary)', whiteSpace: 'nowrap',
        }}>
          {lang === 'en' ? page.en : page.bm}
        </h1>
      </div>

      <div style={{ flex: 1 }} />

      {/* Session chip */}
      <button
        onClick={() => nav('/history')}
        title={t('Go to history', 'Ke sejarah')}
        style={{
          display: 'flex', alignItems: 'center', gap: 7,
          background: filename ? 'var(--info-bg)' : 'transparent',
          border: `1px solid ${filename ? 'var(--primary-light)' : 'var(--border)'}`,
          borderRadius: 'var(--radius-pill)', padding: '6px 14px',
          color: filename ? 'var(--primary-light)' : 'var(--text-muted)',
          fontSize: 12, fontWeight: 600, maxWidth: 220,
          transition: 'all var(--transition)',
        }}
      >
        <FileText size={13} style={{ flexShrink: 0 }} />
        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {filename || t('No active session', 'Tiada sesi aktif')}
        </span>
      </button>

      {/* Language segmented control */}
      <div style={{
        display: 'flex', border: '1px solid var(--border)',
        borderRadius: 8, overflow: 'hidden', background: 'var(--surface-2)',
      }}>
        {(['en', 'bm'] as const).map(code => {
          const active = lang === code;
          return (
            <button
              key={code}
              onClick={() => setLang(code)}
              aria-pressed={active}
              style={{
                background: active ? 'var(--gradient-brand)' : 'transparent',
                border: 'none', padding: '6px 13px',
                color: active ? '#fff' : 'var(--text-secondary)',
                fontSize: 11.5, fontWeight: 700, letterSpacing: '0.04em',
                transition: 'all var(--transition)',
              }}
            >
              {code.toUpperCase()}
            </button>
          );
        })}
      </div>

      {/* Theme toggle */}
      <button
        onClick={toggleTheme}
        title={theme === 'dark' ? t('Light mode', 'Mod terang') : t('Dark mode', 'Mod gelap')}
        aria-label={theme === 'dark' ? t('Switch to light mode', 'Tukar ke mod terang') : t('Switch to dark mode', 'Tukar ke mod gelap')}
        style={iconBtn}
        onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--primary-light)'; e.currentTarget.style.color = 'var(--primary-light)'; e.currentTarget.style.transform = 'scale(1.08)'; }}
        onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.color = 'var(--text-secondary)'; e.currentTarget.style.transform = 'scale(1)'; }}
      >
        {theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />}
      </button>

      {/* User chip */}
      {user && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 9,
          background: 'var(--surface-2)', border: '1px solid var(--border)',
          borderRadius: 'var(--radius-pill)', padding: '4px 12px 4px 5px',
        }}>
          <div style={{
            width: 27, height: 27, borderRadius: '50%',
            background: 'var(--gradient-brand)', color: '#fff',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 11, fontWeight: 700,
          }}>
            {user.username.charAt(0).toUpperCase()}
          </div>
          <span style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--text-primary)' }}>
            {user.username}
          </span>
          <span style={{
            fontSize: 9.5, fontWeight: 700, letterSpacing: '0.05em',
            background: 'var(--gradient-gold)', color: '#0F1B2F',
            borderRadius: 'var(--radius-pill)', padding: '2px 8px', textTransform: 'uppercase',
          }}>
            {user.role}
          </span>
        </div>
      )}

      {/* Logout */}
      <button
        onClick={logout}
        title={t('Logout', 'Log Keluar')}
        aria-label={t('Logout', 'Log Keluar')}
        style={iconBtn}
        onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--danger)'; e.currentTarget.style.color = 'var(--danger)'; e.currentTarget.style.transform = 'scale(1.08)'; }}
        onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.color = 'var(--text-secondary)'; e.currentTarget.style.transform = 'scale(1)'; }}
      >
        <LogOut size={15} />
      </button>
    </header>
  );
}
