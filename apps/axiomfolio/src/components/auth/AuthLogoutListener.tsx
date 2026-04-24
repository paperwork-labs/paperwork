import React from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';

const PUBLIC_PATHS = new Set(['/login', '/register', '/invite', '/auth/callback']);

function isPublicPath(pathname: string): boolean {
  if (PUBLIC_PATHS.has(pathname)) return true;
  return Array.from(PUBLIC_PATHS).some((p) => pathname.startsWith(`${p}/`));
}

/**
 * Listens for the `auth:logout` event dispatched by `frontend/src/services/api.ts`
 * when access-token refresh fails (expired refresh cookie, revoked token family,
 * etc.) and explicitly navigates to `/login` with a toast.
 *
 * Lives inside `<Router>` so `useNavigate` is available. AuthContext's own
 * listener still clears React state and localStorage; this component owns the
 * routing + user-facing notification side effects so the page never gets stuck
 * in a "Loading…" state with all queries silently 401'ing.
 */
const AuthLogoutListener: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  React.useEffect(() => {
    const handler = () => {
      if (isPublicPath(location.pathname)) {
        return;
      }
      toast.error('Session expired. Please sign in again.', { id: 'auth-session-expired' });
      navigate('/login', { replace: true, state: { from: location } });
    };
    window.addEventListener('auth:logout', handler);
    return () => window.removeEventListener('auth:logout', handler);
  }, [navigate, location]);

  return null;
};

export default AuthLogoutListener;
