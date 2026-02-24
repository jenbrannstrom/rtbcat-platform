"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useTranslation } from "@/contexts/i18n-context";

export default function AdminSettingsRedirect() {
  const router = useRouter();
  const { t } = useTranslation();

  useEffect(() => {
    router.replace("/admin/configuration");
  }, [router]);

  return (
    <div className="p-8 flex items-center justify-center min-h-[400px]">
      <p className="text-gray-500">{t.admin.redirectingToConfiguration}</p>
    </div>
  );
}
