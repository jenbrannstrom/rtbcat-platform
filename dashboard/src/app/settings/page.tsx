"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Users, Clock, Activity, Link2, ChevronRight, CheckCircle, XCircle } from "lucide-react";
import { getHealth, getSeats } from "@/lib/api";
import { useTranslation } from "@/contexts/i18n-context";

export default function SettingsPage() {
  const { t } = useTranslation();

  const { data: health } = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
  });

  const { data: seats } = useQuery({
    queryKey: ["seats"],
    queryFn: () => getSeats({ active_only: true }),
    enabled: health?.configured === true,
  });

  const settingsCards = [
    {
      title: t.settingsNav.connectedAccounts,
      description: health?.configured
        ? t.settings.manageConnection
        : t.settings.connectAccount,
      href: "/settings/accounts",
      icon: Link2,
      status: health?.configured ? (
        <span className="text-xs font-medium text-green-600 bg-green-50 px-2 py-1 rounded flex items-center gap-1">
          <CheckCircle className="h-3 w-3" />
          {t.settings.connected}
        </span>
      ) : (
        <span className="text-xs font-medium text-yellow-600 bg-yellow-50 px-2 py-1 rounded flex items-center gap-1">
          <XCircle className="h-3 w-3" />
          {t.settings.notConnected}
        </span>
      ),
    },
    {
      title: t.settingsNav.buyerSeats,
      description: t.settings.manageSeatDisplayNames,
      href: "/settings/seats",
      icon: Users,
      status: seats && seats.length > 0 ? (
        <span className="text-xs font-medium text-gray-600 bg-gray-100 px-2 py-1 rounded">
          {seats.length} {t.settings.seats}
        </span>
      ) : null,
    },
    {
      title: t.settingsNav.dataRetention,
      description: t.settings.configureRetention,
      href: "/settings/retention",
      icon: Clock,
      status: null,
    },
    {
      title: t.settingsNav.systemStatus,
      description: t.settings.systemConfiguration,
      href: "/settings/system",
      icon: Activity,
      status: health?.status ? (
        <span className="text-xs font-medium text-green-600 bg-green-50 px-2 py-1 rounded">
          {health.status}
        </span>
      ) : null,
    },
  ];

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">{t.settings.title}</h1>
        <p className="mt-1 text-sm text-gray-500">
          {t.settings.systemConfiguration}
        </p>
      </div>

      <div className="max-w-2xl space-y-4">
        {settingsCards.map((card) => (
          <Link
            key={card.href}
            href={card.href}
            className="block card p-4 hover:bg-gray-50 transition-colors"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center">
                <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-primary-50 flex items-center justify-center">
                  <card.icon className="h-5 w-5 text-primary-600" />
                </div>
                <div className="ml-4">
                  <h3 className="text-sm font-medium text-gray-900">{card.title}</h3>
                  <p className="text-sm text-gray-500">{card.description}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                {card.status}
                <ChevronRight className="h-5 w-5 text-gray-400" />
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
