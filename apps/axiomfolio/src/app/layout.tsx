import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import "./globals.css";
import { axiomfolioAppearance } from "@paperwork-labs/auth-clerk/appearance";
import { createProductClerkLocalization } from "@paperwork-labs/auth-clerk/localization";
import { Providers } from "../providers";

const clerkLocalization = createProductClerkLocalization("AxiomFolio");

export const metadata: Metadata = {
  metadataBase: new URL("https://axiomfolio.com"),
  title: "AxiomFolio",
  description: "Portfolio + signals — Next.js 16 (AxiomFolio).",
  openGraph: {
    title: "AxiomFolio",
    description: "Portfolio + signals — Next.js 16 (AxiomFolio).",
    url: "https://axiomfolio.com",
    siteName: "AxiomFolio",
    type: "website",
    images: [
      {
        url: "/brand/axiomfolio-lockup.svg",
        width: 540,
        height: 150,
        alt: "AxiomFolio",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "AxiomFolio",
    description: "Portfolio + signals — Next.js 16 (AxiomFolio).",
    images: ["/brand/axiomfolio-lockup.svg"],
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body className="min-h-screen bg-background text-foreground antialiased">
        <ClerkProvider
          appearance={axiomfolioAppearance}
          localization={clerkLocalization}
          signInUrl="/sign-in"
          signUpUrl="/sign-up"
        >
          <Providers>{children}</Providers>
        </ClerkProvider>
      </body>
    </html>
  );
}
