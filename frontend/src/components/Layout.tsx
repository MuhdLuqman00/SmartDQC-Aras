import React, { useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { TopNav } from './TopNav';
import { ChatFab } from './ChatFab';
import { useLang } from '../context/LanguageContext';

interface Props { username?: string; role?: string; onLogout: () => void; }

export function Layout({ username: _username, role, onLogout }: Props): JSX.Element {
  const [collapsed, setCollapsed] = useState<boolean>(false);
  const location = useLocation();
  const { t } = useLang();

  const PAGE_META: Record<string, [string, string]> = {
    '/':         [t('Dashboard', 'Papan Pemuka'),          t('System overview', 'Gambaran keseluruhan sistem')],
    '/upload':   [t('Upload Dataset', 'Muat Naik Dataset'), t('Ingest CSV or Excel files', 'Ingest fail CSV atau Excel')],
    '/explorer': [t('Data Explorer', 'Penjelajah Data'),    t('Browse and analyse raw data', 'Semak dan analisis data mentah')],
    '/quality':  [t('Quality Check', 'Semakan Kualiti'),    t('Completeness score and anomalies', 'Skor kelengkapan dan anomali')],
    '/cleaning': [t('Data Cleaning', 'Pembersihan Data'),   t('Review auto-cleaning actions', 'Semak tindakan pembersihan automatik')],
    '/ai':       [t('Smart Analysis', 'Analisis Pintar'),   t('Ask questions in natural language', 'Tanya soalan dalam bahasa semula jadi')],
    '/geo':      [t('Geo Map', 'Peta Geo'),                 t('Choropleth map and district forecast', 'Peta choropleth dan ramalan daerah')],
    '/reports':  [t('Generate Report', 'Jana Laporan'),     t('Export KKM-branded PDF or PPTX', 'Eksport PDF atau PPTX berjenama KKM')],
    '/datasets': [t('Library', 'Perpustakaan'),             t('Compare datasets and link records', 'Bandingkan dataset dan paut rekod')],
    '/history':  [t('Session History', 'Sejarah Sesi'),     t('Review past cleaning sessions', 'Semak semula sesi pembersihan lepas')],
    '/settings': [t('Settings', 'Tetapan'),                 t('Quality thresholds and cleaning rules', 'Ambang kualiti dan peraturan pembersihan')],
    '/audit':    [t('Audit Log', 'Log Audit'),              t('System action history', 'Sejarah tindakan sistem')],
  };

  const match = Object.entries(PAGE_META).find(([p]) =>
    p === '/' ? location.pathname === '/' : location.pathname.startsWith(p)
  );
  const [title, subtitle] = match ? match[1] : ['SmartDQC', ''];

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      <Sidebar role={role} collapsed={collapsed} onToggle={() => setCollapsed(c => !c)} />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <TopNav title={title} subtitle={subtitle} onLogout={onLogout} />
        <main style={{ flex: 1, overflowY: 'auto', background: 'var(--bg)', padding: 24 }}>
          <Outlet />
        </main>
      </div>
      <ChatFab />
    </div>
  );
}
