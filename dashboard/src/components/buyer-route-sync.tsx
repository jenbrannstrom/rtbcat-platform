"use client";

import { useEffect, useMemo } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useAccount } from "@/contexts/account-context";
import { getSeats } from "@/lib/api";
import {
  isBuyerScopedPath,
  splitBuyerPath,
} from "@/lib/buyer-routes";
import { resolveCanonicalBuyerId } from "@/lib/buyer-context-sync";
import {
  getBuyerContextUpdateTarget,
  getBuyerScopedRouteReplaceTarget,
  getNonScopedRouteCleanupTarget,
} from "@/lib/buyer-route-sync-logic";

export function BuyerRouteSync() {
  const pathname = usePathname() || "/";
  const searchParams = useSearchParams();
  const router = useRouter();
  const { selectedBuyerId, setSelectedBuyerId } = useAccount();

  const { buyerIdInPath, pathWithoutBuyer } = splitBuyerPath(pathname);
  const isScoped = isBuyerScopedPath(pathWithoutBuyer);
  const queryString = searchParams.toString();
  const currentUrl = queryString ? `${pathname}?${queryString}` : pathname;

  // Share the same seats query cache as the home page (staleTime: 60s there)
  const { data: seats } = useQuery({
    queryKey: ["seats"],
    queryFn: () => getSeats({ active_only: true }),
    staleTime: 60_000,
  });

  const canonicalBuyerResolution = useMemo(
    () =>
      resolveCanonicalBuyerId({
        buyerIdInPath,
        selectedBuyerId,
        seats,
      }),
    [buyerIdInPath, selectedBuyerId, seats]
  );

  // Keep account context aligned with canonical seat selection.
  useEffect(() => {
    const targetBuyerId = getBuyerContextUpdateTarget({
      isScoped,
      seatsLoaded: canonicalBuyerResolution.seatsLoaded,
      buyerIdInPath,
      selectedBuyerId,
      canonicalBuyerId: canonicalBuyerResolution.canonicalBuyerId,
    });
    if (targetBuyerId === null) return;
    setSelectedBuyerId(targetBuyerId);
  }, [
    buyerIdInPath,
    canonicalBuyerResolution.canonicalBuyerId,
    canonicalBuyerResolution.seatsLoaded,
    isScoped,
    selectedBuyerId,
    setSelectedBuyerId,
  ]);

  // Keep URL aligned with canonical seat selection.
  useEffect(() => {
    const targetUrl = getBuyerScopedRouteReplaceTarget({
      isScoped,
      seatsLoaded: canonicalBuyerResolution.seatsLoaded,
      buyerIdInPath,
      selectedBuyerId,
      pathname,
      queryString,
      currentUrl,
      canonicalBuyerId: canonicalBuyerResolution.canonicalBuyerId,
    });
    if (targetUrl === null) return;
    router.replace(targetUrl, { scroll: false });
  }, [
    buyerIdInPath,
    currentUrl,
    isScoped,
    pathname,
    queryString,
    router,
    canonicalBuyerResolution.canonicalBuyerId,
    canonicalBuyerResolution.seatsLoaded,
    selectedBuyerId,
  ]);

  // Clean accidental buyer prefix on non-scoped pages
  useEffect(() => {
    const targetUrl = getNonScopedRouteCleanupTarget({
      buyerIdInPath,
      isScoped,
      pathWithoutBuyer,
      queryString,
      currentUrl,
    });
    if (targetUrl === null) return;
    router.replace(targetUrl, { scroll: false });
  }, [
    buyerIdInPath,
    currentUrl,
    isScoped,
    pathWithoutBuyer,
    queryString,
    router,
  ]);

  return null;
}
