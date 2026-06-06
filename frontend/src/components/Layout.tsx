import React, { useState, useEffect } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import { useAuth } from '../context/AuthContext';

export function Layout() {
  const { user } = useAuth();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    document.documentElement.style.setProperty('--sidebar-w', collapsed ? '72px' : '248px');
  }, [collapsed]);

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden', background: 'var(--bg)' }}>
      <Sidebar
        role={user?.role}
        collapsed={collapsed}
        onToggle={() => setCollapsed(c => !c)}
      />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 }}>
        <TopBar />
        <main style={{ flex: 1, overflowY: 'auto', background: 'var(--bg)' }}>
          <div
            key={location.pathname}
            className="page-enter"
            style={{ padding: '28px 32px', maxWidth: 1440, margin: '0 auto' }}
          >
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
