import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { authApi, appSettingsApi } from '../services/api';
import { useColorMode } from '../theme/colorMode';

type User = {
  id: number;
  username: string;
  email: string;
  full_name?: string | null;
  is_active: boolean;
  role?: string | null;
  timezone?: string | null;
  currency_preference?: string | null;
  notification_preferences?: any;
  ui_preferences?: any;
  has_password?: boolean;
};

type AppSettings = {
  market_only_mode: boolean;
  portfolio_enabled: boolean;
  strategy_enabled: boolean;
};

type AuthContextValue = {
  user: User | null;
  token: string | null;
  ready: boolean;
  appSettings: AppSettings | null;
  appSettingsReady: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, email: string, password: string, full_name?: string) => Promise<void>;
  logout: () => void;
  refreshMe: () => Promise<void>;
  refreshAppSettings: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

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
  const [appSettings, setAppSettings] = useState<AppSettings | null>(null);
  const [appSettingsReady, setAppSettingsReady] = useState(false);

  useEffect(() => {
    const sync = async () => {
      try {
        if (token) {
          const me: any = await authApi.me();
          setUser(me);
          const pref = me?.ui_preferences?.color_mode_preference;
          if (pref === 'system' || pref === 'light' || pref === 'dark') {
            setColorModePreference(pref);
          }
          try {
            const app = await appSettingsApi.get();
            setAppSettings(app as AppSettings);
          } catch {
            setAppSettings(null);
          }
        }
      } catch {
        // invalid token -> clear
        try { localStorage.removeItem('qm_token'); } catch { }
        setToken(null);
        setUser(null);
        setAppSettings(null);
      } finally {
        setReady(true);
        setAppSettingsReady(true);
      }
    };
    sync();
  }, []);

  const login = async (username: string, password: string) => {
    const res: any = await authApi.login({ username, password });
    const t = res?.access_token;
    if (t) {
      localStorage.setItem('qm_token', t);
      setToken(t);
      const me: any = await authApi.me();
      setUser(me);
      const pref = me?.ui_preferences?.color_mode_preference;
      if (pref === 'system' || pref === 'light' || pref === 'dark') {
        setColorModePreference(pref);
      }
      try {
        const app = await appSettingsApi.get();
        setAppSettings(app as AppSettings);
      } catch {
        setAppSettings(null);
      } finally {
        setAppSettingsReady(true);
      }
    }
  };

  const register = async (username: string, email: string, password: string, full_name?: string) => {
    await authApi.register({ username, email, password, full_name });
    await login(username, password);
  };

  const logout = () => {
    localStorage.removeItem('qm_token');
    setToken(null);
    setUser(null);
    setAppSettings(null);
    setAppSettingsReady(false);
  };

  const refreshMe = async () => {
    const me: any = await authApi.me();
    setUser(me);
    const pref = me?.ui_preferences?.color_mode_preference;
    if (pref === 'system' || pref === 'light' || pref === 'dark') {
      setColorModePreference(pref);
    }
  };

  const refreshAppSettings = async () => {
    const app = await appSettingsApi.get();
    setAppSettings(app as AppSettings);
    setAppSettingsReady(true);
  };

  const value = useMemo<AuthContextValue>(() => ({
    user,
    token,
    ready,
    appSettings,
    appSettingsReady,
    login,
    register,
    logout,
    refreshMe,
    refreshAppSettings,
  }), [user, token, ready, appSettings, appSettingsReady]);

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


