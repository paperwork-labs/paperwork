import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import "./globals.css";
import { axiomfolioClerkAppearance } from "@/lib/axiomfolio-clerk-appearance";
import { Providers } from "../providers";

export const metadata: Metadata = {
  title: "AxiomFolio",
  description: "Strategy-native portfolio intelligence — Next.js 16 (AxiomFolio).",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body className="min-h-screen bg-background text-foreground antialiased">
        <ClerkProvider
          appearance={axiomfolioClerkAppearance}
          signInUrl="/sign-in"
          signUpUrl="/sign-up"
        >
          <Providers>{children}</Providers>
        </ClerkProvider>
      </body>
    </html>
  );
}
