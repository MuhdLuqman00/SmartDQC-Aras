import React, { createContext, useContext, useState } from 'react';

export interface User { username: string; role: string; }

interface AuthContextValue {
  user: User | null;
  isAuthenticated: boolean;
  isInitializing: boolean;
  identify: (name: string) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue>({} as AuthContextValue);

// Anonymous named-identity (no password). The user types a name once; we store
// it in localStorage and send it as the X-User header (see api/client.ts) so
// the backend can scope each person's history. The same name on any device
// resolves to the same history — that's the cross-device behaviour. Access
// control is the deployment's network perimeter (office LAN + Tailscale), not a
// password. Everyone is treated as 'admin' since there are no roles to gate.
function readIdentity(): User | null {
  const name = (localStorage.getItem('identity') || '').trim();
  return name ? { username: name, role: 'admin' } : null;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  // Identity lives in localStorage, so init is synchronous — no /auth/me round
  // trip, no isInitializing flicker. The flag is kept (always false) so the
  // existing AuthGuard interface is unchanged.
  const [user, setUser] = useState<User | null>(readIdentity);

  const identify = (name: string) => {
    const clean = name.trim();
    if (!clean) return;
    localStorage.setItem('identity', clean);
    setUser({ username: clean, role: 'admin' });
  };

  const logout = () => {
    localStorage.removeItem('identity');
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{ user, isAuthenticated: !!user, isInitializing: false, identify, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
