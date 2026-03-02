import { replaceBuyerInPath } from "@/lib/buyer-routes";

export interface BuyerContextSyncInput {
  isScoped: boolean;
  seatsLoaded: boolean;
  buyerIdInPath: string | null;
  selectedBuyerId: string | null;
  canonicalBuyerId: string | null;
}

export function getBuyerContextUpdateTarget({
  isScoped,
  seatsLoaded,
  buyerIdInPath,
  selectedBuyerId,
  canonicalBuyerId,
}: BuyerContextSyncInput): string | null {
  if (!isScoped) return null;

  if (!seatsLoaded) {
    if (!buyerIdInPath || buyerIdInPath === selectedBuyerId) return null;
    return buyerIdInPath;
  }

  if (canonicalBuyerId === selectedBuyerId) return null;
  return canonicalBuyerId;
}

export interface BuyerScopedRouteSyncInput {
  isScoped: boolean;
  seatsLoaded: boolean;
  buyerIdInPath: string | null;
  selectedBuyerId: string | null;
  pathname: string;
  queryString: string;
  currentUrl: string;
  canonicalBuyerId: string | null;
}

export function getBuyerScopedRouteReplaceTarget({
  isScoped,
  seatsLoaded,
  buyerIdInPath,
  selectedBuyerId,
  pathname,
  queryString,
  currentUrl,
  canonicalBuyerId,
}: BuyerScopedRouteSyncInput): string | null {
  if (!isScoped) return null;

  if (!seatsLoaded) {
    if (!selectedBuyerId || buyerIdInPath) return null;
    const targetPath = replaceBuyerInPath(pathname, selectedBuyerId);
    const targetUrl = queryString ? `${targetPath}?${queryString}` : targetPath;
    return targetUrl !== currentUrl ? targetUrl : null;
  }

  const targetPath = replaceBuyerInPath(pathname, canonicalBuyerId);
  const targetUrl = queryString ? `${targetPath}?${queryString}` : targetPath;
  return targetUrl !== currentUrl ? targetUrl : null;
}

export interface NonScopedRouteCleanupInput {
  buyerIdInPath: string | null;
  isScoped: boolean;
  pathWithoutBuyer: string;
  queryString: string;
  currentUrl: string;
}

export function getNonScopedRouteCleanupTarget({
  buyerIdInPath,
  isScoped,
  pathWithoutBuyer,
  queryString,
  currentUrl,
}: NonScopedRouteCleanupInput): string | null {
  if (!buyerIdInPath || isScoped) return null;
  const targetUrl = queryString ? `${pathWithoutBuyer}?${queryString}` : pathWithoutBuyer;
  return targetUrl !== currentUrl ? targetUrl : null;
}

