import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import { Providers } from "@/components/providers";
import { Nav } from "@/components/nav";
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
  metadataBase: new URL("https://filefree.tax"),
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
  icons: {
    icon: "/favicon.svg",
  },
  openGraph: {
    title: "FileFree — Free AI Tax Filing",
    description:
      "Snap your W-2, get your completed return in minutes. Actually free.",
    url: "https://filefree.tax",
    siteName: "FileFree",
    type: "website",
    locale: "en_US",
  },
  twitter: {
    card: "summary_large_image",
    title: "FileFree — Free AI Tax Filing",
    description:
      "Snap your W-2, get your completed return in minutes. Actually free.",
    creator: "@filefreetax",
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
        className={`${inter.variable} ${jetbrainsMono.variable} font-sans antialiased`}
      >
        <Providers>
          <Nav />
          {children}
        </Providers>
      </body>
    </html>
  );
}
