import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "LifePilot Circles — Make more happen, together",
  description: "Your AI-powered family and team action assistant. Plan, approve, coordinate, and get things done.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
