import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  LayoutDashboard, Upload, Table2, ShieldCheck, Bot, BarChart3,
  BookOpen, Clock, Settings, ClipboardList, ChevronRight, ChevronLeft,
  MapPin, Brush, LayoutGrid, Link2,
} from 'lucide-react';
import { useLang } from '../context/LanguageContext';
import { useSession } from '../context/SessionContext';
import { BRAND } from '../config/brand';

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
      // Cross-dataset linkage — admin-only because it can surface PII
      // (full IC + name + DOB) across previously-isolated datasets.
      { path: '/linkage',  en: 'Linkage',        bm: 'Pemautan',       icon: <Link2 size={18} />,   adminOnly: true },
    ],
  },
  {
    labelEn: 'INTELLIGENCE', labelBm: 'KECERDASAN',
    items: [
      // AI narrative + NLQ are now one unified page; the /chatbot route
      // still resolves (redirects to /ai) so old bookmarks keep working.
      { path: '/ai', en: 'AI Assistant', bm: 'Pembantu AI', icon: <Bot size={18} /> },
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

const NO_CACHE_PAGES = ['/upload', '/datasets', '/linkage', '/history', '/settings', '/audit', '/features'];

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
      /* Flat navy "ink", not a gradient — a printed-document surface reads as
         deliberate, where a soft gradient reads as generic SaaS chrome. */
      background: 'var(--brand-deep)',
      display: 'flex', flexDirection: 'column',
      transition: 'width var(--transition-lg)',
      overflow: 'hidden', flexShrink: 0,
      borderRight: '1px solid rgba(255,255,255,0.06)',
      position: 'relative',
    }}>
      {/* Brand — pure-typographic letterhead. No monogram tile:
          the serif wordmark + a single gold rule + the org register carry
          the identity. A flat, document-like mark that reads as deliberate and
          can't be mistaken for a generated/stock badge. Height matches the
          TopBar (64px) so the divider below aligns with the page content line.
          The gold rule (alignItems:stretch) spans the register width. */}
      <div style={{
        height: 64, flexShrink: 0, display: 'flex', alignItems: 'center',
        justifyContent: collapsed ? 'center' : 'flex-start',
        padding: collapsed ? '0 12px' : '0 20px',
        borderBottom: '1px solid rgba(255,255,255,0.07)',
      }}>
        {collapsed ? (
          <div style={{ display: 'inline-flex', flexDirection: 'column', alignItems: 'center' }}>
            <span style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 22, color: '#fff', lineHeight: 1 }}>S</span>
            <span style={{ width: 18, height: 1.5, marginTop: 5, background: 'var(--accent)' }} />
          </div>
        ) : (
          <div style={{ display: 'inline-flex', flexDirection: 'column', alignItems: 'stretch' }}>
            <span style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 17, color: '#fff', lineHeight: 1, whiteSpace: 'nowrap' }}>
              SmartDQC
            </span>
            <span style={{ height: 1.5, margin: '7px 0 6px', background: 'var(--accent)' }} />
            <span style={{
              fontFamily: 'var(--font-mono)', fontSize: 8, letterSpacing: '0.06em',
              textTransform: 'uppercase', color: 'rgba(255,255,255,0.46)',
              whiteSpace: 'nowrap', lineHeight: 1,
            }}>
              {lang === 'en' ? BRAND.orgNameEn : BRAND.orgNameBm}
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
                const label = lang === 'en' ? item.en : item.bm;
                return (
                  <Link
                    key={item.path}
                    to={buildLink(item.path)}
                    className={`icon-pop-host ${collapsed ? 'tooltip-host' : ''}`}
                    onMouseEnter={() => setHovered(item.path)}
                    onMouseLeave={() => setHovered(null)}
                    style={{
                      position: 'relative',
                      display: 'flex', alignItems: 'center', gap: 12,
                      padding: collapsed ? '11px 14px' : '10px 14px',
                      borderRadius: 6, marginBottom: 2,
                      color: active ? '#fff' : hov ? 'rgba(255,255,255,0.92)' : 'rgba(255,255,255,0.55)',
                      /* Flat lifted row for the active item — no gradient
                         (gradients read as generic SaaS chrome). */
                      background: active
                        ? 'rgba(255,255,255,0.07)'
                        : hov ? 'rgba(255,255,255,0.06)' : 'transparent',
                      fontSize: 13.5, fontWeight: active ? 600 : 500,
                      transition: 'color var(--transition), background var(--transition)',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {active && (
                      /* Flat gold index bar — a crisp "you are here" marker,
                         no glow, no gradient. Absolutely positioned so the
                         label never shifts between active and inactive. */
                      <span style={{
                        position: 'absolute', left: 0, top: '50%', transform: 'translateY(-50%)',
                        width: 3, height: 20, borderRadius: 1,
                        background: 'var(--accent)',
                      }} />
                    )}
                    <span className="icon-pop" style={{ flexShrink: 0, display: 'flex', alignItems: 'center' }}>{item.icon}</span>
                    <span style={{
                      opacity: collapsed ? 0 : 1,
                      maxWidth: collapsed ? 0 : 200,
                      overflow: 'hidden',
                      transition: 'opacity 180ms ease-out, max-width var(--transition-lg)',
                      transitionDelay: collapsed ? '0ms' : '80ms',
                    }}>{label}</span>
                    {collapsed && <span className="tooltip-chip">{label}</span>}
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
