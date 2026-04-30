import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import { Inter, JetBrains_Mono } from "next/font/google";
import { Analytics } from "@vercel/analytics/next";
import { distillAppearance } from "@paperwork-labs/auth-clerk/appearance";
import { createProductClerkLocalization } from "@paperwork-labs/auth-clerk/localization";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains",
});

const clerkLocalization = createProductClerkLocalization("Distill");

export const metadata: Metadata = {
  metadataBase: new URL("https://distill.tax"),
  title: "Distill — Compliance automation for modern platforms",
  description: "Tax API, formation API, and CPA SaaS for compliance workflows.",
  openGraph: {
    title: "Distill — Compliance automation for modern platforms",
    description: "Tax API, formation API, and CPA SaaS for compliance workflows.",
    url: "https://distill.tax",
    siteName: "Distill",
    type: "website",
    images: [
      {
        url: "/brand/distill-icon.svg",
        width: 128,
        height: 128,
        alt: "Distill",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Distill — Compliance automation for modern platforms",
    description: "Tax API, formation API, and CPA SaaS for compliance workflows.",
    images: ["/brand/distill-icon.svg"],
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body
        data-theme="distill"
        className={`${inter.variable} ${jetbrainsMono.variable} font-sans`}
      >
        <ClerkProvider
          appearance={distillAppearance}
          localization={clerkLocalization}
          signInUrl="/sign-in"
          signUpUrl="/sign-up"
        >
          {children}
          <Analytics />
        </ClerkProvider>
      </body>
    </html>
  );
}
