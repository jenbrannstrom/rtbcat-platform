import { NextRequest, NextResponse } from "next/server";
import {
  isBuyerIdSegment,
  isBuyerScopedPath,
  SELECTED_BUYER_COOKIE,
  splitBuyerPath,
  toBuyerScopedPath,
} from "@/lib/buyer-routes";

const SKIP_PREFIXES = ["/_next", "/api", "/thumbnails"];
const SKIP_EXACT = new Set([
  "/favicon.ico",
  "/icon.svg",
  "/apple-icon.svg",
  "/robots.txt",
  "/sitemap.xml",
]);

const LEGACY_ALIASES: Record<string, string> = {
  "/creatives": "/clusters",
  "/uploads": "/import",
  "/waste-analysis": "/",
};

function shouldSkipPath(pathname: string): boolean {
  if (SKIP_EXACT.has(pathname)) return true;
  if (SKIP_PREFIXES.some((prefix) => pathname.startsWith(prefix))) return true;
  return /\.[a-z0-9]+$/i.test(pathname);
}

function buildPathWithBuyer(buyerId: string | null, basePath: string): string {
  if (!buyerId) return basePath;
  return basePath === "/" ? `/${buyerId}` : `/${buyerId}${basePath}`;
}

function redirectTo(request: NextRequest, pathname: string) {
  const url = request.nextUrl.clone();
  url.pathname = pathname;
  return NextResponse.redirect(url);
}

export function middleware(request: NextRequest) {
  const pathname = request.nextUrl.pathname;

  if (shouldSkipPath(pathname)) {
    return NextResponse.next();
  }

  const { buyerIdInPath, hasBuyerPrefix, pathWithoutBuyer } = splitBuyerPath(pathname);
  const buyerIdFromCookie = request.cookies.get(SELECTED_BUYER_COOKIE)?.value?.trim() || null;
  const validCookieBuyerId = buyerIdFromCookie && isBuyerIdSegment(buyerIdFromCookie)
    ? buyerIdFromCookie
    : null;

  const aliasTarget = LEGACY_ALIASES[pathWithoutBuyer];
  if (aliasTarget) {
    const buyerForAlias = buyerIdInPath || (isBuyerScopedPath(aliasTarget) ? validCookieBuyerId : null);
    return redirectTo(request, buildPathWithBuyer(buyerForAlias, aliasTarget));
  }

  // If a buyer prefix is present on a non-buyer-scoped page, normalize it away.
  if (hasBuyerPrefix && !isBuyerScopedPath(pathWithoutBuyer)) {
    return redirectTo(request, pathWithoutBuyer);
  }

  // For buyer-scoped pages without buyer prefix, inject the selected buyer from cookie.
  if (!hasBuyerPrefix && isBuyerScopedPath(pathWithoutBuyer)) {
    if (validCookieBuyerId) {
      const targetPath = toBuyerScopedPath(pathWithoutBuyer, validCookieBuyerId);
      if (targetPath !== pathname) {
        return redirectTo(request, targetPath);
      }
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/:path*"],
};
