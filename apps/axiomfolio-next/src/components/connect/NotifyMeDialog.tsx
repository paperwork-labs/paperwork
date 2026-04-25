/**
 * NotifyMeDialog — captures an email for a coming-soon broker.
 *
 * Backend persistence is currently a logged-only stub (see
 * `backend/api/routes/notify.py` docstring). The dialog is honest about
 * this: it shows a confirming toast on success but does not pretend the
 * subscription is durable. When persistence ships in a follow-up PR
 * the UI contract here doesn't have to change.
 */
import * as React from "react";
import toast from "react-hot-toast";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { connectHubApi, handleApiError } from "@/services/api";

interface NotifyMeDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  brokerSlug: string;
  brokerName: string;
  defaultEmail?: string;
}

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function NotifyMeDialog({
  open,
  onOpenChange,
  brokerSlug,
  brokerName,
  defaultEmail = "",
}: NotifyMeDialogProps) {
  const [email, setEmail] = React.useState(defaultEmail);
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (open) {
      setEmail(defaultEmail);
      setError(null);
    }
  }, [open, defaultEmail]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    const trimmed = email.trim();
    if (!EMAIL_RE.test(trimmed)) {
      setError("Enter a valid email address.");
      return;
    }
    setSubmitting(true);
    try {
      await connectHubApi.notifyBrokerLaunch({
        broker_slug: brokerSlug,
        email: trimmed,
      });
      toast.success(`We'll email you when ${brokerName} is live.`);
      onOpenChange(false);
    } catch (err) {
      setError(handleApiError(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Get notified when {brokerName} is live</DialogTitle>
          <DialogDescription>
            We&apos;ll send a single email when the {brokerName} integration ships
            in v1.1. No marketing, no newsletter — just the launch ping.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="notify-email">Email</Label>
            <Input
              id="notify-email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              aria-invalid={error ? true : undefined}
              aria-describedby={error ? "notify-email-error" : undefined}
              placeholder="you@example.com"
            />
            {error ? (
              <p
                id="notify-email-error"
                role="alert"
                className="text-xs text-destructive"
              >
                {error}
              </p>
            ) : null}
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="ghost"
              onClick={() => onOpenChange(false)}
              disabled={submitting}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting ? "Saving…" : "Notify me"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default NotifyMeDialog;
