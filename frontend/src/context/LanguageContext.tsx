import React, { createContext, useContext, useState } from 'react';

type Lang = 'en' | 'bm';

interface LangContextValue {
  lang: Lang;
  setLang: (lang: Lang) => void;
  toggleLang: () => void;
  t: (en: string, bm: string) => string;
}

const LangContext = createContext<LangContextValue>({ lang: 'bm', setLang: () => {}, toggleLang: () => {}, t: (_, bm) => bm });

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => (localStorage.getItem('lang') as Lang) || 'bm');

  const setLang = (next: Lang) => {
    localStorage.setItem('lang', next);
    setLangState(next);
  };

  const toggleLang = () => setLang(lang === 'en' ? 'bm' : 'en');

  const t = (en: string, bm: string) => lang === 'en' ? en : bm;

  return <LangContext.Provider value={{ lang, setLang, toggleLang, t }}>{children}</LangContext.Provider>;
}

export const useLang = () => useContext(LangContext);
