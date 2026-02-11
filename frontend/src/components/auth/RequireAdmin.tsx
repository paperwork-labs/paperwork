import React from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

const RequireAdmin: React.FC<{ children?: React.ReactElement }> = ({ children }) => {
  const { user, ready } = useAuth();
  const location = useLocation();
  if (!ready) {
    return null;
  }
  if (user?.role !== 'admin') {
    return <Navigate to="/" state={{ from: location }} replace />;
  }
  return children ?? <Outlet />;
};

export default RequireAdmin;
