"use client";

import { Suspense } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";
import { useState } from "react";
import { Toaster } from "@/components/ui/sonner";
import { AttributionProvider } from "@/lib/attribution";
import { PostHogProvider } from "@/components/posthog-provider";
import { AuthProvider } from "@/components/auth-provider";
import { SessionTimeoutDialog } from "@/components/session-timeout-dialog";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000,
            retry: 1,
          },
        },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider
        attribute="class"
        defaultTheme="dark"
        enableSystem
        disableTransitionOnChange
      >
        <Suspense fallback={null}>
          <PostHogProvider>
            <AttributionProvider>
              <AuthProvider>
                {children}
                <SessionTimeoutDialog />
              </AuthProvider>
              <Toaster richColors position="top-right" />
            </AttributionProvider>
          </PostHogProvider>
        </Suspense>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
