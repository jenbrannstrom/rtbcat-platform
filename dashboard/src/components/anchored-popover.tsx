"use client";

import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type ReactNode,
  type RefObject,
} from "react";
import { cn } from "@/lib/utils";

export type PopoverPlacement = "right-start" | "top-start" | "bottom-end";

interface AnchoredPopoverProps {
  anchorRef: RefObject<HTMLElement | null>;
  open: boolean;
  onClose: () => void;
  placement: PopoverPlacement;
  /** Accessible name for the dialog. */
  label: string;
  className?: string;
  children: ReactNode;
}

const MARGIN_PX = 8;

/**
 * Popover positioned `fixed` from its anchor's bounding rect.
 *
 * The sidebar is `overflow-hidden` with a scrolling nav, so an absolutely
 * positioned menu inside it is clipped. Fixed positioning sidesteps that and
 * lets the same component serve the seat switcher, the collapsed-rail
 * flyouts, the language menu and the account menu.
 *
 * Closes on Escape (returning focus to the anchor) and on pointer-down
 * outside both the anchor and the panel.
 */
export function AnchoredPopover({
  anchorRef,
  open,
  onClose,
  placement,
  label,
  className,
  children,
}: AnchoredPopoverProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const [style, setStyle] = useState<Record<string, number> | null>(null);

  const updatePosition = useCallback(() => {
    const anchor = anchorRef.current;
    const panel = panelRef.current;
    if (!anchor || !panel || typeof window === "undefined") return;
    const rect = anchor.getBoundingClientRect();
    const width = panel.offsetWidth;
    const height = panel.offsetHeight;
    const maxLeft = Math.max(MARGIN_PX, window.innerWidth - width - MARGIN_PX);
    const maxTop = Math.max(MARGIN_PX, window.innerHeight - height - MARGIN_PX);

    if (placement === "right-start") {
      setStyle({
        left: Math.min(rect.right + MARGIN_PX, maxLeft),
        top: Math.min(Math.max(MARGIN_PX, rect.top), maxTop),
      });
    } else if (placement === "top-start") {
      setStyle({
        left: Math.min(Math.max(MARGIN_PX, rect.left), maxLeft),
        bottom: Math.max(MARGIN_PX, window.innerHeight - rect.top + MARGIN_PX / 2),
      });
    } else {
      setStyle({
        right: Math.max(MARGIN_PX, window.innerWidth - rect.right),
        top: Math.min(rect.bottom + MARGIN_PX / 2, maxTop),
      });
    }
  }, [anchorRef, placement]);

  useLayoutEffect(() => {
    if (!open) {
      setStyle(null);
      return;
    }
    updatePosition();
    window.addEventListener("resize", updatePosition);
    window.addEventListener("scroll", updatePosition, true);
    return () => {
      window.removeEventListener("resize", updatePosition);
      window.removeEventListener("scroll", updatePosition, true);
    };
  }, [open, updatePosition]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
        anchorRef.current?.focus();
      }
    };
    const onPointerDown = (event: MouseEvent) => {
      const target = event.target as Node;
      if (panelRef.current?.contains(target) || anchorRef.current?.contains(target)) return;
      onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("mousedown", onPointerDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("mousedown", onPointerDown);
    };
  }, [open, onClose, anchorRef]);

  if (!open) return null;

  return (
    <div
      ref={panelRef}
      role="dialog"
      aria-label={label}
      style={{ position: "fixed", visibility: style ? "visible" : "hidden", ...(style ?? {}) }}
      className={cn(
        "z-9999 rounded-lg border border-gray-200 bg-white shadow-lg",
        className,
      )}
    >
      {children}
    </div>
  );
}
