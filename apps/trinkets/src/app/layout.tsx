import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import { Inter, JetBrains_Mono } from "next/font/google";
import { Analytics } from "@vercel/analytics/next";
import { trinketsAppearance } from "@paperwork-labs/auth-clerk/appearance";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains",
});

export const metadata: Metadata = {
  metadataBase: new URL("https://tools.filefree.ai"),
  title: "Trinkets — Financial utility tools",
  description: "Fast free calculators and utility tools from Paperwork Labs.",
  openGraph: {
    title: "Trinkets — Financial utility tools",
    description: "Fast free calculators and utility tools from Paperwork Labs.",
    url: "https://tools.filefree.ai",
    siteName: "Trinkets",
    type: "website",
    images: [
      {
        url: "/brand/trinkets-icon.svg",
        width: 128,
        height: 128,
        alt: "Trinkets",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Trinkets — Financial utility tools",
    description: "Fast free calculators and utility tools from Paperwork Labs.",
    images: ["/brand/trinkets-icon.svg"],
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
        data-theme="trinkets"
        className={`${inter.variable} ${jetbrainsMono.variable} font-sans`}
      >
        <ClerkProvider
          appearance={trinketsAppearance}
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
