import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "FileFree — Free AI Tax Filing",
  description:
    "Snap your W-2, get your completed return in minutes. Actually free.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
