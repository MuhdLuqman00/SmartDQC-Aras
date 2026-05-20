import React, { createContext, useContext, useState } from 'react';

export interface SessionState {
  cacheId:      string | null;
  filename:     string | null;
  sourceType:   string | null;
  rowCount:     number | null;
  qualityScore: number | null;
  cleanStats:   Record<string, unknown> | null;
  preview:      Record<string, unknown>[] | null;
  /** Active chat session id for the current dataset. Null = no chat
      selected yet; AIPage will auto-load the most recent on dataset
      mount. Reset to null whenever cacheId changes (handled in setSession). */
  chatId:       string | null;
}

interface SessionContextValue extends SessionState {
  setSession: (s: Partial<SessionState>) => void;
  setChatId: (id: string | null) => void;
  clearSession: () => void;
  /** legacy aliases used by Sidebar */
  currentCacheId:    string | null;
  currentFilename:   string | null;
  currentSourceType: string | null;
}

const empty: SessionState = {
  cacheId: null, filename: null, sourceType: null,
  rowCount: null, qualityScore: null, cleanStats: null, preview: null,
  chatId: null,
};

const SessionContext = createContext<SessionContextValue>({} as SessionContextValue);

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [session, setSessionState] = useState<SessionState>(empty);

  /* When the active dataset changes (cacheId is being set to a different
     value), drop the chatId — chats are scoped to a dataset and the
     previous chat won't make sense against the new dataset. */
  const setSession = (s: Partial<SessionState>) =>
    setSessionState(prev => {
      const datasetChanged = 'cacheId' in s && s.cacheId !== prev.cacheId;
      return {
        ...prev,
        ...s,
        chatId: datasetChanged ? null : (s.chatId ?? prev.chatId),
      };
    });

  const setChatId = (id: string | null) =>
    setSessionState(prev => ({ ...prev, chatId: id }));

  const clearSession = () => setSessionState(empty);

  return (
    <SessionContext.Provider value={{
      ...session,
      setSession,
      setChatId,
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
