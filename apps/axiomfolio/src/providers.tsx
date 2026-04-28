"use client";

import * as React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "react-hot-toast";

import { ClerkTokenBridge } from "@/components/providers/ClerkTokenBridge";
import { AccountProvider } from "@/context/AccountContext";
import { ColorModeProvider } from "@/theme/colorMode";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = React.useState(() => new QueryClient());

  return (
    <ColorModeProvider>
      <QueryClientProvider client={queryClient}>
        <ClerkTokenBridge />
        <AccountProvider>
          {children}
          <Toaster position="top-right" />
        </AccountProvider>
      </QueryClientProvider>
    </ColorModeProvider>
  );
}
