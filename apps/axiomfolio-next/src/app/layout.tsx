import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "../providers";

export const metadata: Metadata = {
  title: "AxiomFolio",
  description: "Strategy-native portfolio intelligence — Next.js 16 (AxiomFolio).",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body className="min-h-screen bg-background text-foreground antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
