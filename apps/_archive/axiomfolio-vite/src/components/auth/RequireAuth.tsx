import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

const RequireAuth: React.FC<{ children: React.ReactElement }> = ({ children }) => {
  const { token, ready } = useAuth();
  const location = useLocation();
  if (!ready) {
    // Delay decision until auth context is hydrated
    return null;
  }
  if (!token) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  return children;
};

export default RequireAuth;


