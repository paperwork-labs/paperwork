import React from 'react';
import { Box, Button, CardRoot, CardBody, Heading, Input, Text, VStack } from '@chakra-ui/react';
import { useParams, useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { authApi } from '../services/api';

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
        const res: any = await authApi.inviteInfo(token);
        setEmail(res?.email || null);
        setRole(res?.role || null);
      } catch (e: any) {
        toast.error(e?.response?.data?.detail || e?.message || 'Invalid invite');
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
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || e?.message || 'Failed to accept invite');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box p={6} display="flex" justifyContent="center">
      <CardRoot maxW="420px" w="full">
        <CardBody>
          <VStack align="stretch" gap={3}>
            <Heading size="md">Accept Invite</Heading>
            <Text fontSize="sm" color="fg.muted">
              {email ? `Invite for ${email} (${role || 'user'})` : 'Loading invite...'}
            </Text>
            <Input placeholder="Full name (optional)" value={fullName} onChange={(e) => setFullName(e.target.value)} />
            <Input placeholder="Username" value={username} onChange={(e) => setUsername(e.target.value)} />
            <Input placeholder="Password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
            <Text fontSize="xs" color={passwordTooShort ? 'status.danger' : 'fg.muted'}>
              Password must be at least 8 characters.
            </Text>
            <Button
              onClick={accept}
              loading={loading}
              colorScheme="brand"
              disabled={loading || !username.trim() || password.length < 8}
            >
              Create account
            </Button>
          </VStack>
        </CardBody>
      </CardRoot>
    </Box>
  );
};

export default Invite;
