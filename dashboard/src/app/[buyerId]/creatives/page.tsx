import { redirect } from "next/navigation";

export default async function BuyerCreativesRedirectPage({
  params,
}: {
  params: Promise<{ buyerId: string }>;
}) {
  const { buyerId } = await params;
  redirect(`/${encodeURIComponent(buyerId)}/clusters`);
}

