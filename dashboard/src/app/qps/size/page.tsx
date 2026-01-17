"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams, useRouter } from "next/navigation";
import { SizeAnalysisSection } from "@/components/waste-analyzer";
import { getSeats } from "@/lib/api";
import { useAccount } from "@/contexts/account-context";
import { useTranslation } from "@/contexts/i18n-context";

const PERIOD_OPTIONS = [
  { value: 7, label: "7 days" },
  { value: 14, label: "14 days" },
  { value: 30, label: "30 days" },
];

export default function SizeQpsPage() {
  const router = useRouter();
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

  const seatName = seats?.find((seat) => seat.buyer_id === selectedBuyerId)?.display_name || selectedBuyerId;

  const handleDaysChange = (newDays: number) => {
    setDays(newDays);
    const params = new URLSearchParams();
    params.set("days", String(newDays));
    router.replace(`/qps/size?${params.toString()}`, { scroll: false });
  };

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t.qpsNav.size}</h1>
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

      <SizeAnalysisSection days={days} buyerId={selectedBuyerId || undefined} />
    </div>
  );
}
