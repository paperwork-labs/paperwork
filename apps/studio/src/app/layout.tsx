import type { Metadata, Viewport } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import { Inter, JetBrains_Mono } from "next/font/google";
import { Analytics } from "@vercel/analytics/next";
import "./globals.css";

import { StudioInstallPrompt } from "@/components/pwa/StudioInstallPrompt";
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
  },
  twitter: {
    card: "summary_large_image",
    site: "@paperworklabs",
  },
};

export const viewport: Viewport = {
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
          <Analytics />
        </ClerkProvider>
      </body>
    </html>
  );
}
