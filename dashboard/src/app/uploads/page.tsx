"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAccount } from "@/contexts/account-context";
import { useTranslation } from "@/contexts/i18n-context";
import { splitBuyerPath, toBuyerScopedPath } from "@/lib/buyer-routes";

/**
 * Redirect /uploads to /import
 * The uploads functionality has been consolidated into the Import page.
 */
export default function UploadsPage() {
  const router = useRouter();
  const pathname = usePathname();
  const { selectedBuyerId } = useAccount();
  const { t } = useTranslation();
  const { buyerIdInPath } = splitBuyerPath(pathname || "/");

  useEffect(() => {
    const targetPath = toBuyerScopedPath("/import", buyerIdInPath || selectedBuyerId);
    router.replace(targetPath);
  }, [buyerIdInPath, router, selectedBuyerId]);

  return (
    <div className="p-6 flex items-center justify-center min-h-[400px]">
      <p className="text-gray-500">
        {t.common.redirectingTo.replace("{destination}", t.navigation.import)}
      </p>
    </div>
  );
}
