"use client";

import { useEffect } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useAccount } from "@/contexts/account-context";
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

  // URL -> context
  useEffect(() => {
    if (!isScoped) return;
    if (!buyerIdInPath) return;
    if (buyerIdInPath === selectedBuyerId) return;
    setSelectedBuyerId(buyerIdInPath);
  }, [buyerIdInPath, isScoped, selectedBuyerId, setSelectedBuyerId]);

  // context -> URL  (also updates URL when context was corrected, e.g. by
  // seats validation removing a buyer the user no longer has access to)
  useEffect(() => {
    if (!isScoped) return;
    if (!selectedBuyerId) return;
    if (buyerIdInPath === selectedBuyerId) return;

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

