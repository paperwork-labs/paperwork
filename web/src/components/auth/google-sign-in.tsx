"use client";

import { useEffect, useRef, useCallback } from "react";
import Script from "next/script";
import { toast } from "sonner";
import { useGoogleAuth } from "@/hooks/use-auth";
import { clientConfig } from "@/lib/client-config";

const GOOGLE_CLIENT_ID = clientConfig.googleClientId;

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: Record<string, unknown>) => void;
          renderButton: (
            element: HTMLElement,
            config: Record<string, unknown>
          ) => void;
        };
      };
    };
  }
}

interface GoogleSignInProps {
  text?: "signin_with" | "signup_with" | "continue_with";
}

export function GoogleSignIn({ text = "continue_with" }: GoogleSignInProps) {
  const buttonRef = useRef<HTMLDivElement>(null);
  const googleAuth = useGoogleAuth();
  const initializedRef = useRef(false);

  const handleCredentialResponse = useCallback(
    (response: { credential: string }) => {
      googleAuth.mutate(response.credential);
    },
    [googleAuth]
  );

  const renderButton = useCallback(() => {
    if (!window.google || !buttonRef.current || initializedRef.current) return;
    if (!GOOGLE_CLIENT_ID) return;

    initializedRef.current = true;

    window.google.accounts.id.initialize({
      client_id: GOOGLE_CLIENT_ID,
      callback: handleCredentialResponse,
      auto_select: false,
      cancel_on_tap_outside: true,
    });

    window.google.accounts.id.renderButton(buttonRef.current, {
      theme: "filled_black",
      size: "large",
      width: buttonRef.current.offsetWidth,
      text,
      shape: "rectangular",
      logo_alignment: "left",
    });
  }, [handleCredentialResponse, text]);

  useEffect(() => {
    if (window.google) renderButton();
  }, [renderButton]);

  if (!GOOGLE_CLIENT_ID) {
    return (
      <button
        type="button"
        onClick={() => toast.info("Google Sign In is not configured in this environment.")}
        className="flex h-10 w-full items-center justify-center gap-2 rounded-md border border-border bg-background px-4 text-sm font-medium text-foreground transition hover:bg-muted"
      >
        <GoogleIcon />
        Continue with Google
      </button>
    );
  }

  return (
    <>
      <Script
        src="https://accounts.google.com/gsi/client"
        strategy="afterInteractive"
        onLoad={renderButton}
      />
      <div ref={buttonRef} className="w-full [&>div]:!w-full" />
    </>
  );
}

function GoogleIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 24 24">
      <path
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"
        fill="#4285F4"
      />
      <path
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
        fill="#34A853"
      />
      <path
        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18A10.96 10.96 0 0 0 1 12c0 1.77.42 3.45 1.18 4.93l2.85-2.22.81-.62z"
        fill="#FBBC05"
      />
      <path
        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
        fill="#EA4335"
      />
    </svg>
  );
}
