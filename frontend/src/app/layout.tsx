import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { Amiri } from "next/font/google";
import { Header } from "@/components/shared/header";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

const amiri = Amiri({
  weight: ["400", "700"],
  subsets: ["arabic", "latin"],
  variable: "--font-amiri",
});

export const metadata: Metadata = {
  title: "Ilm Atlas",
  description:
    "LLM-powered encyclopaedic guide to Sunni Islam, grounded in the Quran, Sunnah, and scholarly consensus.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${inter.variable} ${amiri.variable} font-sans antialiased`}>
        <Header />
        {children}
      </body>
    </html>
  );
}
