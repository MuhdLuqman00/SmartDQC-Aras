import React, { createContext, useContext, useState, useCallback } from 'react';

interface SessionContextType {
  currentCacheId: string | null;
  setCurrentCacheId: (id: string | null) => void;
  currentSession: SessionInfo | null;
  setCurrentSession: (session: SessionInfo | null) => void;
}

interface SessionInfo {
  cache_id: string;
  filename: string;
  source_type: string;
  row_count?: number;
  quality_score?: number;
}

const SessionContext = createContext<SessionContextType>({
  currentCacheId: null,
  setCurrentCacheId: () => {},
  currentSession: null,
  setCurrentSession: () => {},
});

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [currentCacheId, setCurrentCacheId] = useState<string | null>(null);
  const [currentSession, setCurrentSession] = useState<SessionInfo | null>(null);

  return (
    <SessionContext.Provider value={{
      currentCacheId,
      setCurrentCacheId,
      currentSession,
      setCurrentSession,
    }}>
      {children}
    </SessionContext.Provider>
  );
}

export function useSession() {
  return useContext(SessionContext);
}
