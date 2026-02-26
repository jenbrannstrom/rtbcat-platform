import { NextRequest, NextResponse } from "next/server";
import {
  SELECTED_BUYER_COOKIE,
} from "@/lib/buyer-routes";
import { normalizeRoutePath } from "@/lib/route-normalization";

const SKIP_PREFIXES = ["/_next", "/api"];
const SKIP_EXACT = new Set([
  "/favicon.ico",
  "/icon.svg",
  "/apple-icon.svg",
  "/robots.txt",
  "/sitemap.xml",
]);

function shouldSkipPath(pathname: string): boolean {
  if (SKIP_EXACT.has(pathname)) return true;
  if (SKIP_PREFIXES.some((prefix) => pathname.startsWith(prefix))) return true;
  return /\.[a-z0-9]+$/i.test(pathname);
}

function redirectTo(
  request: NextRequest,
  pathname: string,
  options?: { ensurePublishersTab?: boolean }
) {
  const url = request.nextUrl.clone();
  url.pathname = pathname;
  if (options?.ensurePublishersTab && !url.searchParams.has("tab")) {
    url.searchParams.set("tab", "publishers");
  }
  return NextResponse.redirect(url);
}

export function middleware(request: NextRequest) {
  const pathname = request.nextUrl.pathname;

  if (shouldSkipPath(pathname)) {
    return NextResponse.next();
  }

  const buyerIdFromCookie = request.cookies.get(SELECTED_BUYER_COOKIE)?.value?.trim() || null;
  const normalized = normalizeRoutePath(pathname, buyerIdFromCookie);
  if (normalized.targetPathname && normalized.targetPathname !== pathname) {
    return redirectTo(request, normalized.targetPathname, {
      ensurePublishersTab: normalized.ensurePublishersTab,
    });
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/:path*"],
};
