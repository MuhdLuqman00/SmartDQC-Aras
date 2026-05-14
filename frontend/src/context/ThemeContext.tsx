import React, { createContext, useContext, useState, useEffect } from 'react';
import { applyTheme } from '../theme';

interface ThemeCtx { darkMode: boolean; toggleDarkMode: () => void; }
const ThemeContext = createContext<ThemeCtx>({ darkMode: false, toggleDarkMode: () => {} });

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [darkMode, setDarkMode] = useState<boolean>(
    () => localStorage.getItem('sdqc_dark') === 'true'
  );
  useEffect(() => { applyTheme(darkMode); }, [darkMode]);
  const toggleDarkMode = () => {
    setDarkMode(d => {
      const next = !d;
      localStorage.setItem('sdqc_dark', String(next));
      return next;
    });
  };
  return (
    <ThemeContext.Provider value={{ darkMode, toggleDarkMode }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() { return useContext(ThemeContext); }
