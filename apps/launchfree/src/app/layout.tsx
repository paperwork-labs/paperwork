import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import { Inter, JetBrains_Mono } from "next/font/google";
import { Analytics } from "@vercel/analytics/next";
import { Providers } from "@/lib/providers";
import { launchFreeClerkAppearance } from "@/lib/launchfree-clerk-appearance";
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
  title: "LaunchFree — Free LLC formation",
  description: "Starting a business should not require a lawyer.",
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
        <ClerkProvider appearance={launchFreeClerkAppearance}>
          <Providers>{children}</Providers>
          <Analytics />
        </ClerkProvider>
      </body>
    </html>
  );
}
