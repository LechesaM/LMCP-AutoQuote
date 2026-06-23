import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "LMCP Dashboard",
  description: "LMCP AutoQuote dashboard",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="font-sans min-h-full flex flex-col">{children}</body>
    </html>
  );
}
