import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { authApi } from '../services/api';
import { useColorMode } from '../theme/colorMode';

export type User = {
  id: number;
  username: string;
  email: string;
  full_name?: string | null;
  is_verified?: boolean | null;
  is_active: boolean;
  role?: string | null;
  timezone?: string | null;
  currency_preference?: string | null;
  notification_preferences?: any;
  ui_preferences?: any;
  has_password?: boolean;
};

export type AuthContextValue = {
  user: User | null;
  token: string | null;
  ready: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (
    username: string,
    email: string,
    password: string,
    full_name?: string,
  ) => Promise<{ pendingApproval: boolean }>;
  logout: () => void;
  refreshMe: () => Promise<void>;
};

export const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const { setColorModePreference } = useColorMode();
  // Initialize token synchronously from localStorage to avoid redirect flicker
  const [token, setToken] = useState<string | null>(() => {
    try {
      return localStorage.getItem('qm_token');
    } catch {
      return null;
    }
  });
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const sync = async () => {
      try {
        if (token) {
          const me = await authApi.me();
          setUser(me as User);
          const pref = (me as any)?.ui_preferences?.color_mode_preference;
          if (pref === 'system' || pref === 'light' || pref === 'dark') {
            setColorModePreference(pref);
          }
        }
      } catch {
        try { localStorage.removeItem('qm_token'); } catch { }
        setToken(null);
        setUser(null);
      } finally {
        setReady(true);
      }
    };
    sync();
  }, []);

  const login = async (email: string, password: string) => {
    const res: any = await authApi.login({ email, password });
    const t = res?.access_token;
    if (!t) {
      throw new Error(res?.detail || 'Login failed - no token received');
    }
    localStorage.setItem('qm_token', t);
    setToken(t);
    const me = await authApi.me();
    setUser(me as User);
    const pref = (me as any)?.ui_preferences?.color_mode_preference;
    if (pref === 'system' || pref === 'light' || pref === 'dark') {
      setColorModePreference(pref);
    }
  };

  const register = async (username: string, email: string, password: string, full_name?: string) => {
    const data: any = await authApi.register({ username, email, password, full_name });
    if (data?.is_approved === false) {
      return { pendingApproval: true };
    }
    await login(email, password);
    return { pendingApproval: false };
  };

  const logout = React.useCallback(() => {
    try { localStorage.removeItem('qm_token'); } catch { /* ignore */ }
    setToken(null);
    setUser(null);
  }, []);

  // Listen for forced logout from the API interceptor (e.g. 401 on expired token)
  useEffect(() => {
    const handler = () => logout();
    window.addEventListener('auth:logout', handler);
    return () => window.removeEventListener('auth:logout', handler);
  }, [logout]);

  // OAuth callback (and similar) writes qm_token then dispatches auth:login — re-hydrate React state
  useEffect(() => {
    const handleAuthLogin = () => {
      let t: string | null = null;
      try {
        t = localStorage.getItem('qm_token');
      } catch {
        return;
      }
      if (!t) return;
      setToken(t);
      void (async () => {
        try {
          const me = await authApi.me();
          setUser(me as User);
          const pref = (me as any)?.ui_preferences?.color_mode_preference;
          if (pref === 'system' || pref === 'light' || pref === 'dark') {
            setColorModePreference(pref);
          }
        } catch {
          try {
            localStorage.removeItem('qm_token');
          } catch {
            /* ignore */
          }
          setToken(null);
          setUser(null);
        }
      })();
    };
    window.addEventListener('auth:login', handleAuthLogin);
    return () => window.removeEventListener('auth:login', handleAuthLogin);
  }, [setColorModePreference]);

  const refreshMe = async () => {
    const me: any = await authApi.me();
    setUser(me);
    const pref = me?.ui_preferences?.color_mode_preference;
    if (pref === 'system' || pref === 'light' || pref === 'dark') {
      setColorModePreference(pref);
    }
  };

  const value = useMemo<AuthContextValue>(() => ({
    user,
    token,
    ready,
    login,
    register,
    logout,
    refreshMe,
  }), [user, token, ready]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
};

// Optional accessor for non-authenticated contexts (tests, public pages, storybook).
export const useAuthOptional = () => {
  return useContext(AuthContext);
};

