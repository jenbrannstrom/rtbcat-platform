"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/**
 * Redirect /uploads to /import
 * The uploads functionality has been consolidated into the Import page.
 */
export default function UploadsPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/import");
  }, [router]);

  return (
    <div className="p-6 flex items-center justify-center min-h-[400px]">
      <p className="text-gray-500">Redirecting to Import...</p>
    </div>
  );
}
