"use client";

import { useState } from "react";
import { Copy, Check, Info, AlertTriangle } from "lucide-react";
import { useTranslation } from "@/contexts/i18n-context";
import { cn } from "@/lib/utils";
import type { DataNote } from "./utils";

/**
 * Copy to clipboard button component.
 */
export function CopyButton({ text, className }: { text: string; className?: string }) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);

  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <button
      onClick={handleCopy}
      className={cn("p-1 text-gray-400 hover:text-gray-600 rounded", className)}
      title={copied ? t.common.copied : t.common.copy}
    >
      {copied ? <Check className="h-3.5 w-3.5 text-green-500" /> : <Copy className="h-3.5 w-3.5" />}
    </button>
  );
}

/**
 * Metric display card component.
 */
export function MetricCard({ value, label }: { value: string; label: string }) {
  return (
    <div className="text-center p-3 bg-gray-50 rounded-lg">
      <div className="text-lg font-semibold text-gray-900">{value}</div>
      <div className="text-xs text-gray-500">{label}</div>
    </div>
  );
}

/**
 * Data notes section displaying info/alert badges.
 */
export function DataNotesSection({ notes }: { notes: DataNote[] }) {
  if (notes.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-2">
      {notes.map((note, i) => (
        <span
          key={i}
          className={cn(
            "inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full",
            note.icon === "alert"
              ? "bg-amber-50 text-amber-700 border border-amber-200"
              : "bg-blue-50 text-blue-700 border border-blue-200"
          )}
        >
          {note.icon === "alert" ? (
            <AlertTriangle className="h-3 w-3" />
          ) : (
            <Info className="h-3 w-3" />
          )}
          {note.message}
        </span>
      ))}
    </div>
  );
}
