/**
 * Helper functions for campaigns page.
 */

/**
 * Format a bundle ID like com.example.myapp into "Example Myapp"
 */
export function formatBundleId(bundleId: string): string {
  // Split by dots and take the last 2 parts (skip com/org/etc)
  const parts = bundleId.split('.');
  const relevantParts = parts.length > 2 ? parts.slice(-2) : parts;

  return relevantParts
    .map(part =>
      part
        .replace(/([a-z])([A-Z])/g, '$1 $2') // Split camelCase
        .replace(/[_-]/g, ' ')
        .replace(/\b\w/g, c => c.toUpperCase())
    )
    .join(' ');
}

/**
 * Generate a clean cluster name from a URL/domain
 * - Decodes URL-encoded strings
 * - Extracts bundle IDs from AppsFlyer/Adjust URLs
 * - Formats com.app.name as "App Name"
 * - Handles Play Store, App Store, Firebase URLs
 */
export function generateClusterName(url: string | null): string {
  if (!url) return 'Unknown';

  try {
    // Decode URL-encoded strings
    let decoded = decodeURIComponent(url);

    // Extract bundle ID from AppsFlyer URLs
    // e.g., https://app.appsflyer.com/com.example.app?pid=...
    const appsFlyerMatch = decoded.match(/app\.appsflyer\.com\/([a-zA-Z0-9._-]+)/);
    if (appsFlyerMatch) {
      return formatBundleId(appsFlyerMatch[1]);
    }

    // Extract from Adjust URLs
    // e.g., https://app.adjust.com/abc123?campaign=...
    const adjustMatch = decoded.match(/adjust\.com.*[?&]campaign=([^&]+)/i);
    if (adjustMatch) {
      return decodeURIComponent(adjustMatch[1]).replace(/[_-]/g, ' ');
    }

    // Extract from Play Store URLs
    // e.g., https://play.google.com/store/apps/details?id=com.example.app
    const playStoreMatch = decoded.match(/play\.google\.com\/store\/apps\/details\?id=([a-zA-Z0-9._-]+)/);
    if (playStoreMatch) {
      return formatBundleId(playStoreMatch[1]);
    }

    // Extract from App Store URLs
    // e.g., https://apps.apple.com/app/app-name/id123456789
    const appStoreMatch = decoded.match(/apps\.apple\.com\/[^/]+\/app\/([^/]+)/);
    if (appStoreMatch) {
      return appStoreMatch[1].replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    }

    // Extract from Firebase Dynamic Links
    const firebaseMatch = decoded.match(/\.page\.link.*[?&]link=([^&]+)/);
    if (firebaseMatch) {
      return generateClusterName(decodeURIComponent(firebaseMatch[1]));
    }

    // If it looks like a bundle ID (com.something.app)
    if (/^[a-z][a-z0-9]*(\.[a-z][a-z0-9]*)+$/i.test(decoded)) {
      return formatBundleId(decoded);
    }

    // Try to extract domain name
    const domainMatch = decoded.match(/(?:https?:\/\/)?(?:www\.)?([^\/\?]+)/);
    if (domainMatch) {
      const domain = domainMatch[1];
      // Clean up domain - remove .com, .io, etc. and format
      const cleanDomain = domain
        .replace(/\.(com|io|app|net|org|co)$/i, '')
        .replace(/[._-]/g, ' ')
        .replace(/\b\w/g, c => c.toUpperCase());
      return cleanDomain || domain;
    }

    return url.substring(0, 30);
  } catch {
    return url.substring(0, 30);
  }
}
