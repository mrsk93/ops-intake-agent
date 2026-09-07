import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Ops Intake / Control Desk",
  description: "Evidence-first review for governed operations intake.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
