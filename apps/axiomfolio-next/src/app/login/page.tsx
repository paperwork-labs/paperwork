"use client";

import * as React from "react";
import { Suspense, useLayoutEffect } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Eye, EyeOff, Info, Loader2 } from "lucide-react";
import toast from "react-hot-toast";

import { useAuth } from "@/context/AuthContext";
import AuthLayout from "@/components/layout/AuthLayout";
import AppCard from "@/components/ui/AppCard";
import FormField from "@/components/ui/FormField";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { API_BASE_URL } from "@/services/api";
import { REGISTERED_PENDING_APPROVAL_KEY } from "@/lib/authSession";
import {
  axiosErrorDetailMessage,
  isPendingApprovalLoginError,
  isUnverifiedEmailLoginError,
} from "@/utils/authErrors";

const LAST_ROUTE_STORAGE_KEY = "qm.ui.last_route";

const PENDING_APPROVAL_MESSAGE =
  "Your account is pending admin approval. You'll receive access once an administrator approves your registration.";

const UNVERIFIED_EMAIL_MESSAGE =
  "Please check your inbox and click the verification link before signing in.";

const POST_REGISTER_APPROVAL_HINT =
  "Check your email to verify your address. An administrator must approve your account before you can sign in.";

/** `returnTo` query from `RequireAuthClient` must stay in-app (path-only). */
function safeAppReturnPath(raw: string | null): string | null {
  if (raw == null || raw === "") return null;
  let decoded: string;
  try {
    decoded = decodeURIComponent(raw);
  } catch {
    return null;
  }
  if (!decoded.startsWith("/") || decoded.startsWith("//")) return null;
  const pathOnly = decoded.split(/[?#]/)[0];
  if (pathOnly === "/login" || pathOnly === "/register") return null;
  return decoded;
}

function LoginInner() {
  const { login } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [showPw, setShowPw] = React.useState(false);
  const [loading, setLoading] = React.useState(false);
  const [pendingApprovalBanner, setPendingApprovalBanner] = React.useState(false);
  const [unverifiedEmailBanner, setUnverifiedEmailBanner] = React.useState(false);
  const [postRegisterBanner, setPostRegisterBanner] = React.useState(false);

  useLayoutEffect(() => {
    try {
      if (sessionStorage.getItem(REGISTERED_PENDING_APPROVAL_KEY) === "1") {
        setPostRegisterBanner(true);
        sessionStorage.removeItem(REGISTERED_PENDING_APPROVAL_KEY);
      }
    } catch {
      // ignore
    }
  }, []);

  const returnToParam = searchParams.get("returnTo");

  const redirectTo = React.useMemo(() => {
    const fromQuery = safeAppReturnPath(returnToParam);
    if (fromQuery) return fromQuery;
    try {
      const saved = localStorage.getItem(LAST_ROUTE_STORAGE_KEY);
      if (saved && saved !== "/login" && saved !== "/register") return saved;
    } catch {
      // ignore storage errors
    }
    return "/";
  }, [returnToParam]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setPendingApprovalBanner(false);
    setUnverifiedEmailBanner(false);
    try {
      await login(email, password);
      router.replace(redirectTo);
    } catch (err: unknown) {
      if (isPendingApprovalLoginError(err)) {
        setPendingApprovalBanner(true);
        return;
      }
      if (isUnverifiedEmailLoginError(err)) {
        setUnverifiedEmailBanner(true);
        return;
      }
      toast.error(axiosErrorDetailMessage(err) || "Login failed");
    } finally {
      setLoading(false);
    }
  };

  const infoAlert = (body: React.ReactNode, title?: string) => (
    <Alert className="border-primary/20 bg-primary/5 text-foreground">
      <Info className="size-4 text-primary" aria-hidden />
      <div>
        {title ? <AlertTitle className="text-sm">{title}</AlertTitle> : null}
        <AlertDescription className="text-sm text-muted-foreground">{body}</AlertDescription>
      </div>
    </Alert>
  );

  return (
    <AuthLayout>
      <AppCard>
        <div className="flex flex-col gap-4">
          <div>
            <h2 className="text-xl font-semibold tracking-tight text-card-foreground">Log in</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Welcome back. Enter your credentials to continue.
            </p>
          </div>
          {pendingApprovalBanner ? (
            infoAlert(PENDING_APPROVAL_MESSAGE)
          ) : unverifiedEmailBanner ? (
            infoAlert(UNVERIFIED_EMAIL_MESSAGE)
          ) : postRegisterBanner ? (
            infoAlert(POST_REGISTER_APPROVAL_HINT, "Registration received")
          ) : null}
          <Button
            type="button"
            variant="outline"
            className="h-11 rounded-lg font-medium"
            onClick={() => {
              window.location.href = `${API_BASE_URL}/auth/google/login`;
            }}
          >
            <svg width="18" height="18" viewBox="0 0 48 48" className="mr-2 shrink-0" aria-hidden>
              <path
                fill="var(--oauth-google-red)"
                d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"
              />
              <path
                fill="var(--oauth-google-blue)"
                d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"
              />
              <path
                fill="var(--oauth-google-yellow)"
                d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"
              />
              <path
                fill="var(--oauth-google-green)"
                d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"
              />
            </svg>
            Continue with Google
          </Button>
          <Button
            type="button"
            className="h-11 rounded-lg border-0 bg-[var(--oauth-apple-bg)] font-medium text-white hover:bg-[var(--oauth-apple-bg-hover)] focus-visible:ring-white/30"
            onClick={() => {
              window.location.href = `${API_BASE_URL}/auth/apple/login`;
            }}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="white" className="mr-2 shrink-0" aria-hidden>
              <path d="M17.05 20.28c-.98.95-2.05.88-3.08.4-1.09-.5-2.08-.48-3.24 0-1.44.62-2.2.44-3.06-.4C2.79 15.25 3.51 7.59 9.05 7.31c1.35.07 2.29.74 3.08.8 1.18-.24 2.31-.93 3.57-.84 1.51.12 2.65.72 3.4 1.8-3.12 1.87-2.38 5.98.48 7.13-.57 1.5-1.31 2.99-2.54 4.09zM12.03 7.25c-.15-2.23 1.66-4.07 3.74-4.25.29 2.58-2.34 4.5-3.74 4.25z" />
            </svg>
            Continue with Apple
          </Button>
          <div className="h-px w-full bg-border" role="separator" />
          <form className="flex flex-col gap-4" onSubmit={handleSubmit} noValidate>
            <FormField label="Email" required>
              <Input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                autoComplete="email"
              />
            </FormField>
            <FormField label="Password" required htmlFor="login-password">
              <div className="relative">
                <Input
                  id="login-password"
                  type={showPw ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="pr-10"
                  autoComplete="current-password"
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  className="absolute top-1/2 right-1 h-7 w-7 -translate-y-1/2 text-muted-foreground"
                  aria-label={showPw ? "Hide password" : "Show password"}
                  onClick={() => setShowPw(!showPw)}
                >
                  {showPw ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                </Button>
              </div>
            </FormField>
            <div className="flex justify-end">
              <Link
                href="/auth/forgot-password"
                className="text-xs text-muted-foreground underline-offset-4 hover:underline"
              >
                Forgot password?
              </Link>
            </div>
            <Button type="submit" disabled={loading} className="h-11 rounded-lg font-semibold">
              {loading ? "Signing in…" : "Log in"}
            </Button>
            <p className="text-sm text-muted-foreground">
              No account?{" "}
              <Link href="/register" className="font-medium text-primary underline-offset-4 hover:underline">
                Register
              </Link>
            </p>
          </form>
        </div>
      </AppCard>
      <p className="mt-6 text-center text-sm text-white">
        <Link href="/why-free" className="font-medium text-white underline-offset-4 hover:underline">
          Why is this free?
        </Link>
      </p>
    </AuthLayout>
  );
}

function LoginFallback() {
  return (
    <div
      className="flex min-h-screen flex-col items-center justify-center gap-3 bg-background px-4"
      role="status"
      aria-live="polite"
    >
      <Loader2 className="size-8 animate-spin text-primary" aria-hidden />
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<LoginFallback />}>
      <LoginInner />
    </Suspense>
  );
}
