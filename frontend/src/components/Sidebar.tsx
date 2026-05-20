import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  LayoutDashboard, Upload, Table2, ShieldCheck, Sparkles, BarChart3,
  BookOpen, Clock, Settings, ClipboardList, ChevronRight, ChevronLeft,
  MapPin, Brush, LayoutGrid,
} from 'lucide-react';
import { useLang } from '../context/LanguageContext';
import { useSession } from '../context/SessionContext';

interface NavItem { path: string; en: string; bm: string; icon: React.ReactNode; adminOnly?: boolean; }
interface Group { labelEn: string; labelBm: string; items: NavItem[]; }

const GROUPS: Group[] = [
  {
    labelEn: 'OVERVIEW', labelBm: 'GAMBARAN',
    items: [
      { path: '/',         en: 'Dashboard',    bm: 'Papan Pemuka', icon: <LayoutDashboard size={18} /> },
      { path: '/features', en: 'Capabilities', bm: 'Keupayaan',    icon: <LayoutGrid size={18} /> },
    ],
  },
  {
    labelEn: 'NEW SESSION', labelBm: 'SESI BARU',
    items: [{ path: '/upload', en: 'Upload & Map', bm: 'Muat Naik', icon: <Upload size={18} /> }],
  },
  {
    labelEn: 'ANALYSIS', labelBm: 'ANALISIS',
    items: [
      { path: '/explorer', en: 'Data Explorer',  bm: 'Penjelajah',     icon: <Table2 size={18} /> },
      { path: '/quality',  en: 'Quality Report', bm: 'Laporan Kualiti', icon: <ShieldCheck size={18} /> },
      { path: '/cleaning', en: 'Cleaning',       bm: 'Pembersihan',    icon: <Brush size={18} /> },
      { path: '/geo',      en: 'Geo & Risk',     bm: 'Geo & Risiko',   icon: <MapPin size={18} /> },
    ],
  },
  {
    labelEn: 'INTELLIGENCE', labelBm: 'KECERDASAN',
    items: [
      // AI narrative + NLQ are now one unified page; the /chatbot route
      // still resolves (redirects to /ai) so old bookmarks keep working.
      { path: '/ai', en: 'AI Assistant', bm: 'Pembantu AI', icon: <Sparkles size={18} /> },
    ],
  },
  {
    labelEn: 'OUTPUT', labelBm: 'OUTPUT',
    items: [
      { path: '/reports',  en: 'Reports', bm: 'Laporan',      icon: <BarChart3 size={18} /> },
      { path: '/datasets', en: 'Library', bm: 'Perpustakaan', icon: <BookOpen size={18} /> },
      { path: '/history',  en: 'History', bm: 'Sejarah',      icon: <Clock size={18} /> },
    ],
  },
  {
    labelEn: 'ADMINISTRATION', labelBm: 'PENTADBIRAN',
    items: [
      { path: '/settings', en: 'Settings',  bm: 'Tetapan',   icon: <Settings size={18} />,     adminOnly: true },
      { path: '/audit',    en: 'Audit Log', bm: 'Log Audit', icon: <ClipboardList size={18} />, adminOnly: true },
    ],
  },
];

const NO_CACHE_PAGES = ['/upload', '/datasets', '/history', '/settings', '/audit', '/features'];

interface Props { role?: string; collapsed: boolean; onToggle: () => void; }

