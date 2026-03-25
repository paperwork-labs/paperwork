import { useEffect, type FC } from 'react';
import { useNavigate } from 'react-router-dom';

const LAST_ROUTE_STORAGE_KEY = 'qm.ui.last_route';

const AuthCallback: FC = () => {
  const navigate = useNavigate();

  useEffect(() => {
    const hash = window.location.hash.replace('#', '');
    const params = new URLSearchParams(hash);
    const token = params.get('token');

    if (token) {
      localStorage.setItem('qm_token', token);
      window.dispatchEvent(new Event('auth:login'));
      window.history.replaceState(null, '', window.location.pathname);
    }

    let redirectTo = '/';
    try {
      const saved = localStorage.getItem(LAST_ROUTE_STORAGE_KEY);
      if (saved && saved !== '/login' && saved !== '/register' && saved !== '/auth/callback') {
        redirectTo = saved;
      }
    } catch {
      // ignore storage errors
    }

    navigate(redirectTo, { replace: true });
  }, [navigate]);

  return null;
};

export default AuthCallback;
