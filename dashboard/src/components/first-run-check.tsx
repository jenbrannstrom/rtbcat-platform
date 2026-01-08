'use client';

import { useEffect, useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';

const SETUP_PATHS = ['/connect', '/setup', '/initial-setup', '/login', '/change-password'];

export function FirstRunCheck({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    // Don't redirect if already on setup/auth pages
    if (SETUP_PATHS.some(p => pathname?.startsWith(p))) {
      setChecked(true);
      return;
    }

    // Check if initial setup is required (no users exist)
    async function checkSetup() {
      try {
        // First check if initial setup is needed
        const setupRes = await fetch('/api/auth/setup/status');
        if (setupRes.ok) {
          const setupData = await setupRes.json();
          if (setupData.setup_required) {
            router.push('/initial-setup');
            return;
          }
        }

        // Then check if API is configured (has credentials)
        const res = await fetch('/api/health');
        const data = await res.json();

        // If not configured or no credentials, redirect to connect
        if (!data.configured || !data.has_credentials) {
          router.push('/connect');
          return;
        }
      } catch (e) {
        // API not running - let the page handle the error
        console.error('API check failed:', e);
      } finally {
        setChecked(true);
      }
    }

    checkSetup();
  }, [pathname, router]);

  // Show loading while checking (prevents flash)
  if (!checked) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-gray-500">Loading...</div>
      </div>
    );
  }

  return <>{children}</>;
}
