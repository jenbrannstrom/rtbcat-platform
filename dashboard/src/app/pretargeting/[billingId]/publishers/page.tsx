import { redirect } from "next/navigation";

export default async function LegacyPretargetingPublishersRedirectPage({
  params,
}: {
  params: Promise<{ billingId: string; buyerId?: string }>;
}) {
  const { billingId, buyerId } = await params;
  const encodedBillingId = encodeURIComponent(billingId);
  const basePath = `/bill_id/${encodedBillingId}?tab=publishers`;

  if (buyerId) {
    redirect(`/${encodeURIComponent(buyerId)}${basePath}`);
  }

  redirect(basePath);
}

