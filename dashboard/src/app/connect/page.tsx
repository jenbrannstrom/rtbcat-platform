"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function ConnectRedirect() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/settings/accounts");
  }, [router]);

  return (
    <div className="p-8 flex items-center justify-center min-h-[400px]">
      <p className="text-gray-500">Redirecting to Settings...</p>
    </div>
  );
}
