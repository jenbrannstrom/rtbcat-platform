import { redirect } from "next/navigation";

export default async function BuyerWasteAnalysisRedirectPage({
  params,
}: {
  params: Promise<{ buyerId: string }>;
}) {
  const { buyerId } = await params;
  redirect(`/${encodeURIComponent(buyerId)}`);
}

