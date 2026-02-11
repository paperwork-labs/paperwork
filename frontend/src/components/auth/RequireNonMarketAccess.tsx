import React from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

type Section = 'portfolio' | 'strategy';

const RequireNonMarketAccess: React.FC<{ children?: React.ReactElement; section?: Section }> = ({ children, section }) => {
  const { user, appSettings, ready, appSettingsReady } = useAuth();
  const location = useLocation();
  if (!ready || !appSettingsReady) {
    return null;
  }
  const isAdmin = user?.role === 'admin';
  if (isAdmin) {
    return children ?? <Outlet />;
  }

  const marketOnly = appSettings?.market_only_mode ?? true;
  if (marketOnly) {
    return <Navigate to="/" state={{ from: location }} replace />;
  }

  if (section === 'portfolio' && !Boolean(appSettings?.portfolio_enabled)) {
    return <Navigate to="/" state={{ from: location }} replace />;
  }
  if (section === 'strategy' && !Boolean(appSettings?.strategy_enabled)) {
    return <Navigate to="/" state={{ from: location }} replace />;
  }

  return children ?? <Outlet />;
};

export default RequireNonMarketAccess;
