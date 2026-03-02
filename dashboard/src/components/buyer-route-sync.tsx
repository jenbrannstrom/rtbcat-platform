"use client";

import { useEffect, useMemo } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useAccount } from "@/contexts/account-context";
import { getSeats } from "@/lib/api";
import {
  isBuyerScopedPath,
  replaceBuyerInPath,
  splitBuyerPath,
} from "@/lib/buyer-routes";
import { resolveCanonicalBuyerId } from "@/lib/buyer-context-sync";

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
    if (!isScoped) return;
    if (!canonicalBuyerResolution.seatsLoaded) {
      // Before seats resolve, allow URL buyer to seed context optimistically.
      if (!buyerIdInPath || buyerIdInPath === selectedBuyerId) return;
      setSelectedBuyerId(buyerIdInPath);
      return;
    }
    if (canonicalBuyerResolution.canonicalBuyerId === selectedBuyerId) return;
    setSelectedBuyerId(canonicalBuyerResolution.canonicalBuyerId);
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
    if (!isScoped) return;

    if (!canonicalBuyerResolution.seatsLoaded) {
      // Before seats resolve, do not override explicit buyer prefixes in URL.
      if (!selectedBuyerId || buyerIdInPath) return;
      const targetPath = replaceBuyerInPath(pathname, selectedBuyerId);
      const targetUrl = queryString ? `${targetPath}?${queryString}` : targetPath;
      if (targetUrl !== currentUrl) {
        router.replace(targetUrl, { scroll: false });
      }
      return;
    }

    const targetPath = replaceBuyerInPath(pathname, canonicalBuyerResolution.canonicalBuyerId);
    const targetUrl = queryString ? `${targetPath}?${queryString}` : targetPath;
    if (targetUrl !== currentUrl) {
      router.replace(targetUrl, { scroll: false });
    }
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
    if (!buyerIdInPath || isScoped) return;
    const targetUrl = queryString ? `${pathWithoutBuyer}?${queryString}` : pathWithoutBuyer;
    if (targetUrl !== currentUrl) {
      router.replace(targetUrl, { scroll: false });
    }
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
