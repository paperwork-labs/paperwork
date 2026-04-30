import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import { Inter, JetBrains_Mono } from "next/font/google";
import { Analytics } from "@vercel/analytics/next";
import { Providers } from "@/lib/providers";
import { launchFreeAppearance } from "@paperwork-labs/auth-clerk/appearance";
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

const clerkLocalization = createProductClerkLocalization("LaunchFree");

export const metadata: Metadata = {
  metadataBase: new URL("https://launchfree.ai"),
  title: "LaunchFree — Free LLC formation",
  description: "Starting a business should not require a lawyer.",
  openGraph: {
    title: "LaunchFree — Free LLC formation",
    description: "Starting a business should not require a lawyer.",
    url: "https://launchfree.ai",
    siteName: "LaunchFree",
    type: "website",
    images: [
      {
        url: "/brand/launchfree-icon.svg",
        width: 128,
        height: 128,
        alt: "LaunchFree",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "LaunchFree — Free LLC formation",
    description: "Starting a business should not require a lawyer.",
    creator: "@launchfreeai",
    images: ["/brand/launchfree-icon.svg"],
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
        data-theme="launchfree"
        className={`${inter.variable} ${jetbrainsMono.variable} font-sans`}
      >
        <ClerkProvider
          appearance={launchFreeAppearance}
          localization={clerkLocalization}
          signInUrl="/sign-in"
          signUpUrl="/sign-up"
        >
          <Providers>{children}</Providers>
          <Analytics />
        </ClerkProvider>
      </body>
    </html>
  );
}
