"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams, useRouter, usePathname } from "next/navigation";
import { GeoAnalysisSection } from "@/components/waste-analyzer";
import { getRTBFunnel, getSeats } from "@/lib/api";
import { useAccount } from "@/contexts/account-context";
import { useTranslation } from "@/contexts/i18n-context";
import { HelpLink } from "@/components/docs/help-link";

const PERIOD_OPTIONS = [
  { value: 7, label: "7 days" },
  { value: 14, label: "14 days" },
  { value: 30, label: "30 days" },
];

export default function GeoQpsPage() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { selectedBuyerId, setSelectedBuyerId } = useAccount();
  const { t } = useTranslation();

  const initialDays = parseInt(searchParams.get("days") || "7", 10);
  const [days, setDays] = useState<number>(initialDays);

  const { data: seats } = useQuery({
    queryKey: ["seats"],
    queryFn: () => getSeats({ active_only: true }),
  });

  useEffect(() => {
    if (!selectedBuyerId && seats && seats.length > 0) {
      setSelectedBuyerId(seats[0].buyer_id);
    }
  }, [selectedBuyerId, seats, setSelectedBuyerId]);

  const { data: funnel, isLoading } = useQuery({
    queryKey: ["rtb-funnel", days, selectedBuyerId],
    queryFn: () => getRTBFunnel(days, selectedBuyerId || undefined),
    enabled: !!selectedBuyerId,
  });

  const seatName = seats?.find((seat) => seat.buyer_id === selectedBuyerId)?.display_name || selectedBuyerId;

  const handleDaysChange = (newDays: number) => {
    setDays(newDays);
    const params = new URLSearchParams();
    params.set("days", String(newDays));
    const targetPath = pathname || "/qps/geo";
    router.replace(`${targetPath}?${params.toString()}`, { scroll: false });
  };

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">{t.qpsNav.geo} <HelpLink chapter="04-analyzing-waste" /></h1>
          <p className="text-sm text-gray-500">
            {seatName ? `for ${seatName}` : t.common.loading}
          </p>
        </div>
        <select
          value={days}
          onChange={(e) => handleDaysChange(parseInt(e.target.value, 10))}
          className="border rounded-md px-2 py-1 text-sm"
        >
          {PERIOD_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>{option.label}</option>
          ))}
        </select>
      </div>

      {isLoading ? (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <div className="animate-pulse space-y-4">
            <div className="h-6 bg-gray-200 rounded w-1/3" />
            <div className="h-32 bg-gray-100 rounded" />
          </div>
        </div>
      ) : (
        <GeoAnalysisSection
          geos={funnel?.geos || []}
          seatName={seatName || undefined}
        />
      )}
    </div>
  );
}
