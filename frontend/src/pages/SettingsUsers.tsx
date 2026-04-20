import React, { useState } from 'react';
import { Copy, Loader2, Trash2 } from 'lucide-react';
import toast from 'react-hot-toast';
import { adminUsersApi, approveUser, deleteUser } from '../services/api';
import { formatDate } from '../utils/format';
import { useUserPreferences } from '../hooks/useUserPreferences';
import { useAuth } from '../context/AuthContext';
import { PageHeader } from '../components/ui/Page';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import {
  ResponsiveModal as Dialog,
  ResponsiveModalContent as DialogContent,
  ResponsiveModalFooter as DialogFooter,
  ResponsiveModalHeader as DialogHeader,
  ResponsiveModalTitle as DialogTitle,
} from '@/components/ui/responsive-modal';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';

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
  token: string | null;
  expires_at: string;
  accepted_at?: string | null;
  created_at?: string;
};

const ROLE_OPTIONS = [
  { label: 'Viewer', value: 'viewer' },
  { label: 'Analyst', value: 'analyst' },
  { label: 'Owner', value: 'owner' },
];

const selectClass =
  'h-8 rounded-md border border-input bg-background px-2 text-xs text-foreground shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 dark:bg-input/30';

const tableWrap = 'overflow-x-auto rounded-xl border border-border';

