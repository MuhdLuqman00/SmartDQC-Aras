import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  LayoutDashboard, Upload, Table2, ShieldCheck,
  Sparkles, BarChart3, BookOpen, Clock, Settings,
  ClipboardList, ChevronRight, ChevronLeft,
} from 'lucide-react';
import { useLang } from '../context/LanguageContext';
import { useSession } from '../context/SessionContext';

interface NavItem { path: string; en: string; bm: string; icon: React.ReactNode; adminOnly?: boolean; }

interface Group { labelEn: string; labelBm: string; items: NavItem[]; }

const GROUPS: Group[] = [
  {
    labelEn: 'MAIN', labelBm: 'UTAMA',
    items: [{ path: '/', en: 'Dashboard', bm: 'Papan Pemuka', icon: <LayoutDashboard size={17} /> }],
  },
  {
    labelEn: 'NEW SESSION', labelBm: 'SESI BARU',
    items: [{ path: '/upload', en: 'Upload', bm: 'Muat Naik', icon: <Upload size={17} /> }],
  },
  {
    labelEn: 'ANALYSIS', labelBm: 'ANALISIS',
    items: [
      { path: '/explorer', en: 'Explorer',       bm: 'Penjelajah',     icon: <Table2 size={17} /> },
      { path: '/quality',  en: 'Quality Report', bm: 'Laporan Kualiti', icon: <ShieldCheck size={17} /> },
      { path: '/ai',       en: 'AI Assistant',   bm: 'Pembantu AI',    icon: <Sparkles size={17} /> },
    ],
  },
  {
    labelEn: 'OUTPUT', labelBm: 'OUTPUT',
    items: [
      { path: '/reports',  en: 'Reports',   bm: 'Laporan',       icon: <BarChart3 size={17} /> },
      { path: '/datasets', en: 'Library',   bm: 'Perpustakaan',  icon: <BookOpen size={17} /> },
      { path: '/history',  en: 'History',   bm: 'Sejarah',       icon: <Clock size={17} /> },
    ],
  },
  {
    labelEn: 'ADMIN', labelBm: 'ADMIN',
    items: [
      { path: '/settings', en: 'Settings',  bm: 'Tetapan',   icon: <Settings size={17} />,     adminOnly: true },
      { path: '/audit',    en: 'Audit Log', bm: 'Log Audit', icon: <ClipboardList size={17} />, adminOnly: true },
    ],
  },
];

const NO_CACHE_PAGES = ['/upload', '/datasets', '/history', '/settings', '/audit'];

interface Props { role?: string; collapsed: boolean; onToggle: () => void; }

export function Sidebar({ role, collapsed, onToggle }: Props): JSX.Element {
  const location = useLocation();
  const { t, lang } = useLang();
  const { cacheId } = useSession();
  const [hovered, setHovered] = useState<string | null>(null);

  const buildLink = (path: string) => {
    if (!cacheId || NO_CACHE_PAGES.includes(path)) return path;
    return `${path}?cache_id=${cacheId}`;
  };

  const isActive = (path: string) =>
    path === '/' ? location.pathname === '/' : location.pathname.startsWith(path);

  return (
    <aside style={{
      width: collapsed ? 64 : 240,
      background: 'var(--kkm-deep)',
      display: 'flex', flexDirection: 'column',
      transition: 'width 0.25s ease',
      overflow: 'hidden', flexShrink: 0,
      borderRight: '1px solid rgba(255,255,255,0.06)',
    }}>
      {/* Logo */}
      <div style={{
        height: 64, display: 'flex', alignItems: 'center',
        padding: collapsed ? '0 14px' : '0 18px', gap: 10, flexShrink: 0,
        borderBottom: '1px solid rgba(255,255,255,0.08)',
      }}>
        <div style={{
          width: 36, height: 36, borderRadius: 9,
          background: 'var(--kkm-sky)', color: '#fff',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontFamily: "'Plus Jakarta Sans', sans-serif",
          fontWeight: 700, fontSize: 15, flexShrink: 0,
        }}>S</div>
        {!collapsed && (
          <span style={{
            fontFamily: "'Plus Jakarta Sans', sans-serif",
            fontWeight: 700, fontSize: 15, color: '#fff', whiteSpace: 'nowrap',
          }}>
            Smart<span style={{ color: 'var(--kkm-sky)' }}>DQC</span>
          </span>
        )}
      </div>

      {/* Nav */}
      <nav style={{ flex: 1, overflowY: 'auto', padding: '10px 8px' }}>
        {GROUPS.map(group => {
          const visible = group.items.filter(i => !i.adminOnly || role === 'admin');
          if (!visible.length) return null;
          return (
            <div key={group.labelEn} style={{ marginBottom: 4 }}>
              {!collapsed && (
                <div style={{
                  fontSize: 10, fontWeight: 600, letterSpacing: '0.08em',
                  color: 'rgba(255,255,255,0.3)', padding: '8px 10px 4px',
                }}>
                  {lang === 'en' ? group.labelEn : group.labelBm}
                </div>
              )}
              {visible.map(item => {
                const active = isActive(item.path);
                const hov = hovered === item.path;
                return (
                  <Link
                    key={item.path}
                    to={buildLink(item.path)}
                    title={collapsed ? (lang === 'en' ? item.en : item.bm) : undefined}
                    onMouseEnter={() => setHovered(item.path)}
                    onMouseLeave={() => setHovered(null)}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 10,
                      padding: '8px 10px', borderRadius: 8,
                      color: active ? '#fff' : hov ? 'rgba(255,255,255,0.8)' : 'rgba(255,255,255,0.45)',
                      background: active ? 'rgba(0,163,224,0.18)' : hov ? 'rgba(255,255,255,0.05)' : 'transparent',
                      borderLeft: active ? '3px solid var(--kkm-sky)' : '3px solid transparent',
                      fontSize: 13, fontWeight: active ? 500 : 400,
                      transition: 'all var(--transition)', whiteSpace: 'nowrap',
                    }}
                  >
                    <span style={{ flexShrink: 0, display: 'flex', alignItems: 'center' }}>
                      {item.icon}
                    </span>
                    {!collapsed && <span>{lang === 'en' ? item.en : item.bm}</span>}
                  </Link>
                );
              })}
            </div>
          );
        })}
      </nav>

      {/* Toggle */}
      <button
        onClick={onToggle}
        style={{
          background: 'transparent', border: 'none',
          color: 'rgba(255,255,255,0.3)', padding: '12px',
          alignSelf: 'flex-end',
          transition: 'color var(--transition)',
          display: 'flex', alignItems: 'center',
        }}
        onMouseEnter={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.7)')}
        onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.3)')}
      >
        {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
      </button>
    </aside>
  );
}
