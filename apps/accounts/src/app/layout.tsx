import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import { Inter, JetBrains_Mono } from "next/font/google";
import { Analytics } from "@vercel/analytics/next";
import { accountsAppearance } from "@/lib/accounts-clerk-appearance";
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
  metadataBase: new URL("https://accounts.paperworklabs.com"),
  title: "Paperwork Labs — Sign in",
  description: "Sign in to your Paperwork Labs account. One identity for FileFree, AxiomFolio, LaunchFree, and more.",
  openGraph: {
    title: "Paperwork Labs — Sign in",
    description: "Sign in to your Paperwork Labs account.",
    url: "https://accounts.paperworklabs.com",
    siteName: "Paperwork Labs",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Paperwork Labs — Sign in",
    description: "Sign in to your Paperwork Labs account.",
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
        data-theme="accounts"
        className={`${inter.variable} ${jetbrainsMono.variable} font-sans`}
      >
        <ClerkProvider
          appearance={accountsAppearance}
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
