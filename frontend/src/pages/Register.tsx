import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Eye, EyeOff } from 'lucide-react';
import toast from 'react-hot-toast';

import { useAuth } from '../context/AuthContext';
import AuthLayout from '../components/layout/AuthLayout';
import AppCard from '../components/ui/AppCard';
import FormField from '../components/ui/FormField';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

const Register: React.FC = () => {
  const { register } = useAuth();
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [fullName, setFullName] = useState('');
  const [password, setPassword] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const { pendingApproval } = await register(username, email, password, fullName);
      if (pendingApproval) {
        navigate('/login', { replace: true, state: { registeredPendingApproval: true } });
        return;
      }
      navigate('/');
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string } }; message?: string };
      toast.error(ax?.response?.data?.detail || ax?.message || 'Registration failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout>
      <AppCard>
        <form className="flex flex-col gap-4" onSubmit={handleSubmit} noValidate>
          <div>
            <h2 className="text-xl font-semibold tracking-tight text-card-foreground">Create account</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              One minute setup. You can connect brokerages after. New accounts may need administrator approval before
              you can sign in.
            </p>
          </div>
          <FormField label="Username" required>
            <Input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="yourname" autoComplete="username" />
          </FormField>
          <FormField label="Email" required>
            <Input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              autoComplete="email"
            />
          </FormField>
          <FormField label="Full name">
            <Input value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="Optional" autoComplete="name" />
          </FormField>
          <FormField label="Password" required htmlFor="register-password">
            <div className="relative">
              <Input
                id="register-password"
                type={showPw ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="pr-10"
                autoComplete="new-password"
              />
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                className="absolute top-1/2 right-1 h-7 w-7 -translate-y-1/2 text-muted-foreground"
                aria-label={showPw ? 'Hide password' : 'Show password'}
                onClick={() => setShowPw(!showPw)}
              >
                {showPw ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
              </Button>
            </div>
          </FormField>
          <Button type="submit" disabled={loading} className="h-11 rounded-lg" variant="default">
            {loading ? 'Creating account…' : 'Register'}
          </Button>
          <p className="text-sm text-muted-foreground">
            Already have an account?{' '}
            <Link to="/login" className="font-medium text-primary underline-offset-4 hover:underline">
              Log in
            </Link>
          </p>
        </form>
      </AppCard>
    </AuthLayout>
  );
};

export default Register;
