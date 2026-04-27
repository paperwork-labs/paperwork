import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import { Inter, JetBrains_Mono } from "next/font/google";
import { Analytics } from "@vercel/analytics/next";
import { accountsClerkAppearance } from "@/lib/accounts-clerk-appearance";
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
  title: {
    default: "Paperwork ID",
    template: "%s · Paperwork ID",
  },
  description:
    "Sign in once with Paperwork Labs. Your Paperwork ID works across FileFree, LaunchFree, AxiomFolio, Distill, and Trinkets.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body
        data-theme="paperwork-labs"
        className={`${inter.variable} ${jetbrainsMono.variable} min-h-dvh bg-[#0F172A] font-sans text-[#F8FAFC]`}
      >
        <ClerkProvider
          appearance={accountsClerkAppearance}
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
