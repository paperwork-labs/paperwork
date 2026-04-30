import type { Metadata, Viewport } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import { Inter, JetBrains_Mono } from "next/font/google";
import { Analytics } from "@vercel/analytics/next";
import "./globals.css";

import { StudioInstallPrompt } from "@/components/pwa/StudioInstallPrompt";
import { ObservabilityBootstrap } from "./observability-bootstrap";
import { studioAppearance } from "@paperwork-labs/auth-clerk/appearance";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains",
});

export const metadata: Metadata = {
  title: "Paperwork Labs — We build tools that eliminate paperwork.",
  description:
    "Paperwork Labs builds free tools that eliminate paperwork. FileFree (free tax filing), LaunchFree (free LLC formation), Distill (B2B compliance automation), and Trinkets (utility tools).",
  metadataBase: new URL("https://paperworklabs.com"),
  // Track M.7 — wire Studio's web app manifest. Auto-detected by Next
  // because the file lives at app/manifest.ts.
  applicationName: "Paperwork Studio",
  appleWebApp: {
    capable: true,
    title: "Paperwork Studio",
    statusBarStyle: "black-translucent",
  },
  openGraph: {
    title: "Paperwork Labs",
    description: "We build tools that eliminate paperwork.",
    url: "https://paperworklabs.com",
    siteName: "Paperwork Labs",
    type: "website",
    // TODO(brand): re-wire to P5 PNG once founder picks the winning variant
    images: [
      {
        url: "/brand/renders/paperclip-LOCKED-canonical-1024.png",
        width: 1408,
        height: 768,
        alt: "Paperwork Labs",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    site: "@paperworklabs",
    // TODO(brand): re-wire to P5 PNG once founder picks the winning variant
    images: ["/brand/renders/paperclip-LOCKED-canonical-1024.png"],
  },
};

export const viewport: Viewport = {
  /* PWA: canonical slate-night (brand.mdc); `themeColor` has no `var(--brand-surface)` */
  themeColor: "#0F172A",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body
        data-theme="studio"
        className={`${inter.variable} ${jetbrainsMono.variable} font-sans`}
      >
        <ClerkProvider
          appearance={studioAppearance}
          signInUrl="/sign-in"
          signUpUrl="/sign-up"
        >
          {children}
          <StudioInstallPrompt />
          <ObservabilityBootstrap
            brainUrl={process.env.BRAIN_API_URL ?? ""}
            brainToken={process.env.BRAIN_API_INTERNAL_TOKEN ?? ""}
            env={process.env.NODE_ENV === "production" ? "production" : "preview"}
          />
          <Analytics />
        </ClerkProvider>
      </body>
    </html>
  );
}
