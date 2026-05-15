import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Sun, Moon, LogOut, FileText } from 'lucide-react';
import { useTheme } from '../context/ThemeContext';
import { useLang } from '../context/LanguageContext';
import { useAuth } from '../context/AuthContext';
import { useSession } from '../context/SessionContext';

const PAGE_TITLES: Record<string, { en: string; bm: string }> = {
  '/':         { en: 'Dashboard',     bm: 'Papan Pemuka'    },
  '/upload':   { en: 'Upload',        bm: 'Muat Naik'       },
  '/explorer': { en: 'Explorer',      bm: 'Penjelajah'      },
  '/quality':  { en: 'Quality Report',bm: 'Laporan Kualiti' },
  '/ai':       { en: 'AI Assistant',  bm: 'Pembantu AI'     },
  '/reports':  { en: 'Reports',       bm: 'Laporan'         },
  '/datasets': { en: 'Library',       bm: 'Perpustakaan'    },
  '/history':  { en: 'History',       bm: 'Sejarah'         },
  '/settings': { en: 'Settings',      bm: 'Tetapan'         },
  '/audit':    { en: 'Audit Log',     bm: 'Log Audit'       },
};

export function TopBar() {
  const { theme, toggleTheme } = useTheme();
  const { lang, toggleLang, t } = useLang();
  const { user, logout } = useAuth();
  const { filename } = useSession();
  const location = useLocation();
  const nav = useNavigate();

  const pageTitles = PAGE_TITLES[location.pathname] || { en: 'SmartDQC', bm: 'SmartDQC' };

  return (
    <div style={{
      height: 64, background: 'var(--surface)',
      borderBottom: '1px solid var(--border)',
      display: 'flex', alignItems: 'center',
      padding: '0 28px', gap: 16, flexShrink: 0,
    }}>
      {/* Page title */}
      <h1 style={{
        fontFamily: "'Plus Jakarta Sans', sans-serif",
        fontWeight: 600, fontSize: 16,
        color: 'var(--text-primary)', whiteSpace: 'nowrap',
      }}>
        {lang === 'en' ? pageTitles.en : pageTitles.bm}
      </h1>

      {/* Spacer */}
      <div style={{ flex: 1 }} />

      {/* Session chip */}
      <button
        onClick={() => nav('/history')}
        style={{
          display: 'flex', alignItems: 'center', gap: 6,
          background: filename ? 'rgba(0,163,224,0.10)' : 'transparent',
          border: `1px solid ${filename ? 'var(--kkm-sky)' : 'var(--border)'}`,
          borderRadius: 999, padding: '4px 12px',
          color: filename ? 'var(--kkm-sky)' : 'var(--text-muted)',
          fontSize: 12, fontWeight: 500, cursor: 'pointer',
          transition: 'all var(--transition)', whiteSpace: 'nowrap',
        }}
      >
        <FileText size={13} />
        {filename || t('No active session', 'Tiada sesi aktif')}
      </button>

      {/* Lang toggle */}
      <button
        onClick={toggleLang}
        style={{
          background: 'transparent', border: '1px solid var(--border)',
          borderRadius: 6, padding: '5px 10px',
          color: 'var(--text-secondary)', fontSize: 12, fontWeight: 600,
          transition: 'all var(--transition)',
        }}
        onMouseEnter={e => (e.currentTarget.style.borderColor = 'var(--kkm-sky)')}
        onMouseLeave={e => (e.currentTarget.style.borderColor = 'var(--border)')}
      >
        {lang === 'en' ? 'BM' : 'EN'}
      </button>

      {/* Theme toggle */}
      <button
        onClick={toggleTheme}
        style={{
          background: 'transparent', border: '1px solid var(--border)',
          borderRadius: 6, padding: '6px', color: 'var(--text-secondary)',
          display: 'flex', alignItems: 'center', transition: 'all var(--transition)',
        }}
        onMouseEnter={e => (e.currentTarget.style.borderColor = 'var(--kkm-sky)')}
        onMouseLeave={e => (e.currentTarget.style.borderColor = 'var(--border)')}
      >
        {theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />}
      </button>

      {/* User chip */}
      {user && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8,
          background: 'var(--surface-2)', border: '1px solid var(--border)',
          borderRadius: 999, padding: '4px 12px 4px 8px',
        }}>
          <div style={{
            width: 24, height: 24, borderRadius: '50%',
            background: 'var(--kkm-blue)', color: '#fff',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 10, fontWeight: 700,
          }}>
            {user.username.charAt(0).toUpperCase()}
          </div>
          <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-primary)' }}>
            {user.username}
          </span>
          <span style={{
            fontSize: 10, fontWeight: 600,
            background: 'var(--kkm-teal)', color: '#fff',
            borderRadius: 999, padding: '1px 6px',
          }}>
            {user.role}
          </span>
        </div>
      )}

      {/* Logout */}
      <button
        onClick={logout}
        title={t('Logout', 'Log Keluar')}
        style={{
          background: 'transparent', border: '1px solid var(--border)',
          borderRadius: 6, padding: '6px', color: 'var(--text-secondary)',
          display: 'flex', alignItems: 'center', transition: 'all var(--transition)',
        }}
        onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--danger)'; e.currentTarget.style.color = 'var(--danger)'; }}
        onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.color = 'var(--text-secondary)'; }}
      >
        <LogOut size={15} />
      </button>
    </div>
  );
}
