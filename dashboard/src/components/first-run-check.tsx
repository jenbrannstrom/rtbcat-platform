'use client';

import { useEffect, useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';

const SETUP_PATHS = ['/connect', '/setup'];

export function FirstRunCheck({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    // Don't redirect if already on setup page
    if (SETUP_PATHS.some(p => pathname?.startsWith(p))) {
      setChecked(true);
      return;
    }

    // Check if configured
    async function checkConfig() {
      try {
        const res = await fetch('http://localhost:8000/health');
        const data = await res.json();

        // If not configured or no credentials, redirect to connect
        if (!data.configured || !data.has_credentials) {
          router.push('/connect');
          return;
        }
      } catch (e) {
        // API not running - let the page handle the error
        console.error('API health check failed:', e);
      } finally {
        setChecked(true);
      }
    }

    checkConfig();
  }, [pathname, router]);

  // Show loading while checking (prevents flash)
  if (!checked) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-900">
        <div className="text-gray-400">Loading...</div>
      </div>
    );
  }

  return <>{children}</>;
}
