"use client";

import { AlertTriangle, CheckCircle, Loader2, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import type { BuyerContextState } from "@/lib/buyer-context-state";

const STYLE_MAP = {
  loading: {
    bg: "bg-slate-50 border-slate-200",
    text: "text-slate-700",
    Icon: Loader2,
    iconClass: "animate-spin",
  },
  no_active_seats: {
    bg: "bg-red-50 border-red-200",
    text: "text-red-700",
    Icon: XCircle,
    iconClass: "",
  },
  selected_buyer_invalid: {
    bg: "bg-amber-50 border-amber-200",
    text: "text-amber-700",
    Icon: AlertTriangle,
    iconClass: "",
  },
  selected_buyer_valid: {
    bg: "bg-green-50 border-green-200",
    text: "text-green-700",
    Icon: CheckCircle,
    iconClass: "",
  },
} as const;

export function BuyerContextBanner({ state }: { state: BuyerContextState }) {
  const style = STYLE_MAP[state.validity];
  const { Icon, iconClass } = style;

  return (
    <div
      className={cn(
        "mb-6 flex items-start gap-2 rounded-lg border p-3 text-sm",
        style.bg,
        style.text,
      )}
    >
      <Icon className={cn("mt-0.5 h-4 w-4 shrink-0", iconClass)} />
      <span>{state.message}</span>
    </div>
  );
}
