import React, { createContext, useContext, useState } from 'react';

export interface SessionState {
  cacheId:      string | null;
  filename:     string | null;
  sourceType:   string | null;
  rowCount:     number | null;
  qualityScore: number | null;
  cleanStats:   Record<string, unknown> | null;
  preview:      Record<string, unknown>[] | null;
}

interface SessionContextValue extends SessionState {
  setSession: (s: Partial<SessionState>) => void;
  clearSession: () => void;
  /** legacy aliases used by Sidebar */
  currentCacheId:    string | null;
  currentFilename:   string | null;
  currentSourceType: string | null;
}

const empty: SessionState = {
  cacheId: null, filename: null, sourceType: null,
  rowCount: null, qualityScore: null, cleanStats: null, preview: null,
};

const SessionContext = createContext<SessionContextValue>({} as SessionContextValue);

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [session, setSessionState] = useState<SessionState>(empty);

  const setSession = (s: Partial<SessionState>) =>
    setSessionState(prev => ({ ...prev, ...s }));

  const clearSession = () => setSessionState(empty);

  return (
    <SessionContext.Provider value={{
      ...session,
      setSession,
      clearSession,
      currentCacheId:    session.cacheId,
      currentFilename:   session.filename,
      currentSourceType: session.sourceType,
    }}>
      {children}
    </SessionContext.Provider>
  );
}

export const useSession = () => useContext(SessionContext);
