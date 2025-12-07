import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { Suspense } from "react";
import "./globals.css";
import { Providers } from "./providers";
import { Sidebar } from "@/components/sidebar";
import { FirstRunCheck } from "@/components/first-run-check";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Cat-Scan Dashboard",
  description: "Creative Intelligence for Authorized Buyers",
  icons: {
    icon: "/icon.svg",
    apple: "/apple-icon.svg",
  },
};

function SidebarFallback() {
  return (
    <div className="flex flex-col w-64 bg-white border-r border-gray-200">
      <div className="flex items-center h-16 px-4 border-b border-gray-200">
        <div className="h-10 w-10 rounded-lg bg-gray-200 animate-pulse" />
        <div className="ml-3 h-6 w-20 bg-gray-200 rounded animate-pulse" />
      </div>
      <div className="flex-1 px-2 py-4 space-y-2">
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="h-10 bg-gray-100 rounded-md animate-pulse" />
        ))}
      </div>
    </div>
  );
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <Providers>
          <FirstRunCheck>
            <div className="flex h-screen bg-gray-50">
              <Suspense fallback={<SidebarFallback />}>
                <Sidebar />
              </Suspense>
              <main className="flex-1 overflow-auto">{children}</main>
            </div>
          </FirstRunCheck>
        </Providers>
      </body>
    </html>
  );
}
