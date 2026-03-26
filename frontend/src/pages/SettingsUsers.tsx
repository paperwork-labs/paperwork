import React, { useState } from 'react';
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
  DialogRoot,
  DialogBackdrop,
  DialogPositioner,
  DialogContent,
  DialogTitle,
  DialogBody,
  DialogFooter,
  IconButton,
} from '@chakra-ui/react';
import { FiTrash2 } from 'react-icons/fi';
import toast from 'react-hot-toast';
import { adminUsersApi, approveUser, deleteUser } from '../services/api';
import { formatDate } from '../utils/format';
import { useUserPreferences } from '../hooks/useUserPreferences';
import { useAuth } from '../context/AuthContext';
import { PageHeader } from '../components/ui/Page';
import AppCard from '../components/ui/AppCard';

type UserRow = {
  id: number;
  username: string;
  email: string;
  role: string;
  is_active: boolean;
  is_approved?: boolean;
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

const SELECT_STYLE: React.CSSProperties = {
  width: 160,
  fontSize: 12,
  padding: '6px 10px',
  borderRadius: 10,
  border: '1px solid var(--chakra-colors-border-subtle)',
  background: 'var(--chakra-colors-bg-input)',
  color: 'var(--chakra-colors-fg-default)',
};

const SettingsUsers: React.FC = () => {
  const { timezone } = useUserPreferences();
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState<UserRow[]>([]);
  const [invites, setInvites] = useState<InviteRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState('readonly');
  const [inviteUrl, setInviteUrl] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<UserRow | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [approvingUserId, setApprovingUserId] = useState<number | null>(null);

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

  const approvePendingUser = async (userId: number) => {
    setApprovingUserId(userId);
    try {
      await approveUser(userId);
      await load();
      toast.success('User approved');
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || e?.message || 'Failed to approve user');
    } finally {
      setApprovingUserId(null);
    }
  };

  const confirmDeleteUser = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await deleteUser(deleteTarget.id);
      toast.success(`User ${deleteTarget.full_name || deleteTarget.email} deleted`);
      setDeleteTarget(null);
      await load();
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || e?.message || 'Failed to delete user');
    } finally {
      setDeleting(false);
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
    <Box w="full" maxW="960px" mx="auto">
      <PageHeader
        title="Users"
        subtitle="Invite users via email and manage roles."
      />

      <VStack align="stretch" gap={6} mt={6}>
        <AppCard>
          <Text fontSize="sm" fontWeight="semibold" mb={3}>Invite New User</Text>
          <HStack gap={3} flexWrap="wrap">
            <Input
              placeholder="email@example.com"
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
              maxW="280px"
              size="sm"
            />
            <select
              value={inviteRole}
              onChange={(e) => setInviteRole(e.target.value)}
              style={SELECT_STYLE}
              aria-label="Role"
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
        </AppCard>

        <Box>
          <Text fontSize="sm" fontWeight="semibold" mb={2}>All Users</Text>
          <TableScrollArea borderWidth="1px" borderColor="border.subtle" borderRadius="lg">
            <TableRoot size="sm">
              <TableHeader>
                <TableRow>
                  <TableColumnHeader>Name</TableColumnHeader>
                  <TableColumnHeader>Email</TableColumnHeader>
                  <TableColumnHeader>Role</TableColumnHeader>
                  <TableColumnHeader>Approval</TableColumnHeader>
                  <TableColumnHeader>Status</TableColumnHeader>
                  <TableColumnHeader>Actions</TableColumnHeader>
                </TableRow>
              </TableHeader>
              <TableBody>
                {users.map((u) => {
                  const isPendingApproval = u.is_approved === false;
                  return (
                  <TableRow
                    key={u.id}
                    borderLeftWidth={isPendingApproval ? '3px' : undefined}
                    borderLeftColor={isPendingApproval ? 'chart.warning' : undefined}
                    bg={isPendingApproval ? { _light: 'amber.50', _dark: 'whiteAlpha.50' } : undefined}
                  >
                    <TableCell>
                      <Text fontSize="sm" fontWeight="medium">{u.full_name || u.email}</Text>
                    </TableCell>
                    <TableCell>{u.email}</TableCell>
                    <TableCell>
                      <select
                        value={u.role}
                        onChange={(e) => updateUser(u.id, { role: e.target.value })}
                        style={SELECT_STYLE}
                        aria-label="Role"
                      >
                        {ROLE_OPTIONS.map((r) => (
                          <option key={r.value} value={r.value}>
                            {r.label}
                          </option>
                        ))}
                      </select>
                    </TableCell>
                    <TableCell>
                      <Badge
                        colorPalette={isPendingApproval ? 'yellow' : 'green'}
                        variant="subtle"
                      >
                        {isPendingApproval ? 'Pending' : 'Approved'}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge colorPalette={u.is_active ? 'green' : 'red'} variant="subtle">
                        {u.is_active ? 'Active' : 'Disabled'}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <HStack gap={2} flexWrap="wrap">
                        {isPendingApproval ? (
                          <Button
                            size="xs"
                            colorPalette="green"
                            loading={approvingUserId === u.id}
                            onClick={() => void approvePendingUser(u.id)}
                          >
                            Approve
                          </Button>
                        ) : null}
                        <Button
                          size="xs"
                          variant="outline"
                          onClick={() => updateUser(u.id, { is_active: !u.is_active })}
                        >
                          {u.is_active ? 'Deactivate' : 'Activate'}
                        </Button>
                        <IconButton
                          size="xs"
                          variant="ghost"
                          colorPalette="red"
                          aria-label={`Delete ${u.full_name || u.email}`}
                          title={currentUser?.id === u.id ? 'You cannot delete your own account' : undefined}
                          disabled={currentUser?.id === u.id}
                          onClick={() => setDeleteTarget(u)}
                        >
                          <FiTrash2 size={14} />
                        </IconButton>
                      </HStack>
                    </TableCell>
                  </TableRow>
                  );
                })}
              </TableBody>
            </TableRoot>
          </TableScrollArea>
        </Box>

        {invites.filter((i) => !i.accepted_at).length > 0 && (
          <Box>
            <Text fontSize="sm" fontWeight="semibold" mb={2}>Pending Invites</Text>
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
        )}
      </VStack>

      {/* Delete User Confirmation Dialog */}
      <DialogRoot open={Boolean(deleteTarget)} onOpenChange={(d) => { if (!d.open) setDeleteTarget(null); }}>
        <DialogBackdrop />
        <DialogPositioner>
          <DialogContent maxW="400px">
            <DialogTitle>Delete User</DialogTitle>
            <DialogBody>
              <Text fontSize="sm">
                Are you sure you want to delete <strong>{deleteTarget?.full_name || deleteTarget?.email}</strong>? This action cannot be undone.
              </Text>
            </DialogBody>
            <DialogFooter>
              <HStack gap={2}>
                <Button variant="ghost" onClick={() => setDeleteTarget(null)}>
                  Cancel
                </Button>
                <Button colorPalette="red" loading={deleting} onClick={confirmDeleteUser}>
                  Delete
                </Button>
              </HStack>
            </DialogFooter>
          </DialogContent>
        </DialogPositioner>
      </DialogRoot>
    </Box>
  );
};

export default SettingsUsers;
