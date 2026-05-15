import React from 'react';
import ReactDOM from 'react-dom/client';
import './styles/tokens.css';
import { ThemeProvider } from './context/ThemeContext';
import { LanguageProvider } from './context/LanguageContext';
import { AuthProvider } from './context/AuthContext';
import { SessionProvider } from './context/SessionContext';
import { App } from './App';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ThemeProvider>
      <LanguageProvider>
        <AuthProvider>
          <SessionProvider>
            <App />
          </SessionProvider>
        </AuthProvider>
      </LanguageProvider>
    </ThemeProvider>
  </React.StrictMode>,
);