const SettingsUsers: React.FC = () => {
  const { timezone } = useUserPreferences();
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState<UserRow[]>([]);
  const [invites, setInvites] = useState<InviteRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState('viewer');
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
    } catch (e: unknown) {
      const err = e as { message?: string };
      toast.error(err?.message || 'Failed to load users');
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
      const res: { token?: string } = await adminUsersApi.invite({
        email: inviteEmail.trim(),
        role: inviteRole,
      });
      const token = res?.token;
      const url = token ? `${window.location.origin}/invite/${token}` : null;
      setInviteUrl(url);
      setInviteEmail('');
      await load();
      toast.success('Invite created');
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to create invite');
    }
  };

  const updateUser = async (userId: number, payload: { role?: string; is_active?: boolean }) => {
    try {
      await adminUsersApi.update(userId, payload);
      await load();
      toast.success('User updated');
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to update user');
    }
  };

  const approvePendingUser = async (userId: number) => {
    setApprovingUserId(userId);
    try {
      await approveUser(userId);
      await load();
      toast.success('User approved');
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to approve user');
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
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to delete user');
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
    <div className="mx-auto w-full max-w-[960px]">
      <PageHeader title="Users" subtitle="Invite users via email and manage roles." />

      <div className="mt-6 flex flex-col gap-6">
        <Card>
          <CardContent className="space-y-3 pt-6">
            <h2 className="text-sm font-semibold text-foreground">Invite New User</h2>
            <div className="flex flex-wrap items-center gap-3">
              <Input
                placeholder="email@example.com"
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                className="max-w-[280px]"
              />
              <select
                value={inviteRole}
                onChange={(e) => setInviteRole(e.target.value)}
                className={cn(selectClass, 'w-[160px]')}
                aria-label="Role"
              >
                {ROLE_OPTIONS.map((r) => (
                  <option key={r.value} value={r.value}>
                    {r.label}
                  </option>
                ))}
              </select>
              <Button type="button" size="sm" disabled={loading} onClick={() => void inviteUser()}>
                {loading ? <Loader2 className="mr-1 size-3.5 animate-spin" aria-hidden /> : null}
                Create Invite
              </Button>
              {inviteUrl ? (
                <Button type="button" size="sm" variant="outline" onClick={() => void copyInvite()}>
                  Copy Invite Link
                </Button>
              ) : null}
            </div>
            {inviteUrl ? <p className="text-xs text-muted-foreground">{inviteUrl}</p> : null}
          </CardContent>
        </Card>

        <div>
          <h2 className="mb-2 text-sm font-semibold text-foreground">All Users</h2>
          <div className={tableWrap}>
            <table className="w-full min-w-[640px] border-collapse text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/40 text-left text-xs font-medium text-muted-foreground">
                  <th className="px-3 py-2">Name</th>
                  <th className="px-3 py-2">Email</th>
                  <th className="px-3 py-2">Role</th>
                  <th className="px-3 py-2">Approval</th>
                  <th className="px-3 py-2">Status</th>
                  <th className="px-3 py-2">Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => {
                  const isPendingApproval = u.is_approved === false;
                  return (
                    <tr
                      key={u.id}
                      className={cn(
                        'border-b border-border last:border-0',
                        isPendingApproval && 'border-l-[3px] border-l-amber-500 bg-amber-500/5',
                      )}
                    >
                      <td className="px-3 py-2">
                        <span className="font-medium text-foreground">{u.full_name || u.email}</span>
                      </td>
                      <td className="px-3 py-2 text-muted-foreground">{u.email}</td>
                      <td className="px-3 py-2">
                        <select
                          value={u.role}
                          onChange={(e) => void updateUser(u.id, { role: e.target.value })}
                          className={selectClass}
                          aria-label="Role"
                        >
                          {ROLE_OPTIONS.map((r) => (
                            <option key={r.value} value={r.value}>
                              {r.label}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="px-3 py-2">
                        <Badge
                          variant="outline"
                          className={cn(
                            'font-normal',
                            isPendingApproval
                              ? 'border-amber-500/40 bg-amber-500/10 text-amber-900 dark:text-amber-200'
                              : 'border-emerald-500/40 bg-emerald-500/10 text-emerald-800 dark:text-emerald-200',
                          )}
                        >
                          {isPendingApproval ? 'Pending' : 'Approved'}
                        </Badge>
                      </td>
                      <td className="px-3 py-2">
                        <Badge
                          variant="outline"
                          className={cn(
                            'font-normal',
                            u.is_active
                              ? 'border-emerald-500/40 text-emerald-800 dark:text-emerald-200'
                              : 'border-destructive/40 text-destructive',
                          )}
                        >
                          {u.is_active ? 'Active' : 'Disabled'}
                        </Badge>
                      </td>
                      <td className="px-3 py-2">
                        <div className="flex flex-wrap items-center gap-2">
                          {isPendingApproval ? (
                            <Button
                              type="button"
                              size="xs"
                              className="bg-emerald-600 text-white hover:bg-emerald-600/90"
                              disabled={approvingUserId === u.id}
                              onClick={() => void approvePendingUser(u.id)}
                            >
                              {approvingUserId === u.id ? (
                                <Loader2 className="size-3 animate-spin" aria-hidden />
                              ) : null}
                              Approve
                            </Button>
                          ) : null}
                          <Button
                            type="button"
                            size="xs"
                            variant="outline"
                            onClick={() => void updateUser(u.id, { is_active: !u.is_active })}
                          >
                            {u.is_active ? 'Deactivate' : 'Activate'}
                          </Button>
                          <Button
                            type="button"
                            size="icon-xs"
                            variant="ghost"
                            className="text-destructive hover:bg-destructive/10 hover:text-destructive"
                            aria-label={`Delete ${u.full_name || u.email}`}
                            title={currentUser?.id === u.id ? 'You cannot delete your own account' : undefined}
                            disabled={currentUser?.id === u.id}
                            onClick={() => setDeleteTarget(u)}
                          >
                            <Trash2 className="size-3.5" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {invites.filter((i) => !i.accepted_at).length > 0 && (
          <div>
            <h2 className="mb-2 text-sm font-semibold text-foreground">Pending Invites</h2>
            <div className={tableWrap}>
              <table className="w-full border-collapse text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted/40 text-left text-xs font-medium text-muted-foreground">
                    <th className="px-3 py-2">Email</th>
                    <th className="px-3 py-2">Role</th>
                    <th className="px-3 py-2">Expires</th>
                    <th className="px-3 py-2">Invite Link</th>
                  </tr>
                </thead>
                <tbody>
                  {invites
                    .filter((i) => !i.accepted_at)
                    .map((i) => {
                      const link = i.token ? `${window.location.origin}/invite/${i.token}` : '';
                      const isExpired = new Date(i.expires_at) < new Date();
                      return (
                        <tr key={i.id} className={cn('border-b border-border last:border-0', isExpired && 'opacity-50')}>
                          <td className="px-3 py-2">{i.email}</td>
                          <td className="px-3 py-2 text-muted-foreground">{i.role}</td>
                          <td className="px-3 py-2 text-muted-foreground">
                            {formatDate(i.expires_at, timezone)}
                            {isExpired ? <span className="ml-1 text-destructive">(expired)</span> : null}
                          </td>
                          <td className="px-3 py-2">
                            {link && !isExpired ? (
                              <Button
                                type="button"
                                size="xs"
                                variant="outline"
                                onClick={async () => {
                                  try {
                                    await navigator.clipboard.writeText(link);
                                    toast.success('Invite link copied');
                                  } catch {
                                    toast.error('Failed to copy');
                                  }
                                }}
                              >
                                <Copy className="mr-1 size-3" aria-hidden />
                                Copy Link
                              </Button>
                            ) : null}
                          </td>
                        </tr>
                      );
                    })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      <Dialog open={Boolean(deleteTarget)} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <DialogContent showCloseButton className="max-w-[400px]">
          <DialogHeader>
            <DialogTitle>Delete User</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-foreground">
            Are you sure you want to delete{' '}
            <strong>{deleteTarget?.full_name || deleteTarget?.email}</strong>? This action cannot be undone.
          </p>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setDeleteTarget(null)}>
              Cancel
            </Button>
            <Button type="button" variant="destructive" disabled={deleting} onClick={() => void confirmDeleteUser()}>
              {deleting ? <Loader2 className="mr-1 size-3.5 animate-spin" aria-hidden /> : null}
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default SettingsUsers;
