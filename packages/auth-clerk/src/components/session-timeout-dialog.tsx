"use client";

import { Button, Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@paperwork-labs/ui";
import { useIdleTimeout } from "../hooks/use-idle-timeout";

interface SessionTimeoutDialogProps {
  isAuthenticated: boolean;
  onLogout: () => void;
  timeoutMs?: number;
  warningMs?: number;
}

export function SessionTimeoutDialog({
  isAuthenticated,
  onLogout,
  timeoutMs = 30 * 60 * 1000,
  warningMs = 2 * 60 * 1000,
}: SessionTimeoutDialogProps) {
  const { showWarning, extend } = useIdleTimeout({
    timeoutMs,
    warningMs,
    onTimeout: onLogout,
    enabled: isAuthenticated,
  });

  return (
    <Dialog open={showWarning} onOpenChange={(open) => !open && extend()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Still there?</DialogTitle>
          <DialogDescription>
            You&apos;ve been inactive for a while. For your security, we&apos;ll sign you
            out soon unless you continue.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter className="flex gap-2 sm:gap-0">
          <Button variant="outline" onClick={onLogout}>
            Sign out
          </Button>
          <Button
            onClick={extend}
            className="bg-gradient-to-r from-violet-600 to-purple-600 text-white border-0"
          >
            Keep me signed in
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
