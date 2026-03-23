import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
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
  title: "Paperwork Labs — We build tools that eliminate paperwork.",
  description:
    "Paperwork Labs builds free tools that eliminate paperwork. FileFree (free tax filing), LaunchFree (free LLC formation), Distill (B2B compliance automation), and Trinkets (utility tools).",
  metadataBase: new URL("https://paperworklabs.com"),
  openGraph: {
    title: "Paperwork Labs",
    description: "We build tools that eliminate paperwork.",
    url: "https://paperworklabs.com",
    siteName: "Paperwork Labs",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    site: "@paperworklabs",
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
        data-theme="studio"
        className={`${inter.variable} ${jetbrainsMono.variable} font-sans`}
      >
        {children}
      </body>
    </html>
  );
}
