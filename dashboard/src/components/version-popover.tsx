"use client";

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { Check, Copy, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { useTranslation } from "@/contexts/i18n-context";

interface VersionPopoverProps {
  /** Short label shown in the footer, e.g. "v0.9.5 (sha-f00f0a4b…)". */
  label: string;
  /** Release tag, e.g. "v0.9.5", or null when unknown. */
  release: string | null;
  /** Full build identifier (git sha), or null when unknown. */
  build: string | null;
  className?: string;
}

const POPOVER_MARGIN_PX = 8;

/**
 * Footer version label that opens a small popover on click.
 *
 * The previous implementation exposed the full build sha only through a native
 * `title` tooltip, which cannot be selected or copied. The popover renders the
 * release and build as selectable text and offers a one-click copy. It is
 * positioned `fixed` from the trigger's bounding rect because the sidebar
 * footer is `overflow-hidden` and would clip an absolutely-positioned child.
 */
export function VersionPopover({ label, release, build, className }: VersionPopoverProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const [position, setPosition] = useState<{ left: number; bottom: number } | null>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);
  const copiedTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const releaseText = release ?? "unknown";
  const buildText = build ?? "unknown";
  const copyText = `Release: ${releaseText} | Build: ${buildText}`;

  const updatePosition = useCallback(() => {
    const trigger = triggerRef.current;
    if (!trigger || typeof window === "undefined") return;
    const rect = trigger.getBoundingClientRect();
    const popoverWidth = popoverRef.current?.offsetWidth ?? 0;
    const maxLeft = Math.max(POPOVER_MARGIN_PX, window.innerWidth - popoverWidth - POPOVER_MARGIN_PX);
    setPosition({
      left: Math.min(Math.max(POPOVER_MARGIN_PX, rect.left), maxLeft),
      bottom: window.innerHeight - rect.top + POPOVER_MARGIN_PX,
    });
  }, []);

  // Anchor above the trigger; re-anchor on resize/scroll while open.
  useLayoutEffect(() => {
    if (!open) return;
    updatePosition();
    window.addEventListener("resize", updatePosition);
    window.addEventListener("scroll", updatePosition, true);
    return () => {
      window.removeEventListener("resize", updatePosition);
      window.removeEventListener("scroll", updatePosition, true);
    };
  }, [open, updatePosition]);

  // Close on Escape or on a click outside the popover/trigger.
  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        triggerRef.current?.focus();
      }
    };
    const onPointerDown = (event: MouseEvent) => {
      const target = event.target as Node;
      if (popoverRef.current?.contains(target) || triggerRef.current?.contains(target)) return;
      setOpen(false);
    };
    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("mousedown", onPointerDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("mousedown", onPointerDown);
    };
  }, [open]);

  useEffect(() => () => {
    if (copiedTimerRef.current) clearTimeout(copiedTimerRef.current);
  }, []);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(copyText);
    } catch {
      // Clipboard API unavailable (insecure context / permissions): select the
      // text so the user can copy it manually.
      const node = popoverRef.current?.querySelector<HTMLElement>("[data-version-text]");
      if (node && typeof window !== "undefined") {
        const range = document.createRange();
        range.selectNodeContents(node);
        const selection = window.getSelection();
        selection?.removeAllRanges();
        selection?.addRange(range);
      }
      return;
    }
    setCopied(true);
    if (copiedTimerRef.current) clearTimeout(copiedTimerRef.current);
    copiedTimerRef.current = setTimeout(() => setCopied(false), 1500);
  }, [copyText]);

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-haspopup="dialog"
        aria-expanded={open}
        className={cn(
          "min-w-0 flex-1 truncate text-left underline decoration-dotted underline-offset-2 hover:text-gray-600 transition-colors cursor-pointer",
          className,
        )}
      >
        {label}
      </button>

      {open && position && (
        <div
          ref={popoverRef}
          role="dialog"
          aria-label={copyText}
          style={{ position: "fixed", left: position.left, bottom: position.bottom }}
          className="z-[9999] w-[22rem] max-w-[calc(100vw-1rem)] rounded-md border border-gray-200 bg-white p-3 text-xs text-gray-700 shadow-lg"
        >
          <div className="flex items-start justify-between gap-2">
            <dl data-version-text className="min-w-0 flex-1 select-text space-y-1 font-mono">
              <div className="flex gap-2">
                <dt className="flex-shrink-0 text-gray-400">Release:</dt>
                <dd className="min-w-0 break-all">{releaseText}</dd>
              </div>
              <div className="flex gap-2">
                <dt className="flex-shrink-0 text-gray-400">Build:</dt>
                <dd className="min-w-0 break-all select-all">{buildText}</dd>
              </div>
            </dl>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="flex-shrink-0 rounded p-0.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
              aria-label={t.common.close}
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
          <div className="mt-2 flex justify-end">
            <button
              type="button"
              onClick={handleCopy}
              className={cn(
                "inline-flex items-center gap-1 rounded border px-2 py-1 font-medium transition-colors",
                copied
                  ? "border-green-200 bg-green-50 text-green-700"
                  : "border-gray-200 bg-gray-50 text-gray-600 hover:bg-gray-100 hover:text-gray-800",
              )}
            >
              {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
              {copied ? t.common.copied : t.common.copy}
            </button>
          </div>
        </div>
      )}
    </>
  );
}
