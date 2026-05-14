import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from './context/AuthContext';
import { Layout }             from './components/Layout';
import { LoginPage }          from './pages/LoginPage';
import { DashboardPage }      from './pages/DashboardPage';
import { UploadPage }         from './pages/UploadPage';
import { ExplorerPage }       from './pages/ExplorerPage';
import { QualityPage }        from './pages/QualityPage';
import { CleaningPage }       from './pages/CleaningPage';
import { AIPage }             from './pages/AIPage';
import { GeoPage }            from './pages/GeoPage';
import { ReportsPage }        from './pages/ReportsPage';
import { DatasetLibraryPage } from './pages/DatasetLibraryPage';
import { HistoryPage }        from './pages/HistoryPage';
import { SettingsPage }       from './pages/SettingsPage';
import { AuditPage }          from './pages/AuditPage';

function AuthGuard({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isInitializing } = useAuth();
  if (isInitializing) return null;
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />;
}

export function App(): JSX.Element {
  const { user, logout } = useAuth();

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={
          <AuthGuard>
            <Layout username={user?.username} role={user?.role} onLogout={logout} />
          </AuthGuard>
        }>
          <Route path="/"         element={<DashboardPage />} />
          <Route path="/upload"   element={<UploadPage />} />
          <Route path="/explorer" element={<ExplorerPage />} />
          <Route path="/quality"  element={<QualityPage />} />
          <Route path="/cleaning" element={<CleaningPage />} />
          <Route path="/ai"       element={<AIPage />} />
          <Route path="/geo"      element={<GeoPage />} />
          <Route path="/reports"  element={<ReportsPage />} />
          <Route path="/datasets" element={<DatasetLibraryPage />} />
          <Route path="/history"  element={<HistoryPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/audit"    element={<AuditPage />} />
          <Route path="*"         element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
