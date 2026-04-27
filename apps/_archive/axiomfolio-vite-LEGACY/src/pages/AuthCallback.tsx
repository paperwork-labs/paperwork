import { useEffect, type FC } from 'react';
import { useNavigate } from 'react-router-dom';
import { Loader2 } from 'lucide-react';

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

  return (
    <div
      className="flex min-h-screen flex-col items-center justify-center gap-3 bg-background px-4"
      role="status"
      aria-live="polite"
      aria-busy="true"
    >
      <Loader2 className="size-8 animate-spin text-primary" aria-hidden />
      <p className="text-sm text-muted-foreground">Completing sign-in…</p>
    </div>
  );
};

export default AuthCallback;
