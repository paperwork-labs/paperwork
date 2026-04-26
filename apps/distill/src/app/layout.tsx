import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import { Inter, JetBrains_Mono } from "next/font/google";
import { Analytics } from "@vercel/analytics/next";
import { distillClerkAppearance } from "@/lib/clerk-appearance";
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
  title: "Distill — Compliance automation for modern platforms",
  description: "Tax API, formation API, and CPA SaaS for compliance workflows.",
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
        <ClerkProvider appearance={distillClerkAppearance}>
          {children}
          <Analytics />
        </ClerkProvider>
      </body>
    </html>
  );
}
