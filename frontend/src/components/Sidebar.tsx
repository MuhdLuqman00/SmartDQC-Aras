import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useLang } from '../context/LanguageContext';

interface NavItem { path: string; label: string; icon: string; adminOnly?: boolean; }

interface Props { role?: string; collapsed: boolean; onToggle: () => void; }

export function Sidebar({ role, collapsed, onToggle }: Props): JSX.Element {
  const location = useLocation();
  const { t } = useLang();
  const [hoveredPath, setHoveredPath] = useState<string | null>(null);

  const GROUPS: { label: string; items: NavItem[] }[] = [
    {
      label: t('Main', 'Utama'),
      items: [{ path: '/', label: t('Dashboard', 'Papan Pemuka'), icon: '⊞' }],
    },
    {
      label: t('Data', 'Data'),
      items: [
        { path: '/upload',   label: t('Upload', 'Muat Naik'),     icon: '↑' },
        { path: '/explorer', label: t('Explorer', 'Penjelajah'),  icon: '◫' },
        { path: '/quality',  label: t('Quality', 'Kualiti'),      icon: '◎' },
        { path: '/cleaning', label: t('Cleaning', 'Pembersihan'), icon: '✦' },
      ],
    },
    {
      label: 'AI',
      items: [
        { path: '/ai',  label: t('Smart Analysis', 'Analisis Pintar'), icon: '✧' },
        { path: '/geo', label: t('Geo & Forecast', 'Geo & Ramalan'),   icon: '◈' },
      ],
    },
    {
      label: t('Output', 'Output'),
      items: [
        { path: '/reports',  label: t('Reports', 'Laporan'),      icon: '▤' },
        { path: '/datasets', label: t('Library', 'Perpustakaan'), icon: '⊟' },
        { path: '/history',  label: t('History', 'Sejarah'),      icon: '◷' },
      ],
    },
    {
      label: t('Admin', 'Admin'),
      items: [
        { path: '/settings', label: t('Settings', 'Tetapan'), icon: '⚙', adminOnly: true },
        { path: '/audit',    label: t('Audit', 'Audit'),      icon: '⊕', adminOnly: true },
      ],
    },
  ];

  const isActive = (path: string): boolean =>
    path === '/' ? location.pathname === '/' : location.pathname.startsWith(path);

  return (
    <aside style={{
      width: collapsed ? 64 : 220,
      background: 'var(--navy)',
      display: 'flex', flexDirection: 'column',
      transition: 'width 0.25s ease', overflow: 'hidden', flexShrink: 0,
    }}>
      {/* Logo bar */}
      <div style={{
        height: 64, display: 'flex', alignItems: 'center',
        padding: collapsed ? '0 16px' : '0 20px', gap: 10, flexShrink: 0,
        borderBottom: '0.5px solid rgba(255,255,255,0.08)',
      }}>
        <div style={{
          width: 32, height: 32, borderRadius: 8, background: 'var(--blue)',
          color: '#fff', display: 'flex', alignItems: 'center',
          justifyContent: 'center', fontWeight: 700, fontSize: 14, flexShrink: 0,
        }}>S</div>
        {!collapsed && (
          <span style={{ fontWeight: 700, fontSize: 15, color: '#fff', whiteSpace: 'nowrap' }}>
            Smart<span style={{ color: 'var(--blue-light)' }}>DQC</span>
          </span>
        )}
      </div>

      {/* Nav groups */}
      <nav style={{ flex: 1, overflowY: 'auto', padding: '12px 8px' }}>
        {GROUPS.map(group => {
          const visible = group.items.filter(i => !i.adminOnly || role === 'admin');
          if (!visible.length) return null;
          return (
            <div key={group.label} style={{ marginBottom: 4 }}>
              {!collapsed && (
                <div style={{
                  fontSize: 10, fontWeight: 600, letterSpacing: '0.07em',
                  color: 'rgba(255,255,255,0.3)', textTransform: 'uppercase',
                  padding: '8px 10px 4px',
                }}>
                  {group.label}
                </div>
              )}
              {visible.map(item => {
                const active = isActive(item.path);
                const hov = hoveredPath === item.path;
                return (
                  <Link
                    key={item.path} to={item.path}
                    onMouseEnter={() => setHoveredPath(item.path)}
                    onMouseLeave={() => setHoveredPath(null)}
                    title={collapsed ? item.label : undefined}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 10,
                      padding: '8px 10px', borderRadius: 8,
                      color: active ? '#7EB8FF' : hov ? 'rgba(255,255,255,0.8)' : 'rgba(255,255,255,0.45)',
                      background: active ? 'rgba(29,111,232,0.2)' : hov ? 'rgba(255,255,255,0.05)' : 'transparent',
                      borderLeft: active ? '3px solid var(--blue-light)' : '3px solid transparent',
                      fontSize: 13, fontWeight: active ? 500 : 400,
                      transition: 'all 0.15s ease', whiteSpace: 'nowrap', overflow: 'hidden',
                    }}
                  >
                    <span style={{ fontSize: 15, width: 20, textAlign: 'center', flexShrink: 0 }}>
                      {item.icon}
                    </span>
                    {!collapsed && <span>{item.label}</span>}
                  </Link>
                );
              })}
            </div>
          );
        })}
      </nav>

      {/* Collapse toggle */}
      <button
        onClick={onToggle}
        style={{
          background: 'transparent', border: 'none',
          color: 'rgba(255,255,255,0.3)', fontSize: 18,
          padding: 12, alignSelf: 'flex-end',
          transition: 'color 0.15s ease',
        }}
      >
        {collapsed ? '›' : '‹'}
      </button>
    </aside>
  );
}
