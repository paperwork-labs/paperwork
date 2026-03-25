import React, { useEffect, useMemo, useState } from 'react';
import { Alert, Button, Input, VStack, Text, InputGroup, IconButton, Box, Separator } from '@chakra-ui/react';
import { useLocation, useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { FiEye, FiEyeOff } from 'react-icons/fi';
import toast from 'react-hot-toast';
import AuthLayout from '../components/layout/AuthLayout';
import AppCard from '../components/ui/AppCard';
import FormField from '../components/ui/FormField';
import { API_BASE_URL } from '../services/api';
import {
  axiosErrorDetailMessage,
  isPendingApprovalLoginError,
  isUnverifiedEmailLoginError,
} from '../utils/authErrors';

const LAST_ROUTE_STORAGE_KEY = 'qm.ui.last_route';

const PENDING_APPROVAL_MESSAGE =
  "Your account is pending admin approval. You'll receive access once an administrator approves your registration.";

const UNVERIFIED_EMAIL_MESSAGE =
  'Please check your inbox and click the verification link before signing in.';

const POST_REGISTER_APPROVAL_HINT =
  'Check your email to verify your address. An administrator must approve your account before you can sign in.';

const Login: React.FC = () => {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [loading, setLoading] = useState(false);
  const [pendingApprovalBanner, setPendingApprovalBanner] = useState(false);
  const [unverifiedEmailBanner, setUnverifiedEmailBanner] = useState(false);
  const [postRegisterBanner] = useState(
    !!(location.state as { registeredPendingApproval?: boolean } | null)?.registeredPendingApproval,
  );

  useEffect(() => {
    if ((location.state as { registeredPendingApproval?: boolean } | null)?.registeredPendingApproval) {
      navigate(
        { pathname: location.pathname, search: location.search, hash: location.hash },
        { replace: true, state: {} },
      );
    }
  }, [location.pathname, location.search, location.hash, location.state, navigate]);

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
    setPendingApprovalBanner(false);
    setUnverifiedEmailBanner(false);
    try {
      await login(username, password);
      navigate(redirectTo, { replace: true });
    } catch (err: unknown) {
      if (isPendingApprovalLoginError(err)) {
        setPendingApprovalBanner(true);
        return;
      }
      if (isUnverifiedEmailLoginError(err)) {
        setUnverifiedEmailBanner(true);
        return;
      }
      toast.error(axiosErrorDetailMessage(err) || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout>
      <AppCard>
        <VStack gap={4} align="stretch">
          <Box>
            <Text fontSize="xl" fontWeight="semibold" letterSpacing="-0.02em" color="fg.default">
              Log in
            </Text>
            <Text mt={1} fontSize="sm" color="fg.muted">
              Welcome back. Enter your credentials to continue.
            </Text>
          </Box>
          {pendingApprovalBanner ? (
            <Alert.Root colorPalette="blue" status="info" variant="subtle" size="sm">
              <Alert.Indicator />
              <Alert.Content>
                <Alert.Description fontSize="sm">{PENDING_APPROVAL_MESSAGE}</Alert.Description>
              </Alert.Content>
            </Alert.Root>
          ) : unverifiedEmailBanner ? (
            <Alert.Root colorPalette="blue" status="info" variant="subtle" size="sm">
              <Alert.Indicator />
              <Alert.Content>
                <Alert.Description fontSize="sm">{UNVERIFIED_EMAIL_MESSAGE}</Alert.Description>
              </Alert.Content>
            </Alert.Root>
          ) : postRegisterBanner ? (
            <Alert.Root colorPalette="blue" status="info" variant="subtle" size="sm">
              <Alert.Indicator />
              <Alert.Content>
                <Alert.Title fontSize="sm">Registration received</Alert.Title>
                <Alert.Description fontSize="sm">{POST_REGISTER_APPROVAL_HINT}</Alert.Description>
              </Alert.Content>
            </Alert.Root>
          ) : null}
          <Button
            variant="outline"
            borderRadius="lg"
            h={11}
            fontWeight="medium"
            onClick={() => { window.location.href = `${API_BASE_URL}/auth/google/login`; }}
          >
            <svg width="18" height="18" viewBox="0 0 48 48" style={{ marginRight: 8 }}>
              <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
              <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
              <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
              <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
            </svg>
            Continue with Google
          </Button>
          <Button
            variant="solid"
            borderRadius="lg"
            h={11}
            fontWeight="medium"
            bg="#000"
            color="#fff"
            _hover={{ bg: '#1a1a1a' }}
            _active={{ bg: '#333' }}
            onClick={() => { window.location.href = `${API_BASE_URL}/auth/apple/login`; }}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="white" style={{ marginRight: 8 }}>
              <path d="M17.05 20.28c-.98.95-2.05.88-3.08.4-1.09-.5-2.08-.48-3.24 0-1.44.62-2.2.44-3.06-.4C2.79 15.25 3.51 7.59 9.05 7.31c1.35.07 2.29.74 3.08.8 1.18-.24 2.31-.93 3.57-.84 1.51.12 2.65.72 3.4 1.8-3.12 1.87-2.38 5.98.48 7.13-.57 1.5-1.31 2.99-2.54 4.09zM12.03 7.25c-.15-2.23 1.66-4.07 3.74-4.25.29 2.58-2.34 4.5-3.74 4.25z"/>
            </svg>
            Continue with Apple
          </Button>
          <Separator />
          <VStack as="form" gap={4} align="stretch" onSubmit={handleSubmit}>
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
            bg="amber.500"
            color="white"
            _hover={{ bg: 'amber.400' }}
            _active={{ bg: 'amber.600' }}
            borderRadius="lg"
            h={11}
            fontWeight="semibold"
          >
            Log in
          </Button>
          <Text fontSize="sm" color="fg.muted">
            No account? <Link to="/register" style={{ color: 'var(--chakra-colors-amber-400)' }}>Register</Link>
          </Text>
          </VStack>
        </VStack>
      </AppCard>
    </AuthLayout>
  );
};

export default Login;


