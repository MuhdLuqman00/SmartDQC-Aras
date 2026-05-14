import React from 'react';
import ReactDOM from 'react-dom/client';
import './styles/tokens.css';
import { ThemeProvider } from './context/ThemeContext';
import { App } from './App';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ThemeProvider>
      <App />
    </ThemeProvider>
  </React.StrictMode>,
);
