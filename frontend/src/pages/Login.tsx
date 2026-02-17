import React, { useMemo, useState } from 'react';
import { Button, Input, VStack, Text, InputGroup, IconButton, Box } from '@chakra-ui/react';
import { useLocation, useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { FiEye, FiEyeOff } from 'react-icons/fi';
import toast from 'react-hot-toast';
import AuthLayout from '../components/layout/AuthLayout';
import AppCard from '../components/ui/AppCard';
import FormField from '../components/ui/FormField';

const LAST_ROUTE_STORAGE_KEY = 'qm.ui.last_route';

const Login: React.FC = () => {
  const { login } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  const redirectTo = useMemo(() => {
    const stateFrom = (location.state as any)?.from;
    const candidate =
      typeof stateFrom?.pathname === 'string'
        ? `${stateFrom.pathname || ''}${stateFrom.search || ''}${stateFrom.hash || ''}`
        : null;
    if (candidate && candidate !== '/login' && candidate !== '/register') return candidate;
    try {
      const saved = localStorage.getItem(LAST_ROUTE_STORAGE_KEY);
      if (saved && saved !== '/login' && saved !== '/register') return saved;
    } catch {
      // ignore storage errors
    }
    return '/';
  }, [location.state]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await login(username, password);
      navigate(redirectTo, { replace: true });
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || err?.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout>
      <AppCard>
        <VStack as="form" gap={4} align="stretch" onSubmit={handleSubmit}>
          <Box>
            <Text fontSize="xl" fontWeight="semibold" letterSpacing="-0.02em" color="fg.default">
              Log in
            </Text>
            <Text mt={1} fontSize="sm" color="fg.muted">
              Welcome back. Enter your credentials to continue.
            </Text>
          </Box>
          <FormField label="Username" required>
            <Input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="yourname" />
          </FormField>
          <FormField label="Password" required>
            <InputGroup
              endElement={
                <IconButton
                  aria-label={showPw ? 'Hide password' : 'Show password'}
                  size="sm"
                  variant="ghost"
                  onClick={() => setShowPw(!showPw)}
                  color="fg.muted"
                >
                  {showPw ? <FiEyeOff /> : <FiEye />}
                </IconButton>
              }
            >
              <Input type={showPw ? 'text' : 'password'} value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" />
            </InputGroup>
          </FormField>
          <Button
            type="submit"
            loading={loading}
            bg="brand.500"
            _hover={{ bg: 'brand.400' }}
            _active={{ bg: 'brand.600' }}
            borderRadius="lg"
            h={11}
          >
            Login
          </Button>
          <Text fontSize="sm" color="fg.muted">
            No account? <Link to="/register" style={{ color: 'var(--chakra-colors-brand-700)' }}>Register</Link>
          </Text>
        </VStack>
      </AppCard>
    </AuthLayout>
  );
};

export default Login;


