"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function AdminSettingsRedirect() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/admin/configuration");
  }, [router]);

  return (
    <div className="p-8 flex items-center justify-center min-h-[400px]">
      <p className="text-gray-500">Redirecting to Configuration...</p>
    </div>
  );
}
