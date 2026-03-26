import React from 'react';
import { useNavigate } from 'react-router-dom';
import { PageHeader } from '../components/ui/Page';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';

const SettingsNotifications: React.FC = () => {
  const navigate = useNavigate();
  const [emailDigest, setEmailDigest] = React.useState(false);
  const [tradeAlerts, setTradeAlerts] = React.useState(true);

  return (
    <div className="mx-auto w-full max-w-[960px]">
      <PageHeader title="Notifications" subtitle="Notification preferences and delivery channels." />
      <Card className="mt-6">
        <CardContent className="space-y-6 pt-6">
          <p className="text-sm text-muted-foreground">
            Choose what you want to hear about. The notifications center still lists live activity and delivery
            history.
          </p>
          <div className="flex items-center justify-between gap-4 rounded-lg border border-border bg-muted/30 px-4 py-3">
            <div className="space-y-0.5">
              <Label htmlFor="notif-digest" className="text-foreground">
                Email digest
              </Label>
              <p className="text-xs text-muted-foreground">Periodic summary of portfolio and market alerts.</p>
            </div>
            <Switch
              id="notif-digest"
              checked={emailDigest}
              onCheckedChange={setEmailDigest}
              aria-label="Email digest"
            />
          </div>
          <div className="flex items-center justify-between gap-4 rounded-lg border border-border bg-muted/30 px-4 py-3">
            <div className="space-y-0.5">
              <Label htmlFor="notif-trades" className="text-foreground">
                Trade execution alerts
              </Label>
              <p className="text-xs text-muted-foreground">In-app toasts when orders fill or reject.</p>
            </div>
            <Switch
              id="notif-trades"
              checked={tradeAlerts}
              onCheckedChange={setTradeAlerts}
              aria-label="Trade execution alerts"
            />
          </div>
          <p className="text-xs text-muted-foreground">
            Preferences here are UI placeholders until wired to the notifications API. Open the center for full
            history and actions.
          </p>
          <Button type="button" size="sm" variant="outline" onClick={() => navigate('/notifications')}>
            Open Notifications Center
          </Button>
        </CardContent>
      </Card>
    </div>
  );
};

export default SettingsNotifications;
