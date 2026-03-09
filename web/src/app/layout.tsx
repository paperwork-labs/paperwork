import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import { Providers } from "@/components/providers";
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
  title: "FileFree — Free AI Tax Filing",
  description:
    "Snap your W-2, get your completed return in minutes. Actually free. No upsells. No hidden fees.",
  keywords: [
    "free tax filing",
    "AI tax",
    "W2 scanner",
    "file taxes free",
    "AI tax filing",
    "filefree",
  ],
  openGraph: {
    title: "FileFree — Free AI Tax Filing",
    description:
      "Snap your W-2, get your completed return in minutes. Actually free.",
    url: "https://filefree.tax",
    siteName: "FileFree",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "FileFree — Free AI Tax Filing",
    description:
      "Snap your W-2, get your completed return in minutes. Actually free.",
  },
  robots: {
    index: true,
    follow: true,
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
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
