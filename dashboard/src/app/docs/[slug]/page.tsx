"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ChevronLeft, ChevronRight, Loader2, Lock } from "lucide-react";
import { useAuth } from "@/contexts/auth-context";
import { useTranslation } from "@/contexts/i18n-context";
import type { Components } from "react-markdown";

interface ChapterData {
  slug: string;
  title: string;
  content: string;
  prev_slug: string | null;
  next_slug: string | null;
  lang: string;
}

const mdComponents: Components = {
  h1: ({ children }) => (
    <h1 className="text-3xl font-bold text-gray-900 mt-8 mb-4 first:mt-0">{children}</h1>
  ),
  h2: ({ children }) => (
    <h2 className="text-2xl font-semibold text-gray-900 mt-8 mb-3 pb-2 border-b border-gray-200">{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 className="text-xl font-semibold text-gray-800 mt-6 mb-2">{children}</h3>
  ),
  h4: ({ children }) => (
    <h4 className="text-lg font-medium text-gray-800 mt-4 mb-2">{children}</h4>
  ),
  p: ({ children }) => (
    <p className="text-gray-700 leading-7 mb-4">{children}</p>
  ),
  a: ({ href, children }) => {
    const isInternal = href?.startsWith("/");
    return isInternal ? (
      <Link href={href} className="text-primary-600 hover:text-primary-800 underline underline-offset-2">
        {children}
      </Link>
    ) : (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="text-primary-600 hover:text-primary-800 underline underline-offset-2"
      >
        {children}
      </a>
    );
  },
  ul: ({ children }) => (
    <ul className="list-disc pl-6 mb-4 space-y-1 text-gray-700">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="list-decimal pl-6 mb-4 space-y-1 text-gray-700">{children}</ol>
  ),
  li: ({ children }) => (
    <li className="leading-7">{children}</li>
  ),
  blockquote: ({ children }) => (
    <blockquote className="border-l-4 border-primary-200 pl-4 my-4 text-gray-600 italic">
      {children}
    </blockquote>
  ),
  code: ({ className, children }) => {
    const isBlock = className?.startsWith("language-");
    if (isBlock) {
      return (
        <code className="block text-sm">{children}</code>
      );
    }
    return (
      <code className="bg-gray-100 text-gray-800 text-sm px-1.5 py-0.5 rounded font-mono">
        {children}
      </code>
    );
  },
  pre: ({ children }) => (
    <pre className="bg-gray-900 text-gray-100 rounded-lg p-4 mb-4 overflow-x-auto text-sm leading-relaxed">
      {children}
    </pre>
  ),
  table: ({ children }) => (
    <div className="overflow-x-auto mb-4">
      <table className="min-w-full divide-y divide-gray-200 border border-gray-200 rounded-lg">
        {children}
      </table>
    </div>
  ),
  thead: ({ children }) => (
    <thead className="bg-gray-50">{children}</thead>
  ),
  th: ({ children }) => (
    <th className="px-4 py-2 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="px-4 py-2 text-sm text-gray-700 border-t border-gray-100">
      {children}
    </td>
  ),
  hr: () => <hr className="my-8 border-gray-200" />,
  img: ({ src, alt }) => (
    <img src={src} alt={alt || ""} className="max-w-full rounded-lg my-4 border border-gray-200" />
  ),
  strong: ({ children }) => (
    <strong className="font-semibold text-gray-900">{children}</strong>
  ),
  em: ({ children }) => (
    <em className="italic text-gray-600">{children}</em>
  ),
};

export default function DocsChapterPage() {
  const params = useParams();
  const slug = params.slug as string;
  const { isAuthenticated } = useAuth();
  const { language } = useTranslation();
  const [chapter, setChapter] = useState<ChapterData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [restricted, setRestricted] = useState(false);

  const lang = language === "zh" ? "zh" : "en";
  const showInternal = !!isAuthenticated;

  useEffect(() => {
    if (!slug) return;
    setLoading(true);
    setError(null);
    setRestricted(false);
    const qp = new URLSearchParams({ lang });
    if (showInternal) qp.set("internal", "true");
    fetch(`/api/docs/content/${slug}?${qp}`)
      .then((r) => {
        if (r.status === 403) { setRestricted(true); throw new Error("restricted"); }
        if (!r.ok) throw new Error("Chapter not found");
        return r.json();
      })
      .then((data) => setChapter(data))
      .catch((e) => { if (e.message !== "restricted") setError(e.message); })
      .finally(() => setLoading(false));
  }, [slug, lang, showInternal]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
      </div>
    );
  }

  if (restricted) {
    return (
      <div className="max-w-3xl mx-auto px-6 py-20 text-center">
        <Lock className="h-8 w-8 text-gray-300 mx-auto mb-3" />
        <p className="text-gray-600 text-lg mb-1">This chapter requires sign-in</p>
        <p className="text-gray-400 text-sm mb-4">
          DevOps and architecture chapters are available to authenticated users.
        </p>
        <Link href="/login" className="text-primary-600 hover:underline font-medium">
          Sign in to continue
        </Link>
      </div>
    );
  }

  if (error || !chapter) {
    return (
      <div className="max-w-3xl mx-auto px-6 py-20 text-center">
        <p className="text-gray-500 text-lg">Chapter not found.</p>
        <Link href="/docs" className="text-primary-600 hover:underline mt-2 inline-block">
          Back to table of contents
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto px-6 py-10">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>
        {chapter.content}
      </ReactMarkdown>

      {/* Previous / Next navigation */}
      <nav className="flex items-center justify-between mt-12 pt-6 border-t border-gray-200">
        {chapter.prev_slug ? (
          <Link
            href={`/docs/${chapter.prev_slug}`}
            className="flex items-center gap-1 text-sm text-gray-500 hover:text-primary-600 transition-colors"
          >
            <ChevronLeft className="h-4 w-4" />
            Previous
          </Link>
        ) : (
          <div />
        )}
        {chapter.next_slug ? (
          <Link
            href={`/docs/${chapter.next_slug}`}
            className="flex items-center gap-1 text-sm text-gray-500 hover:text-primary-600 transition-colors"
          >
            Next
            <ChevronRight className="h-4 w-4" />
          </Link>
        ) : (
          <div />
        )}
      </nav>
    </div>
  );
}