export function Sidebar({ role, collapsed, onToggle }: Props): JSX.Element {
  const location = useLocation();
  const { lang } = useLang();
  const { cacheId } = useSession();
  const [hovered, setHovered] = useState<string | null>(null);

  const buildLink = (path: string) =>
    (!cacheId || NO_CACHE_PAGES.includes(path)) ? path : `${path}?cache_id=${cacheId}`;

  const isActive = (path: string) =>
    path === '/' ? location.pathname === '/' : location.pathname.startsWith(path);

  return (
    <aside style={{
      width: collapsed ? 72 : 248,
      background: 'var(--gradient-navy)',
      display: 'flex', flexDirection: 'column',
      transition: 'width var(--transition-lg)',
      overflow: 'hidden', flexShrink: 0,
      borderRight: '1px solid rgba(255,255,255,0.06)',
      position: 'relative',
    }}>
      {/* Brand */}
      <div style={{
        height: 68, display: 'flex', alignItems: 'center',
        padding: collapsed ? '0 18px' : '0 20px', gap: 12, flexShrink: 0,
        borderBottom: '1px solid rgba(255,255,255,0.07)',
      }}>
        <div style={{
          width: 38, height: 38, borderRadius: 11, flexShrink: 0,
          background: 'var(--gradient-gold)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontFamily: "'Plus Jakarta Sans', sans-serif",
          fontWeight: 800, fontSize: 16, color: '#0F1B2F',
          boxShadow: '0 4px 14px rgba(200,150,46,0.35)',
        }}>S</div>
        {!collapsed && (
          <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.15 }}>
            <span style={{
              fontFamily: "'Plus Jakarta Sans', sans-serif",
              fontWeight: 800, fontSize: 16, color: '#fff', whiteSpace: 'nowrap',
            }}>
              Smart<span style={{ color: 'var(--accent-soft)' }}>DQC</span>
            </span>
            <span style={{
              fontSize: 9.5, letterSpacing: '0.16em', textTransform: 'uppercase',
              color: 'rgba(255,255,255,0.42)', fontWeight: 600,
            }}>
              KKM · Data Quality
            </span>
          </div>
        )}
      </div>

      {/* Nav */}
      <nav style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden', padding: '14px 10px' }}>
        {GROUPS.map(group => {
          const visible = group.items.filter(i => !i.adminOnly || role === 'admin');
          if (!visible.length) return null;
          return (
            <div key={group.labelEn} style={{ marginBottom: 14 }}>
              {!collapsed && (
                <div style={{
                  fontSize: 9.5, fontWeight: 700, letterSpacing: '0.13em',
                  color: 'rgba(255,255,255,0.32)', padding: '4px 12px 8px',
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
                      position: 'relative',
                      display: 'flex', alignItems: 'center', gap: 12,
                      padding: collapsed ? '11px 14px' : '10px 14px',
                      borderRadius: 10, marginBottom: 2,
                      color: active ? '#fff' : hov ? 'rgba(255,255,255,0.92)' : 'rgba(255,255,255,0.55)',
                      background: active
                        ? 'linear-gradient(100deg, rgba(46,74,122,0.55), rgba(46,74,122,0.18))'
                        : hov ? 'rgba(255,255,255,0.06)' : 'transparent',
                      fontSize: 13.5, fontWeight: active ? 600 : 500,
                      transition: 'all var(--transition)', whiteSpace: 'nowrap',
                    }}
                  >
                    {active && (
                      <span style={{
                        position: 'absolute', left: 0, top: '50%', transform: 'translateY(-50%)',
                        width: 3, height: 22, borderRadius: 3,
                        background: 'var(--gradient-gold)',
                        boxShadow: '0 0 10px rgba(200,150,46,0.6)',
                      }} />
                    )}
                    <span style={{ flexShrink: 0, display: 'flex', alignItems: 'center' }}>{item.icon}</span>
                    {!collapsed && <span>{lang === 'en' ? item.en : item.bm}</span>}
                  </Link>
                );
              })}
            </div>
          );
        })}
      </nav>

      {/* Footer / toggle */}
      <div style={{
        borderTop: '1px solid rgba(255,255,255,0.07)',
        padding: '10px 12px', display: 'flex', alignItems: 'center',
        justifyContent: collapsed ? 'center' : 'space-between',
      }}>
        {!collapsed && (
          <span style={{ fontSize: 10.5, color: 'rgba(255,255,255,0.32)', fontWeight: 500 }}>
            SmartDQC v3.0
          </span>
        )}
        <button
          onClick={onToggle}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          style={{
            background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.08)',
            color: 'rgba(255,255,255,0.55)', padding: 7, borderRadius: 8,
            transition: 'all var(--transition)', display: 'flex', alignItems: 'center',
          }}
          onMouseEnter={e => { e.currentTarget.style.color = '#fff'; e.currentTarget.style.background = 'rgba(255,255,255,0.12)'; }}
          onMouseLeave={e => { e.currentTarget.style.color = 'rgba(255,255,255,0.55)'; e.currentTarget.style.background = 'rgba(255,255,255,0.05)'; }}
        >
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>
    </aside>
  );
}
