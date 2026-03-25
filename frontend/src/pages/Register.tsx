import React, { useState } from 'react';
import { Button, Input, VStack, Text, InputGroup, IconButton, Box } from '@chakra-ui/react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { FiEye, FiEyeOff } from 'react-icons/fi';
import toast from 'react-hot-toast';
import AuthLayout from '../components/layout/AuthLayout';
import AppCard from '../components/ui/AppCard';
import FormField from '../components/ui/FormField';

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
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || err?.message || 'Registration failed');
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
              Create account
            </Text>
            <Text mt={1} fontSize="sm" color="fg.muted">
              One minute setup. You can connect brokerages after. New accounts may need administrator approval before
              you can sign in.
            </Text>
          </Box>
          <FormField label="Username" required>
            <Input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="yourname" />
          </FormField>
          <FormField label="Email" required>
            <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" />
          </FormField>
          <FormField label="Full name">
            <Input value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="Optional" />
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
            Register
          </Button>
          <Text fontSize="sm" color="fg.muted">
            Already have an account? <Link to="/login" style={{ color: 'var(--chakra-colors-brand-700)' }}>Log in</Link>
          </Text>
        </VStack>
      </AppCard>
    </AuthLayout>
  );
};

export default Register;


