'use client';

import { useEffect, useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';

/**
 * First run check for OAuth2 Proxy setup.
 *
 * With OAuth2 Proxy (Google Auth):
 * - Users are already authenticated before reaching the app
 * - GCP deployments use the VM's attached service account via ADC
 * - Only check if API credentials are configured
 */

const SETUP_PATHS = ['/connect', '/setup', '/settings'];

export function FirstRunCheck({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    // Don't redirect if already on setup/settings pages
    if (SETUP_PATHS.some(p => pathname?.startsWith(p))) {
      setChecked(true);
      return;
    }

    // Check if API is configured
    async function checkSetup() {
      try {
        // Check if API credentials are configured
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
