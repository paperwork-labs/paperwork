import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';

import { authApi } from '../services/api';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

const Invite: React.FC = () => {
  const { token } = useParams();
  const navigate = useNavigate();
  const [email, setEmail] = React.useState<string | null>(null);
  const [role, setRole] = React.useState<string | null>(null);
  const [username, setUsername] = React.useState('');
  const [password, setPassword] = React.useState('');
  const [fullName, setFullName] = React.useState('');
  const [loading, setLoading] = React.useState(false);

  React.useEffect(() => {
    const load = async () => {
      if (!token) return;
      try {
        const res: Record<string, unknown> = (await authApi.inviteInfo(token)) as Record<string, unknown>;
        setEmail(typeof res?.email === 'string' ? res.email : null);
        setRole(typeof res?.role === 'string' ? res.role : null);
      } catch (e: unknown) {
        const ax = e as { response?: { data?: { detail?: string } }; message?: string };
        toast.error(ax?.response?.data?.detail || ax?.message || 'Invalid invite');
      }
    };
    void load();
  }, [token]);

  const passwordTooShort = password.length > 0 && password.length < 8;

  const accept = async () => {
    if (!token) return;
    if (!username.trim() || !password) {
      toast.error('Username and password are required');
      return;
    }
    if (password.length < 8) {
      toast.error('Password must be at least 8 characters');
      return;
    }
    setLoading(true);
    try {
      await authApi.acceptInvite({
        token,
        username: username.trim(),
        password,
        full_name: fullName.trim() || undefined,
      });
      toast.success('Invite accepted. You can now log in.');
      navigate('/login');
    } catch (e: unknown) {
      const ax = e as { response?: { data?: { detail?: string } }; message?: string };
      toast.error(ax?.response?.data?.detail || ax?.message || 'Failed to accept invite');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen justify-center bg-background p-6">
      <Card className="w-full max-w-[420px] gap-0 py-0">
        <CardHeader className="px-6 pt-6">
          <CardTitle>Accept Invite</CardTitle>
          <CardDescription>
            {email ? `Invite for ${email} (${role || 'user'})` : 'Loading invite...'}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3 px-6 pb-6">
          <div className="grid gap-2">
            <Label htmlFor="invite-full-name">Full name (optional)</Label>
            <Input
              id="invite-full-name"
              placeholder="Full name (optional)"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              autoComplete="name"
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="invite-username">Username</Label>
            <Input
              id="invite-username"
              placeholder="Username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="invite-password">Password</Label>
            <Input
              id="invite-password"
              placeholder="Password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
            />
          </div>
          <p
            className={passwordTooShort ? 'text-xs text-destructive' : 'text-xs text-muted-foreground'}
            id="invite-password-hint"
          >
            Password must be at least 8 characters.
          </p>
          <Button
            type="button"
            onClick={accept}
            disabled={loading || !username.trim() || password.length < 8}
            aria-describedby="invite-password-hint"
          >
            {loading ? 'Creating account…' : 'Create account'}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
};

export default Invite;
