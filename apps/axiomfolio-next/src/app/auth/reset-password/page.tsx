"use client";

import * as React from "react";
import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { Loader2 } from "lucide-react";

import AuthLayout from "@/components/layout/AuthLayout";
import AppCard from "@/components/ui/AppCard";

function ResetPasswordInner() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token");

  return (
    <AuthLayout>
      <AppCard>
        <h2 className="text-xl font-semibold tracking-tight text-card-foreground">Reset password</h2>
        <p className="mt-3 text-sm text-muted-foreground">
          Password reset will open soon — meanwhile, contact support@axiomfolio.com.
        </p>
        <span className="sr-only">
          {token ? "This URL includes a reset token." : "No reset token was provided in the URL."}
        </span>
      </AppCard>
    </AuthLayout>
  );
}

function ResetPasswordFallback() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <Loader2 className="size-8 animate-spin text-primary" aria-hidden />
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<ResetPasswordFallback />}>
      <ResetPasswordInner />
    </Suspense>
  );
}
