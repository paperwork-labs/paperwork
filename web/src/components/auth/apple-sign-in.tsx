"use client";

import { useCallback } from "react";
import Script from "next/script";
import { toast } from "sonner";
import { useAppleAuth } from "@/hooks/use-auth";
import { clientConfig } from "@/lib/client-config";

const APPLE_CLIENT_ID = clientConfig.appleClientId;
const APPLE_REDIRECT_URI =
  clientConfig.appleRedirectUri ||
  (typeof window !== "undefined" ? window.location.origin : "");

declare global {
  interface Window {
    AppleID?: {
      auth: {
        init: (config: Record<string, unknown>) => void;
        signIn: () => Promise<{
          authorization: { id_token: string; code: string };
          user?: { name?: { firstName?: string; lastName?: string }; email?: string };
        }>;
      };
    };
  }
}

export function AppleSignIn() {
  const appleAuth = useAppleAuth();

  const handleClick = useCallback(async () => {
    if (!APPLE_CLIENT_ID) {
      toast.info("Apple Sign In is not configured in this environment.");
      return;
    }

    if (!window.AppleID) {
      toast.error("Apple Sign In failed to load. Please try again.");
      return;
    }

    try {
      window.AppleID.auth.init({
        clientId: APPLE_CLIENT_ID,
        scope: "name email",
        redirectURI: APPLE_REDIRECT_URI,
        usePopup: true,
      });

      const response = await window.AppleID.auth.signIn();

      appleAuth.mutate({
        idToken: response.authorization.id_token,
        user: response.user,
      });
    } catch (error) {
      if (error && typeof error === "object" && "error" in error) {
        const appleError = error as { error: string };
        if (appleError.error === "popup_closed_by_user") return;
      }
      toast.error("Apple Sign In failed. Please try again.");
    }
  }, [appleAuth]);

  return (
    <>
      {APPLE_CLIENT_ID && (
        <Script
          src="https://appleid.cdn-apple.com/appleauth/static/jsapi/appleid/1/en_US/appleid.auth.js"
          strategy="afterInteractive"
        />
      )}
      <button
        type="button"
        onClick={handleClick}
        disabled={appleAuth.isPending}
        className="flex h-10 w-full items-center justify-center gap-2 rounded-md border border-border bg-foreground px-4 text-sm font-medium text-background transition hover:opacity-90"
      >
        <AppleIcon />
        Continue with Apple
      </button>
    </>
  );
}

function AppleIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
      <path d="M17.05 20.28c-.98.95-2.05.88-3.08.4-1.09-.5-2.08-.48-3.24 0-1.44.62-2.2.44-3.06-.4C2.79 15.25 3.51 7.59 9.05 7.31c1.35.07 2.29.74 3.08.8 1.18-.24 2.31-.93 3.57-.84 1.51.12 2.65.72 3.4 1.8-3.12 1.87-2.38 5.98.48 7.13-.57 1.5-1.31 2.99-2.54 4.09zM12.03 7.25c-.15-2.23 1.66-4.07 3.74-4.25.29 2.58-2.34 4.5-3.74 4.25z" />
    </svg>
  );
}
