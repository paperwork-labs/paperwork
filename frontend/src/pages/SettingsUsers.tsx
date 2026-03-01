import React from 'react';
import {
  Box,
  Button,
  HStack,
  Text,
  VStack,
  Input,
  Badge,
  TableRoot,
  TableHeader,
  TableBody,
  TableRow,
  TableColumnHeader,
  TableCell,
  TableScrollArea,
  CardRoot,
  CardBody,
} from '@chakra-ui/react';
import toast from 'react-hot-toast';
import { adminUsersApi } from '../services/api';
import { formatDate } from '../utils/format';
import { useUserPreferences } from '../hooks/useUserPreferences';

type UserRow = {
  id: number;
  username: string;
  email: string;
  role: string;
  is_active: boolean;
  is_verified?: boolean;
  created_at?: string;
  last_login?: string | null;
  full_name?: string | null;
};

type InviteRow = {
  id: number;
  email: string;
  role: string;
  token: string;
  expires_at: string;
  accepted_at?: string | null;
  created_at?: string;
};

const ROLE_OPTIONS = [
  { label: 'Viewer', value: 'readonly' },
  { label: 'Analyst', value: 'analyst' },
  { label: 'Admin', value: 'admin' },
];

const SettingsUsers: React.FC = () => {
  const { timezone } = useUserPreferences();
  const [users, setUsers] = React.useState<UserRow[]>([]);
  const [invites, setInvites] = React.useState<InviteRow[]>([]);
  const [loading, setLoading] = React.useState(false);
  const [inviteEmail, setInviteEmail] = React.useState('');
  const [inviteRole, setInviteRole] = React.useState('readonly');
  const [inviteUrl, setInviteUrl] = React.useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const res = await adminUsersApi.list();
      const inv = await adminUsersApi.invites();
      setUsers((res?.users ?? []) as UserRow[]);
      setInvites((inv?.invites ?? []) as InviteRow[]);
    } catch (e: any) {
      toast.error(e?.message || 'Failed to load users');
    } finally {
      setLoading(false);
    }
  };

  React.useEffect(() => {
    void load();
  }, []);

  const inviteUser = async () => {
    if (!inviteEmail.trim()) {
      toast.error('Email is required');
      return;
    }
    try {
      const res: any = await adminUsersApi.invite({
        email: inviteEmail.trim(),
        role: inviteRole,
      });
      const token = res?.token;
      const url = token ? `${window.location.origin}/invite/${token}` : null;
      setInviteUrl(url);
      setInviteEmail('');
      await load();
      toast.success('Invite created');
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || e?.message || 'Failed to create invite');
    }
  };

  const updateUser = async (userId: number, payload: { role?: string; is_active?: boolean }) => {
    try {
      await adminUsersApi.update(userId, payload);
      await load();
      toast.success('User updated');
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || e?.message || 'Failed to update user');
    }
  };

  const copyInvite = async () => {
    if (!inviteUrl) return;
    try {
      await navigator.clipboard.writeText(inviteUrl);
      toast.success('Invite link copied');
    } catch {
      toast.error('Failed to copy invite link');
    }
  };

  return (
    <Box>
      <Text fontSize="lg" fontWeight="semibold" mb={2}>
        Users
      </Text>
      <Text fontSize="sm" color="fg.muted" mb={4}>
        Invite users via email and manage roles.
      </Text>

      <CardRoot mb={4}>
        <CardBody>
          <HStack gap={3} flexWrap="wrap">
            <Input
              placeholder="email@example.com"
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
              maxW="280px"
            />
            <select
              value={inviteRole}
              onChange={(e) => setInviteRole(e.target.value)}
              style={{
                width: 180,
                fontSize: 12,
                padding: '8px 10px',
                borderRadius: 10,
                border: '1px solid var(--chakra-colors-border-subtle)',
                background: 'var(--chakra-colors-bg-input)',
                color: 'var(--chakra-colors-fg-default)',
              }}
            >
              {ROLE_OPTIONS.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
                </option>
              ))}
            </select>
            <Button size="sm" onClick={inviteUser} loading={loading}>
              Create Invite
            </Button>
            {inviteUrl ? (
              <Button size="sm" variant="outline" onClick={copyInvite}>
                Copy Invite Link
              </Button>
            ) : null}
          </HStack>
          {inviteUrl ? (
            <Text mt={2} fontSize="xs" color="fg.muted">
              {inviteUrl}
            </Text>
          ) : null}
        </CardBody>
      </CardRoot>

      <TableScrollArea borderWidth="1px" borderColor="border.subtle" borderRadius="lg">
        <TableRoot size="sm">
          <TableHeader>
            <TableRow>
              <TableColumnHeader>User</TableColumnHeader>
              <TableColumnHeader>Email</TableColumnHeader>
              <TableColumnHeader>Role</TableColumnHeader>
              <TableColumnHeader>Status</TableColumnHeader>
              <TableColumnHeader>Actions</TableColumnHeader>
            </TableRow>
          </TableHeader>
          <TableBody>
            {users.map((u) => (
              <TableRow key={u.id}>
                <TableCell>
                  <VStack align="start" gap={0}>
                    <Text fontSize="sm" fontWeight="medium">{u.full_name || u.username}</Text>
                    <Text fontSize="xs" color="fg.muted">@{u.username}</Text>
                  </VStack>
                </TableCell>
                <TableCell>{u.email}</TableCell>
                <TableCell>
                  <select
                    value={u.role}
                    onChange={(e) => updateUser(u.id, { role: e.target.value })}
                    style={{
                      width: 160,
                      fontSize: 12,
                      padding: '6px 8px',
                      borderRadius: 8,
                      border: '1px solid var(--chakra-colors-border-subtle)',
                      background: 'var(--chakra-colors-bg-input)',
                      color: 'var(--chakra-colors-fg-default)',
                    }}
                  >
                    {ROLE_OPTIONS.map((r) => (
                      <option key={r.value} value={r.value}>
                        {r.label}
                      </option>
                    ))}
                  </select>
                </TableCell>
                <TableCell>
                  {u.is_active ? <Badge colorScheme="green">Active</Badge> : <Badge colorScheme="red">Disabled</Badge>}
                </TableCell>
                <TableCell>
                  <Button
                    size="xs"
                    variant="outline"
                    onClick={() => updateUser(u.id, { is_active: !u.is_active })}
                  >
                    {u.is_active ? 'Deactivate' : 'Activate'}
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </TableRoot>
      </TableScrollArea>

      {invites.length ? (
        <Box mt={6}>
          <Text fontSize="sm" fontWeight="semibold" mb={2}>
            Pending Invites
          </Text>
          <TableScrollArea borderWidth="1px" borderColor="border.subtle" borderRadius="lg">
            <TableRoot size="sm">
              <TableHeader>
                <TableRow>
                  <TableColumnHeader>Email</TableColumnHeader>
                  <TableColumnHeader>Role</TableColumnHeader>
                  <TableColumnHeader>Expires</TableColumnHeader>
                </TableRow>
              </TableHeader>
              <TableBody>
                {invites
                  .filter((i) => !i.accepted_at)
                  .map((i) => (
                    <TableRow key={i.id}>
                      <TableCell>{i.email}</TableCell>
                      <TableCell>{i.role}</TableCell>
                      <TableCell>{formatDate(i.expires_at, timezone)}</TableCell>
                    </TableRow>
                  ))}
              </TableBody>
            </TableRoot>
          </TableScrollArea>
        </Box>
      ) : null}
    </Box>
  );
};

export default SettingsUsers;
