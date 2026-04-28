import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import { Inter, JetBrains_Mono } from "next/font/google";
import { Analytics } from "@vercel/analytics/next";
import { Providers } from "@/components/providers";
import { Nav } from "@/components/nav";
import { fileFreeAppearance } from "@paperwork-labs/auth-clerk/appearance";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-inter",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-jetbrains",
});

export const metadata: Metadata = {
  metadataBase: new URL("https://filefree.ai"),
  title: {
    default: "FileFree — Free AI Tax Filing",
    template: "%s | FileFree",
  },
  description:
    "Snap your W-2, get your completed return in minutes. Actually free. No upsells. No hidden fees.",
  keywords: [
    "free tax filing",
    "AI tax",
    "W2 scanner",
    "file taxes free",
    "AI tax filing",
    "filefree",
    "free tax return",
    "tax filing app",
  ],
  openGraph: {
    title: "FileFree — Free AI Tax Filing",
    description:
      "Snap your W-2, get your completed return in minutes. Actually free.",
    url: "https://filefree.ai",
    siteName: "FileFree",
    type: "website",
    locale: "en_US",
    images: [
      {
        url: "/brand/filefree-icon.svg",
        width: 128,
        height: 128,
        alt: "FileFree",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "FileFree — Free AI Tax Filing",
    description:
      "Snap your W-2, get your completed return in minutes. Actually free.",
    creator: "@filefreetax",
    images: ["/brand/filefree-icon.svg"],
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        data-theme="filefree"
        className={`${inter.variable} ${jetbrainsMono.variable} font-sans antialiased`}
      >
        <ClerkProvider
          appearance={fileFreeAppearance}
          signInUrl="/sign-in"
          signUpUrl="/sign-up"
        >
          <Providers>
            <Nav />
            {/* Pages provide their own <main>; wrapper is a div to avoid nested mains. */}
            <div className="pt-14">{children}</div>
          </Providers>
          <Analytics />
        </ClerkProvider>
      </body>
    </html>
  );
}
