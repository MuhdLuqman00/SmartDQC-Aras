import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from './context/AuthContext';
import { LinkageProvider } from './context/LinkageContext';
import { Layout }             from './components/Layout';
import { LoginPage }          from './pages/LoginPage';
import { DashboardPage }      from './pages/DashboardPage';
import { FeaturesPage }       from './pages/FeaturesPage';
import { UploadPage }         from './pages/UploadPage';
import { ExplorerPage }       from './pages/ExplorerPage';
import { QualityPage }        from './pages/QualityPage';
import { CleaningPage }       from './pages/CleaningPage';
import { AIPage }             from './pages/AIPage';
import { ReportsPage }        from './pages/ReportsPage';
import { DatasetLibraryPage } from './pages/DatasetLibraryPage';
import { HistoryPage }        from './pages/HistoryPage';
import { SettingsPage }       from './pages/SettingsPage';
import { AuditPage }          from './pages/AuditPage';
import { GeoPage }            from './pages/GeoPage';
import { LinkagePage }        from './pages/LinkagePage';

function AuthGuard({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isInitializing } = useAuth();
  if (isInitializing) return null;
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />;
}

export function App(): JSX.Element {
  return (
    <BrowserRouter>
      <LinkageProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<AuthGuard><Layout /></AuthGuard>}>
            <Route path="/"         element={<DashboardPage />} />
            <Route path="/features" element={<FeaturesPage />} />
            <Route path="/upload"   element={<UploadPage />} />
            <Route path="/explorer" element={<ExplorerPage />} />
            <Route path="/quality"  element={<QualityPage />} />
            <Route path="/cleaning" element={<CleaningPage />} />
            <Route path="/ai"       element={<AIPage />} />
            {/* /chatbot used to render AIPage directly; keep as a redirect so
                old bookmarks and the legacy FeaturesPage NLQ card still resolve. */}
            <Route path="/chatbot"  element={<Navigate to="/ai" replace />} />
            <Route path="/geo"      element={<GeoPage />} />
            <Route path="/reports"  element={<ReportsPage />} />
            <Route path="/datasets" element={<DatasetLibraryPage />} />
            <Route path="/linkage"  element={<LinkagePage />} />
            <Route path="/history"  element={<HistoryPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/audit"    element={<AuditPage />} />
            <Route path="*"         element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </LinkageProvider>
    </BrowserRouter>
  );
}
