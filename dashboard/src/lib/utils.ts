import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatNumber(num: number): string {
  return new Intl.NumberFormat().format(num);
}

export function formatDate(date: string | Date): string {
  return new Intl.DateTimeFormat("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(date));
}

export function truncate(str: string, length: number): string {
  if (str.length <= length) return str;
  return str.slice(0, length) + "...";
}

// Display label mapping - API returns HTML/IMAGE but UI shows "Display"
const FORMAT_LABELS: Record<string, string> = {
  HTML: "Display",
  IMAGE: "Display",
  DISPLAY: "Display",
  VIDEO: "Video",
  NATIVE: "Native",
};

export function getFormatLabel(format: string): string {
  return FORMAT_LABELS[format] || format;
}

export function getFormatColor(format: string): string {
  const colors: Record<string, string> = {
    HTML: "bg-blue-100 text-blue-800",
    VIDEO: "bg-purple-100 text-purple-800",
    NATIVE: "bg-green-100 text-green-800",
    IMAGE: "bg-blue-100 text-blue-800", // Same as HTML (both are Display)
    DISPLAY: "bg-blue-100 text-blue-800",
    UNKNOWN: "bg-gray-100 text-gray-800",
  };
  return colors[format] || colors.UNKNOWN;
}

export function getStatusColor(status: string | null): string {
  if (!status) return "bg-gray-100 text-gray-600";
  const colors: Record<string, string> = {
    APPROVED: "bg-green-100 text-green-800",
    PENDING_REVIEW: "bg-yellow-100 text-yellow-800",
    DISAPPROVED: "bg-red-100 text-red-800",
  };
  return colors[status] || "bg-gray-100 text-gray-600";
}
