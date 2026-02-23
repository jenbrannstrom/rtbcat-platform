import {
  isBuyerIdSegment,
  isBuyerScopedPath,
  splitBuyerPath,
  toBuyerScopedPath,
} from "./buyer-routes";

const LEGACY_ALIASES: Record<string, string> = {
  "/uploads": "/import",
  "/waste-analysis": "/",
};

export interface RouteNormalizationResult {
  targetPathname: string | null;
  ensurePublishersTab: boolean;
  reason:
    | "legacy_alias"
    | "legacy_pretargeting_publishers"
    | "strip_invalid_buyer_prefix"
    | "inject_buyer_prefix"
    | null;
}

function buildPathWithBuyer(buyerId: string | null, basePath: string): string {
  if (!buyerId) return basePath;
  return basePath === "/" ? `/${buyerId}` : `/${buyerId}${basePath}`;
}

function normalizeBillingSegment(segment: string): string {
  try {
    return encodeURIComponent(decodeURIComponent(segment));
  } catch {
    return encodeURIComponent(segment);
  }
}

export function normalizeRoutePath(
  pathname: string,
  cookieBuyerId: string | null | undefined
): RouteNormalizationResult {
  const { buyerIdInPath, hasBuyerPrefix, pathWithoutBuyer } = splitBuyerPath(pathname);
  const validCookieBuyerId =
    cookieBuyerId && isBuyerIdSegment(cookieBuyerId) ? cookieBuyerId : null;

  const legacyPretargetingMatch = pathWithoutBuyer.match(/^\/pretargeting\/([^/]+)\/publishers$/);
  if (legacyPretargetingMatch) {
    const billingId = normalizeBillingSegment(legacyPretargetingMatch[1]);
    const buyerForTarget = buyerIdInPath || validCookieBuyerId;
    return {
      targetPathname: buildPathWithBuyer(buyerForTarget, `/bill_id/${billingId}`),
      ensurePublishersTab: true,
      reason: "legacy_pretargeting_publishers",
    };
  }

  const aliasTarget = LEGACY_ALIASES[pathWithoutBuyer];
  if (aliasTarget) {
    const buyerForAlias = buyerIdInPath || (isBuyerScopedPath(aliasTarget) ? validCookieBuyerId : null);
    return {
      targetPathname: buildPathWithBuyer(buyerForAlias, aliasTarget),
      ensurePublishersTab: false,
      reason: "legacy_alias",
    };
  }

  if (hasBuyerPrefix && !isBuyerScopedPath(pathWithoutBuyer)) {
    return {
      targetPathname: pathWithoutBuyer,
      ensurePublishersTab: false,
      reason: "strip_invalid_buyer_prefix",
    };
  }

  if (!hasBuyerPrefix && isBuyerScopedPath(pathWithoutBuyer) && validCookieBuyerId) {
    const targetPathname = toBuyerScopedPath(pathWithoutBuyer, validCookieBuyerId);
    if (targetPathname !== pathname) {
      return {
        targetPathname,
        ensurePublishersTab: false,
        reason: "inject_buyer_prefix",
      };
    }
  }

  return {
    targetPathname: null,
    ensurePublishersTab: false,
    reason: null,
  };
}

