"use client";

import { useEffect } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useAccount } from "@/contexts/account-context";
import { getSeats } from "@/lib/api";
import {
  isBuyerScopedPath,
  replaceBuyerInPath,
  splitBuyerPath,
} from "@/lib/buyer-routes";

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

  // URL -> context: only sync if the buyer_id in the URL is a valid seat
  // (or if seats haven't loaded yet, allow it so initial nav still works)
  useEffect(() => {
    if (!isScoped) return;
    if (!buyerIdInPath) return;
    if (buyerIdInPath === selectedBuyerId) return;
    // Once seats are known, don't sync a revoked buyer_id into context
    if (seats && !seats.some((s) => s.buyer_id === buyerIdInPath)) return;
    setSelectedBuyerId(buyerIdInPath);
  }, [buyerIdInPath, isScoped, selectedBuyerId, setSelectedBuyerId, seats]);

  // context -> URL: update URL when context differs (e.g. after RBAC correction)
  useEffect(() => {
    if (!isScoped) return;
    if (!selectedBuyerId) return;
    if (buyerIdInPath === selectedBuyerId) return;

    // If the URL already has a buyer seat, prefer the URL as source-of-truth
    // unless that buyer becomes invalid (e.g. RBAC revoked). This avoids a
    // race where a seat switch navigation briefly lands on /<newBuyer>/... and
    // the old context value immediately rewrites it back.
    if (buyerIdInPath) {
      if (!seats) return;
      const buyerInPathIsValid = seats.some((s) => s.buyer_id === buyerIdInPath);
      if (buyerInPathIsValid) return;

      // If both URL buyer and selected buyer are invalid, wait for the pages
      // that normalize selection to resolve a valid seat.
      const selectedBuyerIsValid = seats.some((s) => s.buyer_id === selectedBuyerId);
      if (!selectedBuyerIsValid) return;
    }

    const targetPath = replaceBuyerInPath(pathname, selectedBuyerId);
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
    selectedBuyerId,
    seats,
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
