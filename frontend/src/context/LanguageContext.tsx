import React, { createContext, useContext, useState } from 'react';

type Lang = 'EN' | 'MY';

interface LangCtx {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: (en: string, my: string) => string;
}

const LanguageContext = createContext<LangCtx>({
  lang: 'EN',
  setLang: () => {},
  t: (en) => en,
});

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLang] = useState<Lang>('EN');
  const t = (en: string, my: string) => (lang === 'MY' ? my : en);
  return (
    <LanguageContext.Provider value={{ lang, setLang, t }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLang() {
  return useContext(LanguageContext);
}
