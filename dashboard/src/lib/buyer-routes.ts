const BUYER_ID_PATTERN = /^\d+$/;

export const SELECTED_BUYER_STORAGE_KEY = "rtbcat-selected-buyer-id";
export const SELECTED_BUYER_COOKIE = "rtbcat-selected-buyer-id";

const NON_BUYER_SCOPED_PREFIXES = [
  "/admin",
  "/api",
  "/connect",
  "/login",
  "/settings",
  "/setup",
];

const BUYER_SCOPED_PREFIXES = [
  "/",
  "/campaigns",
  "/clusters",
  "/creatives",
  "/history",
  "/import",
  "/pretargeting",
  "/qps",
  "/uploads",
  "/waste-analysis",
];

export interface BuyerPathInfo {
  buyerIdInPath: string | null;
  hasBuyerPrefix: boolean;
  pathWithoutBuyer: string;
}

function normalizePath(pathname: string): string {
  if (!pathname) return "/";
  const withLeadingSlash = pathname.startsWith("/") ? pathname : `/${pathname}`;
  if (withLeadingSlash.length === 1) return withLeadingSlash;
  return withLeadingSlash.replace(/\/+$/, "");
}

export function isBuyerIdSegment(segment: string): boolean {
  return BUYER_ID_PATTERN.test(segment);
}

export function splitBuyerPath(pathname: string): BuyerPathInfo {
  const normalized = normalizePath(pathname);
  const segments = normalized.split("/").filter(Boolean);
  const first = segments[0];

  if (!first || !isBuyerIdSegment(first)) {
    return {
      buyerIdInPath: null,
      hasBuyerPrefix: false,
      pathWithoutBuyer: normalized,
    };
  }

  const remainder = segments.slice(1);
  return {
    buyerIdInPath: first,
    hasBuyerPrefix: true,
    pathWithoutBuyer: remainder.length > 0 ? `/${remainder.join("/")}` : "/",
  };
}

export function isBuyerScopedPath(pathname: string): boolean {
  const normalized = normalizePath(pathname);

  if (
    NON_BUYER_SCOPED_PREFIXES.some(
      (prefix) => normalized === prefix || normalized.startsWith(`${prefix}/`)
    )
  ) {
    return false;
  }

  return BUYER_SCOPED_PREFIXES.some((prefix) => {
    if (prefix === "/") {
      return normalized === "/";
    }
    return normalized === prefix || normalized.startsWith(`${prefix}/`);
  });
}

export function toBuyerScopedPath(
  pathname: string,
  buyerId: string | null | undefined
): string {
  const { pathWithoutBuyer } = splitBuyerPath(pathname);
  if (!isBuyerScopedPath(pathWithoutBuyer) || !buyerId) {
    return pathWithoutBuyer;
  }
  return pathWithoutBuyer === "/" ? `/${buyerId}` : `/${buyerId}${pathWithoutBuyer}`;
}

export function replaceBuyerInPath(
  pathname: string,
  buyerId: string | null | undefined
): string {
  return toBuyerScopedPath(pathname, buyerId);
}
