"use client";

import * as React from "react";
import { Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Eye, EyeOff, Loader2 } from "lucide-react";
import toast from "react-hot-toast";

import { useAuth } from "@/context/AuthContext";
import AuthLayout from "@/components/layout/AuthLayout";
import PasswordStrengthMeter from "@/components/auth/PasswordStrengthMeter";
import AppCard from "@/components/ui/AppCard";
import FormField from "@/components/ui/FormField";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { REGISTERED_PENDING_APPROVAL_KEY } from "@/lib/authSession";
import { TIER_LABEL, type SubscriptionTier } from "@/types/entitlement";

const PENDING_UPGRADE_KEY = "pending_upgrade_tier";

const tierKeys = Object.keys(TIER_LABEL) as SubscriptionTier[];
const SUBSCRIPTION_TIER_SET = new Set<SubscriptionTier>(tierKeys);

function RegisterInner() {
  const { register } = useAuth();
  const [username, setUsername] = React.useState("");
  const [email, setEmail] = React.useState("");
  const [fullName, setFullName] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [showPw, setShowPw] = React.useState(false);
  const [loading, setLoading] = React.useState(false);
  const router = useRouter();
  const searchParams = useSearchParams();

  const upgradeTierSlug = React.useMemo((): SubscriptionTier | null => {
    const raw = searchParams.get("upgrade");
    if (!raw) return null;
    const key = raw.trim().toLowerCase() as SubscriptionTier;
    return SUBSCRIPTION_TIER_SET.has(key) ? key : null;
  }, [searchParams]);

  const upgradeTierLabel = upgradeTierSlug ? TIER_LABEL[upgradeTierSlug] : null;

  React.useEffect(() => {
    if (!upgradeTierSlug) return;
    try {
      localStorage.setItem(PENDING_UPGRADE_KEY, upgradeTierSlug);
    } catch {
      // Storage unavailable — checkout handoff can still read the query string on this session.
    }
  }, [upgradeTierSlug]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const { pendingApproval } = await register(username, email, password, fullName);
      if (pendingApproval) {
        try {
          sessionStorage.setItem(REGISTERED_PENDING_APPROVAL_KEY, "1");
        } catch {
          // ignore
        }
        router.replace("/login");
        return;
      }
      router.replace("/");
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string } }; message?: string };
      toast.error(ax?.response?.data?.detail || ax?.message || "Registration failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout>
      <AppCard>
        <form className="flex flex-col gap-4" onSubmit={handleSubmit} noValidate>
          <div>
            <h2 className="text-xl font-semibold tracking-tight text-card-foreground">Create account</h2>
            {upgradeTierLabel ? (
              <p className="mt-2 text-sm text-foreground">
                You&apos;re upgrading to <span className="font-semibold">{upgradeTierLabel}</span>.
              </p>
            ) : null}
            <p className="mt-1 text-sm text-muted-foreground">
              One minute setup. You can connect brokerages after. New accounts may need administrator approval before
              you can sign in.
            </p>
          </div>
          <FormField label="Username" required>
            <Input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="yourname"
              autoComplete="username"
            />
          </FormField>
          <FormField label="Email" required>
            <Input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              autoComplete="email"
            />
          </FormField>
          <FormField label="Full name">
            <Input
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="Optional"
              autoComplete="name"
            />
          </FormField>
          <FormField label="Password" required htmlFor="register-password">
            <div className="relative">
              <Input
                id="register-password"
                type={showPw ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="pr-10"
                autoComplete="new-password"
              />
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                className="absolute top-1/2 right-1 h-7 w-7 -translate-y-1/2 text-muted-foreground"
                aria-label={showPw ? "Hide password" : "Show password"}
                onClick={() => setShowPw(!showPw)}
              >
                {showPw ? <EyeOff className="size-4" aria-hidden /> : <Eye className="size-4" aria-hidden />}
              </Button>
            </div>
            {password.length > 0 ? <PasswordStrengthMeter password={password} /> : null}
          </FormField>
          <Button type="submit" disabled={loading} className="h-11 rounded-lg" variant="default">
            {loading ? "Creating account…" : "Register"}
          </Button>
          <p className="text-sm text-muted-foreground">
            Already have an account?{" "}
            <Link href="/login" className="font-medium text-primary underline-offset-4 hover:underline">
              Log in
            </Link>
          </p>
        </form>
      </AppCard>
      <p className="mt-6 text-center text-sm text-white">
        <Link href="/why-free" className="font-medium text-white underline-offset-4 hover:underline">
          Why is this free?
        </Link>
      </p>
    </AuthLayout>
  );
}

function RegisterFallback() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-background px-4" role="status">
      <Loader2 className="size-8 animate-spin text-primary" aria-hidden />
    </div>
  );
}

export default function RegisterPage() {
  return (
    <Suspense fallback={<RegisterFallback />}>
      <RegisterInner />
    </Suspense>
  );
}
