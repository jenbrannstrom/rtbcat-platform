"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { PretargetingSettingsEditor } from "@/components/rtb/pretargeting-settings-editor";
import { useAccount } from "@/contexts/account-context";
import { toBuyerScopedPath } from "@/lib/buyer-routes";

export default function PretargetingBillingDetailPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const { selectedBuyerId } = useAccount();

  const billingId = typeof params?.billingId === "string" ? params.billingId : "";
  const buyerIdFromParams = typeof params?.buyerId === "string" ? params.buyerId : null;
  const backHref = toBuyerScopedPath("/", buyerIdFromParams || selectedBuyerId);

  const requestedTab = searchParams.get("tab");
  const initialTab = requestedTab === "publishers" ? "publishers" : "settings";

  if (!billingId) {
    return (
      <div className="p-6">
        <div className="rounded border bg-white p-6 text-sm text-gray-500">
          Missing pretargeting config ID (billing_id).
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between gap-3">
        <Link
          href={backHref}
          className="inline-flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to configs
        </Link>
        <span className="text-xs text-gray-500 font-mono">{billingId}</span>
      </div>
      <PretargetingSettingsEditor
        billing_id={billingId}
        initialTab={initialTab}
      />
    </div>
  );
}
