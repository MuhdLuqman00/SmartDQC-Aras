import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTheme } from '../context/ThemeContext';
import { useLang } from '../context/LanguageContext';

interface Props { title: string; subtitle: string; onLogout: () => void; }

export function TopNav({ title, subtitle, onLogout }: Props): JSX.Element {
  const { darkMode, toggleDarkMode } = useTheme();
  const { lang, setLang } = useLang();
  const navigate = useNavigate();
  const [logoutHovered, setLogoutHovered] = useState<boolean>(false);

  const iconBtn: React.CSSProperties = {
    width: 36, height: 36, borderRadius: 8,
    border: '0.5px solid var(--border)',
    background: 'var(--surface)', color: 'var(--text-secondary)',
    fontSize: 16, display: 'flex', alignItems: 'center',
    justifyContent: 'center', transition: 'all 0.15s ease',
  };

  return (
    <header style={{
      height: 64, background: 'var(--surface)',
      borderBottom: '0.5px solid var(--border)',
      display: 'flex', alignItems: 'center',
      justifyContent: 'space-between', padding: '0 28px',
      flexShrink: 0,
    }}>
      <div>
        <div style={{ fontSize: 16, fontWeight: 500, color: 'var(--text-primary)' }}>
          {title}
        </div>
        {subtitle && (
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 1 }}>
            {subtitle}
          </div>
        )}
      </div>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        <button
          style={{
            ...iconBtn,
            width: 'auto',
            padding: '0 10px',
            fontSize: 12,
            fontWeight: 700,
            letterSpacing: '0.04em',
          }}
          onClick={() => setLang(lang === 'EN' ? 'MY' : 'EN')}
          title="Toggle language"
        >
          {lang === 'EN' ? 'MY' : 'EN'}
        </button>
        <button style={iconBtn} onClick={toggleDarkMode} title="Toggle dark mode">
          {darkMode ? '☀' : '◑'}
        </button>
        <button
          onMouseEnter={() => setLogoutHovered(true)}
          onMouseLeave={() => setLogoutHovered(false)}
          style={{
            ...iconBtn,
            color: logoutHovered ? 'var(--danger)' : 'var(--text-secondary)',
            borderColor: logoutHovered ? 'var(--danger)' : 'var(--border)',
          }}
          onClick={() => { onLogout(); navigate('/login'); }}
          title="Log out"
        >
          ⎋
        </button>
      </div>
    </header>
  );
}
