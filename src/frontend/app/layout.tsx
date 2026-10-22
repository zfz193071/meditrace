import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MediTrace | Referral Review Copilot",
  description: "Review referral documents, trace source evidence and prepare a human-confirmed handoff. Synthetic portfolio prototype.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
