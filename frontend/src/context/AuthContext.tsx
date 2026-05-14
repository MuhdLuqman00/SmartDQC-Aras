import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { api } from '../api/client';

export interface User {
  username: string;
  role: 'admin' | 'user';
}

interface AuthCtx {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isInitializing: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  fetchMe: () => Promise<void>;
}

const AuthContext = createContext<AuthCtx>({
  user: null, token: null, isAuthenticated: false, isInitializing: true,
  login: async () => {}, logout: () => {}, fetchMe: async () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const storedToken = localStorage.getItem('smartdqc_token');
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(storedToken);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [isInitializing, setIsInitializing] = useState<boolean>(!!storedToken);

  const logout = useCallback(() => {
    localStorage.removeItem('smartdqc_token');
    setToken(null);
    setUser(null);
    setIsAuthenticated(false);
  }, []);

  const fetchMe = useCallback(async () => {
    try {
      const { data } = await api.get<{ username: string; role: string }>('/auth/me');
      setUser({ username: data.username, role: data.role as 'admin' | 'user' });
      setIsAuthenticated(true);
    } catch {
      logout();
    }
  }, [logout]);

  useEffect(() => {
    if (storedToken) {
      fetchMe().finally(() => setIsInitializing(false));
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const login = useCallback(async (username: string, password: string) => {
    const form = new URLSearchParams();
    form.append('username', username);
    form.append('password', password);
    const { data } = await api.post<{ access_token: string; token_type: string; role: string }>(
      '/auth/login', form,
      { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } },
    );
    localStorage.setItem('smartdqc_token', data.access_token);
    setToken(data.access_token);
    setUser({ username, role: data.role as 'admin' | 'user' });
    setIsAuthenticated(true);
  }, []);

  return (
    <AuthContext.Provider value={{ user, token, isAuthenticated, isInitializing, login, logout, fetchMe }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
