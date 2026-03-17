"use client";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  Button,
} from "@venture/ui";
import { useLogout } from "@/hooks/use-auth";
import { useIdleTimeout } from "@/hooks/use-idle-timeout";
import { useAuthStore } from "@/stores/auth-store";

const TIMEOUT_MS = 30 * 60 * 1000; // 30 minutes
const WARNING_MS = 2 * 60 * 1000; // show warning 2 min before logout

export function SessionTimeoutDialog() {
  const { isAuthenticated } = useAuthStore();
  const logout = useLogout();

  const { showWarning, extend } = useIdleTimeout({
    timeoutMs: TIMEOUT_MS,
    warningMs: WARNING_MS,
    onTimeout: () => logout.mutate(),
    enabled: isAuthenticated,
  });

  return (
    <Dialog open={showWarning} onOpenChange={(open) => !open && extend()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Still there?</DialogTitle>
          <DialogDescription>
            You&apos;ve been inactive for a while. For your security,
            we&apos;ll sign you out soon unless you continue.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter className="flex gap-2 sm:gap-0">
          <Button variant="outline" onClick={() => logout.mutate()}>
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
