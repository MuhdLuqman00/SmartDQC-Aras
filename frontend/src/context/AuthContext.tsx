import React, { createContext, useContext, useEffect, useState } from 'react';
import { api } from '../api/client';

export interface User { username: string; role: string; }

interface AuthContextValue {
  user: User | null;
  isAuthenticated: boolean;
  isInitializing: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue>({} as AuthContextValue);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isInitializing, setIsInitializing] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (!token) { setIsInitializing(false); return; }
    api.get<User>('/auth/me')
      .then(r => setUser(r.data))
      .catch(() => localStorage.removeItem('token'))
      .finally(() => setIsInitializing(false));
  }, []);

  const login = async (username: string, password: string) => {
    const fd = new FormData();
    fd.append('username', username);
    fd.append('password', password);
    const r = await api.post<{ access_token: string }>('/auth/login', fd);
    localStorage.setItem('token', r.data.access_token);
    const me = await api.get<User>('/auth/me');
    setUser(me.data);
  };

  const logout = () => {
    api.post('/auth/logout').catch(() => {});
    localStorage.removeItem('token');
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, isAuthenticated: !!user, isInitializing, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
