import React from 'react';
import { Eye, EyeOff, Loader2 } from 'lucide-react';
import { PageHeader } from '../components/ui/Page';
import hotToast from 'react-hot-toast';
import { authApi, handleApiError } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';

const SettingsProfile: React.FC = () => {
  const { user, refreshMe } = useAuth();
  const [fullName, setFullName] = React.useState(user?.full_name || '');
  const [email, setEmail] = React.useState(user?.email || '');
  const [currentPasswordForEmail, setCurrentPasswordForEmail] = React.useState('');
  const [savingProfile, setSavingProfile] = React.useState(false);

  const [currentPassword, setCurrentPassword] = React.useState('');
  const [newPassword, setNewPassword] = React.useState('');
  const [confirmPassword, setConfirmPassword] = React.useState('');
  const [savingPassword, setSavingPassword] = React.useState(false);
  const [showPw, setShowPw] = React.useState(false);
  const [showNewPw, setShowNewPw] = React.useState(false);

  React.useLayoutEffect(() => {
    setFullName(user?.full_name ?? '');
    setEmail(user?.email ?? '');
  }, [user?.full_name, user?.email]);

  const saveProfile = async () => {
    try {
      setSavingProfile(true);
      const payload: Record<string, unknown> = {};
      if (fullName !== (user?.full_name || '')) payload.full_name = fullName;
      if (email !== (user?.email || '')) payload.email = email;
      if (payload.email && currentPasswordForEmail) payload.current_password = currentPasswordForEmail;
      if (Object.keys(payload).length === 0) {
        hotToast('No changes to save');
        return;
      }
      await authApi.updateMe(payload);
      await refreshMe();
      setCurrentPasswordForEmail('');
      hotToast.success('Profile updated');
    } catch (e) {
      hotToast.error(handleApiError(e));
    } finally {
      setSavingProfile(false);
    }
  };

  const savePassword = async () => {
    try {
      if (!newPassword || newPassword.length < 8) {
        hotToast.error('New password must be at least 8 characters');
        return;
      }
      if (newPassword !== confirmPassword) {
        hotToast.error('New passwords do not match');
        return;
      }
      setSavingPassword(true);
      await authApi.changePassword({
        current_password: (user?.has_password ? currentPassword : undefined),
        new_password: newPassword,
      });
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      hotToast.success(user?.has_password ? 'Password updated' : 'Password set');
    } catch (e) {
      hotToast.error(handleApiError(e));
    } finally {
      setSavingPassword(false);
    }
  };

  const fieldWrap = 'min-w-0 flex-1 basis-full md:basis-0';

  return (
    <TooltipProvider delayDuration={200}>
    <div className="w-full">
      <div className="mx-auto w-full max-w-[960px]">
        <PageHeader title="Profile" subtitle="Update your personal info and security settings." />
        <div className="flex flex-col gap-4">
          <Card>
            <CardContent className="space-y-4 pt-6">
              <h2 className="font-heading font-semibold text-foreground">Account</h2>
              <div className="flex flex-wrap gap-4">
                <div className={cn(fieldWrap, 'md:max-w-[280px]')}>
                  <Label htmlFor="profile-username" className="mb-1.5 block text-muted-foreground">
                    Username
                  </Label>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <span
                        aria-label="Username"
                        className={cn(
                          'block w-full rounded-md outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background',
                        )}
                        data-testid="profile-username-focus-target"
                        role="group"
                        tabIndex={0}
                      >
                        <Input id="profile-username" value={user?.username || ''} disabled className="w-full" />
                      </span>
                    </TooltipTrigger>
                    <TooltipContent side="right" className="max-w-[260px] text-xs">
                      Usernames are set at signup. Contact support if you need to change yours.
                    </TooltipContent>
                  </Tooltip>
                </div>
                <div className={cn(fieldWrap, 'md:min-w-[280px]')}>
                  <Label htmlFor="profile-fullname" className="mb-1.5 block text-muted-foreground">
                    Full name
                  </Label>
                  <Input
                    id="profile-fullname"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="Your name"
                  />
                </div>
              </div>

              <div className="flex flex-wrap gap-4">
                <div className={cn(fieldWrap, 'md:min-w-[320px]')}>
                  <Label htmlFor="profile-email" className="mb-1.5 block text-muted-foreground">
                    Email
                  </Label>
                  <Input
                    id="profile-email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="name@domain.com"
                  />
                </div>
                {user?.has_password && email !== (user?.email || '') ? (
                  <div className={cn(fieldWrap, 'md:min-w-[320px]')}>
                    <Label htmlFor="profile-email-pw" className="mb-1.5 block text-muted-foreground">
                      Current password
                    </Label>
                    <div className="relative">
                      <Input
                        id="profile-email-pw"
                        aria-label="Current password for email change"
                        type={showPw ? 'text' : 'password'}
                        value={currentPasswordForEmail}
                        onChange={(e) => setCurrentPasswordForEmail(e.target.value)}
                        placeholder="Email change password"
                        className="pr-10"
                      />
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon-xs"
                        className="absolute top-1/2 right-1 -translate-y-1/2"
                        aria-label={showPw ? 'Hide password' : 'Show password'}
                        onClick={() => setShowPw(!showPw)}
                      >
                        {showPw ? <EyeOff className="size-4" aria-hidden /> : <Eye className="size-4" aria-hidden />}
                      </Button>
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">
                      Changing email requires your current password.
                    </p>
                  </div>
                ) : null}
              </div>

              <div className="flex justify-end">
                <Button type="button" disabled={savingProfile} onClick={() => void saveProfile()}>
                  {savingProfile ? <Loader2 className="mr-1 size-3.5 animate-spin" aria-hidden /> : null}
                  Save changes
                </Button>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="space-y-4 pt-6">
              <h2 className="font-heading font-semibold text-foreground">Password</h2>
              <p className="text-sm text-muted-foreground">
                {user?.has_password
                  ? 'Change your password.'
                  : 'No password is set for this account yet. Set one to enable password-based login.'}
              </p>
              <div className="flex flex-wrap gap-4">
                {user?.has_password ? (
                  <div className={cn(fieldWrap, 'md:min-w-[320px]')}>
                    <Label htmlFor="profile-current-pw" className="mb-1.5 block text-muted-foreground">
                      Current password
                    </Label>
                    <Input
                      id="profile-current-pw"
                      aria-label="Current password for password change"
                      type="password"
                      value={currentPassword}
                      onChange={(e) => setCurrentPassword(e.target.value)}
                      placeholder="Current password"
                    />
                  </div>
                ) : null}
                <div className={cn(fieldWrap, 'md:min-w-[320px]')}>
                  <Label htmlFor="profile-new-pw" className="mb-1.5 block text-muted-foreground">
                    New password
                  </Label>
                  <div className="relative">
                    <Input
                      id="profile-new-pw"
                      type={showNewPw ? 'text' : 'password'}
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                      placeholder="At least 8 characters"
                      className="pr-10"
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-xs"
                      className="absolute top-1/2 right-1 -translate-y-1/2"
                      aria-label={showNewPw ? 'Hide password' : 'Show password'}
                      onClick={() => setShowNewPw(!showNewPw)}
                    >
                      {showNewPw ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                    </Button>
                  </div>
                </div>
                <div className={cn(fieldWrap, 'md:min-w-[320px]')}>
                  <Label htmlFor="profile-confirm-pw" className="mb-1.5 block text-muted-foreground">
                    Confirm new password
                  </Label>
                  <Input
                    id="profile-confirm-pw"
                    type={showNewPw ? 'text' : 'password'}
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="Repeat new password"
                  />
                </div>
              </div>

              <div className="border-t border-border pt-4">
                <div className="flex justify-end">
                  <Button type="button" disabled={savingPassword} onClick={() => void savePassword()}>
                    {savingPassword ? <Loader2 className="mr-1 size-3.5 animate-spin" aria-hidden /> : null}
                    {user?.has_password ? 'Change password' : 'Set password'}
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
    </TooltipProvider>
  );
};

export default SettingsProfile;
