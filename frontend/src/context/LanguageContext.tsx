import React, { createContext, useContext, useState } from 'react';

type Lang = 'en' | 'bm';

interface LangContextValue {
  lang: Lang;
  toggleLang: () => void;
  t: (en: string, bm: string) => string;
}

const LangContext = createContext<LangContextValue>({ lang: 'bm', toggleLang: () => {}, t: (_, bm) => bm });

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLang] = useState<Lang>(() => (localStorage.getItem('lang') as Lang) || 'bm');

  const toggleLang = () => setLang(l => {
    const next = l === 'en' ? 'bm' : 'en';
    localStorage.setItem('lang', next);
    return next;
  });

  const t = (en: string, bm: string) => lang === 'en' ? en : bm;

  return <LangContext.Provider value={{ lang, toggleLang, t }}>{children}</LangContext.Provider>;
}

export const useLang = () => useContext(LangContext);
