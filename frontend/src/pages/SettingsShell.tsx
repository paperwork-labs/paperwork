import React from 'react';
import { Link, NavLink, Outlet } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { isPlatformAdminRole } from '../utils/userRole';
import { Bell, Cpu, KeyRound, Sliders, User, Shield, Activity, ClipboardList, Lock, Database } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';

const MenuLink: React.FC<{ to: string; children: React.ReactNode }> = ({ to, children }) => (
  <NavLink to={to} className="block no-underline">
    {({ isActive }) => (
      <Button
        type="button"
        variant="ghost"
        className={cn(
          'h-9 w-full justify-start rounded-md border-l-2 border-transparent px-3 font-medium transition-colors',
          isActive
            ? 'border-primary bg-muted text-foreground'
            : 'text-muted-foreground hover:bg-muted/80 hover:text-foreground',
        )}
      >
        {children}
      </Button>
    )}
  </NavLink>
);

const SettingsShell: React.FC = () => {
  const { user } = useAuth();
  const [isDesktop, setIsDesktop] = React.useState(
    typeof window !== 'undefined' ? window.matchMedia('(min-width: 48em)').matches : true,
  );

  React.useEffect(() => {
    const mq = window.matchMedia('(min-width: 48em)');
    const handler = () => setIsDesktop(mq.matches);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);

  const iconNav = (to: string, label: string, icon: React.ReactNode) => (
    <NavLink to={to} className="no-underline">
      {({ isActive }) => (
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              type="button"
              size="icon"
              variant={isActive ? 'default' : 'ghost'}
              className={cn(isActive && 'bg-primary text-primary-foreground hover:bg-primary/90 hover:text-primary-foreground')}
              aria-label={label}
            >
              {icon}
            </Button>
          </TooltipTrigger>
          <TooltipContent side="right" className="text-background">
            {label}
          </TooltipContent>
        </Tooltip>
      )}
    </NavLink>
  );

  return (
    <TooltipProvider delayDuration={200}>
      <div className="flex min-w-0 gap-2 overflow-x-hidden p-0">
        {isDesktop ? (
          <nav className="w-40 shrink-0" aria-label="Settings">
            <div className="flex flex-col gap-1">
              <p className="px-2 text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">
                Account
              </p>
              <MenuLink to="/settings/profile">Profile</MenuLink>
              <MenuLink to="/settings/preferences">Preferences</MenuLink>
              <MenuLink to="/settings/connections">Connections</MenuLink>
              <MenuLink to="/settings/historical-import">Historical import</MenuLink>
              <MenuLink to="/settings/mcp">MCP Tokens</MenuLink>
              <MenuLink to="/settings/notifications">Notifications</MenuLink>
              <MenuLink to="/settings/data-privacy">Data privacy</MenuLink>
              {isPlatformAdminRole(user?.role) && (
                <>
                  <p className="mt-4 px-2 text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">
                    Admin
                  </p>
                  <MenuLink to="/settings/admin/system">System Status</MenuLink>
                  <MenuLink to="/settings/admin/users">Users</MenuLink>
                  <MenuLink to="/settings/admin/agent">Agent</MenuLink>
                  <Button
                    asChild
                    type="button"
                    variant="ghost"
                    className={cn(
                      'h-9 w-full justify-start rounded-md border-l-2 border-transparent px-3 font-medium transition-colors',
                      'text-muted-foreground hover:bg-muted/80 hover:text-foreground',
                    )}
                  >
                    <Link to="/admin/picks" className="inline-flex w-full items-center justify-between gap-1 no-underline">
                      <span>Picks validator</span>
                      <span className="text-xs text-muted-foreground" aria-hidden>
                        ↗
                      </span>
                    </Link>
                  </Button>
                </>
              )}
            </div>
          </nav>
        ) : (
          <nav className="flex w-14 shrink-0 flex-col gap-2" aria-label="Settings">
            {iconNav('/settings/profile', 'Profile', <User className="size-4" />)}
            {iconNav('/settings/preferences', 'Preferences', <Sliders className="size-4" />)}
            {iconNav('/settings/connections', 'Connections', <Shield className="size-4" />)}
            {iconNav('/settings/historical-import', 'Historical import', <Database className="size-4" />)}
            {iconNav('/settings/mcp', 'MCP Tokens', <KeyRound className="size-4" />)}
            {iconNav('/settings/notifications', 'Notifications', <Bell className="size-4" />)}
            {iconNav('/settings/data-privacy', 'Data privacy', <Lock className="size-4" />)}
            {isPlatformAdminRole(user?.role) ? (
              <>
                {iconNav('/settings/admin/system', 'System Status', <Activity className="size-4" />)}
                {iconNav('/settings/admin/users', 'Users', <User className="size-4" />)}
                {iconNav('/settings/admin/agent', 'Agent', <Cpu className="size-4" />)}
                {iconNav('/admin/picks', 'Picks validator ↗', <ClipboardList className="size-4" />)}
              </>
            ) : null}
          </nav>
        )}
        <div className="min-w-0 flex-1 overflow-x-hidden">
          <Outlet />
        </div>
      </div>
    </TooltipProvider>
  );
};

export default SettingsShell;
