"use client";

import { useState, useEffect, type ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { BookOpen, ChevronLeft, ChevronRight, Lock, Menu, X } from "lucide-react";
import { useAuth } from "@/contexts/auth-context";
import { useTranslation } from "@/contexts/i18n-context";
import { cn } from "@/lib/utils";

interface TocEntry {
  slug: string;
  title: string;
  audience: string | null;
  order: number;
  part: string;
  internal: boolean;
}

const PART_ORDER = [
  "Getting Started",
  "Media Buyer Track",
  "DevOps Track",
  "Reference",
];

export default function DocsLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { isAuthenticated } = useAuth();
  const { language, setLanguage, t } = useTranslation();
  const [chapters, setChapters] = useState<TocEntry[]>([]);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

  const lang = language === "zh" ? "zh" : "en";
  // Authenticated users see all chapters; public visitors see only public ones
  const showInternal = !!isAuthenticated;

  useEffect(() => {
    const params = new URLSearchParams({ lang });
    if (showInternal) params.set("internal", "true");
    fetch(`/api/docs/toc?${params}`)
      .then((r) => {
        if (!r.ok) throw new Error("API unavailable");
        return r.json();
      })
      .then((data) => setChapters(data.chapters || []))
      .catch(() => {});
  }, [lang, showInternal]);

  useEffect(() => {
    setMobileSidebarOpen(false);
  }, [pathname]);

  const currentSlug = pathname.replace("/docs/", "").replace("/docs", "");

  const grouped = PART_ORDER.map((part) => ({
    part,
    items: chapters.filter((c) => c.part === part),
  })).filter((g) => g.items.length > 0);

  const sidebarContent = (
    <nav className="flex-1 overflow-y-auto py-4 px-3">
      {grouped.map((group) => (
        <div key={group.part} className="mb-4">
          <h3 className="px-2 mb-1 text-xs font-semibold text-gray-400 uppercase tracking-wider">
            {group.part}
          </h3>
          <ul className="space-y-0.5">
            {group.items.map((ch) => (
              <li key={ch.slug}>
                <Link
                  href={`/docs/${ch.slug}`}
                  className={cn(
                    "block px-2 py-1.5 text-sm rounded-md transition-colors",
                    currentSlug === ch.slug
                      ? "bg-primary-50 text-primary-700 font-medium"
                      : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                  )}
                >
                  {ch.internal && <Lock className="inline h-3 w-3 mr-1 opacity-40" />}
                  {ch.title}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      ))}
      {!showInternal && (
        <div className="px-2 pt-3 border-t border-gray-200 mt-2">
          <p className="text-xs text-gray-400">
            <Lock className="inline h-3 w-3 mr-1" />
            DevOps &amp; architecture chapters are available after{" "}
            <Link href="/login" className="text-primary-600 hover:underline">
              signing in
            </Link>.
          </p>
        </div>
      )}
    </nav>
  );

  return (
    <div className="flex h-screen bg-white">
      {sidebarOpen && (
        <aside className="hidden md:flex md:flex-col w-72 border-r border-gray-200 bg-gray-50/50">
          <div className="flex items-center justify-between h-14 px-4 border-b border-gray-200">
            <Link href="/docs" className="flex items-center gap-2 text-gray-900 hover:text-primary-600">
              <BookOpen className="h-5 w-5" />
              <span className="font-semibold text-sm">Cat-Scan Docs</span>
            </Link>
            <button
              onClick={() => setSidebarOpen(false)}
              className="p-1 text-gray-400 hover:text-gray-600 rounded"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
          </div>
          {sidebarContent}
        </aside>
      )}

      {mobileSidebarOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          <div
            className="fixed inset-0 bg-black/30"
            onClick={() => setMobileSidebarOpen(false)}
          />
          <aside className="relative flex flex-col w-72 h-full bg-white shadow-xl">
            <div className="flex items-center justify-between h-14 px-4 border-b border-gray-200">
              <Link href="/docs" className="flex items-center gap-2 text-gray-900">
                <BookOpen className="h-5 w-5" />
                <span className="font-semibold text-sm">Cat-Scan Docs</span>
              </Link>
              <button
                onClick={() => setMobileSidebarOpen(false)}
                className="p-1 text-gray-400 hover:text-gray-600 rounded"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            {sidebarContent}
          </aside>
        </div>
      )}

      <div className="flex-1 flex flex-col min-w-0">
        <header className="flex items-center h-14 px-4 border-b border-gray-200 bg-white gap-3">
          <button
            onClick={() => setMobileSidebarOpen(true)}
            className="md:hidden p-1.5 text-gray-500 hover:text-gray-700 rounded"
          >
            <Menu className="h-5 w-5" />
          </button>

          {!sidebarOpen && (
            <button
              onClick={() => setSidebarOpen(true)}
              className="hidden md:block p-1.5 text-gray-400 hover:text-gray-600 rounded"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          )}

          <div className="flex-1" />

          <button
            onClick={() => setLanguage(lang === "en" ? "zh" : "en")}
            className="px-2.5 py-1 text-xs font-medium text-gray-600 bg-gray-100 hover:bg-gray-200 rounded-md transition-colors"
          >
            {lang === "en" ? "中文" : "EN"}
          </button>

          {isAuthenticated ? (
            <Link
              href="/"
              className="text-sm text-gray-500 hover:text-primary-600 transition-colors"
            >
              {t.common?.backToApp ?? "Back to app"}
            </Link>
          ) : (
            <Link
              href="/login"
              className="text-sm text-primary-600 hover:text-primary-800 font-medium transition-colors"
            >
              Sign in
            </Link>
          )}
        </header>

        <main className="flex-1 overflow-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
