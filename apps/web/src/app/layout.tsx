import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Ops Intake Agent",
  description: "Governed document intake with evidence and human review.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
